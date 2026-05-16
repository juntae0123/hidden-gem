"""
환경 설정 - Docker 컨테이너 DB 연결
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # DB 설정 (Docker hidden_gem_db 컨테이너)
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "juntae"
    DB_PASSWORD: str = "0312"
    DB_NAME: str = "hidden_gem_db"
    
    # 앱 설정
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    
    # 추천 설정
    DEFAULT_RECOMMEND_COUNT: int = 5
    MAX_RECOMMEND_COUNT: int = 20
    
    # gem_potential 스케일 (CSV는 0~100 기준)
    GEM_POTENTIAL_SCALE: float = 100.0
    
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
