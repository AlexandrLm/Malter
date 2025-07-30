# -*- coding: utf-8 -*-

"""
Модуль для создания и управления сводками (summaries) диалогов.
"""
import asyncio
import logging
import json
from pydantic import BaseModel, Field
from google.genai import types
from config import GEMINI_CLIENT, SUMMARY_THRESHOLD, MESSAGES_TO_SUMMARIZE_COUNT
from server.database import get_unsummarized_messages, save_summary, delete_summarized_messages, get_profile, create_or_update_profile
from server.models import ChatHistory, ChatSummary
from server.relationship_logic import check_for_level_up

JSON_SUMMARY_AND_ANALYSIS_PROMPT = (
    "Твоя задача — выступить в роли психолога-аналитика и внимательно изучить предоставленный диалог. "
    "На основе анализа ты должен вернуть СТРОГО валидный JSON-объект без каких-либо лишних символов или текста до или после него. "
    "JSON должен иметь следующую структуру:\n"
    "{{\n"
    '  "new_summary": "Краткая, но исчерпывающая сводка диалога.",\n'
    '  "relationship_analysis": {{\n'
    '    "quality_score": <число от -5 до +10>,\n'
    '    "key_insight": "Ключевой вывод о динамике отношений."\n'
    "  }}\n"
    "}}\n\n"
    "## Инструкции по заполнению полей:\n\n"
    "### 1. `new_summary` (Сводка диалога):\n"
    "-   **Стиль:** Нейтральный, от третьего лица ('пользователь поделился...', 'модель предложила...').\n"
    "-   **Содержание:**\n"
    "    -   **Основные темы:** О чем шла речь? (например, 'Обсуждали проблемы на работе пользователя и планировали совместный просмотр фильма').\n"
    "    -   **Ключевые факты:** Новая информация о пользователе, его чувства, принятые решения. (например, 'Пользователь расстроен из-за ссоры с коллегой', 'Решили посмотреть комедию в субботу').\n"
    "    -   **Эмоциональный фон:** Общее настроение диалога (например, 'Диалог был напряженным, но закончился на позитивной ноте').\n"
    "-   **Цель:** Сводка должна помочь быстро понять контекст разговора, не читая его целиком.\n\n"
    "### 2. `relationship_analysis` (Анализ отношений):\n"
    "#### `quality_score` (Оценка качества общения):\n"
    "-   Это числовая оценка глубины и качества коммуникации в данном фрагменте диалога.\n"
    "-   **+10:** Очень глубокий, доверительный и эмоционально насыщенный диалог. Пользователь делится чем-то важным, модель оказывает поддержку.\n"
    "-   **+5:** Позитивный, дружелюбный диалог. Обмен мнениями, шутки, поддержка.\n"
    "-   **0:** Нейтральный или поверхностный обмен информацией. (например, 'какая погода?').\n"
    "-   **-2:** Небольшое недопонимание, холодность в общении.\n"
    "-   **-5:** Конфликт, явное раздражение или негатив со стороны пользователя.\n"
    "#### `key_insight` (Ключевой вывод):\n"
    "-   Краткий, но емкий вывод о том, что этот диалог говорит об отношениях между пользователем и моделью.\n"
    "-   **Примеры:**\n"
    "    -   'Пользователь начинает больше доверять модели, делясь личными переживаниями о работе.'\n"
    "    -   'Отношения становятся более теплыми и неформальными, появляются общие шутки.'\n"
    "    -   'Возникло небольшое недопонимание, но его удалось разрешить к концу диалога.'\n\n"
    "--- ДИАЛОГ ДЛЯ АНАЛИЗА ---\n"
    "{chat_history}\n"
    "--------------------------\n\n"
    "ВАЛИДНЫЙ JSON-ОТВЕТ:"
)

# Настраиваем Gemini API
client = GEMINI_CLIENT

# --- Pydantic схемы для надежного парсинга JSON ---
class RelationshipAnalysis(BaseModel):
    quality_score: int = Field(description="Оценка качества общения от -5 до +10.")
    key_insight: str = Field(description="Ключевой вывод об отношениях.")

class SummaryAndAnalysisResponse(BaseModel):
    new_summary: str = Field(description="Краткая сводка диалога.")
    relationship_analysis: RelationshipAnalysis

async def generate_summary_and_analyze(user_id: int) -> str | None:
    """
    Генерирует сводку, анализирует отношения и обновляет профиль пользователя.
    """
    all_unsummarized_messages = await get_unsummarized_messages(user_id)

    if len(all_unsummarized_messages) < SUMMARY_THRESHOLD:
        logging.info(f"Недостаточно сообщений для анализа у user_id {user_id}.")
        return None

    messages_to_analyze = all_unsummarized_messages[:MESSAGES_TO_SUMMARIZE_COUNT]
    chat_history_text = "\n".join([f"{msg.role}: {msg.content}" for msg in messages_to_analyze])

    prompt = JSON_SUMMARY_AND_ANALYSIS_PROMPT.format(chat_history=chat_history_text)

    try:
        # Используем Gemma-3 и убираем response_schema
        response = await client.aio.models.generate_content(
            model="gemma-3-27b-it",
            contents=prompt
        )
        
        # Возвращаемся к ручному парсингу JSON с усиленным логированием
        try:
            # Очищаем ответ от блоков кода Markdown
            cleaned_text = response.text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            
            analysis_data = json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            logging.error(f"Критическая ошибка парсинга JSON от Gemma-3 для user_id {user_id}: {e}\n--- ОТВЕТ МОДЕЛИ ---\n{response.text}\n--------------------")
            return None # Прерываем выполнение, если JSON невалидный

        new_summary = analysis_data.get("new_summary")
        relationship_analysis = analysis_data.get("relationship_analysis", {})
        quality_score = relationship_analysis.get("quality_score", 0)

        profile = await get_profile(user_id)
        if profile:
            await create_or_update_profile(user_id, {
                "relationship_score": profile.relationship_score + quality_score
            })

        last_processed_message_id = messages_to_analyze[-1].id
        await save_summary(user_id, new_summary, last_processed_message_id)
        await delete_summarized_messages(user_id, last_processed_message_id)

        await check_for_level_up(user_id)

        logging.info(f"Анализ для user_id {user_id} завершен. Очки: {quality_score}.")
        return new_summary

    except Exception as e:
        logging.error(f"Ошибка при анализе для user_id {user_id}: {e}")
        return None
