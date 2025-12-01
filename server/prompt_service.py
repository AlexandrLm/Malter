"""
Сервис для формирования промптов.
"""

import logging
from typing import List, Optional, Any

from config import (
    CHAT_HISTORY_LIMIT_FREE,
    CHAT_HISTORY_LIMIT_PREMIUM,
)
from prompts import BASE_SYSTEM_PROMPT, PREMIUM_SYSTEM_PROMPT
from personality_prompts import PERSONALITIES
from server.models import UserProfile, ChatSummary, ChatHistory, LongTermMemory

logger = logging.getLogger(__name__)

class PromptService:
    """Сервис для подготовки промптов и контекста."""

    def __init__(self, user: UserProfile):
        self.user = user

    def get_system_instruction(self, emotional_memories: List[LongTermMemory], chat_summary: Optional[ChatSummary]) -> str:
        """Формирует системную инструкцию для модели."""
        
        # 1. Базовый контекст пользователя
        user_context = (
            f"User: {self.user.name or 'Unknown'}\n"
            f"Relationship Level: {self.user.relationship_level}\n"
            f"Relationship Score: {self.user.relationship_score}"
        )

        # 2. Добавляем саммари предыдущих бесед
        if chat_summary:
            user_context += f"\n\nPrevious Context:\n{chat_summary.summary}"

        # 3. Добавляем эмоциональные воспоминания
        if emotional_memories:
            emotions_str = "\n".join([f"- {m.content} (Intensity: {m.intensity})" for m in emotional_memories])
            user_context += f"\n\nEmotional Context:\n{emotions_str}"

        # 4. Выбираем шаблон промпта
        base_prompt = PREMIUM_SYSTEM_PROMPT if self.user.is_premium_active else BASE_SYSTEM_PROMPT

        # 5. Подставляем переменные
        return base_prompt.format(
            personality=PERSONALITIES,
            user_context=user_context
        )

    def prepare_chat_history(self, history: List[ChatHistory]) -> List[dict]:
        """
        Подготавливает историю чата для Gemini API.
        Обрезает историю согласно лимитам подписки.
        """
        limit = CHAT_HISTORY_LIMIT_PREMIUM if self.user.is_premium_active else CHAT_HISTORY_LIMIT_FREE
        limited_history = history[-limit:]

        formatted_history = []
        for msg in limited_history:
            role = "user" if msg.is_user else "model"
            formatted_history.append({"role": role, "parts": [msg.content]})
        
        return formatted_history

    def format_user_message(self, message: str, image_data: Optional[dict] = None) -> List[Any]:
        """Формирует сообщение пользователя (текст + опционально картинка)."""
        parts = [message]
        if image_data:
            parts.append(image_data)
        return parts
