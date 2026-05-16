"""
Pydantic 스키마 - API 요청/응답 모델
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import date


# ==================== 지표 응답 ====================

class GameMetricResponse(BaseModel):
    """60개 지표 응답 (49 수치 + 9 태그 + 2 평가)"""
    model_config = ConfigDict(from_attributes=True)
    
    # ===== VIBE (7) =====
    cozy_factor: Optional[float] = None
    horror_factor: Optional[float] = None
    gore_level: Optional[float] = None
    humor_rating: Optional[float] = None
    dark_fantasy_vibe: Optional[float] = None
    epic_scale: Optional[float] = None
    melancholy: Optional[float] = None
    
    # ===== DEMANDS (5) =====
    reflex_demand: Optional[float] = None
    strategic_depth: Optional[float] = None
    grind_factor: Optional[float] = None
    time_pressure: Optional[float] = None
    learning_curve: Optional[float] = None
    
    # ===== MECHANICS (9) =====
    freedom_level: Optional[float] = None
    action_pacing: Optional[float] = None
    rng_dependency: Optional[float] = None
    growth_reward: Optional[float] = None
    exploration_reward: Optional[float] = None
    management_complexity: Optional[float] = None
    stealth_importance: Optional[float] = None
    session_length: Optional[float] = None
    narrative_linearity: Optional[float] = None
    
    # ===== MECHANICS EXTRA (2) =====
    puzzle_complexity: Optional[float] = None
    platforming_precision: Optional[float] = None
    
    # ===== SOCIAL (5) =====
    coop_synergy: Optional[float] = None
    competitive_stress: Optional[float] = None
    npc_interaction: Optional[float] = None
    user_creation: Optional[float] = None
    multiplayer_scale: Optional[float] = None
    
    # ===== PRESENTATION (5) =====
    lore_richness: Optional[float] = None
    choice_consequence: Optional[float] = None
    visual_spectacle: Optional[float] = None
    environmental_storytelling: Optional[float] = None
    soundtrack_impact: Optional[float] = None
    
    # ===== SYSTEM/UX (7) =====
    build_variety: Optional[float] = None
    progression_clarity: Optional[float] = None
    save_flexibility: Optional[float] = None
    difficulty_accessibility: Optional[float] = None
    tutorial_quality: Optional[float] = None
    ui_ux_polish: Optional[float] = None
    modding_support: Optional[float] = None
    
    # ===== ART/AUDIO (3) =====
    art_style_uniqueness: Optional[float] = None
    audio_design: Optional[float] = None
    animation_quality: Optional[float] = None
    
    # ===== OTHER (2) =====
    world_reactivity: Optional[float] = None
    community_dependency: Optional[float] = None
    
    # ===== NEW (4) =====
    narrative_depth: Optional[float] = None
    replay_value: Optional[float] = None
    endgame_content: Optional[float] = None
    monetization_fairness: Optional[float] = None
    
    # ===== TAGS (9) =====
    is_turn_based: bool = False
    is_real_time: bool = False
    is_first_person: bool = False
    is_third_person: bool = False
    has_permadeath: bool = False
    has_base_building: bool = False
    has_crafting: bool = False
    is_anime_style: bool = False
    is_retro_aesthetic: bool = False
    
    # ===== EVAL (2) =====
    gem_potential: Optional[float] = None
    confidence_score: Optional[float] = None
    
    # ===== REASONING =====
    analysis_summary: str = ""


# ==================== 게임 응답 ====================

class GameResponse(BaseModel):
    """게임 기본 응답"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    app_id: int
    name: str = ""
    genres: str = ""
    developer: str = ""
    publisher: str = ""
    short_description: str = ""
    header_image: str = ""
    release_date: Optional[date] = None
    price: Optional[float] = None
    
    steam_positive_ratio: Optional[float] = None
    review_count: int = 0
    is_free: bool = False
    is_indie: bool = True
    is_early_access: bool = False
    
    one_line_summary: str = ""
    marketing_hook: str = ""
    target_personas: List[Any] = []
    similar_games: List[Any] = []
    unique_selling_points: List[Any] = []
    
    is_analyzed: bool = False
    analysis_method: str = "pending"


class GameWithMetrics(GameResponse):
    """게임 + 60개 지표"""
    metrics: Optional[GameMetricResponse] = None


class GameSearchResult(BaseModel):
    """검색 결과 (간략 정보)"""
    app_id: int
    name: str
    genres: str = ""
    header_image: str = ""
    one_line_summary: str = ""
    gem_potential: Optional[float] = None
    steam_positive_ratio: Optional[float] = None
    review_count: int = 0


# ==================== 추천 요청 ====================

class RecommendByGameRequest(BaseModel):
    """특정 게임 기반 추천 요청"""
    app_id: int = Field(..., description="기준 게임의 Steam App ID")
    count: int = Field(5, ge=1, le=20, description="추천 개수")
    exclude_same_developer: bool = Field(False, description="같은 개발사 제외")


class RecommendByPreferenceRequest(BaseModel):
    """유저 선호도 기반 추천 요청
    
    Example:
        {
            "preferences": {"cozy_factor": 8, "time_pressure": 2},
            "required_tags": ["has_crafting"],
            "excluded_tags": ["has_permadeath"],
            "count": 5,
            "min_gem_potential": 60
        }
    """
    preferences: Dict[str, float] = Field(
        ...,
        description="원하는 지표와 값 (0~10 스케일)",
    )
    required_tags: List[str] = Field(default=[], description="필수 태그")
    excluded_tags: List[str] = Field(default=[], description="제외할 태그")
    count: int = Field(5, ge=1, le=20)
    min_gem_potential: float = Field(
        0, ge=0, le=100, 
        description="최소 gem_potential (0~100 스케일)"
    )


# ==================== 추천 응답 ====================

class RecommendedGame(BaseModel):
    """추천 결과 단일 게임"""
    app_id: int
    name: str
    genres: str = ""
    header_image: str = ""
    one_line_summary: str = ""
    marketing_hook: str = ""
    
    similarity_score: float
    gem_potential: Optional[float] = None
    
    match_reasons: List[str] = []
    key_metrics: Dict[str, float] = {}


class RecommendationResponse(BaseModel):
    """추천 응답"""
    query_type: str
    reference_game: Optional[str] = None
    total_candidates: int
    recommendations: List[RecommendedGame]
