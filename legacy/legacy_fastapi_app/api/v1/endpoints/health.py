# fastapi_app/api/v1/endpoints/health.py
"""
Hidden Gem - 헬스체크 API
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from config import settings

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/")
async def health_check():
    """기본 헬스체크"""
    return {
        "status": "healthy",
        "service": "Hidden Gem API",
        "version": settings.VERSION,
    }


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """준비 상태 체크 (DB 연결 확인)"""
    
    checks = {
        "database": False,
        "redis": False,
    }
    
    # PostgreSQL 체크
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        checks["database"] = str(e)
    
    # Redis 체크
    try:
        import redis.asyncio as redis
        r = await redis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.close()
        checks["redis"] = True
    except Exception as e:
        checks["redis"] = str(e)
    
    all_healthy = all(v is True for v in checks.values())
    
    return {
        "status": "ready" if all_healthy else "degraded",
        "checks": checks,
    }


@router.get("/live")
async def liveness_check():
    """생존 체크 (컨테이너 재시작 판단용)"""
    return {"status": "alive"}
