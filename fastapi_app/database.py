# fastapi_app/database.py
"""
Hidden Gem - 데이터베이스 연결

SQLAlchemy Async Engine 설정

⚠️ 주의: 테이블 생성/스키마 관리는 Django migrate가 전담
   FastAPI는 읽기/쓰기만 수행
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator

from config import settings


# ============================================================
# 엔진 생성
# ============================================================

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # DEBUG 모드에서 SQL 로깅
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,  # 연결 상태 확인
)


# ============================================================
# 세션 팩토리
# ============================================================

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ============================================================
# Base 클래스 (ORM 모델 기반)
# ============================================================

Base = declarative_base()


# ============================================================
# 의존성 주입용 세션 제공자
# ============================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    DB 세션 의존성
    
    FastAPI의 Depends()에서 사용
    요청 끝나면 자동으로 세션 종료
    """
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


# ============================================================
# 연결 테스트 (헬스체크용)
# ============================================================

async def check_db_connection() -> bool:
    """DB 연결 상태 확인"""
    try:
        async with async_session() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        print(f"❌ DB connection failed: {e}")
        return False


# ============================================================
# ⚠️ 테이블 생성 함수 제거됨
# ============================================================
# Django migrate가 Single Source of Truth
# 아래 함수들은 더 이상 사용하지 않음
#
# async def create_tables():
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)
#
# async def drop_tables():
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.drop_all)
