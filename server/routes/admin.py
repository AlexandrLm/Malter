"""
Admin routes.
Administrative endpoints for monitoring, maintenance, and system health.
"""

import logging
import io
from fastapi import APIRouter, HTTPException, Request, Depends
from slowapi import Limiter

from server.api_schemas import CleanupResponse, TTSTestRequest, TTSTestResponse, MessageResponse
from server.api_helpers import verify_admin, get_limiter_key
from server.database import cleanup_old_chat_history
from server.tts import create_telegram_voice_message
from utils.db_monitoring import get_query_metrics
from utils.cache import get_cache_stats

# ============================================================================
# SETUP
# ============================================================================

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
limiter = Limiter(key_func=get_limiter_key)

logger = logging.getLogger(__name__)


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@router.get(
    "/db_metrics",
    summary="Database metrics",
    description="Return database performance metrics and slow queries (admin only).",
)
@limiter.limit("10/minute")
async def db_metrics_handler(
    request: Request,
    user_id: int = Depends(verify_admin)
):
    """
    Get database performance metrics.

    Args:
        request: FastAPI request (for rate limiting)
        user_id: Admin user ID from JWT token

    Returns:
        dict: Database metrics

    Raises:
        HTTPException: 500 if error occurs
    """
    try:
        logger.info(f"Admin {user_id} requested DB metrics")
        metrics = get_query_metrics()
        return {"db_metrics": metrics}
    except Exception as e:
        logger.error(f"Error fetching DB metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error fetching database metrics"
        )


@router.get(
    "/cache_stats",
    summary="Cache statistics",
    description="Return Redis cache usage statistics (admin only).",
)
@limiter.limit("10/minute")
async def cache_stats_handler(
    request: Request,
    user_id: int = Depends(verify_admin)
):
    """
    Get Redis cache statistics.

    Args:
        request: FastAPI request (for rate limiting)
        user_id: Admin user ID from JWT token

    Returns:
        dict: Cache statistics

    Raises:
        HTTPException: 500 if error occurs
    """
    try:
        logger.info(f"Admin {user_id} requested cache stats")
        stats = await get_cache_stats()
        return {"cache_stats": stats}
    except Exception as e:
        logger.error(f"Error fetching cache stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error fetching cache statistics"
        )


@router.get(
    "/scheduler_status",
    summary="Scheduler status",
    description="Return background job scheduler status (admin only).",
)
@limiter.limit("10/minute")
async def scheduler_status_handler(
    request: Request,
    user_id: int = Depends(verify_admin)
):
    """
    Get scheduler status and scheduled tasks.

    Args:
        request: FastAPI request (for rate limiting)
        user_id: Admin user ID from JWT token

    Returns:
        dict: Scheduler status

    Raises:
        HTTPException: 500 if error occurs
    """
    try:
        logger.info(f"Admin {user_id} requested scheduler status")
        from server.scheduler import get_scheduler_status
        status = get_scheduler_status()
        return {"scheduler": status}
    except Exception as e:
        logger.error(f"Error fetching scheduler status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error fetching scheduler status"
        )


@router.post(
    "/cleanup_chat_history",
    response_model=CleanupResponse,
    summary="Cleanup chat history",
    description="Delete chat history older than specified days (admin only).",
)
@limiter.limit("1/hour")
async def cleanup_chat_history_handler(
    request: Request,
    days_to_keep: int = 30,
    user_id: int = Depends(verify_admin)
):
    """
    Delete old chat history.
    This function is executed automatically by APScheduler.
    This endpoint is provided for manual execution if needed.

    Args:
        request: FastAPI request (for rate limiting)
        days_to_keep: Number of days of history to keep (1-365)
        user_id: Admin user ID from JWT token

    Returns:
        CleanupResponse: Number of deleted records

    Raises:
        HTTPException: 500 if error occurs
    """
    try:
        logger.warning(
            f"Admin {user_id} initiated manual chat history cleanup (keep {days_to_keep} days)"
        )
        count = await cleanup_old_chat_history(days_to_keep)
        logger.info(f"Cleanup completed: {count} records deleted")
        return CleanupResponse(deleted_count=count, days_kept=days_to_keep)
    except Exception as e:
        logger.error(f"Error during chat history cleanup: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error during chat history cleanup"
        )


@router.post(
    "/test_tts",
    response_model=TTSTestResponse,
    summary="Test TTS functionality",
    description="Test text-to-speech generation (admin only).",
)
@limiter.limit("5/minute")
async def test_tts_handler(
    request: Request,
    tts_request: TTSTestRequest,
    user_id: int = Depends(verify_admin)
):
    """
    Test TTS functionality.

    Args:
        request: FastAPI request (for rate limiting)
        tts_request: TTS test request with text
        user_id: Admin user ID from JWT token

    Returns:
        TTSTestResponse: TTS test result with voice data

    Raises:
        HTTPException: 500 if error occurs
    """
    try:
        logger.info(f"Admin {user_id} initiated TTS test")
        import base64

        voice_file_object = io.BytesIO()
        success = await create_telegram_voice_message(tts_request.text, voice_file_object)

        if success:
            voice_file_object.seek(0)
            voice_data = voice_file_object.read()
            logger.info(f"TTS test successful: {len(voice_data)} bytes generated")
            return TTSTestResponse(
                success=True,
                message="TTS working correctly",
                voice_size_bytes=len(voice_data),
                voice_data_base64=base64.b64encode(voice_data).decode('utf-8')
            )
        else:
            logger.warning("TTS test failed")
            return TTSTestResponse(
                success=False,
                message="TTS generation failed"
            )
    except Exception as e:
        logger.error(f"Error during TTS test: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error during TTS test"
        )
