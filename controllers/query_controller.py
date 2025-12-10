import logging
import os
from typing import Dict, Any, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import CONFIDENCE_THRESHOLD, CHROMA_DB_PATH
from utils.openai_client import OpenAIClient
from storage.database_unified import save_message
from retrieval.retriever import retrieve_relevant_docs

logger = logging.getLogger(__name__)

# Инициализируем клиент OpenAI
openai_client = OpenAIClient()

def process_user_query(user_text: str, user_id: int, language: str = 'ru') -> Tuple[str, float]:
    """
    Обрабатывает запрос пользователя через RAG-пайплайн.
    
    Args:
        user_text: Текст запроса пользователя
        user_id: ID пользователя
        language: Язык пользователя ('ru' или 'en')
        
    Returns:
        Tuple[str, float]: (ответ, уровень уверенности)
    """
    try:
        # Получаем релевантные документы из базы знаний
        relevant_docs = retrieve_relevant_docs(user_text, top_k=3)
        logger.info(f"Retrieved {len(relevant_docs)} relevant documents for query: {user_text[:50]}...")
        
        # Формируем контекст из найденных документов
        context = ""
        if relevant_docs:
            context = "Информация из базы знаний:\n\n"
            for i, doc in enumerate(relevant_docs, 1):
                content = doc.get("content", "")
                metadata = doc.get("metadata", {})
                source = metadata.get("source", "неизвестный источник")
                context += f"Документ {i} (источник: {source}):\n{content}\n\n"
        
        # Системный промпт для модели
        system_prompt = f"""
        Ты корпоративный бот поддержки, который отвечает на вопросы клиентов.
        Отвечай кратко, но информативно, основываясь на предоставленной информации.
        Если не знаешь ответа, честно признайся в этом.
        Не выдумывай информацию и не ссылайся на то, что ты AI модель.
        
        {context}
        """
        
        if language == 'en':
            system_prompt = f"""
            You are a corporate support bot that answers customer questions.
            Answer briefly but informatively, based on the provided information.
            If you don't know the answer, honestly admit it.
            Don't make up information and don't refer to yourself as an AI model.
            
            Information from knowledge base:
            {context}
            """
        
        # Получаем ответ от модели
        response, confidence = openai_client.get_completion(
            system_prompt=system_prompt,
            user_message=user_text,
            user_id=user_id,
            language=language,
            retrieved_docs=relevant_docs
        )
        
        return response, confidence
        
    except Exception as e:
        logger.error(f"Error in process_user_query: {e}")
        
        # Возвращаем безопасный ответ в случае ошибки
        fallback_response = "Извините, произошла ошибка при обработке вашего запроса." if language == 'ru' else \
                           "Sorry, an error occurred while processing your request."
        
        return fallback_response, 0.0
