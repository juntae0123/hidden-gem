# fastapi_app/api/v1/router.py
"""
Hidden Gem - API v1 통합 라우터

모든 v1 엔드포인트를 하나로 통합
"""

from fastapi import APIRouter

from api.v1.endpoints import search, feedback, health


# ============================================================
# 메인 라우터 생성
# ============================================================

api_router = APIRouter()


# ============================================================
# 엔드포인트 라우터 등록
# ============================================================

# 검색 API (/api/v1/search/...)
api_router.include_router(
    search.router,
    tags=["Search"],
)

# 피드백 API (/api/v1/feedback/...)
api_router.include_router(
    feedback.router,
    tags=["Feedback"],
)

# 헬스체크 API (/api/v1/health/...)
api_router.include_router(
    health.router,
    tags=["Health"],
)
