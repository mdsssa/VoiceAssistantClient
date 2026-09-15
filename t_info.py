import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

bot_token = os.environ.get("BOT_TOKEN")
chat_id = os.environ.get("CHAT_ID")

print(bot_token)
print(chat_id)