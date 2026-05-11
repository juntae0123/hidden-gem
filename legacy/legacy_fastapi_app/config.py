# fastapi_app/config.py
"""
Hidden Gem - 환경 설정
Pydantic Settings로 타입 안전한 설정 관리
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
from functools import lru_cache


class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # ============================================================
    # 기본 설정
    # ============================================================
    APP_NAME: str = "Hidden Gem API"
    VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False)
    SECRET_KEY: str = Field(default="change-me-in-production")
    
    # ============================================================
    # 데이터베이스 (PostgreSQL + pgvector)
    # ============================================================
    DB_HOST: str = Field(default="localhost")
    DB_PORT: int = Field(default=5432)
    DB_NAME: str = Field(default="hidden_gem_db")
    DB_USER: str = Field(default="juntae")
    DB_PASSWORD: str = Field(default="0312")
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def SYNC_DATABASE_URL(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    # ============================================================
    # Redis (캐싱)
    # ============================================================
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)
    
    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # Semantic Cache 설정
    CACHE_TTL_SECONDS: int = Field(default=3600)  # 1시간
    CACHE_SIMILARITY_THRESHOLD: float = Field(default=0.92)  # 92% 유사도 이상이면 캐시 히트
    
    # ============================================================
    # OpenAI
    # ============================================================
    OPENAI_API_KEY: str = Field(default="")
    
    # 모델 설정
    LLM_PRIMARY_MODEL: str = Field(default="gpt-4o-mini")
    LLM_FALLBACK_MODEL: str = Field(default="gpt-4o")
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-small")
    EMBEDDING_DIMENSIONS: int = Field(default=512)  # 차원 축소 (비용 절감)
    
    # ============================================================
    # 검색 설정
    # ============================================================
    RETRIEVAL_TOP_K: int = Field(default=1000)
    FINAL_RESULTS_LIMIT: int = Field(default=20)
    MIN_CONFIDENCE_THRESHOLD: float = Field(default=0.6)
    
    # ============================================================
    # Rate Limiting
    # ============================================================
    RATE_LIMIT_PER_MINUTE: int = Field(default=60)
    RATE_LIMIT_BURST: int = Field(default=10)
    
    # ============================================================
    # CORS
    # ============================================================
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000"])
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # <--- 이 한 줄만 추가하세요!

@lru_cache()
def get_settings() -> Settings:
    """설정 싱글톤"""
    return Settings()


settings = get_settings()
