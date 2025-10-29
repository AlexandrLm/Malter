"""
Authentication routes.
JWT token generation and user authentication endpoints.
"""

import logging
from datetime import timedelta
from fastapi import APIRouter, HTTPException, Body, Request
from slowapi import Limiter

from server.api_schemas import AuthRequest, AuthResponse
from server.api_helpers import create_access_token, get_limiter_key, ACCESS_TOKEN_EXPIRE_MINUTES

# ============================================================================
# SETUP
# ============================================================================

router = APIRouter(prefix="/api/v1", tags=["auth"])
limiter = Limiter(key_func=get_limiter_key)

logger = logging.getLogger(__name__)


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@router.post(
    "/auth",
    response_model=AuthResponse,
    summary="Generate JWT token",
    description="Create JWT token for user authentication (for internal bot use).",
)
@limiter.limit("10/minute")
async def auth_endpoint(
    request: Request,
    auth_data: AuthRequest
):
    """
    Generate JWT token for API authentication.

    Args:
        request: FastAPI request (for rate limiting)
        auth_data: Authentication request with user_id

    Returns:
        AuthResponse: Access token and token type

    Raises:
        HTTPException: 400 if user_id is missing
    """
    if not auth_data.user_id:
        logger.warning("Auth attempt without user_id")
        raise HTTPException(status_code=400, detail="user_id required")

    logger.info(f"Generating JWT token for user {auth_data.user_id}")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(auth_data.user_id)},
        expires_delta=access_token_expires
    )

    return AuthResponse(
        access_token=access_token,
        token_type="bearer"
    )
