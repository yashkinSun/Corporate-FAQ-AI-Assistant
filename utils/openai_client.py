import logging
import math
from typing import Dict, Any, Optional, Tuple, List

import httpx
import openai

# Обновленные импорты для совместимости с новыми версиями LangChain
from langchain_openai import ChatOpenAI

from config import OPENAI_API_KEY, RERANKING_MODEL, CONFIDENCE_BASELINE, OPENAI_REQUEST_TIMEOUT
from utils.response_validation import validate_response, sanitize_environment_variables, format_chat_messages

logger = logging.getLogger(__name__)

class OpenAIClient:
    """
    Клиент для взаимодействия с OpenAI API с улучшенной безопасностью.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-3.5-turbo",
        default_confidence: float = CONFIDENCE_BASELINE,
    ):
        """
        Инициализирует клиент OpenAI.
        
        Args:
            api_key: API ключ OpenAI (если не указан, берется из конфигурации)
            model: Модель OpenAI для использования
        """
        self.api_key = api_key or OPENAI_API_KEY
        self.model = model
        self.chat = ChatOpenAI(
            openai_api_key=self.api_key,
            model=self.model,
            temperature=0.7,
            timeout=OPENAI_REQUEST_TIMEOUT,
        )
        self.default_confidence = max(0.0, min(1.0, default_confidence))

    def get_completion(self, system_prompt: str, user_message: str, user_id: int,
                      language: str = 'ru', retrieved_docs: Optional[List[Dict[str, Any]]] = None) -> Tuple[str, float]:
        """
        Получает ответ от модели OpenAI с улучшенной безопасностью.
        
        Args:
            system_prompt: Системный промпт
            user_message: Сообщение пользователя
            user_id: ID пользователя для логирования
            language: Язык пользователя ('ru' или 'en')
            
        Returns:
            Tuple[str, float]: (ответ модели, уровень уверенности)
        """
        try:
            # Форматируем сообщения в правильном формате чата
            messages = format_chat_messages(system_prompt, user_message)
            
            # Получаем ответ от модели используя метод invoke вместо прямого вызова
            response = self.chat.invoke(messages)
            
            # Извлекаем текст ответа
            response_text = response.content
            
            # Проверяем ответ на наличие подозрительных паттернов
            response_text = validate_response(response_text, user_id, language)
            
            # Проверяем ответ на наличие потенциальных секретов
            response_text = sanitize_environment_variables(response_text, user_id)
            
            confidence = self._estimate_confidence(response, retrieved_docs)

            return response_text, confidence
            
        except (openai.APITimeoutError, httpx.TimeoutException) as exc:
            logger.error("OpenAI API call timed out: %s", exc)

            fallback_response = "Извините, произошла ошибка при обработке вашего запроса." if language == 'ru' else \
                               "Sorry, an error occurred while processing your request."

            return fallback_response, 0.0

        except Exception as e:
            logger.error(f"Error in OpenAI API call: {e}")
            
            # Возвращаем безопасный ответ в случае ошибки
            fallback_response = "Извините, произошла ошибка при обработке вашего запроса." if language == 'ru' else \
                               "Sorry, an error occurred while processing your request."

            return fallback_response, 0.0

    def _estimate_confidence(self, response: Any, retrieved_docs: Optional[List[Dict[str, Any]]]) -> float:
        """
        Оценивает уверенность ответа на основе метаданных модели и релевантности документов.

        Args:
            response: Ответ модели (LangChain message)
            retrieved_docs: Документы, использованные для формирования контекста

        Returns:
            float: Оценка уверенности в диапазоне [0, 1]
        """
        scores: List[float] = []

        logprob_score = self._score_from_logprobs(getattr(response, "response_metadata", {}))
        if logprob_score is not None:
            scores.append(logprob_score)

        relevance_score = self._score_from_documents(retrieved_docs)
        if relevance_score is not None:
            scores.append(relevance_score)

        if not scores:
            return self.default_confidence

        combined = sum(scores) / len(scores)
        return max(0.0, min(1.0, combined))

    def _score_from_logprobs(self, metadata: Dict[str, Any]) -> Optional[float]:
        """
        Преобразует логарифмы вероятностей токенов в оценку уверенности.
        """
        if not metadata:
            return None

        logprobs = metadata.get("logprobs")
        if not logprobs:
            return None

        token_logprobs: List[float] = []

        if isinstance(logprobs, dict):
            token_logprobs = [lp for lp in logprobs.get("token_logprobs", []) if lp is not None]
            # Формат logprobs в новых моделях может быть вложенным
            if not token_logprobs and isinstance(logprobs.get("content"), list):
                token_logprobs = [segment.get("logprob") for segment in logprobs["content"] if segment.get("logprob") is not None]
        elif isinstance(logprobs, list):
            token_logprobs = [lp for lp in logprobs if lp is not None]

        if not token_logprobs:
            return None

        avg_logprob = sum(token_logprobs) / len(token_logprobs)
        return 1 / (1 + math.exp(-avg_logprob))

    def _score_from_documents(self, retrieved_docs: Optional[List[Dict[str, Any]]]) -> Optional[float]:
        """
        Рассчитывает уверенность на основе оценок релевантности документов.
        """
        if not retrieved_docs:
            return None

        relevance_scores: List[float] = []
        for doc in retrieved_docs:
            score = doc.get("relevance_score")
            if score is None:
                score = doc.get("metadata", {}).get("relevance_score")
            if score is not None:
                relevance_scores.append(float(score))

        if not relevance_scores:
            return None

        normalized_scores = [max(0.0, min(1.0, s / 5.0)) for s in relevance_scores]
        return sum(normalized_scores) / len(normalized_scores)

def get_openai_client(model: str = RERANKING_MODEL):
    """
    Возвращает экземпляр клиента OpenAI.
    
    Args:
        model: Модель OpenAI для использования
        
    Returns:
        OpenAI: Клиент OpenAI
    """
    # Инициализируем клиент OpenAI
    client = openai.OpenAI(api_key=OPENAI_API_KEY, timeout=OPENAI_REQUEST_TIMEOUT)
    
    return client
