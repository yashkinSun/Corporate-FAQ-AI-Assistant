#!/bin/bash
#
# backup_postgres.sh — делает дамп базы из контейнера faqbot-postgres
#

# Настройки
CONTAINER_NAME="faqbot-postgres"
BACKUP_DIR="./backups"             # папка на хосте для хранения дампов
TIMESTAMP=$(date +'%Y%m%d_%H%M%S') # метка времени
DB_NAME="${PG_DB:-faqbot}"         # имя базы из .env или по умолчанию
DB_USER="${PG_USER:-postgres}"     # пользователь
DB_HOST="localhost"
DB_PORT="${PG_PORT:-5432}"
# В случае пароля, можно положить .pgpass или передавать через переменную окружения PGPASSWORD.

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup of $DB_NAME to $BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"
docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" "$DB_NAME" \
  | gzip > "$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"

if [ $? -eq 0 ]; then
  echo "[$(date)] Backup succeeded"
else
  echo "[$(date)] Backup FAILED" >&2
fi
