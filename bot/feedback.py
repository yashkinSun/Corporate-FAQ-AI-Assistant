import logging
from typing import Dict, Any, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from storage.database_unified import save_rating, save_feedback, get_or_create_session
from bot.operator import ACTIVE_OPERATOR_SESSIONS

logger = logging.getLogger(__name__)

# Словарь для хранения ожидания обратной связи
WAITING_FEEDBACK = {}  # {user_id: rating_id}

async def rating_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик callback-запросов для оценки сессии.
    """
    query = update.callback_query
    data = query.data  # rating_<value>
    user_id = update.effective_user.id
    
    await query.answer()
    
    if data.startswith("rating_"):
        try:
            rating = int(data.split("_")[1])
            
            # Получаем или создаем сессию пользователя
            session_id = get_or_create_session(user_id)
            
            # Сохраняем оценку
            rating_id = save_rating(session_id, rating)
            
            if rating <= 3:
                # Если оценка низкая (1-3), запрашиваем дополнительную обратную связь
                await query.edit_message_text(
                    "Нам жаль, что вы остались не полностью довольны. "
                    "Пожалуйста, расскажите, что пошло не так?"
                )
                
                # Сохраняем ID оценки для последующего сохранения обратной связи
                WAITING_FEEDBACK[user_id] = rating_id
            else:
                # Если оценка высокая (4-5), благодарим пользователя
                await query.edit_message_text(
                    f"Спасибо за вашу оценку: {rating}/5! "
                    "Мы рады, что смогли вам помочь."
                )
        except (ValueError, IndexError):
            logger.error(f"Invalid rating data: {data}")
            await query.edit_message_text("Произошла ошибка при обработке оценки.")

async def handle_feedback_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Обрабатывает сообщения с обратной связью после низкой оценки.
    Возвращает True, если сообщение было обработано как обратная связь.
    """
    user_id = update.effective_user.id
    
    # Проверяем, ожидается ли обратная связь от этого пользователя
    if user_id in WAITING_FEEDBACK:
        rating_id = WAITING_FEEDBACK[user_id]
        feedback_text = update.message.text
        
        # Сохраняем обратную связь
        save_feedback(rating_id, feedback_text)
        
        # Удаляем пользователя из списка ожидания
        del WAITING_FEEDBACK[user_id]
        
        # Благодарим пользователя за обратную связь
        await update.message.reply_text(
            "Спасибо за вашу обратную связь! Мы учтем ваши комментарии для улучшения нашего сервиса."
        )
        
        return True
    
    return False

def get_feedback_handlers():
    """
    Возвращает список хендлеров для функций обратной связи.
    """
    return []  # Будет заполнено в main.py
