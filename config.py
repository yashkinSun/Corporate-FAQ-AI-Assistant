"""
Конфигурационный файл для корпоративного FAQ бота.
Содержит настройки и константы, используемые в различных модулях.
"""
import os
import warnings

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

# Загружаем переменные окружения из .env файла
load_dotenv()


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Базовые настройки
    TELEGRAM_BOT_TOKEN: str = Field(..., min_length=1, description="Токен Telegram-бота")
    OPENAI_API_KEY: str = Field(..., min_length=1, description="API-ключ OpenAI")
    OPENAI_REQUEST_TIMEOUT: float = Field(
        default=30.0,
        gt=0,
        description="Таймаут запросов к OpenAI в секундах",
    )
    CHROMA_DB_PATH: str = Field(default="data/chroma_db")
    DOCUMENTS_PATH: str = Field(default="data/documents")
    FOLLOWUP_MAP_PATH: str = Field(default="data/followup_map.json")

    # Настройки для индексации
    INDEX_SCHEDULE_HOURS: int = Field(default=24, description="Периодичность обновления индекса в часах")

    # Настройки для PostgreSQL
    PG_USER: str = Field(..., min_length=1)
    PG_PASSWORD: str = Field(..., min_length=1)
    PG_HOST: str = Field(..., min_length=1)
    PG_PORT: int = Field(default=5432)
    PG_DB: str = Field(..., min_length=1)

    # Настройки для Redis (rate-limiting)
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)
    REDIS_PASSWORD: str = Field(default="")

    # Настройки для rate-limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    TELEGRAM_RATE_LIMIT_SECONDS: int = Field(default=5)
    TELEGRAM_RATE_LIMIT_MAX_VIOLATIONS: int = Field(default=3)
    TELEGRAM_RATE_LIMIT_BLOCK_SECONDS: int = Field(default=30)
    WEB_RATE_LIMIT_REQUESTS: int = Field(default=100)
    WEB_RATE_LIMIT_MINUTES: int = Field(default=1)

    # Настройки для JWT
    JWT_SECRET_KEY: str = Field(default="super-secret-key-change-in-production")
    JWT_ACCESS_TOKEN_EXPIRES: int = Field(default=21600)  # 6 часов в секундах

    # Настройки для CRM
    CRM_ENABLED: bool = Field(default=False)
    CRM_ENDPOINT: str = Field(default="")
    CRM_LOG_PATH: str = Field(default="logs/crm_events.log")

    # Настройки для follow-up
    FOLLOWUP_MODE: str = Field(default="map")  # 'map' или 'llm'
    FOLLOWUP_LLM_MODEL: str = Field(default="gpt-4o-mini")

    # Настройки для LLM reranking
    RERANKING_ENABLED: bool = Field(default=True)
    RERANKING_MODEL: str = Field(default="gpt-4o-mini")
    RERANKING_CACHE_SIZE: int = Field(default=1000)
    RERANKING_MIN_SCORE: float = Field(default=4.0)
    RERANKING_MAX_CHUNKS: int = Field(default=3)
    RERANKING_INITIAL_CHUNKS: int = Field(default=10)

    # Настройки для веб-интерфейса
    WEB_HOST: str = Field(default="0.0.0.0")
    WEB_PORT: int = Field(default=5000)
    WEB_DEBUG: bool = Field(default=False)

    # Настройки для операторов
    ADMIN_IDS: list[int] = Field(default_factory=lambda: [123456789])
    OPERATOR_ID: int = Field(default=123456789)
    ESCALATION_COOLDOWN_MINUTES: int = Field(default=15)

    # Настройки для сообщений
    MAX_MESSAGE_LENGTH: int = Field(default=4000)
    CONFIDENCE_THRESHOLD: float = Field(default=0.7)
    CONFIDENCE_BASELINE: float = Field(default=0.6)  # была удалена случайно

    # Поддерживаемые языки
    SUPPORTED_LANGUAGES: list[str] = Field(default_factory=lambda: ["ru", "en"])

    # Настройки для логирования
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FILE: str = Field(default="logs/bot.log")

    # Настройки для режима запуска
    RUN_MODE: str = Field(default="all")  # 'all', 'telegram', 'web'

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: str | list[int]):
        if isinstance(value, str):
            try:
                return [int(id.strip()) for id in value.split(",") if id.strip()]
            except ValueError as exc:  # pragma: no cover - runtime configuration guard
                raise ValueError("ADMIN_IDS должны содержать целые числа, разделённые запятыми") from exc
        return value

    @field_validator(
        "TELEGRAM_RATE_LIMIT_SECONDS",
        "TELEGRAM_RATE_LIMIT_MAX_VIOLATIONS",
        "TELEGRAM_RATE_LIMIT_BLOCK_SECONDS",
        "WEB_RATE_LIMIT_REQUESTS",
        "WEB_RATE_LIMIT_MINUTES",
        "INDEX_SCHEDULE_HOURS",
        "RERANKING_CACHE_SIZE",
        "RERANKING_MAX_CHUNKS",
        "RERANKING_INITIAL_CHUNKS",
        "MAX_MESSAGE_LENGTH",
        "ESCALATION_COOLDOWN_MINUTES",
        "WEB_PORT",
        "PG_PORT",
    )
    @classmethod
    def ensure_positive(cls, value: int, field):
        if value <= 0:
            raise ValueError(f"{field.alias} должно быть положительным числом")
        return value

    @field_validator("CONFIDENCE_THRESHOLD")
    @classmethod
    def confidence_range(cls, value: float):
        if not 0 <= value <= 1:
            raise ValueError("CONFIDENCE_THRESHOLD должен быть в диапазоне от 0 до 1")
        return value

    @field_validator("RERANKING_MIN_SCORE")
    @classmethod
    def reranking_score_range(cls, value: float):
        if not 0 <= value <= 10:
            raise ValueError("RERANKING_MIN_SCORE должен быть в диапазоне от 0 до 10")
        return value

    @model_validator(mode="after")
    def warn_on_insecure_defaults(self):
        if self.JWT_SECRET_KEY == "super-secret-key-change-in-production":
            warnings.warn(
                "JWT_SECRET_KEY использует значение по умолчанию. Замените его в продакшене",
                RuntimeWarning,
            )
        return self


def _collect_env() -> dict[str, str]:
    """Получить словарь заданных переменных окружения, игнорируя неопределённые."""

    candidates = [
        "TELEGRAM_BOT_TOKEN",
        "OPENAI_API_KEY",
        "OPENAI_REQUEST_TIMEOUT",
        "CHROMA_DB_PATH",
        "DOCUMENTS_PATH",
        "FOLLOWUP_MAP_PATH",
        "INDEX_SCHEDULE_HOURS",
        "PG_USER",
        "PG_PASSWORD",
        "PG_HOST",
        "PG_PORT",
        "PG_DB",
        "REDIS_HOST",
        "REDIS_PORT",
        "REDIS_DB",
        "REDIS_PASSWORD",
        "RATE_LIMIT_ENABLED",
        "TELEGRAM_RATE_LIMIT_SECONDS",
        "TELEGRAM_RATE_LIMIT_MAX_VIOLATIONS",
        "TELEGRAM_RATE_LIMIT_BLOCK_SECONDS",
        "WEB_RATE_LIMIT_REQUESTS",
        "WEB_RATE_LIMIT_MINUTES",
        "JWT_SECRET_KEY",
        "JWT_ACCESS_TOKEN_EXPIRES",
        "CRM_ENABLED",
        "CRM_ENDPOINT",
        "CRM_LOG_PATH",
        "FOLLOWUP_MODE",
        "FOLLOWUP_LLM_MODEL",
        "RERANKING_ENABLED",
        "RERANKING_MODEL",
        "RERANKING_CACHE_SIZE",
        "RERANKING_MIN_SCORE",
        "RERANKING_MAX_CHUNKS",
        "RERANKING_INITIAL_CHUNKS",
        "WEB_HOST",
        "WEB_PORT",
        "WEB_DEBUG",
        "ADMIN_IDS",
        "OPERATOR_ID",
        "ESCALATION_COOLDOWN_MINUTES",
        "MAX_MESSAGE_LENGTH",
        "CONFIDENCE_THRESHOLD",
        "SUPPORTED_LANGUAGES",
        "LOG_LEVEL",
        "LOG_FILE",
        "RUN_MODE",
    ]
    return {key: value for key in candidates if (value := os.getenv(key)) is not None}


try:
    SETTINGS = Settings(**_collect_env())
except ValidationError as exc:  # pragma: no cover - executed at startup
    raise RuntimeError(f"Configuration validation failed:\n{exc}") from exc

# Базовые настройки
TELEGRAM_BOT_TOKEN = SETTINGS.TELEGRAM_BOT_TOKEN
OPENAI_API_KEY = SETTINGS.OPENAI_API_KEY
OPENAI_REQUEST_TIMEOUT = SETTINGS.OPENAI_REQUEST_TIMEOUT
CHROMA_DB_PATH = SETTINGS.CHROMA_DB_PATH
DOCUMENTS_PATH = SETTINGS.DOCUMENTS_PATH
FOLLOWUP_MAP_PATH = SETTINGS.FOLLOWUP_MAP_PATH

# Настройки для индексации
INDEX_SCHEDULE_HOURS = SETTINGS.INDEX_SCHEDULE_HOURS  # Периодичность обновления индекса в часах

# Настройки для PostgreSQL
PG_USER = SETTINGS.PG_USER
PG_PASSWORD = SETTINGS.PG_PASSWORD
PG_HOST = SETTINGS.PG_HOST
PG_PORT = SETTINGS.PG_PORT
PG_DB = SETTINGS.PG_DB

# Формируем URL для PostgreSQL
DATABASE_URL = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"

# Настройки для Redis (rate-limiting)
REDIS_HOST = SETTINGS.REDIS_HOST
REDIS_PORT = SETTINGS.REDIS_PORT
REDIS_DB = SETTINGS.REDIS_DB
REDIS_PASSWORD = SETTINGS.REDIS_PASSWORD
if REDIS_PASSWORD:
    REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
else:
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# Настройки для rate-limiting
RATE_LIMIT_ENABLED = SETTINGS.RATE_LIMIT_ENABLED
TELEGRAM_RATE_LIMIT_SECONDS = SETTINGS.TELEGRAM_RATE_LIMIT_SECONDS
TELEGRAM_RATE_LIMIT_MAX_VIOLATIONS = SETTINGS.TELEGRAM_RATE_LIMIT_MAX_VIOLATIONS
TELEGRAM_RATE_LIMIT_BLOCK_SECONDS = SETTINGS.TELEGRAM_RATE_LIMIT_BLOCK_SECONDS
WEB_RATE_LIMIT_REQUESTS = SETTINGS.WEB_RATE_LIMIT_REQUESTS
WEB_RATE_LIMIT_MINUTES = SETTINGS.WEB_RATE_LIMIT_MINUTES

# Настройки для JWT
JWT_SECRET_KEY = SETTINGS.JWT_SECRET_KEY
JWT_ACCESS_TOKEN_EXPIRES = SETTINGS.JWT_ACCESS_TOKEN_EXPIRES  # 6 часов в секундах

# Настройки для CRM
CRM_ENABLED = SETTINGS.CRM_ENABLED
CRM_ENDPOINT = SETTINGS.CRM_ENDPOINT
CRM_LOG_PATH = SETTINGS.CRM_LOG_PATH

# Настройки для follow-up
FOLLOWUP_MODE = SETTINGS.FOLLOWUP_MODE  # 'map' или 'llm'
FOLLOWUP_LLM_MODEL = SETTINGS.FOLLOWUP_LLM_MODEL

# Настройки для LLM reranking
RERANKING_ENABLED = SETTINGS.RERANKING_ENABLED
RERANKING_MODEL = SETTINGS.RERANKING_MODEL
RERANKING_CACHE_SIZE = SETTINGS.RERANKING_CACHE_SIZE
RERANKING_MIN_SCORE = SETTINGS.RERANKING_MIN_SCORE
RERANKING_MAX_CHUNKS = SETTINGS.RERANKING_MAX_CHUNKS
RERANKING_INITIAL_CHUNKS = SETTINGS.RERANKING_INITIAL_CHUNKS

# Настройки для веб-интерфейса
WEB_HOST = SETTINGS.WEB_HOST
WEB_PORT = SETTINGS.WEB_PORT
WEB_DEBUG = SETTINGS.WEB_DEBUG

# Настройки для операторов
ADMIN_IDS = SETTINGS.ADMIN_IDS
OPERATOR_ID = SETTINGS.OPERATOR_ID
ESCALATION_COOLDOWN_MINUTES = SETTINGS.ESCALATION_COOLDOWN_MINUTES

# Настройки для сообщений
MAX_MESSAGE_LENGTH = SETTINGS.MAX_MESSAGE_LENGTH
CONFIDENCE_THRESHOLD = SETTINGS.CONFIDENCE_THRESHOLD
CONFIDENCE_BASELINE = SETTINGS.CONFIDENCE_BASELINE  # <-- вернули

# Поддерживаемые языки
SUPPORTED_LANGUAGES = SETTINGS.SUPPORTED_LANGUAGES

# Настройки для логирования
LOG_LEVEL = SETTINGS.LOG_LEVEL
LOG_FILE = SETTINGS.LOG_FILE

# Настройки для режима запуска
RUN_MODE = SETTINGS.RUN_MODE  # 'all', 'telegram', 'web'
