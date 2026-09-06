"""
Hidden Gem API 서버 진입점 (FastAPI Application Entry Point)

Steam 게임 AI 추천 서비스의 FastAPI 앱 설정.
- 4,190개 게임 데이터 (GPT-5.4 Batch 분석)
- 60개 지표 (49 수치 + 9 태그 + 2 평가)
- 49차원 벡터 + 1536차원 임베딩 하이브리드 추천 엔진 v5

v3.1 → v3.2 변경사항:
    - taste 라우터 추가 (Phase 1.5 행동 로그 수집)

실행:
    uvicorn main:app --reload --port 8000
"""

import logging
import os
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from config import settings
from routers import games_router
from routers.taste import router as taste_router
from routers.ranking import router as ranking_router

logger = logging.getLogger(__name__)


# ==================== Sentry 초기화 / Sentry Setup ====================

def init_sentry():
    """
    Initialize Sentry error tracking and performance monitoring.
    Korean: Sentry 에러 추적 + 성능 모니터링 초기화.
    """
    dsn = getattr(settings, "SENTRY_DSN", None)
    if not dsn:
        logger.info("Sentry DSN 없음 — 에러 추적 비활성화 (로컬 모드)")
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=getattr(settings, "SENTRY_ENV", "production"),
        release=f"hidden-gem@{getattr(settings, 'APP_VERSION', '3.2.0')}",
        traces_sample_rate=getattr(settings, "SENTRY_TRACES_SAMPLE_RATE", 1.0),
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            RedisIntegration(),
        ],
        before_send=_filter_sensitive_data,
        profiles_sample_rate=0.1,
    )
    logger.info(f"Sentry 초기화 완료 (env={getattr(settings, 'SENTRY_ENV', 'production')})")


def _filter_sensitive_data(event, hint):
    """
    Filter sensitive data before sending to Sentry.
    Korean: Sentry 전송 전 민감 정보 필터링.
    """
    if "request" in event and "data" in event.get("request", {}):
        data = event["request"]["data"]
        if isinstance(data, dict):
            for key in ("api_key", "password", "token", "secret"):
                if key in data:
                    data[key] = "[Filtered]"
    return event


init_sentry()


# ==================== Rate Limiter ====================

limiter = Limiter(key_func=get_remote_address)


# ==================== 앱 생명주기 / Lifespan ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Korean: 앱 생명주기 관리 — 시작 시 Redis/비용가드 초기화.
    """
    try:
        from services.cache import recommendation_cache
        await recommendation_cache._get_redis()
        logger.info("Redis 연결 성공")
    except Exception as e:
        logger.warning(f" Redis 연결 실패 (캐싱 비활성화): {e}")

    try:
        from services.cost_guard import cost_guard
        stats = await cost_guard.get_stats()
        logger.info(f"OpenAI 오늘 누적 비용: ${stats.get('daily_cost_usd', 0):.4f}")
    except Exception as e:
        logger.warning(f" 비용 가드 초기화 실패: {e}")

    print("=" * 60)
    print("Hidden Gem API Server v3.2 starting...")
    print(f"Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    print(f"Docs:     http://localhost:8000/docs")
    print(f"Health:   http://localhost:8000/health")
    print(f"Cost:     http://localhost:8000/ops/cost")
    print(f"Taste:    http://localhost:8000/api/v1/taste/stats")
    print("=" * 60)

    yield

    print("Shutting down...")


# ==================== FastAPI 앱 ====================

app = FastAPI(
    # 운영에서는 API 문서/스키마 비노출 (내부 구조 정찰 차단)
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    title="Hidden Gem API",
    description=(
        "**Steam 게임 AI 추천 서비스**\n\n"
        "## 핵심 기능\n"
        "- **60개 지표 기반 게임 분석** (49 수치 + 9 태그 + 2 평가)\n"
        "- **유사 게임 추천**: 4단계 가중치 + 앵커 점수 (v5)\n"
        "- **자연어 시맨틱 검색**: GPT 번역 + pgvector\n"
        "- **선호도 기반 추천**: 원하는 게임 스타일 직접 지정\n"
        "- **행동 로그 수집**: 취향 학습 데이터 수집 (Phase 1.5)\n\n"
        "## 데이터\n"
        "- 4,190개 게임 (인디/AAA 무관)\n"
        "- GPT-5.4 Batch + Steam CSV 통합"
    ),
    version="3.2.0",
    lifespan=lifespan,
)


# ==================== 미들웨어 ====================

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

if settings.DEBUG:
    ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
else:
    # 운영: FRONTEND_URL 콤마 구분 다중 허용
    # Korean: 여러 주소를 콤마로 받아 허용 (Vercel 프리뷰는 아래 regex가 커버)
    _frontend = os.getenv("FRONTEND_URL", "https://hiddengem.io")
    ALLOWED_ORIGINS = [o.strip() for o in _frontend.split(",") if o.strip()]    
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    # 기본: Vercel 프리뷰 전체 허용 (Bearer 토큰 방식이라 쿠키 탈취 위험은 없음).
    # 운영에서 좁히려면 CORS_ORIGIN_REGEX 환경변수로 자기 프로젝트 슬러그만 허용:
    #   예) https://hidden-gem-.*\.vercel\.app
    allow_origin_regex=os.getenv("CORS_ORIGIN_REGEX", r"https://.*\.vercel\.app"),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Remaining", "X-RateLimit-Limit"],
)


# ==================== 라우터 ====================

# ranking 은 games 보다 먼저 — /games/{app_id} 가 'ranking' 을 app_id 로 잡아먹지 않게
app.include_router(ranking_router, prefix=settings.API_V1_PREFIX)
app.include_router(games_router, prefix=settings.API_V1_PREFIX)
app.include_router(taste_router, prefix=settings.API_V1_PREFIX)  # Phase 1.5


# ==================== 기본 엔드포인트 ====================

@app.get("/")
async def root():
    """서비스 기본 정보 반환 (Service Info)"""
    return {
        "service": "Hidden Gem API",
        "version": "3.2.0",
        "dimension": "49D vector + 1536D embedding",
        "engine": "v5 (4-tier weighting + anchor score)",
        "docs": "/docs",
        "health": "/health",
        "cost": "/ops/cost",
        "taste": "/api/v1/taste/stats",
    }


@app.get("/health")
async def health_check():
    """헬스 체크 — 의존 구성요소까지 실제로 두드린다.

    2026-09-06: 정적으로 {"status":"healthy"} 만 돌려주던 탓에 운영에서
    ① DB 비밀번호 교체 후 커넥션이 옛 값이라 랭킹이 전부 500 이던 때도,
    ② Redis 인증 실패로 캐시가 통째로 죽어 있던 때도 '정상'으로 보였다.
    무엇을 확인하는지 모르는 헬스체크는 증거가 아니다 (C-14).

    HTTP 는 200 을 유지한다 — Railway 헬스체크가 이 경로를 보고 있어
    503 을 주면 배포가 죽는다. 대신 status 를 healthy/degraded 로 구분한다.
    """
    components: dict = {}

    try:
        from database import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        components["db"] = "ok"
    except Exception as exc:
        components["db"] = f"error: {type(exc).__name__}: {exc}"[:200]

    try:
        from services.cache import recommendation_cache
        r = await recommendation_cache._get_redis()
        await r.ping()
        components["redis"] = "ok"
    except Exception as exc:
        components["redis"] = f"error: {type(exc).__name__}: {exc}"[:200]

    degraded = [k for k, v in components.items() if v != "ok"]
    return {
        "status": "degraded" if degraded else "healthy",
        "version": "3.2.0",
        "components": components,
        "score_version": settings.SCORE_VERSION,
        "gem_source": settings.GEM_SOURCE,
    }


# ==================== 운영 엔드포인트 ====================

@app.get("/ops/cost")
async def get_cost_stats():
    """OpenAI 비용 현황 조회 (OpenAI Cost Stats)"""
    from services.cost_guard import cost_guard
    return await cost_guard.get_stats()


@app.get("/ops/cache")
async def get_cache_stats():
    """Redis 캐시 현황 조회 (Cache Stats)"""
    from services.cache import recommendation_cache
    return await recommendation_cache.get_stats()


@app.post("/ops/cache/invalidate")
async def invalidate_cache():
    """전체 캐시 초기화 (Cache Invalidation)"""
    from services.cache import recommendation_cache
    deleted = await recommendation_cache.invalidate_all()
    return {"deleted_keys": deleted, "message": f"{deleted}개 캐시 삭제 완료"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)