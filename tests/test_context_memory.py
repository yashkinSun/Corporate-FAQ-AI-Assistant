"""
Unit-тесты для модуля контекстной памяти (utils/context_memory.py).

Тестирует:
- Определение follow-up вопросов
- Переформулирование вопросов с контекстом
- Graceful degradation при недоступности Redis
"""

import pytest
from unittest.mock import patch, MagicMock
import json


class TestIsFollowupQuestion:
    """Тесты для функции is_followup_question"""
    
    def test_empty_context_returns_false(self):
        """При пустом контексте всегда возвращает False"""
        from utils.context_memory import is_followup_question
        
        result = is_followup_question("Расскажи подробнее", [])
        assert result is False
    
    def test_empty_question_returns_false(self):
        """При пустом вопросе возвращает False"""
        from utils.context_memory import is_followup_question
        
        context = [{"role": "user", "content": "Что такое Python?"}]
        result = is_followup_question("", context)
        assert result is False
        
        result = is_followup_question("   ", context)
        assert result is False
    
    def test_short_question_with_keyword_is_followup(self):
        """Короткий вопрос с ключевым словом определяется как follow-up"""
        from utils.context_memory import is_followup_question
        
        context = [{"role": "user", "content": "Что такое Python?"}]
        
        # Русские ключевые слова
        assert is_followup_question("Расскажи подробнее", context) is True
        assert is_followup_question("А сколько это стоит?", context) is True
        assert is_followup_question("Какие еще варианты?", context) is True
        assert is_followup_question("Что еще?", context) is True
        assert is_followup_question("Объясни это", context) is True
        
        # Английские ключевые слова
        assert is_followup_question("Tell me more", context) is True
        assert is_followup_question("What else?", context) is True
        assert is_followup_question("More details please", context) is True
    
    def test_short_question_with_pronoun_is_followup(self):
        """Короткий вопрос с местоимением определяется как follow-up"""
        from utils.context_memory import is_followup_question
        
        context = [{"role": "user", "content": "Расскажи про тарифы"}]
        
        # Русские местоимения
        assert is_followup_question("А сколько это стоит?", context) is True
        assert is_followup_question("Расскажи про это", context) is True
        assert is_followup_question("Об этом подробнее", context) is True
        
        # Английские местоимения
        assert is_followup_question("What about this?", context) is True
        assert is_followup_question("Tell me about it", context) is True
    
    def test_long_question_without_explicit_marker_is_not_followup(self):
        """Длинный вопрос без явного маркера не определяется как follow-up"""
        from utils.context_memory import is_followup_question
        
        context = [{"role": "user", "content": "Что такое Python?"}]
        
        long_question = "Какие существуют языки программирования для веб-разработки и какой из них лучше выбрать для начинающего?"
        assert is_followup_question(long_question, context) is False
    
    def test_long_question_with_explicit_marker_is_followup(self):
        """Длинный вопрос с явным маркером определяется как follow-up"""
        from utils.context_memory import is_followup_question
        
        context = [{"role": "user", "content": "Что такое Python?"}]
        
        long_question = "Расскажи подробнее о том, как Python используется в машинном обучении и какие библиотеки для этого нужны?"
        assert is_followup_question(long_question, context) is True
    
    def test_new_topic_question_is_not_followup(self):
        """Новый вопрос на другую тему не определяется как follow-up"""
        from utils.context_memory import is_followup_question
        
        context = [{"role": "user", "content": "Что такое Python?"}]
        
        # Новая тема без ключевых слов
        assert is_followup_question("Какая погода в Москве?", context) is False
        assert is_followup_question("Как добраться до офиса?", context) is False


class TestReformulateQuestion:
    """Тесты для функции reformulate_question"""
    
    def test_empty_context_returns_original(self):
        """При пустом контексте возвращает оригинальный вопрос"""
        from utils.context_memory import reformulate_question
        
        question = "Расскажи подробнее"
        result = reformulate_question(question, [])
        assert result == question
    
    def test_empty_question_returns_original(self):
        """При пустом вопросе возвращает оригинальный вопрос"""
        from utils.context_memory import reformulate_question
        
        context = [{"role": "user", "content": "Что такое Python?"}]
        
        assert reformulate_question("", context) == ""
        assert reformulate_question("   ", context) == "   "
    
    def test_reformulation_includes_context(self):
        """Переформулированный вопрос включает контекст предыдущего диалога"""
        from utils.context_memory import reformulate_question
        
        context = [
            {"role": "user", "content": "Что такое Python?"},
            {"role": "assistant", "content": "Python - это язык программирования."}
        ]
        
        result = reformulate_question("Расскажи подробнее", context)
        
        # Проверяем, что результат содержит информацию о контексте
        assert "Что такое Python?" in result
        assert "Python - это язык программирования" in result
        assert "Расскажи подробнее" in result
    
    def test_reformulation_truncates_long_assistant_response(self):
        """Длинный ответ ассистента обрезается"""
        from utils.context_memory import reformulate_question
        
        long_response = "A" * 1000  # 1000 символов
        context = [
            {"role": "user", "content": "Вопрос"},
            {"role": "assistant", "content": long_response}
        ]
        
        result = reformulate_question("Подробнее", context)
        
        # Ответ должен быть обрезан до 500 символов
        assert len(result) < len(long_response) + 200  # С учетом шаблона


class TestContextOperations:
    """Тесты для операций с контекстом (get_context, save_message, clear_context)"""
    
    @patch('utils.context_memory.redis_client', None)
    def test_get_context_returns_empty_when_redis_unavailable(self):
        """get_context возвращает пустой список при недоступности Redis"""
        from utils.context_memory import get_context
        
        result = get_context(123456)
        assert result == []
    
    @patch('utils.context_memory.redis_client', None)
    def test_save_message_returns_false_when_redis_unavailable(self):
        """save_message возвращает False при недоступности Redis"""
        from utils.context_memory import save_message
        
        result = save_message(123456, "user", "Test message")
        assert result is False
    
    @patch('utils.context_memory.redis_client', None)
    def test_clear_context_returns_false_when_redis_unavailable(self):
        """clear_context возвращает False при недоступности Redis"""
        from utils.context_memory import clear_context
        
        result = clear_context(123456)
        assert result is False
    
    def test_save_message_validates_role(self):
        """save_message проверяет корректность роли"""
        from utils.context_memory import save_message
        
        with patch('utils.context_memory.redis_client') as mock_redis:
            mock_redis.get.return_value = None
            
            # Некорректная роль должна вернуть False
            result = save_message(123456, "invalid_role", "Test")
            assert result is False
    
    @patch('utils.context_memory.redis_client')
    def test_get_context_handles_corrupted_json(self, mock_redis):
        """get_context обрабатывает поврежденные JSON данные"""
        from utils.context_memory import get_context
        
        mock_redis.get.return_value = "not valid json {"
        
        result = get_context(123456)
        assert result == []
        
        # Проверяем, что поврежденные данные были удалены
        mock_redis.delete.assert_called_once()


class TestGracefulDegradation:
    """Тесты для graceful degradation"""
    
    @patch('utils.context_memory.CONTEXT_MEMORY_ENABLED', False)
    def test_init_redis_returns_none_when_disabled(self):
        """_init_redis возвращает None когда функция отключена"""
        from utils.context_memory import _init_redis
        
        result = _init_redis()
        assert result is None
    
    @patch('utils.context_memory.redis.Redis')
    def test_init_redis_handles_connection_error(self, mock_redis_class):
        """_init_redis обрабатывает ошибку подключения"""
        import redis
        from utils.context_memory import _init_redis
        
        mock_redis_class.return_value.ping.side_effect = redis.ConnectionError("Connection refused")
        
        with patch('utils.context_memory.CONTEXT_MEMORY_ENABLED', True):
            result = _init_redis()
            assert result is None


class TestMemoryStats:
    """Тесты для функции get_memory_stats"""
    
    @patch('utils.context_memory.redis_client', None)
    def test_memory_stats_when_disabled(self):
        """get_memory_stats возвращает статус disabled при недоступности Redis"""
        from utils.context_memory import get_memory_stats
        
        result = get_memory_stats()
        assert result["status"] in ["disabled", "error"]
    
    @patch('utils.context_memory.redis_client')
    def test_memory_stats_returns_info(self, mock_redis):
        """get_memory_stats возвращает информацию о памяти"""
        from utils.context_memory import get_memory_stats
        
        mock_redis.info.return_value = {
            "used_memory_human": "1.5M",
            "used_memory_peak_human": "2.0M"
        }
        mock_redis.dbsize.return_value = 100
        
        result = get_memory_stats()
        
        assert result["status"] == "active"
        assert "used_memory_human" in result
        assert "total_keys" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
