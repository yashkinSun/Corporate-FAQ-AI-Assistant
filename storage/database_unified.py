"""
Унифицированный модуль для работы с базой данных.
Объединяет функциональность для телеграм-бота и веб-интерфейса.
"""
import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session

from config import DATABASE_URL

logger = logging.getLogger(__name__)

# Создаем базовый класс для моделей
Base = declarative_base()

# Определяем модели
class UserSession(Base):
    __tablename__ = 'sessions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    start_time = Column(DateTime, nullable=False, default=datetime.now)
    end_time = Column(DateTime, nullable=True)
    language = Column(String(10), nullable=True)
    last_escalation_time = Column(DateTime, nullable=True)
    interface_type = Column(String(20), nullable=True, default='telegram')  # 'telegram' или 'web'
    
    # Отношения
    messages = relationship("Message", back_populates="session")
    ratings = relationship("Rating", back_populates="session")

class Message(Base):
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('sessions.id'), nullable=False)
    user_id = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)
    message_text = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=True)
    language = Column(String(10), nullable=True)
    
    # Отношения
    session = relationship("UserSession", back_populates="messages")
    followups = relationship("FollowupQuestion", back_populates="message")

class Rating(Base):
    __tablename__ = 'ratings'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('sessions.id'), nullable=False)
    rating = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)
    
    # Отношения
    session = relationship("UserSession", back_populates="ratings")
    feedback = relationship("Feedback", back_populates="rating", uselist=False)

class Feedback(Base):
    __tablename__ = 'feedback'
    
    id = Column(Integer, primary_key=True)
    rating_id = Column(Integer, ForeignKey('ratings.id'), nullable=False)
    feedback_text = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)
    
    # Отношения
    rating = relationship("Rating", back_populates="feedback")

class SuspiciousInput(Base):
    __tablename__ = 'suspicious_inputs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)
    input_text = Column(Text, nullable=False)
    detected_pattern = Column(String(255), nullable=False)
    action_taken = Column(String(255), nullable=False)

class FollowupQuestion(Base):
    __tablename__ = 'followup_questions'
    
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey('messages.id'), nullable=False)
    question_text = Column(Text, nullable=False)
    original_query = Column(Text, nullable=True)  # Исходный запрос пользователя
    confidence_score = Column(Float, nullable=True)  # Оценка уверенности
    generated_by = Column(String(20), nullable=False, default='map')  # 'llm' или 'map'
    was_clicked = Column(Boolean, nullable=False, default=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)
    
    # Отношения
    message = relationship("Message", back_populates="followups")

class WebUser(Base):
    __tablename__ = 'web_users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # 'admin', 'operator', 'viewer'
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    last_login = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

class Chat(Base):
    __tablename__ = 'chats'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    operator_id = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default='waiting')  # 'waiting', 'active', 'closed'
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

class Document(Base):
    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    path = Column(String(1024), nullable=False)
    description = Column(Text, nullable=True)
    uploaded_by = Column(Integer, ForeignKey('web_users.id'), nullable=False)
    uploaded_at = Column(DateTime, nullable=False, default=datetime.now)

# Создаем движок с правильной конфигурацией connection pooling
engine = create_engine(
    DATABASE_URL,
    # Connection pooling настройки
    pool_size=10,           # Базовый размер pool
    max_overflow=20,        # Дополнительные соединения
    pool_timeout=30,        # Timeout получения соединения (сек)
    pool_recycle=3600,      # Пересоздание соединений каждый час
    pool_pre_ping=True,     # Проверка соединения перед использованием
    
    # Настройки для PostgreSQL
    connect_args={
        "options": "-c timezone=utc",
        "application_name": "faqbot",
        "connect_timeout": 10,
    } if DATABASE_URL.startswith('postgresql') else {},
    
    # Логирование SQL (для отладки)
    echo=False,
    echo_pool=True if os.getenv("DEBUG") else False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def db_session():
    """Context manager для безопасной работы с БД"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def get_db():
    """Dependency injection для Flask - возвращает сессию с автоматическим закрытием"""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise

def init_db():
    """Инициализирует базу данных, создавая все таблицы"""
    Base.metadata.create_all(bind=engine)
    logger.info(f"Database initialized with SQLAlchemy at {DATABASE_URL}")

# Функции для работы с сессиями
def get_or_create_session(user_id: int, language: Optional[str] = None, 
                          interface_type: str = 'telegram') -> int:
    """
    Получает активную сессию пользователя или создает новую, возвращает id сессии
    
    Args:
        user_id: ID пользователя
        language: Язык пользователя
        interface_type: Тип интерфейса ('telegram' или 'web')
        
    Returns:
        int: ID сессии
    """
    with db_session() as db:
        # Проверяем, есть ли активная сессия
        session = db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.end_time.is_(None)
        ).first()
        
        if session:
            return session.id
        
        # Создаем новую сессию
        new_session = UserSession(
            user_id=user_id,
            start_time=datetime.now(),
            language=language,
            interface_type=interface_type
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        
        return new_session.id

def end_session(session_id: int):
    """
    Завершает сессию пользователя
    
    Args:
        session_id: ID сессии
    """
    with db_session() as db:
        session = db.query(UserSession).filter(UserSession.id == session_id).first()
        if session:
            session.end_time = datetime.now()
            logger.debug(f"Ended session {session_id}")

def update_session_language(session_id: int, language: str):
    """
    Обновляет язык сессии
    
    Args:
        session_id: ID сессии
        language: Язык
    """
    with db_session() as db:
        session = db.query(UserSession).filter(UserSession.id == session_id).first()
        if session:
            session.language = language
            logger.debug(f"Updated language for session {session_id} to {language}")

def update_last_escalation_time(session_id: int):
    """
    Обновляет время последней эскалации в сессии
    
    Args:
        session_id: ID сессии
    """
    with db_session() as db:
        session = db.query(UserSession).filter(UserSession.id == session_id).first()
        if session:
            session.last_escalation_time = datetime.now()
            logger.debug(f"Updated last escalation time for session {session_id}")

def can_escalate(user_id: int) -> bool:
    """
    Проверяет, может ли пользователь эскалировать запрос (прошло ли ESCALATION_COOLDOWN_MINUTES минут с последней эскалации)
    
    Args:
        user_id: ID пользователя
        
    Returns:
        bool: True, если пользователь может эскалировать запрос
    """
    from config import ESCALATION_COOLDOWN_MINUTES
    
    with db_session() as db:
        session = db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.end_time.is_(None)
        ).first()
        
        if not session or not session.last_escalation_time:
            return True
        
        last_time = session.last_escalation_time
        now = datetime.now()
        
        # Проверяем, прошло ли ESCALATION_COOLDOWN_MINUTES минут
        time_diff = (now - last_time).total_seconds() / 60
        
        return time_diff >= ESCALATION_COOLDOWN_MINUTES

# Функции для работы с сообщениями
def save_message(user_id: int, message_text: str, bot_response: str,
                confidence_score: Optional[float] = None, language: Optional[str] = None):
    """
    Сохраняет сообщение пользователя и ответ бота в базу данных
    
    Args:
        user_id: ID пользователя
        message_text: Текст сообщения пользователя
        bot_response: Ответ бота
        confidence_score: Оценка уверенности
        language: Язык
    """
    with db_session() as db:
        # Получаем или создаем сессию
        session_id = get_or_create_session(user_id, language)
        
        # Создаем новое сообщение
        new_message = Message(
            session_id=session_id,
            user_id=user_id,
            timestamp=datetime.now(),
            message_text=message_text,
            bot_response=bot_response,
            confidence_score=confidence_score,
            language=language
        )
        db.add(new_message)
        db.commit()
        db.refresh(new_message)
        
        logger.debug(f"Saved message from user {user_id}")
        return new_message.id


def get_recent_confidence_scores(user_id: int, limit: int = 5) -> List[float]:
    """
    Возвращает последние confidence_score пользователя из базы данных.

    Args:
        user_id: ID пользователя
        limit: Максимальное количество оценок

    Returns:
        List[float]: Список confidence_score в порядке от новых к старым
    """

    with db_session() as db:
        query = (
            db.query(Message.confidence_score)
            .filter(Message.user_id == user_id, Message.confidence_score.isnot(None))
            .order_by(Message.timestamp.desc())
            .limit(limit)
        )
        return [row[0] for row in query.all() if row[0] is not None]

# Функции для работы с оценками и обратной связью
def save_rating(session_id: int, rating: int) -> int:
    """
    Сохраняет оценку сессии, возвращает id оценки
    
    Args:
        session_id: ID сессии
        rating: Оценка (1-5)
        
    Returns:
        int: ID оценки
    """
    with db_session() as db:
        new_rating = Rating(
            session_id=session_id,
            rating=rating,
            timestamp=datetime.now()
        )
        db.add(new_rating)
        db.commit()
        db.refresh(new_rating)
        
        logger.debug(f"Saved rating {rating} for session {session_id}")
        
        return new_rating.id

def save_feedback(rating_id: int, feedback_text: str):
    """
    Сохраняет обратную связь для оценки
    
    Args:
        rating_id: ID оценки
        feedback_text: Текст обратной связи
    """
    with db_session() as db:
        new_feedback = Feedback(
            rating_id=rating_id,
            feedback_text=feedback_text,
            timestamp=datetime.now()
        )
        db.add(new_feedback)
        logger.debug(f"Saved feedback for rating {rating_id}")

# Функции для работы с подозрительными вводами
def log_suspicious_input(user_id: int, input_text: str, detected_pattern: str, action_taken: str):
    """
    Логирует подозрительный ввод пользователя
    
    Args:
        user_id: ID пользователя
        input_text: Текст ввода
        detected_pattern: Обнаруженный паттерн
        action_taken: Предпринятое действие
    """
    with db_session() as db:
        new_suspicious_input = SuspiciousInput(
            user_id=user_id,
            timestamp=datetime.now(),
            input_text=input_text,
            detected_pattern=detected_pattern,
            action_taken=action_taken
        )
        db.add(new_suspicious_input)
        logger.debug(f"Logged suspicious input from user {user_id}")

# Функции для работы с follow-up вопросами
def save_followup_question(message_id: int, question_text: str, 
                      original_query: str = None, confidence_score: float = None, 
                      generated_by: str = 'map'):
    """
    Сохраняет follow-up вопрос
    
    Args:
        message_id: ID сообщения
        question_text: Текст вопроса
        original_query: Исходный запрос пользователя
        confidence_score: Оценка уверенности
        generated_by: Источник генерации ('llm' или 'map')
    """
    with db_session() as db:
        new_followup = FollowupQuestion(
            message_id=message_id,
            question_text=question_text,
            original_query=original_query,
            confidence_score=confidence_score,
            generated_by=generated_by,
            timestamp=datetime.now()
        )
        db.add(new_followup)
        logger.debug(f"Saved followup question for message {message_id}")

def mark_followup_clicked(followup_id: int):
    """
    Отмечает follow-up вопрос как нажатый
    
    Args:
        followup_id: ID follow-up вопроса
    """
    with db_session() as db:
        followup = db.query(FollowupQuestion).filter(FollowupQuestion.id == followup_id).first()
        if followup:
            followup.was_clicked = True
            logger.debug(f"Marked followup {followup_id} as clicked")

# Функции для работы с пользователями веб-интерфейса
def create_web_user(username: str, password_hash: str, role: str = 'operator'):
    """
    Создает нового пользователя веб-интерфейса
    
    Args:
        username: Имя пользователя
        password_hash: Хеш пароля
        role: Роль пользователя ('admin', 'operator', 'viewer')
    """
    with db_session() as db:
        new_user = WebUser(
            username=username,
            password_hash=password_hash,
            role=role,
            created_at=datetime.now()
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        logger.debug(f"Created web user {username} with role {role}")
        return new_user.id

def get_web_user_by_username(username: str):
    """
    Получает пользователя веб-интерфейса по имени пользователя
    
    Args:
        username: Имя пользователя
        
    Returns:
        WebUser: Пользователь веб-интерфейса или None
    """
    with db_session() as db:
        return db.query(WebUser).filter(WebUser.username == username).first()

def update_last_login(user_id: int):
    """
    Обновляет время последнего входа пользователя
    
    Args:
        user_id: ID пользователя
    """
    with db_session() as db:
        user = db.query(WebUser).filter(WebUser.id == user_id).first()
        if user:
            user.last_login = datetime.now()
            logger.debug(f"Updated last login for user {user_id}")

# Функции для аналитики
def get_user_statistics(user_id: int) -> Dict[str, Any]:
    """
    Получает статистику использования бота пользователем
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Dict[str, Any]: Статистика пользователя
    """
    with db_session() as db:
        # Количество сообщений
        message_count = db.query(func.count(Message.id)).filter(Message.user_id == user_id).scalar() or 0
        
        # Количество сессий
        session_count = db.query(func.count(UserSession.id)).filter(UserSession.user_id == user_id).scalar() or 0
        
        # Средняя оценка (если есть)
        avg_rating = db.query(func.avg(Rating.rating)).join(
            UserSession, Rating.session_id == UserSession.id
        ).filter(UserSession.user_id == user_id).scalar()
        
        return {
            "message_count": message_count,
            "session_count": session_count,
            "average_rating": avg_rating
        }

def get_recent_messages(user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Получает последние сообщения пользователя для контекста
    
    Args:
        user_id: ID пользователя
        limit: Максимальное количество сообщений
        
    Returns:
        List[Dict[str, Any]]: Список сообщений
    """
    with db_session() as db:
        messages = db.query(Message).filter(
            Message.user_id == user_id
        ).order_by(Message.timestamp.desc()).limit(limit).all()
        
        result = []
        for msg in messages:
            result.append({
                "message_text": msg.message_text,
                "bot_response": msg.bot_response,
                "timestamp": msg.timestamp.isoformat(),
                "confidence_score": msg.confidence_score
            })
        
        return result

def get_user_language(user_id: int) -> Optional[str]:
    """
    Получает предпочтительный язык пользователя из активной сессии
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Optional[str]: Язык пользователя или None
    """
    with db_session() as db:
        session = db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.end_time.is_(None)
        ).first()
        
        return session.language if session else None

