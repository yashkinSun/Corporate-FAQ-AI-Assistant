"""
Маршруты для работы с историей запросов.
"""
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, g
from webapp.auth.jwt_auth import token_required
from storage.database_unified import db_session, Message, UserSession

logger = logging.getLogger(__name__)

history_bp = Blueprint('history', __name__)

@history_bp.route('/api/history', methods=['GET'])
@token_required
def get_history():
    """
    Возвращает историю запросов с фильтрацией и пагинацией.
    """
    with db_session() as db:
    try:
        # Получаем параметры запроса
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        interface = request.args.get('interface')
        query = request.args.get('query')
        
        # Преобразуем строки дат в объекты datetime
        start_date = None
        end_date = None
        
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        
        if end_date_str:
            # Устанавливаем конец дня для end_date
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            end_date = end_date.replace(hour=23, minute=59, second=59)
        
        # Получаем историю сообщений
        history_items, total = get_message_history(
            db, 
            start_date=start_date,
            end_date=end_date,
            interface=interface if interface and interface != 'all' else None,
            query=query,
            page=page,
            per_page=per_page
        )
        
        return jsonify({
            'history': history_items,
            'total': total,
            'page': page,
            'per_page': per_page
        }), 200
    except Exception as e:
        logger.error(f"Ошибка при получении истории запросов: {e}")
        return jsonify({'message': 'Внутренняя ошибка сервера', 'code': 'server_error'}), 500
    finally:

@history_bp.route('/api/history/<int:message_id>', methods=['GET'])
@token_required
def get_message_details(message_id):
    """
    Возвращает детальную информацию о сообщении.
    """
    with db_session() as db:
    try:
        # Получаем сообщение из базы данных
        message = db.query(Message).filter_by(id=message_id).first()
        
        if not message:
            return jsonify({'message': 'Сообщение не найдено', 'code': 'message_not_found'}), 404
        
        # Получаем связанную сессию
        session = message.session
        
        # Получаем follow-up вопросы
        followups = []
        for followup in message.followups:
            followups.append({
                'id': followup.id,
                'question_text': followup.question_text,
                'was_clicked': followup.was_clicked,
                'generated_by': followup.generated_by,
                'timestamp': int(followup.timestamp.timestamp())
            })
        
        # Формируем ответ
        result = {
            'id': message.id,
            'user_id': message.user_id,
            'query': message.message_text,
            'response': message.bot_response,
            'timestamp': int(message.timestamp.timestamp()),
            'interface': session.interface_type,
            'language': message.language,
            'confidence_score': message.confidence_score,
            'followups': followups
        }
        
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Ошибка при получении деталей сообщения: {e}")
        return jsonify({'message': 'Внутренняя ошибка сервера', 'code': 'server_error'}), 500
    finally:
