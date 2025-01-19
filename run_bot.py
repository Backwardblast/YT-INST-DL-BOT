import subprocess
import sys

# Укажите путь к вашему файлу
bot_script = r"D:\shortsdownload_bot\bot1.py"

# Запуск бота
try:
    subprocess.run([sys.executable, bot_script], check=True)
    print(f"Bot {bot_script} is running.")
except subprocess.CalledProcessError as e:
    print(f"Error occurred while starting the bot: {e}")
