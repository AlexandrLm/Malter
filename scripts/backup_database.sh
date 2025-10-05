#!/bin/bash
#
# PostgreSQL Backup Script для EvolveAI
#
# Этот скрипт создает резервную копию БД PostgreSQL с ротацией старых бэкапов.
# Использует pg_dump для создания SQL dump файла.
#
# Использование:
#   ./scripts/backup_database.sh
#
# Настройка через переменные окружения или .env файл
#

set -e  # Exit on error

# Загрузка переменных окружения из .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Конфигурация
BACKUP_DIR="${BACKUP_DIR:-./backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/evolveai_backup_${TIMESTAMP}.sql.gz"

# Извлекаем параметры подключения из DATABASE_URL
# Формат: postgresql+asyncpg://user:pass@host:port/dbname
DB_USER=$(echo $DATABASE_URL | sed -n 's#.*://\([^:]*\):.*#\1#p')
DB_PASS=$(echo $DATABASE_URL | sed -n 's#.*://[^:]*:\([^@]*\)@.*#\1#p')
DB_HOST=$(echo $DATABASE_URL | sed -n 's#.*@\([^:]*\):.*#\1#p')
DB_PORT=$(echo $DATABASE_URL | sed -n 's#.*:\([0-9]*\)/.*#\1#p')
DB_NAME=$(echo $DATABASE_URL | sed -n 's#.*/\([^?]*\).*#\1#p')

# Проверка необходимых команд
command -v pg_dump >/dev/null 2>&1 || { echo "ERROR: pg_dump не установлен. Установите postgresql-client."; exit 1; }
command -v gzip >/dev/null 2>&1 || { echo "ERROR: gzip не установлен."; exit 1; }

# Создание директории для бэкапов
mkdir -p "$BACKUP_DIR"

echo "========================================="
echo "PostgreSQL Backup для EvolveAI"
echo "========================================="
echo "Дата: $(date)"
echo "База данных: $DB_NAME"
echo "Хост: $DB_HOST:$DB_PORT"
echo "Пользователь: $DB_USER"
echo "Файл бэкапа: $BACKUP_FILE"
echo "========================================="

# Создание бэкапа
echo "Начинаем создание бэкапа..."
export PGPASSWORD="$DB_PASS"

pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --clean \
    --if-exists \
    --no-owner \
    --no-acl \
    | gzip > "$BACKUP_FILE"

unset PGPASSWORD

# Проверка успешности создания бэкапа
if [ -f "$BACKUP_FILE" ] && [ -s "$BACKUP_FILE" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "✓ Бэкап успешно создан: $BACKUP_FILE ($BACKUP_SIZE)"
else
    echo "✗ ОШИБКА: Бэкап не был создан или пустой!"
    exit 1
fi

# Удаление старых бэкапов (старше BACKUP_RETENTION_DAYS дней)
echo "Удаление старых бэкапов (старше ${BACKUP_RETENTION_DAYS} дней)..."
find "$BACKUP_DIR" -name "evolveai_backup_*.sql.gz" -type f -mtime +${BACKUP_RETENTION_DAYS} -delete
echo "✓ Очистка завершена"

# Список всех бэкапов
echo ""
echo "Список всех бэкапов:"
ls -lh "$BACKUP_DIR"/evolveai_backup_*.sql.gz 2>/dev/null || echo "Нет бэкапов"

echo ""
echo "========================================="
echo "Бэкап завершен успешно!"
echo "========================================="
