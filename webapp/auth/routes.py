"""
Маршруты для аутентификации в веб-интерфейсе.
"""
import logging
from flask import Blueprint, request, jsonify, current_app

from webapp.auth.jwt_auth import login_user
from storage.database_unified import db_session, WebUser
from webapp.auth.jwt_auth import generate_password_hash, token_required, role_required
from utils.rate_limit import web_rate_limit  # Импортируем декоратор для rate-limiting

logger = logging.getLogger(__name__)

# Создаем blueprint
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
@web_rate_limit  # Применяем декоратор для ограничения частоты запросов
def login():
    """
    Аутентификация пользователя и выдача JWT-токена.
    """
    # Получаем данные из запроса
    data = request.get_json()
    
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'message': 'Missing username or password'}), 400
    
    username = data['username']
    password = data['password']
    
    # Аутентифицируем пользователя
    user_data = login_user(username, password)
    
    if not user_data:
        return jsonify({'message': 'Invalid username or password'}), 401
    
    # Возвращаем данные пользователя и токен
    return jsonify({
        'message': 'Login successful',
        'user': {
            'id': user_data['user_id'],
            'username': user_data['username'],
            'role': user_data['role']
        },
        'token': user_data['token']
    }), 200

@auth_bp.route('/check', methods=['GET'])
@token_required
@web_rate_limit  # Применяем декоратор для ограничения частоты запросов
def check_auth():
    """
    Проверка аутентификации пользователя.
    """
    from flask import g
    
    return jsonify({
        'message': 'Authentication valid',
        'user': {
            'id': g.user['sub'],
            'username': g.user['username'],
            'role': g.user['role']
        }
    }), 200

@auth_bp.route('/users', methods=['POST'])
@token_required
@role_required(['admin'])
@web_rate_limit  # Применяем декоратор для ограничения частоты запросов
def create_user():
    """
    Создание нового пользователя (только для администраторов).
    """
    # Получаем данные из запроса
    data = request.get_json()
    
    if not data or 'username' not in data or 'password' not in data or 'role' not in data:
        return jsonify({'message': 'Missing required fields'}), 400
    
    username = data['username']
    password = data['password']
    role = data['role']
    
    # Проверяем роль
    if role not in ['admin', 'operator', 'viewer']:
        return jsonify({'message': 'Invalid role'}), 400
    
    # Проверяем, существует ли пользователь с таким именем и создаем нового
    try:
        with db_session() as db:
            # Проверяем существование пользователя в той же сессии
            existing_user = db.query(WebUser).filter_by(username=username).first()
            
            if existing_user:
                return jsonify({'message': 'Username already exists'}), 409
            
            # Хешируем пароль
            password_hash = generate_password_hash(password)
            
            # Создаем пользователя в той же сессии
            new_user = WebUser(
                username=username,
                password_hash=password_hash,
                role=role,
                is_active=True
            )
            
            db.add(new_user)
            db.commit()
            
            # Получаем ID созданного пользователя
            user_id = new_user.id
            
            return jsonify({
                'message': 'User created successfully',
                'user_id': user_id
            }), 201
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return jsonify({'message': 'Failed to create user'}), 500

@auth_bp.route('/init-admin', methods=['POST'])
@web_rate_limit  # Применяем декоратор для ограничения частоты запросов
def init_admin():
    """
    Инициализация первого администратора (только если нет пользователей).
    """
    # Получаем данные из запроса
    data = request.get_json()
    
    if not data or 'username' not in data or 'password' not in data or 'init_key' not in data:
        return jsonify({'message': 'Missing required fields'}), 400
    
    # Проверяем ключ инициализации
    init_key = data['init_key']
    expected_key = current_app.config.get('ADMIN_INIT_KEY', 'change-me-in-production')
    
    if init_key != expected_key:
        return jsonify({'message': 'Invalid initialization key'}), 403
    
    username = data['username']
    password = data['password']
    
    # Проверяем, есть ли уже пользователи в системе и создаем администратора
    try:
        with db_session() as db:
            # Проверяем, существует ли пользователь с таким именем в той же сессии
            existing_user = db.query(WebUser).filter_by(username=username).first()
            
            if existing_user:
                return jsonify({'message': 'Username already exists'}), 409
            
            # Хешируем пароль
            password_hash = generate_password_hash(password)
            
            # Создаем администратора в той же сессии
            admin_user = WebUser(
                username=username,
                password_hash=password_hash,
                role='admin',
                is_active=True
            )
            
            db.add(admin_user)
            db.commit()
            
            # Получаем ID созданного пользователя
            user_id = admin_user.id
            
            return jsonify({
                'message': 'Admin user created successfully',
                'user_id': user_id
            }), 201
    except Exception as e:
        logger.error(f"Error creating admin user: {e}", exc_info=True)
        return jsonify({'message': 'Failed to create admin user'}), 500
