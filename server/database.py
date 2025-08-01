from datetime import datetime, date
from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import json
from sqlalchemy.dialects.postgresql import insert
from config import DATABASE_URL, CHAT_HISTORY_LIMIT, REDIS_CLIENT
from server.models import Base, UserProfile, LongTermMemory, ChatHistory, ChatSummary

# Создаем асинхронный "движок" и фабрику сессий
async_engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,  # Количество соединений, которые будут оставаться открытыми в пуле
    max_overflow=10, # Максимальное количество "дополнительных" соединений сверх pool_size
    pool_timeout=30, # Время в секундах, которое можно ждать соединения перед тем, как выбросить ошибку
    pool_recycle=1800 # Время в секундах, через которое соединение будет пересоздано (для предотвращения проблем с "устаревшими" соединениями)
)
async_session_factory = async_sessionmaker(async_engine)

# --- Константы для кэширования ---
CACHE_TTL_SECONDS = 3600 # 1 час

def get_profile_cache_key(user_id: int) -> str:
    """Генерирует ключ для кэша профиля."""
    return f"profile:{user_id}"

# Функция для инициализации БД (создания таблицы)
async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# CRUD-операции
async def get_profile(user_id: int) -> UserProfile | None:
    """
    Получает профиль пользователя, используя кэширование в Redis.
    """
    if REDIS_CLIENT:
        cache_key = get_profile_cache_key(user_id)
        cached_profile_json = await REDIS_CLIENT.get(cache_key)
        if cached_profile_json:
            profile_data = json.loads(cached_profile_json)
            # Преобразуем строки с датами обратно в объекты date/datetime
            for key, value in profile_data.items():
                if isinstance(value, str):
                    try:
                        profile_data[key] = datetime.fromisoformat(value)
                    except (ValueError, TypeError):
                        try:
                            profile_data[key] = date.fromisoformat(value)
                        except (ValueError, TypeError):
                            pass
            return UserProfile(**profile_data)

    # Если в кэше нет, идем в БД
    async with async_session_factory() as session:
        result = await session.execute(select(UserProfile).where(UserProfile.user_id == user_id))
        profile = result.scalars().first()

    # Сохраняем в кэш, если профиль найден
    if profile and REDIS_CLIENT:
        profile_dict = profile.to_dict()
        # Конвертируем date/datetime в ISO строки для JSON
        for key, value in profile_dict.items():
            if isinstance(value, (datetime, date)):
                profile_dict[key] = value.isoformat()
        
        cache_key = get_profile_cache_key(user_id)
        await REDIS_CLIENT.set(cache_key, json.dumps(profile_dict), ex=CACHE_TTL_SECONDS)

    return profile

async def create_or_update_profile(user_id: int, data: dict):
    """
    Атомарно создает или обновляет профиль и инвалидирует кэш.
    """
    async with async_session_factory() as session:
        stmt = insert(UserProfile).values(user_id=user_id, **data)
        stmt = stmt.on_conflict_do_update(index_elements=['user_id'], set_=data)
        await session.execute(stmt)
        await session.commit()

    # Инвалидируем кэш
    if REDIS_CLIENT:
        cache_key = get_profile_cache_key(user_id)
        await REDIS_CLIENT.delete(cache_key)

async def delete_profile(user_id: int):
    """Удаляет профиль и инвалидирует кэш."""
    async with async_session_factory() as session:
        await session.execute(delete(UserProfile).where(UserProfile.user_id == user_id))
        await session.commit()

    # Инвалидируем кэш
    if REDIS_CLIENT:
        cache_key = get_profile_cache_key(user_id)
        await REDIS_CLIENT.delete(cache_key)

async def delete_chat_history(user_id: int):
    """Удаляет всю историю чата для пользователя."""
    async with async_session_factory() as session:
        await session.execute(delete(ChatHistory).where(ChatHistory.user_id == user_id))
        await session.commit()

async def delete_long_term_memory(user_id: int):
    async with async_session_factory() as session:
        await session.execute(delete(LongTermMemory).where(LongTermMemory.user_id == user_id))
        await session.commit()

async def delete_summary(user_id: int):
    async with async_session_factory() as session:
        await session.execute(delete(ChatSummary).where(ChatSummary.user_id == user_id))
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

        # 3. Если факта нет, сохраняем его
        print(f"Сохранение нового факта для user_id {user_id}")
        memory = LongTermMemory(
            user_id=user_id,
            fact=fact,
            category=category
        )
        session.add(memory)
        await session.commit()
        return {"status": "success", "fact_saved": fact}

async def get_long_term_memories(user_id: int, query: str) -> dict:
    """Выполняет поиск по ключевым словам в долгосрочной памяти."""
    print(f"Выполнение поиска по ключевым словам для user_id {user_id} с запросом: '{query}'")
    try:
        async with async_session_factory() as session:
            # Используем ilike для регистронезависимого поиска
            result = await session.execute(
                select(LongTermMemory).where(
                    LongTermMemory.user_id == user_id,
                    LongTermMemory.fact.ilike(f"%{query}%")
                ).order_by(desc(LongTermMemory.timestamp)).limit(5)
            )
            memories = result.scalars().all()

        if not memories:
            return {"memories": ["Поиск по ключевым словам не дал результатов."]}

        # Форматируем результат
        formatted_memories = [
            {
                "fact": mem.fact,
                "category": mem.category,
                "timestamp": str(mem.timestamp)
            }
            for mem in memories
        ]

        return {"memories": formatted_memories}

    except Exception as e:
        print(f"Ошибка при поиске по ключевым словам для user_id {user_id}: {e}")
        return {"status": "error", "reason": "keyword_search_failed"}

async def save_chat_message(user_id: int, role: str, content: str):
    """Сохраняет одно сообщение в историю чата и обновляет счетчик ежедневных сообщений."""
    today = date.today()
    async with async_session_factory() as session:
        # Обновляем счетчик ежедневных сообщений
        profile = await session.execute(select(UserProfile).where(UserProfile.user_id == user_id))
        profile = profile.scalars().first()
        
        if profile:
            # Если дата последнего сообщения отличается от сегодняшней, сбрасываем счетчик
            if profile.last_message_date != today:
                profile.daily_message_count = 1
                profile.last_message_date = today
            else:
                # Иначе увеличиваем счетчик
                profile.daily_message_count += 1
            
            session.add(profile)
        
        # Сохраняем сообщение в истории чата
        message = ChatHistory(user_id=user_id, role=role, content=content)
        session.add(message)
        
        await session.commit()

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

async def get_all_unsummarized_messages(user_id: int) -> list[ChatHistory]:
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

async def get_unsummarized_messages(user_id: int, limit: int = CHAT_HISTORY_LIMIT) -> list[ChatHistory]:
    """
    Извлекает сообщения пользователя, ограничено лимитом.
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
            .order_by(ChatHistory.timestamp.desc())
            .limit(limit)
        )
        messages = result.scalars().all()
        return messages[::-1]
    
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