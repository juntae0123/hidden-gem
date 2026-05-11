# fastapi_app/schemas/game.py
"""
Pydantic 스키마 - API 요청/응답 모델 (49차원)
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime


# ==================== 지표 스키마 ====================

class GameMetricBase(BaseModel):
    """49개 수치 지표 스키마"""
    
    # ===== VIBE (7) =====
    cozy_factor: Optional[float] = Field(None, ge=0, le=10, description="아늑함/편안함")
    horror_factor: Optional[float] = Field(None, ge=0, le=10, description="공포 강도")
    gore_level: Optional[float] = Field(None, ge=0, le=10, description="고어/잔인함")
    humor_rating: Optional[float] = Field(None, ge=0, le=10, description="유머/코믹 요소")
    dark_fantasy_vibe: Optional[float] = Field(None, ge=0, le=10, description="다크 판타지 분위기")
    epic_scale: Optional[float] = Field(None, ge=0, le=10, description="서사적 규모감")
    melancholy: Optional[float] = Field(None, ge=0, le=10, description="우울함/멜랑콜리")
    
    # ===== DEMANDS (5) =====
    reflex_demand: Optional[float] = Field(None, ge=0, le=10, description="반사신경 요구도")
    strategic_depth: Optional[float] = Field(None, ge=0, le=10, description="전략적 깊이")
    grind_factor: Optional[float] = Field(None, ge=0, le=10, description="노가다/반복 요소")
    time_pressure: Optional[float] = Field(None, ge=0, le=10, description="시간 압박감")
    learning_curve: Optional[float] = Field(None, ge=0, le=10, description="학습 곡선")
    
    # ===== MECHANICS (9) =====
    freedom_level: Optional[float] = Field(None, ge=0, le=10, description="자유도")
    action_pacing: Optional[float] = Field(None, ge=0, le=10, description="액션 템포")
    rng_dependency: Optional[float] = Field(None, ge=0, le=10, description="운/랜덤 의존도")
    growth_reward: Optional[float] = Field(None, ge=0, le=10, description="성장 보상감")
    exploration_reward: Optional[float] = Field(None, ge=0, le=10, description="탐험 보상감")
    management_complexity: Optional[float] = Field(None, ge=0, le=10, description="관리 복잡도")
    stealth_importance: Optional[float] = Field(None, ge=0, le=10, description="스텔스 중요도")
    session_length: Optional[float] = Field(None, ge=0, le=10, description="세션 길이")
    narrative_linearity: Optional[float] = Field(None, ge=0, le=10, description="서사 선형성")
    
    # ===== MECHANICS EXTRA (2) =====
    puzzle_complexity: Optional[float] = Field(None, ge=0, le=10, description="퍼즐 복잡도")
    platforming_precision: Optional[float] = Field(None, ge=0, le=10, description="플랫포밍 정밀도")
    
    # ===== SOCIAL (5) =====
    coop_synergy: Optional[float] = Field(None, ge=0, le=10, description="협동 시너지")
    competitive_stress: Optional[float] = Field(None, ge=0, le=10, description="경쟁 스트레스")
    npc_interaction: Optional[float] = Field(None, ge=0, le=10, description="NPC 상호작용")
    user_creation: Optional[float] = Field(None, ge=0, le=10, description="유저 창작 요소")
    multiplayer_scale: Optional[float] = Field(None, ge=0, le=10, description="멀티플레이어 규모")
    
    # ===== PRESENTATION (5) =====
    lore_richness: Optional[float] = Field(None, ge=0, le=10, description="세계관/로어 깊이")
    choice_consequence: Optional[float] = Field(None, ge=0, le=10, description="선택의 결과")
    visual_spectacle: Optional[float] = Field(None, ge=0, le=10, description="시각적 화려함")
    environmental_storytelling: Optional[float] = Field(None, ge=0, le=10, description="환경 스토리텔링")
    soundtrack_impact: Optional[float] = Field(None, ge=0, le=10, description="사운드트랙 영향력")
    
    # ===== SYSTEM/UX (7) - 신규 =====
    build_variety: Optional[float] = Field(None, ge=0, le=10, description="빌드 다양성")
    progression_clarity: Optional[float] = Field(None, ge=0, le=10, description="진행 명확성")
    save_flexibility: Optional[float] = Field(None, ge=0, le=10, description="저장 유연성")
    difficulty_accessibility: Optional[float] = Field(None, ge=0, le=10, description="난이도 접근성")
    tutorial_quality: Optional[float] = Field(None, ge=0, le=10, description="튜토리얼 품질")
    ui_ux_polish: Optional[float] = Field(None, ge=0, le=10, description="UI/UX 완성도")
    modding_support: Optional[float] = Field(None, ge=0, le=10, description="모딩 지원")
    
    # ===== ART/AUDIO (3) - 신규 =====
    art_style_uniqueness: Optional[float] = Field(None, ge=0, le=10, description="아트 스타일 독창성")
    audio_design: Optional[float] = Field(None, ge=0, le=10, description="오디오 디자인")
    animation_quality: Optional[float] = Field(None, ge=0, le=10, description="애니메이션 품질")
    
    # ===== OTHER (2) - 신규 =====
    world_reactivity: Optional[float] = Field(None, ge=0, le=10, description="월드 반응성")
    community_dependency: Optional[float] = Field(None, ge=0, le=10, description="커뮤니티 의존도")
    
    # ===== NEW (4) - 신규 =====
    narrative_depth: Optional[float] = Field(None, ge=0, le=10, description="서사 깊이")
    replay_value: Optional[float] = Field(None, ge=0, le=10, description="리플레이 가치")
    endgame_content: Optional[float] = Field(None, ge=0, le=10, description="엔드게임 콘텐츠")
    monetization_fairness: Optional[float] = Field(None, ge=0, le=10, description="과금 공정성")


class GameMetricTags(BaseModel):
    """9개 Boolean 태그"""
    is_turn_based: bool = False
    is_real_time: bool = False
    is_first_person: bool = False
    is_third_person: bool = False
    has_permadeath: bool = False
    has_base_building: bool = False
    has_crafting: bool = False
    is_anime_style: bool = False
    is_retro_aesthetic: bool = False


class GameMetricResponse(GameMetricBase, GameMetricTags):
    """게임 지표 응답 (49개 수치 + 9개 태그 + AI 평가)"""
    gem_potential: Optional[float] = Field(None, description="AI 평가 잠재력 (0~10)")
    confidence_score: Optional[float] = Field(None, description="분석 신뢰도 (0~1)")
    analysis_summary: str = ""
    
    class Config:
        from_attributes = True


# ==================== 게임 스키마 ====================

class GameBase(BaseModel):
    """게임 기본 정보"""
    app_id: int
    name: str
    genres: str = ""
    developer: str = ""
    publisher: str = ""


class GameResponse(GameBase):
    """게임 상세 응답"""
    id: int
    short_description: str = ""
    header_image: str = ""
    release_date: Optional[date] = None
    price: Optional[float] = None
    
    # 스팀 데이터
    steam_positive_ratio: Optional[float] = None
    review_count: int = 0
    is_free: bool = False
    is_indie: bool = True
    
    # AI 콘텐츠
    one_line_summary: str = ""
    marketing_hook: str = ""
    target_personas: List[str] = []
    similar_games: List[str] = []
    unique_selling_points: List[str] = []
    
    # 분석 상태
    is_analyzed: bool = False
    analysis_method: str = "pending"
    
    class Config:
        from_attributes = True


class GameWithMetrics(GameResponse):
    """게임 + 60개 지표 전체 응답"""
    metrics: Optional[GameMetricResponse] = None


class GameSearchResult(BaseModel):
    """검색 결과 (간략 정보)"""
    app_id: int
    name: str
    genres: str
    header_image: str
    one_line_summary: str
    gem_potential: Optional[float] = None
    steam_positive_ratio: Optional[float] = None
    review_count: int = 0


# ==================== 추천 관련 스키마 ====================

class RecommendByGameRequest(BaseModel):
    """특정 게임 기반 추천 요청"""
    app_id: int = Field(..., description="기준 게임의 Steam App ID")
    count: int = Field(5, ge=1, le=20, description="추천 개수")
    exclude_same_developer: bool = Field(False, description="같은 개발사 제외")


class RecommendByPreferenceRequest(BaseModel):
    """유저 선호도 기반 추천 요청
    
    예시:
    - cozy 게임: {"cozy_factor": 8, "time_pressure": 2}
    - 전략 게임: {"strategic_depth": 9, "reflex_demand": 2}
    - 스토리 게임: {"narrative_depth": 9, "lore_richness": 8}
    """
    preferences: Dict[str, float] = Field(
        ..., 
        description="원하는 지표와 값 (0~10)",
        example={"cozy_factor": 8, "time_pressure": 2, "grind_factor": 3}
    )
    required_tags: List[str] = Field(
        default=[],
        description="필수 태그",
        example=["has_crafting"]
    )
    excluded_tags: List[str] = Field(
        default=[],
        description="제외할 태그",
        example=["has_permadeath"]
    )
    count: int = Field(5, ge=1, le=20)
    min_gem_potential: float = Field(0, ge=0, le=10, description="최소 gem_potential")


class RecommendedGame(BaseModel):
    """추천 결과 단일 게임"""
    app_id: int
    name: str
    genres: str
    header_image: str
    one_line_summary: str
    marketing_hook: str
    
    # 추천 점수
    similarity_score: float = Field(..., description="유사도 점수 (0~1)")
    gem_potential: Optional[float] = None
    
    # 추천 이유
    match_reasons: List[str] = Field(default=[], description="추천 이유")
    
    # 주요 지표 미리보기
    key_metrics: Dict[str, float] = Field(default={}, description="핵심 지표 5개")


class RecommendationResponse(BaseModel):
    """추천 응답"""
    query_type: str = Field(..., description="'by_game' 또는 'by_preference'")
    reference_game: Optional[str] = Field(None, description="기준 게임 이름")
    total_candidates: int = Field(..., description="검색된 후보 수")
    recommendations: List[RecommendedGame]
