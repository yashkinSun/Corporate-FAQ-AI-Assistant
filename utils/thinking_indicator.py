# utils/thinking_indicator.py

from telegram.constants import ChatAction
from telegram.ext import ContextTypes
from telegram import Update

class ThinkingIndicator:
    """
    Модуль для отображения пользователю «Думаю...» (или «Thinking...»)
    с последующим редактированием этого сообщения на готовый ответ.
    """
    def __init__(self):
        # chat_id → message_id
        self.active_indicators: dict[int, int] = {}

    async def start(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        language: str = 'ru'
    ) -> None:
        # Показываем «бот печатает...»
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING
        )
        # Текст «думаю» в зависимости от языка
        text = 'Думаю...' if language == 'ru' else 'Thinking...'
        msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text
        )
        # Сохраняем ID сообщения, чтобы потом его отредактировать
        self.active_indicators[update.effective_chat.id] = msg.message_id

    async def stop(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        new_text: str,
        reply_markup=None
    ) -> None:
        chat_id = update.effective_chat.id
        msg_id = self.active_indicators.pop(chat_id, None)
        if not msg_id:
            # Если индикатор вдруг не найден, просто отправляем новое сообщение
            await context.bot.send_message(
                chat_id=chat_id,
                text=new_text,
                reply_markup=reply_markup
            )
            return

        # Редактируем сообщение «Думаю...» на полноценный ответ
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=new_text,
            reply_markup=reply_markup
        )
