"""
Hidden Gem API 서버 진입점 (FastAPI Application Entry Point)

Steam 게임 AI 추천 서비스의 FastAPI 앱 설정.
- 4,190개 게임 데이터 (GPT-5.4 Batch 분석)
- 60개 지표 (49 수치 + 9 태그 + 2 평가)
- 49차원 벡터 + 1536차원 임베딩 하이브리드 추천 엔진

실행:
    uvicorn main:app --reload --port 8000
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from config import settings
from routers import games_router

logger = logging.getLogger(__name__)

# ==================== Rate Limiter 초기화 / Rate Limiter Setup ====================
# IP 기반 Rate Limiting / IP-based rate limiting
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    앱 생명주기 관리 (Application Lifespan)

    FastAPI 0.95+ 에서 @app.on_event 대신 권장되는 방식.
    서버 시작 시 Redis 연결 확인 및 리소스 초기화.
    """
    # Redis 연결 확인 / Check Redis connection
    try:
        from services.cache import recommendation_cache
        await recommendation_cache._get_redis()
        logger.info("✅ Redis 연결 성공")
    except Exception as e:
        logger.warning(f"⚠️  Redis 연결 실패 (캐싱 비활성화): {e}")

    # 비용 가드 초기화 / Initialize cost guard
    try:
        from services.cost_guard import cost_guard
        stats = await cost_guard.get_stats()
        logger.info(f"💰 OpenAI 오늘 누적 비용: ${stats.get('daily_cost_usd', 0):.4f}")
    except Exception as e:
        logger.warning(f"⚠️  비용 가드 초기화 실패: {e}")

    print("=" * 60)
    print("🚀 Hidden Gem API Server (49D + Embedding) starting...")
    print(f"📊 Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    print(f"📖 Docs:     http://localhost:8000/docs")
    print(f"🩺 Health:   http://localhost:8000/health")
    print(f"💰 Cost:     http://localhost:8000/ops/cost")
    print("=" * 60)

    yield  # 앱 실행 구간 (요청 처리)

    print("👋 Shutting down...")


app = FastAPI(
    title="Hidden Gem API",
    description=(
        "🎮 **Steam 게임 AI 추천 서비스**\n\n"
        "## 핵심 기능\n"
        "- **60개 지표 기반 게임 분석** (49 수치 + 9 태그 + 2 평가)\n"
        "- **유사 게임 추천**: 코사인+유클리드+임베딩 하이브리드\n"
        "- **자연어 시맨틱 검색**: GPT 번역 + pgvector\n"
        "- **선호도 기반 추천**: 원하는 게임 스타일 직접 지정\n\n"
        "## 데이터\n"
        "- 4,190개 게임 (인디/AAA 무관)\n"
        "- GPT-5.4 Batch + Steam CSV 통합"
    ),
    version="3.0.0",
    lifespan=lifespan,
)

# ==================== 미들웨어 / Middleware ====================

# Rate Limiting 미들웨어 / Rate limiting middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS 미들웨어 / CORS middleware
# 운영 환경에서는 allow_origins를 구체적인 도메인으로 제한
# In production, restrict allow_origins to specific domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 개발용 / Production: ["https://hiddengem.io"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 라우터 / Routers ====================

# /api/v1 접두사로 게임 관련 라우터 등록
app.include_router(games_router, prefix=settings.API_V1_PREFIX)

# ==================== 기본 엔드포인트 / Base Endpoints ====================

@app.get("/")
async def root():
    """서비스 기본 정보 반환 (Service Info)"""
    return {
        "service": "Hidden Gem API",
        "version": "3.0.0",
        "dimension": "49D vector + 1536D embedding",
        "docs": "/docs",
        "health": "/health",
        "cost": "/ops/cost",
    }


@app.get("/health")
async def health_check():
    """헬스 체크 - Docker/k8s 컨테이너 상태 확인용 (Health Check)"""
    return {"status": "healthy", "version": "3.0.0"}


# ==================== 운영 엔드포인트 / Ops Endpoints ====================

@app.get("/ops/cost")
async def get_cost_stats():
    """
    OpenAI 비용 현황 조회 (OpenAI Cost Stats)
    오늘 누적 비용, 시간당 비용, 한도 대비 사용률 반환.
    """
    from services.cost_guard import cost_guard
    return await cost_guard.get_stats()


@app.get("/ops/cache")
async def get_cache_stats():
    """
    Redis 캐시 현황 조회 (Cache Stats)
    캐시 키 수, 적중률 반환.
    """
    from services.cache import recommendation_cache
    return await recommendation_cache.get_stats()


@app.post("/ops/cache/invalidate")
async def invalidate_cache():
    """
    전체 캐시 초기화 (Cache Invalidation)
    daily_update 후 수동 초기화 또는 긴급 캐시 클리어용.
    """
    from services.cache import recommendation_cache
    deleted = await recommendation_cache.invalidate_all()
    return {"deleted_keys": deleted, "message": f"{deleted}개 캐시 삭제 완료"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )