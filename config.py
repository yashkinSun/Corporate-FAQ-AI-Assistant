"""
Конфигурационный файл для корпоративного FAQ бота.
Содержит настройки и константы, используемые в различных модулях.
"""
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Базовые настройки
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "data/chroma_db")
DOCUMENTS_PATH = os.getenv("DOCUMENTS_PATH", "data/documents")
FOLLOWUP_MAP_PATH = os.getenv("FOLLOWUP_MAP_PATH", "data/followup_map.json")

# Настройки для индексации
INDEX_SCHEDULE_HOURS = int(os.getenv("INDEX_SCHEDULE_HOURS", "24"))  # Периодичность обновления индекса в часах

# Настройки для PostgreSQL
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DB = os.getenv("PG_DB", "faqbot")

# Формируем URL для PostgreSQL
DATABASE_URL = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"

# Настройки для Redis (rate-limiting)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
if REDIS_PASSWORD:
    REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
else:
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# Настройки для rate-limiting
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "True").lower() in ["true", "1", "yes"]
TELEGRAM_RATE_LIMIT_SECONDS = int(os.getenv("TELEGRAM_RATE_LIMIT_SECONDS", "5"))
TELEGRAM_RATE_LIMIT_MAX_VIOLATIONS = int(os.getenv("TELEGRAM_RATE_LIMIT_MAX_VIOLATIONS", "3"))
TELEGRAM_RATE_LIMIT_BLOCK_SECONDS = int(os.getenv("TELEGRAM_RATE_LIMIT_BLOCK_SECONDS", "30"))
WEB_RATE_LIMIT_REQUESTS = int(os.getenv("WEB_RATE_LIMIT_REQUESTS", "100"))
WEB_RATE_LIMIT_MINUTES = int(os.getenv("WEB_RATE_LIMIT_MINUTES", "1"))

# Настройки для JWT
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-key-change-in-production")
JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", "21600"))  # 6 часов в секундах

# Настройки для CRM
CRM_ENABLED = os.getenv("CRM_ENABLED", "False").lower() in ["true", "1", "yes"]
CRM_ENDPOINT = os.getenv("CRM_ENDPOINT", "")
CRM_LOG_PATH = os.getenv("CRM_LOG_PATH", "logs/crm_events.log")

# Настройки для follow-up
FOLLOWUP_MODE = os.getenv("FOLLOWUP_MODE", "map")  # 'map' или 'llm'
FOLLOWUP_LLM_MODEL = os.getenv("FOLLOWUP_LLM_MODEL", "gpt-4o-mini")

# Настройки для LLM reranking
RERANKING_ENABLED = os.getenv("RERANKING_ENABLED", "True").lower() in ["true", "1", "yes"]
RERANKING_MODEL = os.getenv("RERANKING_MODEL", "gpt-4o-mini")
RERANKING_CACHE_SIZE = int(os.getenv("RERANKING_CACHE_SIZE", "1000"))
RERANKING_MIN_SCORE = float(os.getenv("RERANKING_MIN_SCORE", "4.0"))
RERANKING_MAX_CHUNKS = int(os.getenv("RERANKING_MAX_CHUNKS", "3"))
RERANKING_INITIAL_CHUNKS = int(os.getenv("RERANKING_INITIAL_CHUNKS", "10"))

# Настройки для веб-интерфейса
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "5000"))
WEB_DEBUG = os.getenv("WEB_DEBUG", "False").lower() in ["true", "1", "yes"]

# Настройки для операторов
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "123456789").split(",")]
OPERATOR_ID = int(os.getenv("OPERATOR_ID", "123456789"))
ESCALATION_COOLDOWN_MINUTES = int(os.getenv("ESCALATION_COOLDOWN_MINUTES", "15"))

# Настройки для сообщений
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "4000"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))

# Поддерживаемые языки
SUPPORTED_LANGUAGES = ['ru', 'en']

# Настройки для логирования
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/bot.log")

# Настройки для режима запуска
RUN_MODE = os.getenv("RUN_MODE", "all")  # 'all', 'telegram', 'web'
