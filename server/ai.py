import logging
import asyncio
from google import genai

from prompts import BASE_SYSTEM_PROMPT
from server.database import get_profile, UserProfile

# Словарь для хранения активных сессий чата с Gemini
user_chat_sessions = {}

def generate_user_prompt(profile: UserProfile):
    return (
        f"- Его зовут: {profile.name}.\n"
        f"- Его занятие: {profile.occupation}.\n"
        f"- Наше любимое общее дело: {profile.hobby}.\n"
        f"- Наше особенное место: {profile.place}.\n"
    )

async def get_or_create_chat_session(user_id: int):
    if user_id not in user_chat_sessions:
        logging.info(f"Создание новой сессии чата для пользователя {user_id}")
        profile = await get_profile(user_id)
        if not profile:
            raise ValueError("Профиль пользователя не найден для создания сессии!")

        user_context = generate_user_prompt(profile)
        personalized_prompt = BASE_SYSTEM_PROMPT.format(user_context=user_context)
        
        model = "gemini-2.5-flash" # Используем обновленную и более подходящую модель
        
        initial_history = [
            {'role': 'user', 'parts': [{'text': personalized_prompt}]},
            {'role': 'model', 'parts': [{'text': "Хорошо, я все поняла. Буду твоей девушкой Машей. Я так соскучилась..."}]}
        ]
        
        # Создаем чат через новый SDK
        client = genai.Client()
        chat = client.chats.create(
            model=model,
            history=initial_history
        )
        user_chat_sessions[user_id] = chat
        
    return user_chat_sessions[user_id]

async def generate_ai_response(user_id: int, user_message: str) -> str:
    chat_session = await get_or_create_chat_session(user_id)
    
    # Отправляем сообщение в отдельном потоке
    response = await asyncio.to_thread(chat_session.send_message, message=user_message)
    response_text = response.text.strip()
    return response_text