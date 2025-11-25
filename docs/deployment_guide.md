# Инструкция по развертыванию и переносу телеграм-бота поддержки клиентов

## Введение

Данная инструкция предоставляет пошаговое руководство по развертыванию и переносу телеграм-бота поддержки клиентов с интегрированным искусственным интеллектом. Система поддерживает различные сценарии развертывания: от простых локальных установок для разработки до масштабируемых продакшн кластеров с высокой доступностью.

Архитектура системы позволяет гибко настраивать компоненты в зависимости от требований инфраструктуры. Система может работать как единое приложение в одном контейнере, так и в виде распределенной архитектуры с отдельными сервисами для телеграм-бота, веб-интерфейса и обработки данных.

Инструкция охватывает все аспекты развертывания: подготовку инфраструктуры, настройку зависимостей, конфигурацию безопасности, миграцию данных и мониторинг производительности. Особое внимание уделено процедурам резервного копирования и восстановления для обеспечения непрерывности бизнес-процессов.

## Системные требования

### Минимальные требования для разработки

Для локальной разработки и тестирования системы требуются следующие ресурсы:

**Операционная система:** Ubuntu 20.04 LTS или новее, CentOS 8+, macOS 11+, Windows 10 с WSL2. Система протестирована на Linux дистрибутивах и полностью совместима с контейнеризованными средами.

**Процессор:** 1 CPU ядро с частотой 2.0 GHz или выше. Система эффективно работает на одном ядре при небольшой нагрузке (3-5 пользователей), потребляя около 40% ресурсов процессора.

**Оперативная память:** Минимум 1 GB RAM для базовой функциональности. Система показывает стабильную работу с потреблением менее 1 GB при обработке запросов небольшого количества пользователей. Рекомендуется 2 GB для комфортной работы с векторной базой данных ChromaDB.

**Дисковое пространство:** 5 GB свободного места для установки зависимостей, базы данных и документов. Дополнительное пространство требуется для логов, резервных копий и растущей базы знаний.

**Сетевое подключение:** Стабильное интернет-соединение для взаимодействия с Telegram Bot API и OpenAI API. Система требует исходящих HTTPS соединений на порты 443 для внешних API.

### Рекомендуемые требования для продакшн

Продакшн развертывание масштабируется в зависимости от нагрузки:

**Малая нагрузка (до 50 пользователей):**
- Процессор: 1-2 CPU ядра с частотой 2.5 GHz
- Оперативная память: 2 GB RAM
- Дисковое пространство: 20 GB SSD

**Средняя нагрузка (50-200 пользователей):**
- Процессор: 2-4 CPU ядра с частотой 3.0 GHz
- Оперативная память: 4-8 GB RAM  
- Дисковое пространство: 50 GB SSD

**Высокая нагрузка (200+ пользователей):**
- Процессор: 4+ CPU ядра с частотой 3.0 GHz или выше
- Оперативная память: 8+ GB RAM
- Дисковое пространство: 100 GB+ SSD хранилище

**Сетевая инфраструктура:** Высокоскоростное подключение с низкой задержкой для внешних API. Load balancer для распределения нагрузки между экземплярами приложения при масштабировании.

**База данных:** PostgreSQL 13+ с настроенным connection pooling. Для высоких нагрузок рекомендуется кластер с репликацией.

### Внешние зависимости и сервисы

Система требует доступа к следующим внешним сервисам:

**Telegram Bot API:** Стабильное подключение к api.telegram.org для получения и отправки сообщений. Система использует webhook режим для real-time обработки сообщений и поддерживает fallback на polling при проблемах с webhook.

**OpenAI API:** Доступ к api.openai.com для генерации ответов и переранжирования документов. Система поддерживает различные модели GPT и может быть настроена на использование Azure OpenAI Service для enterprise развертываний.

**Redis (опционально):** Для распределенного кэширования и rate limiting в кластерных конфигурациях. Система может работать без Redis в single-instance развертываниях, используя in-memory кэширование.

**SMTP сервер (опционально):** Для отправки уведомлений администраторам о критических событиях и еженедельных отчетов о производительности системы.

## Подготовка к развертыванию

### Получение необходимых токенов и ключей

Перед началом развертывания необходимо получить доступы к внешним сервисам:

**Создание Telegram бота:**

Откройте диалог с @BotFather в Telegram и выполните следующие команды для создания нового бота. Отправьте команду `/newbot` и следуйте инструкциям для выбора имени и username бота. BotFather предоставит токен в формате `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`, который необходимо сохранить для конфигурации системы.

Настройте webhook URL для бота через команду `/setwebhook` или оставьте эту настройку для автоматической конфигурации при запуске системы. Система автоматически регистрирует webhook при первом запуске, если переменная `WEBHOOK_URL` настроена корректно.

Получите Telegram ID администраторов через @userinfobot или другие специализированные боты. Эти ID необходимы для настройки списка `ADMIN_IDS` в конфигурации системы. Администраторы получают уведомления о запросах эскалации и имеют доступ к административным функциям.

**Получение OpenAI API ключа:**

Зарегистрируйтесь на platform.openai.com и создайте новый API ключ в разделе API Keys. Система поддерживает как pay-as-you-go, так и prepaid планы OpenAI. Рекомендуется настроить usage limits для контроля расходов на API вызовы.

Для enterprise развертываний рассмотрите использование Azure OpenAI Service, который предоставляет те же модели с дополнительными гарантиями SLA и соответствием корпоративным требованиям безопасности. Система поддерживает Azure OpenAI через настройку переменной `OPENAI_API_BASE`.

Настройте rate limits и usage monitoring в OpenAI dashboard для предотвращения неожиданных расходов. Система включает встроенные механизмы rate limiting, но дополнительные ограничения на уровне API provider обеспечивают дополнительную защиту.

**Настройка JWT секрета:**

Сгенерируйте криптографически стойкий секретный ключ для подписи JWT токенов. Используйте команду `openssl rand -hex 32` для генерации 256-битного ключа. Этот ключ критически важен для безопасности веб-интерфейса и должен храниться в безопасном месте.

В продакшн средах рекомендуется использовать системы управления секретами, такие как HashiCorp Vault, AWS Secrets Manager или Azure Key Vault для безопасного хранения и ротации секретных ключей.

### Подготовка инфраструктуры

**Настройка сервера или облачной инфраструктуры:**

Для облачного развертывания рекомендуются следующие конфигурации:

AWS: EC2 инстансы t3.large или больше с EBS GP3 хранилищем. Используйте Application Load Balancer для распределения нагрузки и Auto Scaling Groups для автоматического масштабирования. RDS PostgreSQL для базы данных и ElastiCache Redis для кэширования.

Google Cloud: Compute Engine инстансы n2-standard-4 или больше с SSD persistent disks. Cloud SQL для PostgreSQL и Memorystore для Redis. Cloud Load Balancing для распределения трафика.

Azure: Virtual Machines Standard_D4s_v3 или больше с Premium SSD дисками. Azure Database for PostgreSQL и Azure Cache for Redis. Application Gateway для load balancing.

**Настройка сетевой безопасности:**

Настройте security groups или firewall правила для ограничения доступа к системе. Откройте только необходимые порты: 80/443 для веб-трафика, 22 для SSH доступа (только с доверенных IP), и внутренние порты для межсервисного взаимодействия.

Используйте VPC или виртуальные сети для изоляции компонентов системы. Разместите базу данных и Redis в приватных подсетях без прямого доступа из интернета. Настройте NAT Gateway для исходящих соединений к внешним API.

Реализуйте network ACLs и security groups по принципу least privilege, разрешая только минимально необходимый трафик между компонентами системы.

**Настройка мониторинга и логирования:**

Настройте централизованное логирование через ELK Stack (Elasticsearch, Logstash, Kibana) или аналогичные решения. Система генерирует структурированные JSON логи, совместимые с большинством log aggregation платформ.

Настройте мониторинг производительности через Prometheus и Grafana или облачные решения мониторинга (CloudWatch, Stackdriver, Azure Monitor). Система экспортирует метрики производительности через стандартные endpoints.

Настройте алертинг для критических событий: недоступность внешних API, превышение error rate, исчерпание дисковой памяти, высокая нагрузка на CPU или память.

## Развертывание с использованием Docker

### Простое развертывание (все компоненты в одном контейнере)

Самый простой способ развертывания системы использует Docker Compose для запуска всех компонентов в едином окружении:

**Клонирование репозитория и подготовка файлов:**

```bash
# Клонирование репозитория
git clone <repository_url> telegram-support-bot
cd telegram-support-bot

# Создание директорий для данных
mkdir -p data/documents data/chroma_db logs

# Установка правильных прав доступа
chmod 755 data logs
chmod 777 data/documents data/chroma_db
```

**Создание файла переменных окружения:**

Создайте файл `.env` в корневой директории проекта с следующим содержимым:

```bash
# Основные настройки
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here
JWT_SECRET_KEY=your_generated_jwt_secret_here

# Список администраторов (Telegram ID через запятую)
ADMIN_IDS=123456789,987654321

# Настройки базы данных
DATABASE_PATH=data/bot_database.db
CHROMA_DB_PATH=data/chroma_db/

# Настройки AI
OPENAI_MODEL=gpt-3.5-turbo
RERANKING_MODEL=gpt-4o
CONFIDENCE_THRESHOLD=0.7

# Настройки веб-интерфейса
WEB_PORT=5000
JWT_ACCESS_TOKEN_EXPIRES=21600

# Режим запуска (all, telegram, web)
RUN_MODE=all

# Настройки логирования
LOG_LEVEL=INFO
```

**Запуск системы через Docker Compose:**

```bash
# Сборка и запуск контейнеров
docker-compose up -d

# Проверка статуса контейнеров
docker-compose ps

# Просмотр логов
docker-compose logs -f

# Остановка системы
docker-compose down
```

Система автоматически создаст необходимые таблицы в базе данных при первом запуске. Веб-интерфейс будет доступен по адресу `http://localhost:5000`, а телеграм-бот начнет обрабатывать сообщения автоматически.

**Проверка работоспособности:**

После запуска проверьте доступность компонентов:

```bash
# Проверка веб-интерфейса
curl http://localhost:5000/health

# Проверка логов телеграм-бота
docker-compose logs telegram-bot

# Проверка подключения к базе данных
docker-compose exec app python -c "from storage.database import ensure_db_exists; ensure_db_exists(); print('Database OK')"
```

### Масштабируемое развертывание (отдельные сервисы)

Для продакшн развертывания рекомендуется разделение компонентов на отдельные сервисы:

**Создание Docker Compose файла для продакшн:**

Создайте файл `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: telegram_bot
      POSTGRES_USER: bot_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - bot_network
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    networks:
      - bot_network
    restart: unless-stopped

  telegram-bot:
    build: .
    environment:
      - RUN_MODE=telegram
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=telegram_bot
      - DB_USER=bot_user
      - DB_PASSWORD=${DB_PASSWORD}
      - REDIS_HOST=redis
      - REDIS_PASSWORD=${REDIS_PASSWORD}
    volumes:
      - ./data/documents:/app/data/documents
      - ./data/chroma_db:/app/data/chroma_db
      - ./logs:/app/logs
    depends_on:
      - postgres
      - redis
    networks:
      - bot_network
    restart: unless-stopped

  web-interface:
    build: .
    environment:
      - RUN_MODE=web
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=telegram_bot
      - DB_USER=bot_user
      - DB_PASSWORD=${DB_PASSWORD}
      - REDIS_HOST=redis
      - REDIS_PASSWORD=${REDIS_PASSWORD}
    volumes:
      - ./data/documents:/app/data/documents
      - ./data/chroma_db:/app/data/chroma_db
    ports:
      - "5000:5000"
    depends_on:
      - postgres
      - redis
    networks:
      - bot_network
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - web-interface
    networks:
      - bot_network
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:

networks:
  bot_network:
    driver: bridge
```

**Настройка Nginx для reverse proxy:**

Создайте файл `nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream web_backend {
        server web-interface:5000;
    }

    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;

        location / {
            proxy_pass http://web_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /health {
            access_log off;
            return 200 "healthy\n";
        }
    }
}
```

**Запуск продакшн конфигурации:**

```bash
# Создание продакшн .env файла
cp .env .env.prod

# Редактирование продакшн настроек
nano .env.prod

# Запуск продакшн конфигурации
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# Проверка статуса всех сервисов
docker-compose -f docker-compose.prod.yml ps
```

## Ручное развертывание без Docker

### Установка зависимостей

Для развертывания без Docker необходимо установить все зависимости вручную:

**Установка Python и системных пакетов:**

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev
sudo apt install postgresql postgresql-contrib redis-server
sudo apt install build-essential libpq-dev

# CentOS/RHEL
sudo yum install python3.11 python3.11-devel
sudo yum install postgresql postgresql-server postgresql-contrib redis
sudo yum install gcc postgresql-devel

# Создание виртуального окружения
python3.11 -m venv venv
source venv/bin/activate

# Обновление pip
pip install --upgrade pip setuptools wheel
```

**Установка Python зависимостей:**

```bash
# Установка основных зависимостей
pip install -r requirements.txt

# Проверка установки критических пакетов
python -c "import telegram, openai, chromadb, flask, sqlalchemy; print('All packages installed successfully')"
```

**Настройка PostgreSQL:**

```bash
# Инициализация базы данных (CentOS/RHEL)
sudo postgresql-setup initdb

# Запуск и включение автозапуска
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Создание пользователя и базы данных
sudo -u postgres psql
CREATE USER bot_user WITH PASSWORD 'secure_password';
CREATE DATABASE telegram_bot OWNER bot_user;
GRANT ALL PRIVILEGES ON DATABASE telegram_bot TO bot_user;

-- Настройка connection limits для стабильности
ALTER USER bot_user CONNECTION LIMIT 50;

-- Оптимизация настроек для connection pooling
ALTER SYSTEM SET max_connections = 100;
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;

\q

# Перезапуск PostgreSQL для применения настроек
sudo systemctl restart postgresql
```

**Важно:** После исправления критических проблем система использует унифицированный модуль `database_unified.py` для всех операций с базой данных. Убедитесь, что все компоненты используют одну и ту же систему доступа к данным.

**Настройка Redis:**

```bash
# Запуск и включение автозапуска
sudo systemctl start redis
sudo systemctl enable redis

# Настройка пароля Redis
sudo nano /etc/redis/redis.conf
# Раскомментируйте и установите: requirepass your_redis_password

# Перезапуск Redis
sudo systemctl restart redis
```

### Конфигурация системы

**Создание конфигурационного файла:**

Создайте файл `config.local.py` с локальными настройками:

```python
import os

# Основные настройки
TELEGRAM_BOT_TOKEN = "your_telegram_bot_token"
OPENAI_API_KEY = "your_openai_api_key"
JWT_SECRET_KEY = "your_jwt_secret_key"

# Администраторы
ADMIN_IDS = [123456789, 987654321]

# База данных PostgreSQL
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "telegram_bot"
DB_USER = "bot_user"
DB_PASSWORD = "secure_password"

# Redis
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASSWORD = "your_redis_password"

# Пути к данным
DOCUMENTS_PATH = "/opt/telegram-bot/data/documents"
CHROMA_DB_PATH = "/opt/telegram-bot/data/chroma_db"
LOGS_PATH = "/opt/telegram-bot/logs"

# AI настройки
OPENAI_MODEL = "gpt-3.5-turbo"
RERANKING_MODEL = "gpt-4o"
CONFIDENCE_THRESHOLD = 0.7
```

**Создание директорий и установка прав:**

```bash
# Создание директорий
sudo mkdir -p /opt/telegram-bot/data/documents
sudo mkdir -p /opt/telegram-bot/data/chroma_db
sudo mkdir -p /opt/telegram-bot/logs

# Установка прав доступа
sudo chown -R $USER:$USER /opt/telegram-bot
chmod 755 /opt/telegram-bot/data
chmod 777 /opt/telegram-bot/data/documents
chmod 777 /opt/telegram-bot/data/chroma_db
chmod 755 /opt/telegram-bot/logs
```

**Инициализация базы данных:**

```bash
# Активация виртуального окружения
source venv/bin/activate

# Инициализация схемы базы данных через унифицированный модуль
python -c "
import sys
sys.path.append('.')
from storage.database_unified import ensure_db_exists
ensure_db_exists()
print('Database initialized successfully with unified module')
"

# Проверка состояния connection pool
python -c "
import sys
sys.path.append('.')
from utils.db_monitor import get_connection_stats
stats = get_connection_stats()
print(f'Connection pool initialized: {stats}')
"
```

### Создание systemd сервисов

**Создание сервиса для телеграм-бота:**

Создайте файл `/etc/systemd/system/telegram-bot.service`:

```ini
[Unit]
Description=Telegram Support Bot
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=simple
User=telegram-bot
Group=telegram-bot
WorkingDirectory=/opt/telegram-bot
Environment=PYTHONPATH=/opt/telegram-bot
Environment=RUN_MODE=telegram
EnvironmentFile=/opt/telegram-bot/.env
ExecStart=/opt/telegram-bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Создание сервиса для веб-интерфейса:**

Создайте файл `/etc/systemd/system/telegram-bot-web.service`:

```ini
[Unit]
Description=Telegram Bot Web Interface
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=simple
User=telegram-bot
Group=telegram-bot
WorkingDirectory=/opt/telegram-bot
Environment=PYTHONPATH=/opt/telegram-bot
Environment=RUN_MODE=web
EnvironmentFile=/opt/telegram-bot/.env
ExecStart=/opt/telegram-bot/venv/bin/python webapp_main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Создание пользователя и запуск сервисов:**

```bash
# Создание системного пользователя
sudo useradd -r -s /bin/false telegram-bot
sudo chown -R telegram-bot:telegram-bot /opt/telegram-bot

# Перезагрузка systemd и запуск сервисов
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot telegram-bot-web
sudo systemctl start telegram-bot telegram-bot-web

# Проверка статуса сервисов
sudo systemctl status telegram-bot
sudo systemctl status telegram-bot-web
```

## Настройка веб-сервера и SSL

### Настройка Nginx

**Установка и базовая настройка:**

```bash
# Установка Nginx
sudo apt install nginx  # Ubuntu/Debian
sudo yum install nginx  # CentOS/RHEL

# Создание конфигурации сайта
sudo nano /etc/nginx/sites-available/telegram-bot
```

**Конфигурация Nginx для телеграм-бота:**

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    # SSL настройки
    ssl_certificate /etc/ssl/certs/your-domain.crt;
    ssl_certificate_key /etc/ssl/private/your-domain.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # Безопасность заголовков
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";

    # Основная локация
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Таймауты
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Статические файлы
    location /static/ {
        alias /opt/telegram-bot/webapp/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Health check
    location /health {
        access_log off;
        proxy_pass http://127.0.0.1:5000/health;
    }

    # Ограничение размера загружаемых файлов
    client_max_body_size 10M;
}
```

**Активация конфигурации:**

```bash
# Создание символической ссылки
sudo ln -s /etc/nginx/sites-available/telegram-bot /etc/nginx/sites-enabled/

# Проверка конфигурации
sudo nginx -t

# Перезапуск Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### Получение SSL сертификата

**Использование Let's Encrypt (Certbot):**

```bash
# Установка Certbot
sudo apt install certbot python3-certbot-nginx  # Ubuntu/Debian
sudo yum install certbot python3-certbot-nginx  # CentOS/RHEL

# Получение сертификата
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Настройка автоматического обновления
sudo crontab -e
# Добавьте строку:
0 12 * * * /usr/bin/certbot renew --quiet
```

**Проверка SSL конфигурации:**

```bash
# Проверка сертификата
openssl s_client -connect your-domain.com:443 -servername your-domain.com

# Проверка через онлайн инструменты
# https://www.ssllabs.com/ssltest/
```

## Миграция данных и перенос системы

### Резервное копирование данных

**Создание скрипта резервного копирования:**

Создайте файл `backup.sh`:

```bash
#!/bin/bash

# Настройки
BACKUP_DIR="/opt/backups/telegram-bot"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="telegram_bot_backup_$DATE"

# Создание директории для резервных копий
mkdir -p $BACKUP_DIR

# Резервное копирование PostgreSQL
pg_dump -h localhost -U bot_user -d telegram_bot > $BACKUP_DIR/${BACKUP_NAME}_database.sql

# Резервное копирование ChromaDB
tar -czf $BACKUP_DIR/${BACKUP_NAME}_chromadb.tar.gz -C /opt/telegram-bot/data chroma_db/

# Резервное копирование документов
tar -czf $BACKUP_DIR/${BACKUP_NAME}_documents.tar.gz -C /opt/telegram-bot/data documents/

# Резервное копирование конфигурации
cp /opt/telegram-bot/.env $BACKUP_DIR/${BACKUP_NAME}_config.env

# Создание архива всех резервных копий
tar -czf $BACKUP_DIR/${BACKUP_NAME}_complete.tar.gz -C $BACKUP_DIR ${BACKUP_NAME}_*

# Удаление старых резервных копий (старше 30 дней)
find $BACKUP_DIR -name "telegram_bot_backup_*" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR/${BACKUP_NAME}_complete.tar.gz"
```

**Автоматизация резервного копирования:**

```bash
# Установка прав выполнения
chmod +x backup.sh

# Добавление в crontab для ежедневного выполнения
sudo crontab -e
# Добавьте строку для выполнения в 2:00 каждую ночь:
0 2 * * * /opt/telegram-bot/backup.sh
```

### Восстановление из резервной копии

**Скрипт восстановления:**

Создайте файл `restore.sh`:

```bash
#!/bin/bash

if [ $# -eq 0 ]; then
    echo "Usage: $0 <backup_file.tar.gz>"
    exit 1
fi

BACKUP_FILE=$1
RESTORE_DIR="/tmp/telegram_bot_restore"

# Создание временной директории
mkdir -p $RESTORE_DIR
cd $RESTORE_DIR

# Извлечение резервной копии
tar -xzf $BACKUP_FILE

# Остановка сервисов
sudo systemctl stop telegram-bot telegram-bot-web

# Восстановление базы данных
echo "Restoring database..."
dropdb -h localhost -U bot_user telegram_bot
createdb -h localhost -U bot_user telegram_bot
psql -h localhost -U bot_user -d telegram_bot < *_database.sql

# Восстановление ChromaDB
echo "Restoring ChromaDB..."
rm -rf /opt/telegram-bot/data/chroma_db
tar -xzf *_chromadb.tar.gz -C /opt/telegram-bot/data/

# Восстановление документов
echo "Restoring documents..."
rm -rf /opt/telegram-bot/data/documents
tar -xzf *_documents.tar.gz -C /opt/telegram-bot/data/

# Восстановление конфигурации (опционально)
echo "Configuration backup available: *_config.env"
echo "Please review and apply manually if needed"

# Установка прав доступа
sudo chown -R telegram-bot:telegram-bot /opt/telegram-bot/data

# Запуск сервисов
sudo systemctl start telegram-bot telegram-bot-web

echo "Restore completed successfully"
```

### Перенос на новый сервер

**Подготовка нового сервера:**

```bash
# На новом сервере выполните полную установку согласно инструкции
# Затем остановите сервисы перед переносом данных
sudo systemctl stop telegram-bot telegram-bot-web
```

**Перенос данных:**

```bash
# На старом сервере создайте резервную копию
./backup.sh

# Скопируйте резервную копию на новый сервер
scp /opt/backups/telegram-bot/telegram_bot_backup_*_complete.tar.gz user@new-server:/tmp/

# На новом сервере восстановите данные
./restore.sh /tmp/telegram_bot_backup_*_complete.tar.gz
```

**Обновление DNS и webhook:**

```bash
# Обновите DNS записи для указания на новый сервер
# Обновите webhook URL в Telegram (если изменился)
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://new-domain.com/webhook"}'
```

## Мониторинг и обслуживание

### Настройка мониторинга

**Установка и настройка Prometheus:**

```bash
# Создание пользователя для Prometheus
sudo useradd --no-create-home --shell /bin/false prometheus

# Скачивание и установка Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.40.0/prometheus-2.40.0.linux-amd64.tar.gz
tar xvf prometheus-2.40.0.linux-amd64.tar.gz
sudo cp prometheus-2.40.0.linux-amd64/prometheus /usr/local/bin/
sudo cp prometheus-2.40.0.linux-amd64/promtool /usr/local/bin/

# Создание конфигурации
sudo mkdir /etc/prometheus
sudo nano /etc/prometheus/prometheus.yml
```

**Конфигурация Prometheus:**

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'telegram-bot'
    static_configs:
      - targets: ['localhost:5000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']

  - job_name: 'postgres-exporter'
    static_configs:
      - targets: ['localhost:9187']
```

**Установка Grafana для визуализации:**

```bash
# Добавление репозитория Grafana
sudo apt-get install -y software-properties-common
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -

# Установка Grafana
sudo apt-get update
sudo apt-get install grafana

# Запуск и включение автозапуска
sudo systemctl start grafana-server
sudo systemctl enable grafana-server
```

### Настройка логирования

**Конфигурация logrotate:**

Создайте файл `/etc/logrotate.d/telegram-bot`:

```
/opt/telegram-bot/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 telegram-bot telegram-bot
    postrotate
        systemctl reload telegram-bot telegram-bot-web
    endscript
}
```

**Настройка централизованного логирования:**

```bash
# Установка Filebeat для отправки логов в ELK Stack
curl -L -O https://artifacts.elastic.co/downloads/beats/filebeat/filebeat-8.5.0-amd64.deb
sudo dpkg -i filebeat-8.5.0-amd64.deb

# Конфигурация Filebeat
sudo nano /etc/filebeat/filebeat.yml
```

**Конфигурация Filebeat:**

```yaml
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /opt/telegram-bot/logs/*.log
  fields:
    service: telegram-bot
  fields_under_root: true

output.elasticsearch:
  hosts: ["your-elasticsearch-host:9200"]

setup.kibana:
  host: "your-kibana-host:5601"
```

### Процедуры обслуживания

**Еженедельные задачи обслуживания:**

Создайте файл `maintenance.sh`:

```bash
#!/bin/bash

echo "Starting weekly maintenance..."

# Очистка старых логов
find /opt/telegram-bot/logs -name "*.log.*" -mtime +7 -delete

# Оптимизация базы данных
psql -h localhost -U bot_user -d telegram_bot -c "VACUUM ANALYZE;"

# Очистка кэша Redis
redis-cli -a $REDIS_PASSWORD FLUSHDB

# Проверка дискового пространства
df -h | grep -E "(/$|/opt)" | awk '{print $5 " " $6}' | while read output;
do
  usage=$(echo $output | awk '{print $1}' | sed 's/%//g')
  partition=$(echo $output | awk '{print $2}')
  if [ $usage -ge 80 ]; then
    echo "Warning: Partition $partition is ${usage}% full"
  fi
done

# Проверка статуса сервисов
systemctl is-active --quiet telegram-bot || echo "telegram-bot service is not running"
systemctl is-active --quiet telegram-bot-web || echo "telegram-bot-web service is not running"

echo "Weekly maintenance completed"
```

**Мониторинг производительности:**

```bash
# Создание скрипта мониторинга
cat > /opt/telegram-bot/monitor.sh << 'EOF'
#!/bin/bash

# Проверка использования CPU
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}')
if (( $(echo "$CPU_USAGE > 80" | bc -l) )); then
    echo "High CPU usage: $CPU_USAGE%"
fi

# Проверка использования памяти
MEM_USAGE=$(free | grep Mem | awk '{printf("%.2f", $3/$2 * 100.0)}')
if (( $(echo "$MEM_USAGE > 80" | bc -l) )); then
    echo "High memory usage: $MEM_USAGE%"
fi

# Проверка подключения к внешним API
curl -s --max-time 10 https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe > /dev/null
if [ $? -ne 0 ]; then
    echo "Telegram API is not accessible"
fi

curl -s --max-time 10 -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models > /dev/null
if [ $? -ne 0 ]; then
    echo "OpenAI API is not accessible"
fi
EOF

chmod +x /opt/telegram-bot/monitor.sh

# Добавление в crontab для выполнения каждые 5 минут
echo "*/5 * * * * /opt/telegram-bot/monitor.sh" | crontab -
```

## Устранение неполадок

### Диагностика проблем

**Проверка логов системы:**

```bash
# Просмотр логов телеграм-бота
sudo journalctl -u telegram-bot -f

# Просмотр логов веб-интерфейса
sudo journalctl -u telegram-bot-web -f

# Просмотр логов приложения
tail -f /opt/telegram-bot/logs/app.log

# Поиск ошибок в логах
grep -i error /opt/telegram-bot/logs/*.log
```

**Проверка подключений к базам данных:**

```bash
# Проверка PostgreSQL
psql -h localhost -U bot_user -d telegram_bot -c "SELECT version();"

# Проверка Redis
redis-cli -a $REDIS_PASSWORD ping

# Проверка ChromaDB
python -c "
import chromadb
client = chromadb.PersistentClient(path='/opt/telegram-bot/data/chroma_db')
print('ChromaDB collections:', client.list_collections())
"
```

**Проверка внешних API:**

```bash
# Проверка Telegram Bot API
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe"

# Проверка OpenAI API
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     "https://api.openai.com/v1/models"
```

### Решение типичных проблем

**Проблема: Бот не отвечает на сообщения**

Возможные причины и решения:

1. Проверьте статус сервиса телеграм-бота:
```bash
sudo systemctl status telegram-bot
```

2. Проверьте webhook настройки:
```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo"
```

3. Проверьте логи на ошибки:
```bash
sudo journalctl -u telegram-bot --since "1 hour ago"
```

**Проблема: Веб-интерфейс недоступен**

1. Проверьте статус веб-сервиса:
```bash
sudo systemctl status telegram-bot-web
sudo systemctl status nginx
```

2. Проверьте порты:
```bash
netstat -tlnp | grep :5000
netstat -tlnp | grep :80
```

3. Проверьте конфигурацию Nginx:
```bash
sudo nginx -t
```

**Проблема: Высокое использование ресурсов**

1. Проверьте процессы:
```bash
top -p $(pgrep -f "python.*main.py")
```

2. Проверьте использование памяти ChromaDB:
```bash
du -sh /opt/telegram-bot/data/chroma_db/
```

3. Оптимизируйте базу данных:
```bash
psql -h localhost -U bot_user -d telegram_bot -c "VACUUM FULL ANALYZE;"
```

### Процедуры восстановления

**Восстановление после сбоя сервиса:**

```bash
# Перезапуск всех сервисов
sudo systemctl restart telegram-bot telegram-bot-web nginx

# Проверка статуса
sudo systemctl status telegram-bot telegram-bot-web nginx

# Проверка логов на ошибки
sudo journalctl -u telegram-bot --since "5 minutes ago" | grep -i error
```

**Восстановление после сбоя базы данных:**

```bash
# Остановка сервисов
sudo systemctl stop telegram-bot telegram-bot-web

# Восстановление из последней резервной копии
./restore.sh /opt/backups/telegram-bot/telegram_bot_backup_latest_complete.tar.gz

# Запуск сервисов
sudo systemctl start telegram-bot telegram-bot-web
```

**Аварийное переключение на резервный сервер:**

```bash
# Обновление DNS записей для указания на резервный сервер
# Обновление webhook URL
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://backup-server.com/webhook"}'

# Синхронизация данных с основного сервера
rsync -avz user@main-server:/opt/telegram-bot/data/ /opt/telegram-bot/data/
```

Данная инструкция обеспечивает полное покрытие всех аспектов развертывания и обслуживания системы телеграм-бота поддержки клиентов. Следование этим процедурам гарантирует стабильную работу системы в различных средах развертывания.



## Мониторинг базы данных и стабильности

### Настройка мониторинга PostgreSQL

После исправления критических проблем с connection pooling система включает комплексную систему мониторинга состояния базы данных.

**Настройка мониторинга соединений:**

Система автоматически отслеживает состояние connection pool через модуль `utils/db_monitor.py`. Для настройки детального мониторинга добавьте следующие переменные в конфигурацию:

```bash
# Настройки мониторинга в .env файле
DB_MONITOR_ENABLED=true
DB_MONITOR_LOG_LEVEL=INFO
DB_MONITOR_ALERT_THRESHOLD=80
DB_MONITOR_CHECK_INTERVAL=60
```

**Конфигурация PostgreSQL для мониторинга:**

Обновите настройки PostgreSQL для улучшенного мониторинга:

```sql
-- Включение расширенной статистики
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET pg_stat_statements.track = 'all';
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_duration = on;
ALTER SYSTEM SET log_min_duration_statement = 1000;

-- Перезапуск PostgreSQL для применения настроек
-- sudo systemctl restart postgresql
```

**Настройка connection pooling:**

Система использует исправленную конфигурацию SQLAlchemy engine с оптимальными настройками:

```python
# Рекомендуемые настройки для продакшн
engine = create_engine(
    DATABASE_URL,
    pool_size=10,           # Базовый размер пула
    max_overflow=20,        # Дополнительные соединения
    pool_timeout=30,        # Таймаут получения соединения
    pool_recycle=3600,      # Пересоздание соединений каждый час
    pool_pre_ping=True,     # Проверка соединений перед использованием
    echo=False              # Отключить SQL логирование в продакшн
)
```

### Health Check endpoints

Система предоставляет специализированные endpoints для мониторинга состояния:

**Основные health check endpoints:**

```bash
# Общий статус системы
curl http://localhost:5000/health

# Статус базы данных
curl http://localhost:5000/health/db

# Детальная статистика connection pool
curl http://localhost:5000/health/db/connections

# Kubernetes readiness probe
curl http://localhost:5000/health/ready

# Kubernetes liveness probe
curl http://localhost:5000/health/live
```

**Интеграция с мониторингом:**

Добавьте health checks в Prometheus конфигурацию:

```yaml
# Добавление в prometheus.yml
scrape_configs:
  - job_name: 'telegram-bot-health'
    static_configs:
      - targets: ['localhost:5000']
    metrics_path: '/health/metrics'
    scrape_interval: 30s
    
  - job_name: 'telegram-bot-db'
    static_configs:
      - targets: ['localhost:5000']
    metrics_path: '/health/db/metrics'
    scrape_interval: 60s
```

**Настройка алертов для критических метрик:**

Создайте файл `alerts.yml` для Prometheus:

```yaml
groups:
  - name: telegram-bot-alerts
    rules:
      - alert: DatabaseConnectionPoolExhausted
        expr: db_connection_pool_checked_out / db_connection_pool_size > 0.9
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Database connection pool nearly exhausted"
          description: "Connection pool usage is {{ $value }}%"

      - alert: DatabaseConnectionLeaks
        expr: increase(db_connection_pool_overflow[5m]) > 10
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Potential database connection leaks detected"
          description: "Overflow connections increased by {{ $value }} in 5 minutes"

      - alert: HealthCheckFailed
        expr: up{job="telegram-bot-health"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Telegram bot health check failed"
          description: "Health check endpoint is not responding"
```

### Автоматизированное восстановление

**Скрипт автоматического восстановления:**

Создайте файл `auto_recovery.sh`:

```bash
#!/bin/bash

LOG_FILE="/opt/telegram-bot/logs/auto_recovery.log"
HEALTH_ENDPOINT="http://localhost:5000/health/db"
MAX_RETRIES=3
RETRY_DELAY=30

log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> $LOG_FILE
}

check_database_health() {
    response=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_ENDPOINT)
    if [ "$response" = "200" ]; then
        return 0
    else
        return 1
    fi
}

restart_services() {
    log_message "Restarting telegram-bot services due to database issues"
    sudo systemctl restart telegram-bot telegram-bot-web
    sleep 10
}

# Основная логика восстановления
for i in $(seq 1 $MAX_RETRIES); do
    if check_database_health; then
        log_message "Database health check passed"
        exit 0
    else
        log_message "Database health check failed (attempt $i/$MAX_RETRIES)"
        if [ $i -lt $MAX_RETRIES ]; then
            restart_services
            sleep $RETRY_DELAY
        fi
    fi
done

log_message "Auto recovery failed after $MAX_RETRIES attempts"
# Отправка уведомления администратору
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
     -H "Content-Type: application/json" \
     -d "{\"chat_id\": \"$ADMIN_CHAT_ID\", \"text\": \"🚨 Critical: Auto recovery failed for telegram-bot\"}"

exit 1
```

**Настройка cron для автоматических проверок:**

```bash
# Добавление в crontab
crontab -e

# Проверка каждые 5 минут
*/5 * * * * /opt/telegram-bot/auto_recovery.sh

# Еженедельная очистка логов восстановления
0 2 * * 0 find /opt/telegram-bot/logs -name "auto_recovery.log.*" -mtime +7 -delete
```

### Мониторинг производительности

**Настройка мониторинга медленных запросов:**

Создайте скрипт `monitor_slow_queries.sh`:

```bash
#!/bin/bash

SLOW_QUERY_LOG="/var/log/postgresql/postgresql.log"
ALERT_THRESHOLD=5000  # 5 секунд
ADMIN_CHAT_ID="your_admin_chat_id"

# Поиск медленных запросов за последние 5 минут
slow_queries=$(grep -E "duration: [0-9]{4,}" $SLOW_QUERY_LOG | \
               grep "$(date -d '5 minutes ago' '+%Y-%m-%d %H:%M')" | \
               wc -l)

if [ $slow_queries -gt 0 ]; then
    message="⚠️ Warning: $slow_queries slow database queries detected in the last 5 minutes"
    curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
         -H "Content-Type: application/json" \
         -d "{\"chat_id\": \"$ADMIN_CHAT_ID\", \"text\": \"$message\"}"
fi
```

**Мониторинг использования connection pool:**

Добавьте в cron ежечасную проверку:

```bash
# Скрипт проверки connection pool
cat > /opt/telegram-bot/check_connections.py << 'EOF'
#!/usr/bin/env python3

import requests
import json
import os
import sys

def check_connection_pool():
    try:
        response = requests.get('http://localhost:5000/health/db/connections')
        if response.status_code == 200:
            data = response.json()
            pool_stats = data.get('connection_pool', {})
            
            checked_out = pool_stats.get('checked_out', 0)
            size = pool_stats.get('size', 10)
            overflow = pool_stats.get('overflow', 0)
            
            usage_percent = (checked_out / size) * 100 if size > 0 else 0
            
            if usage_percent > 80:
                send_alert(f"High connection pool usage: {usage_percent:.1f}% ({checked_out}/{size})")
            
            if overflow > 5:
                send_alert(f"High connection overflow: {overflow} connections")
                
        else:
            send_alert(f"Health check endpoint returned status {response.status_code}")
            
    except Exception as e:
        send_alert(f"Connection pool check failed: {str(e)}")

def send_alert(message):
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    admin_chat_id = os.getenv('ADMIN_CHAT_ID')
    
    if bot_token and admin_chat_id:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": admin_chat_id,
            "text": f"🔍 Database Monitor: {message}"
        }
        requests.post(url, json=payload)

if __name__ == "__main__":
    check_connection_pool()
EOF

chmod +x /opt/telegram-bot/check_connections.py

# Добавление в crontab для ежечасной проверки
echo "0 * * * * /opt/telegram-bot/check_connections.py" | crontab -
```

### Диагностика проблем

**Скрипт диагностики системы:**

Создайте файл `diagnose.sh`:

```bash
#!/bin/bash

echo "=== Telegram Bot System Diagnostics ==="
echo "Timestamp: $(date)"
echo

echo "=== Service Status ==="
systemctl status telegram-bot --no-pager
systemctl status telegram-bot-web --no-pager
systemctl status postgresql --no-pager
systemctl status redis --no-pager
echo

echo "=== Database Connection Test ==="
python3 -c "
import sys
sys.path.append('/opt/telegram-bot')
try:
    from utils.db_monitor import get_connection_stats
    stats = get_connection_stats()
    print(f'Connection Pool Stats: {stats}')
    print('Database connection: OK')
except Exception as e:
    print(f'Database connection: FAILED - {e}')
"
echo

echo "=== Health Check Status ==="
curl -s http://localhost:5000/health | python3 -m json.tool
echo

echo "=== Recent Error Logs ==="
tail -20 /opt/telegram-bot/logs/error.log
echo

echo "=== System Resources ==="
echo "CPU Usage:"
top -bn1 | grep "Cpu(s)"
echo "Memory Usage:"
free -h
echo "Disk Usage:"
df -h /opt/telegram-bot
echo

echo "=== PostgreSQL Activity ==="
sudo -u postgres psql -d telegram_bot -c "
SELECT count(*) as active_connections, state 
FROM pg_stat_activity 
WHERE datname = 'telegram_bot' 
GROUP BY state;
"
```

Этот раздел обеспечивает комплексный мониторинг системы после исправления критических проблем с PostgreSQL и позволяет предотвратить повторные падения базы данных через проактивное отслеживание состояния connection pool и автоматическое восстановление при обнаружении проблем.

