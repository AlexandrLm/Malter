"""
Health check endpoints.
Liveness and readiness probes for Kubernetes and Docker monitoring.
"""

import logging
from fastapi import APIRouter, HTTPException, status
from server.api_schemas import HealthCheckResponse, ReadyCheckResponse
from server.database import get_profile
from server.api_helpers import get_limiter_key
from slowapi import Limiter

# ============================================================================
# SETUP
# ============================================================================

router = APIRouter(tags=["health"])
limiter = Limiter(key_func=get_limiter_key)

logger = logging.getLogger(__name__)


# ============================================================================
# HEALTH CHECK ENDPOINTS
# ============================================================================

@router.get(
    "/",
    summary="Root endpoint",
    description="Welcome message indicating backend is running.",
    response_model=dict
)
async def read_root():
    """
    Root endpoint.
    Returns welcome message.
    """
    return {"message": "EvolveAI Backend is running"}


@router.get(
    "/health",
    status_code=200,
    summary="Liveness probe",
    description="Basic health check. Verifies process is running (no dependency checks).",
    response_model=HealthCheckResponse
)
async def health_check():
    """
    Basic health check (liveness probe).
    Doesn't check dependencies - only verifies the process is running.

    Returns:
        HealthCheckResponse: JSON with status='ok' if service is running
    """
    return HealthCheckResponse(status="ok")


@router.get(
    "/ready",
    status_code=200,
    summary="Readiness probe",
    description="Full readiness check. Verifies all critical dependencies: Database, Redis, Gemini API.",
    response_model=ReadyCheckResponse
)
async def ready_check():
    """
    Full readiness check (readiness probe).
    Verifies all critical dependencies are available:
    - PostgreSQL database
    - Redis cache
    - Gemini AI API

    Returns:
        ReadyCheckResponse: JSON with status of each service

    Raises:
        HTTPException: 503 if any critical service is unavailable
    """
    checks = {
        "database": {"status": "unknown", "message": ""},
        "redis": {"status": "unknown", "message": ""},
        "gemini": {"status": "unknown", "message": ""},
        "overall": "healthy"
    }

    # 1. Check database
    try:
        await get_profile(0)  # Try to fetch profile (may return None, that's ok)
        checks["database"]["status"] = "healthy"
        checks["database"]["message"] = "Connected"
    except Exception as e:
        checks["database"]["status"] = "unhealthy"
        checks["database"]["message"] = str(e)
        checks["overall"] = "unhealthy"
        logger.error(f"Database healthcheck failed: {e}")

    # 2. Check Redis (optional but important) + Circuit Breaker status
    import config
    from server.database import redis_circuit_breaker

    if config.REDIS_CLIENT:
        try:
            await config.REDIS_CLIENT.ping()
            cb_state = redis_circuit_breaker.get_state()
            checks["redis"]["status"] = "healthy" if cb_state == "CLOSED" else "degraded"
            checks["redis"]["message"] = f"Connected, Circuit Breaker: {cb_state}"
            checks["redis"]["circuit_breaker"] = {
                "state": cb_state,
                "failure_count": redis_circuit_breaker.failure_count
            }
        except Exception as e:
            checks["redis"]["status"] = "degraded"  # Redis not critical
            checks["redis"]["message"] = str(e)
            checks["redis"]["circuit_breaker"] = {
                "state": redis_circuit_breaker.get_state(),
                "failure_count": redis_circuit_breaker.failure_count
            }
            logger.warning(f"Redis healthcheck failed: {e}")
    else:
        checks["redis"]["status"] = "disabled"
        checks["redis"]["message"] = "Redis not configured"

    # 3. Check Gemini API + Circuit Breaker
    from utils.circuit_breaker import gemini_circuit_breaker

    if config.GEMINI_CLIENT:
        try:
            cb_stats = gemini_circuit_breaker.get_stats()
            cb_state = cb_stats["state"]

            # Determine status based on circuit breaker
            if cb_state == "CLOSED":
                checks["gemini"]["status"] = "healthy"
                checks["gemini"]["message"] = f"Client initialized, Circuit Breaker: {cb_state}"
            elif cb_state == "HALF_OPEN":
                checks["gemini"]["status"] = "degraded"
                checks["gemini"]["message"] = f"Testing recovery, Circuit Breaker: {cb_state}"
                checks["overall"] = "degraded"
            else:  # OPEN
                checks["gemini"]["status"] = "unhealthy"
                checks["gemini"]["message"] = f"Circuit Breaker OPEN (retry in {cb_stats['time_until_retry']}s)"
                checks["overall"] = "unhealthy"

            # Add circuit breaker stats
            checks["gemini"]["circuit_breaker"] = {
                "state": cb_state,
                "failure_count": cb_stats["failure_count"],
                "total_calls": cb_stats["total_calls"],
                "total_blocked": cb_stats["total_blocked"],
                "success_rate": round(
                    cb_stats["total_successes"] / cb_stats["total_calls"] * 100, 2
                ) if cb_stats["total_calls"] > 0 else 100
            }

        except Exception as e:
            checks["gemini"]["status"] = "unhealthy"
            checks["gemini"]["message"] = str(e)
            checks["overall"] = "unhealthy"
            logger.error(f"Gemini healthcheck failed: {e}")
    else:
        checks["gemini"]["status"] = "unhealthy"
        checks["gemini"]["message"] = "Gemini client not initialized"
        checks["overall"] = "unhealthy"

    # Return 503 if overall status is unhealthy
    if checks["overall"] == "unhealthy":
        raise HTTPException(status_code=503, detail=checks)

    return ReadyCheckResponse(**checks)
