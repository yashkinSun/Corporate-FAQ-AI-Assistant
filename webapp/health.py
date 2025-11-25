"""
Health check endpoints для мониторинга состояния системы.
"""
import logging
from flask import Blueprint, jsonify
from utils.db_monitor import check_db_health, get_connection_stats

logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__)

@health_bp.route('/health')
def health_check():
    """
    Общий health check endpoint
    
    Returns:
        JSON: Статус здоровья системы
    """
    try:
        db_health = check_db_health()
        
        # Определяем общий статус системы
        overall_status = "healthy" if db_health["status"] == "healthy" else "unhealthy"
        
        return jsonify({
            "status": overall_status,
            "timestamp": db_health["timestamp"],
            "components": {
                "database": {
                    "status": db_health["status"],
                    "message": db_health["message"]
                }
            }
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return jsonify({
            "status": "unhealthy",
            "error": "Health check failed",
            "details": str(e)
        }), 500

@health_bp.route('/health/db')
def db_health_check():
    """
    Детальный health check для базы данных
    
    Returns:
        JSON: Подробная информация о состоянии БД
    """
    try:
        health_info = check_db_health()
        
        if health_info["status"] == "healthy":
            return jsonify(health_info)
        else:
            return jsonify(health_info), 503  # Service Unavailable
            
    except Exception as e:
        logger.error(f"Database health check failed: {e}", exc_info=True)
        return jsonify({
            "status": "unhealthy",
            "message": "Database health check failed",
            "error": str(e)
        }), 500

@health_bp.route('/health/db/connections')
def db_connections_info():
    """
    Информация о соединениях с базой данных
    
    Returns:
        JSON: Статистика соединений с БД
    """
    try:
        stats = get_connection_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Failed to get connection stats: {e}", exc_info=True)
        return jsonify({
            "error": "Failed to get connection statistics",
            "details": str(e)
        }), 500

@health_bp.route('/health/ready')
def readiness_check():
    """
    Readiness probe для Kubernetes/Docker
    
    Returns:
        JSON: Готовность системы к обработке запросов
    """
    try:
        db_health = check_db_health()
        
        if db_health["status"] == "healthy":
            return jsonify({
                "status": "ready",
                "message": "Service is ready to handle requests"
            })
        else:
            return jsonify({
                "status": "not_ready",
                "message": "Service is not ready - database issues",
                "details": db_health["message"]
            }), 503
            
    except Exception as e:
        logger.error(f"Readiness check failed: {e}", exc_info=True)
        return jsonify({
            "status": "not_ready",
            "message": "Readiness check failed",
            "error": str(e)
        }), 500

@health_bp.route('/health/live')
def liveness_check():
    """
    Liveness probe для Kubernetes/Docker
    
    Returns:
        JSON: Жизнеспособность системы
    """
    try:
        # Простая проверка - если мы можем ответить, значит живы
        return jsonify({
            "status": "alive",
            "message": "Service is alive"
        })
    except Exception as e:
        logger.error(f"Liveness check failed: {e}", exc_info=True)
        return jsonify({
            "status": "dead",
            "message": "Liveness check failed",
            "error": str(e)
        }), 500

