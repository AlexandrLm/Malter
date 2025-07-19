import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
import asyncio
import re
from functools import partial
from google import genai
from google.genai import types
from prompts import BASE_SYSTEM_PROMPT
# Импортируем все необходимые функции из database.py
from server.database import get_profile, UserProfile, save_long_term_memory, get_long_term_memories
from datetime import datetime, timedelta
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
            logging.error(f"Профиль пользователя {user_id} не найден!")
            raise ValueError("Профиль пользователя не найден для создания сессии!")

        user_context = generate_user_prompt(profile)
        personalized_prompt = BASE_SYSTEM_PROMPT.format(user_context=user_context)
        
        model = "gemini-2.5-flash"
        tools = types.Tool(function_declarations=[add_memory_function, get_memories_function])
        config = types.GenerateContentConfig(tools=[tools], system_instruction=personalized_prompt)
        
        # Создаем чат через новый SDK
        client = genai.Client()
        chat = client.chats.create(
            model=model,
            config=config
        )
        user_chat_sessions[user_id] = chat
        logging.info(f"Новая сессия чата для пользователя {user_id} успешно создана.")
        
    return user_chat_sessions[user_id]

async def generate_ai_response(user_id: int, user_message: str) -> str:
    logging.info(f"Получено сообщение от пользователя {user_id}: '{user_message}'")
    try:
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
            function_call = None
            try:
                function_call = response.candidates[0].content.parts[0].function_call
            except (IndexError, AttributeError):
                pass

            if not function_call:
                final_response = response.text.strip()
                logging.info(f"Сгенерирован ответ для пользователя {user_id}: '{final_response}'")
                return final_response

            function_name = function_call.name
            logging.info(f"Модель вызвала функцию: {function_name}")
            
            if function_name not in available_functions:
                logging.warning(f"Модель попыталась вызвать неизвестную функцию '{function_name}'")
                return f"Ошибка: модель попыталась вызвать неизвестную функцию '{function_name}'"

            function_to_call = available_functions[function_name]
            function_args = function_call.args
            logging.info(f"Аргументы функции: {dict(function_args)}")

            function_response = await function_to_call(**dict(function_args))
            logging.info(f"Результат функции '{function_name}': {function_response}")

            response = await asyncio.to_thread(
                chat_session.send_message,
                types.Part.from_function_response(
                    name=function_name,
                    response=function_response
                )
            )
            # Логируем текстовую часть ответа модели после вызова функции, если она есть
            if response.candidates and response.candidates[0].content.parts:
                 logging.info(f"Промежуточный ответ модели: '{response.candidates[0].content.parts[0].text}'")

    except Exception as e:
        logging.error(f"Ошибка при генерации ответа для пользователя {user_id}: {e}", exc_info=True)
        return "Произошла внутренняя ошибка. Попробуйте еще раз позже."