import logging
import re
from typing import Dict, Any, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import OPERATOR_ID, ADMIN_IDS
from storage.database_unified import (
    get_or_create_session, 
    update_last_escalation_time, 
    end_session,
    can_escalate
)
import logging

logger = logging.getLogger(__name__)

def save_operator_action(action: str, user_chat_id: str, detail: str = ""):
    """
    Логирование действий оператора (принял/отклонил/ответил).
    """
    logger.info(f"[OPERATOR ACTION] {action} for user {user_chat_id}, detail={detail}")

# Словарь для хранения временных данных, например, user_id -> вопрос
OPERATOR_REQUESTS = {}  # {chat_id : {"user_id": ..., "message_id": ..., "text": ..., "photo": ...}}

# Словарь для хранения активных сессий с оператором
ACTIVE_OPERATOR_SESSIONS = {}  # {user_id: {"operator_id": ..., "session_id": ...}}

async def forward_request_to_operator(update: Update, context: ContextTypes.DEFAULT_TYPE, category: Optional[str] = None):
    """
    Пересылает запрос (текст или фото) оператору, добавляя inline-кнопки «Принять»/«Отклонить».
    
    Args:
        update: Объект Update от Telegram
        context: Контекст бота
        category: Категория запроса (опционально)
    """
    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id
    message_id = update.message.message_id
    
    # Проверяем, может ли пользователь эскалировать запрос (прошло ли 15 минут с последней эскалации)
    if not can_escalate(user_id):
        await update.message.reply_text(
            "Вы недавно уже обращались к оператору. Пожалуйста, подождите некоторое время перед следующим обращением."
        )
        return
    
    # Получаем или создаем сессию пользователя
    session_id = get_or_create_session(user_id)
    
    # Обновляем время последней эскалации
    update_last_escalation_time(session_id)
    
    text = update.message.caption if update.message.caption else update.message.text
    # Получим фото (если есть)
    photo_file_id = None
    if update.message.photo:
        photo_file_id = update.message.photo[-1].file_id
    
    # Добавляем категорию, если она указана
    category_text = f"\nКатегория: {category}" if category else ""
    
    OPERATOR_REQUESTS[str(chat_id)] = {
        "user_id": user_id,
        "message_id": message_id,
        "text": text,
        "photo": photo_file_id,
        "session_id": session_id,
        "category": category
    }
    
    keyboard = [
        [
            InlineKeyboardButton("Принять запрос", callback_data=f"accept_{chat_id}"),
            InlineKeyboardButton("Отклонить", callback_data=f"decline_{chat_id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    operator_msg = f"Поступил запрос от пользователя {user_id}:\n\n{text or '[Фото]'}{category_text}"
    logger.info(f"Forwarding request to operator with chat_id={chat_id}, user_id={user_id}")
    
    # Флаг для отслеживания успешной отправки хотя бы одному оператору
    at_least_one_success = False
    
    # Отправляем оператору
    for operator_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=operator_id,
                text=operator_msg,
                reply_markup=reply_markup
            )
            logger.info(f"Successfully sent message to operator {operator_id}")
            at_least_one_success = True
        except Exception as e:
            logger.error(f"Error sending message to operator {operator_id}: {e}")
            # Продолжаем попытки с другими операторами
    
    # Информируем пользователя о результате
    if at_least_one_success:
        await update.message.reply_text(
            "Ваш запрос передан оператору. Пожалуйста, ожидайте ответа."
        )
    else:
        await update.message.reply_text(
            "К сожалению, в данный момент все операторы недоступны. Пожалуйста, попробуйте позже или задайте вопрос боту."
        )
        logger.warning(f"Failed to forward request to any operator for user {user_id}")

async def operator_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик inline-кнопок «Принять запрос» / «Отклонить запрос».
    """
    query = update.callback_query
    data = query.data  # accept_<chat_id> или decline_<chat_id>
    operator_id = update.effective_user.id
    
    # Проверяем, является ли пользователь оператором
    if operator_id not in ADMIN_IDS:
        await query.answer("У вас нет прав для выполнения этого действия.")
        return
    
    await query.answer()  # Закрываем "часики"
    
    if data.startswith("accept_"):
        user_chat_id = data.split("_")[1]
        
        # Проверяем, не принял ли уже другой оператор этот запрос
        if user_chat_id in OPERATOR_REQUESTS:
            user_id = OPERATOR_REQUESTS[user_chat_id]["user_id"]
            session_id = OPERATOR_REQUESTS[user_chat_id]["session_id"]
            
            if user_id in ACTIVE_OPERATOR_SESSIONS:
                await query.message.reply_text(
                    f"Запрос уже принят другим оператором."
                )
                return
            
            # Добавляем пользователя в активные сессии
            ACTIVE_OPERATOR_SESSIONS[user_id] = {
                "operator_id": operator_id,
                "session_id": session_id
            }
            
            # Уведомляем пользователя
            await context.bot.send_message(
                chat_id=user_id,
                text="Оператор принял ваш запрос и скоро ответит. Пожалуйста, ожидайте."
            )
            
            # Предлагаем оператору ввести ответ
            keyboard = [
                [InlineKeyboardButton("Завершить сессию", callback_data=f"end_session_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"Запрос принят. Теперь вы можете общаться с пользователем {user_id}.\n"
                f"Когда закончите, нажмите 'Завершить сессию'.",
                reply_markup=reply_markup
            )
            
            save_operator_action("ACCEPT", user_id)
        else:
            await query.edit_message_text(
                f"Запрос больше не доступен."
            )
    
    elif data.startswith("decline_"):
        user_chat_id = data.split("_")[1]
        
        if user_chat_id in OPERATOR_REQUESTS:
            user_id = OPERATOR_REQUESTS[user_chat_id]["user_id"]
            
            # Уведомляем пользователя
            await context.bot.send_message(
                chat_id=user_id,
                text="К сожалению, все операторы сейчас заняты. Пожалуйста, попробуйте позже."
            )
            
            # Удаляем запрос
            del OPERATOR_REQUESTS[user_chat_id]
            
            # Сообщаем оператору об отклонении
            await query.edit_message_text(
                f"Запрос отклонён. Пользователь {user_id} уведомлен."
            )
            
            save_operator_action("DECLINE", user_id)
        else:
            await query.edit_message_text(
                f"Запрос больше не доступен."
            )
    
    elif data.startswith("end_session_"):
        user_id = int(data.split("_")[2])
        
        if user_id in ACTIVE_OPERATOR_SESSIONS:
            session_id = ACTIVE_OPERATOR_SESSIONS[user_id]["session_id"]
            
            # Завершаем сессию
            end_session(session_id)
            
            # Удаляем из активных сессий
            del ACTIVE_OPERATOR_SESSIONS[user_id]
            
            # Отправляем запрос на оценку пользователю
            await send_rating_request(context, user_id)
            
            # Уведомляем оператора
            await query.edit_message_text(
                f"Сессия с пользователем {user_id} завершена. Пользователю отправлен запрос на оценку."
            )
            
            save_operator_action("END_SESSION", user_id)
        else:
            await query.edit_message_text(
                f"Сессия с пользователем {user_id} не найдена или уже завершена."
            )

async def operator_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Обрабатывает сообщения от оператора для пересылки пользователю.
    Возвращает True, если сообщение было обработано как часть оператор-пользователь коммуникации.
    """
    operator_id = update.effective_user.id
    
    # Проверяем, является ли пользователь оператором
    if operator_id not in ADMIN_IDS:
        return False
    
    # Проверяем, есть ли активные сессии для этого оператора
    active_sessions = {user_id: data for user_id, data in ACTIVE_OPERATOR_SESSIONS.items() 
                      if data["operator_id"] == operator_id}
    
    if not active_sessions:
        return False
    
    # Если оператор отвечает в группе, ищем упоминание ID пользователя
    text = update.message.text
    user_id_match = re.search(r"#user_(\d+)", text)
    
    if user_id_match:
        user_id = int(user_id_match.group(1))
        # Удаляем тег из сообщения
        text = re.sub(r"#user_\d+\s*", "", text).strip()
    else:
        # Если только одна активная сессия, предполагаем, что оператор отвечает этому пользователю
        if len(active_sessions) == 1:
            user_id = list(active_sessions.keys())[0]
        else:
            # Если несколько сессий, просим уточнить, кому отвечать
            user_ids = list(active_sessions.keys())
            keyboard = []
            for uid in user_ids:
                keyboard.append([InlineKeyboardButton(f"Пользователь {uid}", callback_data=f"select_user_{uid}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "У вас несколько активных сессий. Выберите пользователя, которому хотите ответить:",
                reply_markup=reply_markup
            )
            
            # Сохраняем сообщение для последующей отправки
            context.user_data["pending_message"] = text
            
            return True
    
    # Проверяем, есть ли активная сессия с этим пользователем
    if user_id in ACTIVE_OPERATOR_SESSIONS and ACTIVE_OPERATOR_SESSIONS[user_id]["operator_id"] == operator_id:
        # Пересылаем сообщение пользователю
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Оператор: {text}"
            )
            
            await update.message.reply_text(
                f"Сообщение отправлено пользователю {user_id}."
            )
            
            save_operator_action("MESSAGE", user_id, detail=text)
            
            return True
        except Exception as e:
            logger.error(f"Error sending message to user {user_id}: {e}")
            
            await update.message.reply_text(
                f"Ошибка отправки сообщения пользователю {user_id}: {e}"
            )
            
            return True
    
    return False

async def user_message_to_operator_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Обрабатывает сообщения от пользователя для пересылки оператору.
    Возвращает True, если сообщение было обработано как часть пользователь-оператор коммуникации.
    """
    user_id = update.effective_user.id
    
    # Проверяем, есть ли активная сессия с оператором
    if user_id in ACTIVE_OPERATOR_SESSIONS:
        operator_id = ACTIVE_OPERATOR_SESSIONS[user_id]["operator_id"]
        
        # Пересылаем сообщение оператору
        try:
            if update.message.photo:
                # Если пользователь отправил фото
                photo_file_id = update.message.photo[-1].file_id
                caption = update.message.caption or ""
                
                await context.bot.send_photo(
                    chat_id=operator_id,
                    photo=photo_file_id,
                    caption=f"Пользователь {user_id}: {caption}"
                )
            else:
                # Если пользователь отправил текст
                text = update.message.text
                
                await context.bot.send_message(
                    chat_id=operator_id,
                    text=f"Пользователь {user_id}: {text}"
                )
            
            return True
        except Exception as e:
            logger.error(f"Error forwarding message to operator {operator_id}: {e}")
            
            # Если не удалось переслать сообщение оператору, завершаем сессию
            session_id = ACTIVE_OPERATOR_SESSIONS[user_id]["session_id"]
            end_session(session_id)
            del ACTIVE_OPERATOR_SESSIONS[user_id]
            
            await update.message.reply_text(
                "Произошла ошибка при пересылке сообщения оператору. Сессия завершена."
            )
            
            return True
    
    return False

async def select_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик выбора пользователя для отправки сообщения.
    """
    query = update.callback_query
    data = query.data  # select_user_<user_id>
    operator_id = update.effective_user.id
    
    # Проверяем, является ли пользователь оператором
    if operator_id not in ADMIN_IDS:
        await query.answer("У вас нет прав для выполнения этого действия.")
        return
    
    await query.answer()
    
    if data.startswith("select_user_"):
        user_id = int(data.split("_")[2])
        
        # Проверяем, есть ли активная сессия с этим пользователем
        if user_id in ACTIVE_OPERATOR_SESSIONS and ACTIVE_OPERATOR_SESSIONS[user_id]["operator_id"] == operator_id:
            # Получаем сохраненное сообщение
            text = context.user_data.get("pending_message", "")
            
            if text:
                # Пересылаем сообщение пользователю
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"Оператор: {text}"
                    )
                    
                    await query.edit_message_text(
                        f"Сообщение отправлено пользователю {user_id}."
                    )
                    
                    save_operator_action("MESSAGE", user_id, detail=text)
                    
                    # Очищаем сохраненное сообщение
                    del context.user_data["pending_message"]
                except Exception as e:
                    logger.error(f"Error sending message to user {user_id}: {e}")
                    
                    await query.edit_message_text(
                        f"Ошибка отправки сообщения пользователю {user_id}: {e}"
                    )
            else:
                await query.edit_message_text(
                    f"Выбран пользователь {user_id}. Теперь вы можете отправлять сообщения этому пользователю."
                )
        else:
            await query.edit_message_text(
                f"Сессия с пользователем {user_id} не найдена или принадлежит другому оператору."
            )

async def send_rating_request(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """
    Отправляет запрос на оценку сессии пользователю.
    
    Args:
        context: Контекст бота
        user_id: ID пользователя
    """
    keyboard = []
    row = []
    
    for rating in range(1, 6):
        row.append(InlineKeyboardButton(f"{rating}", callback_data=f"rating_{rating}"))
    
    keyboard.append(row)
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user_id,
        text="Пожалуйста, оцените этот разговор:",
        reply_markup=reply_markup
    )

def is_operator(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь оператором.
    
    Args:
        user_id: ID пользователя
        
    Returns:
        bool: True, если пользователь является оператором
    """
    return user_id in ADMIN_IDS

def get_operator_handlers():
    """
    Возвращает список хендлеров для функций оператора.
    """
    return []  # Будет заполнено в main.py
