"""
환경 설정 모듈 (Environment Configuration)

.env 파일 또는 환경변수에서 설정값을 읽어 앱 전역에서 사용.
pydantic-settings의 BaseSettings로 타입 검증 및 자동 파싱 지원.

Usage:
    from config import settings
    print(settings.DATABASE_URL)
"""

from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    앱 전역 설정 클래스 (Application-wide Settings)

    .env 파일 또는 환경변수에서 자동으로 값을 주입받음.
    Docker 환경에서는 REDIS_HOST=redis, 로컬에서는 REDIS_HOST=localhost.
    """

    # ==================== DB 연결 / Database ====================
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "juntae"
    DB_PASSWORD: str = "0312"
    DB_NAME: str = "hidden_gem_db"

    # ==================== 앱 기본 / App Basic ====================
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # ==================== 추천 엔진 / Recommender ====================
    DEFAULT_RECOMMEND_COUNT: int = 5
    MAX_RECOMMEND_COUNT: int = 20
    GEM_POTENTIAL_SCALE: float = 100.0

    # ==================== OpenAI ====================
    # .env에서 주입, 코드에 키 값 절대 하드코딩 금지
    OPENAI_API_KEY: str = ""

    # OpenAI 비용 가드 한도 / Cost Guard Limits
    OPENAI_DAILY_LIMIT_USD: float = 50.0
    OPENAI_DAILY_WARN_USD: float = 30.0
    OPENAI_HOURLY_LIMIT_USD: float = 5.0
    OPENAI_HOURLY_WARN_USD: float = 3.0

    # ==================== Redis 캐시 / Redis Cache ====================
    # Docker: REDIS_HOST=redis (컨테이너명), 로컬: REDIS_HOST=localhost
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: str = ""  # 직접 지정 시 HOST+PORT 무시 / Overrides HOST+PORT if set

    # 캐시 TTL (초) / Cache TTL in seconds
    CACHE_TTL_SEMANTIC: int = 3600
    CACHE_TTL_BY_GAME: int = 3600
    CACHE_TTL_BY_PREFERENCE: int = 1800

    # ==================== Rate Limiting ====================
    RATE_LIMIT_SEARCH_ANON: str = "10/minute"
    RATE_LIMIT_SEARCH_AUTH: str = "30/minute"
    RATE_LIMIT_RECOMMEND_ANON: str = "20/minute"
    RATE_LIMIT_DEFAULT: str = "60/minute"

    # ==================== 알람 / Alerts ====================
    DISCORD_WEBHOOK_URL: Optional[str] = None

    @property
    def DATABASE_URL(self) -> str:
        """asyncpg 드라이버용 비동기 DB 연결 URL 조합"""
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def REDIS_CONNECTION_URL(self) -> str:
        """
        Redis 연결 URL 자동 조합 (Redis Connection URL)
        REDIS_URL 직접 지정 시 그대로 사용.
        없으면 REDIS_HOST + REDIS_PORT 조합.
        Docker: redis://redis:6379, 로컬: redis://localhost:6379
        """
        if self.REDIS_URL:
            return self.REDIS_URL
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """
    Settings 싱글톤 반환 (Cached Settings Factory)

    lru_cache로 최초 호출 시에만 Settings 인스턴스를 생성하여
    .env 파일을 반복 읽는 오버헤드를 방지.
    """
    return Settings()


# 앱 전역에서 임포트해 사용하는 단일 설정 객체
settings = get_settings()