# bot/telegram_bot.py
import os
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from bot.handlers import start_command, handle_text_message, handle_photo_message

# Экспортируем глобально, чтобы web-интерфейс мог из этого файла брать .send_message()
bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))

def start_bot(token: str):
    application = ApplicationBuilder().token(token).build()

    # асинхронные обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))

    # запуск бота
    application.run_polling()
