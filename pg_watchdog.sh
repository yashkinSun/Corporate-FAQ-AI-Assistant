#!/bin/bash
#
# pg_watchdog.sh — проверяет состояние Postgres и рестартит docker-compose при проблемах
#

# Путь к папке с docker-compose.yml
PROJECT_DIR="/path/to/botvopros3"
# Имя сервиса в Compose
SERVICE_NAME="faqbot-postgres"
# Лог-файл
LOGFILE="$PROJECT_DIR/watchdog.log"

cd "$PROJECT_DIR" || exit 1

# Проверяем состояние healthcheck
STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$SERVICE_NAME")

if [ "$STATUS" != "healthy" ]; then
  echo "[$(date)] WARNING: $SERVICE_NAME status = $STATUS. Restarting services..." >> "$LOGFILE"
  
  # Сначала делаем бэкап перед рестартом
  ./backup_postgres.sh >> "$LOGFILE" 2>&1
  
  # Рестартим контейнеры
  docker-compose restart
  
  echo "[$(date)] Restart command issued." >> "$LOGFILE"
else
  echo "[$(date)] OK: $SERVICE_NAME is healthy." >> "$LOGFILE"
fi
