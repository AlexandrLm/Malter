"""
Модуль для генерации ответов AI.

Этот файл содержит функции для взаимодействия с моделью Gemini,
генерации ответов на сообщения пользователей и обработки изображений.
"""

import logging
import asyncio
from functools import partial
from typing import Any
import base64
import io
from google.genai import types as genai_types
from google.genai.errors import APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from prompts import BASE_SYSTEM_PROMPT, PREMIUM_SYSTEM_PROMPT
from server.database import check_subscription_expiry
from personality_prompts import PERSONALITIES
from config import (
    CHAT_HISTORY_LIMIT, 
    MODEL_NAME, 
    GEMINI_CLIENT,
    MAX_AI_ITERATIONS,
    AI_THINKING_BUDGET,
    MAX_IMAGE_SIZE_MB
)
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


class AIResponseGenerator:
    """
    Класс для генерации AI ответов с улучшенной организацией кода.
    Инкапсулирует логику генерации ответов и управления состоянием.
    """
    
    def __init__(self, user_id: int, user_message: str, timestamp: datetime, image_data: str | None = None):
        """
        Инициализация генератора ответов.
        
        Args:
            user_id: ID пользователя
            user_message: Сообщение пользователя
            timestamp: Временная метка
            image_data: Опциональные данные изображения в base64
        """
        self.user_id = user_id
        self.user_message = user_message
        self.timestamp = timestamp
        self.image_data = image_data
        
        # Состояние генератора
        self.profile: UserProfile | None = None
        self.latest_summary: ChatSummary | None = None
        self.unsummarized_messages: list[ChatHistory] = []
        self.formatted_message: str = ""
        self.system_instruction: str = ""
        self.history: list[genai_types.Content] = []
        self.tools: genai_types.Tool | None = None
        self.available_functions: dict = {}
        
    async def _load_user_context(self) -> bool:
        """
        Загружает контекст пользователя из БД.
        
        Returns:
            True если профиль найден, False иначе
        """
        from server.database import get_user_context_data
        self.profile, self.latest_summary, self.unsummarized_messages = await get_user_context_data(self.user_id)
        return self.profile is not None
    
    async def _prepare_request_data(self) -> None:
        """Подготавливает данные для запроса к AI."""
        self.formatted_message = format_user_message(self.user_message, self.profile, self.timestamp)
        self.system_instruction = build_system_instruction(self.profile, self.latest_summary)
        # Передаем timestamp для сообщений пользователя
        await save_chat_message(self.user_id, 'user', self.formatted_message, timestamp=self.timestamp)
        
        image_part = await process_image_data(self.image_data, self.user_id)
        self.history = await prepare_chat_history(
            self.unsummarized_messages, 
            self.formatted_message, 
            image_part
        )
        
        self.tools = genai_types.Tool(
            function_declarations=[add_memory_function, get_memories_function, generate_image_function]
        )
        
        self.available_functions = {
            "save_long_term_memory": partial(save_long_term_memory, self.user_id),
            "get_long_term_memories": partial(get_long_term_memories, self.user_id),
            "generate_image": generate_image,
        }
    
    async def _process_iteration(self, iteration: int) -> tuple[bool, str | None, str | None]:
        """
        Обрабатывает одну итерацию генерации ответа.
        
        Args:
            iteration: Номер текущей итерации
            
        Returns:
            Tuple[should_continue, final_response, image_b64]
            - should_continue: True если нужна ещё одна итерация
            - final_response: Финальный ответ если готов
            - image_b64: base64 изображения если сгенерировано
        """
        response = await call_gemini_api_with_retry(
            user_id=self.user_id,
            model_name=MODEL_NAME,
            contents=self.history,
            tools=[self.tools],
            system_instruction=self.system_instruction,
            thinking_budget=AI_THINKING_BUDGET
        )
        
        # Проверка наличия кандидатов
        if not response.candidates:
            logging.warning(f"Ответ от API для пользователя {self.user_id} не содержит кандидатов.")
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                logging.error(
                    f"Запрос для {self.user_id} заблокирован: "
                    f"{response.prompt_feedback.block_reason_message}"
                )
                return False, "Я не могу ответить на это. Запрос был заблокирован.", None
            return False, "Я не могу ответить на это. Возможно, твой запрос нарушает политику безопасности.", None
        
        candidate = response.candidates[0]
        
        # Обработка вызовов функций
        tool_image = await manage_function_calls(
            response, 
            self.history, 
            self.available_functions, 
            self.user_id
        )
        if tool_image:
            return True, None, tool_image  # Продолжаем с изображением
        
        # Получаем финальный ответ
        final_response = await handle_final_response(response, self.user_id, candidate)
        
        # Логирование usage metadata
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            logging.debug(f"Gemini usage for user {self.user_id}: {response.usage_metadata}")
        
        return False, final_response, None  # Готово
    
    async def _save_response_and_trigger_analysis(self, final_response: str) -> None:
        """
        Сохраняет ответ и запускает фоновый анализ.
        
        Args:
            final_response: Финальный ответ для сохранения
        """
        logging.debug(f"Сгенерирован финальный ответ для пользователя {self.user_id}: '{final_response}'")
        # Не передаем timestamp для ответов модели - будет использоваться server_default из БД
        await save_chat_message(self.user_id, 'model', final_response)
        
        # Запускаем фоновую задачу анализа с обработкой ошибок
        from server.summarizer import generate_summary_and_analyze
        task = asyncio.create_task(generate_summary_and_analyze(self.user_id))
        task.add_done_callback(lambda t: _handle_background_task_error(t, self.user_id))
    
    async def generate(self) -> dict[str, str | None]:
        """
        Главный метод генерации ответа.
        
        Returns:
            Dict с ключами 'text' и 'image_base64'
        """
        # Валидация клиента
        if client is None:
            logging.error("Клиент Gemini не инициализирован.")
            return {
                "text": "Произошла критическая ошибка конфигурации. Попробуйте еще раз позже.",
                "image_base64": None
            }
        
        try:
            # Загрузка контекста
            if not await self._load_user_context():
                logging.error(f"Профиль пользователя {self.user_id} не найден!")
                return {
                    "text": "Ой, кажется, мы не знакомы. Нажми /start, чтобы начать общение.",
                    "image_base64": None
                }
            
            # Подготовка данных
            await self._prepare_request_data()
            
            # Итеративная генерация ответа
            image_b64 = None
            for iteration in range(MAX_AI_ITERATIONS):
                should_continue, final_response, tool_image = await self._process_iteration(iteration + 1)
                
                if tool_image:
                    image_b64 = tool_image
                    continue
                
                if final_response:
                    await self._save_response_and_trigger_analysis(final_response)
                    return {"text": final_response, "image_base64": image_b64}
            
            # Достигнут лимит итераций
            logging.warning(f"Достигнут лимит итераций ({MAX_AI_ITERATIONS}) для пользователя {self.user_id}.")
            return {
                "text": "Что-то я запуталась в своих мыслях... Попробуй спросить что-нибудь другое.",
                "image_base64": None
            }
            
        except Exception as e:
            logging.error(f"Ошибка при генерации ответа для пользователя {self.user_id}: {e}", exc_info=True)
            return {
                "text": "Произошла внутренняя ошибка. Попробуйте еще раз позже.",
                "image_base64": None
            }
        finally:
            # MEMORY LEAK FIX: Явно очищаем большие объекты для освобождения памяти
            self.history.clear()
            self.unsummarized_messages = []
            self.tools = None
            if self.available_functions:
                self.available_functions.clear()


def _handle_background_task_error(task: asyncio.Task, user_id: int) -> None:
    """
    Обработчик ошибок для фоновых задач.
    Логирует исключения, которые произошли в фоновых задачах.
    
    Args:
        task (asyncio.Task): Завершённая задача
        user_id (int): ID пользователя для контекста логирования
    """
    try:
        # Получаем результат задачи - если была ошибка, она будет выброшена
        task.result()
    except asyncio.CancelledError:
        logging.info(f"Фоновая задача анализа для пользователя {user_id} была отменена")
    except Exception as e:
        logging.error(
            f"Ошибка в фоновой задаче анализа для пользователя {user_id}: {e}",
            exc_info=True,
            extra={"user_id": user_id, "task_name": "generate_summary_and_analyze"}
        )

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

generate_image_function = {
    "name": "generate_image",
    "description": "Generate an image based on a text prompt. Use this tool when the user requests a picture, visualization, diagram, or any creative image to illustrate your response. Only use if it enhances the conversation meaningfully.",
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "A detailed, descriptive prompt for the image generation. Be specific about style, content, and details."
            }
        },
        "required": ["prompt"]
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

    voice_style = ""
    if profile.is_premium_active:
        # Dynamic voice style based on relationship level for premium surprise
        if profile.relationship_level >= 3:  # Intimate levels
            voice_style = "\nДля близких уровней отношений используй интимный стиль голоса: начинай с 'Say in a whisper:' перед текстом в [VOICE]."
        elif profile.relationship_level >= 2:  # Friends
            voice_style = "\nДля дружеских уровней используй энергичный стиль: 'Say excitedly:' в [VOICE]."
        else:
            voice_style = "\nДля начальных уровней используй нейтральный стиль: просто текст в [VOICE]."

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
        f"{voice_style}"
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
    # Используем новый property для проверки premium
    is_premium = profile.is_premium_active
    logging.debug(f"Building prompt for user {profile.user_id}: {'PREMIUM' if is_premium else 'BASE'} (plan: {profile.subscription_plan}, expires: {profile.subscription_expires})")

    user_context = generate_user_prompt(profile)
    if is_premium:
        system_instruction = PREMIUM_SYSTEM_PROMPT.format(user_context=user_context, personality=PERSONALITIES)
    else:
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
    
    SECURITY: Валидация размера ДО декодирования для предотвращения DoS атак через memory exhaustion.
    
    Args:
        image_data (str | None): Данные изображения в формате base64.
        user_id (int): Идентификатор пользователя.
        
    Returns:
        genai_types.Part | None: Объект Part с изображением или None, если изображение отсутствует или произошла ошибка.
    """
    MAX_IMAGE_SIZE = MAX_IMAGE_SIZE_MB * 1024 * 1024  # Конвертируем MB в байты
    # Base64 увеличивает размер на ~33%, поэтому умножаем на 1.4 для проверки
    MAX_BASE64_SIZE = MAX_IMAGE_SIZE * 1.4
    
    if not image_data:
        return None
    
    # SECURITY: Проверяем размер base64 строки ДО декодирования
    if len(image_data) > MAX_BASE64_SIZE:
        logging.warning(f"Base64 изображение слишком большое ({len(image_data)} символов, максимум {int(MAX_BASE64_SIZE)}) для пользователя {user_id}")
        return None
        
    try:
        image_bytes = base64.b64decode(image_data)
        image_size = len(image_bytes)
        
        # Дополнительная валидация размера после декодирования (double-check)
        if image_size > MAX_IMAGE_SIZE:
            logging.warning(f"Изображение слишком большое ({image_size} байт, максимум {MAX_IMAGE_SIZE} байт) для пользователя {user_id}")
            return None
        
        logging.debug(f"Обработка изображения размером {image_size} байт для пользователя {user_id}")
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


async def manage_function_calls(response: Any, history: list[genai_types.Content], available_functions: dict[str, Any], user_id: int) -> str | None:
    """
    Обрабатывает вызовы функций моделью Gemini.
    
    Args:
        response: Ответ от Gemini API.
        history (list[genai_types.Content]): Текущая история чата.
        available_functions (dict[str, Any]): Доступные функции.
        user_id (int): ID пользователя.
        
    Returns:
        str | None: Base64 image data if generate_image was called, else None.
    """
    if not response.function_calls:
        return None
    
    function_call = response.function_calls[0]
    function_name = function_call.name
    logging.debug(f"Модель вызвала функцию: {function_name}")

    if function_name not in available_functions:
        logging.warning(f"Модель попыталась вызвать неизвестную функцию '{function_name}'")
        history.append(genai_types.Content(role="model", parts=[genai_types.Part.from_text(text=f"Вызвана неизвестная функция: {function_name}")]))
        return None

    function_to_call = available_functions[function_name]
    function_args = dict(function_call.args)
    logging.debug(f"Аргументы функции: {function_args}")

    function_response_data = await function_to_call(**function_args)
    logging.debug(f"Результат функции '{function_name}': {function_response_data if function_name != 'generate_image' else 'Image generated'}")

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
    
    if function_name == "generate_image":
        return function_response_data
    return None


async def handle_final_response(response: Any, user_id: int, candidate: Any) -> str:
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


async def generate_ai_response(user_id: int, user_message: str, timestamp: datetime, image_data: str | None = None) -> dict[str, str | None]:
    """
    Генерирует ответ AI с использованием `generate_content`, сохраняя и извлекая историю чата из БД.
    Поддерживает обработку изображений.
    
    Использует класс AIResponseGenerator для лучшей организации кода.
    
    Args:
        user_id: ID пользователя
        user_message: Сообщение пользователя
        timestamp: Временная метка сообщения
        image_data: Опциональные данные изображения в base64
        
    Returns:
        Dict с ключами 'text' и 'image_base64'
    """
    logging.info(f"Получено сообщение от пользователя {user_id} в {timestamp}: '{user_message}'")
    
    generator = AIResponseGenerator(user_id, user_message, timestamp, image_data)
    return await generator.generate()

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
    logging.debug(f"Попытка вызова Gemini API для пользователя {user_id}")
    
    # Log system instruction and context for debugging
    system_log = system_instruction[:500] + "..." if len(system_instruction) > 500 else system_instruction
    logging.debug(f"Системная инструкция для пользователя {user_id}: {system_log}")
    
    context_parts = []
    for content in contents:
        role = content.role
        text_parts = [part.text for part in content.parts if hasattr(part, 'text') and part.text]
        if text_parts:
            text = " ".join(text_parts)[:200] + "..." if len(" ".join(text_parts)) > 200 else " ".join(text_parts)
            context_parts.append(f"{role}: {text}")
        else:
            context_parts.append(f"{role}: [no text, possibly image]")
    context_str = "\n".join(context_parts)
    logging.debug(f"Контекст, переданный в модель для пользователя {user_id}:\n{context_str}")
    
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
        
        # Log token usage for debugging
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            logging.debug(f"Потребление токенов для пользователя {user_id}: prompt={response.usage_metadata.prompt_token_count}, candidates={response.usage_metadata.candidates_token_count}")
        
        return response
    except APIError as e:
        logging.warning(f"Ошибка Gemini API для пользователя {user_id}: {e}. Повторная попытка...")
        raise
    except Exception as e:
        logging.error(f"Непредвиденная ошибка при вызове Gemini API для {user_id}: {e}", exc_info=True)
        raise


async def generate_image(prompt: str) -> str:
    """
    Generates an image using the Gemini preview model and returns base64 encoded data.
    
    Args:
        prompt (str): Text description for the image.
        
    Returns:
        str: Base64 encoded image data.
    """
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash-image-preview",
            contents=[prompt],
        )
        
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image_data = part.inline_data.data
                    image_b64 = base64.b64encode(image_data).decode('utf-8')
                    logging.debug(f"Image generated successfully for prompt: {prompt[:50]}...")
                    return image_b64
        
        raise ValueError("Image generation failed: No image data in response")
    except Exception as e:
        logging.error(f"Error generating image: {e}")
        raise
