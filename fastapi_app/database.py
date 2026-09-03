"""
SQLAlchemy 비동기 DB 연결 모듈 (Async Database Connection)

Django가 생성한 PostgreSQL 테이블을 FastAPI에서 읽기 전용으로 접근.
asyncpg 드라이버 + SQLAlchemy 비동기 엔진 조합으로 고성능 처리.

Notes:
    - Django ORM과 FastAPI SQLAlchemy는 동일 DB를 공유
    - 쓰기 작업은 Django Admin 또는 management command를 통해 수행
"""

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
from config import settings

# ---- 비동기 엔진 생성 (Async Engine) ----
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,      # DEBUG=True 시 실행 SQL을 콘솔에 출력 (운영에서는 False)
    pool_size=10,             # 연결 풀 기본 크기 - 동시 처리 요청 수에 맞게 조정
    max_overflow=20,          # 풀 초과 시 임시 생성 가능한 추가 연결 수 (peak load 대응)
    pool_pre_ping=True,       # 쿼리 전 연결 유효성 확인 - 끊어진 연결 자동 재시도
    pool_recycle=3600,        # 1시간 이상 된 연결 재생성 - PostgreSQL 유휴 연결 타임아웃 방지
)

# ---- 세션 팩토리 (Session Factory) ----
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # commit 후 객체 속성 만료 비활성 - 추가 쿼리 없이 재사용 가능
    autocommit=False,        # 명시적 commit 필요 (읽기 전용이므로 사실상 불필요)
    autoflush=False,         # 자동 flush 비활성 - 의도치 않은 INSERT/UPDATE 방지
)

# ---- ORM Base 클래스 ----
# fastapi_app/models/*.py 의 모든 ORM 모델이 이 Base를 상속
Base = declarative_base()


async def get_db() -> AsyncSession:
    """
    FastAPI 의존성 주입용 DB 세션 제공 (Dependency-Injected DB Session)

    FastAPI의 Depends(get_db)로 각 요청마다 독립 세션을 생성하고,
    요청 완료 후 자동으로 세션을 닫음 (context manager 방식).

    Yields:
        AsyncSession: 요청 범위의 비동기 DB 세션

    Example:
        @router.get("/games")
        async def get_games(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()  # 예외 발생 여부와 무관하게 세션 반드시 종료
