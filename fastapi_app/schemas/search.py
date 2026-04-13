# fastapi_app/schemas/search.py
"""
Hidden Gem - 검색 API 스키마

Traceability를 위한 search_id (UUID) 포함
AI Curation Summary 필드 포함
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum


# ============================================================
# Enum 정의
# ============================================================

class SearchType(str, Enum):
    """검색 유형"""
    NATURAL_LANGUAGE = "natural"
    GAME_NAME = "game_name"
    SIMILAR = "similar"
    FALLBACK = "fallback"


class PreferenceType(str, Enum):
    """선호도 유형"""
    MUST_HIGH = "MUST_HIGH"
    MUST_LOW = "MUST_LOW"
    MUST_EXACT = "MUST_EXACT"
    NEUTRAL = "NEUTRAL"


# ============================================================
# 요청 스키마
# ============================================================

class MetricPreference(BaseModel):
    """지표 선호도"""
    value: Optional[float] = Field(None, ge=0, le=10)
    type: PreferenceType = PreferenceType.NEUTRAL
    confidence: float = Field(0.8, ge=0, le=1)


class TagPreference(BaseModel):
    """태그 선호도"""
    value: Optional[bool] = None
    type: str = "NEUTRAL"
    confidence: float = Field(0.8, ge=0, le=1)


class SearchRequest(BaseModel):
    """검색 요청"""
    query: str = Field(..., min_length=1, max_length=500, description="검색어")
    
    # 직접 지표 입력 (고급 검색)
    metrics: Optional[Dict[str, MetricPreference]] = Field(None, description="지표별 선호도")
    tags: Optional[Dict[str, TagPreference]] = Field(None, description="태그 필터")
    
    # 검색 옵션
    limit: int = Field(20, ge=1, le=100, description="결과 개수")
    min_score: float = Field(0, ge=0, le=120, description="최소 점수")
    exclude_app_ids: List[int] = Field(default_factory=list, description="제외할 게임")
    
    # 개인화 (로그인 유저)
    user_id: Optional[int] = Field(None, description="유저 ID (개인화용)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "힐링되는 농사 게임",
                "limit": 20,
                "min_score": 70
            }
        }


class SimilarGameRequest(BaseModel):
    """유사 게임 검색 요청"""
    limit: int = Field(20, ge=1, le=100)
    exclude_self: bool = Field(True)


# ============================================================
# 응답 스키마
# ============================================================

class QualityBonusDetail(BaseModel):
    """품질 보너스 상세"""
    bayesian_score: float = Field(0.0, description="Bayesian Smoothing 적용 점수")
    gem_potential: Optional[float] = Field(None, description="AI 평가 잠재력")
    review_count: Optional[int] = Field(None, description="리뷰 수")
    popularity_modifier: float = Field(1.0, description="인기도 보정")
    discovery_bonus: float = Field(0.0, description="발견의 기쁨 보너스")
    final_multiplier: float = Field(1.0, description="최종 배수")


class PersonalBiasDetail(BaseModel):
    """개인화 조정 상세"""
    taste_similarity: float = Field(0.0, description="취향 DNA 유사도")
    history_boost: float = Field(0.0, description="플레이 이력 부스트")
    total_adjustment: float = Field(0.0, description="총 조정값")


class ScoreBreakdown(BaseModel):
    """점수 상세 분석"""
    category_scores: Dict[str, float] = Field(default_factory=dict, description="카테고리별 점수")
    penalty_details: Dict[str, float] = Field(default_factory=dict, description="지표별 페널티")
    matched_metrics: List[str] = Field(default_factory=list, description="잘 맞은 지표")
    mismatched_metrics: List[str] = Field(default_factory=list, description="안 맞은 지표")


class MatchScoreResult(BaseModel):
    """매칭 점수 결과"""
    base_match_score: float = Field(..., ge=0, le=100, description="기본 매칭 점수")
    quality_bonus: QualityBonusDetail = Field(default_factory=QualityBonusDetail)
    personal_bias: PersonalBiasDetail = Field(default_factory=PersonalBiasDetail)
    final_gem_score: float = Field(..., ge=0, le=120, description="최종 점수")
    breakdown: Optional[ScoreBreakdown] = Field(None, description="점수 상세")


class GameResult(BaseModel):
    """게임 검색 결과"""
    app_id: int = Field(..., description="Steam App ID")
    name: str = Field(..., description="게임명")
    genres: str = Field("", description="장르")
    description: str = Field("", max_length=500, description="설명")
    header_image: Optional[str] = Field(None, description="헤더 이미지 URL")
    
    # 점수
    score: MatchScoreResult = Field(..., description="매칭 점수")
    
    # AI 큐레이션 (핵심!)
    ai_curation_summary: Optional[str] = Field(
        None,
        description="AI가 분석한 이 게임의 핵심 매력 한 줄 평"
    )
    
    # 매칭 이유
    match_reasons: List[str] = Field(default_factory=list, description="추천 이유")
    caution_reasons: List[str] = Field(default_factory=list, description="주의 사항")
    
    # 메타
    tags: Dict[str, bool] = Field(default_factory=dict, description="태그")
    analysis_method: str = Field("gpt5.4_batch", description="분석 방법")
    is_fallback: bool = Field(False, description="폴백 추천 여부")
    
    class Config:
        json_schema_extra = {
            "example": {
                "app_id": 1145360,
                "name": "Hades",
                "genres": "액션, 로그라이크",
                "description": "그리스 신화 기반 액션 로그라이크",
                "ai_curation_summary": "💎 타격감과 스토리의 완벽한 조화! 로그라이크의 새로운 기준",
                "score": {
                    "base_match_score": 95.5,
                    "final_gem_score": 112.3
                },
                "match_reasons": ["✅ 액션 템포, 성장 보상이 딱 맞아요!"],
            }
        }


class SearchMetrics(BaseModel):
    """검색 성능 메트릭"""
    total_time_ms: float = Field(0.0, description="총 처리 시간")
    validation_time_ms: float = Field(0.0, description="검증 시간")
    parsing_time_ms: float = Field(0.0, description="파싱 시간")
    retrieval_time_ms: float = Field(0.0, description="검색 시간")
    reranking_time_ms: float = Field(0.0, description="재정렬 시간")
    scoring_time_ms: float = Field(0.0, description="점수 계산 시간")
    
    stage1_candidates: int = Field(0, description="Stage 1 후보 수")
    final_results: int = Field(0, description="최종 결과 수")


class SearchResponse(BaseModel):
    """검색 응답 (Traceability 포함)"""
    
    # Traceability (핵심!)
    search_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="고유 검색 ID (UUID) - 피드백 추적용"
    )
    
    # 상태
    success: bool = Field(True, description="성공 여부")
    
    # 검색 정보
    query: str = Field(..., description="원본 검색어")
    search_type: SearchType = Field(..., description="검색 유형")
    interpretation: Optional[str] = Field(None, description="검색어 해석")
    
    # 결과
    total_candidates: int = Field(0, description="총 후보 수")
    result_count: int = Field(0, description="반환된 결과 수")
    results: List[GameResult] = Field(default_factory=list, description="검색 결과")
    
    # 메타
    processing_time_ms: float = Field(0.0, description="처리 시간 (ms)")
    llm_used: Optional[str] = Field(None, description="사용된 LLM 모델")
    cache_hit: bool = Field(False, description="캐시 히트 여부")
    reference_game: Optional[str] = Field(None, description="참조 게임 (Type A)")
    
    # 성능 상세 (디버그용)
    metrics: Optional[SearchMetrics] = Field(None, description="성능 메트릭")
    
    # 폴백 정보
    fallback_message: Optional[str] = Field(None, description="폴백 메시지")
    fallback_suggestions: Optional[List[str]] = Field(None, description="폴백 제안")
    
    # 타임스탬프
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="응답 시간")
    
    class Config:
        json_schema_extra = {
            "example": {
                "search_id": "550e8400-e29b-41d4-a716-446655440000",
                "success": True,
                "query": "힐링 게임 추천",
                "search_type": "natural",
                "interpretation": "편안하고 아늑한 힐링 게임",
                "total_candidates": 1000,
                "result_count": 20,
                "processing_time_ms": 215.5,
                "cache_hit": False,
            }
        }
