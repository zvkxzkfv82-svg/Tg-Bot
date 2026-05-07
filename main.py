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
OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID", "0"))

# =========================
# STATE
# =========================

album_buffer = defaultdict(lambda: {
    "photos": {},
    "number": None
})

album_last_update = {}
processed_albums = set()

queue = asyncio.Queue()

processed_count = 0

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

async def process_and_send(photos, number, context):
    global processed_count

    try:
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        folder_name = f"{date}_вагон_{number or 'unknown'}"

        zip_path = f"/tmp/{folder_name}.zip"

        # создаем zip
        with zipfile.ZipFile(zip_path, "w") as zipf:

            for i, photo in enumerate(photos):

                file = await context.bot.get_file(photo.file_id)

                file_path = f"/tmp/{photo.file_id}.jpg"

                await file.download_to_drive(file_path)

                zipf.write(
                    file_path,
                    arcname=f"{i+1}.jpg"
                )

        # отправка владельцу
        with open(zip_path, "rb") as f:

            await context.bot.send_document(
                chat_id=OWNER_CHAT_ID,
                document=f,
                filename=f"{folder_name}.zip",
                caption=f"📦 {folder_name}",
                read_timeout=120,
                write_timeout=120,
                connect_timeout=60,
            )

        processed_count += 1

        print(f"✅ SENT: {folder_name}")

    except Exception as e:
        print("❌ SEND ERROR:", repr(e))

# =========================
# WORKER
# =========================

async def worker(app):

    while True:

        photos, number = await queue.get()

        try:
            await process_and_send(
                photos,
                number,
                app
            )

        except Exception as e:
            print("❌ WORKER ERROR:", repr(e))

        queue.task_done()

# =========================
# PHOTO HANDLER
# =========================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    msg = update.message

    if not msg.photo:
        return

    group_id = msg.media_group_id
    photo = msg.photo[-1]

    number = extract_number(msg.caption)

    # =====================
    # ОДИНОЧНОЕ ФОТО
    # =====================

    if not group_id:

        if number:
            await queue.put(([photo], number))

        return

    # =====================
    # АЛЬБОМ
    # =====================

    album = album_buffer[group_id]

    album["photos"][photo.file_id] = photo

    # сохраняем номер
    if number and not album["number"]:
        album["number"] = number

    album_last_update[group_id] = time.time()

# =========================
# ALBUM WATCHER
# =========================

async def album_watcher(app):

    while True:

        await asyncio.sleep(1)

        now = time.time()

        for gid in list(album_buffer.keys()):

            # защита от дублей
            if gid in processed_albums:

                album_buffer.pop(gid, None)
                album_last_update.pop(gid, None)

                continue

            last = album_last_update.get(gid, 0)

            # 1 фаза: 6 сек тишины
            if now - last < 6:
                continue

            album = album_buffer.get(gid, {})

            photos_dict = album.get("photos", {})

            if not photos_dict:
                continue

            size1 = len(photos_dict)

            # 2 фаза: стабилизация
            await asyncio.sleep(2)

            album2 = album_buffer.get(gid, {})

            photos_dict2 = album2.get("photos", {})

            size2 = len(photos_dict2)

            if size1 != size2:
                continue

            photos = list(photos_dict2.values())

            if not photos:
                continue

            number = album2.get("number")

            # помечаем как обработанный
            processed_albums.add(gid)

            # в очередь
            await queue.put((photos, number))

            # cleanup
            album_buffer.pop(gid, None)
            album_last_update.pop(gid, None)

# =========================
# STATS LOOP
# =========================

async def stats_loop(app):

    global processed_count

    while True:

        await asyncio.sleep(1800)

        if processed_count == 0:
            continue

        try:

            await app.bot.send_message(
                chat_id=OWNER_CHAT_ID,
                text=f"📊 За 30 минут обработано: {processed_count} вагонов"
            )

            processed_count = 0

        except Exception as e:
            print("❌ STATS ERROR:", repr(e))

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.is_bot:
        return
        
    print(update.effective_user.id)

    await update.message.reply_text(
        "🤖 Бот работает"
    )

# =========================
# POST INIT
# =========================

async def post_init(app):

    # watcher
    asyncio.create_task(
        album_watcher(app)
    )

    # stats
    asyncio.create_task(
        stats_loop(app)
    )

    # workers
    for _ in range(2):

        asyncio.create_task(
            worker(app)
        )

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

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_photo
        )
    )

    print("🚀 BOT STARTED")

    app.run_polling()

# =========================
# RUN
# =========================

if __name__ == "__main__":
    main()