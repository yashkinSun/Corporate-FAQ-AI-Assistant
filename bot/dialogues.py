import logging
import re
from typing import List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import SUPPORTED_LANGUAGES, ESCALATION_COOLDOWN_MINUTES
from utils.followup_manager import get_followup_suggestions
from utils.message_utils import truncate_message
from storage.database_unified import can_escalate, get_or_create_session
from bot.operator import forward_request_to_operator
from utils.language_detection import get_language_message
from controllers.query_controller import process_user_query

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# /support
# ─────────────────────────────────────────────────────────────
async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if not can_escalate(user_id):
        await update.message.reply_text(get_language_message('ru', 'cooldown_active'))
        return

    language = 'ru'        # /support пока остаётся русским
    session_id = get_or_create_session(user_id)

    keyboard = [
        [
            InlineKeyboardButton(get_language_message(language, 'support_order'),   callback_data="support_order"),
            InlineKeyboardButton(get_language_message(language, 'support_payment'), callback_data="support_payment")
        ],
        [
            InlineKeyboardButton(get_language_message(language, 'support_delivery'), callback_data="support_delivery"),
            InlineKeyboardButton(get_language_message(language, 'support_other'),    callback_data="support_other")
        ]
    ]
    await update.message.reply_text(
        get_language_message(language, 'support_menu'),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def support_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = update.effective_user.id
    await query.answer()

    if not can_escalate(user_id):
        await query.edit_message_text(get_language_message('ru', 'cooldown_active'))
        return

    data_map = {
        "support_order":    "Заказ",
        "support_payment":  "Оплата",
        "support_delivery": "Доставка",
        "support_other":    "Другое"
    }
    category = data_map.get(query.data)

    if category:
        await query.edit_message_text(get_language_message('ru', 'operator_request_sent'))

        # ── создаём «фиктивное» сообщение и пробрасываем оператору
        class FakeMessage:
            def __init__(self, text, from_user, chat_id, message_id):
                self.text, self.from_user, self.chat_id, self.message_id = text, from_user, chat_id, message_id
                self.photo, self.caption = None, None

        class FakeUpdate:
            def __init__(self, message, effective_chat):
                self.message, self.effective_chat = message, effective_chat

        fake_msg = FakeMessage(f"Запрос поддержки: {category}", update.effective_user, update.effective_chat.id, query.message.message_id)
        await forward_request_to_operator(FakeUpdate(fake_msg, update.effective_chat), context, category)

# ─────────────────────────────────────────────────────────────
# Клавиатура follow-up
# ─────────────────────────────────────────────────────────────
def create_followup_keyboard(followups: List[str], language: str) -> InlineKeyboardMarkup:
    keyboard = [[InlineKeyboardButton(fu, callback_data=f"followup_{i}")] for i, fu in enumerate(followups)]
    return InlineKeyboardMarkup(keyboard)

# ─────────────────────────────────────────────────────────────
# Callback-handler для follow-up
# ─────────────────────────────────────────────────────────────
async def followup_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not query.data.startswith("followup_"):
        return

    selected_index = int(query.data.split("_")[1])
    selected_text  = query.message.reply_markup.inline_keyboard[selected_index][0].text

    # Язык берём из user_data (записывается в handle_text_message)
    language = context.user_data.get("lang") or 'en'  # т.к. англ. чаще нужен как fallback

    # Локализованный префикс «Ваш вопрос / Your question»
    prefix = get_language_message(language, 'question_prefix')
    await query.message.reply_text(f"{prefix}{selected_text}")

    user_id = update.effective_user.id
    response, confidence = process_user_query(selected_text, user_id, language=language)
    await query.message.reply_text(truncate_message(response))

    if confidence < 0.7:
        await low_confidence_handler(update, context, selected_text, response, confidence, language)
        return

    from bot.handlers import USER_CONFIDENCE_HISTORY, LOW_CONFIDENCE_THRESHOLD
    context_low_conf = False
    if len(USER_CONFIDENCE_HISTORY.get(user_id, [])) >= 2:
        low_cnt = sum(c < LOW_CONFIDENCE_THRESHOLD for c in USER_CONFIDENCE_HISTORY[user_id])
        context_low_conf = low_cnt >= 2

    followups = get_followup_suggestions(selected_text, response, language, context_low_conf)

    if len(followups) == 1 and (
        "can't provide" in followups[0].lower() or "не могу предложить" in followups[0].lower()
    ):
        reply_markup = None
    else:
        reply_markup = create_followup_keyboard(followups, language)

    prompt = get_language_message(language, 'followup_prompt')
    await query.message.reply_text(prompt, reply_markup=reply_markup)

# ─────────────────────────────────────────────────────────────
# Low-confidence handler
# ─────────────────────────────────────────────────────────────
async def low_confidence_handler(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                 question: str, answer: str, confidence: float, language: str) -> None:
    keyboard = [[
        InlineKeyboardButton(get_language_message(language, 'rephrase_question'), callback_data="rephrase"),
        InlineKeyboardButton(get_language_message(language, 'talk_to_operator'),  callback_data="talk_to_operator")
    ]]
    await update.message.reply_text(
        truncate_message(f"{answer}\n\n{get_language_message(language, 'clarification_needed').format('')}"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─────────────────────────────────────────────────────────────
# Хендлер для кнопок low-confidence
# ─────────────────────────────────────────────────────────────
async def confidence_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "rephrase":
        await query.edit_message_text("Пожалуйста, перефразируйте ваш вопрос для получения более точного ответа.")
        return

    if query.data == "talk_to_operator":
        await query.edit_message_text(get_language_message('ru', 'operator_request_sent'))

        class FakeMessage:
            def __init__(self, text, from_user, chat_id, message_id):
                self.text, self.from_user, self.chat_id, self.message_id = text, from_user, chat_id, message_id
                self.photo, self.caption = None, None

        class FakeUpdate:
            def __init__(self, message, effective_chat):
                self.message, self.effective_chat = message, effective_chat

        original_q = context.user_data.get("last_question", "Запрос помощи оператора")
        fake_msg   = FakeMessage(original_q, update.effective_user, update.effective_chat.id, query.message.message_id)
        await forward_request_to_operator(FakeUpdate(fake_msg, update.effective_chat), context)

# ─────────────────────────────────────────────────────────────
def get_dialogue_handlers():
    return []  # заполняется в main.py
