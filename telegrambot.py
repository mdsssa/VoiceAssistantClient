import os

import telebot
from dotenv import load_dotenv

from main import ask_llm
from prompts import TELEGRAM_PROMPT


load_dotenv()

bot = telebot.TeleBot(str(os.environ.get("BOT_TOKEN")))

history = [{"role": "system", "content": TELEGRAM_PROMPT}]


@bot.message_handler()
def handler(message):
    if not message.text:
        return
    reply = ask_llm(message.text, history)
    if reply:
        bot.reply_to(message, reply.replace("**", "*"), parse_mode="Markdown")


if __name__ == "__main__":
    bot.polling()
