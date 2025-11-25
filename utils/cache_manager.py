"""
Модуль для управления кэшированием запросов к внешним API и результатов поиска.
Реализует многоуровневое кэширование для оптимизации времени ответа бота.
"""
import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional, Tuple, Union

import redis
from config import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, CACHE_TTL

logger = logging.getLogger(__name__)

class CacheManager:
    """
    Менеджер кэша для оптимизации запросов к внешним API и результатов поиска.
    Поддерживает кэширование в Redis и локальный кэш в памяти.
    """
    
    def __init__(self, prefix: str = "bot_cache", ttl: int = CACHE_TTL):
        """
        Инициализирует менеджер кэша.
        
        Args:
            prefix: Префикс для ключей кэша в Redis
            ttl: Время жизни кэша в секундах (по умолчанию из конфигурации)
        """
        self.prefix = prefix
        self.ttl = ttl
        self.local_cache = {}  # Локальный кэш в памяти для самых частых запросов
        self.local_cache_ttl = {}  # Время истечения для локального кэша
        
        # Инициализация подключения к Redis
        try:
            self.redis = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD,
                decode_responses=True
            )
            self.redis_available = True
            logger.info("Redis connection established successfully")
        except Exception as e:
            self.redis_available = False
            logger.warning(f"Failed to connect to Redis: {e}. Using only local cache.")
    
    def _generate_key(self, data: Union[str, Dict[str, Any]]) -> str:
        """
        Генерирует ключ кэша на основе входных данных.
        
        Args:
            data: Данные для генерации ключа (строка или словарь)
            
        Returns:
            str: Ключ кэша
        """
        if isinstance(data, dict):
            # Сортируем ключи для обеспечения стабильности хеширования
            data_str = json.dumps(data, sort_keys=True)
        else:
            data_str = str(data)
        
        # Создаем хеш для использования в качестве ключа
        key_hash = hashlib.md5(data_str.encode('utf-8')).hexdigest()
        return f"{self.prefix}:{key_hash}"
    
    def get(self, key_data: Union[str, Dict[str, Any]]) -> Optional[Any]:
        """
        Получает данные из кэша.
        
        Args:
            key_data: Данные для генерации ключа кэша
            
        Returns:
            Optional[Any]: Данные из кэша или None, если кэш не найден
        """
        key = self._generate_key(key_data)
        
        # Сначала проверяем локальный кэш
        if key in self.local_cache:
            # Проверяем, не истек ли срок действия
            if time.time() < self.local_cache_ttl.get(key, 0):
                logger.debug(f"Cache hit (local): {key}")
                return self.local_cache[key]
            else:
                # Удаляем истекший кэш
                del self.local_cache[key]
                if key in self.local_cache_ttl:
                    del self.local_cache_ttl[key]
        
        # Если локальный кэш не найден или истек, проверяем Redis
        if self.redis_available:
            try:
                cached_data = self.redis.get(key)
                if cached_data:
                    # Десериализуем данные из JSON
                    data = json.loads(cached_data)
                    
                    # Обновляем локальный кэш
                    self.local_cache[key] = data
                    self.local_cache_ttl[key] = time.time() + self.ttl
                    
                    logger.debug(f"Cache hit (Redis): {key}")
                    return data
            except Exception as e:
                logger.error(f"Error retrieving from Redis cache: {e}")
        
        logger.debug(f"Cache miss: {key}")
        return None
    
    def set(self, key_data: Union[str, Dict[str, Any]], value: Any, ttl: Optional[int] = None) -> bool:
        """
        Сохраняет данные в кэш.
        
        Args:
            key_data: Данные для генерации ключа кэша
            value: Данные для сохранения
            ttl: Время жизни кэша в секундах (если None, используется значение по умолчанию)
            
        Returns:
            bool: True, если данные успешно сохранены
        """
        if ttl is None:
            ttl = self.ttl
            
        key = self._generate_key(key_data)
        
        # Сериализуем данные в JSON
        try:
            value_json = json.dumps(value)
        except (TypeError, ValueError) as e:
            logger.error(f"Error serializing cache value: {e}")
            return False
        
        # Сохраняем в локальный кэш
        self.local_cache[key] = value
        self.local_cache_ttl[key] = time.time() + ttl
        
        # Сохраняем в Redis, если доступен
        if self.redis_available:
            try:
                self.redis.setex(key, ttl, value_json)
                logger.debug(f"Cache set: {key}")
                return True
            except Exception as e:
                logger.error(f"Error setting Redis cache: {e}")
                return False
        
        return True
    
    def delete(self, key_data: Union[str, Dict[str, Any]]) -> bool:
        """
        Удаляет данные из кэша.
        
        Args:
            key_data: Данные для генерации ключа кэша
            
        Returns:
            bool: True, если данные успешно удалены
        """
        key = self._generate_key(key_data)
        
        # Удаляем из локального кэша
        if key in self.local_cache:
            del self.local_cache[key]
        if key in self.local_cache_ttl:
            del self.local_cache_ttl[key]
        
        # Удаляем из Redis, если доступен
        if self.redis_available:
            try:
                self.redis.delete(key)
                logger.debug(f"Cache deleted: {key}")
                return True
            except Exception as e:
                logger.error(f"Error deleting from Redis cache: {e}")
                return False
        
        return True
    
    def clear_prefix(self, prefix: str) -> bool:
        """
        Очищает все ключи кэша с указанным префиксом.
        
        Args:
            prefix: Префикс ключей для очистки
            
        Returns:
            bool: True, если кэш успешно очищен
        """
        # Очищаем локальный кэш
        keys_to_delete = []
        full_prefix = f"{self.prefix}:{prefix}"
        
        for key in self.local_cache.keys():
            if key.startswith(full_prefix):
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            del self.local_cache[key]
            if key in self.local_cache_ttl:
                del self.local_cache_ttl[key]
        
        # Очищаем Redis, если доступен
        if self.redis_available:
            try:
                # Получаем все ключи с указанным префиксом
                pattern = f"{full_prefix}*"
                keys = self.redis.keys(pattern)
                
                if keys:
                    self.redis.delete(*keys)
                    logger.debug(f"Cleared {len(keys)} keys with prefix: {prefix}")
                
                return True
            except Exception as e:
                logger.error(f"Error clearing Redis cache with prefix {prefix}: {e}")
                return False
        
        return True
    
    def clear_all(self) -> bool:
        """
        Очищает весь кэш.
        
        Returns:
            bool: True, если кэш успешно очищен
        """
        # Очищаем локальный кэш
        self.local_cache.clear()
        self.local_cache_ttl.clear()
        
        # Очищаем Redis, если доступен
        if self.redis_available:
            try:
                # Получаем все ключи с префиксом бота
                pattern = f"{self.prefix}:*"
                keys = self.redis.keys(pattern)
                
                if keys:
                    self.redis.delete(*keys)
                    logger.debug(f"Cleared all cache ({len(keys)} keys)")
                
                return True
            except Exception as e:
                logger.error(f"Error clearing all Redis cache: {e}")
                return False
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику использования кэша.
        
        Returns:
            Dict[str, Any]: Статистика кэша
        """
        stats = {
            "local_cache_size": len(self.local_cache),
            "redis_available": self.redis_available,
            "redis_cache_size": 0,
            "ttl": self.ttl
        }
        
        if self.redis_available:
            try:
                pattern = f"{self.prefix}:*"
                keys = self.redis.keys(pattern)
                stats["redis_cache_size"] = len(keys)
            except Exception as e:
                logger.error(f"Error getting Redis cache stats: {e}")
        
        return stats


# Создаем глобальный экземпляр менеджера кэша
cache_manager = CacheManager()
