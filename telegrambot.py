import telebot
import os
from dotenv import load_dotenv

load_dotenv()
bot_token = os.environ.get("BOT_TOKEN")
chat_id = os.environ.get("CHAT_ID")

bot = telebot.TeleBot(str(bot_token))

def send_message(message):
    bot.send_message(chat_id = chat_id, text= message , parse_mode='markdown')

@bot.message_handler()
def handler(message):
    print(message.text)


bot.polling()