# Инструкция: Создание первого администратора для веб-интерфейса

## Обзор

Для загрузки документов в базу данных через веб-интерфейс необходимо создать первого пользователя с правами администратора.

## Структура таблицы web_users

```sql
CREATE TABLE web_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,  -- 'admin', 'operator', 'viewer'
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login TIMESTAMP NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);
```

## Способ 1: Через SQL запрос (Рекомендуемый)

### Шаг 1: Генерация хеша пароля (Пример)

Создайте файл `generate_hash.py`:

```python
#!/usr/bin/env python3
import bcrypt

def generate_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

if __name__ == "__main__":
    password = "arminda2025" 
    password_hash = generate_password_hash(password)
    print(f"Хеш пароля: {password_hash}")
```

Выполните:
```bash
pip3 install bcrypt
python3 generate_hash.py
```

**Результат для пароля "arminda2025":**
```
$2b$12$62RIcEMlytJlqCGX8xWKwubEI5QCkMS5AqWJ12UsSkUbCaei7lHMe
```

### Шаг 2: SQL запрос для создания администратора

Подключитесь к PostgreSQL и выполните:

```sql
INSERT INTO web_users (
    username, 
    password_hash, 
    role, 
    created_at, 
    is_active
) VALUES (
    'admin',
    '$2b$12$62RIcEMlytJlqCGX8xWKwubEI5QCkMS5AqWJ12UsSkUbCaei7lHMe',
    'admin',
    NOW(),
    TRUE
);
```

### Шаг 3: Проверка создания пользователя

```sql
SELECT id, username, role, created_at, is_active 
FROM web_users 
WHERE username = 'admin';
```

## Способ 2: Через API endpoint (Альтернативный)

Если веб-сервер уже запущен, можно использовать специальный endpoint для инициализации:

```bash
curl -X POST http://localhost:5000/auth/init-admin \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "arminda2025",
    "init_key": "your_init_key_from_env"
  }'
```

**Примечание:** Для этого способа нужен `INIT_KEY` в переменных окружения.

## Способ 3: Через Python скрипт (Программный)

Создайте файл `create_admin.py`:

```python
#!/usr/bin/env python3
import os
import sys
sys.path.append('/path/to/your/bot')

from storage.database_unified import create_web_user
from webapp.auth.jwt_auth import generate_password_hash

def create_admin():
    username = "admin"
    password = "arminda2025"
    role = "admin"
    
    # Генерируем хеш пароля
    password_hash = generate_password_hash(password)
    
    # Создаем пользователя
    try:
        user_id = create_web_user(username, password_hash, role)
        print(f"Администратор создан успешно! ID: {user_id}")
    except Exception as e:
        print(f"Ошибка создания администратора: {e}")

if __name__ == "__main__":
    create_admin()
```

## Подключение к PostgreSQL

### Через psql:
```bash
psql -h localhost -p 5432 -U postgres -d faqbot
```

### Через Docker (если PostgreSQL в контейнере):
```bash
docker exec -it faqbot-postgres psql -U postgres -d faqbot
```

## Данные для входа

После создания администратора:

- **URL веб-интерфейса:** http://localhost:5000
- **Имя пользователя:** admin
- **Пароль:** arminda2025
- **Роль:** admin

## Проверка работы

1. Откройте веб-интерфейс в браузере
2. Войдите с созданными учетными данными
3. Перейдите в раздел загрузки документов
4. Загрузите документы для индексации

## Безопасность

⚠️ **Важно:** После создания администратора рекомендуется:
1. Сменить пароль через веб-интерфейс
2. Создать дополнительных пользователей с ограниченными правами
3. Отключить или защитить endpoint `/auth/init-admin`

## Устранение проблем

### Ошибка "username already exists"
```sql
DELETE FROM web_users WHERE username = 'admin';
```

### Проверка подключения к БД
```sql
SELECT current_database(), current_user, version();
```

### Проверка таблиц
```sql
\dt
```

