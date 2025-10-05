# 💾 Backup Strategy для PostgreSQL

> Документация по резервному копированию БД EvolveAI

---

## 📋 Содержание

1. [Обзор стратегии](#обзор-стратегии)
2. [Ручные бэкапы](#ручные-бэкапы)
3. [Автоматические бэкапы](#автоматические-бэкапы)
4. [Восстановление из бэкапа](#восстановление-из-бэкапа)
5. [Тестирование бэкапов](#тестирование-бэкапов)
6. [Облачные бэкапы (S3)](#облачные-бэкапы-s3)
7. [Мониторинг и алерты](#мониторинг-и-алерты)

---

## Обзор стратегии

### Типы бэкапов

1. **Ежедневные бэкапы** (автоматические)
   - Частота: Каждый день в 02:00 UTC
   - Хранение: 7 дней
   - Метод: pg_dump + gzip

2. **Еженедельные бэкапы** (автоматические)
   - Частота: Каждое воскресенье в 03:00 UTC
   - Хранение: 4 недели
   - Метод: pg_dump + gzip
   - Загрузка в S3 (опционально)

3. **Ручные бэкапы** (перед критическими изменениями)
   - Перед миграцией БД
   - Перед major updates
   - По требованию

### Политика хранения

| Тип бэкапа | Хранение | Место хранения |
|------------|----------|----------------|
| Ежедневный | 7 дней | Локальный диск |
| Еженедельный | 30 дней | Локальный + S3 |
| Ручной | Неограниченно | По выбору |

---

## Ручные бэкапы

### Создание бэкапа

```bash
# Базовое использование
./scripts/backup_database.sh

# Результат:
# ./backups/evolveai_backup_20250110_120000.sql.gz
```

### Параметры через переменные окружения

```bash
# В .env файле:
BACKUP_DIR=./backups
BACKUP_RETENTION_DAYS=7

# Или напрямую:
BACKUP_DIR=/mnt/backups ./scripts/backup_database.sh
```

### Docker окружение

```bash
# Бэкап из Docker контейнера
docker-compose exec postgres pg_dump \
  -U evolveai_user \
  -d evolveai_db \
  --clean \
  --if-exists \
  | gzip > ./backups/manual_backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

---

## Автоматические бэкапы

### Настройка с Cron

Добавьте в crontab сервера:

```bash
# Открыть crontab
crontab -e

# Добавить задачи:
# Ежедневный бэкап в 02:00 UTC
0 2 * * * /opt/evolveai/scripts/backup_database.sh >> /var/log/evolveai_backup.log 2>&1

# Еженедельный бэкап в воскресенье 03:00 UTC + загрузка в S3
0 3 * * 0 /opt/evolveai/scripts/backup_database.sh && /opt/evolveai/scripts/upload_to_s3.sh >> /var/log/evolveai_backup.log 2>&1
```

### Настройка с Kubernetes CronJob

Создайте файл `k8s/backup-cronjob.yaml`:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
spec:
  schedule: "0 2 * * *"  # Каждый день в 02:00
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:16
            env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: evolveai-secrets
                  key: database-url
            command:
            - /bin/bash
            - -c
            - |
              TIMESTAMP=$(date +%Y%m%d_%H%M%S)
              BACKUP_FILE="/backups/evolveai_backup_${TIMESTAMP}.sql.gz"
              
              pg_dump "${DATABASE_URL}" --clean --if-exists | gzip > "$BACKUP_FILE"
              
              # Удаление старых бэкапов (>7 дней)
              find /backups -name "*.sql.gz" -mtime +7 -delete
            volumeMounts:
            - name: backup-storage
              mountPath: /backups
          restartPolicy: OnFailure
          volumes:
          - name: backup-storage
            persistentVolumeClaim:
              claimName: backup-pvc
```

Применить:
```bash
kubectl apply -f k8s/backup-cronjob.yaml
```

### Настройка с Docker Compose

Добавьте в `docker-compose.yml`:

```yaml
services:
  backup:
    image: postgres:16
    depends_on:
      - postgres
    volumes:
      - ./backups:/backups
      - ./scripts:/scripts
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - BACKUP_DIR=/backups
      - BACKUP_RETENTION_DAYS=7
    command: >
      bash -c "
      while true; do
        sleep 86400;  # 24 часа
        /scripts/backup_database.sh
      done
      "
```

---

## Восстановление из бэкапа

### Базовое восстановление

```bash
# 1. Выбрать бэкап
ls -lh ./backups/

# 2. Остановить сервисы (для безопасности)
docker-compose stop api bot

# 3. Восстановить БД
./scripts/restore_database.sh ./backups/evolveai_backup_20250110_120000.sql.gz

# 4. Запустить сервисы
docker-compose start api bot

# 5. Проверить логи
docker-compose logs -f api
```

### Восстановление в новую БД (тестирование)

```bash
# 1. Создать тестовую БД
docker-compose exec postgres psql -U postgres -c "CREATE DATABASE evolveai_test;"

# 2. Восстановить в тестовую БД
gunzip -c ./backups/evolveai_backup_20250110_120000.sql.gz | \
  docker-compose exec -T postgres psql -U postgres -d evolveai_test

# 3. Проверить данные
docker-compose exec postgres psql -U postgres -d evolveai_test -c "\dt"
```

### Point-in-Time Recovery (PITR)

Для PITR необходимо настроить WAL архивирование:

```bash
# В postgresql.conf:
wal_level = replica
archive_mode = on
archive_command = 'cp %p /var/lib/postgresql/wal_archive/%f'
```

---

## Тестирование бэкапов

### Автоматическое тестирование

Создайте скрипт `scripts/test_backup.sh`:

```bash
#!/bin/bash
set -e

BACKUP_FILE="$1"
TEST_DB="evolveai_test_$(date +%s)"

echo "Тестирование бэкапа: $BACKUP_FILE"

# 1. Создать тестовую БД
docker-compose exec -T postgres psql -U postgres -c "CREATE DATABASE $TEST_DB;"

# 2. Восстановить бэкап
gunzip -c "$BACKUP_FILE" | \
  docker-compose exec -T postgres psql -U postgres -d "$TEST_DB"

# 3. Проверить таблицы
TABLES=$(docker-compose exec -T postgres psql -U postgres -d "$TEST_DB" -t -c "\dt" | wc -l)

if [ "$TABLES" -gt 5 ]; then
    echo "✓ Бэкап валидный: $TABLES таблиц"
else
    echo "✗ ОШИБКА: Недостаточно таблиц в бэкапе!"
    exit 1
fi

# 4. Удалить тестовую БД
docker-compose exec -T postgres psql -U postgres -c "DROP DATABASE $TEST_DB;"

echo "✓ Тестирование успешно завершено"
```

Использование:
```bash
./scripts/test_backup.sh ./backups/evolveai_backup_20250110_120000.sql.gz
```

---

## Облачные бэкапы (S3)

### Настройка AWS S3

```bash
# Установка AWS CLI
pip install awscli

# Конфигурация
aws configure
# AWS Access Key ID: YOUR_KEY
# AWS Secret Access Key: YOUR_SECRET
# Default region: us-east-1
```

### Скрипт загрузки в S3

Создайте `scripts/upload_to_s3.sh`:

```bash
#!/bin/bash
set -e

BACKUP_DIR="${BACKUP_DIR:-./backups}"
S3_BUCKET="${S3_BUCKET:-evolveai-backups}"
S3_PREFIX="${S3_PREFIX:-postgres}"

# Загрузка последнего бэкапа
LATEST_BACKUP=$(ls -t "${BACKUP_DIR}"/evolveai_backup_*.sql.gz | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "Нет бэкапов для загрузки"
    exit 1
fi

echo "Загрузка $LATEST_BACKUP в S3..."
aws s3 cp "$LATEST_BACKUP" "s3://${S3_BUCKET}/${S3_PREFIX}/" --storage-class STANDARD_IA

echo "✓ Загрузка завершена"
```

### Автоматическая загрузка в S3 (cron)

```bash
# Добавить в crontab
0 3 * * 0 /opt/evolveai/scripts/backup_database.sh && /opt/evolveai/scripts/upload_to_s3.sh
```

### Скачивание из S3

```bash
# Список бэкапов в S3
aws s3 ls s3://evolveai-backups/postgres/

# Скачать конкретный бэкап
aws s3 cp s3://evolveai-backups/postgres/evolveai_backup_20250110_120000.sql.gz ./backups/
```

---

## Мониторинг и алерты

### Проверка успешности бэкапов

Добавьте в скрипт `scripts/backup_database.sh`:

```bash
# В конце скрипта
if [ $? -eq 0 ]; then
    # Отправить успешное уведомление
    curl -X POST https://your-monitoring-service.com/webhook \
        -d "status=success" \
        -d "backup_file=$BACKUP_FILE" \
        -d "backup_size=$BACKUP_SIZE"
else
    # Отправить алерт о провале
    curl -X POST https://your-monitoring-service.com/webhook \
        -d "status=failed" \
        -d "error=$?"
fi
```

### Мониторинг с Prometheus

Экспортируйте метрики бэкапов:

```python
# В utils/backup_metrics.py
from prometheus_client import Gauge, Counter

backup_last_success_timestamp = Gauge('backup_last_success_timestamp', 'Last successful backup timestamp')
backup_size_bytes = Gauge('backup_size_bytes', 'Size of last backup in bytes')
backup_failures_total = Counter('backup_failures_total', 'Total number of backup failures')
```

### Алерты с Healthchecks.io

```bash
# В scripts/backup_database.sh
HEALTHCHECK_URL="https://hc-ping.com/your-unique-id"

# В начале скрипта
curl -m 10 --retry 5 "${HEALTHCHECK_URL}/start"

# В конце при успехе
curl -m 10 --retry 5 "${HEALTHCHECK_URL}"

# При ошибке
curl -m 10 --retry 5 "${HEALTHCHECK_URL}/fail"
```

---

## Рекомендации для Production

### Обязательно:
- ✅ Автоматические ежедневные бэкапы
- ✅ Хранение как минимум 7 дней бэкапов
- ✅ Еженедельное тестирование восстановления
- ✅ Offsite storage (S3, Azure, etc.)
- ✅ Мониторинг и алерты

### Желательно:
- 📝 Шифрование бэкапов (gpg)
- 📝 PITR с WAL архивированием
- 📝 Replica для read-only запросов
- 📝 Автоматическое тестирование бэкапов

### Чек-лист перед Production:
- [ ] Cron задачи настроены
- [ ] Тестовое восстановление выполнено успешно
- [ ] S3 bucket создан и настроен
- [ ] Мониторинг настроен
- [ ] Runbook документирован
- [ ] Команда обучена процедуре восстановления

---

## FAQ

**Q: Как часто делать бэкапы?**  
A: Зависит от критичности данных. Для production рекомендуется:
- Ежедневные бэкапы минимум
- Continuous backup с WAL для критичных систем

**Q: Сколько места занимают бэкапы?**  
A: ~60-80% от размера БД после сжатия gzip. Например, 1GB БД → ~600MB backup.

**Q: Как долго восстанавливается БД?**  
A: Зависит от размера:
- < 1GB: ~1-2 минуты
- 1-10GB: ~5-15 минут
- > 10GB: ~30+ минут

**Q: Можно ли делать бэкапы без остановки сервиса?**  
A: Да! pg_dump работает онлайн без блокировки БД.

---
