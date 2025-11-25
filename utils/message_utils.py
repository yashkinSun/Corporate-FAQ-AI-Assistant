import logging
from config import MAX_MESSAGE_LENGTH

logger = logging.getLogger(__name__)

def truncate_message(message: str) -> str:
    """
    Обрезает сообщение до максимально допустимой длины для Telegram.
    
    Args:
        message: Исходное сообщение
        
    Returns:
        str: Обрезанное сообщение
    """
    if len(message) <= MAX_MESSAGE_LENGTH:
        return message
    
    # Если сообщение слишком длинное, обрезаем его и добавляем уведомление
    truncated_message = message[:MAX_MESSAGE_LENGTH - 200]
    
    # Находим последний полный абзац для более аккуратного обрезания
    last_paragraph = truncated_message.rfind('\n\n')
    if last_paragraph > MAX_MESSAGE_LENGTH // 2:
        truncated_message = truncated_message[:last_paragraph]
    
    # Добавляем уведомление о том, что сообщение было обрезано
    truncation_notice = "\n\n... (ответ был сокращен из-за ограничений длины сообщения)"
    
    logger.info(f"Message truncated from {len(message)} to {len(truncated_message)} characters")
    
    return truncated_message + truncation_notice
