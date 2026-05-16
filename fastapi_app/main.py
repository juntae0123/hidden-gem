"""
Hidden Gem API Server
- 4,190개 인디 게임
- 60개 지표 (49 수치 + 9 태그 + 2 평가)
- 49차원 벡터 유사도 기반 추천
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import settings
from routers import games_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print("🚀 Hidden Gem API Server (49D) starting...")
    print(f"📊 Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    print(f"📖 Docs:     http://localhost:8000/docs")
    print(f"🩺 Health:   http://localhost:8000/health")
    print("=" * 60)
    yield
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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터
app.include_router(games_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root():
    return {
        "service": "Hidden Gem API",
        "version": "2.0.0",
        "dimension": "49D vector + 9 tags",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "dimension": 49}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
