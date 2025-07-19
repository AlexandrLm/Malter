from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from config import DATABASE_URL
from server.models import Base, UserProfile, LongTermMemory

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
    async with async_session_factory() as session:
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await session.execute(stmt)
        profile = result.scalars().first()
        
        if profile:
            profile.name = data['name']
            profile.occupation = data['occupation']
            profile.hobby = data['hobby']
            profile.place = data['place']
        else:
            profile = UserProfile(user_id=user_id, **data)
        
        session.add(profile)
        await session.commit()

async def delete_profile(user_id: int):
    async with async_session_factory() as session:
        await session.execute(delete(UserProfile).where(UserProfile.user_id == user_id))
        await session.commit()

async def save_long_term_memory(user_id: int, fact: str, category: str):
    async with async_session_factory() as session:
        memory = LongTermMemory(user_id=user_id, fact=fact, category=category)
        session.add(memory)
        await session.commit()
        return {"status": "success", "fact_saved": fact}

# server/database.py

# Измените тип возвращаемого значения для большей ясности
async def get_long_term_memories(user_id: int, limit: int = 20) -> dict:
    async with async_session_factory() as session:
        result = await session.execute(
            select(LongTermMemory)
            .where(LongTermMemory.user_id == user_id)
            .order_by(desc(LongTermMemory.timestamp))
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