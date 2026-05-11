# fastapi_app/main.py
"""
Hidden Gem API Server - 49차원 추천 서비스
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import settings
from routers import games_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Hidden Gem API Server (49D) starting...")
    print(f"📊 Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    yield
    print("👋 Shutting down...")


app = FastAPI(
    title="Hidden Gem API",
    description="""
    🎮 Steam 인디 게임 AI 추천 서비스 - 49차원 완전체
    
    ## 핵심 기능
    - **49개 수치 지표 + 9개 태그 기반** 게임 분석
    - **유사 게임 추천**: 코사인+유클리드 하이브리드 유사도
    - **선호도 기반 추천**: 원하는 스타일 직접 지정
    
    ## 데이터
    - 4,190개 인디 게임
    - GPT-5.4 Batch로 추출한 고품질 지표
    """,
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(games_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root():
    return {
        "service": "Hidden Gem API",
        "version": "2.0.0 (49D)",
        "docs": "/docs",
        "health": "OK"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "dimension": 49}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
