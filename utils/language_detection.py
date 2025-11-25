# language_detection.py

import logging
import re
from typing import Dict, Any, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import SUPPORTED_LANGUAGES
from utils.input_sanitization import detect_language, is_supported_language
from storage.database_unified import get_or_create_session, update_session_language, get_user_language

logger = logging.getLogger(__name__)

async def detect_and_set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Определяет язык сообщения пользователя и устанавливает его в сессии.

    Args:
        update: Объект Update от Telegram
        context: Контекст бота

    Returns:
        str: Определенный язык ('ru', 'en') или язык по умолчанию ('ru')
    """
    user_id = update.effective_user.id
    # Используем caption, если text отсутствует
    text = update.message.text or update.message.caption  # ← patched

    # Получаем текущий язык пользователя из сессии
    current_language = get_user_language(user_id)

    # ← added: если пришло не текстовое сообщение (например, фото или документ),
    #    сразу возвращаем уже установленный язык (или ставим 'ru' по умолчанию)
    if not isinstance(text, str):                    # ← added
        if current_language:                          # ← added
            return current_language                    # ← added
        # нет текущего языка – устанавливаем 'ru' как дефолт
        default_lang = 'ru'                           # ← added
        session_id = get_or_create_session(user_id)   # ← added
        update_session_language(session_id, default_lang)  # ← added
        return default_lang                           # ← added

    # Если язык уже установлен, проверяем, не изменился ли он
    if current_language:
        # Определяем язык текущего сообщения
        detected_language = detect_language(text)
        # Патч: если короткое слово на кириллице ошибочно распознано как 'en' — поправим
        if detected_language == 'en' and isinstance(text, str) and re.fullmatch(r"[а-яё\s]+", text.lower()):  # ← patched
            detected_language = 'ru'
        # Если язык определен и отличается от текущего, и поддерживается
        if detected_language and detected_language != current_language and is_supported_language(detected_language):
            # Обновляем язык в сессии
            session_id = get_or_create_session(user_id)
            update_session_language(session_id, detected_language)

            # Уведомляем пользователя о смене языка
            await update.message.reply_text(
                get_language_message(detected_language, 'language_switched')
            )
            return detected_language

        return current_language

    # Если язык ещё не установлен, определяем его
    detected_language = detect_language(text)
    # Патч: если короткое слово на кириллице ошибочно распознано как 'en' — поправим
    if detected_language == 'en' and isinstance(text, str) and re.fullmatch(r"[а-яё\s]+", text.lower()):  # ← patched
        detected_language = 'ru'
    # Если язык не удалось определить или он не поддерживается — по умолчанию 'ru'
    if not detected_language or not is_supported_language(detected_language):
        detected_language = 'ru'

    # Сохраняем язык в сессии
    session_id = get_or_create_session(user_id)
    update_session_language(session_id, detected_language)

    return detected_language

def get_language_message(language: str, message_key: str) -> str:
    """
    Возвращает сообщение на указанном языке.
    
    Args:
        language: Код языка ('ru', 'en')
        message_key: Ключ сообщения
        
    Returns:
        str: Сообщение на указанном языке
    """
    messages = {
        'welcome': {
            'ru': "Привет! Я корпоративный бот. Чем могу помочь?",
            'en': "Hello! I'm a corporate bot. How can I help you?"
        },
        'unsupported_language': {
            'ru': "Извините, я не поддерживаю этот язык. Пожалуйста, используйте русский или английский.",
            'en': "Sorry, I don't support this language. Please use Russian or English."
        },
        'clarification_needed': {
            'ru': "Я не совсем уверен в ответе. Возможно, стоит уточнить:\n\n{}\n\nИли введите 'Позови человека', чтобы связаться с оператором.",
            'en': "I'm not entirely sure about the answer. Perhaps you could clarify:\n\n{}\n\nOr type 'Call a human' to contact an operator."
        },
        'operator_request_sent': {
            'ru': "Ваш запрос передан оператору. Пожалуйста, дождитесь ответа.",
            'en': "Your request has been forwarded to an operator. Please wait for a response."
        },
        'operator_accepted': {
            'ru': "Оператор принял ваш запрос и скоро ответит. Пожалуйста, ожидайте.",
            'en': "An operator has accepted your request and will respond shortly. Please wait."
        },
        'operators_busy': {
            'ru': "К сожалению, все операторы сейчас заняты. Пожалуйста, попробуйте позже.",
            'en': "Unfortunately, all operators are currently busy. Please try again later."
        },
        'rate_conversation': {
            'ru': "Пожалуйста, оцените этот разговор:",
            'en': "Please rate this conversation:"
        },
        'feedback_request': {
            'ru': "Нам жаль, что вы остались не полностью довольны. Пожалуйста, расскажите, что пошло не так?",
            'en': "We're sorry it wasn't great. Could you let us know what went wrong?"
        },
        'thanks_for_rating': {
            'ru': "Спасибо за вашу оценку: {}/5! Мы рады, что смогли вам помочь.",
            'en': "Thank you for your rating: {}/5! We're glad we could help you."
        },
        'thanks_for_feedback': {
            'ru': "Спасибо за вашу обратную связь! Мы учтем ваши комментарии для улучшения нашего сервиса.",
            'en': "Thank you for your feedback! We will take your comments into account to improve our service."
        },
        'message_too_long': {
            'ru': "Ваше сообщение слишком длинное. Пожалуйста, сократите его и попробуйте снова.",
            'en': "Your message is too long. Please shorten it and try again."
        },
        'support_menu': {
            'ru': "Выберите категорию вашего вопроса:",
            'en': "Please select the category of your question:"
        },
        'support_order': {
            'ru': "📦 Заказ",
            'en': "📦 Order"
        },
        'support_payment': {
            'ru': "💳 Оплата",
            'en': "💳 Payment"
        },
        'support_delivery': {
            'ru': "🚚 Доставка",
            'en': "🚚 Delivery"
        },
        'support_other': {
            'ru': "❓ Другое",
            'en': "❓ Other"
        },
        'cooldown_active': {
            'ru': "Вы недавно уже обращались к оператору. Пожалуйста, подождите некоторое время перед следующим обращением.",
            'en': "You have recently contacted an operator. Please wait some time before your next request."
        },
        'rephrase_question': {
            'ru': "Перефразировать",
            'en': "Rephrase"
        },
        'talk_to_operator': {
            'ru': "Связаться с оператором",
            'en': "Talk to operator"
        },
        'question_prefix': {
        'ru': "Ваш вопрос: ",
        'en': "Your question: "
        },
        'greeting_full': {
        'ru': "Здравтсвуйте!, я - Veliro, чат-бот поддержки ООО Транс-Логистика. Готов помочь вам с различными вопросами",
        'en': "Greetings! I'm Veliro - support bot from OOO Trans-Logistica company. I'me here to help you with your questions"
        },
        'language_switched': {
        'ru': "Чат переключен на русский язык.",
        'en': "Chat switched to English language"
        },
        'followup_prompt': {
        'ru': "Что-нибудь ещё?",
        'en': "Anything else?"
        },
        'error_occurred': {
            'ru': "Извините, произошла ошибка при обработке вашего запроса.",
            'en': "Sorry, an error occurred while processing your request."
        }
    }
    
    # Если сообщение с указанным ключом не найдено, возвращаем ключ
    if message_key not in messages:
        return message_key
    
    # Если язык не поддерживается, используем английский
    if language not in SUPPORTED_LANGUAGES:
        language = 'en'
    
    return messages[message_key][language]
