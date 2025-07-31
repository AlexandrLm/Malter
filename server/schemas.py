from pydantic import BaseModel
from datetime import datetime

class ChatRequest(BaseModel):
    user_id: int
    message: str
    timestamp: datetime
    image_data: str | None = None


class LevelUpInfo(BaseModel):
    new_level_name: str | None = None
    offer_subscription: bool = False

class ChatResponse(BaseModel):
    response_text: str
    voice_message: bytes | None = None
    level_up_info: LevelUpInfo | None = None

class ProfileData(BaseModel):
    name: str
    gender: str
    timezone: str | None = None

class ProfileUpdate(BaseModel):
    user_id: int
    data: ProfileData

class ChatHistory(BaseModel):
    user_id: int
    history: list[dict]