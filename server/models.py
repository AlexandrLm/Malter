from sqlalchemy import BigInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

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

    def to_dict(self):
        return {
            "name": self.name,
            "occupation": self.occupation,
            "hobby": self.hobby,
            "place": self.place,
        }