# -*- coding: utf-8 -*-

"""
Модуль для создания и управления сводками (summaries) диалогов.
"""
import asyncio
from google.genai import types
from config import GEMINI_CLIENT, SUMMARY_THRESHOLD
from server.database import async_session_factory, get_unsummarized_messages, save_summary, delete_summarized_messages, get_latest_summary
from server.models import ChatHistory, ChatSummary

# Промпт для создания ПЕРВОЙ сводки
INITIAL_SUMMARY_PROMPT = (
    "Ты — AI-ассистент, твоя задача — анализировать диалог и создавать из него краткую, но информативную сводку. "
    "Сводка должна быть написана от третьего лица и отражать ключевые факты, события, решения и эмоциональное состояние участников. "
    "Представь, что ты пишешь краткий отчет для человека, который хочет быстро понять суть долгого разговора.\n\n"
    "Вот диалог для анализа:\n"
    "------\n"
    "{chat_history}\n"
    "------\n"
    "Краткая сводка этого диалога:"
)

# Промпт для ОБНОВЛЕНИЯ существующей сводки
CUMULATIVE_SUMMARY_PROMPT = (
    "Ты — AI-ассистент. Ниже представлена предыдущая сводка диалога и новые сообщения после нее. "
    "Твоя задача — обновить сводку, интегрировав в нее информацию из новых сообщений, чтобы получился единый, актуальный пересказ всего диалога. "
    "Новая сводка должна полностью заменить старую, сохранив при этом важную информацию из нее.\n\n"
    "ПРЕДЫДУЩАЯ СВОДКА:\n"
    "------\n"
    "{previous_summary}\n"
    "------\n\n"
    "НОВЫЕ СООБЩЕНИЯ:\n"
    "------\n"
    "{new_messages}\n"
    "------\n\n"
    "ОБНОВЛЕННАЯ И ПОЛНАЯ СВОДКА ДИАЛОГА:"
)


# Настраиваем Gemini API
client = GEMINI_CLIENT

async def generate_summary(user_id: int) -> str | None:
    """
    Генерирует и сохраняет новую накопительную сводку для пользователя.
    """
    # 1. Получаем сообщения, которые еще не вошли в сводку
    messages = await get_unsummarized_messages(user_id)

    # Устанавливаем порог для создания сводки (например, 20 сообщений)
    if len(messages) < SUMMARY_THRESHOLD:
        return None

    # 2. Получаем предыдущую сводку
    latest_summary = await get_latest_summary(user_id)
    
    # 3. Форматируем историю и выбираем промпт
    new_messages_text = "\n".join([f"{msg.role}: {msg.content}" for msg in messages])
    
    if latest_summary:
        prompt = CUMULATIVE_SUMMARY_PROMPT.format(
            previous_summary=latest_summary.summary,
            new_messages=new_messages_text
        )
    else:
        prompt = INITIAL_SUMMARY_PROMPT.format(chat_history=new_messages_text)

    # 4. Вызываем gemma для генерации сводки
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemma-3-27b-it",
            contents=prompt,
        )
        summary_text = response.text
    except Exception as e:
        print(f"Ошибка при генерации сводки: {e}")
        return None

    # 5. Сохраняем новую сводку и удаляем старые сообщения
    last_message_id = messages[-1].id
    await save_summary(user_id, summary_text, last_message_id)
    await delete_summarized_messages(user_id, last_message_id)
    
    print(f"Создана/обновлена сводка и удалено {len(messages)} старых сообщений для пользователя {user_id}")
    return summary_text
