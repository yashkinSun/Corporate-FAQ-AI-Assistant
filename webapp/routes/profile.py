"""
Маршруты для работы с профилем пользователя.
"""
import logging
from flask import Blueprint, render_template, request, jsonify, g
from webapp.auth.jwt_auth import token_required, check_password, generate_password_hash
from storage.database_unified import db_session, WebUser

logger = logging.getLogger(__name__)

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/profile')
def profile_page():
    """
    Отображает страницу профиля пользователя.
    """
    return render_template('tailwind/profile.html')

@profile_bp.route('/api/profile', methods=['GET'])
@token_required
def get_profile():
    """
    Возвращает данные профиля пользователя.
    """
    with db_session() as db:
    try:
        # Получаем данные пользователя из базы данных
        user_id = g.user['sub']
        
        # Запрос к базе данных для получения полных данных пользователя
        user = db.query(WebUser).filter_by(id=user_id).first()
        
        if not user:
            return jsonify({'message': 'Пользователь не найден', 'code': 'user_not_found'}), 404
        
        # Формируем ответ
        user_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'last_login': user.last_login,
            'created_at': user.created_at
        }
        
        return jsonify({'user': user_data}), 200
    except Exception as e:
        logger.error(f"Ошибка при получении данных профиля: {e}")
        return jsonify({'message': 'Внутренняя ошибка сервера', 'code': 'server_error'}), 500
    finally:

@profile_bp.route('/api/profile', methods=['PUT'])
@token_required
def update_profile():
    """
    Обновляет данные профиля пользователя.
    """
    with db_session() as db:
    try:
        # Получаем данные из запроса
        data = request.json
        user_id = g.user['sub']
        
        # Проверяем наличие обязательных полей
        if 'email' not in data:
            return jsonify({'message': 'Отсутствуют обязательные поля', 'code': 'missing_fields'}), 400
        
        # Обновляем email пользователя
        update_web_user_email(db, user_id, data['email'])
        
        # Получаем обновленные данные пользователя
        user = db.query(WebUser).filter_by(id=user_id).first()
        
        # Формируем ответ
        user_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'last_login': user.last_login,
            'created_at': user.created_at
        }
        
        return jsonify({'message': 'Профиль успешно обновлен', 'user': user_data}), 200
    except Exception as e:
        logger.error(f"Ошибка при обновлении профиля: {e}")
        db.rollback()
        return jsonify({'message': 'Внутренняя ошибка сервера', 'code': 'server_error'}), 500
    finally:

@profile_bp.route('/api/profile/password', methods=['PUT'])
@token_required
def change_password():
    """
    Изменяет пароль пользователя.
    """
    with db_session() as db:
    try:
        # Получаем данные из запроса
        data = request.json
        user_id = g.user['sub']
        
        # Проверяем наличие обязательных полей
        if 'current_password' not in data or 'new_password' not in data:
            return jsonify({'message': 'Отсутствуют обязательные поля', 'code': 'missing_fields'}), 400
        
        # Получаем пользователя из базы данных
        user = db.query(WebUser).filter_by(id=user_id).first()
        
        # Проверяем текущий пароль
        if not check_password(data['current_password'], user.password_hash):
            return jsonify({'message': 'Текущий пароль указан неверно', 'code': 'invalid_password'}), 401
        
        # Генерируем хеш нового пароля
        new_password_hash = generate_password_hash(data['new_password'])
        
        # Обновляем пароль пользователя
        update_web_user_password(db, user_id, new_password_hash)
        
        return jsonify({'message': 'Пароль успешно изменен'}), 200
    except Exception as e:
        logger.error(f"Ошибка при изменении пароля: {e}")
        db.rollback()
        return jsonify({'message': 'Внутренняя ошибка сервера', 'code': 'server_error'}), 500
    finally:
