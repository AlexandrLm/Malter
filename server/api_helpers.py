"""
Helper functions for API routes.
Contains shared business logic, JWT handling, TTS processing, etc.
"""

import logging
import io
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import config
from server.database import get_profile, check_message_limit
try:
    from server.tts import create_telegram_voice_message
except ImportError:
    logging.warning("TTS module could not be imported (likely due to missing audioop). TTS disabled.")
    async def create_telegram_voice_message(text, file_obj):
        return False

security = HTTPBearer()
SECRET_KEY = config.JWT_SECRET
ALGORITHM = config.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = config.JWT_EXPIRE_MINUTES


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.

    Args:
        data: Dictionary containing token claims
        expires_delta: Token expiration time delta

    Returns:
        str: Encoded JWT token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    """
    Verify JWT token and extract user_id.

    Args:
        credentials: HTTP Bearer credentials

    Returns:
        int: User ID from token

    Raises:
        HTTPException: 401 if token is invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exception
        user_id: int = int(sub)
        if user_id is None:
            raise credentials_exception
    except JWTError as je:
        logging.error(f"JWT verification error: {str(je)}")
        raise credentials_exception
    return user_id


async def verify_admin(user_id: int = Depends(verify_token)) -> int:
    """
    Verify that user is an administrator.

    Args:
        user_id: User ID from JWT token

    Returns:
        int: User ID if admin

    Raises:
        HTTPException: 403 if user is not admin
    """
    if user_id not in config.ADMIN_USER_IDS:
        logging.warning(f"Unauthorized admin access attempt from user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user_id


def strip_voice_markers(text: str) -> str:
    """
    Remove [VOICE] marker and intonation description.

    Examples:
        '[VOICE]Saying with a smile: "Привет!"' -> 'Привет!'
        '[VOICE]Say sadly: Ой, Саш...' -> 'Ой, Саш...'

    Args:
        text: Text with potential voice markers

    Returns:
        str: Cleaned text without voice markers
    """
    text = text.replace('[VOICE]', '', 1).strip()

    if ':' in text:
        colon_idx = text.index(':')

        if '"' in text:
            quote_idx = text.index('"', colon_idx)
            between = text[colon_idx+1:quote_idx]
            if between.strip() == '':
                text = text[quote_idx+1:]
                if text.endswith('"'):
                    text = text[:-1]
        else:
            before_colon = text[:colon_idx].strip()
            if before_colon.lower().startswith('say'):
                text = text[colon_idx+1:].strip()

    return text.strip()


async def handle_tts_generation(user_id: int, response_text: str) -> dict:
    """
    Handle TTS generation for premium users if [VOICE] marker is present.

    Args:
        user_id: User ID
        response_text: Response text potentially containing [VOICE] marker

    Returns:
        dict: Dictionary containing:
            - 'text': The processed text (with or without voice markers)
            - 'voice_data': Base64-encoded voice message or None
    """
    profile = await get_profile(user_id)
    is_premium = profile and profile.is_premium_active
    logging.debug(
        f"TTS processing: premium={'enabled' if is_premium else 'disabled'} "
        f"for user {user_id} (plan: {profile.subscription_plan if profile else 'none'})"
    )

    voice_message_data = None
    has_voice_marker = response_text.startswith('[VOICE]')

    if has_voice_marker:
        if not is_premium:
            clean_text = strip_voice_markers(response_text)
            return {
                "text": clean_text,
                "voice_data": None
            }
        else:
            text_to_speak = response_text.replace('[VOICE]', '', 1).strip()
            voice_file_object = io.BytesIO()

            success = await create_telegram_voice_message(text_to_speak, voice_file_object)

            if success:
                voice_file_object.seek(0)
                voice_message_bytes = voice_file_object.read()
                voice_message_data = base64.b64encode(voice_message_bytes).decode('utf-8')
                logging.info(f"TTS generated successfully for user {user_id}: {len(voice_message_bytes)} bytes")
                return {
                    "text": text_to_speak,
                    "voice_data": voice_message_data
                }
            else:
                logging.warning(f"TTS generation failed for user {user_id}, sending text only")
                clean_text = strip_voice_markers(response_text)
                return {
                    "text": clean_text,
                    "voice_data": None
                }

    return {
        "text": response_text,
        "voice_data": None
    }


async def check_message_limits(user_id: int) -> dict:
    """
    Check if user has reached message limit.

    Args:
        user_id: User ID

    Returns:
        dict: Limit check result with 'allowed' and 'message' keys
    """
    limit_check = await check_message_limit(user_id)
    return limit_check


def get_limiter_key(request) -> str:
    """
    Get IP address for rate limiting.

    Args:
        request: FastAPI request object

    Returns:
        str: Client IP address
    """
    from slowapi.util import get_remote_address
    return get_remote_address(request)
