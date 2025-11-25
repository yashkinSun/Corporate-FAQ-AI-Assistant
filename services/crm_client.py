"""
Модуль для интеграции с CRM системой.
Предоставляет заглушку для отправки событий в CRM.
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from config import CRM_ENDPOINT, CRM_LOG_PATH, CRM_ENABLED

# Настройка логирования
logger = logging.getLogger(__name__)
file_handler = logging.FileHandler(CRM_LOG_PATH)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)

def send_event(payload: Dict[str, Any], event_type: str = "bot_interaction") -> bool:
    """
    Отправляет событие в CRM систему.
    В текущей реализации просто логирует событие в файл.
    
    Args:
        payload: Данные события
        event_type: Тип события
        
    Returns:
        bool: True, если событие успешно отправлено
    """
    try:
        # Проверяем, включена ли интеграция с CRM
        if not CRM_ENABLED:
            logger.debug(f"CRM integration disabled, event not sent: {event_type}")
            return True
            
        # Добавляем метаданные
        event_data = {
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "payload": payload
        }
        
        # Логируем событие
        logger.info(f"CRM Event: {json.dumps(event_data)}")
        
        # Если указан CRM_ENDPOINT, можно реализовать отправку по API
        if CRM_ENDPOINT:
            # Здесь будет код для отправки данных в CRM
            # Например, через requests.post(CRM_ENDPOINT, json=event_data)
            logger.info(f"Would send to CRM endpoint: {CRM_ENDPOINT}")
        
        return True
    except Exception as e:
        logger.error(f"Error sending event to CRM: {e}")
        return False

def log_user_interaction(user_id: int, message_text: str, bot_response: str, 
                        confidence_score: Optional[float] = None) -> bool:
    """
    Логирует взаимодействие пользователя с ботом.
    
    Args:
        user_id: ID пользователя
        message_text: Текст сообщения пользователя
        bot_response: Ответ бота
        confidence_score: Оценка уверенности
        
    Returns:
        bool: True, если событие успешно отправлено
    """
    payload = {
        "user_id": user_id,
        "message_text": message_text,
        "bot_response": bot_response,
        "confidence_score": confidence_score
    }
    
    return send_event(payload, "user_interaction")

def log_operator_action(operator_id: int, action_type: str, user_id: int, 
                       detail: Optional[str] = None) -> bool:
    """
    Логирует действие оператора.
    
    Args:
        operator_id: ID оператора
        action_type: Тип действия (ACCEPT, DECLINE, END_SESSION, MESSAGE)
        user_id: ID пользователя
        detail: Дополнительная информация
        
    Returns:
        bool: True, если событие успешно отправлено
    """
    payload = {
        "operator_id": operator_id,
        "action_type": action_type,
        "user_id": user_id,
        "detail": detail
    }
    
    return send_event(payload, "operator_action")

def log_session_feedback(session_id: int, user_id: int, rating: int, 
                        feedback_text: Optional[str] = None) -> bool:
    """
    Логирует обратную связь по сессии.
    
    Args:
        session_id: ID сессии
        user_id: ID пользователя
        rating: Оценка (1-5)
        feedback_text: Текст обратной связи
        
    Returns:
        bool: True, если событие успешно отправлено
    """
    payload = {
        "session_id": session_id,
        "user_id": user_id,
        "rating": rating,
        "feedback_text": feedback_text
    }
    
    return send_event(payload, "session_feedback")

def log_system_event(event_name: str, details: Dict[str, Any]) -> bool:
    """
    Логирует системное событие.
    
    Args:
        event_name: Название события
        details: Детали события
        
    Returns:
        bool: True, если событие успешно отправлено
    """
    payload = {
        "event_name": event_name,
        "details": details
    }
    
    return send_event(payload, "system_event")
