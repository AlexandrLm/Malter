# 🔧 Исправление контейнера миграций

## Проблема

Контейнер `migration` не запускается с ошибкой:
```
ModuleNotFoundError: No module named 'utils'
```

или

```
ImportError: cannot import name 'encryption' from 'utils'
```

## Причина

В `Dockerfile.migration` отсутствует копирование папки `utils`, которая содержит модули необходимые для работы миграций (encryption, circuit_breaker и т.д.).

## Решение

### Уже примененные исправления:

1. **Обновлен `Dockerfile.migration`:**
   - Добавлена строка `COPY utils ./utils`
   - Добавлена переменная окружения `ENV PYTHONPATH=/app`

2. **Исправлен `alembic/env.py`:**
   - Удалены дублирующиеся импорты моделей
   - Оставлен только необходимый импорт `from server.models import Base`

## Как применить исправления на VDS

### Если вы еще не запускали проект:

```bash
cd /home/user/evolveai  # ваш путь к проекту

# 1. Обновить код
git pull origin main

# 2. Сразу запустить Docker Compose
docker compose up -d

# 3. Проверить статус миграций
docker compose logs migration

# Должно увидеть:
# INFO [alembic.runtime.migration] Running upgrade ... до ...
# INFO [alembic.runtime.migration] Done
```

### Если уже запускали и контейнер migration упал:

```bash
# 1. Остановить все сервисы
docker compose down

# 2. Обновить код
git pull origin main

# 3. Пересобрать образ migration
docker compose build --no-cache migration

# 4. Запустить снова
docker compose up -d

# 5. Проверить логи
docker compose logs -f migration
```

### Полная переборка (если ничего не помогает):

```bash
# 1. Остановить и удалить все (ОПАСНО - удалит БД!)
docker compose down -v

# 2. Обновить код
git pull origin main

# 3. Пересобрать все образы
docker compose build --no-cache

# 4. Запустить
docker compose up -d

# 5. Ждать пока миграции завершатся
docker compose logs -f migration

# Должно вывести:
# Migration complete!
# service_completed_successfully
```

## Проверка успешного выполнения

```bash
# Проверить статус всех контейнеров
docker compose ps

# Должно быть:
# migration  Exited (0)  - это нормально, миграции выполнились и контейнер остановился

# Проверить логи миграций
docker compose logs migration

# Должны быть строки:
# Running upgrade ... to ...
# Done

# Проверить что API работает
curl http://localhost:8000/health
# Должен вернуть: {"status":"ok"}
```

## Если проблема все еще есть

Посмотрите полные логи:

```bash
# Подробные логи миграций
docker compose logs --tail=200 migration

# Логи БД
docker compose logs db

# Логи API (может потребоваться БД)
docker compose logs api
```

Ищите в логах:
- `ModuleNotFoundError` - значит не скопировалась какая-то папка
- `Connection refused` - БД еще не готова
- `FATAL: password authentication failed` - неверный POSTGRES_PASSWORD в .env

## Файлы которые были изменены

1. **Dockerfile.migration**
   - Добавлена строка: `COPY utils ./utils`
   - Добавлена переменная: `ENV PYTHONPATH=/app`

2. **alembic/env.py**
   - Удалены дублирующиеся импорты моделей

## Дополнительная информация

### Что делает контейнер migration:

1. Копирует все необходимые файлы проекта
2. Устанавливает зависимости из requirements.txt
3. Читает переменные окружения из .env
4. Подключается к PostgreSQL БД
5. Выполняет команду: `alembic upgrade head`
6. Применяет все миграции из папки alembic/versions/

### Почему это необходимо:

- Миграции должны выполниться ДО запуска API и Bot
- В docker-compose.yml указано: `depends_on: migration: condition: service_completed_successfully`
- Это гарантирует что БД будет инициализирована правильно

### Как добавить новую миграцию:

```bash
# Локально (на вашей машине):
alembic revision --autogenerate -m "Описание изменений"

# На VDS миграция применится автоматически при:
# - docker compose down && docker compose up -d
# - git pull && docker compose restart
```

---

**Статус:** ✅ Исправлено и протестировано
