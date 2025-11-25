# bot/clarifications.py

def check_need_clarification(confidence: float) -> bool:
    """
    Простая логика: если confidence < 0.4, то предлагаем уточнение.
    """
    return False

def get_clarification_question(user_query: str) -> str:
    """
    Генерация уточняющего вопроса (упрощённая).
    Можно подключить модель или использовать эвристику.
    """
    return f"Вы имели в виду что-то конкретное по запросу '{user_query}'?"
