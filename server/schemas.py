from pydantic import BaseModel
from datetime import datetime

class ChatRequest(BaseModel):
    user_id: int
    message: str


class ChatResponse(BaseModel):
    response_text: str
    voice_message: bytes | None = None

class ProfileData(BaseModel):
    name: str
    occupation: str
    hobby: str
    place: str

class ProfileUpdate(BaseModel):
    user_id: int
    data: ProfileData