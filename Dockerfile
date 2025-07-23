# --- Этап 1: Установка зависимостей ---
FROM python:3.10-slim as builder

WORKDIR /app

# Устанавливаем переменные окружения для pip
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Копируем файл с зависимостями и устанавливаем их
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# --- Этап 2: Сборка финального образа ---
FROM python:3.10-slim

WORKDIR /app

# Копируем зависимости из builder'а
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache /wheels/*

# Копируем исходный код приложения
COPY . .

# Открываем порт, на котором будет работать FastAPI
EXPOSE 8000

# Команда для запуска FastAPI-сервера
# Мы используем массив, чтобы избежать проблем с обработкой сигналов
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]