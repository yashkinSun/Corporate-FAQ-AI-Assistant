import os
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context

# Добавляем корень проекта в PYTHONPATH, чтобы корректно импортировать модули
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from config import DATABASE_URL  # noqa: E402
from storage.database_unified import Base, engine  # noqa: E402

# Это объект конфигурации Alembic, предоставляющий доступ к значениям из файла конфигурации.
config = context.config

# Настраиваем URL базы данных из конфигурации приложения
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Интерпретируем раздел конфигурации для ведения логов.
if config.config_file_name is not None and os.path.exists(config.config_file_name):
    fileConfig(config.config_file_name)

# Метаданные для автогенерации миграций
# pylint: disable=invalid-name
# Alembic ожидает переменную target_metadata в модуле env.py
# Используем метаданные из базового класса ORM


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Запуск миграций в офлайн-режиме.

    В этом режиме Alembic генерирует SQL, не подключаясь к базе данных.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Запуск миграций в онлайн-режиме через существующий движок приложения."""
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
