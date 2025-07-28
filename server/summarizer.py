# -*- coding: utf-8 -*-

"""
Модуль для создания и управления сводками (summaries) диалогов.
"""
import asyncio
import logging
from google.genai import types
from config import GEMINI_CLIENT, SUMMARY_THRESHOLD, MESSAGES_TO_SUMMARIZE_COUNT
from server.database import async_session_factory, get_unsummarized_messages, save_summary, delete_summarized_messages, get_latest_summary
from server.models import ChatHistory, ChatSummary

# Промпт для создания ПЕРВОЙ сводки
INITIAL_SUMMARY_PROMPT = (
    "Твоя задача — проанализировать предоставленный диалог и составить краткую, но исчерпывающую сводку на русском языке. "
    "Сводка должна быть написана в нейтральном тоне от третьего лица (например, 'пользователь спросил...', 'модель ответила...'). "
    "Представь, что ты готовишь краткий отчет для человека, который хочет быстро понять суть разговора, не читая его целиком."
    "\n\n"
    "## Ключевые моменты для включения в сводку:"
    "1.  **Основные темы:** О чем в целом шла речь? (например, 'Обсуждали планы на выходные, выбор фильма и проблемы с проектом на работе')."
    "2.  **Важные факты и детали:** Новые факты о пользователе, конкретные даты, имена, решения. (например, 'Пользователь упомянул, что его кота зовут Мурзик', 'Решили встретиться в субботу в 18:00')."
    "3.  **Эмоциональный фон:** Общее настроение диалога. Был ли пользователь рад, расстроен, задумчив? (например, 'Пользователь был воодушевлен предстоящей поездкой', 'Диалог носил шутливый характер')."
    "4.  **Ключевые вопросы и ответы:** Зафиксируй основные вопросы пользователя и полученные на них ответы."
    "\n"
    "## Требования к стилю:"
    "-   **Краткость:** Избегай дословных цитат. Пересказывай суть."
    "-   **Объективность:** Пиши отстраненно, как наблюдатель."
    "-   **Полнота:** Не упускай важные детали, которые могут понадобиться для продолжения диалога в будущем."
    "\n\n"
    "ДИАЛОГ ДЛЯ АНАЛИЗА:\n"
    "------\n"
    "{chat_history}\n"
    "------\n\n"
    "КРАТКАЯ СВОДКА ДИАЛОГА:"
)

# Промпт для ОБНОВЛЕНИЯ существующей сводки
CUMULATIVE_SUMMARY_PROMPT = (
    "Твоя задача — обновить существующую сводку диалога, интегрировав в нее информацию из новых сообщений. "
    "Итоговая сводка должна стать единым, цельным документом, полностью заменяющим старый. Сохрани всю важную информацию из предыдущей сводки и дополни ее новыми данными."
    "\n\n"
    "## Инструкции:"
    "1.  **Проанализируй 'ПРЕДЫДУЩУЮ СВОДКУ'**: Пойми основной контекст беседы до текущего момента."
    "2.  **Изучи 'НОВЫЕ СООБЩЕНИЯ'**: Определи, как они развивают, изменяют или дополняют диалог."
    "3.  **Создай 'ОБНОВЛЕННУЮ И ПОЛНУЮ СВОДКУ'**: "
    "   -   Объедини старую и новую информацию в связный рассказ от третьего лица."
    "   -   Если новая информация уточняет или отменяет старую, отрази это. (например, 'Изначально планировали встречу в субботу, но перенесли на воскресенье')."
    "   -   Придерживайся тех же принципов: фиксируй ключевые факты, темы, эмоциональный фон и решения."
    "\n\n"
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
    Генерирует и сохраняет новую накопительную сводку для пользователя,
    оставляя "буфер" из недавних сообщений.
    """
    # 1. Получаем ВСЕ сообщения, которые еще не вошли в сводку
    all_unsummarized_messages = await get_unsummarized_messages(user_id)

    # 2. Проверяем, достигнут ли порог для ЗАПУСКА суммирования
    if len(all_unsummarized_messages) < SUMMARY_THRESHOLD:
        logging.info(f"Недостаточно сообщений для сводки у user_id {user_id}. Накоплено: {len(all_unsummarized_messages)}/{SUMMARY_THRESHOLD}.")
        return None
    
    # 3. Берем для обработки только нужное количество сообщений с начала списка
    messages_to_summarize = all_unsummarized_messages[:MESSAGES_TO_SUMMARIZE_COUNT]
    
    # 4. Получаем предыдущую сводку (если она есть)
    latest_summary = await get_latest_summary(user_id)
    
    # 5. Форматируем историю для промпта, используя только `messages_to_summarize`
    new_messages_text = "\n".join([f"{msg.role}: {msg.content}" for msg in messages_to_summarize])
    
    if latest_summary:
        prompt = CUMULATIVE_SUMMARY_PROMPT.format(
            previous_summary=latest_summary.summary,
            new_messages=new_messages_text
        )
    else:
        prompt = INITIAL_SUMMARY_PROMPT.format(chat_history=new_messages_text)

    # 6. Вызываем Gemini для генерации сводки
    try:
        response = await client.aio.models.generate_content(
                                    model="gemma-3-27b-it", # Вы можете поменять модель на свою
                                    contents=prompt
                                    )
        summary_text = response.text.strip()
    except Exception as e:
        logging.error(f"Ошибка при генерации сводки для user_id {user_id}: {e}")
        return None

    # 7. Определяем ID последнего обработанного сообщения
    last_processed_message_id = messages_to_summarize[-1].id

    # 8. Сохраняем/обновляем сводку, указывая правильный ID
    await save_summary(user_id, summary_text, last_processed_message_id)
    
    # 9. Удаляем только те сообщения, которые вошли в сводку
    await delete_summarized_messages(user_id, last_processed_message_id)
    
    logging.info(
        f"Создана/обновлена сводка для user_id {user_id}. "
        f"Обработано и удалено: {len(messages_to_summarize)} сообщений. "
        f"Осталось в истории: {len(all_unsummarized_messages) - len(messages_to_summarize)} сообщений."
    )
    return summary_text
