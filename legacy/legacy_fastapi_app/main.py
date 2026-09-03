# fastapi_app/main.py
"""
Hidden Gem - FastAPI 메인

엔터프라이즈급 설정:
- 미들웨어 (CORS, Rate Limit)
- 예외 핸들러
- Lifespan (시작/종료 이벤트)
- Redis Pub/Sub 동기화

⚠️ 주의: DB 스키마 관리는 Django migrate가 전담
   FastAPI는 테이블 생성하지 않음 (Single Source of Truth)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.v1.router import api_router
from core.exceptions import HiddenGemException, get_friendly_error_response
from core.rate_limiter import rate_limit_middleware
from config import settings
from services.sync_service import start_sync, stop_sync


# ============================================================
# Lifespan (시작/종료 이벤트)
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행"""
    
    # ========== 시작 시 ==========
    print("🚀 Hidden Gem API Server Starting...")
    print(f"📊 Environment: {'Development' if settings.DEBUG else 'Production'}")
    print(f"🗄️ Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    print(f"📦 Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    
    # ⚠️ DB 테이블 생성 제거됨
    # Django migrate가 Single Source of Truth
    # FastAPI는 Django가 생성한 테이블을 사용만 함
    print("📋 DB Schema: Managed by Django (run 'python manage.py migrate' first)")
    
    # Redis Pub/Sub 동기화 시작
    await start_sync()
    
    yield
    
    # ========== 종료 시 ==========
    await stop_sync()
    print("👋 Shutting down...")


# ============================================================
# FastAPI 앱 생성
# ============================================================

app = FastAPI(
    title=settings.APP_NAME,
    description="Steam 게임 AI 추천 서비스 - 당신에게 완벽히 맞는 게임을 찾아드립니다.",
    version=settings.VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)


# ============================================================
# 미들웨어
# ============================================================

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Rate Limit 미들웨어
@app.middleware("http")
async def rate_limit_middleware_handler(request: Request, call_next):
    """Rate Limit 미들웨어"""
    
    # 제외 경로
    excluded_paths = [
        "/health", "/api/v1/health", "/api/v1/health/live", "/api/v1/health/ready",
        "/docs", "/redoc", "/openapi.json", "/"
    ]
    if request.url.path in excluded_paths:
        return await call_next(request)
    
    # Rate Limit 체크
    allowed, retry_after = rate_limit_middleware.check(request)
    
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "error_code": "rate_limit_exceeded",
                "message": "요청이 너무 많아요. 잠시 후 다시 시도해주세요.",
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )
    
    return await call_next(request)


# ============================================================
# 예외 핸들러
# ============================================================

@app.exception_handler(HiddenGemException)
async def hidden_gem_exception_handler(request: Request, exc: HiddenGemException):
    """커스텀 예외 핸들러"""
    return JSONResponse(
        status_code=200,  # 비즈니스 에러는 200으로
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """일반 예외 핸들러"""
    print(f"❌ Unhandled exception: {type(exc).__name__}: {exc}")
    return JSONResponse(
        status_code=500,
        content=get_friendly_error_response(exc),
    )


# ============================================================
# 라우터 등록
# ============================================================

app.include_router(api_router, prefix="/api/v1")


# ============================================================
# 루트 엔드포인트
# ============================================================

@app.get("/")
async def root():
    """API 루트"""
    return {
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs" if settings.DEBUG else "Disabled in production",
        "health": "/api/v1/health",
        "search": "/api/v1/search",
    }


# ============================================================
# 개발 서버 실행
# ============================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else 4,
    )
