import logging
import asyncio
from functools import partial
import base64
import io
from google.genai import types as genai_types
from google.genai.errors import APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from prompts import BASE_SYSTEM_PROMPT
from personality_prompts import PERSONALITIES
from config import MODEL_NAME, GEMINI_CLIENT
from server.relationship_config import RELATIONSHIP_LEVELS_CONFIG
from server.database import (
    get_profile,
    UserProfile,
    save_long_term_memory,
    get_long_term_memories,
    save_chat_message,
    get_latest_summary,
    get_unsummarized_messages
)
from datetime import datetime
import pytz

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

client = GEMINI_CLIENT

add_memory_function = {
    "name": "save_long_term_memory",
    "description": "Saves a NEW, important fact about the user. Use ONLY when: user explicitly asks to remember, shares new personal info, or corrects existing info. AVOID using for known facts or questions like 'what do you remember?'.",
    "parameters": {
        "type": "object",
        "properties": {
            "fact": {
                "type": "string",
                "description": "The specific NEW fact to save. Example: 'user likes black coffee'."
            },
            "category": {
                "type": "string",
                "description": "Category: 'preferences', 'memories', 'work', 'family', 'pets', 'health', 'hobbies'."
            }
        },
        "required": ["fact", "category"]
    }
}

get_memories_function = {
    "name": "get_long_term_memories",
    "description": "Searches for specific facts about the user using a query. Use when you need details not in the current context (e.g., user asks 'what do you remember about my job?'). Formulate a query that captures the essence of the question.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to find relevant facts. Example: 'user's job' or 'favorite color'."
            }
        },
        "required": ["query"]
    }
}

def generate_user_prompt(profile: UserProfile):
    """Генерирует часть системного промпта с информацией о пользователе."""
    relationship_level = RELATIONSHIP_LEVELS_CONFIG.get(profile.relationship_level, {}).get("prompt_context", "")
    return (
        f"Имя: {profile.name}.\n"
        f"Гендер: {profile.gender}.\n"
        f"ВАШИ ТЕКУЩИЕ ОТНОШЕНИЯ: {relationship_level}.\n"
    )

async def generate_ai_response(user_id: int, user_message: str, timestamp: datetime, image_data: str | None = None) -> str:
    """
    Генерирует ответ AI с использованием `generate_content`, сохраняя и извлекая историю чата из БД.
    Поддерживает обработку изображений.
    """
    logging.info(f"Получено сообщение от пользователя {user_id} в {timestamp}: '{user_message}'")
    if client is None:
        logging.error("Клиент Gemini не инициализирован.")
        return "Произошла критическая ошибка конфигурации. Попробуйте еще раз позже."

    uploaded_file = None
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
                formatted_message = f"[{user_time.strftime('%d.%m.%Y %H:%M')}] {user_message}"
            except pytz.UnknownTimeZoneError:
                logging.warning(f"Неизвестная таймзона '{profile.timezone}' для пользователя {user_id}")


        user_context = generate_user_prompt(profile)
        
        # Получаем контекст отношений
        # relationship_level = profile.relationship_level
        # relationship_context = RELATIONSHIP_LEVELS_CONFIG.get(relationship_level, {}).get("prompt_context", "")
        
        system_instruction = BASE_SYSTEM_PROMPT.format(user_context=user_context, personality=PERSONALITIES)
        # system_instruction += f"\n\n# ВАШИ ТЕКУЩИЕ ОТНОШЕНИЯ\n{relationship_context}"
        

        # Получаем сводку и ДОБАВЛЯЕМ ее к системному промпту, а не в историю
        latest_summary = await get_latest_summary(user_id)
        if latest_summary:
            summary_context = (
                "Это краткая сводка вашего предыдущего долгого разговора. "
                "Используй ее, чтобы помнить контекст, но не ссылайся на нее прямо в ответе.\n"
                f"Сводка: {latest_summary.summary}"
            )
            system_instruction += summary_context # Добавляем к основной инструкции

        # Получаем сообщения, которые еще не вошли в сводку
        unsummarized_messages = await get_unsummarized_messages(user_id)

        # Форматируем и добавляем их в историю (без системного сообщения!)
        history = []
        for msg in unsummarized_messages:
            history.append(genai_types.Content(role=msg.role, parts=[genai_types.Part.from_text(text=msg.content)]))

        user_parts = [genai_types.Part.from_text(text=formatted_message)]
        if image_data:
            try:
                image_bytes = base64.b64decode(image_data)
                logging.info(f"Обработка изображения размером {len(image_bytes)} байт для пользователя {user_id}")
                image_part = genai_types.Part.from_bytes(
                    data=image_bytes,
                    mime_type='image/jpeg'
                )
                user_parts.insert(0, image_part) # Вставляем картинку перед текстом
            except Exception as e:
                logging.error(f"Ошибка обработки изображения для пользователя {user_id}: {e}", exc_info=True)
                return "Ой, не могу посмотреть на твою картинку, что-то пошло не так."
        
        history.append(genai_types.Content(role='user', parts=user_parts))
        await save_chat_message(user_id, 'user', formatted_message)

       
        tools = genai_types.Tool(function_declarations=[add_memory_function, get_memories_function])
        
        available_functions = {
            "save_long_term_memory": partial(save_long_term_memory, user_id),
            "get_long_term_memories": partial(get_long_term_memories, user_id),
        }

        max_iterations = 5
        iteration_count = 0
        while iteration_count < max_iterations:
            iteration_count += 1
            contents = history

            print(contents)
            print(system_instruction)

            response = await call_gemini_api_with_retry(
                user_id=user_id,
                model_name=MODEL_NAME,
                contents=contents,
                tools=[tools],
                system_instruction=system_instruction
            )
            logging.info(f"Сгенерирован ответ для пользователя {user_id}: '{response}'")

            if not response.candidates:
                logging.warning(f"Ответ от API для пользователя {user_id} не содержит кандидатов.")
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    logging.error(f"Запрос для {user_id} заблокирован: {response.prompt_feedback.block_reason_message}")
                    return f"Я не могу ответить на это. Запрос был заблокирован."
                return "Я не могу ответить на это. Возможно, твой запрос нарушает политику безопасности."

            candidate = response.candidates[0]

            if response.function_calls:
                function_call = response.function_calls[0]
                function_name = function_call.name
                logging.info(f"Модель вызвала функцию: {function_name}")

                if function_name not in available_functions:
                    logging.warning(f"Модель попыталась вызвать неизвестную функцию '{function_name}'")
                    history.append({"role": "model", "parts": [{"text": f"Вызвана неизвестная функция: {function_name}"}]})
                    formatted_message = "Произошла ошибка при вызове функции."
                    continue

                function_to_call = available_functions[function_name]
                function_args = dict(function_call.args)
                logging.info(f"Аргументы функции: {function_args}")

                function_response_data = await function_to_call(**function_args)
                logging.info(f"Результат функции '{function_name}': {function_response_data}")

                history.append(candidate.content)
                history.append(genai_types.Content(
                    role="function",
                    parts=[genai_types.Part(
                        function_response=genai_types.FunctionResponse(
                            name=function_name,
                            response={"result": function_response_data},
                        )
                    )]
                ))
                
                formatted_message = ""
                continue
            
            else:
                # Этот блок теперь обрабатывает и response.text, и другие причины завершения
                final_response = ""
                if response.text:
                    final_response = response.text.strip()
                else:
                    finish_reason = candidate.finish_reason.name
                    logging.warning(f"Ответ от API для {user_id} не содержит текста. Причина: {finish_reason}")
                    if finish_reason == 'MAX_TOKENS':
                        final_response = "Ой, я так увлеклась, что мысль не поместилась в одно сообщение. Спроси еще раз, я попробую ответить короче."
                    elif finish_reason == 'SAFETY':
                        final_response = "Я не могу обсуждать эту тему, прости. Давай сменим тему?"
                    else:
                        final_response = "Я не могу сейчас ответить. Попробуй переформулировать."

                # --- Единая точка сохранения и запуска анализа ---
                logging.info(f"Сгенерирован финальный ответ для пользователя {user_id}: '{final_response}'")
                await save_chat_message(user_id, 'model', final_response)
                
                from server.summarizer import generate_summary_and_analyze
                asyncio.create_task(generate_summary_and_analyze(user_id))
                # --------------------------------------------------

                return final_response

        logging.warning(f"Достигнут лимит итераций ({max_iterations}) для пользователя {user_id}.")
        return "Что-то я запуталась в своих мыслях... Попробуй спросить что-нибудь другое."

    except Exception as e:
        logging.error(f"Ошибка при генерации ответа для пользователя {user_id}: {e}", exc_info=True)
        return "Произошла внутренняя ошибка. Попробуйте еще раз позже."
    finally:
        # Гарантированное удаление файла после использования
        if uploaded_file:
            try:
                logging.info(f"Удаление файла {uploaded_file.name} для пользователя {user_id}...")
                await asyncio.to_thread(client.files.delete, name=uploaded_file.name)
                logging.info(f"Файл {uploaded_file.name} успешно удален.")
            except Exception as e:
                logging.error(f"Не удалось удалить файл {uploaded_file.name}: {e}", exc_info=True)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10), # Экспоненциальная задержка
    retry=retry_if_exception_type(APIError),
    reraise=True
)
async def call_gemini_api_with_retry(user_id: int, model_name: str, contents: list, tools: list, system_instruction: str):
    """
    Выполняет вызов к Gemini API с логикой повторных попыток.
    """
    logging.info(f"Попытка вызова Gemini API для пользователя {user_id}")
    try:
        response = await client.aio.models.generate_content(
            model=model_name,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                tools=tools,
                system_instruction=system_instruction,
                thinking_config=genai_types.ThinkingConfig(
                    thinking_budget=512
                )
            )
        )
        return response
    except APIError as e:
        logging.warning(f"Ошибка Gemini API для пользователя {user_id}: {e}. Повторная попытка...")
        raise
    except Exception as e:
        logging.error(f"Непредвиденная ошибка при вызове Gemini API для {user_id}: {e}", exc_info=True)
        raise