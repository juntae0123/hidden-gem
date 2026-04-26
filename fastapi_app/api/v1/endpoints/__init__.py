# fastapi_app/api/v1/endpoints/__init__.py
"""
Hidden Gem - API v1 Endpoints

각 도메인별 엔드포인트 모듈
"""

from . import search
from . import feedback
from . import health

__all__ = ["search", "feedback", "health"]
