"""
EvolveAI Backend - Main Application File

A conversational AI bot with evolving relationship system and long-term memory.
Built with FastAPI, PostgreSQL, and Google Gemini API.

Architecture:
- FastAPI REST API with JWT authentication
- PostgreSQL database with async SQLAlchemy ORM
- Redis caching with Circuit Breaker pattern
- Telegram Bot with aiogram
- Google Gemini for AI generation (chat, vision, TTS)

API Version: v1 (/api/v1/*)
"""

import uvicorn
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette_prometheus import PrometheusMiddleware, metrics

import config
from server.routes import setup_routes
from server.api_helpers import get_limiter_key

# ============================================================================
# LOGGING SETUP
# ============================================================================

LOG_LEVEL = config.LOG_LEVEL
logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)

# ============================================================================
# RATE LIMITING SETUP
# ============================================================================

limiter = Limiter(key_func=get_limiter_key)

# ============================================================================
# LIFESPAN AND STARTUP/SHUTDOWN
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown lifecycle.

    Startup:
    - Initialize scheduler for background tasks
    - Start monitoring

    Shutdown:
    - Gracefully shutdown scheduler
    - Close connections
    """
    # Startup
    logger.info("🚀 Starting EvolveAI Backend...")

    from server.scheduler import start_scheduler
    start_scheduler()
    logger.info("✅ Scheduler started")

    yield

    # Shutdown
    logger.info("🛑 Shutting down EvolveAI Backend...")
    from server.scheduler import shutdown_scheduler
    shutdown_scheduler()
    logger.info("✅ Application shutdown complete")


# ============================================================================
# FASTAPI APPLICATION INITIALIZATION
# ============================================================================

app = FastAPI(
    title="EvolveAI Backend",
    description="Conversational AI bot with evolving relationship system and long-term memory",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda request, exc: {
    "detail": "Rate limit exceeded"
})

# Add Prometheus metrics middleware
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics)

# ============================================================================
# ROUTE REGISTRATION
# ============================================================================

setup_routes(app)

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    logger.info(f"Starting server on 0.0.0.0:8000")
    logger.info(f"API Documentation: http://localhost:8000/api/docs")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        workers=1  # Use Gunicorn for multiple workers in production
    )
