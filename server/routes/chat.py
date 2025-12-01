"""
Chat routes.
Message processing and chat history endpoints.
"""

import logging
import time
from fastapi import APIRouter, HTTPException, Request, Depends
from google import genai
from slowapi import Limiter
from prometheus_client import Counter, Histogram

from server.api_schemas import ChatRequest, ChatResponse, ChatHistory
from server.api_helpers import (
    verify_token,
    check_message_limits,
    handle_tts_generation,
    get_limiter_key
)
from server.database import get_unsummarized_messages
from server.ai import generate_ai_response
from server.dependencies import get_gemini_client

router = APIRouter(prefix="/api/v1", tags=["chat"])
limiter = Limiter(key_func=get_limiter_key)

logger = logging.getLogger(__name__)

CHAT_REQUESTS = Counter('chat_requests_total', 'Total number of chat requests')
CHAT_REQUESTS_DURATION = Histogram('chat_requests_duration_seconds', 'Duration of chat requests processing')
AI_RESPONSE_DURATION = Histogram('ai_response_duration_seconds', 'Duration of AI response generation')
TTS_GENERATION_DURATION = Histogram('tts_generation_duration_seconds', 'Duration of TTS generation')
VOICE_MESSAGES_GENERATED = Counter('voice_messages_generated_total', 'Total number of voice messages generated')

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Process chat message",
    description="Send user message and receive AI response. Requires JWT token in Authorization header.",
)
@limiter.limit("10/minute")
async def chat_handler(
    request: Request,
    chat: ChatRequest,
    user_id: int = Depends(verify_token),
    gemini_client: genai.Client = Depends(get_gemini_client)
):
    """
    Process incoming user message and generate AI response.
    User ID is extracted from JWT token for security.

    Args:
        request: FastAPI request (for rate limiting)
        chat: Chat request with message, timestamp, and optional image
        user_id: User ID from JWT token

    Returns:
        ChatResponse: Response with text and optional voice message

    Raises:
        HTTPException: 500 if internal error occurs
    """
    start_time = time.time()
    CHAT_REQUESTS.inc()

    logger.debug(f"Chat request from user {user_id}: {chat.message[:50]}...")

    try:
        limit_check = await check_message_limits(user_id)
        if not limit_check["allowed"]:
            logger.warning(f"User {user_id} hit message limit: {limit_check['message']}")
            CHAT_REQUESTS_DURATION.observe(time.time() - start_time)
            return ChatResponse(
                response_text=limit_check["message"],
                voice_message=None
            )

        ai_start_time = time.time()
        ai_response = await generate_ai_response(
            user_id=user_id,
            message=chat.message,
            image_data=chat.image_data,
            gemini_client=gemini_client
        )
        AI_RESPONSE_DURATION.observe(time.time() - ai_start_time)

        response_text = ai_response['text']
        image_base64 = ai_response.get('image_base64')

        tts_start_time = time.time()
        tts_result = await handle_tts_generation(user_id, response_text)
        if tts_result["voice_data"]:
            TTS_GENERATION_DURATION.observe(time.time() - tts_start_time)
            VOICE_MESSAGES_GENERATED.inc()

        processed_text = tts_result["text"]
        voice_message_data = tts_result["voice_data"]

        logger.info(f"Chat response generated for user {user_id} ({len(processed_text)} chars)")

        CHAT_REQUESTS_DURATION.observe(time.time() - start_time)
        return ChatResponse(
            response_text=processed_text,
            voice_message=voice_message_data,
            image_base64=image_base64
        )

    except Exception as e:
        logger.error(f"Error processing chat for user {user_id}: {str(e)}", exc_info=True)
        CHAT_REQUESTS_DURATION.observe(time.time() - start_time)
        raise HTTPException(
            status_code=500,
            detail="Error processing message"
        )


@router.get(
    "/chat_history/{user_id}",
    response_model=ChatHistory | None,
    summary="Get chat history",
    description="Return chat history for user by ID.",
)
async def get_chat_history_handler(user_id: int):
    """
    Get unsummarized chat history for user.

    Args:
        user_id: User ID

    Returns:
        ChatHistory: Chat history with messages or None

    Raises:
        HTTPException: 500 if error occurs
    """
    try:
        logger.debug(f"Fetching chat history for user {user_id}")
        chat_history = await get_unsummarized_messages(user_id)
        if not chat_history:
            logger.debug(f"No chat history found for user {user_id}")
            return None
        return ChatHistory(user_id=user_id, history=chat_history)
    except Exception as e:
        logger.error(f"Error fetching chat history for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error fetching chat history"
        )
