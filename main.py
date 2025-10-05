import uvicorn
import logging
import os
import asyncio
import io
from fastapi import FastAPI, HTTPException, Request, Body
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager
from pydantic import BaseModel
import json

from server.database import get_profile, create_or_update_profile, delete_profile, delete_chat_history, delete_long_term_memory, delete_summary, get_unsummarized_messages, check_message_limit, activate_premium_subscription, check_subscription_expiry, cleanup_old_chat_history, redis_circuit_breaker
from utils.db_monitoring import get_query_metrics
from datetime import datetime
from server.ai import generate_ai_response
from server.tts import create_telegram_voice_message
from server.schemas import ChatRequest, ChatResponse, ProfileData, ProfileUpdate, ChatHistory, ProfileStatus
import config

# JWT imports
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# --- Метрики Prometheus ---
from starlette_prometheus import PrometheusMiddleware, metrics
from prometheus_client import Counter, Histogram, Gauge
import time

# Определяем пользовательские метрики
CHAT_REQUESTS = Counter('chat_requests_total', 'Total number of chat requests')
CHAT_REQUESTS_DURATION = Histogram('chat_requests_duration_seconds', 'Duration of chat requests processing')
AI_RESPONSE_DURATION = Histogram('ai_response_duration_seconds', 'Duration of AI response generation')
TTS_GENERATION_DURATION = Histogram('tts_generation_duration_seconds', 'Duration of TTS generation')
VOICE_MESSAGES_GENERATED = Counter('voice_messages_generated_total', 'Total number of voice messages generated')
def get_limiter_key(request: Request) -> str:
    """
    Возвращает IP-адрес клиента для rate limiting.
    """
    return get_remote_address(request)

limiter = Limiter(key_func=get_limiter_key)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.info("🚀 Запуск приложения...")
    
    # Запускаем scheduler для фоновых задач
    from server.scheduler import start_scheduler, shutdown_scheduler
    start_scheduler()
    logging.info("✅ Scheduler запущен")
    
    yield
    
    # Shutdown
    logging.info("🛑 Остановка приложения...")
    shutdown_scheduler()
    logging.info("✅ Приложение остановлено")

app = FastAPI(
    title="EvolveAI Backend",
    lifespan=lifespan
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Helper functions for chat_handler

async def check_message_limits(user_id: int) -> dict:
    """
    Checks message limits and returns check result.
    """
    limit_check = await check_message_limit(user_id)
    return limit_check

async def handle_tts_generation(user_id: int, response_text: str) -> str | None:
    """
    Handles TTS generation for premium users if [VOICE] marker is present.
    """
    await check_subscription_expiry(user_id)
    profile = await get_profile(user_id)
    is_premium = profile and profile.is_premium_active
    logging.debug(f"TTS guard: {'enabled' if is_premium else 'disabled'} for user {user_id} (plan: {profile.subscription_plan if profile else 'none'})")

    voice_message_data = None
    has_voice_marker = response_text.startswith('[VOICE]')
    if has_voice_marker:
        if not is_premium:
            # Strip [VOICE] for non-premium and skip TTS
            return response_text.replace('[VOICE]', '', 1).strip(), None
        else:
            # Proceed with TTS for premium
            text_to_speak = response_text.replace('[VOICE]', '', 1).strip()
            
            # Создаем файловый объект в памяти вместо реального файла
            voice_file_object = io.BytesIO()
            
            # Замеряем время генерации голосового сообщения
            tts_start_time = time.time()
            success = await create_telegram_voice_message(text_to_speak, voice_file_object)
            TTS_GENERATION_DURATION.observe(time.time() - tts_start_time)

            if success:
                voice_file_object.seek(0)  # "Перематываем" в начало, чтобы прочитать данные
                voice_message_bytes = voice_file_object.read()
                # Кодируем бинарные данные в base64 для передачи в JSON
                import base64
                voice_message_data = base64.b64encode(voice_message_bytes).decode('utf-8')
                VOICE_MESSAGES_GENERATED.inc()
                return text_to_speak, voice_message_data
            else:
                # Если генерация не удалась, отправляем текстовый fallback
                return "Хо хотела записать голосовое, но что-то с телефоном... короче, я так по тебе соскучилась!", None

    return response_text, None

def assemble_chat_response(response_text: str, voice_data: str | None, image_base64: str | None) -> ChatResponse:
    """
    Assembles the final ChatResponse object.
    """
    if voice_data is None:
        # No voice, use original text
        pass
    else:
        # Voice generated, text is already stripped
        response_text = voice_data[0] if isinstance(voice_data, tuple) else response_text
        voice_message_data = voice_data[1] if isinstance(voice_data, tuple) else voice_data

    return ChatResponse(
        response_text=response_text,
        voice_message=voice_message_data,
        image_base64=image_base64
    )

# JWT setup
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = config.JWT_SECRET
ALGORITHM = config.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = config.JWT_EXPIRE_MINUTES

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

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
    except JWTError as je:
        logging.error(f"JWT Debug Error: {str(je)}")
        raise credentials_exception
    return user_id

# --- Метрики Prometheus ---
from starlette_prometheus import PrometheusMiddleware, metrics
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics)


@app.get("/", summary="Корневой эндпоинт", description="Возвращает приветственное сообщение, указывающее, что бэкенд запущен.")
async def read_root():
    """
    Возвращает JSON с сообщением о том, что бэкенд запущен.
    """
    return {"message": "EvolveAI Backend is running"}

@app.get("/health", status_code=200, summary="Проверка работоспособности", description="Проверяет, что сервис запущен и работает.")
async def health_check():
    """
    Базовая проверка работоспособности сервиса (liveness probe).
    Не проверяет зависимости - только что процесс запущен.
    
    Возвращает:
        dict: JSON с ключом "status" и значением "ok", если сервис работает.
    """
    return {"status": "ok"}

@app.post("/auth", summary="Генерация JWT токена", description="Создает JWT токен для пользователя по user_id (для внутреннего использования бота).")
@limiter.limit("10/minute")
async def auth_endpoint(request: Request, auth_data: dict = Body(...)):
    """
    Генерирует JWT токен для аутентификации API запросов.
    
    Args:
        auth_data (dict): {"user_id": int}
        
    Returns:
        dict: {"access_token": str, "token_type": "bearer"}
    """
    user_id = auth_data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user_id)}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/ready", status_code=200, summary="Проверка готовности", description="Проверяет готовность всех критичных зависимостей: БД, Redis, Gemini API.")
async def ready_check():
    """
    Полная проверка готовности сервиса к приему трафика (readiness probe).
    Проверяет все критичные зависимости:
    - База данных (PostgreSQL)
    - Кэш (Redis)
    - AI API (Gemini)
    
    Возвращает:
        dict: JSON со статусом каждого сервиса и общим статусом.
        
    Вызывает:
        HTTPException: С кодом 503, если хотя бы один критичный сервис недоступен.
    """
    checks = {
        "database": {"status": "unknown", "message": ""},
        "redis": {"status": "unknown", "message": ""},
        "gemini": {"status": "unknown", "message": ""},
        "overall": "healthy"
    }
    
    # 1. Проверка БД
    try:
        await get_profile(0)  # Попытка получить профиль (может вернуть None, это ок)
        checks["database"]["status"] = "healthy"
        checks["database"]["message"] = "Connected"
    except Exception as e:
        checks["database"]["status"] = "unhealthy"
        checks["database"]["message"] = str(e)
        checks["overall"] = "unhealthy"
        logging.error(f"Database healthcheck failed: {e}")
    
    # 2. Проверка Redis (опционально, но желательно) + Circuit Breaker статус
    if config.REDIS_CLIENT:
        try:
            await config.REDIS_CLIENT.ping()
            cb_state = redis_circuit_breaker.get_state()
            checks["redis"]["status"] = "healthy" if cb_state == "CLOSED" else "degraded"
            checks["redis"]["message"] = f"Connected, Circuit Breaker: {cb_state}"
            checks["redis"]["circuit_breaker"] = {
                "state": cb_state,
                "failure_count": redis_circuit_breaker.failure_count
            }
        except Exception as e:
            checks["redis"]["status"] = "degraded"  # Redis не критичен
            checks["redis"]["message"] = str(e)
            checks["redis"]["circuit_breaker"] = {
                "state": redis_circuit_breaker.get_state(),
                "failure_count": redis_circuit_breaker.failure_count
            }
            logging.warning(f"Redis healthcheck failed: {e}")
    else:
        checks["redis"]["status"] = "disabled"
        checks["redis"]["message"] = "Redis not configured"
    
    # 3. Проверка Gemini API + Circuit Breaker
    from utils.circuit_breaker import gemini_circuit_breaker
    
    if config.GEMINI_CLIENT:
        try:
            cb_stats = gemini_circuit_breaker.get_stats()
            cb_state = cb_stats["state"]
            
            # Определяем статус на основе circuit breaker
            if cb_state == "CLOSED":
                checks["gemini"]["status"] = "healthy"
                checks["gemini"]["message"] = f"Client initialized, Circuit Breaker: {cb_state}"
            elif cb_state == "HALF_OPEN":
                checks["gemini"]["status"] = "degraded"
                checks["gemini"]["message"] = f"Testing recovery, Circuit Breaker: {cb_state}"
                checks["overall"] = "degraded"
            else:  # OPEN
                checks["gemini"]["status"] = "unhealthy"
                checks["gemini"]["message"] = f"Circuit Breaker OPEN (retry in {cb_stats['time_until_retry']}s)"
                checks["overall"] = "unhealthy"
            
            # Добавляем статистику circuit breaker
            checks["gemini"]["circuit_breaker"] = {
                "state": cb_state,
                "failure_count": cb_stats["failure_count"],
                "total_calls": cb_stats["total_calls"],
                "total_blocked": cb_stats["total_blocked"],
                "success_rate": round(cb_stats["total_successes"] / cb_stats["total_calls"] * 100, 2) if cb_stats["total_calls"] > 0 else 100
            }
            
        except Exception as e:
            checks["gemini"]["status"] = "unhealthy"
            checks["gemini"]["message"] = str(e)
            checks["overall"] = "unhealthy"
            logging.error(f"Gemini healthcheck failed: {e}")
    else:
        checks["gemini"]["status"] = "unhealthy"
        checks["gemini"]["message"] = "Gemini client not initialized"
        checks["overall"] = "unhealthy"
    
    # Возвращаем 503 если общий статус unhealthy
    if checks["overall"] == "unhealthy":
        raise HTTPException(status_code=503, detail=checks)
    
    return checks

@app.post("/chat", response_model=ChatResponse, summary="Обработка чат-сообщения", description="Принимает сообщение от пользователя и возвращает ответ от AI. Требует JWT токен в заголовке Authorization.")
@limiter.limit("10/minute")
async def chat_handler(
    request: Request,
    chat: ChatRequest,
    user_id: int = Depends(verify_token)
):
    """
    Обрабатывает входящее сообщение от пользователя и генерирует ответ с помощью AI.
    user_id извлекается из JWT токена для безопасности.
    
    Args:
        request (Request): Объект запроса FastAPI.
        chat (ChatRequest): Данные чат-запроса, включая сообщение, временную метку и данные изображения (user_id игнорируется, используется из токена).
        user_id (int): ID пользователя из JWT токена.
        
    Returns:
        ChatResponse: Ответ, содержащий текст сообщения и, при необходимости, голосовое сообщение.
        
    Вызывает:
        HTTPException: С кодом 500, если произошла внутренняя ошибка сервера.
    """
    start_time = time.time()
    CHAT_REQUESTS.inc()

    # Check message limits
    limit_check = await check_message_limits(user_id)
    if not limit_check["allowed"]:
        CHAT_REQUESTS_DURATION.observe(time.time() - start_time)
        return ChatResponse(
            response_text=limit_check["message"],
            voice_message=None
        )

    # Generate AI response
    ai_start_time = time.time()
    ai_response = await generate_ai_response(
        user_id=user_id,
        user_message=chat.message,
        timestamp=chat.timestamp,
        image_data=chat.image_data
    )
    AI_RESPONSE_DURATION.observe(time.time() - ai_start_time)

    response_text = ai_response['text']
    image_base64 = ai_response.get('image_base64')

    # Handle TTS if premium
    voice_message_data = await handle_tts_generation(user_id, response_text)

    CHAT_REQUESTS_DURATION.observe(time.time() - start_time)
    return assemble_chat_response(response_text, voice_message_data, image_base64)


@app.get("/profile/{user_id}", response_model=ProfileData | None, summary="Получение профиля пользователя", description="Возвращает данные профиля пользователя по его ID.")
async def get_profile_handler(user_id: int):
    """
    Получает данные профиля пользователя по его ID.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя.
        
    Returns:
        ProfileData | None: Данные профиля пользователя или None, если профиль не найден.
    """
    profile = await get_profile(user_id)
    if not profile:
        return None
    return ProfileData(**profile.to_dict())

@app.get("/chat_history/{user_id}", response_model=ChatHistory | None, summary="Получение истории чата", description="Возвращает историю чата пользователя по его ID.")
async def get_chat_history_handler(user_id: int):
    """
    Получает историю чата пользователя по его ID.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя.
        
    Returns:
        ChatHistory | None: История чата пользователя или None, если история отсутствует.
    """
    chat_history = await get_unsummarized_messages(user_id)
    if not chat_history:
        return None
    return ChatHistory(user_id=user_id, history=chat_history)

@app.post("/profile", summary="Создание или обновление профиля", description="Создает новый профиль пользователя или обновляет существующий.")
@limiter.limit("20/minute")
async def create_or_update_profile_handler(request: Request, profile_update: ProfileUpdate):
    """
    Создает новый профиль пользователя или обновляет существующий.
    
    Args:
        request (ProfileUpdate): Данные для создания или обновления профиля, включая user_id и данные профиля.
        
    Returns:
        dict: JSON с сообщением об успешном обновлении профиля.
    """
    await create_or_update_profile(profile_update.user_id, profile_update.data.dict())
    return {"message": "Профиль успешно обновлен"}

@app.delete("/profile/{user_id}", summary="Удаление профиля и истории чата", description="Удаляет профиль пользователя, историю чата, долговременную память и сводку.")
async def delete_profile_handler(user_id: int):
    """
    Удаляет профиль пользователя, историю чата, долговременную память и сводку.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя.
        
    Returns:
        dict: JSON с сообщением об успешном удалении профиля и истории чата.
    """
    await delete_profile(user_id)
    await delete_chat_history(user_id)
    await delete_long_term_memory(user_id)
    await delete_summary(user_id)
    return {"message": "Профиль и история чата успешно удалены"}

@app.get("/profile/status/{user_id}", response_model=ProfileStatus, summary="Получение статуса профиля", description="Возвращает статус профиля пользователя, включая план подписки и количество сообщений за день.")
async def get_profile_status_handler(user_id: int):
    """
    Получает статус профиля пользователя, включая план подписки и количество сообщений за день.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя.
        
    Returns:
        ProfileStatus: Статус профиля пользователя.
        
    Вызывает:
        HTTPException: С кодом 404, если профиль не найден.
    """
    profile = await get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")
    
    return ProfileStatus(
        subscription_plan=profile.subscription_plan,
        subscription_expires=profile.subscription_expires,
        daily_message_count=profile.daily_message_count
    )

@app.post("/test-tts", summary="Тест голосовых сообщений")
async def test_tts(
    text: str = "Привет! Это тест голосового сообщения.",
    user_id: int = Depends(verify_token)
):
    """
    Тестовый эндпоинт для проверки TTS функциональности.
    Требует JWT авторизацию для предотвращения злоупотребления.
    
    Args:
        text: Текст для генерации голосового сообщения
        user_id: ID пользователя из JWT токена
    """
    import base64
    voice_file_object = io.BytesIO()
    success = await create_telegram_voice_message(text, voice_file_object)
    
    if success:
        voice_file_object.seek(0)
        voice_data = voice_file_object.read()
        return {
            "success": True,
            "message": "TTS работает корректно",
            "voice_size_bytes": len(voice_data),
            "voice_data_base64": base64.b64encode(voice_data).decode('utf-8')
        }
    else:
        return {
            "success": False,
            "message": "TTS не работает"
        }

@app.get("/admin/db_metrics", summary="Метрики БД", description="Возвращает статистику запросов к БД и slow queries (только для администраторов).")
@limiter.limit("10/minute")
async def db_metrics_handler(
    request: Request,
    user_id: int = Depends(verify_token)
):
    """
    Возвращает метрики производительности БД:
    - Общее количество запросов
    - Количество медленных запросов (>1s)
    - Среднее время выполнения
    - Процент slow queries
    
    ВАЖНО: Этот endpoint должен быть защищен дополнительной проверкой прав администратора.
    
    Args:
        request: FastAPI Request для rate limiting
        user_id: ID пользователя из JWT токена (должен быть админ)
    
    Returns:
        dict: Метрики производительности БД
    """
    metrics = get_query_metrics()
    return {"db_metrics": metrics}

@app.get("/admin/cache_stats", summary="Статистика кэша", description="Возвращает статистику использования Redis кэша (только для администраторов).")
@limiter.limit("10/minute")
async def cache_stats_handler(
    request: Request,
    user_id: int = Depends(verify_token)
):
    """
    Возвращает статистику кэша:
    - Используемая память
    - Количество ключей
    - Hit rate (процент попаданий)
    - Активные соединения
    
    ВАЖНО: Этот endpoint должен быть защищен дополнительной проверкой прав администратора.
    
    Args:
        request: FastAPI Request для rate limiting
        user_id: ID пользователя из JWT токена (должен быть админ)
    
    Returns:
        dict: Статистика кэша
    """
    from utils.cache import get_cache_stats
    stats = await get_cache_stats()
    return {"cache_stats": stats}

@app.get("/admin/scheduler_status", summary="Статус scheduler", description="Возвращает статус фоновых задач (только для администраторов).")
@limiter.limit("10/minute")
async def scheduler_status_handler(
    request: Request,
    user_id: int = Depends(verify_token)
):
    """
    Возвращает статус scheduler и список запланированных задач.
    
    ВАЖНО: Этот endpoint должен быть защищен дополнительной проверкой прав администратора.
    
    Args:
        request: FastAPI Request для rate limiting
        user_id: ID пользователя из JWT токена (должен быть админ)
    
    Returns:
        dict: Статус scheduler и информация о задачах
    """
    from server.scheduler import get_scheduler_status
    status = get_scheduler_status()
    return {"scheduler": status}

@app.post("/admin/cleanup_chat_history", summary="Очистка старых сообщений", description="Удаляет историю чата старше указанного количества дней (только для администраторов).")
@limiter.limit("1/hour")
async def cleanup_chat_history_handler(
    request: Request,
    days_to_keep: int = 30,
    user_id: int = Depends(verify_token)
):
    """
    Удаляет историю чата старше указанного количества дней.
    
    ВАЖНО: Этот endpoint должен быть защищен дополнительной проверкой прав администратора.
    Теперь эта функция выполняется автоматически через APScheduler.
    Этот endpoint оставлен для ручного запуска при необходимости.
    
    Args:
        request: FastAPI Request для rate limiting
        days_to_keep: Количество дней для хранения истории
        user_id: ID пользователя из JWT токена (должен быть админ)
    
    Returns:
        dict: Количество удаленных записей
    """
    count = await cleanup_old_chat_history(days_to_keep)
    return {"deleted_count": count, "days_kept": days_to_keep}

@app.get("/admin/analytics/overview", summary="Общая аналитика", description="Возвращает общую статистику использования бота (только для администраторов).")
@limiter.limit("10/minute")
async def analytics_overview_handler(
    request: Request,
    user_id: int = Depends(verify_token)
):
    """
    Возвращает общую статистику использования бота:
    - Количество пользователей (total, active, DAU, premium)
    - Статистика сообщений
    - Engagement метрики
    
    ВАЖНО: Этот endpoint должен быть защищен дополнительной проверкой прав администратора.
    
    Args:
        request: FastAPI Request для rate limiting
        user_id: ID пользователя из JWT токена (должен быть админ)
    
    Returns:
        dict: Общая статистика
    """
    from server.analytics import get_overview_stats
    stats = await get_overview_stats()
    return {"analytics": stats}

@app.get("/admin/analytics/users", summary="Аналитика пользователей", description="Возвращает детальную статистику о пользователях (только для администраторов).")
@limiter.limit("10/minute")
async def analytics_users_handler(
    request: Request,
    user_id: int = Depends(verify_token)
):
    """
    Возвращает детальную статистику пользователей:
    - Распределение по уровням отношений
    - Распределение по подпискам
    - Топ активных пользователей
    - Новые пользователи
    
    ВАЖНО: Этот endpoint должен быть защищен дополнительной проверкой прав администратора.
    
    Args:
        request: FastAPI Request для rate limiting
        user_id: ID пользователя из JWT токена (должен быть админ)
    
    Returns:
        dict: Статистика пользователей
    """
    from server.analytics import get_users_stats
    stats = await get_users_stats()
    return {"analytics": stats}

@app.get("/admin/analytics/messages", summary="Аналитика сообщений", description="Возвращает статистику сообщений (только для администраторов).")
@limiter.limit("10/minute")
async def analytics_messages_handler(
    request: Request,
    days: int = 7,
    user_id: int = Depends(verify_token)
):
    """
    Возвращает статистику сообщений:
    - Сообщения по дням
    - Сообщения по часам (пиковая нагрузка)
    - Соотношение user/model
    - Средняя длина сообщений
    
    ВАЖНО: Этот endpoint должен быть защищен дополнительной проверкой прав администратора.
    
    Args:
        request: FastAPI Request для rate limiting
        days: Количество дней для анализа (по умолчанию 7)
        user_id: ID пользователя из JWT токена (должен быть админ)
    
    Returns:
        dict: Статистика сообщений
    """
    from server.analytics import get_messages_stats
    stats = await get_messages_stats(days=days)
    return {"analytics": stats}

@app.get("/admin/analytics/revenue", summary="Аналитика подписок", description="Возвращает статистику подписок и доходов (только для администраторов).")
@limiter.limit("10/minute")
async def analytics_revenue_handler(
    request: Request,
    user_id: int = Depends(verify_token)
):
    """
    Возвращает статистику подписок и доходов:
    - Активные подписки
    - Новые подписки за период
    - Истекающие подписки
    - MRR, ARR
    - Churn rate
    
    ВАЖНО: Этот endpoint должен быть защищен дополнительной проверкой прав администратора.
    
    Args:
        request: FastAPI Request для rate limiting
        user_id: ID пользователя из JWT токена (должен быть админ)
    
    Returns:
        dict: Статистика подписок и доходов
    """
    from server.analytics import get_revenue_stats
    stats = await get_revenue_stats()
    return {"analytics": stats}

@app.get("/admin/analytics/features", summary="Аналитика функций", description="Возвращает статистику использования функций бота (только для администраторов).")
@limiter.limit("10/minute")
async def analytics_features_handler(
    request: Request,
    user_id: int = Depends(verify_token)
):
    """
    Возвращает статистику использования функций:
    - Использование долговременной памяти
    - Память по категориям
    - Количество сводок
    
    ВАЖНО: Этот endpoint должен быть защищен дополнительной проверкой прав администратора.
    
    Args:
        request: FastAPI Request для rate limiting
        user_id: ID пользователя из JWT токена (должен быть админ)
    
    Returns:
        dict: Статистика использования функций
    """
    from server.analytics import get_feature_usage_stats
    stats = await get_feature_usage_stats()
    return {"analytics": stats}

@app.get("/admin/analytics/cohort", summary="Когортный анализ", description="Возвращает retention по когортам (только для администраторов).")
@limiter.limit("10/minute")
async def analytics_cohort_handler(
    request: Request,
    days: int = 30,
    user_id: int = Depends(verify_token)
):
    """
    Возвращает когортный анализ:
    - Retention по дням регистрации (Day 1, Day 7)
    - Средний retention по всем когортам
    - Качество аудитории
    
    ВАЖНО: Этот endpoint должен быть защищен дополнительной проверкой прав администратора.
    
    Args:
        request: FastAPI Request для rate limiting
        days: Количество дней для анализа (по умолчанию 30)
        user_id: ID пользователя из JWT токена (должен быть админ)
    
    Returns:
        dict: Когортный анализ
    """
    from server.analytics import get_cohort_analysis
    stats = await get_cohort_analysis(days=days)
    return {"analytics": stats}

@app.get("/admin/analytics/funnel", summary="Funnel analysis", description="Возвращает воронку прогресса по уровням отношений (только для администраторов).")
@limiter.limit("10/minute")
async def analytics_funnel_handler(
    request: Request,
    user_id: int = Depends(verify_token)
):
    """
    Возвращает funnel analysis:
    - Conversion rates между уровнями
    - Bottleneck detection (где больше всего отсеивается)
    - Средний уровень достижения
    - % conversion до финального уровня
    
    ВАЖНО: Этот endpoint должен быть защищен дополнительной проверкой прав администратора.
    
    Args:
        request: FastAPI Request для rate limiting
        user_id: ID пользователя из JWT токена (должен быть админ)
    
    Returns:
        dict: Funnel analysis
    """
    from server.analytics import get_funnel_analysis
    stats = await get_funnel_analysis()
    return {"analytics": stats}

@app.get("/admin/analytics/activity", summary="Паттерны активности", description="Возвращает активность по дням недели и часам (только для администраторов).")
@limiter.limit("10/minute")
async def analytics_activity_handler(
    request: Request,
    user_id: int = Depends(verify_token)
):
    """
    Возвращает паттерны активности:
    - Активность по дням недели
    - Пиковые и медленные часы
    - Средняя длина сессии
    
    ВАЖНО: Этот endpoint должен быть защищен дополнительной проверкой прав администратора.
    
    Args:
        request: FastAPI Request для rate limiting
        user_id: ID пользователя из JWT токена (должен быть админ)
    
    Returns:
        dict: Паттерны активности
    """
    from server.analytics import get_activity_patterns
    stats = await get_activity_patterns()
    return {"analytics": stats}

@app.get("/admin/analytics/tools", summary="Использование AI Tools", description="Возвращает детальную статистику использования функций бота (только для администраторов).")
@limiter.limit("10/minute")
async def analytics_tools_handler(
    request: Request,
    days: int = 7,
    user_id: int = Depends(verify_token)
):
    """
    Возвращает статистику использования AI Tools:
    - Новые факты памяти по дням
    - Топ-5 категорий памяти
    - Power users (>5 фактов)
    
    ВАЖНО: Этот endpoint должен быть защищен дополнительной проверкой прав администратора.
    
    Args:
        request: FastAPI Request для rate limiting
        days: Количество дней для анализа (по умолчанию 7)
        user_id: ID пользователя из JWT токена (должен быть админ)
    
    Returns:
        dict: Статистика использования AI Tools
    """
    from server.analytics import get_tools_usage_stats
    stats = await get_tools_usage_stats(days=days)
    return {"analytics": stats}

@app.post("/activate_premium", summary="Активация премиум подписки", description="Активирует премиум подписку для пользователя.")
@limiter.limit("5/minute")
async def activate_premium_handler(
    request: Request,
    activate_request: dict = Body(...),
    authenticated_user_id: int = Depends(verify_token)
):
    """
    Активирует премиум подписку для пользователя.
    Требует JWT авторизацию и проверяет соответствие user_id.
    
    Args:
        request: FastAPI Request для rate limiting
        activate_request (dict): {"user_id": int, "duration_days": int, "charge_id": str (optional)}
        authenticated_user_id: ID пользователя из JWT токена
        
    Returns:
        dict: {"success": bool, "message": str}
    """
    user_id = activate_request.get("user_id")
    duration_days = activate_request.get("duration_days", 30)
    charge_id = activate_request.get("charge_id")
    
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id обязателен")
    
    # SECURITY: Проверяем, что user_id из токена совпадает с user_id в запросе
    if user_id != authenticated_user_id:
        logging.warning(f"Попытка активации подписки: authenticated_user={authenticated_user_id}, requested_user={user_id}")
        raise HTTPException(status_code=403, detail="Запрещено активировать подписку для другого пользователя")
    
    success = await activate_premium_subscription(user_id, duration_days, charge_id)
    
    if success:
        return {"success": True, "message": f"Премиум подписка активирована на {duration_days} дней"}
    else:
        raise HTTPException(status_code=500, detail="Ошибка активации подписки")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
