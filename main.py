import os
import re
import zipfile
import datetime
import asyncio

from collections import defaultdict

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# ENV
# =========================

TOKEN = os.getenv("BOT_TOKEN")

# =========================
# STATE
# =========================

albums = defaultdict(list)
album_numbers = {}

processed_count = 0
stats_chat_id = None

# =========================
# UTILS
# =========================

def extract_number(text: str):
    if not text:
        return None
    match = re.search(r"\d{3}-?\d{5}", text)
    if not match:
        return None
    return match.group(0).replace("-", "")

# =========================
# ZIP + SEND
# =========================

async def process_and_send(photos, number, update: Update, context: ContextTypes.DEFAULT_TYPE):
    global processed_count

    date = datetime.datetime.now().strftime("%Y-%m-%d")
    folder_name = f"{date}_вагон_{number}"
    zip_path = f"/tmp/{folder_name}.zip"

    with zipfile.ZipFile(zip_path, "w") as zipf:
        for i, photo in enumerate(photos):
            file = await context.bot.get_file(photo.file_id)

            file_path = f"/tmp/{photo.file_id}.jpg"
            await file.download_to_drive(file_path)

            zipf.write(file_path, arcname=f"{i+1}.jpg")

    user_id = update.effective_user.id

    await context.bot.send_document(
        chat_id=user_id,
        document=open(zip_path, "rb"),
        filename=f"{folder_name}.zip",
        caption="📦 Готово"
    )

    processed_count += 1

# =========================
# HANDLER
# =========================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if not message.photo:
        return

    number = extract_number(message.caption)

    if not number:
        return

    group_id = message.media_group_id

    # одиночное фото
    if not group_id:
        await process_and_send([message.photo[-1]], number, update, context)
        return

    # альбом
    albums[group_id].append(message.photo[-1])
    album_numbers[group_id] = number

    await asyncio.sleep(3)

    photos = albums[group_id]
    await process_and_send(photos, number, update, context)

    albums.pop(group_id, None)
    album_numbers.pop(group_id, None)

# =========================
# STATS LOOP
# =========================

async def stats_loop(app):
    global processed_count, stats_chat_id

    while True:
        await asyncio.sleep(1800)

        if processed_count == 0:
            continue

        if not stats_chat_id:
            continue

        await app.bot.send_message(
            chat_id=stats_chat_id,
            text=f"📊 За последние 30 минут обработано: {processed_count} вагонов"
        )

        processed_count = 0

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stats_chat_id

    stats_chat_id = update.effective_user.id

    await update.message.reply_text("Бот работает 🤖")

# =========================
# POST INIT (ВАЖНО)
# =========================

async def post_init(app):
    app.create_task(stats_loop(app))

# =========================
# MAIN
# =========================

def main():
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    app.run_polling()

# =========================
# RUN
# =========================

if __name__ == "__main__":
    main()