"""
Тестовый скрипт для проверки функциональности Эмоциональной памяти.

Использование:
    python test_emotional_memory.py
"""

import asyncio
import logging
from server.database import save_emotional_memory, get_emotional_memories

logging.basicConfig(level=logging.INFO)

async def test_emotional_memory():
    """Тестирует сохранение и получение эмоциональных воспоминаний."""
    
    test_user_id = 999999  # Тестовый пользователь
    
    print("\n" + "="*60)
    print("🧠 Тест эмоциональной памяти")
    print("="*60 + "\n")
    
    # 1. Сохранение тестовых эмоций
    print("📝 Сохранение тестовых эмоций...")
    
    test_emotions = [
        {"emotion": "happy", "intensity": 9, "context": "получил повышение на работе"},
        {"emotion": "sad", "intensity": 7, "context": "поссорился с другом"},
        {"emotion": "excited", "intensity": 10, "context": "узнал что еду в отпуск"},
        {"emotion": "anxious", "intensity": 6, "context": "предстоит важная встреча"},
        {"emotion": "grateful", "intensity": 8, "context": "друг помог с переездом"}
    ]
    
    for emo in test_emotions:
        result = await save_emotional_memory(
            test_user_id,
            emotion=emo["emotion"],
            intensity=emo["intensity"],
            context=emo["context"]
        )
        if result["status"] == "success":
            print(f"  ✅ Сохранено: {emo['emotion']} (intensity: {emo['intensity']})")
        elif result["status"] == "skipped":
            print(f"  ⏭️  Пропущено (дубликат): {emo['emotion']}")
        else:
            print(f"  ❌ Ошибка при сохранении: {emo['emotion']}")
    
    print()
    
    # 2. Получение эмоциональных воспоминаний
    print("🔍 Получение эмоциональных воспоминаний...")
    
    memories = await get_emotional_memories(test_user_id, limit=5)
    
    if not memories:
        print("  ❌ Эмоциональные воспоминания не найдены")
    else:
        print(f"  ✅ Найдено {len(memories)} эмоциональных воспоминаний:\n")
        for i, mem in enumerate(memories, 1):
            print(f"  {i}. {mem['emotion'].upper()} (интенсивность {mem['intensity']}/10)")
            print(f"     Контекст: {mem['context']}")
            print(f"     Время: {mem['timestamp']}")
            print()
    
    # 3. Проверка формата для промпта
    print("💬 Формат для injection в промпт:")
    print("-" * 60)
    if memories:
        emotions_text = "🧠 ЭМОЦИОНАЛЬНАЯ ПАМЯТЬ (важные эмоциональные моменты пользователя):\n"
        for mem in memories[:3]:  # Берем топ-3
            emotions_text += f"- {mem['emotion']} (интенсивность {mem['intensity']}/10): {mem['context']} ({mem['timestamp']})\n"
        emotions_text += "\nИспользуй эту информацию для эмпатии и контекста."
        print(emotions_text)
    print("-" * 60)
    
    print("\n✅ Тест завершен успешно!\n")
    print("📌 Примечание: Для production тестирования используй реального пользователя")
    print("   и проверь, как AI вызывает функцию save_emotional_memory автоматически.\n")

if __name__ == "__main__":
    asyncio.run(test_emotional_memory())
