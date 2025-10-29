"""
Profile routes.
User profile management endpoints.
"""

import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from slowapi import Limiter

from server.api_schemas import (
    ProfileData,
    ProfileUpdate,
    ProfileStatus,
    MessageResponse
)
from server.api_helpers import verify_token, get_limiter_key
from server.database import (
    get_profile,
    create_or_update_profile,
    delete_profile,
    delete_chat_history,
    delete_long_term_memory,
    delete_summary,
    check_subscription_expiry
)

# ============================================================================
# SETUP
# ============================================================================

router = APIRouter(prefix="/api/v1", tags=["profile"])
limiter = Limiter(key_func=get_limiter_key)

logger = logging.getLogger(__name__)


# ============================================================================
# PROFILE ENDPOINTS
# ============================================================================

@router.get(
    "/profile/{user_id}",
    response_model=ProfileData | None,
    summary="Get user profile",
    description="Return user profile data by user ID.",
)
async def get_profile_handler(user_id: int):
    """
    Get user profile data.

    Args:
        user_id: User ID

    Returns:
        ProfileData | None: User profile or None if not found

    Raises:
        HTTPException: 500 if error occurs
    """
    try:
        logger.debug(f"Fetching profile for user {user_id}")
        profile = await get_profile(user_id)
        if not profile:
            logger.debug(f"Profile not found for user {user_id}")
            return None
        return ProfileData(**profile.to_dict())
    except Exception as e:
        logger.error(f"Error fetching profile for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error fetching profile"
        )


@router.get(
    "/profile/status/{user_id}",
    response_model=ProfileStatus,
    summary="Get profile status",
    description="Return profile status including subscription plan and daily message count.",
)
async def get_profile_status_handler(user_id: int):
    """
    Get user profile status (subscription and limits).

    Args:
        user_id: User ID

    Returns:
        ProfileStatus: Profile status

    Raises:
        HTTPException: 404 if profile not found, 500 if error occurs
    """
    try:
        logger.debug(f"Fetching profile status for user {user_id}")
        profile = await get_profile(user_id)
        if not profile:
            logger.warning(f"Profile not found for user {user_id}")
            raise HTTPException(status_code=404, detail="Profile not found")

        return ProfileStatus(
            subscription_plan=profile.subscription_plan,
            subscription_expires=profile.subscription_expires,
            daily_message_count=profile.daily_message_count
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching profile status for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error fetching profile status"
        )


@router.post(
    "/profile",
    response_model=MessageResponse,
    summary="Create or update profile",
    description="Create new user profile or update existing one.",
)
@limiter.limit("20/minute")
async def create_or_update_profile_handler(
    request: Request,
    profile_update: ProfileUpdate
):
    """
    Create or update user profile.

    Args:
        request: FastAPI request (for rate limiting)
        profile_update: Profile data to create or update

    Returns:
        MessageResponse: Success message

    Raises:
        HTTPException: 500 if error occurs
    """
    try:
        logger.info(f"Updating profile for user {profile_update.user_id}")
        await create_or_update_profile(
            profile_update.user_id,
            profile_update.data.dict()
        )
        logger.debug(f"Profile updated for user {profile_update.user_id}")
        return MessageResponse(message="Profile successfully updated")
    except Exception as e:
        logger.error(
            f"Error updating profile for user {profile_update.user_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Error updating profile"
        )


@router.delete(
    "/profile/{user_id}",
    response_model=MessageResponse,
    summary="Delete profile",
    description="Delete user profile, chat history, long-term memory, and summary.",
)
async def delete_profile_handler(user_id: int):
    """
    Delete user profile and all associated data.

    Args:
        user_id: User ID

    Returns:
        MessageResponse: Success message

    Raises:
        HTTPException: 500 if error occurs
    """
    try:
        logger.warning(f"Deleting profile and all data for user {user_id}")
        await delete_profile(user_id)
        await delete_chat_history(user_id)
        await delete_long_term_memory(user_id)
        await delete_summary(user_id)
        logger.info(f"Profile and data deleted for user {user_id}")
        return MessageResponse(message="Profile and chat history successfully deleted")
    except Exception as e:
        logger.error(
            f"Error deleting profile for user {user_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Error deleting profile"
        )
