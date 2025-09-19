from pydantic import BaseModel
from datetime import datetime


class ChatRequest(BaseModel):
    """
    Модель запроса для обработки чат-сообщения.
    
    Attributes:
        user_id (int): Уникальный идентификатор пользователя.
        message (str): Текст сообщения пользователя.
        timestamp (datetime): Временная метка сообщения.
        image_data (str | None): Данные изображения в формате base64 (опционально).
    """
    user_id: int
    message: str
    timestamp: datetime
    image_data: str | None = None


class LevelUpInfo(BaseModel):
    """
    Модель информации о повышении уровня.
    
    Attributes:
        new_level_name (str | None): Название нового уровня (опционально).
        offer_subscription (bool): Предложение подписки.
    """
    new_level_name: str | None = None
    offer_subscription: bool = False


class ChatResponse(BaseModel):
    """
    Модель ответа на чат-сообщение.
    
    Attributes:
        response_text (str): Текст ответа.
        voice_message (str | None): Голосовое сообщение в формате base64 string (опционально).
        level_up_info (LevelUpInfo | None): Информация о повышении уровня (опционально).
    """
    response_text: str
    voice_message: str | None = None
    level_up_info: LevelUpInfo | None = None


class ProfileData(BaseModel):
    """
    Модель данных профиля пользователя.
    
    Attributes:
        name (str): Имя пользователя.
        gender (str): Пол пользователя.
        timezone (str | None): Временная зона пользователя (опционально).
    """
    name: str
    gender: str
    timezone: str | None = None


class ProfileUpdate(BaseModel):
    """
    Модель запроса для создания или обновления профиля.
    
    Attributes:
        user_id (int): Уникальный идентификатор пользователя.
        data (ProfileData): Данные профиля пользователя.
    """
    user_id: int
    data: ProfileData


class ChatHistory(BaseModel):
    """
    Модель истории чата пользователя.
    
    Attributes:
        user_id (int): Уникальный идентификатор пользователя.
        history (list[dict]): История чата в виде списка словарей.
    """
    user_id: int
    history: list[dict]


class ProfileStatus(BaseModel):
    """
    Модель статуса профиля пользователя.
    
    Attributes:
        subscription_plan (str): План подписки пользователя.
        subscription_expires (datetime | None): Дата истечения подписки (опционально).
        daily_message_count (int): Количество сообщений за день.
    """
    subscription_plan: str
    subscription_expires: datetime | None = None
    daily_message_count: int