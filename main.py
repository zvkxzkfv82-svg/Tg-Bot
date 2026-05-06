import os
import re
import zipfile
import datetime
import asyncio
import time

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
album_timers = {}

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

async def process_and_send(photos, number, update, context):
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

    user_id = update.effective_user.id if update else stats_chat_id

    if user_id:
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

    # альбом: копим
    albums[group_id].append(message.photo[-1])
    album_numbers[group_id] = number
    album_timers[group_id] = time.time()

# =========================
# ALBUM WATCHER (DEBOUNCE ENGINE)
# =========================

async def album_watcher(app):
    while True:
        await asyncio.sleep(1)

        now = time.time()

        for group_id in list(albums.keys()):
            last_time = album_timers.get(group_id)

            # если 2 секунды тишины → финал
            if last_time and now - last_time > 2:
                photos = albums[group_id]
                number = album_numbers.get(group_id)

                if photos and number:
                    await process_and_send(photos, number, None, app)

                albums.pop(group_id, None)
                album_numbers.pop(group_id, None)
                album_timers.pop(group_id, None)

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
# POST INIT (ПРАВИЛЬНЫЙ СПОСОБ)
# =========================

async def post_init(app):
    asyncio.create_task(stats_loop(app))
    asyncio.create_task(album_watcher(app))

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