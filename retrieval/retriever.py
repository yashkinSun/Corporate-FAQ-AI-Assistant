"""
Модуль для обновления retriever.py с поддержкой LLM-переранжирования.
"""
from typing import List, Dict

from retrieval.store import get_similar_docs, get_similar_faq
from retrieval.reranker import rerank_documents
from config import RERANKING_ENABLED, RERANKING_INITIAL_CHUNKS

def retrieve_relevant_docs(query: str, top_k: int = 3) -> List[Dict[str, str]]:
    """
    Получаем список наиболее релевантных чанков текста (основная база).
    Каждый элемент — словарь { "content": ..., "metadata": {...} }.
    
    Если включено переранжирование, сначала получаем больше документов,
    затем применяем LLM-переранжирование для улучшения релевантности.
    """
    if RERANKING_ENABLED:
        # Получаем больше документов для последующего переранжирования
        initial_docs = get_similar_docs(query, k=RERANKING_INITIAL_CHUNKS)
        
        # Применяем переранжирование
        docs = rerank_documents(query, initial_docs)
    else:
        # Используем стандартный поиск без переранжирования
        docs = get_similar_docs(query, k=top_k)
    
    return docs

def get_related_questions(query: str, top_k: int = 3) -> List[str]:
    """
    Ищет похожие вопросы в базе FAQ и возвращает список формулировок (строк).
    Возвращает пустой список, если подходящих вопросов нет.
    """
    faq_questions = get_similar_faq(query, k=top_k)
    return faq_questions
