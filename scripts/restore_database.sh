#!/bin/bash
#
# PostgreSQL Restore Script для EvolveAI
#
# Этот скрипт восстанавливает БД из резервной копии.
#
# Использование:
#   ./scripts/restore_database.sh <backup_file>
#
# Пример:
#   ./scripts/restore_database.sh ./backups/evolveai_backup_20250110_120000.sql.gz
#

set -e  # Exit on error

# Загрузка переменных окружения
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Проверка аргументов
if [ $# -eq 0 ]; then
    echo "ОШИБКА: Укажите файл бэкапа для восстановления"
    echo "Использование: $0 <backup_file>"
    echo ""
    echo "Доступные бэкапы:"
    ls -lh ./backups/evolveai_backup_*.sql.gz 2>/dev/null || echo "Нет бэкапов"
    exit 1
fi

BACKUP_FILE="$1"

# Проверка существования файла
if [ ! -f "$BACKUP_FILE" ]; then
    echo "ОШИБКА: Файл $BACKUP_FILE не найден!"
    exit 1
fi

# Извлекаем параметры подключения из DATABASE_URL
DB_USER=$(echo $DATABASE_URL | sed -n 's#.*://\([^:]*\):.*#\1#p')
DB_PASS=$(echo $DATABASE_URL | sed -n 's#.*://[^:]*:\([^@]*\)@.*#\1#p')
DB_HOST=$(echo $DATABASE_URL | sed -n 's#.*@\([^:]*\):.*#\1#p')
DB_PORT=$(echo $DATABASE_URL | sed -n 's#.*:\([0-9]*\)/.*#\1#p')
DB_NAME=$(echo $DATABASE_URL | sed -n 's#.*/\([^?]*\).*#\1#p')

# Проверка необходимых команд
command -v psql >/dev/null 2>&1 || { echo "ERROR: psql не установлен. Установите postgresql-client."; exit 1; }
command -v gunzip >/dev/null 2>&1 || { echo "ERROR: gunzip не установлен."; exit 1; }

echo "========================================="
echo "PostgreSQL Restore для EvolveAI"
echo "========================================="
echo "Дата: $(date)"
echo "База данных: $DB_NAME"
echo "Хост: $DB_HOST:$DB_PORT"
echo "Пользователь: $DB_USER"
echo "Файл бэкапа: $BACKUP_FILE"
echo "========================================="
echo ""
echo "⚠️  ВНИМАНИЕ: Это действие удалит все текущие данные в БД!"
echo "⚠️  Вы уверены, что хотите продолжить? (yes/no)"
read -r CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Восстановление отменено."
    exit 0
fi

echo ""
echo "Начинаем восстановление из бэкапа..."
export PGPASSWORD="$DB_PASS"

# Восстановление из gz файла
gunzip -c "$BACKUP_FILE" | psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -v ON_ERROR_STOP=1

unset PGPASSWORD

echo ""
echo "========================================="
echo "✓ Восстановление завершено успешно!"
echo "========================================="
echo ""
echo "Рекомендуется:"
echo "1. Проверить корректность данных"
echo "2. Перезапустить сервисы: docker-compose restart"
echo "3. Проверить логи: docker-compose logs -f api"
