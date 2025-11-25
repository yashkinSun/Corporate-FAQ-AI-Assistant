import json
import logging
import os
from typing import List, Dict, Any, Optional

from config import FOLLOWUP_MAP_PATH

logger = logging.getLogger(__name__)

def load_followup_map() -> Dict[str, Any]:
    """
    Загружает карту follow-up вопросов из JSON файла.
    
    Returns:
        Dict[str, Any]: Структура данных с follow-up вопросами
    """
    try:
        with open(FOLLOWUP_MAP_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error loading followup map: {e}")
        # Возвращаем базовую структуру, если файл не найден или некорректен
        return {
            "other": {
                "keywords": [],
                "followups": [
                    "У вас есть ещё вопросы?",
                    "Хотите задать что-то ещё?"
                ]
            }
        }

def get_followup_suggestions(user_query: str, language: str = 'ru', context_low_confidence: bool = False) -> List[str]:
    """
    Генерирует контекстные предложения для follow-up вопросов на основе запроса пользователя.
    
    Args:
        user_query: Запрос пользователя
        language: Язык пользователя ('ru' или 'en')
        context_low_confidence: Флаг низкой уверенности в контексте диалога
        
    Returns:
        List[str]: Список предложений для follow-up вопросов
    """
    followup_map = load_followup_map()
    user_query_lower = user_query.lower()
    
    # Определяем категорию запроса на основе ключевых слов
    matched_category = "other"  # Категория по умолчанию
    max_matches = 0
    
    for category, data in followup_map.items():
        keywords = data.get("keywords", [])
        matches = sum(1 for keyword in keywords if keyword.lower() in user_query_lower)
        
        # Требуем минимум 2 совпадения для более точного определения категории
        if matches >= 2 and matches > max_matches:
            max_matches = matches
            matched_category = category
    
    # Получаем follow-up вопросы для найденной категории
    followups = followup_map.get(matched_category, {}).get("followups", [])
    
    # Если язык английский, переводим вопросы (в будущем можно использовать переводчик)
    if language == 'en':
        # Здесь можно добавить перевод с использованием utils/translator.py
        # Пока используем заглушку с базовыми английскими вопросами
        if matched_category == "shipping":
            return [
                "Which shipping company do you prefer?",
                "Could you specify the delivery address?",
                "Would you like to know the shipping cost?",
                "How can I track my package?"
            ]
        elif matched_category == "payment":
            return [
                "Would you like to change the payment method?",
                "Do you want to check the invoice status?",
                "Need to clarify payment terms?",
                "How to request a refund?"
            ]
        elif matched_category == "customs":
            return [
                "What documents are needed for customs clearance?",
                "How is the customs duty calculated?",
                "What to do if the package is detained at customs?"
            ]
        elif matched_category == "products":
            return [
                "How to check product availability?",
                "How to modify an order after placement?",
                "How to return a product?"
            ]
        else:
            return [
                "Do you have any other questions?",
                "Would you like to ask something else?"
            ]
    
    # Добавляем кнопку оператора только при низкой уверенности
    if context_low_confidence:
        operator_help = "Нужна помощь оператора?" if language == 'ru' else "Do you need operator assistance?"
        if operator_help not in followups:
            followups.append(operator_help)
    
    # Возвращаем 2-3 предложения
    return followups[:3] if followups else [
        "У вас есть ещё вопросы?" if language == 'ru' else "Do you have any other questions?",
        "Хотите задать что-то ещё?" if language == 'ru' else "Would you like to ask something else?"
    ]
