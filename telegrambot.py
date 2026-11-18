import os

import telebot
from dotenv import load_dotenv

import display
from main import ask_llm
from prompts import TELEGRAM_PROMPT


load_dotenv()

bot = telebot.TeleBot(str(os.environ.get("BOT_TOKEN")))

history = [{"role": "system", "content": TELEGRAM_PROMPT}]


@bot.message_handler()
def handler(message):
    if not message.text:
        return
    display.state("thinking")
    try:
        reply = ask_llm(message.text, history)
        if reply:
            bot.reply_to(message, reply.replace("**", "*"), parse_mode="Markdown")
    except Exception as e:
        # сеть/LLM/разметка не должны останавливать polling
        print(f"[telegrambot error] {e}")
    finally:
        display.state("idle")


if __name__ == "__main__":
    bot.polling()
