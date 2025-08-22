"""Health check API routes."""

from fastapi import APIRouter, HTTPException
from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from config import get_settings
from utils.logging import get_logger

router = APIRouter()
logger = get_logger("api.health")
settings = get_settings()


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.get_environment()
    }


@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check including database and Redis connectivity."""
    health_status = {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.get_environment(),
        "checks": {}
    }

    # Database health check
    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as connection:
            connection.execute("SELECT 1")
        health_status["checks"]["database"] = "healthy"
    except SQLAlchemyError as e:
        logger.error("Database health check failed", error=str(e))
        health_status["checks"]["database"] = "unhealthy"
        health_status["status"] = "degraded"

    # Redis health check
    try:
        redis_client = Redis.from_url(settings.REDIS_URL)
        redis_client.ping()
        health_status["checks"]["redis"] = "healthy"
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        health_status["checks"]["redis"] = "unhealthy"
        health_status["status"] = "degraded"

    # If any critical service is down, mark as unhealthy
    if health_status["status"] == "degraded":
        raise HTTPException(status_code=503, detail=health_status)

    return health_status


@router.get("/health/ready")
async def readiness_check():
    """Readiness check for Kubernetes/Docker."""
    # Add more sophisticated checks as needed
    return {"status": "ready"}
