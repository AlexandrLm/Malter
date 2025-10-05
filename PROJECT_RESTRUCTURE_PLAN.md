# 📁 ПЛАН РЕСТРУКТУРИЗАЦИИ ПРОЕКТА EVOLVEAI

**Дата:** 6 октября 2025  
**Статус:** Proposal (требует согласования)

---

## 🔍 ТЕКУЩАЯ ПРОБЛЕМА

### Что не так сейчас:

```
C:\Users\alex\Desktop\Malter\
├── 📄 main.py                    # ❌ В корне (должен быть в app/)
├── 📄 config.py                  # ❌ В корне
├── 📄 prompts.py                 # ❌ В корне (должен быть в app/prompts/)
├── 📄 personality_prompts.py     # ❌ В корне
├── 📄 broadcast.py               # ❌ В корне (должен быть в app/cli/)
├── 📄 error.txt                  # ❌ 222KB логов в корне!
├── 📄 improvement_plan.md        # ❌ 11 Markdown файлов в корне!
├── 📄 ANALYTICS_GUIDE.md
├── 📄 APPLY_SECURITY_FIXES.md
├── ... (еще 8 .md файлов)
├── 📁 prompts/                   # ❌ ПУСТАЯ директория
├── 📁 server/                    # ✅ Хорошо
├── 📁 bot/                       # ✅ Хорошо
├── 📁 utils/                     # ✅ Хорошо
├── 📁 scripts/                   # ✅ Хорошо
└── 📁 __pycache__/               # ❌ В корне (должен быть в .gitignore)
```

**Проблемы:**
1. ❌ Слишком много файлов в корне (30+ файлов)
2. ❌ Документация разбросана по корню (11 .md файлов)
3. ❌ Python файлы (prompts.py, config.py) в корне
4. ❌ Пустая папка `prompts/`
5. ❌ Логи (error.txt 222KB) в корне, не в .gitignore
6. ❌ `__pycache__` в корне

---

## ✅ ПРЕДЛАГАЕМАЯ СТРУКТУРА (Best Practice)

### Вариант 1: Standard Python Project (Рекомендуется)

```
evolveai/
├── 📁 .github/                          # CI/CD workflows
│   └── workflows/
│       ├── tests.yml
│       └── deploy.yml
│
├── 📁 docs/                             # 📚 ВСЯ ДОКУМЕНТАЦИЯ
│   ├── README.md -> ../README.md        # Symlink на главный README
│   ├── guides/                          # Руководства
│   │   ├── ANALYTICS_GUIDE.md
│   │   ├── SCALABILITY_IMPROVEMENTS.md
│   │   ├── BACKUP_STRATEGY.md
│   │   └── PROMPT_EVALUATION.md
│   ├── security/                        # Безопасность
│   │   ├── PRIVACY_AND_SECURITY_AUDIT.md
│   │   ├── SECURITY_FIXES.md
│   │   ├── APPLY_SECURITY_FIXES.md
│   │   └── SECURITY_IMPROVEMENTS_SUMMARY.md
│   ├── planning/                        # Планирование
│   │   ├── improvement_plan.md
│   │   ├── DASHBOARD_SPECIFICATION.md
│   │   └── PROJECT_RESTRUCTURE_PLAN.md
│   └── changelog/                       # История изменений
│       ├── CHANGELOG_SCALABILITY.md
│       └── FINAL_PROJECT_STATUS.md
│
├── 📁 src/                              # 🐍 ВЕСЬ КОД ПРИЛОЖЕНИЯ
│   ├── __init__.py
│   ├── main.py                          # FastAPI app (перемещен из корня)
│   ├── config.py                        # Конфигурация (перемещен из корня)
│   │
│   ├── 📁 api/                          # API endpoints
│   │   ├── __init__.py
│   │   ├── routes.py                    # Объединенные routes
│   │   ├── auth.py                      # Auth endpoints
│   │   ├── chat.py                      # Chat endpoints
│   │   ├── admin.py                     # Admin endpoints
│   │   └── analytics.py                 # Analytics endpoints
│   │
│   ├── 📁 core/                         # Базовая функциональность
│   │   ├── __init__.py
│   │   ├── database.py                  # server/database.py → здесь
│   │   ├── models.py                    # server/models.py → здесь
│   │   ├── schemas.py                   # server/schemas.py → здесь
│   │   └── dependencies.py              # FastAPI dependencies
│   │
│   ├── 📁 services/                     # Бизнес-логика
│   │   ├── __init__.py
│   │   ├── ai_service.py                # server/ai.py → здесь
│   │   ├── analytics_service.py         # server/analytics.py → здесь
│   │   ├── summarizer_service.py        # server/summarizer.py → здесь
│   │   ├── subscription_service.py      # server/subscription_service.py
│   │   ├── tts_service.py               # server/tts.py → здесь
│   │   └── scheduler_service.py         # server/scheduler.py → здесь
│   │
│   ├── 📁 prompts/                      # 📝 ПРОМПТЫ
│   │   ├── __init__.py
│   │   ├── system_prompts.py            # prompts.py → здесь
│   │   ├── personality_prompts.py       # перемещен из корня
│   │   └── relationship_config.py       # server/relationship_config.py → здесь
│   │
│   ├── 📁 bot/                          # 🤖 Telegram Bot
│   │   ├── __init__.py
│   │   ├── handlers/
│   │   │   ├── __init__.py
│   │   │   ├── message_handler.py
│   │   │   ├── command_handler.py
│   │   │   └── callback_handler.py
│   │   ├── keyboards.py
│   │   └── filters.py
│   │
│   └── 📁 utils/                        # 🔧 Утилиты
│       ├── __init__.py
│       ├── cache.py
│       ├── circuit_breaker.py
│       ├── db_monitoring.py
│       ├── encryption.py
│       └── retry_configs.py
│
├── 📁 tests/                            # ✅ ТЕСТЫ
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_api/
│   │   ├── test_auth.py
│   │   ├── test_chat.py
│   │   └── test_analytics.py
│   ├── test_services/
│   │   ├── test_ai_service.py
│   │   └── test_analytics_service.py
│   └── test_utils/
│       ├── test_cache.py
│       └── test_circuit_breaker.py
│
├── 📁 scripts/                          # 🛠️ Утилиты (перемещены)
│   ├── backup.sh
│   ├── restore.sh
│   └── broadcast.py                     # broadcast.py → здесь
│
├── 📁 alembic/                          # 🗄️ Миграции БД
│   └── versions/
│
├── 📁 logs/                             # 📋 ЛОГИ (НОВАЯ ПАПКА)
│   ├── .gitkeep
│   └── error.log                        # error.txt → здесь (переименован)
│
├── 📁 deploy/                           # 🚀 Deployment (НОВАЯ ПАПКА)
│   ├── docker/
│   │   ├── Dockerfile
│   │   ├── Dockerfile.migration
│   │   └── docker-compose.yml
│   ├── k8s/                             # Kubernetes (опционально)
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   └── nginx/                           # Nginx config (опционально)
│       └── nginx.conf
│
├── 📄 .env                              # ✅ Остается в корне
├── 📄 .env.example                      # ✅ Остается в корне
├── 📄 .gitignore                        # ✅ Остается в корне
├── 📄 .dockerignore                     # ✅ Остается в корне
├── 📄 alembic.ini                       # ✅ Остается в корне
├── 📄 requirements.txt                  # ✅ Остается в корне
├── 📄 README.md                         # ✅ Остается в корне
├── 📄 LICENSE                           # ✅ Добавить
├── 📄 setup.py                          # ✅ Добавить (для установки)
└── 📄 pyproject.toml                    # ✅ Добавить (modern Python)
```

### Преимущества:
✅ Чистый корень (только конфигурационные файлы)  
✅ Вся документация в `docs/`  
✅ Весь код в `src/`  
✅ Логи в отдельной папке `logs/` (в .gitignore)  
✅ Deployment конфиги в `deploy/`  
✅ Соответствует PEP 8 и modern Python standards  

---

### Вариант 2: FastAPI Microservices (Если планируется масштабирование)

```
evolveai/
├── 📁 docs/                 # Документация
├── 📁 services/             # Микросервисы
│   ├── api-gateway/         # FastAPI Gateway
│   │   ├── src/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── analytics/           # Analytics Service
│   │   ├── src/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── bot/                 # Telegram Bot Service
│   │   ├── src/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── ai/                  # AI Processing Service
│       ├── src/
│       ├── Dockerfile
│       └── requirements.txt
├── 📁 shared/               # Общие утилиты
│   ├── database.py
│   ├── models.py
│   └── utils.py
└── docker-compose.yml       # Orchestration
```

**Преимущество:** Легко масштабировать отдельные сервисы  
**Недостаток:** Сложнее для начала, overkill для текущего размера

---

## 🚀 ПЛАН МИГРАЦИИ (Вариант 1)

### Фаза 1: Создание структуры папок (5 минут)

```bash
# Создать новые папки
mkdir -p docs/{guides,security,planning,changelog}
mkdir -p src/{api,core,services,prompts,bot,utils}
mkdir -p tests/{test_api,test_services,test_utils}
mkdir -p logs
mkdir -p deploy/docker
```

### Фаза 2: Перемещение документации (5 минут)

```bash
# Переместить документы в docs/
mv ANALYTICS_GUIDE.md docs/guides/
mv SCALABILITY_IMPROVEMENTS.md docs/guides/
mv BACKUP_STRATEGY.md docs/guides/
mv PROMPT_EVALUATION.md docs/guides/

mv PRIVACY_AND_SECURITY_AUDIT.md docs/security/
mv SECURITY_FIXES.md docs/security/
mv APPLY_SECURITY_FIXES.md docs/security/
mv SECURITY_IMPROVEMENTS_SUMMARY.md docs/security/

mv improvement_plan.md docs/planning/
mv DASHBOARD_SPECIFICATION.md docs/planning/

mv CHANGELOG_SCALABILITY.md docs/changelog/
mv FINAL_PROJECT_STATUS.md docs/changelog/

# Переместить логи
mv error.txt logs/error.log
```

### Фаза 3: Перемещение кода (15 минут, требует обновления импортов)

```bash
# Переместить main файлы
mv main.py src/main.py
mv config.py src/config.py
mv prompts.py src/prompts/system_prompts.py
mv personality_prompts.py src/prompts/personality_prompts.py

# Переместить server/ в src/
mv server/database.py src/core/database.py
mv server/models.py src/core/models.py
mv server/schemas.py src/core/schemas.py

mv server/ai.py src/services/ai_service.py
mv server/analytics.py src/services/analytics_service.py
mv server/summarizer.py src/services/summarizer_service.py
mv server/subscription_service.py src/services/subscription_service.py
mv server/tts.py src/services/tts_service.py
mv server/scheduler.py src/services/scheduler_service.py
mv server/relationship_config.py src/prompts/relationship_config.py

# Переместить utils/ в src/utils/
mv utils/* src/utils/

# Переместить bot/ в src/bot/
mv bot/* src/bot/

# Переместить broadcast.py в scripts/
mv broadcast.py scripts/broadcast.py

# Переместить Docker файлы
mv Dockerfile deploy/docker/
mv Dockerfile.migration deploy/docker/
mv docker-compose.yml deploy/docker/
```

### Фаза 4: Обновление импортов (30 минут)

**Критично:** Все импорты нужно обновить!

```python
# Было:
from server.database import get_profile
from server.ai import call_gemini_api
from utils.cache import cached

# Стало:
from src.core.database import get_profile
from src.services.ai_service import call_gemini_api
from src.utils.cache import cached
```

**Автоматизация:**
```bash
# Использовать find & replace в VSCode
# Или написать скрипт для замены импортов
```

### Фаза 5: Обновление конфигурации (10 минут)

```python
# pyproject.toml (создать)
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "evolveai"
version = "2.0.0"
description = "AI Chatbot with evolving relationships"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "fastapi==0.116.1",
    "uvicorn[standard]==0.35.0",
    # ... из requirements.txt
]

[project.scripts]
evolveai = "src.main:main"
```

```python
# setup.py (создать)
from setuptools import setup, find_packages

setup(
    name="evolveai",
    version="2.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
)
```

```gitignore
# .gitignore (обновить)
# Логи
logs/
*.log
error.txt

# Cache
__pycache__/
*.pyc
*.pyo
.pytest_cache/

# Environment
.env
.venv/
venv/

# IDE
.vscode/
.idea/
```

### Фаза 6: Обновление README (5 минут)

```markdown
# README.md (обновить секцию установки)

## 🚀 Установка

```bash
# Клонировать репозиторий
git clone https://github.com/yourusername/evolveai.git
cd evolveai

# Создать виртуальное окружение
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Установить зависимости
pip install -r requirements.txt

# Настроить .env
cp .env.example .env
# Заполнить переменные

# Применить миграции
alembic upgrade head

# Запустить
python -m src.main
```

## 📁 Структура проекта

```
evolveai/
├── docs/           # Документация
├── src/            # Исходный код
├── tests/          # Тесты
├── scripts/        # Утилиты
└── deploy/         # Deployment
```

См. подробнее: [docs/planning/PROJECT_RESTRUCTURE_PLAN.md](docs/planning/PROJECT_RESTRUCTURE_PLAN.md)
```

---

## ⚠️ РИСКИ И ПРЕДОСТОРОЖНОСТИ

### Высокий риск:
1. **Сломанные импорты** - все импорты нужно обновить
2. **Alembic миграции** - могут сломаться пути
3. **Docker builds** - нужно обновить Dockerfile пути
4. **Git history** - `git mv` сохранит историю, простое `mv` - нет

### Минимизация рисков:
```bash
# ✅ ОБЯЗАТЕЛЬНО перед началом:
1. git commit -a -m "Checkpoint before restructure"
2. git tag "pre-restructure"
3. Создать ветку: git checkout -b restructure
4. Работать в ветке, тестировать, потом merge
```

---

## ✅ CHECKLIST ДЛЯ МИГРАЦИИ

### Подготовка:
- [ ] Закоммитить все изменения
- [ ] Создать тег `pre-restructure`
- [ ] Создать ветку `restructure`
- [ ] Backup базы данных

### Миграция:
- [ ] Создать структуру папок
- [ ] Переместить документацию → `docs/`
- [ ] Переместить логи → `logs/`
- [ ] Переместить код → `src/`
- [ ] Переместить Docker → `deploy/`
- [ ] Удалить пустую папку `prompts/`
- [ ] Удалить `__pycache__/` из корня

### Обновление:
- [ ] Обновить все импорты в коде
- [ ] Обновить `pyproject.toml`
- [ ] Обновить `.gitignore`
- [ ] Обновить `README.md`
- [ ] Обновить `Dockerfile` пути
- [ ] Обновить `docker-compose.yml`
- [ ] Обновить `alembic.ini`

### Тестирование:
- [ ] `python -m src.main` работает
- [ ] Все импорты разрешаются
- [ ] Alembic миграции работают
- [ ] Docker build успешен
- [ ] Тесты проходят (если есть)

### Финализация:
- [ ] Commit: "Restructure project to src/ layout"
- [ ] Merge в main
- [ ] Обновить документацию
- [ ] Обновить CI/CD (если есть)

---

## 🤔 АЛЬТЕРНАТИВНЫЙ ПОДХОД: Постепенная миграция

Если не хочешь сразу все ломать, можно делать постепенно:

### Этап 1 (неделя 1): Документация
```bash
mkdir docs
mv *.md docs/  # Кроме README.md
```

### Этап 2 (неделя 2): Логи и очистка
```bash
mkdir logs
mv error.txt logs/error.log
rm -rf __pycache__
rm -rf prompts/  # если пустая
```

### Этап 3 (неделя 3): Создать src/ параллельно
```bash
mkdir src
# Копировать файлы в src/, но оставить старые
# Постепенно обновлять импорты
```

### Этап 4 (неделя 4): Удалить старые файлы
```bash
# Когда все импорты обновлены
rm main.py config.py prompts.py
```

---

## 💡 РЕКОМЕНДАЦИЯ

**Мое предложение:**
1. **Начать с документации** - минимальный риск, большая польза
2. **Переместить логи** - тоже безопасно
3. **Потом рефакторинг кода** - когда будет время

**Приоритет:**
1. 🟢 **Low risk, high value:** docs/ и logs/
2. 🟡 **Medium risk, high value:** src/ structure  
3. 🔴 **High risk, medium value:** Полная реструктуризация

---

## 📊 СРАВНЕНИЕ: До и После

| Метрика | До | После | Улучшение |
|---------|-----|--------|-----------|
| **Файлов в корне** | 30+ | 10-12 | ✅ 60% меньше |
| **Документы в корне** | 11 | 1 (README) | ✅ 90% меньше |
| **Навигация** | Хаотичная | Логичная | ✅ Намного лучше |
| **Onboarding новых разработчиков** | Сложно | Легко | ✅ 5x быстрее |
| **Масштабируемость** | Средняя | Высокая | ✅ Ready для роста |

---

## 🎯 СЛЕДУЮЩИЕ ШАГИ

**Вариант A (Быстрый старт):**
1. Сейчас: Переместить документацию в `docs/`
2. Потом: Переместить логи в `logs/`
3. Позже: Подумать о `src/` структуре

**Вариант B (Полная реструктуризация):**
1. Создать ветку `restructure`
2. Следовать плану миграции (1 час работы)
3. Тестировать → Merge

**Что выбираешь?**

---

**Дата создания:** 6 октября 2025  
**Автор:** Droid AI Assistant  
**Статус:** ✅ Proposal Ready
