# handlers.py

"""
Модуль для обработки сообщений в Telegram-боте.
"""
import logging
import os
from typing import Dict, Any, Optional, Tuple, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import CONFIDENCE_THRESHOLD, FOLLOWUP_ENABLED
from utils.input_sanitization import sanitize_input, detect_language, is_supported_language
from utils.language_detection import detect_and_set_language, get_language_message
from utils.followup_manager import get_followup_suggestions
from utils.message_utils import truncate_message
from utils.greeting_detector import is_greeting
from utils.rate_limit import telegram_rate_limit
from storage.database_unified import (
    save_message,
    get_or_create_session,
    can_escalate
)
from bot.dialogues import (
    create_followup_keyboard,
    low_confidence_handler,
    support_command
)
from bot.operator import (
    forward_request_to_operator,
    user_message_to_operator_handler,
    is_operator
)
from bot.feedback import handle_feedback_message
from controllers.query_controller import process_user_query

# Новый импорт для «думаю…»
from utils.thinking_indicator import ThinkingIndicator

logger = logging.getLogger(__name__)

# Инициализируем ThinkingIndicator
thinking_indicator = ThinkingIndicator()

# Ключевые слова для эскалации к оператору
ESCALATION_KEYWORDS = [
    "позови человека", "оператор", "зови человека", "help desk",
    "call a human", "human operator", "talk to human"
]

# Константы для отслеживания уверенности
LOW_CONFIDENCE_THRESHOLD = 0.5
USER_CONFIDENCE_HISTORY: Dict[int, List[float]] = {}  # user_id -> list of recent confidence scores

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Хэндлер для команды /start
    """
    user_id = update.effective_user.id

    # Определяем язык пользователя
    language = await detect_and_set_language(update, context)

    # Отправляем приветственное сообщение на соответствующем языке
    await update.message.reply_text(get_language_message(language, 'welcome'))

@telegram_rate_limit
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Хэндлер для произвольных текстовых сообщений.
    """
    # Проверяем, является ли сообщение обратной связью после оценки
    if await handle_feedback_message(update, context):
        return

    # Проверяем, является ли сообщение частью диалога с оператором
    if await user_message_to_operator_handler(update, context):
        return

    # Проверяем, является ли сообщение частью процесса создания рассылки
    from controllers.broadcast import handle_broadcast_message
    if await handle_broadcast_message(update, context):
        return

    user_id = update.message.from_user.id
    user_text = update.message.text
    logger.info(f"[TEXT] Received from user_id={user_id}: {user_text}")

    # Определяем язык пользователя
    language = await detect_and_set_language(update, context)
    context.user_data["lang"] = language
    context.user_data["last_question"] = user_text

    # Проверка длины сообщения
    if len(user_text) > 3000:
        await update.message.reply_text(get_language_message(language, 'message_too_long'))
        return

    # Санитизация ввода
    sanitized_text, is_suspicious = sanitize_input(user_id, user_text)

    # Проверяем, является ли сообщение приветствием
    if is_greeting(sanitized_text):
        logger.info(f"[GREETING] Detected greeting from user_id={user_id}: {sanitized_text}")
        greeting_response = get_language_message(language, 'greeting_full')
        await update.message.reply_text(greeting_response)
        save_message(user_id, user_text, greeting_response, 1.0, language)
        return

    # Проверка на ключевые слова для эскалации к оператору
    text_lower = sanitized_text.lower()
    if any(keyword in text_lower for keyword in ESCALATION_KEYWORDS):
        if not can_escalate(user_id):
            await update.message.reply_text(get_language_message(language, 'cooldown_active'))
            return

        await update.message.reply_text(get_language_message(language, 'operator_request_sent'))
        await forward_request_to_operator(update, context)
        save_message(user_id, user_text, "[Escalate to operator]", None, language)
        return

    # --- Начало RAG-пайплайна с индикатором «Думаю...» ---
    # Отправляем «бот печатает...» и сообщение «Думаю...»
    await thinking_indicator.start(update, context, language)

    # Собственно обработка запроса
    rag_answer, confidence = process_user_query(sanitized_text, user_id, language)

    # Сохраняем историю уровней уверенности
    USER_CONFIDENCE_HISTORY.setdefault(user_id, []).append(confidence)
    if len(USER_CONFIDENCE_HISTORY[user_id]) > 3:
        USER_CONFIDENCE_HISTORY[user_id].pop(0)

    # Определяем контекст низкой уверенности
    low_count = sum(1 for c in USER_CONFIDENCE_HISTORY[user_id] if c < LOW_CONFIDENCE_THRESHOLD)
    context_low_confidence = low_count >= 2

    # Обработка по confidence
    if confidence < CONFIDENCE_THRESHOLD:
        # Для запросов вне базы знаний или с низкой уверенностью отвечаем безопасным шаблоном
        rag_answer = get_language_message(language, 'offtopic_response')
        await low_confidence_handler(update, context, sanitized_text, rag_answer, confidence, language)
    else:
        reply_markup = None
        if FOLLOWUP_ENABLED:
            # Генерируем follow-up вопросы
            followups = get_followup_suggestions(
                sanitized_text,
                rag_answer,
                language,
                context_low_confidence
            )
            if len(followups) == 1 and (
                "can't provide" in followups[0].lower()
                or "не могу предложить" in followups[0].lower()
            ):
                reply_markup = None
            elif followups:
                reply_markup = create_followup_keyboard(followups, language)

        # Заменяем «Думаю...» на итоговый ответ
        await thinking_indicator.stop(
            update,
            context,
            truncate_message(rag_answer),
            reply_markup
        )

    # Сохраняем в БД
    save_message(user_id, user_text, rag_answer, confidence, language)

@telegram_rate_limit
async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Хэндлер для фотографий.
    Если приходит фото — сразу эскалируем к оператору.
    """
    # Тестовый ответ для проверки срабатывания хэндлера
    #await update.message.reply_text("📷 Фото поймано!")
    #return

    # Ниже временно  основная логика эскалации:
    user_id = update.message.from_user.id
    logger.info(f"[PHOTO] Received photo from user_id={user_id}")
    #
    # # Для фото сразу берём последний установленный язык (или 'ru'), без detect_and_set_language
    language = context.user_data.get("lang", "ru")
    #
    if not can_escalate(user_id):
        await update.message.reply_text(get_language_message(language, 'cooldown_active'))
        return
    
    await update.message.reply_text(get_language_message(language, 'operator_request_sent'))
    await forward_request_to_operator(update, context)
    save_message(user_id, "[PHOTO]", "[Escalate to operator]", None, language)