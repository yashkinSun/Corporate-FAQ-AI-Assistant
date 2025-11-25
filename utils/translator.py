# utils/translator.py

import logging
from googletrans import Translator

logger = logging.getLogger(__name__)

translator = Translator()

def translate_text(text: str, dest_language: str = "en") -> str:
    """
    Переводит text на указанный язык (en|ru).
    """
    if not text.strip():
        return text
    try:
        result = translator.translate(text, dest=dest_language)
        return result.text
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return text  # Возвращаем оригинал, если не вышло

def detect_language(text: str) -> str:
    """
    Определяет язык текста (возвращает код 'en', 'ru' и т.д.).
    """
    try:
        detection = translator.detect(text)
        return detection.lang
    except:
        return "unknown"
