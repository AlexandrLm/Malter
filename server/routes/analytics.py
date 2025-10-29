"""
Analytics routes.
User and system analytics endpoints.
"""

import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from slowapi import Limiter

from server.api_helpers import verify_token, verify_admin, get_limiter_key

# ============================================================================
# SETUP
# ============================================================================

router = APIRouter(prefix="/api/v1/admin/analytics", tags=["analytics"])
limiter = Limiter(key_func=get_limiter_key)

logger = logging.getLogger(__name__)


# ============================================================================
# ANALYTICS ENDPOINTS
# ============================================================================

@router.get(
    "/overview",
    summary="Overview analytics",
    description="Return overall bot usage statistics (admin only).",
)
@limiter.limit("10/minute")
async def analytics_overview_handler(
    request: Request,
    user_id: int = Depends(verify_token)
):
    """
    Get overview analytics.

    Args:
        request: FastAPI request (for rate limiting)
        user_id: Admin user ID from JWT token

    Returns:
        dict: Overview statistics

    Raises:
        HTTPException: 500 if error occurs
    """
    try:
        from server.analytics import get_overview_stats
        logger.debug(f"User {user_id} requested overview analytics")
        stats = await get_overview_stats()
        return {"analytics": stats}
    except Exception as e:
        logger.error(f"Error fetching overview analytics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error fetching overview analytics"
        )


@router.get(
    "/users",
    summary="Users analytics",
    description="Return detailed user statistics (admin only).",
)
@limiter.limit("10/minute")
async def analytics_users_handler(
    request: Request,
    user_id: int = Depends(verify_token)
):
    """
    Get user analytics.

    Args:
        request: FastAPI request (for rate limiting)
        user_id: Admin user ID from JWT token

    Returns:
        dict: User statistics

    Raises:
        HTTPException: 500 if error occurs
    """
    try:
        from server.analytics import get_users_stats
        logger.debug(f"User {user_id} requested users analytics")
        stats = await get_users_stats()
        return {"analytics": stats}
    except Exception as e:
        logger.error(f"Error fetching users analytics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error fetching users analytics"
        )


@router.get(
    "/messages",
    summary="Messages analytics",
    description="Return message statistics (admin only).",
)
@limiter.limit("10/minute")
async def analytics_messages_handler(
    request: Request,
    days: int = 7,
    user_id: int = Depends(verify_admin)
):
    """
    Get message analytics.

    Args:
        request: FastAPI request (for rate limiting)
        days: Number of days to analyze (default 7)
        user_id: Admin user ID from JWT token

    Returns:
        dict: Message statistics

    Raises:
        HTTPException: 500 if error occurs
    """
    try:
        from server.analytics import get_messages_stats
        logger.debug(f"Admin {user_id} requested messages analytics (days={days})")
        stats = await get_messages_stats(days=days)
        return {"analytics": stats}
    except Exception as e:
        logger.error(f"Error fetching messages analytics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error fetching messages analytics"
        )


@router.get(
    "/revenue",
    summary="Revenue analytics",
    description="Return subscription and revenue statistics (admin only).",
)
@limiter.limit("10/minute")
async def analytics_revenue_handler(
    request: Request,
    user_id: int = Depends(verify_token)
):
    """
    Get revenue analytics.

    Args:
        request: FastAPI request (for rate limiting)
        user_id: Admin user ID from JWT token

    Returns:
        dict: Revenue statistics

    Raises:
        HTTPException: 500 if error occurs
    """
    try:
        from server.analytics import get_revenue_stats
        logger.debug(f"User {user_id} requested revenue analytics")
        stats = await get_revenue_stats()
        return {"analytics": stats}
    except Exception as e:
        logger.error(f"Error fetching revenue analytics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error fetching revenue analytics"
        )


@router.get(
    "/features",
    summary="Features analytics",
    description="Return feature usage statistics (admin only).",
)
@limiter.limit("10/minute")
async def analytics_features_handler(
    request: Request,
    user_id: int = Depends(verify_token)
):
    """
    Get feature usage analytics.

    Args:
        request: FastAPI request (for rate limiting)
        user_id: Admin user ID from JWT token

    Returns:
        dict: Feature usage statistics

    Raises:
        HTTPException: 500 if error occurs
    """
    try:
        from server.analytics import get_feature_usage_stats
        logger.debug(f"User {user_id} requested features analytics")
        stats = await get_feature_usage_stats()
        return {"analytics": stats}
    except Exception as e:
        logger.error(f"Error fetching features analytics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error fetching features analytics"
        )


@router.get(
    "/cohort",
    summary="Cohort analysis",
    description="Return retention by cohort (admin only).",
)
@limiter.limit("10/minute")
async def analytics_cohort_handler(
    request: Request,
    days: int = 30,
    user_id: int = Depends(verify_admin)
):
    """
    Get cohort analysis.

    Args:
        request: FastAPI request (for rate limiting)
        days: Number of days to analyze (default 30)
        user_id: Admin user ID from JWT token

    Returns:
        dict: Cohort analysis

    Raises:
        HTTPException: 500 if error occurs
    """
    try:
        from server.analytics import get_cohort_analysis
        logger.debug(f"Admin {user_id} requested cohort analysis (days={days})")
        stats = await get_cohort_analysis(days=days)
        return {"analytics": stats}
    except Exception as e:
        logger.error(f"Error fetching cohort analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error fetching cohort analysis"
        )


@router.get(
    "/funnel",
    summary="Funnel analysis",
    description="Return relationship level conversion funnel (admin only).",
)
@limiter.limit("10/minute")
async def analytics_funnel_handler(
    request: Request,
    user_id: int = Depends(verify_token)
):
    """
    Get funnel analysis.

    Args:
        request: FastAPI request (for rate limiting)
        user_id: Admin user ID from JWT token

    Returns:
        dict: Funnel analysis

    Raises:
        HTTPException: 500 if error occurs
    """
    try:
        from server.analytics import get_funnel_analysis
        logger.debug(f"User {user_id} requested funnel analysis")
        stats = await get_funnel_analysis()
        return {"analytics": stats}
    except Exception as e:
        logger.error(f"Error fetching funnel analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error fetching funnel analysis"
        )


@router.get(
    "/activity",
    summary="Activity patterns",
    description="Return activity patterns by day and hour (admin only).",
)
@limiter.limit("10/minute")
async def analytics_activity_handler(
    request: Request,
    user_id: int = Depends(verify_token)
):
    """
    Get activity patterns.

    Args:
        request: FastAPI request (for rate limiting)
        user_id: Admin user ID from JWT token

    Returns:
        dict: Activity patterns

    Raises:
        HTTPException: 500 if error occurs
    """
    try:
        from server.analytics import get_activity_patterns
        logger.debug(f"User {user_id} requested activity patterns")
        stats = await get_activity_patterns()
        return {"analytics": stats}
    except Exception as e:
        logger.error(f"Error fetching activity patterns: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error fetching activity patterns"
        )


@router.get(
    "/tools",
    summary="Tools usage analytics",
    description="Return AI tools usage statistics (admin only).",
)
@limiter.limit("10/minute")
async def analytics_tools_handler(
    request: Request,
    days: int = 7,
    user_id: int = Depends(verify_admin)
):
    """
    Get AI tools usage analytics.

    Args:
        request: FastAPI request (for rate limiting)
        days: Number of days to analyze (default 7)
        user_id: Admin user ID from JWT token

    Returns:
        dict: Tools usage statistics

    Raises:
        HTTPException: 500 if error occurs
    """
    try:
        from server.analytics import get_tools_usage_stats
        logger.debug(f"Admin {user_id} requested tools analytics (days={days})")
        stats = await get_tools_usage_stats(days=days)
        return {"analytics": stats}
    except Exception as e:
        logger.error(f"Error fetching tools analytics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error fetching tools analytics"
        )
