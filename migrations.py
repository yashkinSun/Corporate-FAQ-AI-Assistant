# Alembic - инструмент для миграций базы данных

from alembic.config import Config
from alembic import command
import os
import sys
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_alembic():
    """
    Инициализирует Alembic для проекта.
    """
    try:
        # Создаем директорию для миграций, если она не существует
        if not os.path.exists('migrations'):
            os.makedirs('migrations')
            logger.info("Created migrations directory")
        
        # Создаем конфигурацию Alembic
        alembic_cfg = Config()
        alembic_cfg.set_main_option('script_location', 'migrations')
        alembic_cfg.set_main_option('sqlalchemy.url', 'driver://user:pass@localhost/dbname')
        
        # Инициализируем Alembic
        command.init(alembic_cfg, 'migrations')
        logger.info("Initialized Alembic in migrations directory")
        
        return True
    except Exception as e:
        logger.error(f"Error initializing Alembic: {e}")
        return False

def create_migration(message):
    """
    Создает новую миграцию.
    
    Args:
        message: Сообщение для миграции
    """
    try:
        # Создаем конфигурацию Alembic
        alembic_cfg = Config()
        alembic_cfg.set_main_option('script_location', 'migrations')
        
        # Создаем миграцию
        command.revision(alembic_cfg, message=message, autogenerate=True)
        logger.info(f"Created migration with message: {message}")
        
        return True
    except Exception as e:
        logger.error(f"Error creating migration: {e}")
        return False

def run_migrations():
    """
    Запускает все миграции.
    """
    try:
        # Создаем конфигурацию Alembic
        alembic_cfg = Config()
        alembic_cfg.set_main_option('script_location', 'migrations')
        
        # Запускаем миграции
        command.upgrade(alembic_cfg, 'head')
        logger.info("Ran all migrations")
        
        return True
    except Exception as e:
        logger.error(f"Error running migrations: {e}")
        return False

if __name__ == '__main__':
    # Парсим аргументы командной строки
    if len(sys.argv) < 2:
        print("Usage: python migrations.py [init|create|run] [message]")
        sys.exit(1)
    
    command_arg = sys.argv[1]
    
    if command_arg == 'init':
        init_alembic()
    elif command_arg == 'create':
        if len(sys.argv) < 3:
            print("Usage: python migrations.py create <message>")
            sys.exit(1)
        create_migration(sys.argv[2])
    elif command_arg == 'run':
        run_migrations()
    else:
        print(f"Unknown command: {command_arg}")
        print("Usage: python migrations.py [init|create|run] [message]")
        sys.exit(1)
