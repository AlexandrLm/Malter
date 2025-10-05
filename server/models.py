"""
Модели базы данных для приложения.

Этот файл определяет модели SQLAlchemy, которые используются для взаимодействия с базой данных.
"""

from sqlalchemy import BigInteger, DateTime, Index, func, JSON, Date, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import TSVECTOR
from datetime import datetime, date

# Базовый класс для наших моделей
class Base(DeclarativeBase):
    """
    Базовый класс для всех моделей SQLAlchemy.
    """
    pass

# Модель пользователя для таблицы в БД
class UserProfile(Base):
    """
    Модель профиля пользователя.
    
    Attributes:
        id (int): Уникальный идентификатор записи.
        user_id (int): Уникальный идентификатор пользователя.
        name (str): Имя пользователя.
        gender (str): Пол пользователя.
        timezone (str): Временная зона пользователя.
        relationship_level (int): Уровень отношений с пользователем.
        relationship_score (int): Очки отношений с пользователем.
        level_unlocked_at (datetime): Дата и время разблокировки текущего уровня.
        subscription_plan (str): План подписки пользователя.
        subscription_expires (datetime): Дата истечения подписки.
        daily_message_count (int): Количество сообщений за день.
        last_message_date (date): Дата последнего сообщения.
    """
    __tablename__ = "user_profiles"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(nullable=True)
    gender: Mapped[str] = mapped_column(nullable=True)
    timezone: Mapped[str] = mapped_column(nullable=True)
    relationship_level: Mapped[int] = mapped_column(server_default='1', nullable=False)
    relationship_score: Mapped[int] = mapped_column(server_default='0', nullable=False)
    level_unlocked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    subscription_plan: Mapped[str] = mapped_column(String, server_default='free', nullable=False)
    subscription_expires: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    daily_message_count: Mapped[int] = mapped_column(server_default='0', nullable=False)
    last_message_date: Mapped[date] = mapped_column(Date, nullable=True)
    last_processed_payment_charge_id: Mapped[str] = mapped_column(String, nullable=True)
    
    __table_args__ = (
        Index('idx_subscription_expires', 'subscription_expires'),
        Index('idx_last_message_date', 'last_message_date'),
    )

    def to_dict(self):
        # Используем inspect, чтобы автоматически собирать все поля модели
        from sqlalchemy import inspect
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}
    
    @property
    def is_premium_active(self) -> bool:
        """
        Проверяет, активна ли премиум подписка пользователя.
        
        Returns:
            bool: True если подписка активна, False в противном случае.
        """
        from datetime import datetime, timezone
        return (
            self.subscription_plan == "premium" 
            and self.subscription_expires is not None
            and self.subscription_expires.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)
        )
    
class LongTermMemory(Base):
    """
    Модель долговременной памяти.
    
    Attributes:
        id (int): Уникальный идентификатор записи.
        user_id (int): Уникальный идентификатор пользователя.
        fact (str): Факт о пользователе.
        category (str): Категория факта.
        timestamp (datetime): Дата и время создания записи.
        fact_tsv (TSVECTOR): Полнотекстовый индекс для быстрого поиска.
    """
    __tablename__ = "long_term_memories"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fact: Mapped[str] = mapped_column(nullable=False)
    category: Mapped[str] = mapped_column(nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Полнотекстовый индекс для быстрого поиска (заполняется автоматически через trigger)
    fact_tsv: Mapped[TSVECTOR] = mapped_column(
        TSVECTOR,
        nullable=True,
        server_default=text("to_tsvector('russian', fact)")
    )
    
    __table_args__ = (
        Index('idx_long_term_memory_user_category', 'user_id', 'category'),
        # GIN индекс для полнотекстового поиска
        Index('idx_long_term_memory_fact_tsv', 'fact_tsv', postgresql_using='gin'),
    )

class ChatHistory(Base):
   """
   Модель истории чата.
   
   Attributes:
       id (int): Уникальный идентификатор записи.
       user_id (int): Уникальный идентификатор пользователя.
       role (str): Роль отправителя сообщения ('user' или 'model').
       content (str): Содержание сообщения.
       timestamp (datetime): Дата и время создания записи.
   """
   __tablename__ = "chat_history"
   
   id: Mapped[int] = mapped_column(primary_key=True)
   user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
   role: Mapped[str] = mapped_column(nullable=False) # 'user' or 'model'
   content: Mapped[str] = mapped_column(nullable=False)
   timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

   __table_args__ = (
       Index('idx_chat_history_user_id_timestamp', "user_id", "timestamp"),
   )

class ChatSummary(Base):
    """
    Модель сводки чата.
    
    Attributes:
        id (int): Уникальный идентификатор записи.
        user_id (int): Уникальный идентификатор пользователя.
        summary (str): Сводка чата.
        last_message_id (int): Идентификатор последнего сообщения, включенного в сводку.
        timestamp (datetime): Дата и время создания записи.
    """
    __tablename__ = "chat_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    summary: Mapped[str] = mapped_column(nullable=False)
    last_message_id: Mapped[int] = mapped_column(nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index('idx_chat_summary_user_id_timestamp', "user_id", "timestamp"),
    )