"""
Модуль для инструментов AI (функций).
Содержит определения инструментов и логику их выполнения.
"""

import logging
import base64
from typing import Any, Callable
from functools import partial
from google.genai import types as genai_types

from server.database import (
    save_long_term_memory,
    get_long_term_memories,
    save_emotional_memory
)

logger = logging.getLogger(__name__)

# ============================================================================
# TOOL DEFINITIONS
# ============================================================================

add_memory_function = {
    "name": "save_long_term_memory",
    "description": "Сохрани НОВЫЙ факт о пользователе только если: явно просит запомнить, делится новой информацией или исправляет старую. НЕ используй для известных фактов.",
    "parameters": {
        "type": "object",
        "properties": {
            "fact": {
                "type": "string",
                "description": "Конкретный факт. Пример: 'любит чёрный кофе'"
            },
            "category": {
                "type": "string",
                "description": "Категория: preferences, memories, work, family, pets, health, hobbies"
            }
        },
        "required": ["fact", "category"]
    }
}

get_memories_function = {
    "name": "get_long_term_memories",
    "description": "Найди факты о пользователе по запросу. Используй когда информация не в контексте.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Поисковый запрос. Пример: 'работа', 'любимый цвет'"
            }
        },
        "required": ["query"]
    }
}

generate_image_function = {
    "name": "generate_image",
    "description": "Сгенери изображение по запросу пользователя только если это улучшит диалог.",
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Детальное описание изображения. Будь конкретен со стилем и содержанием."
            }
        },
        "required": ["prompt"]
    }
}

remember_emotion_function = {
    "name": "save_emotional_memory",
    "description": "Сохрани СИЛЬНУЮ эмоцию (7-10): happy, sad, angry, excited, anxious, proud. НЕ для слабых эмоций.",
    "parameters": {
        "type": "object",
        "properties": {
            "emotion": {
                "type": "string",
                "description": "Эмоция: happy, sad, angry, excited, anxious, frustrated, proud, scared, lonely, grateful"
            },
            "intensity": {
                "type": "integer",
                "description": "Интенсивность 1-10. Сохраняй только если 7+"
            },
            "context": {
                "type": "string",
                "description": "Причина эмоции. Пример: 'получил повышение'"
            }
        },
        "required": ["emotion", "intensity", "context"]
    }
}

ALL_TOOLS_DECLARATIONS = [
    add_memory_function,
    get_memories_function,
    generate_image_function,
    remember_emotion_function
]

# ============================================================================
# TOOL SERVICE
# ============================================================================

class ToolService:
    """Сервис для управления инструментами AI."""

    def __init__(self, user_id: int, gemini_client: Any):
        self.user_id = user_id
        self.gemini_client = gemini_client
        self.available_functions = {
            "save_long_term_memory": partial(save_long_term_memory, self.user_id),
            "get_long_term_memories": partial(get_long_term_memories, self.user_id),
            "generate_image": self._generate_image_wrapper,
            "save_emotional_memory": partial(save_emotional_memory, self.user_id),
        }

    async def _generate_image_wrapper(self, prompt: str) -> str:
        """Обертка для генерации изображения."""
        try:
            response = await self.gemini_client.aio.models.generate_content(
                model="gemini-2.5-flash-image-preview",
                contents=[prompt],
            )
            
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.inline_data is not None:
                        image_data = part.inline_data.data
                        image_b64 = base64.b64encode(image_data).decode('utf-8')
                        logger.debug(f"Image generated successfully for prompt: {prompt[:50]}...")
                        return image_b64
            
            raise ValueError("Image generation failed: No image data in response")
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            raise

    async def execute_tool(self, function_call: Any) -> tuple[Any, str | None]:
        """
        Выполняет инструмент, запрошенный моделью.
        
        Returns:
            tuple: (result_data, image_b64)
            image_b64 присутствует только если была вызвана генерация изображения.
        """
        function_name = function_call.name
        logger.debug(f"Модель вызвала функцию: {function_name}")

        if function_name not in self.available_functions:
            logger.warning(f"Модель попыталась вызвать неизвестную функцию '{function_name}'")
            return f"Error: Unknown function {function_name}", None

        function_to_call = self.available_functions[function_name]
        function_args = dict(function_call.args)
        logger.debug(f"Аргументы функции: {function_args}")

        try:
            result = await function_to_call(**function_args)
            
            image_b64 = None
            if function_name == "generate_image":
                image_b64 = result
                result = "Image generated successfully"

            return result, image_b64
        except Exception as e:
            logger.error(f"Error executing tool {function_name}: {e}", exc_info=True)
            return f"Error executing function: {str(e)}", None
