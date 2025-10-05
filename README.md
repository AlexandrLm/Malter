# 🤖 EvolveAI - Интеллектуальный Telegram Бот

> Продвинутый conversational AI бот с системой эволюционирующих отношений, долговременной памятью и премиум подпиской

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 Содержание

- [О проекте](#-о-проекте)
- [Архитектура](#-архитектура)
- [Основные возможности](#-основные-возможности)
- [Технологический стек](#-технологический-стек)
- [Быстрый старт](#-быстрый-старт)
- [Конфигурация](#-конфигурация)
- [Документация API](#-документация-api)
- [Безопасность](#-безопасность)
- [Масштабируемость](#-масштабируемость)
- [Мониторинг и аналитика](#-мониторинг-и-аналитика)
- [Разработка](#-разработка)
- [Устранение неполадок](#-устранение-неполадок)
- [Лицензия](#-лицензия)

---

## 🎯 О проекте

**EvolveAI** - это enterprise-grade conversational AI система, построенная на базе Google Gemini AI, которая предоставляет персонализированный опыт общения с пользователями через Telegram бота.

### Ключевые особенности:

- 🧠 **Эволюционирующие отношения** - система уровней отношений от "Незнакомец" до "Intimate"
- 💾 **Долговременная память** - сохранение и категоризация фактов о пользователе
- 🔊 **Голосовые сообщения** - генерация реалистичных голосовых ответов (TTS)
- 💳 **Премиум подписка** - система монетизации с расширенными возможностями
- 📊 **Продвинутая аналитика** - детальная статистика использования и поведения пользователей
- 🔐 **Enterprise безопасность** - шифрование данных, JWT аутентификация, rate limiting
- 📈 **Горизонтальное масштабирование** - готовность к высоким нагрузкам

---

## 🏗 Архитектура

Проект построен на микросервисной архитектуре с использованием Docker:

```
┌─────────────────────────────────────────────────────┐
│                   TELEGRAM BOT                       │
│          (aiogram + async processing)                │
└──────────────────┬──────────────────────────────────┘
                   │ JWT Auth + HTTP
                   ▼
┌─────────────────────────────────────────────────────┐
│              FASTAPI REST API                        │
│   (Gunicorn + Uvicorn Workers + Middleware)         │
│                                                      │
│  ┌──────────────┬──────────────┬─────────────────┐ │
│  │  Chat        │  Analytics   │  Admin          │ │
│  │  Endpoints   │  Endpoints   │  Endpoints      │ │
│  └──────────────┴──────────────┴─────────────────┘ │
└──────────┬───────────────┬──────────────────────────┘
           │               │
           ▼               ▼
┌──────────────────┐  ┌──────────────────┐
│   PostgreSQL     │  │   Redis Cache    │
│   (Primary DB)   │  │  (Circuit Breaker)│
└──────────────────┘  └──────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│         Google Gemini AI              │
│  (Text Generation + TTS + Vision)    │
└──────────────────────────────────────┘
```

### Основные компоненты:

#### 1. **Bot Service** (`bot/`)
- Telegram Bot на базе aiogram 3.x
- Асинхронная обработка сообщений
- Интеграция с payment API
- Обработчики команд и колбэков

#### 2. **API Service** (`main.py` + `server/`)
- FastAPI REST API с OpenAPI документацией
- JWT аутентификация
- Rate limiting (SlowAPI)
- Prometheus метрики
- Health checks (liveness/readiness)

#### 3. **Database Layer** (`server/database.py` + `server/models.py`)
- PostgreSQL с asyncpg
- SQLAlchemy ORM
- Alembic миграции
- Шифрование чувствительных данных

#### 4. **AI Engine** (`server/ai.py`)
- Google Gemini integration
- Context management
- Image analysis support
- Circuit Breaker паттерн

#### 5. **Utils** (`utils/`)
- **Circuit Breaker** - защита от каскадных сбоев
- **Cache** - Redis кэширование с fallback
- **Encryption** - шифрование данных (Fernet)
- **DB Monitoring** - отслеживание slow queries

---

## ✨ Основные возможности

### Для пользователей:

| Функция | Free | Premium |
|---------|------|---------|
| Текстовые сообщения | 50/день | Безлимит |
| История диалога | 10 сообщений | Полная |
| Голосовые ответы | ❌ | ✅ |
| Анализ изображений | ❌ | ✅ |
| Долговременная память | Базовая | Расширенная |
| Приоритетная обработка | ❌ | ✅ |

### Система отношений:

1. **Незнакомец** (0-99 очков) - первое знакомство
2. **Знакомый** (100-299) - налаживание контакта
3. **Друг** (300-599) - доверительное общение
4. **Близкий друг** (600-999) - глубокая связь
5. **Intimate** (1000+) - максимальная близость

### AI Capabilities:

- 🧩 **Контекстное общение** - учет истории до 10+ сообщений
- 📝 **Суммаризация** - автоматическое создание сводок диалога
- 🎭 **Адаптивная личность** - изменение тона в зависимости от уровня отношений
- 🖼️ **Мультимодальность** - анализ изображений и текста
- 🗣️ **TTS генерация** - реалистичные голосовые сообщения
- 🧠 **Память фактов** - сохранение и вызов информации о пользователе

---

## 🛠 Технологический стек

### Backend:
- **Python 3.11+** - основной язык
- **FastAPI 0.116** - REST API framework
- **aiogram 3.21** - Telegram Bot framework
- **SQLAlchemy 2.0** - ORM
- **asyncpg** - асинхронный PostgreSQL драйвер
- **Alembic** - database migrations

### AI & ML:
- **Google Gemini API** - LLM для генерации текста
- **Gemini Vision** - анализ изображений
- **Gemini TTS** - text-to-speech

### Infrastructure:
- **PostgreSQL 15.7** - primary database
- **Redis 7.2** - кэширование и circuit breaker
- **Docker & Docker Compose** - контейнеризация
- **Gunicorn + Uvicorn** - ASGI сервер

### Monitoring & Observability:
- **Prometheus** - метрики
- **starlette-prometheus** - FastAPI middleware
- **Custom DB monitoring** - отслеживание slow queries
- **Health checks** - liveness/readiness probes

### Security:
- **python-jose** - JWT токены
- **passlib + bcrypt** - хэширование паролей
- **cryptography** - шифрование данных (Fernet)
- **SlowAPI** - rate limiting

---

## 🚀 Быстрый старт

### Предварительные требования:

- Docker 20.10+
- Docker Compose 2.0+
- Git

### Установка:

```bash
# 1. Клонирование репозитория
git clone https://github.com/yourusername/evolveai.git
cd evolveai

# 2. Создание .env файла
cp .env.example .env

# 3. Настройка переменных окружения (ОБЯЗАТЕЛЬНО!)
nano .env  # Редактируйте файл

# Минимально необходимые переменные:
# - TELEGRAM_BOT_TOKEN (от @BotFather)
# - GOOGLE_API_KEY (от Google AI Studio)
# - POSTGRES_PASSWORD (безопасный пароль)
# - JWT_SECRET (генерация: openssl rand -hex 32)
# - ENCRYPTION_KEY (генерация: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# 4. Запуск всех сервисов
docker-compose up -d

# 5. Проверка статуса
docker-compose ps
docker-compose logs -f
```

### Проверка работоспособности:

```bash
# Health check API
curl http://localhost:8000/health

# Ready check (проверка всех зависимостей)
curl http://localhost:8000/ready

# API документация
open http://localhost:8000/docs

# Prometheus метрики
curl http://localhost:8000/metrics
```

---

## ⚙️ Конфигурация

### Переменные окружения (.env):

#### Обязательные:

```env
# Telegram
TELEGRAM_BOT_TOKEN="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"

# Google AI
GOOGLE_API_KEY="AIza..."

# Database
POSTGRES_USER=myuser
POSTGRES_PASSWORD=super_secure_password_here
POSTGRES_DB=malterdb
DB_HOST=db

# Security (КРИТИЧНО!)
JWT_SECRET=your-super-secret-jwt-key-min-32-chars
ENCRYPTION_KEY=your-fernet-encryption-key-here
```

#### Опциональные:

```env
# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
CACHE_TTL_SECONDS=600

# Payments (опционально)
PAYMENT_PROVIDER_TOKEN="your_payment_token"

# Logging
LOG_LEVEL=INFO

# HTTPX
HTTPX_TIMEOUT=180
HTTPX_CONNECT_TIMEOUT=10

# AI Settings
MAX_AI_ITERATIONS=3
AI_THINKING_BUDGET=0
MAX_IMAGE_SIZE_MB=10
```

### Docker Compose конфигурация:

Проект использует 5 сервисов:

1. **api** - FastAPI REST API (4 Gunicorn workers)
2. **bot** - Telegram Bot (aiogram)
3. **db** - PostgreSQL 15.7
4. **redis** - Redis 7.2
5. **migration** - Alembic миграции (одноразовый)

```bash
# Просмотр логов конкретного сервиса
docker-compose logs -f api
docker-compose logs -f bot

# Перезапуск сервиса
docker-compose restart api

# Масштабирование API workers
docker-compose up -d --scale api=2

# Остановка всех сервисов
docker-compose down

# Остановка с удалением volumes (ОПАСНО: удалит все данные!)
docker-compose down -v
```

---

## 📡 Документация API

### Authentication:

Все эндпоинты требуют JWT токен в заголовке:

```bash
Authorization: Bearer <jwt_token>
```

Получение токена:

```bash
POST /auth
Content-Type: application/json

{
  "user_id": 123456789
}

# Response:
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

### Основные эндпоинты:

#### Chat:

```bash
# Отправка сообщения
POST /chat
Authorization: Bearer <token>
Content-Type: application/json

{
  "message": "Привет!",
  "timestamp": "2025-10-05T12:00:00Z",
  "image_data": null  # или base64 строка
}

# Response:
{
  "response_text": "Привет! Как дела?",
  "voice_message": null,  # или base64 audio
  "image_base64": null
}
```

#### Profile:

```bash
# Получение профиля
GET /profile/{user_id}

# Обновление профиля
POST /profile
{
  "user_id": 123,
  "data": {
    "name": "Иван",
    "gender": "male"
  }
}

# Удаление профиля
DELETE /profile/{user_id}

# Статус подписки
GET /profile/status/{user_id}
```

#### Admin Endpoints (требуют JWT + admin права):

```bash
# Метрики БД
GET /admin/db_metrics
Authorization: Bearer <admin_token>

# Статистика кэша
GET /admin/cache_stats

# Статус scheduler
GET /admin/scheduler_status

# Аналитика
GET /admin/analytics/overview
GET /admin/analytics/users
GET /admin/analytics/messages?days=7
GET /admin/analytics/revenue
GET /admin/analytics/features
GET /admin/analytics/cohort?days=30
GET /admin/analytics/funnel
GET /admin/analytics/activity
GET /admin/analytics/tools?days=7
```

### Swagger UI:

Полная интерактивная документация API доступна по адресу:

```
http://localhost:8000/docs
```

---

## 🔐 Безопасность

### Реализованные меры защиты:

#### 1. Authentication & Authorization:
- ✅ JWT токены с коротким TTL (1 час)
- ✅ HMAC-SHA256 подпись токенов
- ✅ Валидация силы JWT_SECRET (минимум 32 символа)
- ✅ Bearer token scheme

#### 2. Data Encryption:
- ✅ Шифрование чувствительных данных (Fernet)
- ✅ Хэширование паролей (bcrypt)
- ✅ Безопасное хранение имен пользователей

#### 3. Rate Limiting:
```python
# Примеры лимитов:
- /auth: 10/minute
- /chat: 10/minute
- /profile: 20/minute
- /admin/*: 10/minute
- /admin/cleanup_chat_history: 1/hour
```

#### 4. Input Validation:
- ✅ Pydantic schemas для всех входных данных
- ✅ Sanitization (bleach) для предотвращения XSS
- ✅ Валидация размера изображений (макс 10MB)
- ✅ SQL Injection защита (SQLAlchemy ORM)

#### 5. Infrastructure Security:
- ✅ Docker изоляция сервисов
- ✅ Health checks (liveness/readiness)
- ✅ Graceful shutdown (SIGTERM handling)
- ✅ Secrets в environment variables

### Security Checklist для Production:

```bash
# 1. Генерация безопасных ключей
openssl rand -hex 32  # JWT_SECRET
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # ENCRYPTION_KEY

# 2. Настройка HTTPS (через reverse proxy: nginx/traefik)
# 3. Настройка firewall правил
# 4. Ограничение доступа к /admin/* endpoints
# 5. Настройка логирования и мониторинга
# 6. Регулярные бэкапы БД
# 7. Аудит зависимостей (pip-audit, safety)
```

Подробнее:
- [SECURITY_FIXES.md](./SECURITY_FIXES.md)
- [PRIVACY_AND_SECURITY_AUDIT.md](./PRIVACY_AND_SECURITY_AUDIT.md)
- [APPLY_SECURITY_FIXES.md](./APPLY_SECURITY_FIXES.md)

---

## 📈 Масштабируемость

### Текущая архитектура поддерживает:

#### 1. **Горизонтальное масштабирование API:**
```bash
# Увеличение числа API workers
docker-compose up -d --scale api=4

# Gunicorn уже использует 4 worker процесса
```

#### 2. **Connection Pooling:**
- PostgreSQL: asyncpg с пулом соединений
- Redis: Connection pool (max 50 connections)

#### 3. **Caching Strategy:**
- Redis для кэширования часто запрашиваемых данных
- TTL: 600 секунд (настраивается)
- Graceful degradation при недоступности Redis

#### 4. **Circuit Breaker Pattern:**
```python
# Gemini API Circuit Breaker:
- Failure Threshold: 5 ошибок
- Timeout: 60 секунд
- Half-Open: 1 пробный запрос

# Redis Circuit Breaker:
- Failure Threshold: 3 ошибки
- Timeout: 30 секунд
```

#### 5. **Database Optimization:**
- Индексы на ключевых полях (user_id, timestamp)
- Автоматическая очистка старых данных (scheduler)
- Мониторинг slow queries (>1s логируются)

#### 6. **Async Everywhere:**
- Полностью асинхронная обработка (asyncio)
- Non-blocking I/O операции
- Конкурентная обработка запросов

### Рекомендации для высоких нагрузок:

```bash
# 1. Load Balancer (nginx/HAProxy)
# 2. Read Replicas для PostgreSQL
# 3. Redis Cluster для кэша
# 4. CDN для статики
# 5. Message Queue (RabbitMQ/Kafka) для фоновых задач
# 6. Kubernetes для оркестрации
```

Подробнее:
- [SCALABILITY_IMPROVEMENTS.md](./SCALABILITY_IMPROVEMENTS.md)
- [CHANGELOG_SCALABILITY.md](./CHANGELOG_SCALABILITY.md)

---

## 📊 Мониторинг и аналитика

### Prometheus Метрики:

Эндпоинт `/metrics` экспонирует:

```
# Custom метрики:
chat_requests_total - общее количество чат запросов
chat_requests_duration_seconds - время обработки запросов
ai_response_duration_seconds - время генерации AI ответов
tts_generation_duration_seconds - время генерации голоса
voice_messages_generated_total - количество голосовых сообщений

# Стандартные HTTP метрики (starlette-prometheus):
http_requests_total
http_request_duration_seconds
http_requests_in_progress
```

### DB Monitoring:

```bash
# Эндпоинт метрик БД
GET /admin/db_metrics

# Response:
{
  "total_queries": 1543,
  "slow_queries": 3,
  "average_query_time": "0.023s",
  "slow_query_percent": "0.19%",
  "queries": [
    {
      "query": "SELECT * FROM...",
      "duration": "1.234s",
      "timestamp": "2025-10-05 12:00:00"
    }
  ]
}
```

### Scheduler Tasks:

Автоматические фоновые задачи (APScheduler):

1. **Очистка старых сообщений** - ежедневно в 3:00 UTC
2. **Проверка подписок** - каждый час
3. **Метрики кэша** - каждые 5 минут
4. **Прогрев кэша** - при старте

```bash
# Статус scheduler
GET /admin/scheduler_status

# Response:
{
  "running": true,
  "jobs": [
    {
      "id": "cleanup_messages",
      "next_run": "2025-10-06 03:00:00",
      "status": "scheduled"
    }
  ]
}
```

### Analytics Dashboard:

Полный набор аналитических эндпоинтов:

- **Overview** - общая статистика (DAU, MAU, премиум)
- **Users** - распределение по уровням и подпискам
- **Messages** - паттерны использования
- **Revenue** - MRR, ARR, churn rate
- **Features** - использование функций
- **Cohort** - retention analysis
- **Funnel** - конверсия между уровнями
- **Activity** - паттерны по времени
- **Tools** - использование AI tools

Подробнее: [ANALYTICS_GUIDE.md](./ANALYTICS_GUIDE.md)

---

## 💻 Разработка

### Локальная разработка:

```bash
# 1. Создание виртуального окружения
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 2. Установка зависимостей
pip install -r requirements.txt

# 3. Запуск PostgreSQL и Redis локально
docker-compose up db redis -d

# 4. Применение миграций
alembic upgrade head

# 5. Запуск API локально
uvicorn main:app --reload --port 8000

# 6. Запуск бота локально (в другом терминале)
python -m bot
```

### Создание новой миграции:

```bash
# 1. Внесите изменения в server/models.py

# 2. Создайте миграцию
alembic revision --autogenerate -m "Add new column"

# 3. Просмотрите созданную миграцию
cat alembic/versions/<hash>_add_new_column.py

# 4. Примените миграцию
alembic upgrade head

# 5. Откат миграции (если нужно)
alembic downgrade -1
```

### Структура проекта:

```
Malter/
├── alembic/                # Database migrations
│   └── versions/
├── bot/                    # Telegram Bot
│   ├── handlers/           # Message handlers
│   ├── services/           # Business logic
│   └── utils/              # Bot utilities
├── server/                 # FastAPI Application
│   ├── ai.py               # Gemini integration
│   ├── database.py         # Database operations
│   ├── models.py           # SQLAlchemy models
│   ├── schemas.py          # Pydantic schemas
│   ├── analytics.py        # Analytics queries
│   ├── scheduler.py        # Background tasks
│   ├── tts.py              # Text-to-speech
│   └── relationship_config.py  # Levels config
├── utils/                  # Shared utilities
│   ├── cache.py            # Redis caching
│   ├── circuit_breaker.py  # Circuit breaker
│   ├── db_monitoring.py    # DB metrics
│   └── encryption.py       # Data encryption
├── prompts/                # AI prompts
├── scripts/                # Utility scripts
├── main.py                 # FastAPI app entry
├── config.py               # Configuration
├── docker-compose.yml      # Docker orchestration
├── requirements.txt        # Python dependencies
└── .env.example            # Environment template
```

### Тестирование:

```bash
# Запуск всех тестов
pytest

# С покрытием
pytest --cov=server --cov=bot --cov=utils

# Только unit тесты
pytest tests/unit/

# Только integration тесты
pytest tests/integration/
```

### Code Style:

```bash
# Форматирование
black .

# Linting
pylint server/ bot/ utils/

# Type checking
mypy server/ bot/ utils/
```

---

## 🐛 Устранение неполадок

### Частые проблемы:

#### 1. **Ошибка миграции: "Encryption module not available"**

```bash
# Проблема: контейнер миграций не видит модуль utils
# Решение: проверьте PYTHONPATH в Dockerfile.migration

# Временное решение:
docker-compose exec migration python -c "import sys; print(sys.path)"
```

#### 2. **Redis connection refused**

```bash
# Проверка статуса Redis
docker-compose ps redis
docker-compose logs redis

# Перезапуск Redis
docker-compose restart redis

# Проверка доступности
docker-compose exec api ping redis
```

#### 3. **JWT validation failed**

```bash
# Проверьте JWT_SECRET в .env
# Убедитесь, что длина >= 32 символов

# Генерация нового ключа:
openssl rand -hex 32
```

#### 4. **Gemini API errors**

```bash
# Проверка Circuit Breaker статуса
curl http://localhost:8000/ready

# Response покажет состояние:
{
  "gemini": {
    "status": "healthy",
    "circuit_breaker": {
      "state": "CLOSED",
      "failure_count": 0
    }
  }
}

# Если "state": "OPEN" - подождите 60 секунд для автовосстановления
```

#### 5. **Slow database queries**

```bash
# Проверка метрик
curl http://localhost:8000/admin/db_metrics

# Если много slow queries:
# 1. Проверьте индексы
# 2. Запустите очистку старых данных
POST http://localhost:8000/admin/cleanup_chat_history
```

#### 6. **Bot не отвечает**

```bash
# 1. Проверка логов бота
docker-compose logs -f bot

# 2. Проверка статуса API
curl http://localhost:8000/health

# 3. Проверка токена
echo $TELEGRAM_BOT_TOKEN

# 4. Перезапуск бота
docker-compose restart bot
```

### Логи и дебаг:

```bash
# Просмотр всех логов
docker-compose logs -f

# Только ошибки
docker-compose logs --tail=100 | grep ERROR

# Фильтр по сервису
docker-compose logs -f api bot

# Сохранение логов в файл
docker-compose logs > logs_$(date +%Y%m%d_%H%M%S).txt
```

### Performance Profiling:

```bash
# Мониторинг ресурсов
docker stats

# Метрики API
curl http://localhost:8000/metrics | grep http_request_duration

# DB метрики
curl http://localhost:8000/admin/db_metrics

# Cache stats
curl http://localhost:8000/admin/cache_stats
```

---

## 📚 Дополнительная документация

### Руководства:

- [SECURITY_FIXES.md](./SECURITY_FIXES.md) - исправления безопасности
- [SCALABILITY_IMPROVEMENTS.md](./SCALABILITY_IMPROVEMENTS.md) - улучшения масштабируемости
- [ANALYTICS_GUIDE.md](./ANALYTICS_GUIDE.md) - руководство по аналитике
- [BACKUP_STRATEGY.md](./BACKUP_STRATEGY.md) - стратегия резервного копирования
- [PRIVACY_AND_SECURITY_AUDIT.md](./PRIVACY_AND_SECURITY_AUDIT.md) - аудит безопасности
- [improvement_plan.md](./improvement_plan.md) - план улучшений

### Changelogs:

- [CHANGELOG_SCALABILITY.md](./CHANGELOG_SCALABILITY.md) - изменения масштабируемости
- [SECURITY_IMPROVEMENTS_SUMMARY.md](./SECURITY_IMPROVEMENTS_SUMMARY.md) - сводка по безопасности

---

## 🤝 Вклад в проект

Мы приветствуем вклад в проект! Пожалуйста:

1. Форкните репозиторий
2. Создайте feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit изменения (`git commit -m 'Add some AmazingFeature'`)
4. Push в branch (`git push origin feature/AmazingFeature`)
5. Откройте Pull Request

### Правила:

- Следуйте PEP 8 стандартам
- Добавляйте тесты для новых функций
- Обновляйте документацию
- Используйте conventional commits

---

## 📄 Лицензия

Distributed under the MIT License. See `LICENSE` for more information.

---

## 👥 Авторы

- **Alex** - *Initial work*

---

## 🙏 Благодарности

- [Google Gemini](https://ai.google.dev/) - AI модель
- [FastAPI](https://fastapi.tiangolo.com/) - web framework
- [aiogram](https://docs.aiogram.dev/) - Telegram bot framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - ORM

---

## 📞 Контакты

Telegram Bot: [@AlterMaria_bot](https://t.me/AlterMaria_bot)

Project Link: [https://github.com/yourusername/evolveai](https://github.com/yourusername/evolveai)

---

<div align="center">
  <strong>Сделано с ❤️ используя Python и Google Gemini AI</strong>
</div>
