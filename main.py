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
# MEMORY
# =========================

albums = defaultdict(list)
album_numbers = {}

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
# ZIP + SEND TO TELEGRAM
# =========================

async def process_and_send(photos, number, update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    folder_name = f"{date}_вагон_{number}"
    zip_path = f"/tmp/{folder_name}.zip"

    # создаём архив
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for i, photo in enumerate(photos):
            file = await context.bot.get_file(photo.file_id)

            file_path = f"/tmp/{photo.file_id}.jpg"
            await file.download_to_drive(file_path)

            zipf.write(file_path, arcname=f"{i+1}.jpg")

    # отправка в Telegram (в ЛИЧКУ пользователя)
    user_id = update.effective_user.id

    await context.bot.send_document(
        chat_id=user_id,
        document=open(zip_path, "rb"),
        filename=f"{folder_name}.zip",
        caption="📦 Готово, архив собран"
    )

    await update.message.reply_text("Я все сохранил!")

# =========================
# ALBUM HANDLING
# =========================

async def flush_album(group_id, context):
    photos = albums.get(group_id)
    number = album_numbers.get(group_id)

    if not photos or not number:
        albums.pop(group_id, None)
        album_numbers.pop(group_id, None)
        return

    # fake update не нужен — берём context.bot.send_document через user_id позже
    await process_and_send(
        photos,
        number,
        albums[group_id]["update"],
        context
    )

    albums.pop(group_id, None)
    album_numbers.pop(group_id, None)

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

    await message.reply_text("Увидел, принял в работу!")

    group_id = message.media_group_id

    # одиночное фото
    if not group_id:
        await process_and_send([message.photo[-1]], number, update, context)
        return

    # альбом
    albums[group_id].append(message.photo[-1])
    album_numbers[group_id] = number
    albums[group_id] = {"update": update}

    # небольшая задержка перед финализацией
    await asyncio.sleep(3)

    photos = albums[group_id]
    await process_and_send(photos, number, update, context)

    albums.pop(group_id, None)
    album_numbers.pop(group_id, None)

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот работает 🤖")

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    app.run_polling()

# =========================
# RUN
# =========================

if __name__ == "__main__":
    main()