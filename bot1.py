import os
import yt_dlp
import instaloader
import ffmpeg
import requests  # Для работы с HTTP-запросами
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv  # Импортируем функцию для загрузки переменных из .env

# Загружаем переменные окружения из файла .env
load_dotenv(dotenv_path="config.env")

# Получаем токен из переменной окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    print("Ошибка: Токен не найден!")
    exit(1)

# Удаление существующего файла
def safe_remove(filepath):
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        print(f"Ошибка удаления файла {filepath}: {e}")

# Скачивание видео с Instagram
def download_instagram_video(url):
    loader = instaloader.Instaloader()
    try:
        shortcode = url.split("/")[-2]
        post = instaloader.Post.from_shortcode(loader.context, shortcode)

        if post.is_video:
            video_url = post.video_url
            response = requests.get(video_url)

            file_path = f"downloads/instagram_video_{shortcode}.mp4"
            os.makedirs("downloads", exist_ok=True)  # Создаём папку, если её нет
            safe_remove(file_path)  # Удаляем старый файл, если он есть
            with open(file_path, "wb") as f:
                f.write(response.content)
            return file_path
        else:
            return None
    except Exception as e:
        print(f"Ошибка Instagram: {e}")
        return None

# Скачивание видео с YouTube
def download_youtube_video(url):
    output_template = "downloads/youtube_video_%(id)s.%(ext)s"
    ydl_opts = {
        'format': 'best',
        'outtmpl': output_template,  # Уникальное имя файла для каждого видео
        'noplaylist': True,  # Скачиваем только одно видео
        'quiet': True,  # Отключение интерактивного ввода
        'force_overwrites': True,  # Всегда перезаписывать существующие файлы
    }
    try:
        os.makedirs("downloads", exist_ok=True)  # Создаём папку, если её нет
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info_dict)  # Генерация пути скачанного файла

            # Конвертируем файл в mp4, если он в формате webm
            if downloaded_file.endswith('.webm'):
                mp4_file = downloaded_file.replace('.webm', '.mp4')
                safe_remove(mp4_file)  # Удаляем предыдущую mp4-версию, если она существует
                ffmpeg.input(downloaded_file).output(mp4_file).run(overwrite_output=True)
                safe_remove(downloaded_file)  # Удаляем оригинальный webm файл
                return mp4_file

            return downloaded_file
    except Exception as e:
        print(f"Ошибка YouTube: {e}")
        return None

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Отправь ссылку на видео с YouTube или Instagram, и я попробую скачать его для тебя."
    )

# Обработчик сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "youtube.com" in url or "youtu.be" in url:
        await update.message.reply_text("Скачиваю видео с YouTube...")
        video_path = download_youtube_video(url)
        if video_path:
            await update.message.reply_video(video=open(video_path, 'rb'))
            safe_remove(video_path)  # Удаляем видео после отправки
        else:
            await update.message.reply_text("Не удалось скачать видео с YouTube.")
    elif "instagram.com" in url:
        await update.message.reply_text("Скачиваю видео с Instagram...")
        video_path = download_instagram_video(url)
        if video_path:
            await update.message.reply_video(video=open(video_path, 'rb'))
            safe_remove(video_path)  # Удаляем видео после отправки
        else:
            await update.message.reply_text("Не удалось скачать видео с Instagram.")
    else:
        await update.message.reply_text("Ссылка не поддерживается. Попробуйте ещё раз.")

# Основная функция
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == "__main__":
    main()
