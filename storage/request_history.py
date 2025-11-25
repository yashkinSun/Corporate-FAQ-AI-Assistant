# storage/request_history.py

import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("REQUEST_HISTORY_DB_PATH", "requests.db")

def init_db():
    """
    Создаёт таблицу, если её нет.
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS user_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            request_text TEXT,
            response_text TEXT,
            created_at DATETIME
        )
        """)
        conn.commit()

init_db()  # Гарантируем, что таблица создана

def save_user_interaction(user_id: int, request_text: str, response_text: str):
    """
    Сохраняет запрос и ответ в БД.
    Если записей > 5 для user_id, удаляем самую старую.
    """
    now = datetime.utcnow()
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        # Вставляем новую запись
        c.execute("""
            INSERT INTO user_requests(user_id, request_text, response_text, created_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, request_text, response_text, now))
        conn.commit()

        # Проверяем количество записей для user_id
        c.execute("SELECT COUNT(*) FROM user_requests WHERE user_id=?", (user_id,))
        count = c.fetchone()[0]
        if count > 5:
            # Удаляем самую старую
            c.execute("""
                DELETE FROM user_requests 
                WHERE id IN (
                    SELECT id FROM user_requests 
                    WHERE user_id=?
                    ORDER BY created_at ASC
                    LIMIT ?
                )
            """, (user_id, count - 5))
            conn.commit()

def save_operator_action(action: str, user_chat_id: str, detail: str = ""):
    """
    Логирование действий оператора (принял/отклонил/ответил).
    Можно хранить в отдельной таблице или писать в лог-файл.
    """
    logger.info(f"[OPERATOR ACTION] {action} for user {user_chat_id}, detail={detail}")
