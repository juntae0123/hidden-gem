# fastapi_app/schemas/__init__.py
"""
Hidden Gem - Pydantic Schemas

API 요청/응답 스키마 정의
"""

from .search import (
    SearchRequest,
    SearchResponse,
    GameResult,
    MetricPreference,
    TagPreference,
    PreferenceType,
    SearchType,
)
from .feedback import (
    FeedbackRequest,
    FeedbackResponse,
    FeedbackType,
    UserTasteProfile,
)

__all__ = [
    # Search
    "SearchRequest",
    "SearchResponse",
    "GameResult",
    "MetricPreference",
    "TagPreference",
    "PreferenceType",
    "SearchType",
    # Feedback
    "FeedbackRequest",
    "FeedbackResponse",
    "FeedbackType",
    "UserTasteProfile",
]
