"""
Pydantic API Schemas v4 (Request/Response Models)

Korean: FastAPI 엔드포인트 요청 검증 + 응답 직렬화용 Pydantic v2 스키마 모듈.

v3 → v4 변경사항:
    - RecommendByPreferenceRequest: must_not, use_masking 필드 추가
    - 기존 모든 스키마 구조/이름 완전 유지 (하위 호환)

스키마 구조:
    응답 모델:
        GameMetricResponse  - 60개 지표 전체 응답
        GameResponse        - 게임 기본 정보 응답
        GameWithMetrics     - 게임 + 지표 통합 응답
        GameSearchResult    - 검색 결과 간략 응답

    요청 모델:
        RecommendByGameRequest       - by-game 추천 요청 (app_id + count)
        RecommendByPreferenceRequest - by-preference 추천 요청 v4 (preferences + tags + must_not)

    추천 응답:
        RecommendedGame        - 추천 결과 단일 게임
        RecommendationResponse - 추천 최종 응답 (메타 + 결과 목록)
"""

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ==================== 지표 응답 / Metric Response ====================

class GameMetricResponse(BaseModel):
    """
    Full 60-metric response schema (49 numeric + 9 boolean + 2 evaluation).
    Korean: 60개 지표 전체 응답 스키마 (49 수치 + 9 태그 + 2 평가).
    """
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

    # ===== BOOLEAN (9) =====
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
    gem_percentile: Optional[float] = None
    confidence_score: Optional[float] = None


# ==================== 게임 응답 / Game Response ====================

class GameResponse(BaseModel):
    """
    Game basic info response schema.
    Korean: 게임 기본 정보 응답 스키마 (Steam 메타데이터 + AI 생성 콘텐츠).
    """
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


class GameSearchResult(BaseModel):
    """
    Lightweight game search result schema for list views.
    Korean: 검색 결과 목록용 경량 게임 스키마.
    """
    model_config = ConfigDict(from_attributes=True)

    app_id: int
    name: str
    genres: str = ""
    header_image: str = ""
    one_line_summary: str = ""
    gem_potential: Optional[float] = None
    steam_positive_ratio: Optional[float] = None
    review_count: int = 0


class GameWithMetrics(BaseModel):
    """
    Full game detail schema including all 60 metrics.
    Korean: 60개 지표 전체가 포함된 게임 상세 스키마.
    """
    model_config = ConfigDict(from_attributes=True)

    app_id: int
    name: Optional[str] = None
    genres: Optional[str] = None
    developer: Optional[str] = None
    description: Optional[str] = None
    header_image: Optional[str] = None
    one_line_summary: Optional[str] = None
    marketing_hook: Optional[str] = None
    steam_positive_ratio: Optional[float] = None
    review_count: Optional[int] = None
    price: Optional[float] = None
    is_active: bool = True
    is_analyzed: bool = False
    metrics: Optional[GameMetricResponse] = None


# ==================== 추천 요청 / Recommendation Requests ====================

class RecommendByGameRequest(BaseModel):
    """
    Request schema for game-based recommendation.
    Korean: 게임 기반 유사 게임 추천 요청 스키마.

    Example:
        {"app_id": 1086940, "count": 5, "exclude_same_developer": false}
    """
    app_id: int = Field(..., description="기준 게임 Steam App ID")
    count: int = Field(default=5, ge=1, le=20, description="추천 게임 수 (1~20)")
    exclude_same_developer: bool = Field(
        default=False,
        description="동일 개발사 게임 제외 여부",
    )


class RecommendByPreferenceRequest(BaseModel):
    """
    Request schema for preference-based recommendation with dynamic masking (v4).
    Korean: 동적 마스킹 + must_not 하드 필터가 추가된 선호도 기반 추천 요청 스키마 v4.

    v4 신규 필드:
        must_not: 명시적 제외 조건 딕셔너리 {지표명: 임계값}.
            해당 지표 값 >= 임계값인 게임을 결과에서 완전 제외.
            Boolean 태그는 값 0.5 기준으로 True면 제외.
            예시:
                {"horror_factor": 4.0}  → horror_factor >= 4인 게임 제외
                {"gore_level": 3.0}     → 고어 수치 높은 게임 제외
                {"has_permadeath": 0.5} → 퍼마데스 게임 제외

        use_masking: 동적 마스킹 활성화 여부 (기본 True).
            True  → 지정한 지표만 활성화, 무관 지표 96% 노이즈 제거 (변별력 5배↑)
            False → 기존 49개 전체 지표 방식 (하위 호환)

    Example (v4):
        {
            "preferences": {"cozy_factor": 8, "time_pressure": 2},
            "required_tags": ["has_crafting"],
            "excluded_tags": ["has_permadeath"],
            "must_not": {"horror_factor": 4.0, "gore_level": 3.0},
            "count": 5,
            "min_gem_potential": 60,
            "use_masking": true
        }
    """
    preferences: Dict[str, float] = Field(
        ...,
        description="원하는 지표와 값 (0~10 스케일). 예) {\"cozy_factor\": 8}",
    )
    required_tags: List[str] = Field(
        default=[],
        description="반드시 포함해야 할 Boolean 태그. 예) [\"has_crafting\"]",
    )
    excluded_tags: List[str] = Field(
        default=[],
        description="반드시 제외해야 할 Boolean 태그. 예) [\"has_permadeath\"]",
    )
    must_not: Optional[Dict[str, float]] = Field(
        default=None,
        description=(
            "명시적 제외 조건 {지표명: 임계값}. "
            "지표 값 >= 임계값이면 해당 게임 제외. "
            "예) {\"horror_factor\": 4.0} → horror_factor >= 4인 게임 제외."
        ),
    )
    count: int = Field(default=5, ge=1, le=20, description="추천 게임 수 (1~20)")
    min_gem_potential: float = Field(
        default=0,
        ge=0,
        le=100,
        description="최소 gem_potential 필터 (0~100 스케일)",
    )
    use_masking: bool = Field(
        default=True,
        description=(
            "동적 마스킹 활성화 (기본 True). "
            "True → 지정 지표만 활성화하여 변별력 5배 향상. "
            "False → 기존 49개 전체 지표 방식."
        ),
    )

    @field_validator("preferences")
    @classmethod
    def validate_preference_values(cls, v: Dict[str, float]) -> Dict[str, float]:
        """
        Validate preference values are within 0~10 range.
        Korean: 선호도 값이 0~10 범위인지 검증.
        """
        for field, value in v.items():
            if not (0.0 <= value <= 10.0):
                raise ValueError(
                    f"preferences 값 범위 오류: {field}={value} (0~10 사이여야 함)"
                )
        return v

    @field_validator("must_not")
    @classmethod
    def validate_must_not_values(
        cls, v: Optional[Dict[str, float]]
    ) -> Optional[Dict[str, float]]:
        """
        Validate must_not threshold values are non-negative.
        Korean: must_not 임계값이 음수가 아닌지 검증.
        """
        if v is None:
            return v
        for field, threshold in v.items():
            if threshold < 0:
                raise ValueError(
                    f"must_not 임계값은 0 이상이어야 합니다: {field}={threshold}"
                )
        return v


# ==================== 추천 응답 / Recommendation Response ====================

class RecommendedGame(BaseModel):
    """
    Single recommended game with similarity score and match reasons.
    Korean: 추천 결과 단일 게임 스키마 (유사도 점수 + 추천 이유 포함).

    v6 추가:
        score_breakdown: Core/X-Factor/Gem 점수 분해 (UI 표시용)
        v6_identity: 게임 정체성 ("어두운 판타지 + 대서사")
        v6_strengths: X-Factor 독창적 강점 목록

    similarity_score: 0~99 최종 점수 (Core 75 + X-Factor 18 + Gem 6)
    match_reasons: 추천 이유 텍스트 목록 (최대 5개)
    key_metrics: 이 게임의 특징적인 지표 {지표명: 값} (최대 5개)
    """
    app_id: int
    name: str
    genres: str = ""
    header_image: str = ""
    one_line_summary: str = ""
    marketing_hook: str = ""

    similarity_score: float                # 0~99 (v6 최종 점수)
    gem_potential: Optional[float] = None  # AI 평가 잠재력 (0~100 스케일)

    # v6 점수 분해 (UI 표시용)
    score_breakdown: Dict[str, float] = {}  # {core_score, xfactor_score, gem_score, final_score}
    v6_identity: str = ""                    # "어두운 판타지 + 대서사"
    v6_strengths: List[Dict] = []            # [{metric, value, label, is_exceptional}]

    match_reasons: List[str] = []          # 추천 이유 한국어 텍스트 목록
    key_metrics: Dict[str, float] = {}     # 특징 지표 딕셔너리

class RecommendationResponse(BaseModel):
    """
    Recommendation API final response wrapper.
    Korean: 추천 API 최종 응답 래퍼 스키마.

    query_type: "by_game" | "by_preference" | "semantic"
    reference_game: by-game 추천 시 기준 게임명, 나머지는 null
    """
    query_type: str                        # "by_game" | "by_preference" | "semantic"
    reference_game: Optional[str] = None   # by-game: 기준 게임명, 나머지: null
    total_candidates: int                  # 실제 반환된 추천 게임 수
    recommendations: List[RecommendedGame]