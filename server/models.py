from sqlalchemy import BigInteger, DateTime, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func
from datetime import datetime

# Базовый класс для наших моделей
class Base(DeclarativeBase):
    pass

# Модель пользователя для таблицы в БД
class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(nullable=True)
    occupation: Mapped[str] = mapped_column(nullable=True)
    hobby: Mapped[str] = mapped_column(nullable=True)
    place: Mapped[str] = mapped_column(nullable=True)
    timezone: Mapped[str] = mapped_column(nullable=True)

    def to_dict(self):
        return {
            "name": self.name,
            "occupation": self.occupation,
            "hobby": self.hobby,
            "place": self.place,
        }
    
class LongTermMemory(Base):
    __tablename__ = "long_term_memories"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fact: Mapped[str] = mapped_column(nullable=False)
    category: Mapped[str] = mapped_column(nullable=True) 
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class ChatHistory(Base):
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
    __tablename__ = "chat_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    summary: Mapped[str] = mapped_column(nullable=False)
    last_message_id: Mapped[int] = mapped_column(nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index('idx_chat_summary_user_id_timestamp', "user_id", "timestamp"),
    )