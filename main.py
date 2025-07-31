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

from server.database import get_profile, create_or_update_profile, delete_profile, delete_chat_history, delete_long_term_memory, delete_summary, get_chat_history
from server.ai import generate_ai_response
from server.tts import create_telegram_voice_message
from server.schemas import ChatRequest, ChatResponse, ProfileData, ProfileUpdate, ChatHistory, ProfileStatus

# --- Rate Limiting ---
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
    title="MashaGPT Backend",
    lifespan=lifespan
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Метрики Prometheus ---
from starlette_prometheus import PrometheusMiddleware, metrics
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics)


@app.get("/")
async def read_root():
    return {"message": "MashaGPT Backend is running"}

@app.get("/health", status_code=200)
async def health_check():
    """Проверка работоспособности сервиса."""
    return {"status": "ok"}

@app.get("/ready", status_code=200)
async def ready_check():
    """Проверка готовности сервиса к приему трафика (проверка подключения к БД)."""
    try:
        await get_profile(0)
        return {"status": "ready"}
    except Exception as e:
        logging.error(f"Проверка готовности не пройдена: не удалось подключиться к БД. Ошибка: {e}")
        raise HTTPException(status_code=503, detail="Service Unavailable")

@app.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat_handler(request: Request, chat: ChatRequest):
    try:
        response_text = await generate_ai_response(
            user_id=chat.user_id,
            user_message=chat.message,
            timestamp=chat.timestamp,
            image_data=chat.image_data
        )

        voice_message_data = None
        if response_text.startswith('[VOICE]'):
            text_to_speak = response_text.replace('[VOICE]', '').strip()
            
            # Создаем файловый объект в памяти вместо реального файла
            voice_file_object = io.BytesIO()
            
            success = await create_telegram_voice_message(text_to_speak, voice_file_object)

            if success:
                voice_file_object.seek(0)  # "Перематываем" в начало, чтобы прочитать данные
                voice_message_data = voice_file_object.read()
            else:
                # Если генерация не удалась, отправляем текстовый fallback
                response_text = "Хо хотела записать голосовое, но что-то с телефоном... короче, я так по тебе соскучилась!"

        return ChatResponse(response_text=response_text, voice_message=voice_message_data)

    except Exception as e:
        logging.error(f"Ошибка в chat_handler для пользователя {chat.user_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@app.get("/profile/{user_id}", response_model=ProfileData | None)
async def get_profile_handler(user_id: int):
    profile = await get_profile(user_id)
    if not profile:
        return None
    return ProfileData(**profile.to_dict())

@app.get("/chat_history/{user_id}", response_model=ChatHistory | None)
async def get_chat_history_handler(user_id: int):
    chat_history = await get_chat_history(user_id)
    if not chat_history:
        return None
    return ChatHistory(user_id=user_id, history=chat_history)

@app.post("/profile")
async def create_or_update_profile_handler(request: ProfileUpdate):
    await create_or_update_profile(request.user_id, request.data.dict())
    return {"message": "Профиль успешно обновлен"}

@app.delete("/profile/{user_id}")
async def delete_profile_handler(user_id: int):
    await delete_profile(user_id)
    await delete_chat_history(user_id)
    await delete_long_term_memory(user_id)
    await delete_summary(user_id)
    return {"message": "Профиль и история чата успешно удалены"}

@app.get("/profile/status/{user_id}", response_model=ProfileStatus)
async def get_profile_status_handler(user_id: int):
    profile = await get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")
    
    return ProfileStatus(
        subscription_plan=profile.subscription_plan,
        subscription_expires=profile.subscription_expires,
        daily_message_count=profile.daily_message_count
    )
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)