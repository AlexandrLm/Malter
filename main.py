import uvicorn
import logging
import os
import asyncio
import io
from fastapi import FastAPI, HTTPException, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager
from pydantic import BaseModel
import json

from server.database import get_profile, create_or_update_profile, delete_profile, delete_chat_history, delete_long_term_memory, delete_summary, get_unsummarized_messages
from server.ai import generate_ai_response
from server.tts import create_telegram_voice_message
from server.schemas import ChatRequest, ChatResponse, ProfileData, ProfileUpdate, ChatHistory, ProfileStatus

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
async def get_limiter_key(request: Request) -> str:
    """
    Извлекает user_id из тела POST-запроса для точного ограничения.
    Если user_id не найден (например, для GET-запросов), возвращается к IP-адресу.
    """
    try:
        # Пытаемся прочитать тело запроса как JSON
        body = await request.json()
        user_id = body.get("user_id")
        if user_id:
            return str(user_id)
    except (json.JSONDecodeError, AttributeError):
        # Если тело невалидно или это не POST-запрос, возвращаемся к IP
        return get_remote_address(request)
    # Возвращаемся к IP в качестве запасного варианта
    return get_remote_address(request)

limiter = Limiter(key_func=get_limiter_key)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Запускайте `alembic upgrade head` для применения миграций.
    yield
    print("Сервер выключается.")

app = FastAPI(
    title="EvolveAI Backend",
    lifespan=lifespan
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
    Проверка работоспособности сервиса.
    
    Возвращает:
        dict: JSON с ключом "status" и значением "ok", если сервис работает.
    """
    return {"status": "ok"}

@app.get("/ready", status_code=200, summary="Проверка готовности", description="Проверяет, готов ли сервис к приему трафика, включая подключение к базе данных.")
async def ready_check():
    """
    Проверка готовности сервиса к приему трафика (проверка подключения к БД).
    
    Возвращает:
        dict: JSON с ключом "status" и значением "ready", если сервис готов.
        
    Вызывает:
        HTTPException: С кодом 503, если не удалось подключиться к базе данных.
    """
    try:
        await get_profile(0)
        return {"status": "ready"}
    except Exception as e:
        logging.error(f"Проверка готовности не пройдена: не удалось подключиться к БД. Ошибка: {e}")
        raise HTTPException(status_code=503, detail="Service Unavailable")

@app.post("/chat", response_model=ChatResponse, summary="Обработка чат-сообщения", description="Принимает сообщение от пользователя и возвращает ответ от AI.")
@limiter.limit("10/minute")
async def chat_handler(request: Request, chat: ChatRequest):
    """
    Обрабатывает входящее сообщение от пользователя и генерирует ответ с помощью AI.
    
    Args:
        request (Request): Объект запроса FastAPI.
        chat (ChatRequest): Данные чат-запроса, включая user_id, сообщение, временную метку и данные изображения (если есть).
        
    Returns:
        ChatResponse: Ответ, содержащий текст сообщения и, при необходимости, голосовое сообщение.
        
    Вызывает:
        HTTPException: С кодом 500, если произошла внутренняя ошибка сервера.
    """
    start_time = time.time()
    CHAT_REQUESTS.inc()
    
    try:
        # Замеряем время генерации ответа AI
        ai_start_time = time.time()
        response_text = await generate_ai_response(
            user_id=chat.user_id,
            user_message=chat.message,
            timestamp=chat.timestamp,
            image_data=chat.image_data
        )
        AI_RESPONSE_DURATION.observe(time.time() - ai_start_time)

        voice_message_data = None
        if response_text.startswith('[VOICE]'):
            text_to_speak = response_text.replace('[VOICE]', '').strip()
            
            # Создаем файловый объект в памяти вместо реального файла
            voice_file_object = io.BytesIO()
            
            # Замеряем время генерации голосового сообщения
            tts_start_time = time.time()
            success = await create_telegram_voice_message(text_to_speak, voice_file_object)
            TTS_GENERATION_DURATION.observe(time.time() - tts_start_time)

            if success:
                voice_file_object.seek(0)  # "Перематываем" в начало, чтобы прочитать данные
                voice_message_data = voice_file_object.read()
                VOICE_MESSAGES_GENERATED.inc()
            else:
                # Если генерация не удалась, отправляем текстовый fallback
                response_text = "Хо хотела записать голосовое, но что-то с телефоном... короче, я так по тебе соскучилась!"

        CHAT_REQUESTS_DURATION.observe(time.time() - start_time)
        return ChatResponse(response_text=response_text, voice_message=voice_message_data)

    except ValueError as e:
        logging.error(f"Ошибка валидации данных в chat_handler для пользователя {chat.user_id}: {e}")
        CHAT_REQUESTS_DURATION.observe(time.time() - start_time)
        raise HTTPException(status_code=400, detail="Неверные данные запроса")
    except Exception as e:
        logging.error(f"Ошибка в chat_handler для пользователя {chat.user_id}: {e}")
        CHAT_REQUESTS_DURATION.observe(time.time() - start_time)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@app.get("/profile/{user_id}", response_model=ProfileData | None, summary="Получение профиля пользователя", description="Возвращает данные профиля пользователя по его ID.")
async def get_profile_handler(user_id: int):
    """
    Получает данные профиля пользователя по его ID.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя.
        
    Returns:
        ProfileData | None: Данные профиля пользователя или None, если профиль не найден.
    """
    try:
        profile = await get_profile(user_id)
        if not profile:
            return None
        return ProfileData(**profile.to_dict())
    except ValueError as e:
        logging.error(f"Ошибка валидации данных в get_profile_handler для пользователя {user_id}: {e}")
        raise HTTPException(status_code=400, detail="Неверные данные запроса")
    except Exception as e:
        logging.error(f"Ошибка в get_profile_handler для пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@app.get("/chat_history/{user_id}", response_model=ChatHistory | None, summary="Получение истории чата", description="Возвращает историю чата пользователя по его ID.")
async def get_chat_history_handler(user_id: int):
    """
    Получает историю чата пользователя по его ID.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя.
        
    Returns:
        ChatHistory | None: История чата пользователя или None, если история отсутствует.
    """
    try:
        chat_history = await get_unsummarized_messages(user_id)
        if not chat_history:
            return None
        return ChatHistory(user_id=user_id, history=chat_history)
    except ValueError as e:
        logging.error(f"Ошибка валидации данных в get_chat_history_handler для пользователя {user_id}: {e}")
        raise HTTPException(status_code=400, detail="Неверные данные запроса")
    except Exception as e:
        logging.error(f"Ошибка в get_chat_history_handler для пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@app.post("/profile", summary="Создание или обновление профиля", description="Создает новый профиль пользователя или обновляет существующий.")
async def create_or_update_profile_handler(request: ProfileUpdate):
    """
    Создает новый профиль пользователя или обновляет существующий.
    
    Args:
        request (ProfileUpdate): Данные для создания или обновления профиля, включая user_id и данные профиля.
        
    Returns:
        dict: JSON с сообщением об успешном обновлении профиля.
    """
    try:
        await create_or_update_profile(request.user_id, request.data.dict())
        return {"message": "Профиль успешно обновлен"}
    except ValueError as e:
        logging.error(f"Ошибка валидации данных в create_or_update_profile_handler для пользователя {request.user_id}: {e}")
        raise HTTPException(status_code=400, detail="Неверные данные запроса")
    except Exception as e:
        logging.error(f"Ошибка в create_or_update_profile_handler для пользователя {request.user_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@app.delete("/profile/{user_id}", summary="Удаление профиля и истории чата", description="Удаляет профиль пользователя, историю чата, долговременную память и сводку.")
async def delete_profile_handler(user_id: int):
    """
    Удаляет профиль пользователя, историю чата, долговременную память и сводку.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя.
        
    Returns:
        dict: JSON с сообщением об успешном удалении профиля и истории чата.
    """
    try:
        await delete_profile(user_id)
        await delete_chat_history(user_id)
        await delete_long_term_memory(user_id)
        await delete_summary(user_id)
        return {"message": "Профиль и история чата успешно удалены"}
    except ValueError as e:
        logging.error(f"Ошибка валидации данных в delete_profile_handler для пользователя {user_id}: {e}")
        raise HTTPException(status_code=400, detail="Неверные данные запроса")
    except Exception as e:
        logging.error(f"Ошибка в delete_profile_handler для пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

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
    try:
        profile = await get_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Профиль не найден")
        
        return ProfileStatus(
            subscription_plan=profile.subscription_plan,
            subscription_expires=profile.subscription_expires,
            daily_message_count=profile.daily_message_count
        )
    except ValueError as e:
        logging.error(f"Ошибка валидации данных в get_profile_status_handler для пользователя {user_id}: {e}")
        raise HTTPException(status_code=400, detail="Неверные данные запроса")
    except HTTPException:
        # Повторно выбрасываем HTTPException, если он уже был создан
        raise
    except Exception as e:
        logging.error(f"Ошибка в get_profile_status_handler для пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)