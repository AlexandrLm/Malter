"""
Модуль для генерации ответов AI.

Этот файл содержит функции для взаимодействия с моделью Gemini,
генерации ответов на сообщения пользователей и обработки изображений.
"""

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
from config import CHAT_HISTORY_LIMIT, MODEL_NAME, GEMINI_CLIENT
from server.relationship_config import RELATIONSHIP_LEVELS_CONFIG
from server.database import (
    get_profile,
    UserProfile,
    save_long_term_memory,
    get_long_term_memories,
    save_chat_message,
    get_latest_summary,
    get_unsummarized_messages,
    ChatHistory,
    ChatSummary
)
import pytz
from datetime import datetime

# Глобальная переменная для клиента
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

def generate_user_prompt(profile: UserProfile) -> str:
    """
    Генерирует часть системного промпта с информацией о пользователе.
    
    Args:
        profile (UserProfile): Объект профиля пользователя.
        
    Returns:
        str: Сформированная часть системного промпта с информацией о пользователе.
    """
    level_config = RELATIONSHIP_LEVELS_CONFIG.get(profile.relationship_level)
    relationship_name = level_config.get("name", "Незнакомец")
    relationship_context = level_config.get("prompt_context", "")
    behavioral_rules = level_config.get("behavioral_rules", [])
    forbidden_topics = level_config.get("forbidden_topics", [])
    relationship_example = level_config.get("example_dialog", "")
        # Форматируем в строки для промпта
    rules_str = "\n".join([f"- {rule}" for rule in behavioral_rules])
    topics_str = ", ".join(forbidden_topics)

    return (
        f"Имя: {profile.name}.\n"
        f"Гендер: {profile.gender}.\n"
        f"ВАШИ ТЕКУЩИЕ ОТНОШЕНИЯ:\n"
        f"## Текущий уровень: {relationship_name}\n"
        f"## Описание: {relationship_context}\n"
        f"## Правила поведения на этом уровне:\n{rules_str}\n"
        f"## Запрещенные темы на этом уровне: {topics_str}\n"
        f"## Стиль для текущего уровня отношений ({relationship_name})\n"
        f"  {relationship_example}"
    )


def format_user_message(user_message: str, profile: UserProfile, timestamp: datetime) -> str:
    """
    Форматирует сообщение пользователя с учетом его временной зоны.
    
    Args:
        user_message (str): Исходное сообщение пользователя.
        profile (UserProfile): Профиль пользователя.
        timestamp (datetime): Временная метка сообщения.
        
    Returns:
        str: Отформатированное сообщение пользователя.
    """
    formatted_message = user_message
    if profile.timezone:
        try:
            user_timezone = pytz.timezone(profile.timezone)
            user_time = timestamp.astimezone(user_timezone)
            formatted_message = f"[{user_time.strftime('%d.%m.%Y %H:%M')}] {user_message}"
        except pytz.UnknownTimeZoneError:
            logging.warning(f"Неизвестная таймзона '{profile.timezone}' для пользователя {profile.user_id}")
    
    return formatted_message


def build_system_instruction(profile: UserProfile, latest_summary: ChatSummary | None) -> str:
    """
    Формирует системный промпт для AI.
    
    Args:
        profile (UserProfile): Профиль пользователя.
        latest_summary (ChatSummary | None): Последняя сводка чата.
        
    Returns:
        str: Сформированный системный промпт.
    """
    user_context = generate_user_prompt(profile)
    system_instruction = BASE_SYSTEM_PROMPT.format(user_context=user_context, personality=PERSONALITIES)

    # Добавляем сводку к системному промпту
    if latest_summary:
        summary_context = (
            "\n\nЭто краткая сводка вашего предыдущего долгого разговора. "
            "Используй ее, чтобы помнить контекст, но не ссылайся на нее прямо в ответе.\n"
            f"Сводка: {latest_summary.summary}"
        )
        system_instruction += summary_context
        
    return system_instruction


def create_history_from_messages(messages: list[ChatHistory]) -> list[genai_types.Content]:
    """
    Создает историю чата в формате, понятном для Gemini API.
    
    Args:
        messages (list[ChatHistory]): Список сообщений из базы данных.
        
    Returns:
        list[genai_types.Content]: История чата в формате Gemini API.
    """
    history = []
    for msg in messages:
        history.append(genai_types.Content(role=msg.role, parts=[genai_types.Part.from_text(text=msg.content)]))
    return history


async def process_image_data(image_data: str | None, user_id: int) -> genai_types.Part | None:
    """
    Обрабатывает данные изображения и возвращает объект Part для Gemini API.
    
    Args:
        image_data (str | None): Данные изображения в формате base64.
        user_id (int): Идентификатор пользователя.
        
    Returns:
        genai_types.Part | None: Объект Part с изображением или None, если изображение отсутствует или произошла ошибка.
    """
    if not image_data:
        return None
        
    try:
        image_bytes = base64.b64decode(image_data)
        logging.info(f"Обработка изображения размером {len(image_bytes)} байт для пользователя {user_id}")
        return genai_types.Part.from_bytes(
            data=image_bytes,
            mime_type='image/jpeg'
        )
    except Exception as e:
        logging.error(f"Ошибка обработки изображения для пользователя {user_id}: {e}", exc_info=True)
        return None


async def prepare_chat_history(unsummarized_messages: list[ChatHistory], formatted_message: str, image_part: genai_types.Part | None) -> list[genai_types.Content]:
    """
    Подготавливает историю чата для Gemini API, включая ограничение по лимиту и добавление текущего сообщения пользователя.
    
    Args:
        unsummarized_messages (list[ChatHistory]): Несуммаризированные сообщения из БД.
        formatted_message (str): Отформатированное сообщение пользователя.
        image_part (genai_types.Part | None): Часть с изображением, если есть.
        
    Returns:
        list[genai_types.Content]: Готовая история чата.
    """
    history = create_history_from_messages(unsummarized_messages[-CHAT_HISTORY_LIMIT:])
    
    user_parts = [genai_types.Part.from_text(text=formatted_message)]
    if image_part:
        user_parts.insert(0, image_part)
    
    history.append(genai_types.Content(role='user', parts=user_parts))
    return history


async def manage_function_calls(response, history: list[genai_types.Content], available_functions: dict, user_id: int) -> bool:
    """
    Обрабатывает вызовы функций моделью Gemini.
    
    Args:
        response: Ответ от Gemini API.
        history (list[genai_types.Content]): Текущая история чата.
        available_functions (dict): Доступные функции.
        user_id (int): ID пользователя.
        
    Returns:
        bool: True, если функция была вызвана и нужно продолжить итерацию, False иначе.
    """
    if not response.function_calls:
        return False
    
    function_call = response.function_calls[0]
    function_name = function_call.name
    logging.info(f"Модель вызвала функцию: {function_name}")

    if function_name not in available_functions:
        logging.warning(f"Модель попыталась вызвать неизвестную функцию '{function_name}'")
        history.append(genai_types.Content(role="model", parts=[genai_types.Part.from_text(text=f"Вызвана неизвестная функция: {function_name}")]))
        return True  # Продолжаем итерацию

    function_to_call = available_functions[function_name]
    function_args = dict(function_call.args)
    logging.info(f"Аргументы функции: {function_args}")

    function_response_data = await function_to_call(**function_args)
    logging.info(f"Результат функции '{function_name}': {function_response_data}")

    history.append(response.candidates[0].content)
    history.append(genai_types.Content(
        role="function",
        parts=[genai_types.Part(
            function_response=genai_types.FunctionResponse(
                name=function_name,
                response={"result": function_response_data},
            )
        )]
    ))
    
    return True  # Продолжаем итерацию


async def handle_final_response(response, user_id: int, candidate) -> str:
    """
    Обрабатывает финальный ответ от модели, включая fallback'ы для отсутствия текста.
    
    Args:
        response: Ответ от Gemini API.
        user_id (int): ID пользователя.
        candidate: Кандидат ответа.
        
    Returns:
        str: Финальный текст ответа.
    """
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
    
    return final_response


async def generate_ai_response(user_id: int, user_message: str, timestamp: datetime, image_data: str | None = None) -> str:
    """
    Генерирует ответ AI с использованием `generate_content`, сохраняя и извлекая историю чата из БД.
    Поддерживает обработку изображений.
    """
    logging.info(f"Получено сообщение от пользователя {user_id} в {timestamp}: '{user_message}'")
    if client is None:
        logging.error("Клиент Gemini не инициализирован.")
        return "Произошла критическая ошибка конфигурации. Попробуйте еще раз позже."

    try:
        # --- Параллельное извлечение данных из БД ---
        profile_task = get_profile(user_id)
        summary_task = get_latest_summary(user_id)
        messages_task = get_unsummarized_messages(user_id)

        profile, latest_summary, unsummarized_messages = await asyncio.gather(
            profile_task, summary_task, messages_task
        )
        # -----------------------------------------

        if not profile:
            logging.error(f"Профиль пользователя {user_id} не найден!")
            return "Ой, кажется, мы не знакомы. Нажми /start, чтобы начать общение."

        formatted_message = format_user_message(user_message, profile, timestamp)
        system_instruction = build_system_instruction(profile, latest_summary)
        await save_chat_message(user_id, 'user', formatted_message)
        
        image_part = await process_image_data(image_data, user_id)
        history = await prepare_chat_history(unsummarized_messages, formatted_message, image_part)
 
        tools = genai_types.Tool(function_declarations=[add_memory_function, get_memories_function])
        
        available_functions = {
            "save_long_term_memory": partial(save_long_term_memory, user_id),
            "get_long_term_memories": partial(get_long_term_memories, user_id),
        }

        max_iterations = 3  # Уменьшено для безопасности
        iteration_count = 0
        while iteration_count < max_iterations:
            iteration_count += 1
            contents = history

            response = await call_gemini_api_with_retry(
                user_id=user_id,
                model_name=MODEL_NAME,
                contents=contents,
                tools=[tools],
                system_instruction=system_instruction,
                thinking_budget=0
            )

            if not response.candidates:
                logging.warning(f"Ответ от API для пользователя {user_id} не содержит кандидатов.")
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    logging.error(f"Запрос для {user_id} заблокирован: {response.prompt_feedback.block_reason_message}")
                    return f"Я не могу ответить на это. Запрос был заблокирован."
                return "Я не могу ответить на это. Возможно, твой запрос нарушает политику безопасности."

            candidate = response.candidates[0]

            if await manage_function_calls(response, history, available_functions, user_id):
                continue
            
            final_response = await handle_final_response(response, user_id, candidate)

            # --- Единая точка сохранения и запуска анализа ---
            logging.info(f"Сгенерирован финальный ответ для пользователя {user_id}: '{final_response}'")
            await save_chat_message(user_id, 'model', final_response)
            
            from server.summarizer import generate_summary_and_analyze
            asyncio.create_task(generate_summary_and_analyze(user_id))
            # --------------------------------------------------

            # Log usage metadata for monitoring
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                logging.info(f"Gemini usage for user {user_id}: {response.usage_metadata}")

            return final_response

        logging.warning(f"Достигнут лимит итераций ({max_iterations}) для пользователя {user_id}.")
        return "Что-то я запуталась в своих мыслях... Попробуй спросить что-нибудь другое."

    except Exception as e:
        logging.error(f"Ошибка при генерации ответа для пользователя {user_id}: {e}", exc_info=True)
        return "Произошла внутренняя ошибка. Попробуйте еще раз позже."

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10), # Экспоненциальная задержка
    retry=retry_if_exception_type(APIError),
    reraise=True
)
async def call_gemini_api_with_retry(user_id: int, model_name: str, contents: list, tools: list, system_instruction: str, thinking_budget: int = 0):
    """
    Выполняет вызов к Gemini API с логикой повторных попыток.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя.
        model_name (str): Название модели для генерации.
        contents (list): Содержание запроса.
        tools (list): Список инструментов для использования моделью.
        system_instruction (str): Системная инструкция для модели.
        thinking_budget (int): Бюджет для "мышления" модели.
        
    Returns:
        response: Ответ от API Gemini.
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
                    thinking_budget=thinking_budget
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
