"""
API routes package.
Organizes API endpoints into logical modules.
"""

from fastapi import APIRouter

from .health import router as health_router
from .auth import router as auth_router
from .chat import router as chat_router
from .profile import router as profile_router
from .premium import router as premium_router
from .admin import router as admin_router
from .analytics import router as analytics_router

# ============================================================================
# API ROUTER SETUP
# ============================================================================

def setup_routes(app) -> None:
    """
    Register all route modules with the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    # Health checks (no auth required)
    app.include_router(health_router)

    # Authentication (no auth required)
    app.include_router(auth_router)

    # User endpoints
    app.include_router(chat_router)
    app.include_router(profile_router)
    app.include_router(premium_router)

    # Admin endpoints
    app.include_router(admin_router)
    app.include_router(analytics_router)


__all__ = [
    "setup_routes",
    "health_router",
    "auth_router",
    "chat_router",
    "profile_router",
    "premium_router",
    "admin_router",
    "analytics_router",
]
