# 🔒 Аудит безопасности и конфиденциальности проекта EvolveAI

> **Дата проведения:** Январь 2025  
> **Версия проекта:** Main branch  
> **Статус:** Детальный анализ завершен

---

## 📋 Executive Summary

Проведен комплексный анализ безопасности и конфиденциальности AI-бота на базе Telegram. Проект демонстрирует **хороший уровень зрелости** в вопросах безопасности, критические уязвимости уже исправлены. Обнаружено **15 зон для улучшения**, из которых **4 критические**, **6 высокого приоритета** и **5 среднего**.

### Ключевые находки:
✅ **Сильные стороны:**
- JWT-авторизация на критичных endpoints
- SQL Injection защита через параметризованные запросы и санитизацию
- Rate limiting на всех публичных API
- Circuit Breaker для Redis
- Secrets в .env (не в коде)
- RBAC через premium подписки
- Docker контейнеризация с непривилегированным пользователем

⚠️ **Требует внимания:**
- Отсутствие шифрования чувствительных данных в БД
- Логирование может содержать PII
- Нет HTTPS для API (только внутри Docker сети)
- Отсутствие rate limiting на WebSocket соединениях
- Недостаточная валидация платежных данных

---

## 🎯 Классификация уязвимостей

### Критические (CVSS 9.0-10.0) 🔴

#### 1. Отсутствие шифрования чувствительных данных в БД
**Описание:** Персональные данные пользователей (имя, дата рождения, история сообщений) хранятся в PostgreSQL в открытом виде.

**Файлы:** `server/models.py` (UserProfile, ChatHistory)

**Риск:**
- При утечке дампа БД все данные будут скомпрометированы
- Нарушение GDPR (Article 32 - Security of processing)
- Возможность атаки через SQL Injection (несмотря на защиту)

**Доказательство:**
```python
# server/models.py:40-60
class UserProfile(Base):
    __tablename__ = 'userprofiles'
    user_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=True)  # ❌ Открытый текст
    birth_date: Mapped[date] = mapped_column(nullable=True)        # ❌ Чувствительные данные
```

**Решение:**
```python
from cryptography.fernet import Fernet
import os

# 1. Добавить в config.py
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")  # Generate: Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY.encode())

# 2. Создать helper функции в server/encryption.py
def encrypt_field(value: str) -> str:
    """Шифрует чувствительные поля перед сохранением в БД."""
    if not value:
        return None
    return cipher_suite.encrypt(value.encode()).decode()

def decrypt_field(encrypted_value: str) -> str:
    """Расшифровывает поля при чтении из БД."""
    if not encrypted_value:
        return None
    return cipher_suite.decrypt(encrypted_value.encode()).decode()

# 3. Обновить модели
class UserProfile(Base):
    __tablename__ = 'userprofiles'
    user_id: Mapped[int] = mapped_column(primary_key=True)
    _name: Mapped[str] = mapped_column("name", String(200), nullable=True)  # Увеличенный размер для зашифрованных данных
    _birth_date: Mapped[str] = mapped_column("birth_date", String(200), nullable=True)
    
    @property
    def name(self) -> str:
        return decrypt_field(self._name)
    
    @name.setter
    def name(self, value: str):
        self._name = encrypt_field(value)
    
    @property
    def birth_date(self) -> date:
        decrypted = decrypt_field(self._birth_date)
        return date.fromisoformat(decrypted) if decrypted else None
    
    @birth_date.setter
    def birth_date(self, value: date):
        self._birth_date = encrypt_field(value.isoformat())
```

**Приоритет:** 🔴 Критический  
**Время на исправление:** 4-6 часов  
**Сложность:** Средняя (требует миграции БД)

---

#### 2. Отсутствие защиты от брутфорса платежной системы
**Описание:** Endpoint `/buy_premium` и обработчик платежей не имеют достаточной защиты от автоматизированных атак на платежную систему.

**Файлы:** 
- `bot/handlers/payments.py:23-53`
- `main.py` (отсутствует `/payment` endpoint rate limiting)

**Риск:**
- Финансовое мошенничество через генерацию множества инвойсов
- DoS атака на платежную систему Telegram
- Истощение лимитов PAYMENT_PROVIDER_TOKEN

**Доказательство:**
```python
# bot/handlers/payments.py:23
@router.message(Command("buy_premium"))
async def buy_premium_command(message: types.Message):
    # ❌ Нет rate limiting на создание инвойсов
    await callback.bot.send_invoice(...)
```

**Решение:**
```python
# 1. Добавить FSM для отслеживания состояния оплаты
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

class PaymentStates(StatesGroup):
    choosing_plan = State()
    pending_payment = State()

# 2. Добавить rate limiting на уровне пользователя
from collections import defaultdict
from datetime import datetime, timedelta

payment_attempts = defaultdict(list)  # user_id: [timestamp1, timestamp2, ...]
MAX_PAYMENT_ATTEMPTS = 3  # Максимум 3 попытки в час

@router.message(Command("buy_premium"))
async def buy_premium_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    now = datetime.now()
    
    # Очистка старых попыток
    payment_attempts[user_id] = [
        t for t in payment_attempts[user_id]
        if now - t < timedelta(hours=1)
    ]
    
    # Проверка лимита
    if len(payment_attempts[user_id]) >= MAX_PAYMENT_ATTEMPTS:
        await message.answer(
            "⚠️ Превышен лимит попыток оплаты. Попробуйте через час."
        )
        return
    
    payment_attempts[user_id].append(now)
    await state.set_state(PaymentStates.choosing_plan)
    # ... остальной код

# 3. Добавить валидацию payload в pre_checkout_query_handler
@router.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: PreCheckoutQuery):
    payload = pre_checkout_query.invoice_payload
    
    # Валидация формата payload
    try:
        parts = payload.split("_")
        if len(parts) != 3 or parts[0] != "premium":
            raise ValueError("Invalid payload format")
        
        subscription_type = parts[1]
        user_id_from_payload = int(parts[2])
        
        # Проверка соответствия user_id
        if user_id_from_payload != pre_checkout_query.from_user.id:
            logger.warning(f"Payload user_id mismatch: {user_id_from_payload} != {pre_checkout_query.from_user.id}")
            await pre_checkout_query.answer(ok=False, error_message="Неверные данные платежа")
            return
        
        # Проверка валидности типа подписки
        valid_types = ["1_month", "3_months", "6_months", "12_months"]
        if subscription_type not in valid_types:
            raise ValueError(f"Invalid subscription type: {subscription_type}")
            
    except (ValueError, IndexError) as e:
        logger.error(f"Invalid payment payload: {payload}, error: {e}")
        await pre_checkout_query.answer(ok=False, error_message="Неверный формат платежа")
        return
    
    await pre_checkout_query.answer(ok=True)

# 4. Добавить логирование всех платежных операций
@router.message(F.successful_payment)
async def successful_payment_handler(message: types.Message, client: httpx.AsyncClient):
    payment = message.successful_payment
    user_id = message.from_user.id
    
    # AUDIT LOG: Критично для расследований мошенничества
    logger.info(
        f"PAYMENT_SUCCESS: user_id={user_id}, "
        f"amount={payment.total_amount}, "
        f"currency={payment.currency}, "
        f"charge_id={payment.telegram_payment_charge_id}, "
        f"payload={payment.invoice_payload}, "
        f"provider_charge_id={payment.provider_payment_charge_id}"
    )
    # ... остальной код
```

**Приоритет:** 🔴 Критический  
**Время на исправление:** 3-4 часа  
**Сложность:** Средняя

---

#### 3. Логирование может содержать PII (Personally Identifiable Information)
**Описание:** Множество мест в коде логируют пользовательские данные без маскировки, что нарушает GDPR и может привести к утечке через логи.

**Файлы:** 
- `server/ai.py` (логирование сообщений)
- `server/database.py` (логирование запросов с PII)
- `bot/handlers/messages.py`

**Риск:**
- Нарушение GDPR Article 5 (Data minimisation)
- Утечка PII через систему логирования
- Неконтролируемое хранение логов с чувствительными данными

**Доказательство:**
```python
# Множество мест в коде
logging.debug(f"Сгенерирован финальный ответ для пользователя {user_id}: '{final_response}'")
# ❌ final_response может содержать персональные данные пользователя

logging.debug(f"Сохранение нового факта для user_id {user_id}")
# ❌ Факт может быть чувствительным (медицинские данные, финансы)
```

**Решение:**
```python
# 1. Создать утилиту для маскировки PII в utils/logging_helpers.py
import re
from typing import Any

def mask_pii(text: str, mask_char: str = "*") -> str:
    """
    Маскирует PII в строке для безопасного логирования.
    
    Маскирует:
    - Email адреса
    - Номера телефонов
    - Даты рождения
    - Имена (простая эвристика)
    """
    if not text:
        return text
    
    # Email
    text = re.sub(r'\b[\w.-]+@[\w.-]+\.\w+\b', '[EMAIL]', text)
    
    # Телефоны (российский формат)
    text = re.sub(r'\+?[78][\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}', '[PHONE]', text)
    
    # Даты рождения (DD.MM.YYYY или YYYY-MM-DD)
    text = re.sub(r'\b\d{2}\.\d{2}\.\d{4}\b|\b\d{4}-\d{2}-\d{2}\b', '[DATE]', text)
    
    return text

def safe_log_user_message(user_id: int, message: str, max_length: int = 50) -> str:
    """
    Безопасное логирование пользовательского сообщения.
    
    Args:
        user_id: ID пользователя
        message: Исходное сообщение
        max_length: Максимальная длина для логирования
    
    Returns:
        Безопасная строка для логирования
    """
    masked = mask_pii(message)
    truncated = masked[:max_length] + "..." if len(masked) > max_length else masked
    return f"user_{user_id}: {truncated}"

# 2. Обновить все места логирования
# В server/ai.py
from utils.logging_helpers import safe_log_user_message

# БЫЛО:
# logging.debug(f"Сгенерирован финальный ответ для пользователя {user_id}: '{final_response}'")

# СТАЛО:
logging.debug(f"Ответ сгенерирован для user_{user_id}, длина: {len(final_response)} символов")

# В server/database.py
# БЫЛО:
# logging.debug(f"Сохранение нового факта для user_id {user_id}")

# СТАЛО:
logging.debug(f"Сохранение факта для user_{user_id}, категория: {category}")

# 3. Настроить ротацию логов в docker-compose.yml (уже есть)
# logging:
#   driver: "json-file"
#   options:
#     max-size: "10m"
#     max-file: "3"

# 4. Добавить в .gitignore логи с PII
# logs/
# *.log

# 5. Настроить structlog для структурированного логирования
import structlog

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()  # JSON для парсинга без PII
    ],
)

logger = structlog.get_logger()

# Использование:
logger.info("user_message_received", user_id=user_id, message_length=len(message))
# Вместо logger.info(f"Received: {message}")
```

**Приоритет:** 🔴 Критический (GDPR compliance)  
**Время на исправление:** 6-8 часов  
**Сложность:** Средняя-Высокая

---

#### 4. Отсутствие HTTPS для API endpoints
**Описание:** API FastAPI доступен только через HTTP внутри Docker сети, но нет упоминания HTTPS/TLS для external access.

**Файлы:** `docker-compose.yml`, `main.py`

**Риск:**
- Man-in-the-middle атаки
- Перехват JWT токенов
- Перехват платежных данных

**Доказательство:**
```yaml
# docker-compose.yml:20
api:
  ports:
    - "8000:8000"  # ❌ Прямой доступ без TLS
```

**Решение:**
```yaml
# 1. Добавить nginx reverse proxy с TLS в docker-compose.yml
services:
  nginx:
    image: nginx:alpine
    restart: always
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - api
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  api:
    # ... existing config
    ports:
      - "8000"  # ✅ Убираем прямой external доступ
    expose:
      - "8000"

# 2. Создать nginx/nginx.conf
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Rate limiting на nginx уровне
        limit_req zone=api burst=10 nodelay;
    }
}

http {
    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/m;
}

# 3. Генерация self-signed сертификата для development
# openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
#   -keyout nginx/ssl/key.pem -out nginx/ssl/cert.pem

# 4. Для production использовать Let's Encrypt
# certbot certonly --webroot -w /var/www/html -d your-domain.com
```

**Приоритет:** 🔴 Критический (для production)  
**Время на исправление:** 2-3 часа  
**Сложность:** Низкая-Средняя

---

### Высокий приоритет (CVSS 7.0-8.9) 🟠

#### 5. Недостаточная валидация image_data
**Описание:** Изображения от пользователей декодируются без достаточной валидации размера и формата, что может привести к DoS или RCE через malicious images.

**Файлы:** `server/ai.py:460-510`

**Риск:**
- DoS через загрузку огромных изображений
- Memory exhaustion
- Возможная RCE через уязвимости в Pillow

**Доказательство:**
```python
# server/ai.py:485
async def process_image_data(image_data: str | None, user_id: int) -> genai_types.Part | None:
    if not image_data:
        return None
    try:
        image_bytes = base64.b64decode(image_data)  # ❌ Нет проверки размера
        image = Image.open(io.BytesIO(image_bytes))  # ❌ Может быть ZIP bomb
```

**Решение:**
```python
from PIL import Image, UnidentifiedImageError
import io
import base64
from config import MAX_IMAGE_SIZE_MB

MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024  # 10MB
MAX_IMAGE_DIMENSIONS = (4096, 4096)  # Максимальные размеры
ALLOWED_FORMATS = {'JPEG', 'PNG', 'GIF', 'WEBP'}

async def process_image_data(image_data: str | None, user_id: int) -> genai_types.Part | None:
    if not image_data:
        return None
    
    try:
        # 1. Проверка длины base64 ПЕРЕД декодированием
        if len(image_data) > MAX_IMAGE_SIZE_BYTES * 1.37:  # base64 overhead ~37%
            logging.warning(f"Image too large for user {user_id}: {len(image_data)} bytes (base64)")
            raise ValueError(f"Изображение слишком большое. Максимум {MAX_IMAGE_SIZE_MB}MB")
        
        # 2. Декодирование с обработкой ошибок
        try:
            image_bytes = base64.b64decode(image_data, validate=True)
        except Exception as e:
            logging.warning(f"Invalid base64 image from user {user_id}: {e}")
            raise ValueError("Неверный формат изображения")
        
        # 3. Проверка размера после декодирования
        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            logging.warning(f"Decoded image too large for user {user_id}: {len(image_bytes)} bytes")
            raise ValueError(f"Изображение слишком большое. Максимум {MAX_IMAGE_SIZE_MB}MB")
        
        # 4. Безопасное открытие изображения с защитой от ZIP bombs
        image_stream = io.BytesIO(image_bytes)
        try:
            image = Image.open(image_stream)
            
            # 5. Проверка формата
            if image.format not in ALLOWED_FORMATS:
                logging.warning(f"Unsupported image format from user {user_id}: {image.format}")
                raise ValueError(f"Неподдерживаемый формат. Разрешены: {', '.join(ALLOWED_FORMATS)}")
            
            # 6. Проверка размеров для защиты от decompression bombs
            if image.width > MAX_IMAGE_DIMENSIONS[0] or image.height > MAX_IMAGE_DIMENSIONS[1]:
                logging.warning(f"Image dimensions too large for user {user_id}: {image.width}x{image.height}")
                raise ValueError(f"Изображение слишком большое. Максимум {MAX_IMAGE_DIMENSIONS[0]}x{MAX_IMAGE_DIMENSIONS[1]}")
            
            # 7. Проверка на decompression bomb (Pillow защита)
            try:
                image.verify()  # Верифицирует целостность
                image_stream.seek(0)  # Reset после verify
                image = Image.open(image_stream)  # Reopen после verify
            except Exception as e:
                logging.warning(f"Image verification failed for user {user_id}: {e}")
                raise ValueError("Поврежденное изображение")
            
            # 8. Конвертация в RGB и resize если нужно (оптимизация)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 9. Resize если слишком большое (сохраняем aspect ratio)
            if image.width > 2048 or image.height > 2048:
                image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                logging.debug(f"Image resized for user {user_id} to {image.width}x{image.height}")
            
            # 10. Конвертация обратно в bytes для API
            output_stream = io.BytesIO()
            image.save(output_stream, format='JPEG', quality=85)
            optimized_bytes = output_stream.getvalue()
            
            logging.debug(f"Image processed for user {user_id}: {len(image_bytes)} -> {len(optimized_bytes)} bytes")
            
            return genai_types.Part(
                inline_data=genai_types.Blob(
                    mime_type='image/jpeg',
                    data=optimized_bytes
                )
            )
            
        except UnidentifiedImageError:
            logging.warning(f"Unidentifiable image from user {user_id}")
            raise ValueError("Не удалось распознать изображение")
        
    except ValueError as e:
        # User-friendly ошибки
        logging.info(f"Image validation failed for user {user_id}: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error processing image for user {user_id}: {e}", exc_info=True)
        raise ValueError("Ошибка обработки изображения")

# 11. Добавить в .env.example лимиты
# MAX_IMAGE_SIZE_MB=10
# MAX_IMAGE_WIDTH=4096
# MAX_IMAGE_HEIGHT=4096
```

**Приоритет:** 🟠 Высокий  
**Время на исправление:** 2-3 часа  
**Сложность:** Средняя

---

#### 6. JWT_SECRET может быть слабым
**Описание:** Валидация JWT_SECRET только на наличие, но не на энтропию. Слабый secret может быть подобран брутфорсом.

**Файлы:** `config.py:132-134`

**Риск:**
- Брутфорс JWT токенов
- Подделка токенов с admin правами
- Несанкционированный доступ к API

**Доказательство:**
```python
# config.py:132
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise ValueError("JWT_SECRET обязателен для безопасности! Установите его в .env файле.")
# ❌ Нет проверки длины и энтропии
```

**Решение:**
```python
import os
import secrets
import hashlib

JWT_SECRET = os.getenv("JWT_SECRET")

# Валидация JWT_SECRET
if not JWT_SECRET:
    raise ValueError("JWT_SECRET обязателен для безопасности! Установите его в .env файле.")

# Проверка минимальной длины
if len(JWT_SECRET) < 32:
    raise ValueError(
        "JWT_SECRET слишком короткий! Минимум 32 символа.\n"
        f"Сгенерируйте безопасный ключ: openssl rand -hex 32"
    )

# Проверка энтропии (простая эвристика)
unique_chars = len(set(JWT_SECRET))
if unique_chars < 16:
    logging.warning(
        f"JWT_SECRET имеет низкую энтропию ({unique_chars} уникальных символов). "
        "Рекомендуется использовать криптографически стойкий ключ."
    )

# Рекомендация для генерации
def generate_secure_secret() -> str:
    """Генерирует криптографически стойкий JWT secret."""
    return secrets.token_hex(32)  # 64 hex символа = 256 бит

# Добавить в README.md инструкцию
"""
## Генерация JWT_SECRET

Для production окружения ОБЯЗАТЕЛЬНО сгенерируйте новый JWT_SECRET:

```bash
# Linux/macOS
openssl rand -hex 32

# Python
python -c "import secrets; print(secrets.token_hex(32))"

# PowerShell
[System.Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Minimum 0 -Maximum 256 }))
```

⚠️ НИКОГДА не используйте дефолтный ключ из примера!
"""
```

**Приоритет:** 🟠 Высокий  
**Время на исправление:** 30 минут  
**Сложность:** Низкая

---

#### 7. Отсутствие CSRF защиты на API endpoints
**Описание:** FastAPI endpoints не имеют CSRF токенов, что потенциально позволяет CSRF атаки (хотя SameSite cookies и CORS помогают).

**Файлы:** `main.py`

**Риск:**
- CSRF атаки на критичные операции
- Несанкционированное изменение профиля
- Фишинг с автоматическими действиями

**Решение:**
```python
# 1. Добавить CORS middleware с правильными настройками
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.com"],  # ❌ НЕ "*"
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)

# 2. Для form submissions использовать Double Submit Cookie pattern
from fastapi import Cookie, Header, HTTPException
import secrets

def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)

async def verify_csrf_token(
    csrf_token_cookie: str = Cookie(None, alias="csrf_token"),
    csrf_token_header: str = Header(None, alias="X-CSRF-Token")
):
    if not csrf_token_cookie or not csrf_token_header:
        raise HTTPException(status_code=403, detail="CSRF token missing")
    
    if csrf_token_cookie != csrf_token_header:
        raise HTTPException(status_code=403, detail="CSRF token mismatch")
    
    return csrf_token_cookie

# 3. Использовать на критичных endpoints
@app.post("/profile")
@limiter.limit("20/minute")
async def create_or_update_profile_handler(
    request: Request,
    profile_update: ProfileUpdate,
    csrf_token: str = Depends(verify_csrf_token)  # ✅ CSRF защита
):
    await create_or_update_profile(profile_update.user_id, profile_update.data.dict())
    return {"message": "Профиль успешно обновлен"}

# 4. Endpoint для получения CSRF токена
@app.get("/csrf-token")
async def get_csrf_token(response: Response):
    token = generate_csrf_token()
    response.set_cookie(
        key="csrf_token",
        value=token,
        httponly=True,
        secure=True,  # Только HTTPS
        samesite="strict"
    )
    return {"csrf_token": token}
```

**Приоритет:** 🟠 Высокий (если API доступен через веб)  
**Время на исправление:** 1-2 часа  
**Сложность:** Низкая-Средняя

---

#### 8. Отсутствие аудита доступа к premium функциям
**Описание:** Нет логирования использования premium функций (TTS, unlimited messages), что затрудняет расследование мошенничества.

**Файлы:** `server/tts.py`, `server/database.py:check_message_limit`

**Риск:**
- Невозможность отследить злоупотребления
- Отсутствие форензики при инцидентах
- Нарушение compliance требований

**Решение:**
```python
# 1. Создать таблицу для аудита в server/models.py
class AuditLog(Base):
    __tablename__ = 'audit_logs'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource: Mapped[str] = mapped_column(String(200), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)  # IPv6 support
    user_agent: Mapped[str] = mapped_column(String(500), nullable=True)
    metadata: Mapped[dict] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_audit_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_action', 'action'),
    )

# 2. Создать функцию для логирования в server/database.py
async def log_audit_event(
    user_id: int,
    action: str,
    resource: str = None,
    ip_address: str = None,
    user_agent: str = None,
    metadata: dict = None
):
    """
    Логирует события аудита для compliance и расследований.
    
    Args:
        user_id: ID пользователя
        action: Тип действия (TTS_GENERATED, PREMIUM_ACTIVATED, MESSAGE_SENT)
        resource: Ресурс (endpoint, file)
        ip_address: IP адрес клиента
        user_agent: User-Agent клиента
        metadata: Дополнительные данные (без PII!)
    """
    try:
        async with async_session_factory() as session:
            audit_entry = AuditLog(
                user_id=user_id,
                action=action,
                resource=resource,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata=metadata
            )
            session.add(audit_entry)
            await session.commit()
    except Exception as e:
        # Не падаем если аудит не записался
        logging.error(f"Failed to log audit event: {e}", exc_info=True)

# 3. Использовать в критичных местах
# В server/tts.py
async def create_telegram_voice_message(text_to_speak: str, output_file_object: io.BytesIO, user_id: int) -> bool:
    if not TTS_CLIENT:
        logging.error("Клиент TTS не инициализирован.")
        return False
    
    try:
        response = await call_tts_api_with_retry(text_to_speak)
        
        # AUDIT LOG
        await log_audit_event(
            user_id=user_id,
            action="TTS_GENERATED",
            resource="gemini-2.5-flash-preview-tts",
            metadata={
                "text_length": len(text_to_speak),
                "audio_size_bytes": len(pcm_data) if pcm_data else 0,
                "usage_metadata": str(response.usage_metadata) if hasattr(response, 'usage_metadata') else None
            }
        )
        
        # ... остальной код
        return True
    except Exception as e:
        # AUDIT LOG для ошибок тоже
        await log_audit_event(
            user_id=user_id,
            action="TTS_FAILED",
            resource="gemini-2.5-flash-preview-tts",
            metadata={"error": str(e)}
        )
        return False

# В main.py для премиум активации
@app.post("/activate_premium")
async def activate_premium_handler(
    request: Request,
    activate_request: dict = Body(...),
    authenticated_user_id: int = Depends(verify_token)
):
    user_id = activate_request.get("user_id")
    duration_days = activate_request.get("duration_days", 30)
    charge_id = activate_request.get("charge_id")
    
    # AUDIT LOG
    await log_audit_event(
        user_id=user_id,
        action="PREMIUM_ACTIVATED",
        resource="/activate_premium",
        ip_address=get_remote_address(request),
        user_agent=request.headers.get("user-agent"),
        metadata={
            "duration_days": duration_days,
            "charge_id": charge_id,
            "authenticated_user_id": authenticated_user_id
        }
    )
    
    success = await activate_premium_subscription(user_id, duration_days, charge_id)
    # ... остальной код

# 4. Endpoint для админов для просмотра аудита
@app.get("/admin/audit")
@limiter.limit("10/minute")
async def get_audit_logs(
    request: Request,
    user_id: int = None,
    action: str = None,
    limit: int = 100,
    admin_user_id: int = Depends(verify_token)  # TODO: добавить проверку admin роли
):
    """Получить логи аудита (только для администраторов)."""
    # TODO: Проверить что admin_user_id имеет права администратора
    
    async with async_session_factory() as session:
        query = select(AuditLog)
        
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        if action:
            query = query.where(AuditLog.action == action)
        
        query = query.order_by(desc(AuditLog.timestamp)).limit(limit)
        
        result = await session.execute(query)
        logs = result.scalars().all()
        
        return {"logs": [log.__dict__ for log in logs]}
```

**Приоритет:** 🟠 Высокий  
**Время на исправление:** 3-4 часа  
**Сложность:** Средняя

---

#### 9. Возможность Rate Limit Bypass через разные IP
**Описание:** Rate limiting основан на IP адресе (`get_remote_address`), который легко обходится через прокси или VPN.

**Файлы:** `main.py:40-46`

**Риск:**
- Обход rate limiting
- DoS атаки
- Abuse премиум функций

**Решение:**
```python
# 1. Комбинированный rate limiting: IP + user_id
from slowapi import Limiter
from fastapi import Request

def get_combined_limiter_key(request: Request) -> str:
    """
    Возвращает комбинированный ключ для rate limiting.
    Использует как IP, так и user_id из JWT (если доступен).
    """
    ip = get_remote_address(request)
    
    # Попытка извлечь user_id из Authorization header
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"  # Приоритет user_id
        except Exception:
            pass  # Fallback к IP
    
    return f"ip:{ip}"

limiter = Limiter(key_func=get_combined_limiter_key)

# 2. Разные лимиты для авторизованных и неавторизованных
from slowapi.util import get_remote_address

@app.post("/chat")
@limiter.limit("30/minute;100/hour")  # Комбинированный лимит
async def chat_handler(
    request: Request,
    chat: ChatRequest,
    user_id: int = Depends(verify_token)
):
    # Дополнительная проверка на user-level лимит
    # Уже защищены через get_combined_limiter_key
    # ...

# 3. Динамический rate limiting на основе reputation
from collections import defaultdict
from datetime import datetime, timedelta

user_reputation = defaultdict(lambda: {"score": 100, "violations": []})

async def check_user_reputation(user_id: int, request: Request) -> bool:
    """
    Проверяет репутацию пользователя и динамически меняет лимиты.
    
    Returns:
        True если пользователь может продолжить, False если заблокирован
    """
    rep = user_reputation[user_id]
    now = datetime.now()
    
    # Очищаем старые нарушения (старше 24 часов)
    rep["violations"] = [
        v for v in rep["violations"]
        if now - v["timestamp"] < timedelta(hours=24)
    ]
    
    # Пересчитываем score
    rep["score"] = max(0, 100 - len(rep["violations"]) * 20)
    
    # Блокируем если score слишком низкий
    if rep["score"] < 20:
        await log_audit_event(
            user_id=user_id,
            action="USER_BLOCKED_LOW_REPUTATION",
            ip_address=get_remote_address(request),
            metadata={"score": rep["score"], "violations": len(rep["violations"])}
        )
        return False
    
    return True

def record_rate_limit_violation(user_id: int):
    """Записывает нарушение rate limit."""
    user_reputation[user_id]["violations"].append({
        "timestamp": datetime.now(),
        "type": "rate_limit_exceeded"
    })

# 4. Использовать в middleware
@app.middleware("http")
async def reputation_middleware(request: Request, call_next):
    # Извлекаем user_id из токена
    auth_header = request.headers.get("authorization", "")
    user_id = None
    
    if auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
            user_id = int(payload.get("sub"))
        except Exception:
            pass
    
    # Проверяем репутацию
    if user_id and not await check_user_reputation(user_id, request):
        return Response(
            content='{"detail":"Account temporarily blocked due to abuse"}',
            status_code=429,
            media_type="application/json"
        )
    
    response = await call_next(request)
    
    # Записываем нарушение если получили 429
    if response.status_code == 429 and user_id:
        record_rate_limit_violation(user_id)
    
    return response
```

**Приоритет:** 🟠 Высокий  
**Время на исправление:** 2-3 часа  
**Сложность:** Средняя

---

#### 10. Secrets в environment variables без rotation
**Описание:** Все секреты хранятся в .env файле без механизма ротации, что увеличивает риск при компрометации.

**Файлы:** `.env`, `config.py`

**Риск:**
- Длительное использование скомпрометированных секретов
- Невозможность быстрой ротации
- Нарушение best practices для production

**Решение:**
```python
# 1. Использовать Docker Secrets для production
# docker-compose.yml для production:
version: '3.8'
services:
  api:
    secrets:
      - jwt_secret
      - google_api_key
      - telegram_bot_token
      - postgres_password
    environment:
      - JWT_SECRET_FILE=/run/secrets/jwt_secret
      - GOOGLE_API_KEY_FILE=/run/secrets/google_api_key
      - TELEGRAM_BOT_TOKEN_FILE=/run/secrets/telegram_bot_token
      - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password

secrets:
  jwt_secret:
    external: true
  google_api_key:
    external: true
  telegram_bot_token:
    external: true
  postgres_password:
    external: true

# 2. Обновить config.py для поддержки файлов
import os

def get_secret(name: str, default: str = None) -> str:
    """
    Получает секрет из файла (_FILE suffix) или переменной окружения.
    Приоритет: файл > env variable > default
    """
    # Проверяем файл
    file_path = os.getenv(f"{name}_FILE")
    if file_path and os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return f.read().strip()
    
    # Fallback на env variable
    value = os.getenv(name)
    if value:
        return value
    
    if default is None:
        raise ValueError(f"{name} обязателен! Установите {name} или {name}_FILE")
    
    return default

# Использование:
JWT_SECRET = get_secret("JWT_SECRET")
GOOGLE_API_KEY = get_secret("GOOGLE_API_KEY")
TELEGRAM_BOT_TOKEN = get_secret("TELEGRAM_BOT_TOKEN")
POSTGRES_PASSWORD = get_secret("POSTGRES_PASSWORD")

# 3. Скрипт для ротации секретов (scripts/rotate_secrets.sh)
#!/bin/bash
# Ротация JWT_SECRET

set -e

echo "Generating new JWT secret..."
NEW_SECRET=$(openssl rand -hex 32)

echo "Creating Docker secret..."
echo "$NEW_SECRET" | docker secret create jwt_secret_v2 -

echo "Updating service..."
docker service update --secret-rm jwt_secret --secret-add source=jwt_secret_v2,target=jwt_secret evolveai_api

echo "Waiting for service to restart..."
sleep 10

echo "Removing old secret..."
docker secret rm jwt_secret_v1

echo "Secret rotation complete!"

# 4. Для AWS использовать AWS Secrets Manager
# pip install boto3

import boto3
from botocore.exceptions import ClientError

def get_aws_secret(secret_name: str, region: str = "us-east-1") -> str:
    """Получает секрет из AWS Secrets Manager."""
    client = boto3.client('secretsmanager', region_name=region)
    
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except ClientError as e:
        logging.error(f"Failed to retrieve secret {secret_name}: {e}")
        raise

# В config.py для production:
if os.getenv('ENVIRONMENT') == 'production':
    JWT_SECRET = get_aws_secret("evolveai/jwt_secret")
else:
    JWT_SECRET = get_secret("JWT_SECRET")
```

**Приоритет:** 🟠 Высокий (для production)  
**Время на исправление:** 4-6 часов  
**Сложность:** Средняя-Высокая

---

### Средний приоритет (CVSS 4.0-6.9) 🟡

#### 11. Отсутствие Content Security Policy (CSP) headers
**Описание:** API не возвращает security headers (CSP, X-Frame-Options, etc.), что повышает риск XSS атак.

**Файлы:** `main.py`

**Решение:**
```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # CSP для API (строгий)
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        
        return response

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["your-domain.com", "*.your-domain.com"]
)
```

**Приоритет:** 🟡 Средний  
**Время на исправление:** 30 минут  
**Сложность:** Низкая

---

#### 12. Недостаточное логирование неудачных попыток аутентификации
**Описание:** Неудачные попытки JWT аутентификации не логируются детально, что затрудняет обнаружение атак.

**Файлы:** `main.py:146-162`

**Решение:**
```python
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exception
        user_id: int = int(sub)
        if user_id is None:
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        # SECURITY LOG: Детальное логирование
        logging.warning(f"Expired JWT token from IP: {get_remote_address(request)}")
        raise credentials_exception
    except jwt.InvalidTokenError as e:
        logging.warning(f"Invalid JWT token from IP: {get_remote_address(request)}, error: {str(e)}")
        raise credentials_exception
    except JWTError as je:
        logging.error(f"JWT Error: {str(je)}, IP: {get_remote_address(request)}")
        raise credentials_exception
    return user_id
```

**Приоритет:** 🟡 Средний  
**Время на исправление:** 1 час  
**Сложность:** Низкая

---

#### 13. Отсутствие timeout на длительные операции AI
**Описание:** Генерация AI ответов может зависнуть без timeout, блокируя ресурсы.

**Файлы:** `server/ai.py`

**Решение:**
```python
import asyncio

async def generate_ai_response(...):
    try:
        # Timeout на всю генерацию (макс 3 минуты)
        return await asyncio.wait_for(
            _generate_ai_response_internal(...),
            timeout=180.0
        )
    except asyncio.TimeoutError:
        logging.error(f"AI generation timeout for user {user_id}")
        return {
            "text": "Извини, мне нужно слишком много времени на ответ. Попробуй переформулировать вопрос.",
            "image_base64": None
        }
```

**Приоритет:** 🟡 Средний  
**Время на исправление:** 1 час  
**Сложность:** Низкая

---

#### 14. Отсутствие input validation на webhook endpoints
**Описание:** Если добавятся webhook endpoints, нужна валидация подписи.

**Решение:**
```python
import hmac
import hashlib

def verify_telegram_webhook(request: Request, secret: str) -> bool:
    """Верифицирует Telegram webhook signature."""
    signature = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if not signature:
        return False
    return hmac.compare_digest(signature, secret)
```

**Приоритет:** 🟡 Средний (если webhooks добавятся)  
**Время на исправление:** 1 час  
**Сложность:** Низкая

---

#### 15. Отсутствие мониторинга аномальной активности
**Описание:** Нет системы детектирования аномалий (внезапный всплеск запросов, паттерны бота).

**Решение:**
```python
# Использовать Prometheus + Grafana + alerts
# Metrics уже собираются через starlette-prometheus

# Добавить custom metrics для аномалий
from prometheus_client import Counter, Histogram

ANOMALY_DETECTED = Counter('security_anomalies_total', 'Detected security anomalies', ['type'])

async def detect_anomalies(user_id: int, request_count: int, time_window: int):
    """Детектирует аномальную активность."""
    # Простая эвристика: больше 100 запросов в минуту
    if request_count > 100:
        ANOMALY_DETECTED.labels(type='high_request_rate').inc()
        logging.warning(f"Anomaly detected: user {user_id} made {request_count} requests in {time_window}s")
```

**Приоритет:** 🟡 Средний  
**Время на исправление:** 4-6 часов  
**Сложность:** Высокая

---

## 📊 Конфиденциальность данных (GDPR Compliance)

### Обработка персональных данных

#### Какие данные собираются:
1. **Идентификаторы:** Telegram user_id (уникальный идентификатор)
2. **Профиль:** имя, пол, дата рождения, город
3. **Контент:** история сообщений, голосовые сообщения, изображения
4. **Поведенческие данные:** уровень отношений, премиум статус, ежедневный счетчик сообщений
5. **Технические данные:** IP адреса (в логах), User-Agent

#### GDPR статус:

✅ **Соответствует:**
- Явное согласие через команду `/start`
- Право на удаление данных через `/delete_my_data`
- Минимизация данных (собирается только необходимое)
- Прозрачность (README описывает функционал)

⚠️ **Требует улучшения:**
- Нет Privacy Policy документа
- Отсутствие шифрования at-rest
- Логирование может содержать PII (см. пункт 3)
- Нет Data Processing Agreement для сторонних сервисов (Google AI)

#### Рекомендации:

1. **Создать Privacy Policy (PRIVACY.md)**
```markdown
# Политика конфиденциальности EvolveAI

## 1. Какие данные мы собираем
- Telegram user_id (для идентификации)
- Имя, пол, дата рождения (для персонализации)
- История сообщений (для контекста общения)
- Изображения (если отправлены пользователем)

## 2. Как мы используем данные
- Генерация персонализированных ответов
- Улучшение качества общения
- Аналитика использования (анонимно)

## 3. Как долго мы храним данные
- История сообщений: до удаления пользователем
- Профиль: до удаления аккаунта
- Резервные копии: 30 дней

## 4. Ваши права
- Просмотр данных: `/profile`
- Удаление данных: `/delete_my_data`
- Экспорт данных: [планируется]

## 5. Третьи стороны
- Google AI (Gemini) - обработка сообщений
- Telegram - платформа доставки

## 6. Безопасность
- Шифрование транспорта (TLS)
- Шифрование хранения [в разработке]
- Регулярные аудиты безопасности

## 7. Контакты
support@evolveai.example
```

2. **Добавить команду экспорта данных**
```python
@router.message(Command("export_my_data"))
async def export_user_data(message: types.Message, client: httpx.AsyncClient):
    """Экспорт всех данных пользователя (GDPR Article 20)."""
    user_id = message.from_user.id
    
    # Получаем все данные
    profile = await get_profile(user_id)
    history = await get_unsummarized_messages(user_id)
    memories = await get_all_long_term_memories(user_id)
    
    # Формируем JSON
    export_data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "profile": profile.to_dict() if profile else None,
        "chat_history": [msg.to_dict() for msg in history],
        "long_term_memory": [mem.to_dict() for mem in memories],
    }
    
    # Отправляем как файл
    import json
    file_content = json.dumps(export_data, indent=2, ensure_ascii=False)
    await message.answer_document(
        BufferedInputFile(
            file_content.encode('utf-8'),
            filename=f"evolveai_data_export_{user_id}.json"
        ),
        caption="📦 Экспорт ваших данных (GDPR)"
    )
```

3. **Data Retention Policy**
```python
# Автоматическое удаление неактивных аккаунтов через 2 года
async def cleanup_inactive_accounts():
    """Удаляет данные пользователей, неактивных более 2 лет."""
    threshold_date = datetime.now(timezone.utc) - timedelta(days=730)
    
    async with async_session_factory() as session:
        # Находим неактивных пользователей
        result = await session.execute(
            select(UserProfile).where(
                UserProfile.last_message_date < threshold_date
            )
        )
        inactive_users = result.scalars().all()
        
        for user in inactive_users:
            logging.info(f"Deleting inactive user {user.user_id} (last active: {user.last_message_date})")
            await delete_profile(user.user_id)
            await delete_chat_history(user.user_id)
            await delete_long_term_memory(user.user_id)
```

---

## 🔐 Рекомендации по развертыванию

### Production Checklist:

#### Перед деплоем:
- [ ] Сгенерировать новый JWT_SECRET (openssl rand -hex 32)
- [ ] Настроить HTTPS через nginx + Let's Encrypt
- [ ] Включить шифрование БД (pg_crypto или application-level)
- [ ] Настроить Docker Secrets вместо .env
- [ ] Ограничить доступ к БД (только из Docker сети)
- [ ] Настроить firewall (ufw/iptables)
- [ ] Включить fail2ban для SSH
- [ ] Настроить автоматические бэкапы (scripts/backup_database.sh в cron)
- [ ] Настроить мониторинг (Grafana + Prometheus + AlertManager)
- [ ] Добавить WAF (ModSecurity или Cloudflare)

#### После деплоя:
- [ ] Провести penetration testing
- [ ] Настроить centralized logging (ELK stack)
- [ ] Настроить alerting на аномальную активность
- [ ] Документировать incident response plan
- [ ] Провести GDPR compliance audit
- [ ] Настроить rate limiting на nginx level
- [ ] Включить DDoS protection (Cloudflare)

---

## 📈 Приоритизация исправлений

### Roadmap исправлений:

#### Фаза 1 (Критическая) - 1-2 недели:
1. Шифрование чувствительных данных в БД (пункт 1)
2. Защита от брутфорса платежной системы (пункт 2)
3. Маскировка PII в логах (пункт 3)
4. HTTPS для API (пункт 4)

#### Фаза 2 (Высокая) - 2-3 недели:
5. Валидация image_data (пункт 5)
6. Усиление JWT_SECRET (пункт 6)
7. CSRF защита (пункт 7)
8. Аудит premium функций (пункт 8)
9. Rate limit bypass защита (пункт 9)
10. Secrets rotation (пункт 10)

#### Фаза 3 (Средняя) - 1 месяц:
11. Security headers (пункт 11)
12. Логирование auth failures (пункт 12)
13. Timeout на AI операции (пункт 13)
14. Webhook validation (пункт 14)
15. Anomaly detection (пункт 15)

#### Фаза 4 (GDPR) - параллельно:
- Privacy Policy документ
- Команда экспорта данных
- Data retention policy
- DPA с Google AI

---

## 🛡️ Заключение

Проект демонстрирует **хороший фундамент** в области безопасности:
- ✅ JWT авторизация уже внедрена
- ✅ Rate limiting настроен
- ✅ SQL Injection защищен
- ✅ Circuit Breaker для Redis
- ✅ Docker изоляция

**Критические** улучшения требуются в:
1. Шифровании данных at-rest
2. Защите платежной системы
3. Конфиденциальности логирования
4. HTTPS для production

После исправления критических и высокоприоритетных пунктов проект будет **готов к production deployment** с точки зрения безопасности.

**Оценка текущего статуса:** 7/10 🟢  
**Оценка после исправлений:** 9.5/10 ⭐

---

**Подготовил:** AI Security Auditor  
**Дата:** 2025-01-07  
**Версия документа:** 1.0
