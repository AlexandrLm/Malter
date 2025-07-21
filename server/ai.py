import logging
import asyncio
from functools import partial
from google import genai
from google.genai import types as genai_types
from prompts import BASE_SYSTEM_PROMPT
from personality_prompts import PERSONALITIES
from config import MODEL_NAME
from server.database import (
    get_profile,
    UserProfile,
    save_long_term_memory,
    get_long_term_memories,
    save_chat_message,
    get_chat_history
)
from datetime import datetime
import pytz

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    client = genai.Client()
except Exception as e:
    logging.critical(f"Не удалось инициализировать Gemini Client: {e}")
    client = None

# --- Описание инструментов для модели ---
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
        "required": []
    }
}

def generate_user_prompt(profile: UserProfile):
    """Генерирует часть системного промпта с информацией о пользователе."""
    return (
        f"- Его зовут: {profile.name}.\n"
        f"- Его занятие: {profile.occupation}.\n"
        f"- Наше любимое общее дело: {profile.hobby}.\n"
        f"- Наше особенное место: {profile.place}.\n"
    )

async def generate_ai_response(user_id: int, user_message: str, timestamp: datetime) -> str:
    """
    Генерирует ответ AI с использованием `generate_content`, сохраняя и извлекая историю чата из БД.
    """
    logging.info(f"Получено сообщение от пользователя {user_id} в {timestamp}: '{user_message}'")
    if client is None:
        logging.error("Клиент Gemini не инициализирован.")
        return "Произошла критическая ошибка конфигурации. Попробуйте еще раз позже."
        
    try:
        profile = await get_profile(user_id)
        if not profile:
            logging.error(f"Профиль пользователя {user_id} не найден!")
            return "Ой, кажется, мы не знакомы. Нажми /start, чтобы начать общение."

        formatted_message = user_message
        if profile.timezone:
            try:
                user_timezone = pytz.timezone(profile.timezone)
                user_time = timestamp.astimezone(user_timezone)
                formatted_message = f"[Время моего сообщения: {user_time.strftime('%d.%m.%Y %H:%M')}] {user_message}"
            except pytz.UnknownTimeZoneError:
                logging.warning(f"Неизвестная таймзона '{profile.timezone}' для пользователя {user_id}")

        await save_chat_message(user_id, 'user', formatted_message)

        user_context = generate_user_prompt(profile)
        system_instruction = BASE_SYSTEM_PROMPT.format(user_context=user_context, PERSONALITIES=PERSONALITIES)
        
        history = await get_chat_history(user_id)
        
        tools = genai_types.Tool(function_declarations=[add_memory_function, get_memories_function])
        
        available_functions = {
            "save_long_term_memory": partial(save_long_term_memory, user_id),
            "get_long_term_memories": partial(get_long_term_memories, user_id),
        }

        while True:
            if not formatted_message:
                 contents = history
            else:
                 contents = history + [{"role": "user", "parts": [{"text": formatted_message}]}]

            response =client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
                config=genai_types.GenerateContentConfig(
                    tools=[tools],
                    system_instruction=system_instruction
                ),
            )

            if not response.candidates:
                logging.warning(f"Ответ от API для пользователя {user_id} не содержит кандидатов.")
                return "Я не могу ответить на это. Возможно, твой запрос нарушает политику безопасности."

            candidate = response.candidates[0]
            function_call = None
            if candidate.content and candidate.content.parts and hasattr(candidate.content.parts[0], 'function_call'):
                function_call = candidate.content.parts[0].function_call

            if not function_call:
                final_response = response.text.strip()
                logging.info(f"Сгенерирован ответ для пользователя {user_id}: '{final_response}'")
                await save_chat_message(user_id, 'model', final_response)
                return final_response

            function_name = function_call.name
            logging.info(f"Модель вызвала функцию: {function_name}")

            if function_name not in available_functions:
                logging.warning(f"Модель попыталась вызвать неизвестную функцию '{function_name}'")
                history.append({"role": "model", "parts": [{"text": f"Вызвана неизвестная функция: {function_name}"}]})
                formatted_message = "Произошла ошибка при вызове функции."
                continue

            function_to_call = available_functions[function_name]
            function_args = {key: value for key, value in function_call.args.items()}
            logging.info(f"Аргументы функции: {function_args}")

            function_response_data = await function_to_call(**function_args)
            logging.info(f"Результат функции '{function_name}': {function_response_data}")

            history.append({"role": "model", "parts": [genai_types.Part(function_call=function_call)]})
            history.append({
                "role": "function",
                "parts": [genai_types.Part(
                    function_response=genai_types.FunctionResponse(
                        name=function_name,
                        response=function_response_data,
                    )
                )]
            })
            formatted_message = "" 

    except Exception as e:
        logging.error(f"Ошибка при генерации ответа для пользователя {user_id}: {e}", exc_info=True)
        return "Произошла внутренняя ошибка. Попробуйте еще раз позже."