import logging
import os
from typing import Dict, Any, Optional, Tuple

# Обновленные импорты для совместимости с новыми версиями LangChain
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from config import OPENAI_API_KEY, RERANKING_MODEL
from utils.response_validation import validate_response, sanitize_environment_variables, format_chat_messages

logger = logging.getLogger(__name__)

class OpenAIClient:
    """
    Клиент для взаимодействия с OpenAI API с улучшенной безопасностью.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
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
            temperature=0.7
        )
    
    def get_completion(self, system_prompt: str, user_message: str, user_id: int, 
                      language: str = 'ru') -> Tuple[str, float]:
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
            
            # Вычисляем уровень уверенности (заглушка, в реальности нужно использовать более сложную логику)
            # В будущем можно использовать logprobs или другие метрики от API
            confidence = 0.8  # Заглушка
            
            return response_text, confidence
            
        except Exception as e:
            logger.error(f"Error in OpenAI API call: {e}")
            
            # Возвращаем безопасный ответ в случае ошибки
            fallback_response = "Извините, произошла ошибка при обработке вашего запроса." if language == 'ru' else \
                               "Sorry, an error occurred while processing your request."
            
            return fallback_response, 0.0

def get_openai_client(model: str = RERANKING_MODEL):
    """
    Возвращает экземпляр клиента OpenAI.
    
    Args:
        model: Модель OpenAI для использования
        
    Returns:
        OpenAI: Клиент OpenAI
    """
    import openai
    from config import OPENAI_API_KEY
    
    # Инициализируем клиент OpenAI
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    return client
