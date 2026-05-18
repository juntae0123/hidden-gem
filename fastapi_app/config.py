"""
환경 설정 모듈 (Environment Configuration)

.env 파일 또는 환경변수에서 설정값을 읽어 앱 전역에서 사용.
pydantic-settings의 BaseSettings로 타입 검증 및 자동 파싱 지원.

Usage:
    from config import settings
    print(settings.DATABASE_URL)
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    앱 전역 설정 클래스 (Application-wide Settings)

    .env 파일 또는 환경변수에서 자동으로 값을 주입받음.
    pydantic-settings가 타입 변환 및 기본값 처리를 담당.

    Attributes:
        DB_HOST: PostgreSQL 호스트 (Docker 네트워크에서는 컨테이너명 사용)
        GEM_POTENTIAL_SCALE: gem_potential 정규화 기준값 (CSV는 0~100, 내부 로직은 100 기준)
    """

    # ---- DB 연결 설정 (Docker hidden_gem_db 컨테이너) ----
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "juntae"
    DB_PASSWORD: str = "0312"
    DB_NAME: str = "hidden_gem_db"

    # ---- 앱 기본 설정 ----
    DEBUG: bool = False           # True 시 SQLAlchemy SQL 쿼리 로그 출력
    API_V1_PREFIX: str = "/api/v1"  # 모든 게임 API 라우터의 접두사

    # ---- 추천 엔진 설정 ----
    DEFAULT_RECOMMEND_COUNT: int = 5   # 기본 추천 개수
    MAX_RECOMMEND_COUNT: int = 20      # API 요청 가능한 최대 추천 개수

    # gem_potential 스케일 - CSV 원본은 0~100, 하이브리드 점수 계산 시 나눗값으로 사용
    GEM_POTENTIAL_SCALE: float = 100.0

    @property
    def DATABASE_URL(self) -> str:
        """asyncpg 드라이버용 비동기 DB 연결 URL 조합"""
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    class Config:
        env_file = ".env"       # 프로젝트 루트의 .env 우선 적용
        case_sensitive = True   # 환경변수명 대소문자 구분 (DB_HOST != db_host)
        extra = "ignore"        # .env에 정의되지 않은 키는 무시


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
