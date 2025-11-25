import sqlite3
import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from config import DATABASE_PATH

logger = logging.getLogger(__name__)

def ensure_db_exists():
    """Создает базу данных и необходимые таблицы, если они не существуют"""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Таблица сообщений
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        timestamp TIMESTAMP NOT NULL,
        message_text TEXT NOT NULL,
        bot_response TEXT NOT NULL,
        confidence_score REAL,
        language TEXT
    )
    ''')
    
    # Таблица сессий
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        start_time TIMESTAMP NOT NULL,
        end_time TIMESTAMP,
        language TEXT,
        last_escalation_time TIMESTAMP
    )
    ''')
    
    # Таблица оценок
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ratings (
        id INTEGER PRIMARY KEY,
        session_id INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        timestamp TIMESTAMP NOT NULL,
        FOREIGN KEY (session_id) REFERENCES sessions(id)
    )
    ''')
    
    # Таблица обратной связи
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY,
        rating_id INTEGER NOT NULL,
        feedback_text TEXT NOT NULL,
        timestamp TIMESTAMP NOT NULL,
        FOREIGN KEY (rating_id) REFERENCES ratings(id)
    )
    ''')
    
    # Таблица подозрительных вводов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS suspicious_inputs (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        timestamp TIMESTAMP NOT NULL,
        input_text TEXT NOT NULL,
        detected_pattern TEXT NOT NULL,
        action_taken TEXT NOT NULL
    )
    ''')
    
    conn.commit()
    conn.close()
    
    logger.info(f"Database initialized at {DATABASE_PATH}")

def get_connection():
    """Возвращает соединение с базой данных"""
    ensure_db_exists()
    return sqlite3.connect(DATABASE_PATH)

def save_message(user_id: int, message_text: str, bot_response: str, 
                confidence_score: Optional[float] = None, language: Optional[str] = None):
    """Сохраняет сообщение пользователя и ответ бота в базу данных"""
    conn = get_connection()
    cursor = conn.cursor()
    
    timestamp = datetime.now().isoformat()
    
    cursor.execute(
        "INSERT INTO messages (user_id, timestamp, message_text, bot_response, confidence_score, language) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, timestamp, message_text, bot_response, confidence_score, language)
    )
    
    conn.commit()
    conn.close()
    
    logger.debug(f"Saved message from user {user_id}")

def get_or_create_session(user_id: int, language: Optional[str] = None) -> int:
    """Получает активную сессию пользователя или создает новую, возвращает id сессии"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Проверяем, есть ли активная сессия
    cursor.execute(
        "SELECT id FROM sessions WHERE user_id = ? AND end_time IS NULL",
        (user_id,)
    )
    
    result = cursor.fetchone()
    
    if result:
        session_id = result[0]
    else:
        # Создаем новую сессию
        timestamp = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO sessions (user_id, start_time, language) VALUES (?, ?, ?)",
            (user_id, timestamp, language)
        )
        session_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    return session_id

def end_session(session_id: int):
    """Завершает сессию пользователя"""
    conn = get_connection()
    cursor = conn.cursor()
    
    timestamp = datetime.now().isoformat()
    
    cursor.execute(
        "UPDATE sessions SET end_time = ? WHERE id = ?",
        (timestamp, session_id)
    )
    
    conn.commit()
    conn.close()
    
    logger.debug(f"Ended session {session_id}")

def update_session_language(session_id: int, language: str):
    """Обновляет язык сессии"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE sessions SET language = ? WHERE id = ?",
        (language, session_id)
    )
    
    conn.commit()
    conn.close()
    
    logger.debug(f"Updated language for session {session_id} to {language}")

def update_last_escalation_time(session_id: int):
    """Обновляет время последней эскалации в сессии"""
    conn = get_connection()
    cursor = conn.cursor()
    
    timestamp = datetime.now().isoformat()
    
    cursor.execute(
        "UPDATE sessions SET last_escalation_time = ? WHERE id = ?",
        (timestamp, session_id)
    )
    
    conn.commit()
    conn.close()
    
    logger.debug(f"Updated last escalation time for session {session_id}")

def can_escalate(user_id: int) -> bool:
    """Проверяет, может ли пользователь эскалировать запрос (прошло ли 15 минут с последней эскалации)"""
    from config import ESCALATION_COOLDOWN_MINUTES
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT last_escalation_time FROM sessions WHERE user_id = ? AND end_time IS NULL",
        (user_id,)
    )
    
    result = cursor.fetchone()
    conn.close()
    
    if not result or not result[0]:
        return True
    
    last_time = datetime.fromisoformat(result[0])
    now = datetime.now()
    
    # Проверяем, прошло ли ESCALATION_COOLDOWN_MINUTES минут
    time_diff = (now - last_time).total_seconds() / 60
    
    return time_diff >= ESCALATION_COOLDOWN_MINUTES

def save_rating(session_id: int, rating: int) -> int:
    """Сохраняет оценку сессии, возвращает id оценки"""
    conn = get_connection()
    cursor = conn.cursor()
    
    timestamp = datetime.now().isoformat()
    
    cursor.execute(
        "INSERT INTO ratings (session_id, rating, timestamp) VALUES (?, ?, ?)",
        (session_id, rating, timestamp)
    )
    
    rating_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    logger.debug(f"Saved rating {rating} for session {session_id}")
    
    return rating_id

def save_feedback(rating_id: int, feedback_text: str):
    """Сохраняет обратную связь для оценки"""
    conn = get_connection()
    cursor = conn.cursor()
    
    timestamp = datetime.now().isoformat()
    
    cursor.execute(
        "INSERT INTO feedback (rating_id, feedback_text, timestamp) VALUES (?, ?, ?)",
        (rating_id, feedback_text, timestamp)
    )
    
    conn.commit()
    conn.close()
    
    logger.debug(f"Saved feedback for rating {rating_id}")

def log_suspicious_input(user_id: int, input_text: str, detected_pattern: str, action_taken: str):
    """Логирует подозрительный ввод пользователя"""
    conn = get_connection()
    cursor = conn.cursor()
    
    timestamp = datetime.now().isoformat()
    
    cursor.execute(
        "INSERT INTO suspicious_inputs (user_id, timestamp, input_text, detected_pattern, action_taken) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, timestamp, input_text, detected_pattern, action_taken)
    )
    
    conn.commit()
    conn.close()
    
    logger.debug(f"Logged suspicious input from user {user_id}")

def get_user_language(user_id: int) -> Optional[str]:
    """Получает предпочтительный язык пользователя из активной сессии"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT language FROM sessions WHERE user_id = ? AND end_time IS NULL",
        (user_id,)
    )
    
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else None

def get_recent_messages(user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """Получает последние сообщения пользователя для контекста"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT message_text, bot_response, timestamp FROM messages "
        "WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
        (user_id, limit)
    )
    
    results = cursor.fetchall()
    conn.close()
    
    messages = []
    for msg_text, bot_response, timestamp in results:
        messages.append({
            "message_text": msg_text,
            "bot_response": bot_response,
            "timestamp": timestamp
        })
    
    return messages

def get_user_statistics(user_id: int) -> Dict[str, Any]:
    """Получает статистику использования бота пользователем"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Количество сообщений
    cursor.execute("SELECT COUNT(*) FROM messages WHERE user_id = ?", (user_id,))
    message_count = cursor.fetchone()[0]
    
    # Количество сессий
    cursor.execute("SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user_id,))
    session_count = cursor.fetchone()[0]
    
    # Средняя оценка (если есть)
    cursor.execute(
        "SELECT AVG(r.rating) FROM ratings r "
        "JOIN sessions s ON r.session_id = s.id "
        "WHERE s.user_id = ?",
        (user_id,)
    )
    avg_rating = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "message_count": message_count,
        "session_count": session_count,
        "average_rating": avg_rating
    }
