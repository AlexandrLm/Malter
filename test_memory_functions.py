import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# Путь к модулям, которые мы будем тестировать
from server.database import save_long_term_memory, get_long_term_memories, init_db, async_session_factory
from server.models import LongTermMemory

# Используем pytest-asyncio для асинхронных тестов
pytestmark = pytest.mark.asyncio

# Фикстура для инициализации и очистки тестовой БД (in-memory SQLite)
@pytest.fixture(scope="function", autouse=True)
async def setup_database():
    # Убедимся, что используется тестовая БД в памяти
    from config import DATABASE_URL
    assert "sqlite" in DATABASE_URL, "Тесты должны запускаться на SQLite"
    
    await init_db()
    yield
    # Очистка после теста
    async with async_session_factory() as session:
        await session.execute(LongTermMemory.__table__.delete())
        await session.commit()

@patch('server.ai.client')
async def test_save_new_fact(mock_genai_client):
    """
    Тест: успешно сохраняется новый факт, которого еще нет в базе.
    """
    user_id = 100
    fact = "User loves cats"
    category = "pets"

    result = await save_long_term_memory(user_id, fact, category)

    assert result["status"] == "success"
    assert result["fact_saved"] == fact

    # Проверяем, что факт действительно сохранился в БД
    async with async_session_factory() as session:
        from sqlalchemy import select
        stmt = select(LongTermMemory).where(LongTermMemory.user_id == user_id)
        result = await session.execute(stmt)
        saved_fact = result.scalars().first()
        assert saved_fact is not None
        assert saved_fact.fact == fact

async def test_save_duplicate_fact():
    """
    Тест: сохранение дубликата факта пропускается.
    """
    user_id = 200
    fact = "User plays guitar"
    category = "hobbies"

    # Сначала сохраняем факт
    await save_long_term_memory(user_id, fact, category)

    # Пытаемся сохранить его еще раз
    result = await save_long_term_memory(user_id, fact, category)

    assert result["status"] == "skipped"
    assert result["reason"] == "duplicate fact"

    # Проверяем, что в базе только одна запись
    async with async_session_factory() as session:
        facts = await get_long_term_memories(user_id)
        assert len(facts["memories"]) == 1

async def test_get_memories():
    """
    Тест: получение сохраненных фактов для пользователя.
    """
    user_id = 300
    await save_long_term_memory(user_id, "Fact 1", "cat1")
    await asyncio.sleep(0.1) # небольшая задержка для сортировки по времени
    await save_long_term_memory(user_id, "Fact 2", "cat2")

    memories = await get_long_term_memories(user_id, limit=5)

    assert "memories" in memories
    assert len(memories["memories"]) == 2
    # Проверяем порядок (последний сохраненный - первый в списке)
    assert memories["memories"][0]["fact"] == "Fact 2"
    assert memories["memories"][1]["fact"] == "Fact 1"

async def test_get_memories_empty():
    """
    Тест: получение фактов для пользователя без сохраненных воспоминаний.
    """
    user_id = 404
    memories = await get_long_term_memories(user_id)
    assert len(memories["memories"]) == 0