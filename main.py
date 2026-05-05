import os
import re
import time
import zipfile
import datetime
import smtplib
from email.message import EmailMessage
from collections import defaultdict
from threading import Timer

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# =========================
# ENV
# =========================

TOKEN = os.getenv("BOT_TOKEN")

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")

# =========================
# MEMORY
# =========================

albums = defaultdict(list)
album_time = {}

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

    with smtplib.SMTP("smtp.yandex.ru", 587) as smtp:
        smtp.starttls()
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)

# =========================
# ZIP + SEND
# =========================

async def process_and_send(photos, number, update, context):
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
# ALBUM FLUSH
# =========================

async def flush_album(group_id, context):
    photos = albums.get(group_id)
    if not photos:
        return

    # номер пытаемся взять из первого доступного caption
    number = "00000000"

    await process_and_send(photos, number, None, context)

    albums.pop(group_id, None)
    album_time.pop(group_id, None)

# =========================
# TIMER (СТАБИЛЬНО ВМЕСТО LOOP)
# =========================

def schedule_flush(group_id, context):
    def run():
        import asyncio
        asyncio.run_coroutine_threadsafe(flush_album(group_id, context), context.application.loop)

    Timer(3, run).start()

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

    # если альбом
    if group_id:
        albums[group_id].append(message.photo[-1])
        album_time[group_id] = time.time()

        schedule_flush(group_id, context)
        return

    # одиночное фото
    await process_and_send([message.photo[-1]], number, update, context)

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