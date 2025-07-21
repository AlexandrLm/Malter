from sqlalchemy import BigInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func

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
    # Категория поможет в будущем фильтровать воспоминания
    category: Mapped[str] = mapped_column(nullable=True) 
    timestamp: Mapped[str] = mapped_column(server_default=func.now()) # sqlalchemy.sql.func

class ChatHistory(Base):
   __tablename__ = "chat_history"
   
   id: Mapped[int] = mapped_column(primary_key=True)
   user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
   role: Mapped[str] = mapped_column(nullable=False) # 'user' or 'model'
   content: Mapped[str] = mapped_column(nullable=False)
   timestamp: Mapped[str] = mapped_column(server_default=func.now())