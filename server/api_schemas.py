"""
API schemas for request/response validation.
Contains Pydantic models for all endpoints.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


# ============================================================================
# AUTHENTICATION SCHEMAS
# ============================================================================

class AuthRequest(BaseModel):
    """JWT token generation request"""
    user_id: int = Field(..., gt=0, description="Telegram user ID")

    class Config:
        json_schema_extra = {
            "example": {"user_id": 387393405}
        }


class AuthResponse(BaseModel):
    """JWT token generation response"""
    access_token: str
    token_type: str = "bearer"

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer"
            }
        }


# ============================================================================
# CHAT SCHEMAS
# ============================================================================

class ChatRequest(BaseModel):
    """Chat message request"""
    message: str = Field(..., min_length=1, max_length=4096, description="User message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")
    image_data: Optional[str] = Field(None, description="Base64 encoded image")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Привет! Как дела?",
                "timestamp": "2025-10-30T12:00:00",
                "image_data": None
            }
        }


class ChatResponse(BaseModel):
    """Chat response with optional voice message"""
    response_text: str
    voice_message: Optional[str] = None
    image_base64: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "response_text": "Привет! Дела хорошо, спасибо за вопрос!",
                "voice_message": None,
                "image_base64": None
            }
        }


class ChatHistory(BaseModel):
    """Chat history response"""
    user_id: int
    history: list

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 387393405,
                "history": []
            }
        }


# ============================================================================
# PROFILE SCHEMAS
# ============================================================================

class ProfileData(BaseModel):
    """User profile data"""
    user_id: int
    name: Optional[str] = None
    gender: Optional[str] = None
    timezone: Optional[str] = None
    relationship_level: int = 1
    relationship_score: int = 0
    subscription_plan: str = "free"
    subscription_expires: Optional[datetime] = None
    daily_message_count: int = 0

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 387393405,
                "name": "Alex",
                "gender": "male",
                "timezone": "Europe/Moscow",
                "relationship_level": 1,
                "relationship_score": 0,
                "subscription_plan": "free",
                "subscription_expires": None,
                "daily_message_count": 5
            }
        }


class ProfileUpdate(BaseModel):
    """Profile update request"""
    user_id: int = Field(..., gt=0)
    data: ProfileData

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 387393405,
                "data": {
                    "user_id": 387393405,
                    "name": "Alexander",
                    "gender": "male",
                    "timezone": "Europe/Moscow"
                }
            }
        }


class ProfileStatus(BaseModel):
    """User profile status"""
    subscription_plan: str
    subscription_expires: Optional[datetime] = None
    daily_message_count: int

    class Config:
        json_schema_extra = {
            "example": {
                "subscription_plan": "free",
                "subscription_expires": None,
                "daily_message_count": 5
            }
        }


# ============================================================================
# PREMIUM SCHEMAS
# ============================================================================

class PremiumActivateRequest(BaseModel):
    """Premium subscription activation request"""
    user_id: int = Field(..., gt=0)
    duration_days: int = Field(30, ge=1, le=365)
    charge_id: Optional[str] = Field(None, description="Payment provider charge ID")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 387393405,
                "duration_days": 30,
                "charge_id": "ch_1234567890"
            }
        }


class PremiumActivateResponse(BaseModel):
    """Premium activation response"""
    success: bool
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Премиум подписка активирована на 30 дней"
            }
        }


# ============================================================================
# ADMIN SCHEMAS
# ============================================================================

class CleanupRequest(BaseModel):
    """Chat history cleanup request"""
    days_to_keep: int = Field(30, ge=1, le=365)

    class Config:
        json_schema_extra = {
            "example": {"days_to_keep": 30}
        }


class CleanupResponse(BaseModel):
    """Cleanup response"""
    deleted_count: int
    days_kept: int

    class Config:
        json_schema_extra = {
            "example": {
                "deleted_count": 150,
                "days_kept": 30
            }
        }


class TTSTestRequest(BaseModel):
    """TTS testing request"""
    text: str = Field(
        "Привет! Это тест голосового сообщения.",
        min_length=1,
        max_length=1024
    )

    class Config:
        json_schema_extra = {
            "example": {"text": "Привет! Это тест голосового сообщения."}
        }


class TTSTestResponse(BaseModel):
    """TTS testing response"""
    success: bool
    message: str
    voice_size_bytes: Optional[int] = None
    voice_data_base64: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "TTS работает корректно",
                "voice_size_bytes": 12345,
                "voice_data_base64": "..."
            }
        }


# ============================================================================
# HEALTH CHECK SCHEMAS
# ============================================================================

class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str

    class Config:
        json_schema_extra = {
            "example": {"status": "ok"}
        }


class ServiceStatus(BaseModel):
    """Individual service status"""
    status: str
    message: str


class ReadyCheckResponse(BaseModel):
    """Readiness probe response"""
    database: ServiceStatus
    redis: ServiceStatus
    gemini: ServiceStatus
    overall: str

    class Config:
        json_schema_extra = {
            "example": {
                "database": {
                    "status": "healthy",
                    "message": "Connected"
                },
                "redis": {
                    "status": "healthy",
                    "message": "Connected, Circuit Breaker: CLOSED"
                },
                "gemini": {
                    "status": "healthy",
                    "message": "Client initialized, Circuit Breaker: CLOSED"
                },
                "overall": "healthy"
            }
        }


# ============================================================================
# MESSAGE RESPONSE SCHEMAS
# ============================================================================

class MessageResponse(BaseModel):
    """Generic message response"""
    message: str

    class Config:
        json_schema_extra = {
            "example": {"message": "Профиль успешно обновлен"}
        }


class ErrorResponse(BaseModel):
    """Error response"""
    detail: str

    class Config:
        json_schema_extra = {
            "example": {"detail": "Not found"}
        }
