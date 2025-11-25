"""
Маршруты для аналитики и экспорта данных в веб-интерфейсе.
"""
import logging
import json
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, send_file, Response
import io

from webapp.auth.jwt_auth import token_required, role_required
from storage.database_unified import db_session, UserSession, Message, Rating, Feedback
from sqlalchemy import func, and_

logger = logging.getLogger(__name__)

# Создаем blueprint
stats_bp = Blueprint('stats', __name__)

@stats_bp.route('/dashboard')
@token_required
@role_required(['admin', 'operator'])
def get_dashboard_stats():
    """
    Получение статистики для дашборда.
    """
    try:
        with db_session() as db:
            # Общее количество запросов
            total_requests = db.query(func.count(Message.id)).filter(Message.role == 'user').scalar() or 0

            # Запросы за сегодня
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_timestamp = int(today.timestamp())
            today_requests = db.query(func.count(Message.id)).filter(
                Message.role == 'user',
                Message.timestamp >= today_timestamp
            ).scalar() or 0

            # Уникальные пользователи
            unique_users = db.query(func.count(func.distinct(Message.user_id))).filter(
                Message.role == 'user'
            ).scalar() or 0

            # Среднее время ответа (в секундах)
            avg_response_time = 2.5  # Заглушка, в реальности нужно вычислять

            # Последние запросы
            recent_messages = db.query(Message).filter(
                Message.role == 'user'
            ).order_by(Message.timestamp.desc()).limit(10).all()

            recent_requests = []
            for msg in recent_messages:
                # Проверяем, есть ли ответ на этот запрос
                has_answer = db.query(Message).filter(
                    Message.chat_id == msg.chat_id,
                    Message.role == 'assistant',
                    Message.timestamp > msg.timestamp
                ).first() is not None

                recent_requests.append({
                    'id': msg.id,
                    'user_id': msg.user_id,
                    'text': msg.message_text[:50] + ('...' if len(msg.message_text) > 50 else ''),
                    'timestamp': msg.timestamp,
                    'status': 'answered' if has_answer else 'processing'
                })

            # Статистика по дням (за последние 7 дней)
            daily_stats = []
            for i in range(6, -1, -1):
                day = today - timedelta(days=i)
                day_end = day + timedelta(days=1)
                day_start_ts = int(day.timestamp())
                day_end_ts = int(day_end.timestamp())

                count = db.query(func.count(Message.id)).filter(
                    Message.role == 'user',
                    Message.timestamp >= day_start_ts,
                    Message.timestamp < day_end_ts
                ).scalar() or 0

                daily_stats.append({
                    'date': day.strftime('%d.%m'),
                    'count': count
                })

            # Популярные темы (заглушка)
            topics = [
                {'name': 'Доставка', 'count': 35},
                {'name': 'Оплата', 'count': 25},
                {'name': 'Возврат', 'count': 18},
                {'name': 'Наличие', 'count': 15},
                {'name': 'Другое', 'count': 7}
            ]

            return jsonify({
                'total_requests': total_requests,
                'today_requests': today_requests,
                'unique_users': unique_users,
                'avg_response_time': avg_response_time,
                'recent_requests': recent_requests,
                'daily_stats': daily_stats,
                'topics': topics
            })
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        return jsonify({'error': 'Failed to get statistics'}), 500

@stats_bp.route('/dashboard', methods=['GET'])
@token_required
@role_required(['admin', 'operator', 'viewer'])
def get_dashboard():
    """
    Получение основных метрик для дашборда.
    """
    # Получаем параметры запроса
    days = request.args.get('days', default=7, type=int)
    
    # Вычисляем дату начала периода
    start_date = datetime.now() - timedelta(days=days)
    
    try:
        with db_session() as db:
            # Общее количество сессий за период
            total_sessions = db.query(func.count(UserSession.id)).filter(
                UserSession.start_time >= start_date
            ).scalar() or 0
            
            # Количество завершенных сессий
            completed_sessions = db.query(func.count(UserSession.id)).filter(
                UserSession.start_time >= start_date,
                UserSession.end_time.isnot(None)
            ).scalar() or 0
            
            # Количество эскалаций к оператору
            escalations = db.query(func.count(UserSession.id)).filter(
                UserSession.start_time >= start_date,
                UserSession.last_escalation_time.isnot(None)
            ).scalar() or 0
            
            # Процент эскалаций
            escalation_rate = (escalations / total_sessions * 100) if total_sessions > 0 else 0
            
            # Средняя оценка
            avg_rating = db.query(func.avg(Rating.rating)).join(
                UserSession, Rating.session_id == UserSession.id
            ).filter(
                UserSession.start_time >= start_date
            ).scalar() or 0
            
            # Средняя уверенность в ответах
            avg_confidence = db.query(func.avg(Message.confidence_score)).join(
                UserSession, Message.session_id == UserSession.id
            ).filter(
                UserSession.start_time >= start_date,
                Message.confidence_score.isnot(None)
            ).scalar() or 0
            
            # Количество сессий по типу интерфейса
            interface_counts = {}
            for interface_type, count in db.query(
                UserSession.interface_type, func.count(UserSession.id)
            ).filter(
                UserSession.start_time >= start_date
            ).group_by(UserSession.interface_type).all():
                interface_counts[interface_type or 'unknown'] = count
            
            # Формируем ответ
            return jsonify({
                'period': {
                    'days': days,
                    'start_date': start_date.isoformat(),
                    'end_date': datetime.now().isoformat()
                },
                'metrics': {
                    'total_sessions': total_sessions,
                    'completed_sessions': completed_sessions,
                    'escalations': escalations,
                    'escalation_rate': round(escalation_rate, 2),
                    'avg_rating': round(float(avg_rating), 2) if avg_rating else 0,
                    'avg_confidence': round(float(avg_confidence), 2) if avg_confidence else 0,
                    'interface_distribution': interface_counts
                }
            }), 200
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        return jsonify({'error': 'Failed to get dashboard statistics'}), 500

@stats_bp.route('/daily', methods=['GET'])
@token_required
@role_required(['admin', 'operator', 'viewer'])
def get_daily_stats():
    """
    Получение ежедневной статистики за указанный период.
    """
    # Получаем параметры запроса
    days = request.args.get('days', default=30, type=int)
    
    # Вычисляем дату начала периода
    start_date = datetime.now() - timedelta(days=days)
    
    with db_session() as db:
        try:
            # Получаем данные по дням
            daily_stats = []
            
            current_date = start_date.date()
            end_date = datetime.now().date()
            
            while current_date <= end_date:
                day_start = datetime.combine(current_date, datetime.min.time())
                day_end = datetime.combine(current_date, datetime.max.time())
                
                # Количество сессий за день
                sessions_count = db.query(func.count(UserSession.id)).filter(
                    UserSession.start_time >= day_start,
                    UserSession.start_time <= day_end
                ).scalar() or 0
                
                # Количество эскалаций за день
                escalations_count = db.query(func.count(UserSession.id)).filter(
                    UserSession.start_time >= day_start,
                    UserSession.start_time <= day_end,
                    UserSession.last_escalation_time.isnot(None)
                ).scalar() or 0
                
                # Средняя оценка за день
                avg_rating = db.query(func.avg(Rating.rating)).join(
                    UserSession, Rating.session_id == UserSession.id
                ).filter(
                    UserSession.start_time >= day_start,
                    UserSession.start_time <= day_end
                ).scalar()
                
                daily_stats.append({
                    'date': current_date.isoformat(),
                    'sessions': sessions_count,
                    'escalations': escalations_count,
                    'avg_rating': round(float(avg_rating), 2) if avg_rating else None
                })
                
                current_date += timedelta(days=1)
            
            return jsonify({
                'period': {
                    'days': days,
                    'start_date': start_date.isoformat(),
                    'end_date': datetime.now().isoformat()
                },
                'daily_stats': daily_stats
            }), 200
        finally:
            pass

@stats_bp.route('/export/json', methods=['GET'])
@token_required
@role_required(['admin', 'viewer'])
def export_json():
    """
    Экспорт диалогов в формате JSON.
    """
    # Получаем параметры запроса
    start_date_str = request.args.get('start_date', default=None)
    end_date_str = request.args.get('end_date', default=None)
    interface_type = request.args.get('interface_type', default=None)
    
    # Парсим даты
    try:
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str)
        else:
            start_date = datetime.now() - timedelta(days=7)
        
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str)
        else:
            end_date = datetime.now()
    except ValueError:
        return jsonify({'message': 'Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'}), 400
    
    with db_session() as db:
        try:
            # Экспортируем диалоги
            from storage.database_sqlalchemy import export_dialogs
            dialogs = export_dialogs(db, start_date, end_date, interface_type)
            
            # Формируем имя файла
            filename = f"dialogs_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}"
            if interface_type:
                filename += f"_{interface_type}"
            filename += ".json"
            
            # Создаем JSON-файл в памяти
            json_data = json.dumps(dialogs, indent=2, ensure_ascii=False)
            json_bytes = json_data.encode('utf-8')
            
            # Отправляем файл
            return Response(
                io.BytesIO(json_bytes),
                mimetype='application/json',
                headers={'Content-Disposition': f'attachment;filename={filename}'}
            )
        finally:
            pass

@stats_bp.route('/feedback', methods=['GET'])
@token_required
@role_required(['admin', 'operator', 'viewer'])
def get_feedback():
    """
    Получение обратной связи от пользователей.
    """
    # Получаем параметры запроса
    days = request.args.get('days', default=30, type=int)
    min_rating = request.args.get('min_rating', default=1, type=int)
    max_rating = request.args.get('max_rating', default=5, type=int)
    
    # Вычисляем дату начала периода
    start_date = datetime.now() - timedelta(days=days)
    
    with db_session() as db:
        try:
            # Получаем оценки с обратной связью
            feedback_query = db.query(
                Rating.id,
                Rating.rating,
                Rating.timestamp,
                Feedback.feedback_text,
                UserSession.user_id,
                UserSession.interface_type
            ).join(
                UserSession, Rating.session_id == UserSession.id
            ).join(
                Feedback, Rating.id == Feedback.rating_id
            ).filter(
                Rating.timestamp >= start_date,
                Rating.rating >= min_rating,
                Rating.rating <= max_rating
            ).order_by(Rating.timestamp.desc())
            
            feedback_list = []
            for rating_id, rating, timestamp, feedback_text, user_id, interface_type in feedback_query.all():
                feedback_list.append({
                    'rating_id': rating_id,
                    'rating': rating,
                    'timestamp': timestamp.isoformat(),
                    'feedback_text': feedback_text,
                    'user_id': user_id,
                    'interface_type': interface_type or 'unknown'
                })
            
            return jsonify({
                'period': {
                    'days': days,
                    'start_date': start_date.isoformat(),
                    'end_date': datetime.now().isoformat()
                },
                'filters': {
                    'min_rating': min_rating,
                    'max_rating': max_rating
                },
                'feedback': feedback_list,
                'count': len(feedback_list)
            }), 200
        finally:
            pass
