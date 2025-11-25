"""
Модуль для мониторинга состояния базы данных и соединений.
"""
import logging
from typing import Dict, Any
from sqlalchemy import event
from sqlalchemy.engine import Engine

from storage.database_unified import engine

logger = logging.getLogger(__name__)

# Счетчики соединений
connection_stats = {
    'total_connections': 0,
    'active_connections': 0,
    'closed_connections': 0
}

@event.listens_for(Engine, "connect")
def log_connection_open(dbapi_connection, connection_record):
    """Логирует открытие нового соединения с БД"""
    connection_stats['total_connections'] += 1
    connection_stats['active_connections'] += 1
    logger.debug(f"New DB connection established. Total: {connection_stats['total_connections']}, Active: {connection_stats['active_connections']}")

@event.listens_for(Engine, "close")
def log_connection_close(dbapi_connection, connection_record):
    """Логирует закрытие соединения с БД"""
    connection_stats['active_connections'] -= 1
    connection_stats['closed_connections'] += 1
    logger.debug(f"DB connection closed. Active: {connection_stats['active_connections']}, Closed: {connection_stats['closed_connections']}")

def get_connection_stats() -> Dict[str, Any]:
    """
    Получает статистику соединений с базой данных
    
    Returns:
        Dict[str, Any]: Статистика соединений
    """
    try:
        pool = engine.pool
        pool_stats = {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid()
        }
    except Exception as e:
        logger.error(f"Error getting pool stats: {e}")
        pool_stats = {
            "pool_size": "unknown",
            "checked_in": "unknown", 
            "checked_out": "unknown",
            "overflow": "unknown",
            "invalid": "unknown"
        }
    
    return {
        "connection_counts": connection_stats.copy(),
        "pool_stats": pool_stats,
        "engine_url": str(engine.url).replace(engine.url.password or '', '***') if engine.url.password else str(engine.url)
    }

def check_db_health() -> Dict[str, Any]:
    """
    Проверяет состояние базы данных
    
    Returns:
        Dict[str, Any]: Результат проверки здоровья БД
    """
    from storage.database_unified import db_session
    
    try:
        with db_session() as db:
            # Простой запрос для проверки соединения
            result = db.execute("SELECT 1").scalar()
            
            if result == 1:
                status = "healthy"
                message = "Database connection is working"
            else:
                status = "unhealthy"
                message = "Database query returned unexpected result"
                
    except Exception as e:
        status = "unhealthy"
        message = f"Database connection failed: {str(e)}"
        logger.error(f"Database health check failed: {e}", exc_info=True)
    
    stats = get_connection_stats()
    
    return {
        "status": status,
        "message": message,
        "timestamp": logging.Formatter().formatTime(logging.LogRecord(
            name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None
        )),
        "connection_stats": stats
    }

def log_pool_status():
    """Логирует текущее состояние connection pool"""
    stats = get_connection_stats()
    logger.info(f"Connection pool status: {stats['pool_stats']}")
    logger.info(f"Connection counts: {stats['connection_counts']}")

# Инициализируем мониторинг при импорте модуля
logger.info("Database monitoring initialized")

