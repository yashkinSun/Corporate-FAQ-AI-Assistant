import logging
import os
from dotenv import load_dotenv

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.ext.filters import User

from config import ADMIN_IDS

# ─── Bot logic ────────────────────────────────────────────────────────────────
from bot.handlers import start_command, handle_text_message, handle_photo_message
from bot.dialogues import (
    support_command,
    support_callback_handler,
    followup_callback_handler,
    confidence_callback_handler,
)
from bot.operator import (
    operator_callback,
    operator_message_handler,
    select_user_callback,
)
from bot.feedback import rating_callback_handler
from controllers.broadcast import broadcast_command, broadcast_callback_handler
from storage.database_unified import init_db

# ─── .env ─────────────────────────────────────────────────────────────────────
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
print("DEBUG main.py TOKEN:", TELEGRAM_BOT_TOKEN)


# ─── Глобальный обработчик ошибок ────────────────────────────────────────────
async def global_error_handler(update, context):
    logging.error(f"Произошла ошибка: {context.error}", exc_info=context.error)


def main() -> None:
    # Логирование
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # База данных
    init_db()

    # Приложение Telegram
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # ─── Команды ──────────────────────────────────────────────────────────────
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("support", support_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))

    # ─── Callback‑кнопки ──────────────────────────────────────────────────────
    application.add_handler(CallbackQueryHandler(support_callback_handler,    pattern=r"^support_"))
    application.add_handler(CallbackQueryHandler(followup_callback_handler,   pattern=r"^followup_"))
    application.add_handler(CallbackQueryHandler(confidence_callback_handler, pattern=r"^(rephrase|talk_to_operator)$"))
    application.add_handler(CallbackQueryHandler(operator_callback,           pattern=r"^(accept|decline|end_session)_"))
    application.add_handler(CallbackQueryHandler(select_user_callback,        pattern=r"^select_user_"))
    application.add_handler(CallbackQueryHandler(rating_callback_handler,     pattern=r"^rating_"))
    application.add_handler(CallbackQueryHandler(broadcast_callback_handler,  pattern=r"^broadcast_"))

    # ─── Сообщения операторов (обрабатываем ПЕРВЫМИ) ─────────────────────────
    application.add_handler(
        MessageHandler(
            filters.TEXT & User(ADMIN_IDS),
            operator_message_handler,
        )
    )

    # ─── Остальные сообщения / фото ──────────────────────────────────────────
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # ─── Глобальный обработчик ошибок ────────────────────────────────────────
    application.add_error_handler(global_error_handler)

    # ─── Запуск ──────────────────────────────────────────────────────────────
    application.run_polling()


if __name__ == "__main__":
    main()
