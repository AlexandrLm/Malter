import logging
import asyncio
import re
from functools import partial
from google import genai
from google.genai import types
from prompts import BASE_SYSTEM_PROMPT
# Импортируем все необходимые функции из database.py
from server.database import get_profile, UserProfile, save_long_term_memory, get_long_term_memories

# Словарь для хранения активных сессий чата с Gemini
user_chat_sessions = {}

add_memory_function = {
    "name": "save_long_term_memory",
    "description": "Сохраняет важный факт о пользователе или ваших отношениях в долгосрочную память. Используй эту функцию, когда пользователь прямо просит что-то запомнить или делится новой важной информацией о себе.",
    "parameters": {
        "type": "object",
        "properties": {
            "fact": {
                "type": "string",
                "description": "Конкретный факт, который нужно запомнить. Например: 'пользователь любит черный кофе' или 'первое свидание было в парке Горького'."
            },
            "category": {
                "type": "string",
                "description": "Категория факта, чтобы его было легче найти в будущем. Например: 'предпочтения', 'воспоминания', 'работа', 'семья'."
            }
        },
        "required": ["fact", "category"]
    }
}

get_memories_function = {
    "name": "get_long_term_memories",
    "description": "Извлекает из памяти ранее сохраненные факты (воспоминания) о пользователе. Используй эту функцию, чтобы освежить память о чем-то, что обсуждалось ранее, или чтобы найти релевантную информацию для ответа на вопрос пользователя.",
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Максимальное количество воспоминаний для извлечения. Если не указано, вернется 20."
            }
        },
        # "required" пустой, так как параметр 'limit' не является обязательным.
        # Модель может вызвать эту функцию и без него.
        "required": []
    }
}


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
        
        model = "gemini-2.5-flash"
        tools = types.Tool(function_declarations=[add_memory_function])
        config = types.GenerateContentConfig(tools=[tools])
        
        initial_history = [
            {'role': 'user', 'parts': [{'text': personalized_prompt}]},
            {'role': 'model', 'parts': [{'text': "Хорошо, я все поняла. Буду твоей девушкой Машей. Я так соскучилась..."}]}
        ]
        
        # Создаем чат через новый SDK
        client = genai.Client()
        chat = client.chats.create(
            model=model,
            history=initial_history,
            config=config
        )
        user_chat_sessions[user_id] = chat
        
    return user_chat_sessions[user_id]

async def generate_ai_response(user_id: int, user_message: str) -> str:
    chat_session = await get_or_create_chat_session(user_id)
    
    available_functions = {
        "save_long_term_memory": partial(save_long_term_memory, user_id),
        "get_long_term_memories": partial(get_long_term_memories, user_id),
    }

    # Отправляем первоначальное сообщение пользователя
    response = await asyncio.to_thread(
        chat_session.send_message, user_message
    )

    while True:
        # Ищем часть ответа, содержащую вызов функции
        function_call = None
        # Безопасная проверка наличия function_call
        try:
            function_call = response.candidates[0].content.parts[0].function_call
        except (IndexError, AttributeError):
            pass # function_call не найден, это обычный текстовый ответ

        if not function_call:
            # Если вызова функции нет, просто возвращаем текст. [2]
            return response.text.strip()

        # Если вызов функции есть:
        function_name = function_call.name
        
        if function_name not in available_functions:
            # На случай, если модель придумает несуществующую функцию
            return f"Ошибка: модель попыталась вызвать неизвестную функцию '{function_name}'"

        # Получаем реальную функцию Python из нашего словаря
        function_to_call = available_functions[function_name]
        # Извлекаем аргументы, которые предоставила модель
        function_args = function_call.args

        # Вызываем нашу функцию асинхронно
        # Важно: ваши функции `save_long_term_memory` и `get_long_term_memories`
        # тоже должны быть `async def`
        function_response = await function_to_call(**dict(function_args))

        # Отправляем результат выполнения функции обратно в чат
        response = await asyncio.to_thread(
            chat_session.send_message,
            # Оборачиваем ответ функции в объект Part
            types.Part.from_function_response(
                name=function_name,
                response=function_response
            )
        )
        # Цикл продолжится, и на следующей итерации мы получим уже текстовый ответ от модели