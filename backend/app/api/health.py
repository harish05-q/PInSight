import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.db import engine

log = structlog.get_logger()
router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Health check endpoint with DB and Redis connectivity status."""
    status = {"status": "ok", "db": "unknown", "redis": "unknown"}

    # Check database
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        status["db"] = "ok"
    except Exception as e:
        status["db"] = "error"
        status["status"] = "degraded"
        log.error("health_check_db_failed", error=str(e))

    # Check Redis
    try:
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        status["redis"] = "ok"
    except Exception as e:
        status["redis"] = "error"
        status["status"] = "degraded"
        log.error("health_check_redis_failed", error=str(e))

    return status
