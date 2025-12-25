"""
Модуль для управления контекстной памятью диалогов.
Использует Redis для хранения истории сообщений пользователей.

Основные функции:
- Хранение последних N сообщений пользователя
- Определение follow-up вопросов
- Переформулирование запросов с учетом контекста
- Автоматическая очистка старых данных через TTL

Принцип работы: Graceful Degradation
- Если Redis недоступен, бот продолжает работать без контекста
- Все функции возвращают безопасные значения по умолчанию
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Optional

import redis

from config import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_PASSWORD,
    CONTEXT_MEMORY_ENABLED,
    CONTEXT_MEMORY_MAX_MESSAGES,
    CONTEXT_MEMORY_TTL_DAYS,
    CONTEXT_MEMORY_REDIS_DB
)

logger = logging.getLogger(__name__)

# Глобальный Redis-клиент для контекстной памяти
redis_client: Optional[redis.Redis] = None


def _init_redis() -> Optional[redis.Redis]:
    """
    Инициализация Redis-клиента с graceful degradation.
    
    Использует отдельную базу данных Redis (db=1 по умолчанию) для изоляции
    от rate-limiting (db=0).
    
    Returns:
        redis.Redis или None, если подключение не удалось или функция отключена
    """
    global redis_client
    
    if not CONTEXT_MEMORY_ENABLED:
        logger.info("Context memory disabled in config (CONTEXT_MEMORY_ENABLED=False)")
        return None
    
    try:
        client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=CONTEXT_MEMORY_REDIS_DB,
            password=REDIS_PASSWORD if REDIS_PASSWORD else None,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            health_check_interval=30
        )
        client.ping()
        logger.info(f"Context memory Redis connected successfully (host={REDIS_HOST}, db={CONTEXT_MEMORY_REDIS_DB})")
        return client
    except redis.ConnectionError as e:
        logger.warning(f"Context memory Redis unavailable: {e}. Bot will work without context memory.")
        return None
    except Exception as e:
        logger.error(f"Unexpected error connecting to Redis for context memory: {e}")
        return None


def _check_redis_health() -> bool:
    """
    Проверка доступности Redis и автоматическое переподключение.
    
    Returns:
        True если Redis доступен, False иначе
    """
    global redis_client
    
    if redis_client is None:
        # Попытка переподключения
        redis_client = _init_redis()
        return redis_client is not None
    
    try:
        redis_client.ping()
        return True
    except redis.RedisError:
        logger.warning("Redis health check failed, attempting reconnect...")
        redis_client = _init_redis()
        return redis_client is not None


def get_context(user_id: int) -> List[Dict]:
    """
    Получить историю диалога пользователя из Redis.
    
    Args:
        user_id: ID пользователя Telegram
        
    Returns:
        Список сообщений в формате [{"role": "user"|"assistant", "content": str, "timestamp": str}]
        или пустой список, если контекст недоступен
    """
    if redis_client is None:
        return []
    
    try:
        key = f"context:{user_id}"
        data = redis_client.get(key)
        
        if data is None:
            return []
        
        context = json.loads(data)
        
        # Ограничиваем количество сообщений
        if len(context) > CONTEXT_MEMORY_MAX_MESSAGES:
            context = context[-CONTEXT_MEMORY_MAX_MESSAGES:]
        
        return context
        
    except redis.RedisError as e:
        logger.warning(f"Redis error getting context for user {user_id}: {e}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error for user {user_id} context: {e}")
        # Удаляем поврежденные данные
        try:
            redis_client.delete(f"context:{user_id}")
        except Exception:
            pass
        return []
    except Exception as e:
        logger.error(f"Unexpected error getting context for user {user_id}: {e}")
        return []


def save_message(user_id: int, role: str, content: str) -> bool:
    """
    Сохранить сообщение в историю диалога пользователя.
    
    Args:
        user_id: ID пользователя Telegram
        role: 'user' или 'assistant'
        content: Текст сообщения
        
    Returns:
        True если сохранено успешно, False иначе
    """
    if redis_client is None:
        return False
    
    if role not in ("user", "assistant"):
        logger.warning(f"Invalid role '{role}' for save_message, expected 'user' or 'assistant'")
        return False
    
    try:
        key = f"context:{user_id}"
        
        # Получаем текущий контекст
        context = get_context(user_id)
        
        # Добавляем новое сообщение с ограничением длины контента
        message = {
            "role": role,
            "content": content[:1000] if content else "",
            "timestamp": datetime.utcnow().isoformat()
        }
        context.append(message)
        
        # Ограничиваем количество сообщений
        if len(context) > CONTEXT_MEMORY_MAX_MESSAGES:
            context = context[-CONTEXT_MEMORY_MAX_MESSAGES:]
        
        # Сохраняем с TTL
        ttl_seconds = CONTEXT_MEMORY_TTL_DAYS * 24 * 60 * 60
        redis_client.setex(key, ttl_seconds, json.dumps(context, ensure_ascii=False))
        
        logger.debug(f"Saved {role} message for user {user_id}, context size: {len(context)}")
        return True
        
    except redis.RedisError as e:
        logger.warning(f"Redis error saving message for user {user_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error saving message for user {user_id}: {e}")
        return False


def is_followup_question(current_question: str, context: List[Dict]) -> bool:
    """
    Определить, является ли вопрос follow-up (продолжением предыдущего диалога).
    
    Использует эвристику на основе ключевых слов для быстрого определения.
    Короткие вопросы (<50 символов) с ключевыми словами почти всегда являются follow-up.
    
    Args:
        current_question: Текущий вопрос пользователя
        context: История диалога
        
    Returns:
        True если это follow-up вопрос, False иначе
    """
    if not context:
        return False
    
    if not current_question or not current_question.strip():
        return False
    
    # Ключевые слова, указывающие на follow-up вопрос
    followup_keywords_ru = [
        "подробнее", "расскажи больше", "а сколько", "какие еще", "какие ещё",
        "еще варианты", "ещё варианты", "что еще", "что ещё", "а как",
        "а когда", "а где", "а почему", "а зачем", "а кто", "а что",
        "расскажи про это", "объясни", "уточни", "поясни"
    ]
    
    followup_keywords_en = [
        "more details", "tell me more", "what else", "how much",
        "any other", "explain more", "elaborate", "clarify",
        "what about", "how about", "and what", "and how", "and when"
    ]
    
    # Местоимения, указывающие на ссылку на предыдущий контекст
    pronouns_ru = [
        "это", "они", "он", "она", "оно", "их", "его", "её", "ее",
        "этого", "этой", "этих", "этому", "этим", "об этом", "про это"
    ]
    
    pronouns_en = [
        "this", "that", "they", "it", "them", "these", "those",
        "about it", "about this", "about them"
    ]
    
    all_keywords = followup_keywords_ru + followup_keywords_en + pronouns_ru + pronouns_en
    
    question_lower = current_question.lower().strip()
    
    # Короткие вопросы с ключевыми словами — почти всегда follow-up
    if len(current_question) < 50:
        for keyword in all_keywords:
            if keyword in question_lower:
                logger.debug(f"Follow-up detected by keyword '{keyword}' in short question")
                return True
    
    # Для более длинных вопросов проверяем только явные маркеры follow-up
    explicit_markers = [
        "подробнее", "расскажи больше", "tell me more", "more details",
        "elaborate", "уточни", "поясни", "объясни подробнее"
    ]
    
    for marker in explicit_markers:
        if marker in question_lower:
            logger.debug(f"Follow-up detected by explicit marker '{marker}'")
            return True
    
    return False


def reformulate_question(current_question: str, context: List[Dict]) -> str:
    """
    Переформулировать follow-up вопрос с учетом контекста предыдущего диалога.
    
    Добавляет к текущему вопросу информацию о предыдущем вопросе и ответе,
    чтобы RAG-система могла лучше понять контекст запроса.
    
    Args:
        current_question: Текущий вопрос пользователя
        context: История диалога
        
    Returns:
        Переформулированный вопрос или оригинальный, если контекст пуст
    """
    if not context:
        return current_question
    
    if not current_question or not current_question.strip():
        return current_question
    
    # Получаем последний вопрос и ответ из контекста
    last_user_msg = None
    last_assistant_msg = None
    
    for msg in reversed(context):
        if msg.get("role") == "user" and last_user_msg is None:
            last_user_msg = msg.get("content", "")
        elif msg.get("role") == "assistant" and last_assistant_msg is None:
            last_assistant_msg = msg.get("content", "")
        
        if last_user_msg and last_assistant_msg:
            break
    
    if not last_user_msg:
        return current_question
    
    # Ограничиваем длину предыдущего ответа для экономии токенов
    truncated_assistant_msg = last_assistant_msg[:500] if last_assistant_msg else "Нет ответа"
    
    # Формируем расширенный вопрос с контекстом
    reformulated = f"""Контекст предыдущего диалога:
- Предыдущий вопрос пользователя: {last_user_msg}
- Предыдущий ответ бота: {truncated_assistant_msg}

Текущий вопрос пользователя: {current_question}

Ответь на текущий вопрос, учитывая контекст предыдущего диалога."""
    
    logger.debug(f"Reformulated question for user, original length: {len(current_question)}, new length: {len(reformulated)}")
    
    return reformulated.strip()


def clear_context(user_id: int) -> bool:
    """
    Очистить историю диалога пользователя.
    
    Используется для команды /clear, позволяющей пользователю
    начать диалог с чистого листа.
    
    Args:
        user_id: ID пользователя Telegram
        
    Returns:
        True если очистка прошла успешно, False иначе
    """
    if redis_client is None:
        return False
    
    try:
        key = f"context:{user_id}"
        result = redis_client.delete(key)
        logger.info(f"Context cleared for user {user_id}, keys deleted: {result}")
        return True
    except redis.RedisError as e:
        logger.warning(f"Redis error clearing context for user {user_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error clearing context for user {user_id}: {e}")
        return False


def get_memory_stats() -> Dict:
    """
    Получить статистику использования памяти Redis для контекстной памяти.
    
    Полезно для мониторинга и отладки.
    
    Returns:
        Словарь со статистикой или пустой словарь при ошибке
    """
    if redis_client is None:
        return {"status": "disabled", "message": "Context memory is disabled or Redis unavailable"}
    
    try:
        info = redis_client.info("memory")
        return {
            "status": "active",
            "used_memory_human": info.get("used_memory_human", "N/A"),
            "used_memory_peak_human": info.get("used_memory_peak_human", "N/A"),
            "total_keys": redis_client.dbsize(),
            "redis_db": CONTEXT_MEMORY_REDIS_DB
        }
    except redis.RedisError as e:
        logger.warning(f"Redis error getting memory stats: {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error getting memory stats: {e}")
        return {"status": "error", "message": str(e)}


# Инициализация Redis-клиента при импорте модуля
redis_client = _init_redis()
