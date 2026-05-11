# fastapi_app/schemas/__init__.py
from .game import (
    GameMetricBase, GameMetricTags, GameMetricResponse,
    GameBase, GameResponse, GameWithMetrics, GameSearchResult,
    RecommendByGameRequest, RecommendByPreferenceRequest,
    RecommendedGame, RecommendationResponse
)
