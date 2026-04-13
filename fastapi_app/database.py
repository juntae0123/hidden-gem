# fastapi_app/database.py
"""
Hidden Gem - 데이터베이스 연결
SQLAlchemy Async Engine
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from config import settings


# 엔진 생성
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

# 세션 팩토리
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base 클래스
Base = declarative_base()


# 의존성 주입용
async def get_db() -> AsyncSession:
    """DB 세션 의존성"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


# 테이블 생성 (개발용)
async def create_tables():
    """테이블 생성"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables():
    """테이블 삭제"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
