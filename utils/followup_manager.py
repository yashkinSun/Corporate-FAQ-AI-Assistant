"""
Модуль для интеграции существующей логики follow-up предложений
с новой LLM-генерацией. Переключается между режимами map и llm.
"""
import logging
from typing import List

from config import FOLLOWUP_ENABLED, FOLLOWUP_MODE
from utils.followup_llm import generate_followup_questions
from utils.followup_suggestions import (
    load_followup_map,
    get_followup_suggestions as get_map_followup_suggestions,
)
from utils.input_sanitization import sanitize_input

logger = logging.getLogger(__name__)

# ---------- пост-фильтр «отказов» ----------
BANNED_PHRASES = [
    "я не могу сгенерировать уточняющие вопросы",
    "i cannot generate follow-up questions",
    "не могу предложить",
    "sorry, i can't provide",
    "извините, я не могу",
    "тематика разговора не соответствует",
]


def _is_bad_followup(text: str) -> bool:
    """True, если строка содержит одну из запрещённых фраз."""
    t = text.lower()
    return any(b in t for b in BANNED_PHRASES)


# ------------------------------------------


def get_followup_suggestions(
    user_query: str,
    bot_response: str = "",
    language: str = "ru",
    context_low_confidence: bool = False,
) -> List[str]:
    """
    Возвращает список follow-up вопросов (уже отфильтрованных от «отказов»).
    """
    if not FOLLOWUP_ENABLED:
        logger.debug("Follow-up suggestions disabled via config, skipping generation")
        return []

    # 1. базовая проверка на попытку prompt-injection
    cleaned_query, _ = sanitize_input(user_id=None, input_text=user_query)

    if "[FILTERED]" in cleaned_query:
        logger.warning(
            "[SECURITY] Blocked follow-up generation due to suspicious input: %s",
            user_query,
        )
        return (
            [
                "Извините, я не могу предложить дальнейшие вопросы по этому запросу. "
                "Пожалуйста, уточните ваш вопрос."
            ]
            if language == "ru"
            else [
                "Sorry, I can't provide follow-up questions for this request. "
                "Please rephrase your question."
            ]
        )

    # 2. получаем follow-up-ы выбранным способом
    if FOLLOWUP_MODE.lower() == "llm":
        followups = generate_followup_questions(
            user_query=user_query,
            bot_response=bot_response,
            language=language,
            context_low_confidence=context_low_confidence,
        )
    else:
        followups = get_map_followup_suggestions(
            user_query=user_query,
            language=language,
            context_low_confidence=context_low_confidence,
        )

    # 3. пост-фильтрация «отказных» фраз
    followups = [q for q in followups if not _is_bad_followup(q)]

    # если после фильтра ничего не осталось — вернём пустой список,
    # клавиатура не будет показана
    return followups


def save_followup_questions(
    db_session,
    message_id: int,
    questions: List[str],
    original_query: str | None = None,
    confidence_score: float | None = None,
    generated_by: str = "map",
):
    """
    Сохраняет follow-up вопросы в базу данных.
    """
    from storage.database_unified import save_followup_question

    for question in questions:
        save_followup_question(
            db_session,
            message_id,
            question,
            original_query=original_query,
            confidence_score=confidence_score,
            generated_by=generated_by,
        )

    logger.debug("Saved %s follow-up questions for message %s", len(questions), message_id)
