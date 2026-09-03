# fastapi_app/core/__init__.py
"""
Hidden Gem - Core 모듈

상수, 예외, Rate Limiter, 보안 필터 등 핵심 유틸리티
"""

from .constants import (
    ALL_NUMERIC_METRICS,
    TAG_METRICS,
    CATEGORY_METRICS,
    EMBEDDING_DIMENSION,
)
from .exceptions import (
    HiddenGemException,
    QueryValidationError,
    GameUnrelatedQueryError,
    ProfanityDetectedError,
    RateLimitExceededError,
    QueryParsingError,
    LLMServiceError,
    GameNotFoundError,
    NoResultsError,
    get_friendly_error_response,
)
from .rate_limiter import rate_limit_middleware, RateLimiter
from .metrics_config import METRIC_CONFIGS, CATEGORY_BASE_WEIGHTS, get_metric_config

__all__ = [
    # Constants
    "ALL_NUMERIC_METRICS",
    "TAG_METRICS", 
    "CATEGORY_METRICS",
    "EMBEDDING_DIMENSION",
    # Exceptions
    "HiddenGemException",
    "QueryValidationError",
    "GameUnrelatedQueryError",
    "ProfanityDetectedError",
    "RateLimitExceededError",
    "QueryParsingError",
    "LLMServiceError",
    "GameNotFoundError",
    "NoResultsError",
    "get_friendly_error_response",
    # Rate Limiter
    "rate_limit_middleware",
    "RateLimiter",
    # Metrics Config
    "METRIC_CONFIGS",
    "CATEGORY_BASE_WEIGHTS",
    "get_metric_config",
]
