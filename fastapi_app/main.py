"""
Hidden Gem API 서버 진입점 (FastAPI Application Entry Point)

Steam 인디 게임 AI 추천 서비스의 FastAPI 앱 설정.
- 4,190개 인디 게임 데이터 (GPT-5.4 Batch 분석)
- 60개 지표 (49 수치 + 9 태그 + 2 평가)
- 49차원 벡터 유사도 기반 추천 엔진

실행:
    uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import settings
from routers import games_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    앱 생명주기 관리 (Application Lifespan)

    FastAPI 0.95+ 에서 @app.on_event 대신 권장되는 방식.
    서버 시작/종료 시 로그 출력 및 추후 리소스 초기화/정리에 활용.
    """
    # 서버 시작 시 연결 정보 및 접근 URL 출력
    print("=" * 60)
    print("🚀 Hidden Gem API Server (49D) starting...")
    print(f"📊 Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    print(f"📖 Docs:     http://localhost:8000/docs")
    print(f"🩺 Health:   http://localhost:8000/health")
    print("=" * 60)
    yield  # 앱 실행 구간 (요청 처리)
    print("👋 Shutting down...")


app = FastAPI(
    title="Hidden Gem API",
    description=(
        "🎮 **Steam 인디 게임 AI 추천 서비스**\n\n"
        "## 핵심 기능\n"
        "- **60개 지표 기반 게임 분석** (49 수치 + 9 태그 + 2 평가)\n"
        "- **유사 게임 추천**: 코사인+유클리드 하이브리드 유사도\n"
        "- **선호도 기반 추천**: 원하는 게임 스타일 직접 지정\n\n"
        "## 데이터\n"
        "- 4,190개 인디 게임\n"
        "- GPT-5.4 Batch + Steam CSV 통합"
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# CORS 미들웨어 - 프론트엔드(Next.js 등)에서 크로스 오리진 요청 허용
# 운영 환경에서는 allow_origins를 구체적인 도메인으로 제한 권장
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 모든 출처 허용 (개발용 - 운영 시 변경)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# /api/v1 접두사로 게임 관련 라우터 등록
app.include_router(games_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root():
    """서비스 기본 정보 반환 (Service Info)"""
    return {
        "service": "Hidden Gem API",
        "version": "2.0.0",
        "dimension": "49D vector + 9 tags",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트 - Docker/k8s 컨테이너 상태 확인용 (Health Check)"""
    return {"status": "healthy", "dimension": 49}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
