"""
Модуль для запуска основного приложения с учетом режима работы.
"""
import os
import logging
import argparse
from config import RUN_MODE

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def run_telegram_bot():
    """
    Запускает Telegram-бота.
    """
    from main import main as run_telegram
    logger.info("Starting Telegram bot...")
    run_telegram()

def run_web_interface():
    """
    Запускает веб-интерфейс.
    """
    from webapp_main import main as run_web
    logger.info("Starting web interface...")
    run_web()

def init_database():
    """
    Инициализирует базу данных.
    """
    from storage.database_unified import init_db
    logger.info("Initializing database...")
    init_db()

def main():
    """
    Основная функция для запуска приложения в зависимости от режима.
    """
    parser = argparse.ArgumentParser(description='FAQ Bot Runner')
    parser.add_argument('--mode', type=str, choices=['all', 'telegram', 'web'], 
                        default=RUN_MODE, help='Run mode (all, telegram, web)')
    args = parser.parse_args()
    
    mode = args.mode
    
    # Инициализируем базу данных
    init_database()
    
    # Запускаем компоненты в зависимости от режима
    if mode in ['all', 'telegram']:
        run_telegram_bot()
    
    if mode in ['all', 'web']:
        run_web_interface()

if __name__ == '__main__':
    main()
