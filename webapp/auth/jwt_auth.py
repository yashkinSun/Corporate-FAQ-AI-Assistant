"""
Модуль для аутентификации и авторизации в веб-интерфейсе.
Реализует JWT-авторизацию для API.
"""
import logging
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Any, Optional, Callable

import jwt
from flask import request, jsonify, current_app, g

from config import JWT_SECRET_KEY, JWT_ACCESS_TOKEN_EXPIRES
from storage.database_unified import db_session, WebUser

logger = logging.getLogger(__name__)

def generate_password_hash(password: str) -> str:
    """
    Генерирует хеш пароля с использованием bcrypt.
    
    Args:
        password: Пароль в открытом виде
        
    Returns:
        str: Хеш пароля
    """
    # Генерируем соль и хешируем пароль
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

# Добавляем алиас для совместимости с routes.py
hash_password = generate_password_hash

def check_password(password: str, password_hash: str) -> bool:
    """
    Проверяет соответствие пароля хешу.
    
    Args:
        password: Пароль в открытом виде
        password_hash: Хеш пароля
        
    Returns:
        bool: True, если пароль соответствует хешу
    """
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

def create_access_token(user_id: int, username: str, role: str) -> str:
    """
    Создает JWT-токен доступа.
    
    Args:
        user_id: ID пользователя
        username: Имя пользователя
        role: Роль пользователя
        
    Returns:
        str: JWT-токен
    """
    # Устанавливаем время истечения токена
    expires = datetime.utcnow() + timedelta(seconds=JWT_ACCESS_TOKEN_EXPIRES)
    
    # Создаем payload токена
    payload = {
        'sub': user_id,
        'username': username,
        'role': role,
        'exp': expires
    }
    
    # Генерируем токен
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')
    
    return token

def verify_token(token: str) -> Dict[str, Any]:
    """
    Проверяет JWT-токен и возвращает данные пользователя.
    
    Args:
        token: JWT-токен
        
    Returns:
        Dict[str, Any]: Данные пользователя или None, если токен недействителен
    """
    try:
        # Декодируем токен с отключенной проверкой срока действия
        # Это позволит нам самостоятельно обработать истекшие токены
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'], options={"verify_exp": False})
        
        # Проверяем срок действия
        if 'exp' in payload and datetime.fromtimestamp(payload['exp']) < datetime.utcnow():
            # Если токен истек, но не более чем на 7 дней, автоматически продлеваем его
            expiration_delta = datetime.utcnow() - datetime.fromtimestamp(payload['exp'])
            if expiration_delta.days <= 7:
                # Создаем новый токен с теми же данными, но с обновленным сроком действия
                new_token = create_access_token(
                    user_id=payload['sub'],
                    username=payload['username'],
                    role=payload['role']
                )
                # Добавляем информацию о продлении в payload
                payload['renewed'] = True
                payload['original_exp'] = payload['exp']
                payload['exp'] = (datetime.utcnow() + timedelta(seconds=JWT_ACCESS_TOKEN_EXPIRES)).timestamp()
                
                # Логируем продление токена
                logger.info(f"Token for user {payload['username']} was automatically renewed")
                
                # Возвращаем обновленный payload
                return payload
            else:
                # Если токен истек более 7 дней назад, считаем его недействительным
                logger.warning(f"Token expired more than 7 days ago for user {payload.get('username', 'unknown')}")
                return None
        
        return payload
    except jwt.PyJWTError as e:
        logger.error(f"JWT verification error: {e}")
        return None

def login_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Аутентифицирует пользователя и возвращает JWT-токен.
    
    Args:
        username: Имя пользователя
        password: Пароль
        
    Returns:
        Optional[Dict[str, Any]]: Данные пользователя с токеном или None, если аутентификация не удалась
    """
    logger.debug(f"Attempting login for user: {username}")
    
    try:
        with db_session() as db:
            # Получаем пользователя по имени из той же сессии
            user = db.query(WebUser).filter_by(username=username).first()
            
            # Проверяем существование пользователя и активность
            if not user:
                logger.debug(f"User {username} not found")
                return None
                
            if not user.is_active:
                logger.debug(f"User {username} is not active")
                return None
            
            # Проверяем пароль
            if not check_password(password, user.password_hash):
                logger.debug(f"Invalid password for user {username}")
                return None
            
            # Обновляем время последнего входа в той же сессии
            user.last_login = datetime.utcnow()
            db.commit()
            
            logger.debug(f"Login successful for user {username}")
            
            # Создаем токен
            token = create_access_token(user.id, user.username, user.role)
            
            return {
                'user_id': user.id,
                'username': user.username,
                'role': user.role,
                'token': token
            }
    except Exception as e:
        logger.error(f"Login error for user {username}: {e}", exc_info=True)
        return None

def token_required(f: Callable) -> Callable:
    """
    Декоратор для защиты маршрутов API, требующих аутентификации.
    
    Args:
        f: Функция-обработчик маршрута
        
    Returns:
        Callable: Обертка функции
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Получаем токен из заголовка Authorization
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'message': 'Missing or invalid token'}), 401
        
        token = auth_header.split(' ')[1]
        
        # Проверяем токен
        payload = verify_token(token)
        if not payload:
            return jsonify({'message': 'Invalid or expired token'}), 401
        
        # Сохраняем данные пользователя в g для использования в обработчике
        g.user = payload
        
        return f(*args, **kwargs)
    
    return decorated

def role_required(roles: list) -> Callable:
    """
    Декоратор для проверки роли пользователя.
    
    Args:
        roles: Список разрешенных ролей
        
    Returns:
        Callable: Декоратор
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            # Проверяем, что пользователь аутентифицирован
            if not hasattr(g, 'user'):
                return jsonify({'message': 'Authentication required'}), 401
            
            # Проверяем роль пользователя
            if g.user['role'] not in roles:
                return jsonify({'message': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        
        return decorated
    
    return decorator
