"""
Основной файл для запуска веб-интерфейса.
"""
import os
import logging
from webapp.app import create_app
from config import WEB_HOST, WEB_PORT, WEB_DEBUG, RUN_MODE

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """
    Основная функция для запуска веб-интерфейса.
    """
    # Проверяем режим запуска
    if RUN_MODE not in ['all', 'web']:
        logger.info(f"Web interface not started: RUN_MODE={RUN_MODE}")
        return
    
    # Создаем приложение
    app = create_app()
    
    # Запускаем приложение
    logger.info(f"Starting web interface on {WEB_HOST}:{WEB_PORT}")
    app.run(host=WEB_HOST, port=WEB_PORT, debug=WEB_DEBUG)

if __name__ == '__main__':
    main()
