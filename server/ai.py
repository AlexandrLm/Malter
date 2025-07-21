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

add_memory_function = {
    "name": "save_long_term_memory",
    "description": "Сохраняет НОВЫЙ важный факт о пользователе в долгосрочную память. Используй ТОЛЬКО когда: 1) Пользователь прямо просит запомнить что-то ('запомни, что...'), 2) Пользователь впервые делится личной информацией, 3) Пользователь исправляет/обновляет информацию о себе. НЕ используй для информации, которую ты уже знаешь или когда пользователь спрашивает 'что помнишь?'",
    "parameters": {
        "type": "object",
        "properties": {
            "fact": {
                "type": "string",
                "description": "Конкретный НОВЫЙ факт, который нужно запомнить. Например: 'пользователь любит черный кофе' или 'у пользователя родился котенок'."
            },
            "category": {
                "type": "string",
                "description": "Категория факта. Варианты: 'предпочтения', 'воспоминания', 'работа', 'семья', 'питомцы', 'здоровье', 'хобби'."
            }
        },
        "required": ["fact", "category"]
    }
}

get_memories_function = {
    "name": "get_long_term_memories",
    "description": "Извлекает из памяти ранее сохраненные факты о пользователе. Используй когда: 1) Нужно вспомнить конкретные детали, которых нет в текущем контексте, 2) Пользователь спрашивает о прошлых беседах или общих воспоминаниях, 3) Ты не уверена в детали, на которую ссылается пользователь. НЕ нужно использовать, если информация уже есть в текущей беседе.",
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Максимальное количество воспоминаний для извлечения (по умолчанию 20)."
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
                    system_instruction=system_instruction,
                    thinking_config=genai_types.ThinkingConfig(
                        include_thoughts=True,
                        thinking_budget=-1
                    )
                ),
            )
            logging.info(f"Сгенерирован ответ для пользователя {user_id}: '{response}'")

            if not response.candidates:
                logging.warning(f"Ответ от API для пользователя {user_id} не содержит кандидатов.")
                return "Я не могу ответить на это. Возможно, твой запрос нарушает политику безопасности."

            candidate = response.candidates[0]
            # Проверяем, есть ли текстовый ответ (модель может генерировать и текст, и функцию одновременно)
            text_response = None
            function_call = None
            
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    try:
                        # Проверяем текстовую часть
                        if hasattr(part, 'text') and part.text:
                            text_response = part.text.strip()
                    except AttributeError:
                        pass
                    
                    try:
                        # Проверяем вызов функции
                        if hasattr(part, 'function_call') and part.function_call:
                            function_call = part.function_call
                    except AttributeError:
                        pass

            # Если есть текстовый ответ и НЕТ вызова функции - возвращаем текст
            if text_response and not function_call:
                logging.info(f"Сгенерирован ответ для пользователя {user_id}: '{text_response}'")
                await save_chat_message(user_id, 'model', text_response)
                return text_response
            
            # Если есть и текст, и функция - НЕ возвращаем текст (это обычно thoughts)
            if text_response and function_call:
                logging.info(f"Модель сгенерировала текст и вызвала функцию. Текст (thoughts): '{text_response}'")
                # НЕ сохраняем этот текст - это внутренние размышления модели
            
            # Если нет вызова функции и нет текста
            if not function_call and not text_response:
                logging.warning(f"Ответ от API для {user_id} не содержит ни текста, ни вызова функции.")
                final_response = "Я не могу сейчас ответить. Попробуй переформулировать."
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

            # Добавляем вызов функции в историю
            history.append({"role": "model", "parts": [genai_types.Part(function_call=function_call)]})
            # Добавляем результат функции в историю
            history.append({
                "role": "function",
                "parts": [genai_types.Part(
                    function_response=genai_types.FunctionResponse(
                        name=function_name,
                        response=function_response_data,
                    )
                )]
            })
            
            # Продолжаем цикл для генерации финального ответа после функции
            # (не возвращаем text_response, так как это могли быть внутренние размышления)
            formatted_message = ""

    except Exception as e:
        logging.error(f"Ошибка при генерации ответа для пользователя {user_id}: {e}", exc_info=True)
        return "Произошла внутренняя ошибка. Попробуйте еще раз позже."