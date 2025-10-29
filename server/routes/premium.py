"""
Premium subscription routes.
Premium account management endpoints.
"""

import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from slowapi import Limiter

from server.api_schemas import PremiumActivateRequest, PremiumActivateResponse
from server.api_helpers import verify_token, get_limiter_key
from server.database import activate_premium_subscription

# ============================================================================
# SETUP
# ============================================================================

router = APIRouter(prefix="/api/v1", tags=["premium"])
limiter = Limiter(key_func=get_limiter_key)

logger = logging.getLogger(__name__)


# ============================================================================
# PREMIUM ENDPOINTS
# ============================================================================

@router.post(
    "/activate_premium",
    response_model=PremiumActivateResponse,
    summary="Activate premium subscription",
    description="Activate premium subscription for user. Requires JWT authentication.",
)
@limiter.limit("5/minute")
async def activate_premium_handler(
    request: Request,
    activate_request: PremiumActivateRequest,
    authenticated_user_id: int = Depends(verify_token)
):
    """
    Activate premium subscription for user.
    Requires JWT authentication and verifies user_id matches.

    Args:
        request: FastAPI request (for rate limiting)
        activate_request: Premium activation request with user_id, duration, charge_id
        authenticated_user_id: User ID from JWT token

    Returns:
        PremiumActivateResponse: Success/failure response

    Raises:
        HTTPException: 400 if user_id missing, 403 if trying to activate for another user,
                      500 if activation fails
    """
    user_id = activate_request.user_id

    if not user_id:
        logger.warning("Premium activation attempt without user_id")
        raise HTTPException(status_code=400, detail="user_id is required")

    # SECURITY: Verify that authenticated user can only activate for themselves
    if user_id != authenticated_user_id:
        logger.warning(
            f"Attempted premium activation: authenticated_user={authenticated_user_id}, "
            f"requested_user={user_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="Cannot activate premium subscription for another user"
        )

    try:
        logger.info(
            f"Activating premium subscription for user {user_id} "
            f"({activate_request.duration_days} days)"
        )

        success = await activate_premium_subscription(
            user_id,
            activate_request.duration_days,
            activate_request.charge_id
        )

        if success:
            logger.info(f"Premium subscription activated for user {user_id}")
            return PremiumActivateResponse(
                success=True,
                message=f"Premium subscription activated for {activate_request.duration_days} days"
            )
        else:
            logger.error(f"Failed to activate premium subscription for user {user_id}")
            raise HTTPException(
                status_code=500,
                detail="Error activating premium subscription"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error activating premium subscription for user {user_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Error activating premium subscription"
        )
