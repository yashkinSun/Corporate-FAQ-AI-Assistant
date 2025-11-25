# input_sanitization.py

import re
import logging
from typing import Tuple, List, Optional

from config import SUPPORTED_LANGUAGES
from storage.database_unified import log_suspicious_input

logger = logging.getLogger(__name__)

# Список подозрительных паттернов для обнаружения попыток prompt injection
SUSPICIOUS_PATTERNS = [
    (r"(?i)(ignore previous instructions|override system prompt|jailbreak)", "system_override_attempt"),
    (r"(?i)(you are chatgpt|system_prompt|sk-[A-Za-z0-9]{20,})", "identity_manipulation"),
    (r"(?i)(show me your prompt|repeat the entire conversation|root access)", "prompt_exposure_attempt"),
    (r"(?i)(export|print|display).*(api[_\s]?key|secret|token|password)", "credential_exposure_attempt"),
    (r"(?i)(execute|run|eval).*(command|code|script|shell)", "code_execution_attempt")
]

# Максимальная длина сообщения (примерно 1000 токенов)
MAX_MESSAGE_LENGTH = 3000

def sanitize_input(user_id: int, input_text: str) -> Tuple[str, bool]:
    """
    Проверяет и санитизирует пользовательский ввод.
    
    Args:
        user_id: ID пользователя
        input_text: Текст сообщения пользователя
        
    Returns:
        Tuple[str, bool]: (санитизированный текст, флаг подозрительности)
    """
    # Проверка длины сообщения
    if len(input_text) > MAX_MESSAGE_LENGTH:
        log_suspicious_input(
            user_id, 
            input_text[:100] + "...", 
            "message_too_long", 
            "truncated"
        )
        return input_text[:MAX_MESSAGE_LENGTH], True
    
    # Проверка на подозрительные паттерны
    original_text = input_text
    is_suspicious = False
    
    for pattern, pattern_name in SUSPICIOUS_PATTERNS:
        if re.search(pattern, input_text):
            # Логируем подозрительный ввод
            log_suspicious_input(
                user_id, 
                input_text, 
                pattern_name, 
                "sanitized"
            )
            
            # Заменяем подозрительный паттерн на [FILTERED]
            input_text = re.sub(pattern, "[FILTERED]", input_text)
            is_suspicious = True
    
    return input_text, is_suspicious

def detect_language(text: str) -> Optional[str]:
    """
    Определяет язык текста на основе простой эвристики.

    Args:
        text: Текст для анализа

    Returns:
        str: Код языка ('ru', 'en') или None, если не удалось определить
    """
    # guard: если текст не строка, просто возвращаем None (не определено)
    if not isinstance(text, str):  # ← patched
        return None                # ← patched

    # Простая эвристика для определения языка
    # Подсчитываем символы кириллицы и латиницы
    cyrillic_count = len(re.findall(r'[а-яА-ЯёЁ]', text))
    latin_count = len(re.findall(r'[a-zA-Z]', text))

    # Если текст слишком короткий, не определяем язык
    if cyrillic_count + latin_count < 3:
        return None

    # Определяем язык на основе преобладающего алфавита
    if cyrillic_count > latin_count:
        return 'ru'
    elif latin_count > cyrillic_count:
        return 'en'

    return None

def is_supported_language(language_code: str) -> bool:
    """
    Проверяет, поддерживается ли указанный язык.
    
    Args:
        language_code: Код языка
        
    Returns:
        bool: True, если язык поддерживается
    """
    return language_code in SUPPORTED_LANGUAGES
