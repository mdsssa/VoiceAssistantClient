import telebot
import os
from dotenv import load_dotenv
from main import ask_llm , trim_history

history = []

load_dotenv()
bot_token = os.environ.get("BOT_TOKEN")
chat_id = os.environ.get("CHAT_ID")

bot = telebot.TeleBot(str(bot_token))



@bot.message_handler()
def handler(message):
    llmResponse = ask_llm(message.text , history)
    bot.reply_to(message , llmResponse);
    trim_history(history)


bot.polling()
