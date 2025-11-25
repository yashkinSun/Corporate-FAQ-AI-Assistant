"""
Модуль для LLM-переранжирования результатов поиска.
Улучшает релевантность найденных документов с помощью GPT-4o.
"""
import logging
from typing import List, Dict, Any
from functools import lru_cache

from config import (
    RERANKING_ENABLED, 
    RERANKING_MODEL, 
    RERANKING_CACHE_SIZE, 
    RERANKING_MIN_SCORE,
    RERANKING_MAX_CHUNKS
)
from utils.openai_client import get_openai_client

logger = logging.getLogger(__name__)

# Создаем LRU-кэш для результатов переранжирования
@lru_cache(maxsize=RERANKING_CACHE_SIZE)
def get_cached_relevance_score(query: str, document: str) -> float:
    """
    Получает оценку релевантности документа для запроса из кэша.
    Если оценки нет в кэше, вычисляет ее с помощью LLM.
    
    Args:
        query: Запрос пользователя
        document: Текст документа
        
    Returns:
        float: Оценка релевантности (1-5)
    """
    return calculate_relevance_score(query, document)

def calculate_relevance_score(query: str, document: str) -> float:
    """
    Вычисляет оценку релевантности документа для запроса с помощью LLM.
    
    Args:
        query: Запрос пользователя
        document: Текст документа
        
    Returns:
        float: Оценка релевантности (1-5)
    """
    try:
        client = get_openai_client()
        
        prompt = f"""
        Оцените релевантность следующего фрагмента текста для заданного вопроса по шкале от 1 до 5, 
        где 1 - совершенно не релевантен, 5 - полностью релевантен.
        
        Вопрос: {query}
        
        Фрагмент текста:
        {document}
        
        Оценка (только число от 1 до 5):
        """
        
        response = client.chat.completions.create(
            model=RERANKING_MODEL,
            messages=[
                {"role": "system", "content": "Вы - система оценки релевантности текста. Ваша задача - оценить, насколько фрагмент текста отвечает на заданный вопрос. Отвечайте только числом от 1 до 5."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=10
        )
        
        # Извлекаем оценку из ответа
        score_text = response.choices[0].message.content.strip()
        
        # Пытаемся преобразовать в число
        try:
            score = float(score_text)
            # Ограничиваем значение от 1 до 5
            score = max(1.0, min(5.0, score))
            return score
        except ValueError:
            # Если не удалось преобразовать в число, возвращаем среднее значение
            logger.warning(f"Failed to parse relevance score from LLM response: {score_text}")
            return 3.0
    
    except Exception as e:
        logger.error(f"Error calculating relevance score: {e}")
        # В случае ошибки возвращаем среднее значение
        return 3.0

def rerank_documents(query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Переранжирует документы на основе их релевантности запросу.
    
    Args:
        query: Запрос пользователя
        documents: Список документов для переранжирования
        
    Returns:
        List[Dict[str, Any]]: Отсортированный список документов
    """
    if not RERANKING_ENABLED or not documents:
        return documents
    
    # Вычисляем оценки релевантности для каждого документа
    scored_docs = []
    for doc in documents:
        content = doc["content"]
        # Используем кэшированную функцию для получения оценки
        score = get_cached_relevance_score(query, content)
        
        # Добавляем оценку в документ
        doc_with_score = doc.copy()
        doc_with_score["relevance_score"] = score
        scored_docs.append(doc_with_score)
    
    # Сортируем документы по оценке релевантности (по убыванию)
    sorted_docs = sorted(scored_docs, key=lambda x: x["relevance_score"], reverse=True)
    
    # Фильтруем документы с оценкой ниже порогового значения
    filtered_docs = [doc for doc in sorted_docs if doc["relevance_score"] >= RERANKING_MIN_SCORE]
    
    # Ограничиваем количество документов
    result_docs = filtered_docs[:RERANKING_MAX_CHUNKS]
    
    # Логируем результаты переранжирования
    logger.debug(f"Reranked {len(documents)} documents to {len(result_docs)} with min score {RERANKING_MIN_SCORE}")
    
    return result_docs
