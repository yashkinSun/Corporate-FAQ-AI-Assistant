import logging
import re
from typing import Dict, Any, Optional, Tuple, List

from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage

from config import SUPPORTED_LANGUAGES
from storage.database_unified import log_suspicious_input

logger = logging.getLogger(__name__)

# Подозрительные паттерны в ответах LLM
SUSPICIOUS_RESPONSE_PATTERNS = [
    r"(?i)(as an ai language model|as an artificial intelligence|as a language model)",
    r"(?i)(i was instructed to|my instructions are|according to my prompt)",
    r"(?i)(the prompt says|here's the system prompt|my system prompt)",
    r"(?i)(i cannot|i'm not able to|i am not allowed to|i'm not permitted to)",
    r"(?i)(sk-[A-Za-z0-9]{20,}|api[_\s]?key|secret|token)",
]

# Безопасные замены для подозрительных ответов
SAFE_FALLBACK_RESPONSES = {
    "ru": "Извините, я не могу предоставить ответ на этот вопрос. Пожалуйста, попробуйте переформулировать запрос или обратитесь к оператору.",
    "en": "Sorry, I cannot provide an answer to this question. Please try rephrasing your query or contact an operator."
}

def validate_response(response: str, user_id: int, language: str = 'ru') -> str:
    """
    Проверяет ответ LLM на наличие подозрительных паттернов и заменяет их при необходимости.
    
    Args:
        response: Ответ LLM
        user_id: ID пользователя
        language: Язык пользователя ('ru' или 'en')
        
    Returns:
        str: Проверенный и при необходимости измененный ответ
    """
    original_response = response
    is_suspicious = False
    
    # Проверяем на наличие подозрительных паттернов
    for pattern in SUSPICIOUS_RESPONSE_PATTERNS:
        if re.search(pattern, response):
            is_suspicious = True
            # Логируем подозрительный ответ
            log_suspicious_input(
                user_id, 
                original_response[:100] + "...", 
                "suspicious_response", 
                "replaced_with_fallback"
            )
            
            # Заменяем на безопасный ответ
            fallback_language = language if language in SAFE_FALLBACK_RESPONSES else 'en'
            return SAFE_FALLBACK_RESPONSES[fallback_language]
    
    return response

def sanitize_environment_variables(response: str, user_id: int) -> str:
    """
    Проверяет ответ на наличие паттернов, похожих на переменные окружения или секреты.
    
    Args:
        response: Ответ LLM
        user_id: ID пользователя
        
    Returns:
        str: Проверенный и при необходимости измененный ответ
    """
    # Паттерны для обнаружения потенциальных секретов
    env_var_patterns = [
        (r"(?i)(TELEGRAM_BOT_TOKEN|OPENAI_API_KEY|API_KEY|SECRET_KEY)[\s]*=[\s]*['\"](.*?)['\"]", "[REDACTED]"),
        (r"(?i)(sk-[A-Za-z0-9]{1,})", "[API_KEY_REDACTED]"),  # Исправлено: {20,} -> {1,}
        (r"(?i)(access_token|bearer token|auth token)[\s]*[:=][\s]*['\"](.*?)['\"]", "[TOKEN_REDACTED]"),
        # Добавлен новый паттерн для обнаружения API ключей без кавычек
        (r"(?i)(TELEGRAM_BOT_TOKEN|OPENAI_API_KEY|API_KEY|SECRET_KEY)[\s]*=[\s]*([\w\-]+)", r"\1=[REDACTED]"),
    ]
    
    original_response = response
    is_modified = False
    
    # Проверяем на наличие паттернов секретов
    for pattern, replacement in env_var_patterns:
        if re.search(pattern, response):
            is_modified = True
            response = re.sub(pattern, replacement, response)
    
    if is_modified:
        # Логируем обнаружение потенциальных секретов
        log_suspicious_input(
            user_id, 
            "Potential secrets in response", 
            "env_var_exposure", 
            "redacted"
        )
    
    return response

def format_chat_messages(system_prompt: str, user_message: str) -> List[BaseMessage]:
    """
    Форматирует сообщения для API чата OpenAI в правильном формате.
    
    Args:
        system_prompt: Системный промпт
        user_message: Сообщение пользователя
        
    Returns:
        List[BaseMessage]: Список сообщений в формате LangChain
    """
    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message)
    ]
