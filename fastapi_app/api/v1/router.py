# fastapi_app/api/v1/router.py
"""
Hidden Gem - API v1 통합 라우터
"""

from fastapi import APIRouter

from api.v1.endpoints import search, feedback, health


# ============================================================
# 메인 라우터
# ============================================================

api_router = APIRouter()

# 검색 API
api_router.include_router(
    search.router,
    tags=["Search"],
)

# 피드백 API
api_router.include_router(
    feedback.router,
    tags=["Feedback"],
)

# 헬스체크
api_router.include_router(
    health.router,
    tags=["Health"],
)
