import asyncio
from datetime import datetime
import logging
from server.ai import generate_ai_response
from server.database import init_db, save_long_term_memory, get_long_term_memories

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_memory_scenarios():
    """Тестирует различные сценарии использования функций памяти"""
    
    # Инициализация БД
    await init_db()
    
    test_user_id = 999999  # Тестовый user_id
    
    print("\n=== ТЕСТ 1: Вопрос о воспоминаниях (НЕ должен вызывать save_memory) ===")
    response = await generate_ai_response(
        test_user_id, 
        "Что помнишь о моих кошках?",
        datetime.now()
    )
    print(f"Ответ: {response}")
    
    print("\n=== ТЕСТ 2: Просьба запомнить (ДОЛЖЕН вызвать save_memory) ===")
    response = await generate_ai_response(
        test_user_id,
        "Запомни, что у меня три собаки: Рекс, Бобик и Шарик",
        datetime.now()
    )
    print(f"Ответ: {response}")
    
    print("\n=== ТЕСТ 3: Новая информация без явной просьбы (МОЖЕТ вызвать save_memory) ===")
    response = await generate_ai_response(
        test_user_id,
        "Кстати, я переехал в Москву на прошлой неделе",
        datetime.now()
    )
    print(f"Ответ: {response}")
    
    print("\n=== ТЕСТ 4: Обычный разговор (НЕ должен вызывать save_memory) ===")
    response = await generate_ai_response(
        test_user_id,
        "Как твои дела?",
        datetime.now()
    )
    print(f"Ответ: {response}")
    
    print("\n=== ПРОВЕРКА СОХРАНЕННЫХ ВОСПОМИНАНИЙ ===")
    memories = await get_long_term_memories(test_user_id)
    print(f"Всего воспоминаний: {len(memories.get('memories', []))}")
    for i, memory in enumerate(memories.get('memories', []), 1):
        print(f"{i}. {memory['fact']} (категория: {memory['category']})")

if __name__ == "__main__":
    asyncio.run(test_memory_scenarios())