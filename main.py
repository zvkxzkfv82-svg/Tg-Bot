import os
import re
import time
import zipfile
import datetime
import smtplib
from email.message import EmailMessage
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

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")

# =========================
# MEMORY (альбомы)
# =========================

albums = defaultdict(list)
album_time = {}

# =========================
# UTILS
# =========================

def extract_number(text: str):
    match = re.search(r"\d{3}-?\d{5}", text)
    if not match:
        return None
    return match.group(0).replace("-", "")

def send_email(subject, zip_path):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO
    msg.set_content("Архив с фото во вложении")

    with open(zip_path, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="zip",
            filename=os.path.basename(zip_path),
        )

    with smtplib.SMTP_SSL("smtp.yandex.ru", 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)

# =========================
# CORE PROCESSING
# =========================

async def process_and_send(photos, number, context, update):
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    folder_name = f"{date}_вагон_{number}"

    zip_path = f"/tmp/{folder_name}.zip"

    with zipfile.ZipFile(zip_path, "w") as zipf:
        for i, photo in enumerate(photos):
            file = await context.bot.get_file(photo.file_id)

            file_path = f"/tmp/{photo.file_id}.jpg"
            await file.download_to_drive(file_path)

            zipf.write(file_path, arcname=f"{i+1}.jpg")

    send_email(folder_name, zip_path)

    if update:
        await update.message.reply_text("Я все сохранил!")

# =========================
# HANDLER: PHOTO
# =========================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if not message.photo:
        return

    number = None
    if message.caption:
        number = extract_number(message.caption)

    if not number:
        return

    await message.reply_text("Увидел, принял в работу!")

    group_id = message.media_group_id

    # если альбом
    if group_id:
        albums[group_id].append(message.photo[-1])
        album_time[group_id] = time.time()
        return

    # одиночное фото
    await process_and_send([message.photo[-1]], number, context, update)

# =========================
# FLUSH ALBUMS (сбор альбомов)
# =========================

async def flush_albums(context: ContextTypes.DEFAULT_TYPE):
    now = time.time()
    to_remove = []

    for group_id, photos in albums.items():
        if now - album_time[group_id] < 3:
            continue

        if not photos:
            continue

        # номер берём из caption первого сообщения (упрощение)
        number = "00000000"

        await process_and_send(photos, number, context, None)

        to_remove.append(group_id)

    for gid in to_remove:
        albums.pop(gid, None)
        album_time.pop(gid, None)

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Я запущен и работаю в группе 🤖")

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # периодическая проверка альбомов
    job_queue = app.job_queue
    job_queue.run_repeating(flush_albums, interval=3)

    app.run_polling()

if __name__ == "__main__":
    main()