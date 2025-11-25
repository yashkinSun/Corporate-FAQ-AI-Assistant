"""
Модуль для реализации rate-limiting и защиты от злоупотреблений.
Использует Redis для хранения данных о лимитах.
"""
import time
import redis
import logging
from functools import wraps
from flask import request, jsonify
from typing import Callable, Dict, Optional, Union, Any

from config import (
    REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, REDIS_URL,
    RATE_LIMIT_ENABLED, TELEGRAM_RATE_LIMIT_SECONDS, TELEGRAM_RATE_LIMIT_MAX_VIOLATIONS,
    TELEGRAM_RATE_LIMIT_BLOCK_SECONDS, WEB_RATE_LIMIT_REQUESTS, WEB_RATE_LIMIT_MINUTES
)

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Инициализация Redis-клиента
try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=True
    )
    redis_client.ping()  # Проверка соединения
    logger.info("Redis connection established successfully")
except redis.ConnectionError as e:
    logger.error(f"Failed to connect to Redis: {e}")
    redis_client = None


class RateLimiter:
    """
    Класс для управления ограничениями запросов.
    Поддерживает различные типы ограничений для Telegram-бота и веб-интерфейса.
    """
    
    def __init__(self):
        self.enabled = RATE_LIMIT_ENABLED
        self.redis = redis_client
    
    def _get_key(self, prefix: str, identifier: str) -> str:
        """
        Формирует ключ для хранения в Redis.
        
        Args:
            prefix: Префикс ключа (например, 'telegram', 'web')
            identifier: Идентификатор пользователя или IP-адрес
            
        Returns:
            Строка ключа для Redis
        """
        return f"rate_limit:{prefix}:{identifier}"
    
    def _get_violation_key(self, prefix: str, identifier: str) -> str:
        """
        Формирует ключ для хранения количества нарушений.
        
        Args:
            prefix: Префикс ключа (например, 'telegram', 'web')
            identifier: Идентификатор пользователя или IP-адрес
            
        Returns:
            Строка ключа для Redis
        """
        return f"rate_limit_violations:{prefix}:{identifier}"
    
    def _get_block_key(self, prefix: str, identifier: str) -> str:
        """
        Формирует ключ для хранения информации о блокировке.
        
        Args:
            prefix: Префикс ключа (например, 'telegram', 'web')
            identifier: Идентификатор пользователя или IP-адрес
            
        Returns:
            Строка ключа для Redis
        """
        return f"rate_limit_block:{prefix}:{identifier}"
    
    def check_telegram_limit(self, user_id: Union[int, str]) -> Dict[str, Any]:
        """
        Проверяет ограничение для Telegram-пользователя.
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            Словарь с результатами проверки:
                - allowed: True, если запрос разрешен, иначе False
                - blocked_until: Время окончания блокировки (если заблокирован)
                - retry_after: Время до следующего разрешенного запроса (если превышен лимит)
        """
        if not self.enabled or not self.redis:
            return {"allowed": True}
        
        user_id = str(user_id)
        now = int(time.time())
        
        # Проверяем, заблокирован ли пользователь
        block_key = self._get_block_key("telegram", user_id)
        blocked_until = self.redis.get(block_key)
        
        if blocked_until:
            blocked_until = int(blocked_until)
            if now < blocked_until:
                logger.warning(f"Telegram user {user_id} is blocked until {blocked_until}")
                return {
                    "allowed": False,
                    "blocked_until": blocked_until,
                    "retry_after": blocked_until - now
                }
            else:
                # Блокировка истекла, удаляем ключ
                self.redis.delete(block_key)
        
        # Проверяем ограничение частоты запросов
        key = self._get_key("telegram", user_id)
        last_request = self.redis.get(key)
        
        if last_request:
            last_request = int(last_request)
            time_passed = now - last_request
            
            if time_passed < TELEGRAM_RATE_LIMIT_SECONDS:
                # Увеличиваем счетчик нарушений
                violation_key = self._get_violation_key("telegram", user_id)
                violations = self.redis.incr(violation_key)
                self.redis.expire(violation_key, 60)  # Сбрасываем счетчик через минуту
                
                # Если превышено максимальное количество нарушений, блокируем пользователя
                if violations > TELEGRAM_RATE_LIMIT_MAX_VIOLATIONS:
                    blocked_until = now + TELEGRAM_RATE_LIMIT_BLOCK_SECONDS
                    self.redis.set(block_key, blocked_until)
                    self.redis.expire(block_key, TELEGRAM_RATE_LIMIT_BLOCK_SECONDS)
                    logger.warning(f"Telegram user {user_id} blocked for {TELEGRAM_RATE_LIMIT_BLOCK_SECONDS} seconds")
                    return {
                        "allowed": False,
                        "blocked_until": blocked_until,
                        "retry_after": TELEGRAM_RATE_LIMIT_BLOCK_SECONDS
                    }
                
                logger.warning(f"Rate limit exceeded for Telegram user {user_id}, violations: {violations}")
                return {
                    "allowed": False,
                    "retry_after": TELEGRAM_RATE_LIMIT_SECONDS - time_passed
                }
        
        # Обновляем время последнего запроса
        self.redis.set(key, now)
        self.redis.expire(key, 60)  # Ключ истекает через минуту
        
        return {"allowed": True}
    
    def check_web_limit(self, ip_address: str) -> Dict[str, Any]:
        """
        Проверяет ограничение для веб-запросов.
        
        Args:
            ip_address: IP-адрес клиента
            
        Returns:
            Словарь с результатами проверки:
                - allowed: True, если запрос разрешен, иначе False
                - retry_after: Время до следующего разрешенного запроса (если превышен лимит)
        """
        if not self.enabled or not self.redis:
            return {"allowed": True}
        
        now = int(time.time())
        window = WEB_RATE_LIMIT_MINUTES * 60  # Окно в секундах
        
        # Ключ для хранения запросов в текущем окне
        key = self._get_key("web", ip_address)
        
        # Получаем текущее количество запросов
        count = self.redis.get(key)
        
        if count is None:
            # Первый запрос в окне
            self.redis.set(key, 1)
            self.redis.expire(key, window)
            return {"allowed": True}
        
        count = int(count)
        
        if count >= WEB_RATE_LIMIT_REQUESTS:
            # Превышен лимит запросов
            ttl = self.redis.ttl(key)
            logger.warning(f"Web rate limit exceeded for IP {ip_address}, count: {count}")
            return {
                "allowed": False,
                "retry_after": ttl
            }
        
        # Увеличиваем счетчик запросов
        self.redis.incr(key)
        
        return {"allowed": True}


# Создаем глобальный экземпляр RateLimiter
rate_limiter = RateLimiter()


def telegram_rate_limit(func: Callable) -> Callable:
    """
    Декоратор для ограничения частоты запросов в Telegram-боте.
    
    Args:
        func: Функция-обработчик сообщений Telegram
        
    Returns:
        Обернутая функция с проверкой ограничений
    """
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        if not RATE_LIMIT_ENABLED:
            return await func(update, context, *args, **kwargs)
        
        user_id = update.effective_user.id
        result = rate_limiter.check_telegram_limit(user_id)
        
        if not result["allowed"]:
            if "blocked_until" in result:
                # Пользователь заблокирован
                blocked_until = time.strftime('%H:%M:%S', time.localtime(result["blocked_until"]))
                await update.message.reply_text(
                    f"Вы временно заблокированы из-за слишком частых запросов. "
                    f"Повторите попытку после {blocked_until}."
                )
            else:
                # Превышен лимит запросов
                await update.message.reply_text(
                    "Пожалуйста, не отправляйте сообщения слишком часто. "
                    f"Повторите попытку через {result['retry_after']} секунд."
                )
            return None
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper


def web_rate_limit(func: Callable) -> Callable:
    """
    Декоратор для ограничения частоты запросов в веб-интерфейсе.
    
    Args:
        func: Функция-обработчик запросов Flask
        
    Returns:
        Обернутая функция с проверкой ограничений
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not RATE_LIMIT_ENABLED:
            return func(*args, **kwargs)
        
        ip_address = request.remote_addr
        result = rate_limiter.check_web_limit(ip_address)
        
        if not result["allowed"]:
            response = {
                "error": "Rate limit exceeded",
                "retry_after": result["retry_after"]
            }
            return jsonify(response), 429
        
        return func(*args, **kwargs)
    
    return wrapper
