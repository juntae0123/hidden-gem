"""
Hidden Gem API v3.0 - Main Application Entry Point
===================================================
앱 초기화, CORS, 라우터 등록만 담당하는 가벼운 메인 파일
"""

import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# 프로젝트 루트 경로 설정 (backend/ 상위 폴더)
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# .env 로드 (프로젝트 루트에서)
load_dotenv(PROJECT_ROOT / ".env")

# 라우터 임포트
from backend.routers import search, games, debug
from backend.database import engine
from backend.models import Base

# ============== Lifespan 이벤트 ==============
@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행되는 이벤트"""
    # Startup
    print("🚀 Hidden Gem API Starting...")
    print(f"📁 Project Root: {PROJECT_ROOT}")
    print(f"📁 Data Path: {PROJECT_ROOT / 'data'}")
    
    # DB 테이블 생성 (없으면)
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables ready")
    
    yield
    
    # Shutdown
    print("👋 Hidden Gem API Shutting down...")

# ============== FastAPI 앱 생성 ==============
app = FastAPI(
    title="Hidden Gem API",
    description="Steam 숨겨진 명작 발굴 서비스",
    version="3.0.0",
    lifespan=lifespan
)

# ============== CORS 설정 ==============
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== 라우터 등록 ==============
app.include_router(search.router, tags=["Search"])
app.include_router(games.router, prefix="/games", tags=["Games"])
app.include_router(debug.router, prefix="/debug", tags=["Debug"])

# ============== 루트 엔드포인트 ==============
@app.get("/")
def root():
    return {
        "service": "Hidden Gem API",
        "version": "3.0.0",
        "description": "Steam 숨겨진 명작 발굴 서비스",
        "endpoints": {
            "search": "POST /search",
            "games": "GET /games/top, GET /games/{app_id}",
            "health": "GET /health"
        }
    }

@app.get("/health")
def health_check():
    """서버 상태 확인"""
    from backend.database import engine
    from sqlalchemy import text
    
    try:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM games")).scalar()
        return {
            "status": "healthy",
            "database": "connected",
            "game_count": count,
            "version": "3.0.0"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }

# ============== 서버 실행 ==============
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
