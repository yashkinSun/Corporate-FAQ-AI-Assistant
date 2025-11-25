import logging
import json
from typing import List, Dict, Any, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import ADMIN_IDS
from storage.database_unified import db_session, UserSession

logger = logging.getLogger(__name__)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /broadcast для массовой рассылки сообщений.
    Доступно только администраторам.
    """
    user_id = update.effective_user.id
    
    # Проверка прав администратора
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("У вас нет прав для использования этой команды.")
        return
    
    # Создаем клавиатуру с вариантами типа рассылки
    keyboard = [
        [InlineKeyboardButton("Текстовое сообщение", callback_data="broadcast_text")],
        [InlineKeyboardButton("Изображение", callback_data="broadcast_image")],
        [InlineKeyboardButton("Текст + кнопки", callback_data="broadcast_text_buttons")],
        [InlineKeyboardButton("Отменить", callback_data="broadcast_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Выберите тип сообщения для рассылки:",
        reply_markup=reply_markup
    )

async def broadcast_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик callback-запросов для команды broadcast.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("У вас нет прав для использования этой команды.")
        return
    
    callback_data = query.data
    
    if callback_data == "broadcast_text":
        await query.edit_message_text(
            "Введите текст сообщения для рассылки (до 1000 символов).\n"
            "Для отмены введите /cancel"
        )
        context.user_data["broadcast_state"] = "waiting_for_text"
        
    elif callback_data == "broadcast_image":
        await query.edit_message_text(
            "Отправьте изображение для рассылки.\n"
            "Вы можете добавить подпись к изображению.\n"
            "Для отмены введите /cancel"
        )
        context.user_data["broadcast_state"] = "waiting_for_image"
        
    elif callback_data == "broadcast_text_buttons":
        await query.edit_message_text(
            "Введите текст сообщения и кнопки в формате:\n\n"
            "Текст сообщения\n"
            "---\n"
            "Текст кнопки 1|https://example.com\n"
            "Текст кнопки 2|https://example.org\n\n"
            "Для отмены введите /cancel"
        )
        context.user_data["broadcast_state"] = "waiting_for_text_buttons"
        
    elif callback_data == "broadcast_cancel":
        await query.edit_message_text("Рассылка отменена.")
        if "broadcast_state" in context.user_data:
            del context.user_data["broadcast_state"]
    
    elif callback_data == "broadcast_confirm":
        await query.edit_message_text("Рассылка начата. Вы получите уведомление по завершении.")
        
        # Получаем данные для рассылки
        broadcast_data = context.user_data.get("broadcast_data", {})
        
        # Запускаем рассылку
        await execute_broadcast(context, broadcast_data)
        
        # Очищаем данные рассылки
        if "broadcast_state" in context.user_data:
            del context.user_data["broadcast_state"]
        if "broadcast_data" in context.user_data:
            del context.user_data["broadcast_data"]
    
    elif callback_data == "broadcast_cancel_confirm":
        await query.edit_message_text("Рассылка отменена.")
        if "broadcast_state" in context.user_data:
            del context.user_data["broadcast_state"]
        if "broadcast_data" in context.user_data:
            del context.user_data["broadcast_data"]

async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Обрабатывает сообщения в контексте создания рассылки.
    Возвращает True, если сообщение было обработано как часть процесса рассылки.
    """
    user_id = update.effective_user.id
    
    # Проверка прав администратора
    if user_id not in ADMIN_IDS:
        return False
    
    # Проверяем, находится ли пользователь в процессе создания рассылки
    broadcast_state = context.user_data.get("broadcast_state")
    if not broadcast_state:
        return False
    
    # Обработка команды отмены
    if update.message.text == "/cancel":
        await update.message.reply_text("Создание рассылки отменено.")
        del context.user_data["broadcast_state"]
        return True
    
    # Обработка текстового сообщения для рассылки
    if broadcast_state == "waiting_for_text":
        text = update.message.text
        
        if len(text) > 1000:
            await update.message.reply_text(
                "Текст слишком длинный. Пожалуйста, сократите его до 1000 символов."
            )
            return True
        
        # Сохраняем текст для рассылки
        context.user_data["broadcast_data"] = {"type": "text", "text": text}
        
        # Показываем предпросмотр и запрашиваем подтверждение
        keyboard = [
            [InlineKeyboardButton("Подтвердить", callback_data="broadcast_confirm")],
            [InlineKeyboardButton("Отменить", callback_data="broadcast_cancel_confirm")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Получаем количество получателей
        recipient_count = await get_recipient_count()
        
        await update.message.reply_text(
            f"Предпросмотр сообщения:\n\n{text}\n\n"
            f"Рассылка будет отправлена {recipient_count} получателям.\n"
            "Подтвердить?",
            reply_markup=reply_markup
        )
        
        context.user_data["broadcast_state"] = "confirming"
        return True
    
    # Обработка текстового сообщения с кнопками для рассылки
    elif broadcast_state == "waiting_for_text_buttons":
        message_text = update.message.text
        
        try:
            # Разделяем текст и кнопки
            parts = message_text.split("---")
            if len(parts) != 2:
                raise ValueError("Неверный формат. Используйте '---' для разделения текста и кнопок.")
            
            text = parts[0].strip()
            buttons_text = parts[1].strip()
            
            # Парсим кнопки
            buttons = []
            for line in buttons_text.split("\n"):
                if not line.strip():
                    continue
                
                button_parts = line.split("|")
                if len(button_parts) != 2:
                    raise ValueError(f"Неверный формат кнопки: {line}. Используйте 'Текст|URL'.")
                
                button_text = button_parts[0].strip()
                button_url = button_parts[1].strip()
                
                buttons.append({"text": button_text, "url": button_url})
            
            if not buttons:
                raise ValueError("Не указаны кнопки.")
            
            # Сохраняем данные для рассылки
            context.user_data["broadcast_data"] = {
                "type": "text_buttons",
                "text": text,
                "buttons": buttons
            }
            
            # Показываем предпросмотр и запрашиваем подтверждение
            keyboard_preview = []
            for button in buttons:
                keyboard_preview.append([InlineKeyboardButton(button["text"], url=button["url"])])
            
            preview_markup = InlineKeyboardMarkup(keyboard_preview)
            
            await update.message.reply_text(
                f"Предпросмотр сообщения:\n\n{text}",
                reply_markup=preview_markup
            )
            
            # Кнопки подтверждения
            confirm_keyboard = [
                [InlineKeyboardButton("Подтвердить", callback_data="broadcast_confirm")],
                [InlineKeyboardButton("Отменить", callback_data="broadcast_cancel_confirm")]
            ]
            confirm_markup = InlineKeyboardMarkup(confirm_keyboard)
            
            # Получаем количество получателей
            recipient_count = await get_recipient_count()
            
            await update.message.reply_text(
                f"Рассылка будет отправлена {recipient_count} получателям.\n"
                "Подтвердить?",
                reply_markup=confirm_markup
            )
            
            context.user_data["broadcast_state"] = "confirming"
            return True
            
        except ValueError as e:
            await update.message.reply_text(
                f"Ошибка: {str(e)}\n\n"
                "Пожалуйста, используйте формат:\n"
                "Текст сообщения\n"
                "---\n"
                "Текст кнопки 1|https://example.com\n"
                "Текст кнопки 2|https://example.org"
            )
            return True
    
    # Обработка изображения для рассылки
    elif broadcast_state == "waiting_for_image" and update.message.photo:
        photo_file_id = update.message.photo[-1].file_id
        caption = update.message.caption or ""
        
        # Сохраняем данные для рассылки
        context.user_data["broadcast_data"] = {
            "type": "image",
            "photo_file_id": photo_file_id,
            "caption": caption
        }
        
        # Показываем предпросмотр и запрашиваем подтверждение
        keyboard = [
            [InlineKeyboardButton("Подтвердить", callback_data="broadcast_confirm")],
            [InlineKeyboardButton("Отменить", callback_data="broadcast_cancel_confirm")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Получаем количество получателей
        recipient_count = await get_recipient_count()
        
        await update.message.reply_text(
            f"Изображение получено.\n"
            f"Подпись: {caption}\n\n"
            f"Рассылка будет отправлена {recipient_count} получателям.\n"
            "Подтвердить?",
            reply_markup=reply_markup
        )
        
        context.user_data["broadcast_state"] = "confirming"
        return True
    
    return False

async def get_recipient_count() -> int:
    """
    Получает количество получателей для рассылки.
    """
    try:
        with db_session() as db:
            # Получаем уникальных пользователей из базы данных
            count = db.query(UserSession.user_id).distinct().count()
            return count or 0
    except Exception as e:
        logger.error(f"Error getting recipient count: {e}")
        return 0

async def get_recipients() -> List[int]:
    """
    Получает список ID пользователей для рассылки.
    """
    try:
        with db_session() as db:
            # Получаем уникальных пользователей из базы данных
            recipients = db.query(UserSession.user_id).distinct().all()
            return [user_id[0] for user_id in recipients]
    except Exception as e:
        logger.error(f"Error getting recipients: {e}")
        return []

async def execute_broadcast(context: ContextTypes.DEFAULT_TYPE, broadcast_data: Dict[str, Any]) -> None:
    """
    Выполняет рассылку сообщений пользователям.
    """
    broadcast_type = broadcast_data.get("type")
    if not broadcast_type:
        return
    
    # Получаем список получателей
    recipients = await get_recipients()
    
    # Счетчики для статистики
    successful = 0
    failed = 0
    
    # Выполняем рассылку
    for user_id in recipients:
        try:
            if broadcast_type == "text":
                await context.bot.send_message(
                    chat_id=user_id,
                    text=broadcast_data["text"]
                )
            
            elif broadcast_type == "image":
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=broadcast_data["photo_file_id"],
                    caption=broadcast_data.get("caption", "")
                )
            
            elif broadcast_type == "text_buttons":
                # Создаем клавиатуру с кнопками
                keyboard = []
                for button in broadcast_data.get("buttons", []):
                    keyboard.append([InlineKeyboardButton(button["text"], url=button["url"])])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text=broadcast_data["text"],
                    reply_markup=reply_markup
                )
            
            successful += 1
        
        except Exception as e:
            logger.error(f"Error sending broadcast to user {user_id}: {e}")
            failed += 1
    
    # Отправляем отчет администратору
    admin_id = context.user_data.get("user_id")
    if admin_id:
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"Рассылка завершена.\n"
                f"Успешно отправлено: {successful}\n"
                f"Ошибок: {failed}"
        )

def get_broadcast_handlers():
    """
    Возвращает список обработчиков для функции broadcast.
    """
    return []  # Будет заполнено в main.py
