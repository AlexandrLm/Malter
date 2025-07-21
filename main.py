import uvicorn
import logging
import os
import asyncio
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from pydantic import BaseModel

from server.database import init_db, get_profile, create_or_update_profile, delete_profile, delete_chat_history
from server.ai import generate_ai_response
from server.tts import create_telegram_voice_message
from server.schemas import ChatRequest, ChatResponse, ProfileData, ProfileUpdate


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Действия при старте
    print("Инициализация базы данных...")
    await init_db()
    print("База данных инициализирована.")
    yield
    # Действия при выключении
    print("Сервер выключается.")


app = FastAPI(
    title="MashaGPT Backend",
    lifespan=lifespan
)


@app.get("/")
async def read_root():
    return {"message": "MashaGPT Backend is running"}


@app.post("/chat", response_model=ChatResponse)
async def chat_handler(request: ChatRequest):
    try:
        response_text = await generate_ai_response(request.user_id, request.message, request.timestamp)
        
        voice_message_data = None
        if response_text.startswith('[VOICE]'):
            text_to_speak = response_text.replace('[VOICE]', '').strip()
            output_filename = f"voice_message_{request.user_id}.ogg"
            
            success = await asyncio.to_thread(create_telegram_voice_message, text_to_speak, output_filename)
            
            if success:
                with open(output_filename, "rb") as f:
                    voice_message_data = f.read()
                os.remove(output_filename)
            else:
                # Возвращаем текстовый ответ, если TTS не удался
                response_text = "Хо хотела записать голосовое, но что-то с телефоном... короче, я так по тебе соскучилась!"

        return ChatResponse(response_text=response_text, voice_message=voice_message_data)

    except Exception as e:
        logging.error(f"Ошибка в chat_handler для пользователя {request.user_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@app.get("/profile/{user_id}", response_model=ProfileData | None)
async def get_profile_handler(user_id: int):
    profile = await get_profile(user_id)
    if not profile:
        return None
    return ProfileData(**profile.to_dict())


@app.post("/profile")
async def create_or_update_profile_handler(request: ProfileUpdate):
    await create_or_update_profile(request.user_id, request.data.dict())
    return {"message": "Профиль успешно обновлен"}


@app.delete("/profile/{user_id}")
async def delete_profile_handler(user_id: int):
    await delete_profile(user_id)
    # Также удаляем историю чата пользователя
    await delete_chat_history(user_id)
    return {"message": "Профиль и история чата успешно удалены"}


# --- FSM для анкеты ---
class FSMState(BaseModel):
    state: str
    data: dict = {}

fsm_storage = {} # Просто словарь в памяти для простоты

@app.post("/fsm/state")
async def set_fsm_state(request: FSMState):
    fsm_storage[request.state] = request.data
    return {"message": "Состояние установлено"}

@app.get("/fsm/state/{user_id}")
async def get_fsm_state(user_id: int):
    return fsm_storage.get(user_id)

@app.delete("/fsm/state/{user_id}")
async def delete_fsm_state(user_id: int):
    if user_id in fsm_storage:
        del fsm_storage[user_id]
    return {"message": "Состояние удалено"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)