"""
Hidden Gem - Pydantic Schemas
==============================
API 요청/응답 모델 정의
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

# ============== 요청 모델 ==============
class SearchRequest(BaseModel):
    query: str = Field(..., description="검색 쿼리", min_length=1, max_length=500)
    top_k: int = Field(default=10, ge=1, le=50, description="반환할 결과 수")
    include_maniac: bool = Field(default=False, description="마니아 결과 포함 여부")

# ============== 응답 모델 ==============
class IntentObject(BaseModel):
    id: str
    name: str

class GenreMatch(BaseModel):
    multiplier: float
    reason: str
    is_match: bool

class GameResult(BaseModel):
    app_id: str
    name: str
    genres: str
    developer: str
    description: str
    final_score: float
    status: str
    similarity: float
    matched_intents: List[str]
    boost_reason: Optional[str]
    boost_info: Dict[str, Any]
    scores: Dict[str, int]
    genre_match: Optional[GenreMatch] = None
    fallback_rescued: Optional[bool] = None
    is_popular_fallback: Optional[bool] = None

class GenreAnalysis(BaseModel):
    required_genres: List[str]
    negative_genres: List[str]
    preferred_keywords: List[str]
    core_keywords: List[str]
    reference_game: Optional[str]
    strictness: float

class SearchResponse(BaseModel):
    query: str
    intents: List[IntentObject]
    gems: List[GameResult]
    maniacs: List[GameResult]
    total_candidates: int
    algorithm_version: str
    scoring_formula: str
    fallback_activated: bool
    fallback_message: Optional[str]
    search_stage: int
    genre_analysis: GenreAnalysis
    is_recommendation_mode: bool = False
    error: Optional[str] = None
