import os
import re
import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")

# извлечение номера
def extract_number(text: str):
    match = re.search(r"\d{3}-?\d{5}", text)
    if not match:
        return None
    return match.group(0).replace("-", "")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if not message.photo or not message.caption:
        return

    number = extract_number(message.caption)
    if not number:
        return

    await message.reply_text("Увидел, принял в работу!")

    # дата
    date = datetime.datetime.now().strftime("%Y-%m-%d")

    folder_name = f"{date}_вагон_{number}"

    # дальше тут будет Яндекс Диск логика
    print("Создать папку:", folder_name)

    await message.reply_text("Я все сохранил!")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

app.run_polling()