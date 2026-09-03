# fastapi_app/models/__init__.py
"""
Hidden Gem - SQLAlchemy Models

⚠️ DB 스키마는 Django migrate가 관리
   여기서는 ORM 매핑만 정의
"""

from .game import Game, GameMetric
from .user import User, SearchLog, UserFeedback

__all__ = [
    "Game",
    "GameMetric",
    "User",
    "SearchLog",
    "UserFeedback",
]
