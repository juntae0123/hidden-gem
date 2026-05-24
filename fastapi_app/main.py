"""
Hidden Gem API 서버 진입점 (FastAPI Application Entry Point)

Steam 게임 AI 추천 서비스의 FastAPI 앱 설정.
- 4,190개 게임 데이터 (GPT-5.4 Batch 분석)
- 60개 지표 (49 수치 + 9 태그 + 2 평가)
- 49차원 벡터 + 1536차원 임베딩 하이브리드 추천 엔진 v5

v3.0 → v3.1 변경사항:
    - Sentry 에러 추적 + p95 알람 통합
    - Discord 알람 연동 (DISCORD_WEBHOOK_URL 설정 시)

실행:
    uvicorn main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from config import settings
from routers import games_router

logger = logging.getLogger(__name__)


# ==================== Sentry 초기화 / Sentry Setup ====================

def init_sentry():
    """
    Initialize Sentry error tracking and performance monitoring.
    Korean: Sentry 에러 추적 + 성능 모니터링 초기화.

    SENTRY_DSN 환경변수 없으면 비활성화 (로컬 개발 모드).
    통합:
        - FastAPI: 요청/응답 추적
        - SQLAlchemy: 슬로우 쿼리 감지
        - Redis: 캐시 에러 추적
    """
    dsn = getattr(settings, "SENTRY_DSN", None)
    if not dsn:
        logger.info("Sentry DSN 없음 — 에러 추적 비활성화 (로컬 모드)")
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=getattr(settings, "SENTRY_ENV", "production"),
        release=f"hidden-gem@{getattr(settings, 'APP_VERSION', '3.1.0')}",

        # 성능 추적 / Performance tracing
        # 운영 초기: 100% 샘플링, MAU 1K+ 이후 0.1~0.2로 낮추기
        traces_sample_rate=getattr(settings, "SENTRY_TRACES_SAMPLE_RATE", 1.0),

        # 통합 / Integrations
        integrations=[
            FastApiIntegration(
                transaction_style="endpoint",  # 엔드포인트별 트랜잭션
            ),
            SqlalchemyIntegration(),   # 슬로우 쿼리 감지
            RedisIntegration(),        # Redis 에러 추적
        ],

        # 민감 정보 필터링 / Sensitive data filtering
        before_send=_filter_sensitive_data,

        # p95 응답시간 알람용 프로파일링
        profiles_sample_rate=0.1,
    )

    logger.info(f"✅ Sentry 초기화 완료 (env={getattr(settings, 'SENTRY_ENV', 'production')})")


def _filter_sensitive_data(event, hint):
    """
    Filter sensitive data before sending to Sentry.
    Korean: Sentry 전송 전 민감 정보 필터링.

    OPENAI_API_KEY, DB 비밀번호 등 환경변수 값 제거.
    """
    # request body에서 민감 필드 제거
    if "request" in event and "data" in event.get("request", {}):
        data = event["request"]["data"]
        if isinstance(data, dict):
            for key in ("api_key", "password", "token", "secret"):
                if key in data:
                    data[key] = "[Filtered]"
    return event


# Sentry 앱 시작 전 초기화 (import 시점)
init_sentry()


# ==================== Rate Limiter 초기화 / Rate Limiter Setup ====================

limiter = Limiter(key_func=get_remote_address)


# ==================== 앱 생명주기 / Lifespan ====================

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
    print("🚀 Hidden Gem API Server v3.1 starting...")
    print(f"📊 Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    print(f"📖 Docs:     http://localhost:8000/docs")
    print(f"🩺 Health:   http://localhost:8000/health")
    print(f"💰 Cost:     http://localhost:8000/ops/cost")
    print("=" * 60)

    yield  # 앱 실행 구간 (요청 처리)

    print("👋 Shutting down...")


# ==================== FastAPI 앱 / FastAPI App ====================

app = FastAPI(
    title="Hidden Gem API",
    description=(
        "🎮 **Steam 게임 AI 추천 서비스**\n\n"
        "## 핵심 기능\n"
        "- **60개 지표 기반 게임 분석** (49 수치 + 9 태그 + 2 평가)\n"
        "- **유사 게임 추천**: 4단계 가중치 + 앵커 점수 (v5)\n"
        "- **자연어 시맨틱 검색**: GPT 번역 + pgvector\n"
        "- **선호도 기반 추천**: 원하는 게임 스타일 직접 지정\n\n"
        "## 데이터\n"
        "- 4,190개 게임 (인디/AAA 무관)\n"
        "- GPT-5.4 Batch + Steam CSV 통합"
    ),
    version="3.1.0",
    lifespan=lifespan,
)


# ==================== 미들웨어 / Middleware ====================

# Rate Limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 개발용 / Production: ["https://hiddengem.io"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 라우터 / Routers ====================

app.include_router(games_router, prefix=settings.API_V1_PREFIX)


# ==================== 기본 엔드포인트 / Base Endpoints ====================

@app.get("/")
async def root():
    """서비스 기본 정보 반환 (Service Info)"""
    return {
        "service": "Hidden Gem API",
        "version": "3.1.0",
        "dimension": "49D vector + 1536D embedding",
        "engine": "v5 (4-tier weighting + anchor score)",
        "docs": "/docs",
        "health": "/health",
        "cost": "/ops/cost",
    }


@app.get("/health")
async def health_check():
    """헬스 체크 - Docker/k8s 컨테이너 상태 확인용 (Health Check)"""
    return {"status": "healthy", "version": "3.1.0"}


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

'''
@app.get("/ops/sentry-test")
async def sentry_test():
    """
    Sentry 연결 테스트 엔드포인트 (Sentry Connection Test)
    의도적으로 예외를 발생시켜 Sentry 수신 여부 확인.
    운영 배포 후 한 번만 실행, 확인 후 제거 권장.
    """
    raise ValueError("Sentry 테스트 에러 — 정상 수신되면 이 에러가 Sentry에 표시됩니다.")
'''

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )