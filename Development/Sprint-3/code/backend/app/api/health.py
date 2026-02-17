"""
Health check endpoints for monitoring system status.

Provides endpoints to verify:
- Application health
- Database connectivity
- Redis cache availability
"""

from fastapi import APIRouter, status
from sqlalchemy import text

from app.db.database import SessionLocal
from app.core.cache import ping_redis

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check():
    """
    Basic health check endpoint.

    Checks:
    - Application is running
    - Database connection
    - Redis connection (non-critical)

    Returns:
        200: System healthy
        503: System degraded (Redis down but app continues)
        500: Critical failure (database down)
    """
    health_status = {"status": "healthy", "components": {}}

    # Check database
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        health_status["components"]["database"] = "connected"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["database"] = f"disconnected: {str(e)}"
        return health_status, status.HTTP_500_INTERNAL_SERVER_ERROR

    # Check Redis (non-critical)
    redis_healthy = ping_redis()
    if redis_healthy:
        health_status["components"]["redis"] = "connected"
    else:
        # Redis down is not critical - app can continue without cache
        health_status["status"] = "degraded"
        health_status["components"]["redis"] = "disconnected (cache disabled)"

    return health_status


@router.get("/redis")
def redis_health():
    """
    Dedicated Redis health check.

    Returns:
        200: Redis connected
        503: Redis unavailable
    """
    if ping_redis():
        return {"status": "healthy", "redis": "connected"}
    else:
        return {"status": "unhealthy", "redis": "disconnected"}
