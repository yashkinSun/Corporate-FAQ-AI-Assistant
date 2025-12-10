# utils/thinking_indicator.py

import logging

from telegram.error import BadRequest, TelegramError

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

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
        chat_id = update.effective_chat.id
        text = 'Думаю...' if language == 'ru' else 'Thinking...'
        try:
            # Показываем «бот печатает...»
            await context.bot.send_chat_action(
                chat_id=chat_id,
                action=ChatAction.TYPING
            )
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=text
            )
            # Сохраняем ID сообщения, чтобы потом его отредактировать
            self.active_indicators[chat_id] = msg.message_id
        except Exception:
            logging.exception("Failed to start thinking indicator for chat %s", chat_id)
            self.active_indicators.pop(chat_id, None)
            try:
                await context.bot.send_message(chat_id=chat_id, text=text)
            except Exception:
                logging.exception(
                    "Failed to send fallback thinking indicator for chat %s", chat_id
                )

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
            await self._send_reply_safely(chat_id, context, new_text, reply_markup)
            return

        # Редактируем сообщение «Думаю...» на полноценный ответ
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=new_text,
                reply_markup=reply_markup
            )
        except BadRequest as exc:
            message = str(exc).lower()
            if "message to edit not found" in message or "message to edit is not found" in message:
                logging.info(
                    "Thinking indicator message was removed for chat %s, sending new reply", chat_id
                )
            else:
                logging.exception(
                    "BadRequest while editing thinking indicator message for chat %s", chat_id
                )
            await self._send_reply_safely(chat_id, context, new_text, reply_markup)
        except TelegramError:
            logging.exception(
                "Failed to edit thinking indicator message for chat %s", chat_id
            )
            await self._send_reply_safely(chat_id, context, new_text, reply_markup)

    async def _send_reply_safely(
        self,
        chat_id: int,
        context: ContextTypes.DEFAULT_TYPE,
        new_text: str,
        reply_markup=None
    ) -> None:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=new_text,
                reply_markup=reply_markup
            )
        except TelegramError:
            logging.exception(
                "Failed to send fallback reply message for chat %s", chat_id
            )
