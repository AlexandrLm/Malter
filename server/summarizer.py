# -*- coding: utf-8 -*-

"""
Модуль для создания и управления сводками (summaries) диалогов.
"""
import asyncio
import logging
import json
from pydantic import BaseModel, Field
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from sqlalchemy.exc import SQLAlchemyError
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
    '    "quality_score": <число от -5 до +5>,\n'
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
    "-   **+5:** Очень глубокий, доверительный и эмоционально насыщенный диалог. Пользователь делится чем-то важным, модель оказывает поддержку.\n"
    "-   **+2:** Позитивный, дружелюбный диалог. Обмен мнениями, шутки, поддержка.\n"
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

def parse_summary_json(response_text: str, user_id: int) -> dict | None:
    """
    Парсит JSON из ответа модели, с очисткой Markdown и валидацией через Pydantic.
    
    Args:
        response_text (str): Текст ответа от модели.
        user_id (int): ID пользователя для логирования.
        
    Returns:
        dict | None: Распарсенные данные или None при ошибке.
    """
    try:
        # Очищаем ответ от блоков кода Markdown
        cleaned_text = response_text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]
        
        analysis_data = json.loads(cleaned_text)
        
        # Валидация через Pydantic
        validated = SummaryAndAnalysisResponse.model_validate(analysis_data)
        return validated.model_dump()
        
    except json.JSONDecodeError as e:
        logging.error(f"Ошибка парсинга JSON для user_id {user_id}: {e}\n--- ОТВЕТ МОДЕЛИ ---\n{response_text}\n--------------------")
        return None
    except ValueError as e:  # Pydantic validation error
        logging.error(f"Ошибка валидации JSON для user_id {user_id}: {e}")
        return None


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
        
        # Log usage metadata for monitoring
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            logging.info(f"Gemini summarizer usage for user {user_id}: {response.usage_metadata}")
        
        analysis_data = parse_summary_json(response.text, user_id)
        if not analysis_data:
            logging.warning(f"Не удалось распарсить анализ для user_id {user_id}. Пропускаем обновление.")
            return None

        new_summary = analysis_data.get("new_summary")
        relationship_analysis = analysis_data.get("relationship_analysis", {})
        quality_score = relationship_analysis.get("quality_score", 0)

        # Критичные операции с БД - выполняем с retry
        await _update_profile_and_summary_with_retry(
            user_id=user_id,
            quality_score=quality_score,
            new_summary=new_summary,
            last_message_id=messages_to_analyze[-1].id
        )

        await check_for_level_up(user_id)

        logging.info(f"Анализ для user_id {user_id} завершен. Очки: {quality_score}.")
        return new_summary

    except Exception as e:
        logging.error(f"Ошибка при анализе для user_id {user_id}: {e}", exc_info=True)
        return None

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(SQLAlchemyError),
    reraise=True
)
async def _update_profile_and_summary_with_retry(
    user_id: int,
    quality_score: int,
    new_summary: str,
    last_message_id: int
) -> None:
    """
    Критичные операции с БД с retry механизмом.
    Гарантирует атомарность: либо все операции выполнятся, либо ни одна.
    
    Args:
        user_id: ID пользователя
        quality_score: Оценка качества общения
        new_summary: Текст сводки
        last_message_id: ID последнего обработанного сообщения
    """
    try:
        # 1. Обновляем профиль с новым score
        profile = await get_profile(user_id)
        if profile:
            await create_or_update_profile(user_id, {
                "relationship_score": profile.relationship_score + quality_score
            })
        
        # 2. Сохраняем сводку
        await save_summary(user_id, new_summary, last_message_id)
        
        # 3. Удаляем обработанные сообщения
        await delete_summarized_messages(user_id, last_message_id)
        
        logging.info(f"Профиль и сводка успешно обновлены для user_id {user_id}")
    except SQLAlchemyError as e:
        logging.error(f"Ошибка БД при обновлении профиля/сводки для user_id {user_id}: {e}", exc_info=True)
        raise  # Будет повторная попытка через retry
    except Exception as e:
        logging.error(f"Неожиданная ошибка при обновлении для user_id {user_id}: {e}", exc_info=True)
        raise
