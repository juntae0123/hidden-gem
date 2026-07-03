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
    OPENAI_API_KEY: str = ""
    OPENAI_DAILY_LIMIT_USD: float = 50.0
    OPENAI_DAILY_WARN_USD: float = 30.0
    OPENAI_HOURLY_LIMIT_USD: float = 5.0
    OPENAI_HOURLY_WARN_USD: float = 3.0

    # ==================== Redis 캐시 / Redis Cache ====================
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: str = ""

    CACHE_TTL_SEMANTIC: int = 3600
    CACHE_TTL_BY_GAME: int = 3600
    CACHE_TTL_BY_PREFERENCE: int = 1800

    # ==================== Rate Limiting ====================
    RATE_LIMIT_SEARCH_ANON: str = "10/minute"
    RATE_LIMIT_SEARCH_AUTH: str = "30/minute"
    RATE_LIMIT_RECOMMEND_ANON: str = "20/minute"
    RATE_LIMIT_DEFAULT: str = "60/minute"
    RATE_LIMIT_TASTE: str = "60/minute"  # 행동 로그 수집

    # ==================== 알람 / Alerts ====================
    DISCORD_WEBHOOK_URL: Optional[str] = None

    # ==================== Sentry ====================
    SENTRY_DSN: str = ""
    SENTRY_ENV: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 1.0
    APP_VERSION: str = "3.2.0"

    # ==================== 어드민 / Admin ====================
    # /taste/stats 등 운영 엔드포인트 Basic Auth용
    ADMIN_USERNAME: str = ""
    ADMIN_PASSWORD: str = ""
    
    # ==================== JWT (Django 토큰 검증용) ====================
    # Django와 동일한 SECRET_KEY로 JWT 검증 → user_id 추출
    DJANGO_SECRET_KEY: str = "dev-secret-key-12345"
    JWT_ALGORITHM: str = "HS256"

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


settings = get_settings()