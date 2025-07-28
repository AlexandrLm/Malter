from datetime import datetime
from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.dialects.postgresql import insert

from config import DATABASE_URL
from server.models import Base, UserProfile, LongTermMemory, ChatHistory, ChatSummary

# Создаем асинхронный "движок" и фабрику сессий
async_engine = create_async_engine(DATABASE_URL)
async_session_factory = async_sessionmaker(async_engine)

# Функция для инициализации БД (создания таблицы)
async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# CRUD-операции
async def get_profile(user_id: int) -> UserProfile | None:
    async with async_session_factory() as session:
        result = await session.execute(select(UserProfile).where(UserProfile.user_id == user_id))
        return result.scalars().first()

async def create_or_update_profile(user_id: int, data: dict):
    """
    Атомарно создает или обновляет профиль пользователя, используя UPSERT.
    Примечание: эта реализация специфична для PostgreSQL.
    Для SQLite потребуется оставить старую логику "select-then-update".
    """
    async with async_session_factory() as session:
        # Создаем оператор insert
        stmt = insert(UserProfile).values(user_id=user_id, **data)
        
        # Указываем, что делать при конфликте по уникальному полю user_id
        stmt = stmt.on_conflict_do_update(
            index_elements=['user_id'],  # Поле, которое вызывает конфликт
            set_=data  # Обновляем поля из словаря data
        )
        
        await session.execute(stmt)
        await session.commit()

async def delete_profile(user_id: int):
    async with async_session_factory() as session:
        await session.execute(delete(UserProfile).where(UserProfile.user_id == user_id))
        await session.commit()

async def delete_chat_history(user_id: int):
    """Удаляет всю историю чата для пользователя."""
    async with async_session_factory() as session:
        await session.execute(delete(ChatHistory).where(ChatHistory.user_id == user_id))
        await session.commit()

async def delete_long_term_memory(user_id: int):
    async with async_session_factory() as session:
        await session.execute(delete(LongTermMemory).where(LongTermMemory.user_id == user_id))
        await session.commit()

async def save_long_term_memory(user_id: int, fact: str, category: str):
    """
    Сохраняет новый факт, только если точно такого же факта еще нет в базе.
    """
    async with async_session_factory() as session:
        # 1. Проверяем, существует ли уже такой факт
        stmt = select(LongTermMemory).where(
            LongTermMemory.user_id == user_id,
            LongTermMemory.fact == fact
        )
        result = await session.execute(stmt)
        existing_fact = result.scalars().first()
        
        # 2. Если факт уже существует, ничего не делаем и сообщаем об этом
        if existing_fact:
            print(f"Факт для user_id {user_id} уже существует: '{fact}'. Пропускаем сохранение.")
            # Возвращаем информацию, что факт не был сохранен, т.к. уже есть
            return {"status": "skipped", "reason": "duplicate fact"}

        # 3. Если факта нет, создаем и сохраняем его
        print(f"Сохранение нового факта для user_id {user_id}: '{fact}'")
        memory = LongTermMemory(user_id=user_id, fact=fact, category=category)
        session.add(memory)
        await session.commit()
        return {"status": "success", "fact_saved": fact}

# Измените тип возвращаемого значения для большей ясности
async def get_long_term_memories(user_id: int, limit: int = 20) -> dict:
    async with async_session_factory() as session:
        result = await session.execute(
            select(LongTermMemory)
            .where(LongTermMemory.user_id == user_id)
            .order_by(LongTermMemory.timestamp.desc())
            .limit(limit)
        )
        memories = result.scalars().all()

        # Преобразуем список объектов в список словарей
        formatted_memories = [
            {
                "fact": mem.fact,
                "category": mem.category,
                # Преобразуем timestamp в строку, чтобы он был JSON-сериализуемым
                "timestamp": str(mem.timestamp) 
            }
            for mem in memories
        ]

        # Возвращаем один словарь, как того ожидает API Gemini
        # Ключ "memories" поможет модели понять структуру данных
        return {"memories": formatted_memories}

async def save_chat_message(user_id: int, role: str, content: str):
    """Сохраняет сообщение в историю чата и запускает процесс суммирования."""
    async with async_session_factory() as session:
        message = ChatHistory(user_id=user_id, role=role, content=content)
        session.add(message)
        await session.commit()
    
    # После сохранения сообщения, пытаемся сгенерировать сводку.
    # Это можно сделать в фоновом режиме, чтобы не блокировать основной поток.
    # Например, с помощью asyncio.create_task()
    from server.summarizer import generate_summary
    import asyncio
    asyncio.create_task(generate_summary(user_id))

async def get_chat_history(user_id: int, limit: int = 10) -> list[dict]:
    """Извлекает историю чата для пользователя."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(ChatHistory)
            .where(ChatHistory.user_id == user_id)
            .order_by(ChatHistory.timestamp.desc())
            .limit(limit)
        )
        # Получаем сообщения и сразу разворачиваем, чтобы новые были в конце
        messages = result.scalars().all()[::-1]
        
        history = [
            {"role": msg.role, "parts": [{"text": msg.content}]}
            for msg in messages
        ]
        return history

async def get_latest_summary(user_id: int) -> ChatSummary | None:
    """Извлекает самую последнюю сводку для пользователя."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(ChatSummary)
            .where(ChatSummary.user_id == user_id)
            .order_by(ChatSummary.timestamp.desc())
            .limit(1)
        )
        return result.scalars().first()

async def get_unsummarized_messages(user_id: int) -> list[ChatHistory]:
    """
    Извлекает все сообщения пользователя, которые еще не были включены в сводку.
    """
    latest_summary = await get_latest_summary(user_id)
    last_message_id = latest_summary.last_message_id if latest_summary else 0

    async with async_session_factory() as session:
        result = await session.execute(
            select(ChatHistory)
            .where(
                ChatHistory.user_id == user_id,
                ChatHistory.id > last_message_id
            )
            .order_by(ChatHistory.timestamp.asc())
        )
        return result.scalars().all()

# async def save_summary(user_id: int, summary_text: str, last_message_id: int):
#     """Сохраняет новую сводку в базу данных."""
#     async with async_session_factory() as session:
#         summary = ChatSummary(
#             user_id=user_id,
#             summary=summary_text,
#             last_message_id=last_message_id
#         )
#         session.add(summary)
#         await session.commit()

async def save_summary(user_id: int, summary_text: str, last_message_id: int):
    """
    Атомарно создает или обновляет сводку для пользователя (UPSERT).
    Гарантирует, что у каждого пользователя будет только одна запись в таблице.
    """
    async with async_session_factory() as session:
        # Данные для вставки или обновления
        data = {
            "summary": summary_text,
            "last_message_id": last_message_id,
            "timestamp": datetime.now() # Явно обновляем время
        }
        
        # Создаем оператор insert
        stmt = insert(ChatSummary).values(user_id=user_id, **data)
        
        # Указываем, что делать при конфликте по уникальному полю user_id
        # Мы обновляем все поля из словаря `data`
        stmt = stmt.on_conflict_do_update(
            index_elements=['user_id'],  # Поле, которое вызывает конфликт
            set_=data  # Обновляемые поля
        )
        
        await session.execute(stmt)
        await session.commit()

async def delete_summarized_messages(user_id: int, last_message_id: int):
    """Удаляет сообщения, которые уже вошли в сводку."""
    async with async_session_factory() as session:
        await session.execute(
            delete(ChatHistory)
            .where(
                ChatHistory.user_id == user_id,
                ChatHistory.id <= last_message_id
            )
        )
        await session.commit()