import os
import logging
import aiohttp
import asyncio
from dotenv import load_dotenv
import yt_dlp
import instaloader
from telegram import Update
from telegram.error import TimedOut
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Загружаем переменные из .env
load_dotenv()

# Получаем токен из переменной окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Проверяем, что токен загружен
if TELEGRAM_BOT_TOKEN is None:
    raise ValueError("Токен Telegram не найден. Убедитесь, что переменная TELEGRAM_BOT_TOKEN задана в .env файле.")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Новый прокси (HTTP или SOCKS5)
PROXY_HOST = "185.195.71.218"
PROXY_PORT = 35177

# Прокси для aiohttp и yt-dlp
proxy = {
    "http": f"http://{PROXY_HOST}:{PROXY_PORT}",  # HTTP прокси
    "https": f"http://{PROXY_HOST}:{PROXY_PORT}",
}

# Сайты для проверки
SITES_TO_CHECK = {
    "YouTube": "https://www.youtube.com",
    "Instagram": "https://www.instagram.com",
}

# Функция для безопасного удаления файла
def safe_remove(filepath):
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Файл {filepath} удалён.")
    except Exception as e:
        logger.error(f"Ошибка удаления файла {filepath}: {e}")

# Проверка размера файла
def check_file_size(filepath, max_size_mb=50):
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    return size_mb <= max_size_mb

# Асинхронное скачивание видео с YouTube или Instagram
async def download_video(url):
    if "youtube.com" in url or "youtu.be" in url:
        # Скачивание с YouTube
        output_template = "downloads/youtube_video_%(id)s.%(ext)s"
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',  # Скачиваем сразу в mp4
            'outtmpl': output_template,
            'noplaylist': True,
            'quiet': True,
            'force_overwrites': True,
            'proxy': proxy['http'],  # Используем прокси для yt-dlp
        }
        try:
            os.makedirs("downloads", exist_ok=True)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                downloaded_file = ydl.prepare_filename(info_dict)
                return downloaded_file
        except Exception as e:
            logger.error(f"Ошибка YouTube: {e}")
            return None

    elif "instagram.com" in url:
        # Скачивание с Instagram
        loader = instaloader.Instaloader()
        try:
            shortcode = url.split("/")[-2]
            post = instaloader.Post.from_shortcode(loader.context, shortcode)

            if post.is_video:
                video_url = post.video_url
                async with aiohttp.ClientSession() as session:
                    async with session.get(video_url, proxy=proxy['http']) as response:  # Используем прокси для aiohttp
                        if response.status == 200:
                            file_path = f"downloads/instagram_video_{shortcode}.mp4"
                            os.makedirs("downloads", exist_ok=True)
                            safe_remove(file_path)
                            with open(file_path, "wb") as f:
                                f.write(await response.read())
                            return file_path
                        else:
                            logger.error(f"Ошибка HTTP: {response.status}")
                            return None
            else:
                logger.error("Это не видео.")
                return None
        except Exception as e:
            logger.error(f"Ошибка Instagram: {e}")
            return None

    else:
        return None

# Функция для проверки доступности сайта через прокси
async def check_site_availability(site_name, site_url):
    try:
        timeout = aiohttp.ClientTimeout(total=10)  # Тайм-аут 10 секунд
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(site_url, proxy=proxy['http']) as response:
                if response.status == 200:
                    return f"{site_name}: ✅ Доступен"
                else:
                    return f"{site_name}: ❌ Ошибка (код {response.status})"
    except asyncio.TimeoutError:
        return f"{site_name}: ❌ Ошибка (Тайм-аут)"
    except Exception as e:
        return f"{site_name}: ❌ Ошибка ({str(e)})"

# Команда /status
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Проверяю доступность сайтов через прокси...")

    results = []
    for site_name, site_url in SITES_TO_CHECK.items():
        status_message = await check_site_availability(site_name, site_url)
        results.append(status_message)

    # Отправляем результат в чат
    await update.message.reply_text("\n".join(results))

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для скачивания видео с YouTube и Instagram.\n"
        "Используй команду /status, чтобы проверить доступность сайтов через прокси."
    )

# Обработчик сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    platform = "YouTube" if ("youtube.com" in url or "youtu.be" in url) else "Instagram" if "instagram.com" in url else None

    if platform:
        await update.message.reply_text(f"Скачиваю видео с {platform}...")
        video_path = await download_video(url)
        if video_path:
            if check_file_size(video_path):
                try:
                    with open(video_path, 'rb') as video_file:
                        await update.message.reply_video(video=video_file)
                    logger.info(f"Видео успешно отправлено: {video_path}")
                except TimedOut:
                    logger.error("Тайм-аут при отправке видео.")
                    await update.message.reply_text("Время ожидания истекло. Попробуйте ещё раз.")
                except Exception as e:
                    logger.error(f"Ошибка при отправке видео: {e}")
                    await update.message.reply_text("Произошла ошибка. Попробуйте ещё раз.")
            else:
                await update.message.reply_text("Файл слишком большой для отправки через Telegram.")
                logger.warning(f"Файл слишком большой: {video_path}")
            safe_remove(video_path)
        else:
            await update.message.reply_text(f"Не удалось скачать видео с {platform}.")
            logger.error(f"Не удалось скачать видео: {url}")
    else:
        await update.message.reply_text("Ссылка не поддерживается. Попробуйте ещё раз.")
        logger.warning(f"Неподдерживаемая ссылка: {url}")

# Основная функция
def main():
    # Увеличиваем тайм-аут до 30 секунд
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).read_timeout(30).write_timeout(30).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))  # Добавляем команду /status
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота
    application.run_polling()

if __name__ == "__main__":
    main()
