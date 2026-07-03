"""
Hidden Gem Recommendation Engine v5 (Weighted Scoring + Anchor System)

Korean: 가중치 차등 + 앵커 점수 시스템이 도입된 추천 엔진 v5.

v4 → v5 핵심 변경사항:
    1. 가중치 4단계 차등
       관련(primary) 5.0x / 연관(secondary) 2.0x / 중립 0.5x / 무관 0.1x
       전체 49개 지표 사용 (6개 제한 철회) — 무관 지표도 0.1x로 약하게 반영

    2. 절대 점수 시스템 (0~100, 초과 없음)
       기준 게임 = 100점 앵커 (by-game 추천 시)
       raw 유클리드 거리 → sigmoid 변환 → 0~99점 매핑
       min-max 상대 정규화 폐기

    3. 기준 게임 제외
       by-game 추천 결과에서 기준 게임 자신 제외
       기준 게임은 100점 앵커로 별도 반환

    4. score_breakdown 응답 구조
       metric_score / embedding_score / gem_bonus / final_score 분리 반환
       유저 데이터 기반 확장 용이 (Phase 3)

알고리즘:
    지표 점수 (60%) = 가중치 유클리드 유사도 (40%) + 가중치 코사인 유사도 (20%)
    임베딩 점수 (40%) = pgvector 코사인 유사도
    gem 보너스 = gem_percentile 기반 (최대 +5점)
    최종 = 지표(60%) + 임베딩(40%) → sigmoid → 0~99 → gem보너스 → max 99
"""

import json
import math
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
from openai import AsyncOpenAI
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings
from models.game import (
    BOOLEAN_TAG_FIELDS,
    NUMERIC_METRIC_FIELDS,
    Game,
    GameMetric,
)

from schemas.game import RecommendedGame
from services.score_v6 import calculate_score_v6



# ==================== 한국어 라벨 / Korean Metric Labels ====================

METRIC_LABELS_KO: Dict[str, str] = {
    "cozy_factor": "아늑함", "horror_factor": "공포", "gore_level": "고어",
    "humor_rating": "유머", "dark_fantasy_vibe": "다크판타지", "epic_scale": "스케일",
    "melancholy": "멜랑콜리", "reflex_demand": "반응속도", "strategic_depth": "전략깊이",
    "grind_factor": "노가다", "time_pressure": "시간압박", "learning_curve": "학습곡선",
    "freedom_level": "자유도", "action_pacing": "액션템포", "rng_dependency": "RNG의존도",
    "growth_reward": "성장보상", "exploration_reward": "탐험보상",
    "management_complexity": "관리복잡도", "stealth_importance": "스텔스",
    "session_length": "세션길이", "narrative_linearity": "서사선형성",
    "puzzle_complexity": "퍼즐복잡도", "platforming_precision": "플랫폼정밀도",
    "coop_synergy": "협동시너지", "competitive_stress": "경쟁스트레스",
    "npc_interaction": "NPC상호작용", "user_creation": "유저창작",
    "multiplayer_scale": "멀티규모", "lore_richness": "세계관밀도",
    "choice_consequence": "선택결과", "visual_spectacle": "시각연출",
    "environmental_storytelling": "환경서사", "soundtrack_impact": "사운드트랙",
    "build_variety": "빌드다양성", "progression_clarity": "진행명확성",
    "save_flexibility": "저장유연성", "difficulty_accessibility": "난이도접근성",
    "tutorial_quality": "튜토리얼", "ui_ux_polish": "UI/UX완성도",
    "modding_support": "모딩지원", "art_style_uniqueness": "아트독창성",
    "audio_design": "오디오디자인", "animation_quality": "애니메이션",
    "world_reactivity": "세계반응성", "community_dependency": "커뮤니티의존",
    "narrative_depth": "서사깊이", "replay_value": "리플레이",
    "endgame_content": "엔드게임", "monetization_fairness": "과금공정성",
}


# ==================== 가중치 상수 / Weight Constants ====================

# v5 가중치 4단계 / v5 four-tier weight system
W_PRIMARY   = 5.0   # 관련 지표 (primary)   — 주된 결정 요소
W_SECONDARY = 2.0   # 연관 지표 (secondary) — 보조 결정
W_NEUTRAL   = 0.5   # 중립 지표 (neutral)   — 약하게 반영
W_IRRELEVANT = 0.1  # 무관 지표 (irrelevant) — 거의 영향 없음, but 0은 아님

# 점수 상한 / Score ceiling (기준 게임=100, 나머지 max 99)
SCORE_MAX = 99.0
SCORE_ANCHOR = 100.0  # 기준 게임 앵커 점수

# sigmoid 변환 파라미터 (거리 → 점수) / Sigmoid params for distance-to-score
# 거리 0 → 99점, 거리 클수록 0점 수렴
SIGMOID_SCALE = 3.5   # 거리 감도 (클수록 민감) / Distance sensitivity


# ==================== 검색 의도 분류 / Search Intent Types ====================

class SearchIntent(str, Enum):
    """
    Search intent categories for dynamic metric weighting.
    Korean: 동적 가중치 적용에 사용하는 검색 의도 5가지 카테고리.
    """
    EXACT_MATCH = "exact_match"
    SIMILARITY  = "similarity"
    MOOD        = "mood"
    FEATURE     = "feature"
    META        = "meta"
    UNKNOWN     = "unknown"


# ==================== 의도별 지표 그룹 / Intent → Metric Groups ====================
# v5: primary(5x) / secondary(2x) 정의. 나머지는 neutral(0.5x) 또는 irrelevant(0.1x)

INTENT_TO_METRIC_GROUPS: Dict[str, Dict[str, List[str]]] = {
    "mood_cozy": {
        "primary":   ["cozy_factor", "time_pressure", "grind_factor"],
        "secondary": ["humor_rating", "narrative_depth", "save_flexibility",
                      "horror_factor", "gore_level"],  # 공포/고어 낮을수록 좋음 반영
    },
    "mood_horror": {
        "primary":   ["horror_factor", "gore_level", "dark_fantasy_vibe"],
        "secondary": ["melancholy", "environmental_storytelling", "time_pressure"],
    },
    "mood_dark": {
        "primary":   ["dark_fantasy_vibe", "melancholy", "horror_factor"],
        "secondary": ["lore_richness", "narrative_depth", "epic_scale", "gore_level"],
    },
    "mood_narrative": {
        "primary":   ["narrative_depth", "lore_richness", "choice_consequence"],
        "secondary": ["environmental_storytelling", "npc_interaction", "melancholy",
                      "narrative_linearity"],
    },
    "feature_strategy": {
        "primary":   ["strategic_depth", "management_complexity", "learning_curve"],
        "secondary": ["rng_dependency", "build_variety", "session_length",
                      "time_pressure", "grind_factor"],
    },
    "feature_narrative": {
        "primary":   ["narrative_depth", "lore_richness", "choice_consequence"],
        "secondary": ["environmental_storytelling", "npc_interaction", "narrative_linearity"],
    },
    "feature_coop": {
        "primary":   ["coop_synergy", "multiplayer_scale"],
        "secondary": ["user_creation", "community_dependency", "competitive_stress"],
    },
    "feature_action": {
        "primary":   ["action_pacing", "reflex_demand", "time_pressure"],
        "secondary": ["platforming_precision", "learning_curve", "epic_scale"],
    },
    "feature_puzzle": {
        "primary":   ["puzzle_complexity", "learning_curve", "freedom_level"],
        "secondary": ["narrative_depth", "session_length", "strategic_depth"],
    },
    "feature_exploration": {
        "primary":   ["exploration_reward", "freedom_level", "world_reactivity"],
        "secondary": ["lore_richness", "environmental_storytelling", "session_length"],
    },
    "feature_roguelike": {
        "primary":   ["rng_dependency", "replay_value", "learning_curve"],
        "secondary": ["build_variety", "endgame_content", "growth_reward",
                      "grind_factor"],
    },
    "feature_management": {
        "primary":   ["management_complexity", "strategic_depth", "freedom_level"],
        "secondary": ["session_length", "grind_factor", "growth_reward",
                      "world_reactivity"],
    },
}

# 분위기 키워드 / Mood keywords
MOOD_KEYWORDS: Dict[str, str] = {
    "힐링": "mood_cozy", "cozy": "mood_cozy", "아늑": "mood_cozy",
    "평화": "mood_cozy", "잔잔": "mood_cozy", "편안": "mood_cozy",
    "공포": "mood_horror", "horror": "mood_horror", "무서": "mood_horror",
    "공포게임": "mood_horror", "겁": "mood_horror",
    "다크판타지": "mood_dark", "dark": "mood_dark", "어두": "mood_dark",
    "음침": "mood_dark", "우울": "mood_dark",
    "스토리": "mood_narrative", "서사": "mood_narrative", "narrative": "mood_narrative",
    "감동": "mood_narrative", "시나리오": "mood_narrative",
}

# 기능 키워드 / Feature keywords
FEATURE_KEYWORDS: Dict[str, str] = {
    "전략": "feature_strategy", "strategy": "feature_strategy", "경영": "feature_management",
    "rts": "feature_strategy", "턴제": "feature_strategy",
    "협동": "feature_coop", "coop": "feature_coop", "멀티": "feature_coop",
    "액션": "feature_action", "action": "feature_action", "격투": "feature_action",
    "퍼즐": "feature_puzzle", "puzzle": "feature_puzzle",
    "탐험": "feature_exploration", "오픈월드": "feature_exploration",
    "로그라이크": "feature_roguelike", "roguelike": "feature_roguelike",
    "로그라이트": "feature_roguelike",
    "식민지": "feature_management", "도시건설": "feature_management",
    "림월드": "feature_management",  # 림월드류 직접 키워드
}

# 유사 게임 키워드 / Similarity keywords
SIMILARITY_KEYWORDS: List[str] = [
    "같은", "비슷한", "similar", "like", "닮은", "feels like", "esque",
    "같은 느낌", "류", "스타일",
]

# 메타 키워드 / Meta keywords
META_KEYWORDS: List[str] = [
    "리뷰", "평점", "인기", "인디", "무료", "할인", "신작", "최신",
]


# ==================== must_not 제외 키워드 / Exclusion Keywords ====================

EXCLUSION_KEYWORDS: Dict[str, str] = {
    "공포": "horror_factor",
    "공포게임": "horror_factor",
    "잔인": "gore_level",
    "고어": "gore_level",
    "노가다": "grind_factor",
    "반복작업": "grind_factor",
    "경쟁": "competitive_stress",
    "pvp": "competitive_stress",
    "멀티": "multiplayer_scale",
    "멀티플레이": "multiplayer_scale",
    "퍼마데스": "has_permadeath",
    "영구죽음": "has_permadeath",
}

EXCLUSION_TRIGGERS: List[str] = [
    "없는", "없이", "제외", "빼고", "싫어", "싫은", "no ", "without",
    "not ", "avoid", "exclude", "안 좋아", "말고", "제외하고",
]

MUST_NOT_THRESHOLD: float = 4.0


# ==================== NULL 폴백 정책 / NULL Fallback Policy ====================

class FallbackType(str, Enum):
    """
    Three-level NULL fallback strategy types.
    Korean: NULL 지표에 적용할 3단계 폴백 전략 타입.
    """
    ZERO        = "zero"
    GLOBAL_MEAN = "global_mean"
    GENRE_MEAN  = "genre_mean"


NULL_FALLBACK_POLICY: Dict[str, FallbackType] = {
    # ZERO: 해당 없음 = 0이 맞음
    "multiplayer_scale":     FallbackType.ZERO,
    "coop_synergy":          FallbackType.ZERO,
    "competitive_stress":    FallbackType.ZERO,
    "modding_support":       FallbackType.ZERO,
    "horror_factor":         FallbackType.ZERO,
    "gore_level":            FallbackType.ZERO,
    "platforming_precision": FallbackType.ZERO,
    "puzzle_complexity":     FallbackType.ZERO,
    "stealth_importance":    FallbackType.ZERO,
    "community_dependency":  FallbackType.ZERO,
    "user_creation":         FallbackType.ZERO,
    # GLOBAL_MEAN: 프레젠테이션 지표
    "visual_spectacle":      FallbackType.GLOBAL_MEAN,
    "audio_design":          FallbackType.GLOBAL_MEAN,
    "animation_quality":     FallbackType.GLOBAL_MEAN,
    "ui_ux_polish":          FallbackType.GLOBAL_MEAN,
    "art_style_uniqueness":  FallbackType.GLOBAL_MEAN,
    "soundtrack_impact":     FallbackType.GLOBAL_MEAN,
    # GENRE_MEAN: 장르 의존 지표
    "strategic_depth":       FallbackType.GENRE_MEAN,
    "narrative_depth":       FallbackType.GENRE_MEAN,
    "lore_richness":         FallbackType.GENRE_MEAN,
    "exploration_reward":    FallbackType.GENRE_MEAN,
    "endgame_content":       FallbackType.GENRE_MEAN,
    "replay_value":          FallbackType.GENRE_MEAN,
}

GLOBAL_METRIC_MEANS: Dict[str, float] = {
    "visual_spectacle": 7.0, "audio_design": 6.8, "animation_quality": 6.5,
    "ui_ux_polish": 6.5, "art_style_uniqueness": 6.2, "soundtrack_impact": 6.5,
}

GENRE_METRIC_DEFAULTS: Dict[str, float] = {
    "strategic_depth": 5.5, "narrative_depth": 5.5, "lore_richness": 5.0,
    "exploration_reward": 5.5, "endgame_content": 5.0, "replay_value": 6.0,
}


# ==================== SearchIntentClassifier ====================

class SearchIntentClassifier:
    """
    Classifies search intent and determines metric weight tiers.
    Korean: 검색 의도 분류 후 지표별 가중치 등급을 결정하는 분류기.
    """

    def classify(self, query: str) -> Tuple[SearchIntent, Optional[str]]:
        """
        Classify search intent and return group name.
        Korean: 검색어 의도 분류. (intent, group_name) 반환.
        """
        q_lower = query.lower()
        for kw in SIMILARITY_KEYWORDS:
            if kw in q_lower:
                return SearchIntent.SIMILARITY, None
        for kw in META_KEYWORDS:
            if kw in q_lower:
                return SearchIntent.META, None
        for kw, group in MOOD_KEYWORDS.items():
            if kw in q_lower:
                return SearchIntent.MOOD, group
        for kw, group in FEATURE_KEYWORDS.items():
            if kw in q_lower:
                return SearchIntent.FEATURE, group
        return SearchIntent.UNKNOWN, None

    def extract_must_not(self, query: str) -> Dict[str, float]:
        """
        Extract must_not constraints from query.
        Korean: 쿼리에서 must_not 제외 조건 추출.
        """
        q_lower = query.lower()
        must_not: Dict[str, float] = {}
        has_trigger = any(t in q_lower for t in EXCLUSION_TRIGGERS)
        if not has_trigger:
            return must_not
        for keyword, metric in EXCLUSION_KEYWORDS.items():
            if keyword in q_lower:
                must_not[metric] = 0.5 if metric in BOOLEAN_TAG_FIELDS else MUST_NOT_THRESHOLD
        return must_not

    def get_weight_map(
        self,
        group_name: Optional[str],
        preferences: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """
        Build per-metric weight map using four-tier system.
        Korean: 지표별 가중치 맵 생성 (4단계: primary/secondary/neutral/irrelevant).

        primary(5x) > secondary(2x) > neutral(0.5x) > irrelevant(0.1x)
        preferences가 있으면 해당 지표는 최소 primary(5x) 보장.
        group_name 없으면 전체 neutral(0.5x) — 고른 비교.

        Returns:
            Dict[str, float]: {지표명: 가중치}
        """
        # 기본값: 전체 neutral / Default: all neutral
        weight_map: Dict[str, float] = {f: W_NEUTRAL for f in NUMERIC_METRIC_FIELDS}

        primary_set: Set[str] = set()
        secondary_set: Set[str] = set()

        if group_name and group_name in INTENT_TO_METRIC_GROUPS:
            group = INTENT_TO_METRIC_GROUPS[group_name]
            primary_set = set(group.get("primary", []))
            secondary_set = set(group.get("secondary", []))

            for f in NUMERIC_METRIC_FIELDS:
                if f in primary_set:
                    weight_map[f] = W_PRIMARY
                elif f in secondary_set:
                    weight_map[f] = W_SECONDARY
                else:
                    # 나머지: 관련 없는 지표 → irrelevant (0.1x)
                    # 단, 중요 공통 지표는 neutral 유지
                    weight_map[f] = W_IRRELEVANT

            # 공통 중요 지표는 neutral 최소 보장 / Always neutral for key cross-genre metrics
            for f in ["replay_value", "ui_ux_polish", "save_flexibility",
                      "difficulty_accessibility", "monetization_fairness"]:
                if f not in primary_set and f not in secondary_set:
                    weight_map[f] = W_NEUTRAL

        # preferences 지표는 primary 보장 / Preference metrics always get primary weight
        if preferences:
            for f in preferences:
                if f in NUMERIC_METRIC_FIELDS:
                    weight_map[f] = max(weight_map.get(f, W_PRIMARY), W_PRIMARY)

        return weight_map


# ==================== NULL 폴백 / NULL Fallback ====================

def resolve_null(field: str, value: Optional[float]) -> float:
    """
    Resolve NULL metric value using fallback policy.
    Korean: NULL 지표 값을 폴백 정책으로 해결. None 없이 항상 float 반환.
    """
    if value is not None:
        return float(value)
    policy = NULL_FALLBACK_POLICY.get(field)
    if policy == FallbackType.ZERO:
        return 0.0
    if policy == FallbackType.GLOBAL_MEAN:
        return GLOBAL_METRIC_MEANS.get(field, 5.0)
    if policy == FallbackType.GENRE_MEAN:
        return GENRE_METRIC_DEFAULTS.get(field, 5.0)
    return 5.0  # 기본 중립값


# ==================== 점수 계산 / Score Computation ====================

def build_weighted_vector(
    metric: GameMetric,
    weight_map: Dict[str, float],
) -> np.ndarray:
    """
    Build weighted 49D metric vector.
    Korean: 가중치 맵 적용한 49차원 지표 벡터 생성. NULL은 폴백 처리.
    """
    vec = np.empty(len(NUMERIC_METRIC_FIELDS), dtype=np.float32)
    for i, field in enumerate(NUMERIC_METRIC_FIELDS):
        raw = getattr(metric, field, None)
        if isinstance(raw, (int, float)):
            val = float(raw)
        else:
            val = resolve_null(field, None)
        vec[i] = val * weight_map.get(field, W_NEUTRAL)
    return vec


def build_preference_vector(
    preferences: Dict[str, float],
    weight_map: Dict[str, float],
) -> np.ndarray:
    """
    Build weighted 49D preference target vector.
    Korean: 선호도 기반 타겟 벡터 생성. 미지정 지표는 폴백값으로 채움.
    """
    vec = np.empty(len(NUMERIC_METRIC_FIELDS), dtype=np.float32)
    for i, field in enumerate(NUMERIC_METRIC_FIELDS):
        if field in preferences:
            val = preferences[field]
        else:
            val = resolve_null(field, None)
        vec[i] = val * weight_map.get(field, W_NEUTRAL)
    return vec


def weighted_euclidean_similarity(
    v1: np.ndarray,
    v2: np.ndarray,
    n_active: int,
) -> float:
    """
    Compute sigmoid-mapped euclidean similarity (0~1).
    Korean: 유클리드 거리를 sigmoid로 0~1 유사도로 변환. 활성 차원 수로 정규화.

    거리=0 → 1.0, 거리 클수록 → 0.0 수렴.
    n_active: 실제 활성 지표 수 (정규화 기준).
    """
    dist = float(np.linalg.norm(v1 - v2))
    # 활성 차원으로 정규화된 평균 거리 / Normalize by active dims
    norm_dist = dist / max(n_active ** 0.5, 1.0)
    # sigmoid 변환: 1 / (1 + exp(dist/scale - 1))
    return 1.0 / (1.0 + math.exp(norm_dist / SIGMOID_SCALE - 1.0))


def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """
    Compute cosine similarity (0~1).
    Korean: 코사인 유사도 (0~1).
    """
    n1 = np.linalg.norm(v1)
    n2 = np.linalg.norm(v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    return float(max(0.0, min(np.dot(v1, v2) / (n1 * n2), 1.0)))


def compute_metric_score(
    target_vec: np.ndarray,
    cand_vec: np.ndarray,
    n_active: int,
) -> float:
    """
    Compute metric similarity score (0~1).
    Korean: 지표 유사도 점수. 유클리드(67%) + 코사인(33%) 혼합.

    유클리드: 실제 값 차이 (변별력 핵심)
    코사인: 게임 성격/방향성 유사도
    """
    eucl = weighted_euclidean_similarity(target_vec, cand_vec, n_active)
    cos = cosine_similarity(target_vec, cand_vec)
    return eucl * 0.67 + cos * 0.33


def to_display_score(raw_score: float, gem_bonus: float) -> float:
    """
    Convert raw similarity (0~1) to display score (0~99).
    Korean: raw 유사도(0~1) → 표시 점수(0~99). gem 보너스 합산. 상한 99.

    100점은 기준 게임 앵커 전용. 나머지 최대 99.
    """
    base = raw_score * 94.0      # 0~94 범위로 스케일
    gem_add = gem_bonus * 5.0    # gem 보너스 최대 +5
    return min(round(base + gem_add, 1), SCORE_MAX)


# ==================== GameRecommender (v5) ====================

class GameRecommender:
    """
    Hybrid game recommender v5 with four-tier weighting and anchor score system.
    Korean: 4단계 가중치 + 앵커 점수 시스템이 도입된 하이브리드 추천 엔진 v5.

    점수 시스템:
        기준 게임 = 100점 앵커 (by-game 추천 시)
        나머지 게임 = 0~99점 (절대 초과 불가)
        지표 유사도(60%) + 임베딩 유사도(40%) → 0~94 + gem보너스 최대+5 → max 99

    추천 방식:
        1. by-game:       기준 게임 지표+임베딩 → 4단계 가중치 유사도 → 앵커 점수
        2. by-preference: 선호도 지표 primary 가중치 → 전체 49개 비교
        3. semantic:      GPT 분석 + pgvector 임베딩 → 지표 힌트 보정
    """

    def __init__(self):
        self.dimension = len(NUMERIC_METRIC_FIELDS)  # 49
        self._openai: Optional[AsyncOpenAI] = None
        self.intent_classifier = SearchIntentClassifier()

    def _get_openai(self) -> AsyncOpenAI:
        """
        Get or create singleton OpenAI client.
        Korean: 싱글톤 OpenAI 클라이언트 반환.
        """
        if self._openai is None:
            self._openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._openai

    def _parse_embedding(self, metric: GameMetric) -> Optional[np.ndarray]:
        """
        Parse stored embedding to numpy array.
        Korean: DB 저장 임베딩 → numpy 배열 파싱. 실패 시 None.
        """
        emb = getattr(metric, "embedding", None)
        if emb is None:
            return None
        try:
            if isinstance(emb, str):
                emb = json.loads(emb)
            arr = np.array(emb, dtype=np.float32)
            if arr.shape[0] == 1536:
                return arr
        except Exception:
            pass
        return None

    def _calculate_gem_bonus(self, game: Game, metric: GameMetric) -> float:
        """
        Calculate gem bonus (0~1.0, applied as +5 max in display score).
        Korean: gem_percentile 기반 Hidden Gem 보너스 (0~1.0). 표시 점수에서 최대 +5점.

        리뷰 1,000개 미만 게임 우대.
        """
        gem = (
            metric.gem_percentile
            if metric.gem_percentile is not None
            else (metric.gem_potential if metric.gem_potential is not None else 50.0)
        )
        confidence = metric.confidence_score if metric.confidence_score is not None else 0.5
        reviews = game.review_count or 0
        review_bonus = 0.3 * (1.0 - reviews / 1000.0) if reviews < 1000 else 0.0
        gem_normalized = (gem / 100.0) * 0.7
        return min((gem_normalized + review_bonus) * confidence, 1.0)

    def _check_tags(
        self,
        metric: GameMetric,
        required: List[str],
        excluded: List[str],
    ) -> bool:
        """
        Check boolean tag conditions.
        Korean: Boolean 태그 필터 검사.
        """
        for tag in required:
            if tag in BOOLEAN_TAG_FIELDS and not getattr(metric, tag, False):
                return False
        for tag in excluded:
            if tag in BOOLEAN_TAG_FIELDS and getattr(metric, tag, False):
                return False
        return True

    def _check_must_not(
        self,
        metric: GameMetric,
        must_not: Dict[str, float],
    ) -> bool:
        """
        Check must_not hard filter.
        Korean: must_not 하드 필터. 지표 값 ≥ 임계값이면 False(제외).
        """
        for metric_name, threshold in must_not.items():
            if metric_name in BOOLEAN_TAG_FIELDS:
                if getattr(metric, metric_name, False):
                    return False
            elif metric_name in NUMERIC_METRIC_FIELDS:
                value = getattr(metric, metric_name, None)
                if value is not None and float(value) >= threshold:
                    return False
        return True

    def _get_key_metrics(self, metric: GameMetric) -> Dict[str, float]:
        """
        Extract top key metrics (extreme values prioritized).
        Korean: 극단값(≤2 or ≥8) 우선으로 핵심 지표 최대 5개 추출.
        """
        all_metrics: Dict[str, float] = {}
        for field in NUMERIC_METRIC_FIELDS:
            v = getattr(metric, field, None)
            if v is not None:
                all_metrics[field] = float(v)

        extreme = {k: v for k, v in all_metrics.items() if v <= 2 or v >= 8}
        priority = [
            "cozy_factor", "strategic_depth", "horror_factor", "narrative_depth",
            "freedom_level", "action_pacing", "lore_richness", "replay_value",
            "management_complexity", "rng_dependency",
        ]
        result: Dict[str, float] = {}
        for p in priority:
            if p in extreme and len(result) < 5:
                result[p] = extreme[p]
        for k, v in extreme.items():
            if len(result) >= 5:
                break
            if k not in result:
                result[k] = v
        if len(result) < 5:
            for p in priority:
                if len(result) >= 5:
                    break
                if p not in result and p in all_metrics:
                    result[p] = all_metrics[p]
        return result

    def _generate_match_reasons_from_preferences(
        self,
        metric: GameMetric,
        preferences: Dict[str, float],
        weight_map: Dict[str, float],
    ) -> List[str]:
        """
        Generate match reasons from preference comparison.
        Korean: 선호도 목표값과 실제 값 비교로 추천 이유 생성. 가중치 높은 지표 우선.
        """
        reasons: List[str] = []
        # 가중치 높은 순으로 정렬 / Sort by weight descending
        sorted_prefs = sorted(
            preferences.items(),
            key=lambda x: weight_map.get(x[0], W_NEUTRAL),
            reverse=True,
        )
        for field, target_value in sorted_prefs:
            if field not in NUMERIC_METRIC_FIELDS:
                continue
            raw = getattr(metric, field, None)
            actual_value = float(raw) if raw is not None else resolve_null(field, None)
            diff = abs(actual_value - target_value)
            if diff <= 2.0:
                label = METRIC_LABELS_KO.get(field, field)
                if target_value >= 7:
                    reasons.append(f"✓ {label} 높음 ({actual_value:.1f})")
                elif target_value <= 3:
                    reasons.append(f"✓ {label} 낮음 ({actual_value:.1f})")
                else:
                    reasons.append(f"✓ {label} 적절 ({actual_value:.1f})")
        return reasons[:5]

    def _generate_match_reasons_from_target(
        self,
        target_metric: GameMetric,
        cand_metric: GameMetric,
        weight_map: Dict[str, float],
    ) -> List[str]:
        """
        Extract common features between target and candidate games.
        Korean: 기준/후보 게임 공통 특징 추출. 가중치 높은 지표 우선.
        """
        common: List[Tuple[float, str, str, float]] = []
        for field in NUMERIC_METRIC_FIELDS:
            t_raw = getattr(target_metric, field, None)
            c_raw = getattr(cand_metric, field, None)
            target = float(t_raw) if t_raw is not None else resolve_null(field, None)
            cand = float(c_raw) if c_raw is not None else resolve_null(field, None)
            w = weight_map.get(field, W_NEUTRAL)
            if abs(target - cand) <= 1.5:
                if target >= 7 and cand >= 7:
                    common.append((w, field, "공통적으로 높음", cand))
                elif target <= 3 and cand <= 3:
                    common.append((w, field, "공통적으로 낮음", cand))
        # 가중치 높은 순 정렬
        common.sort(key=lambda x: x[0], reverse=True)
        return [
            f"✓ {METRIC_LABELS_KO.get(f, f)} {desc} ({v:.1f})"
            for _, f, desc, v in common[:5]
        ]

    # ==================== 추천 메인 로직 / Main Recommendation Logic ====================

    async def recommend_by_game(
        self,
        db: AsyncSession,
        app_id: int,
        count: int = 5,
        exclude_same_developer: bool = False,
        query_hint: Optional[str] = None,
    ) -> Tuple[Optional[Game], List[Dict]]:
        """
        Recommend similar games with anchor score system (v5).
        Korean: 앵커 점수 시스템 기반 게임 유사 추천 v5.

        기준 게임 = 100점 앵커, 결과에서 제외.
        query_hint: 의도 분류용 힌트 쿼리 (예: "림월드 같은 게임").
        → 힌트 있으면 해당 의도의 가중치 맵 사용.
        → 힌트 없으면 전체 neutral 가중치.

        Returns:
            (기준 게임, [{"game": Game, "metric": GameMetric, "score": float,
                          "score_breakdown": dict}, ...])
        """
        # 기준 게임 조회
        stmt = (
            select(Game)
            .options(selectinload(Game.metrics))
            .where(Game.app_id == app_id)
        )
        result = await db.execute(stmt)
        target_game = result.scalar_one_or_none()

        if not target_game or not target_game.metrics:
            return None, []

        # 의도 분류 → 가중치 맵 / Classify intent → weight map
        _, group_name = (
            self.intent_classifier.classify(query_hint)
            if query_hint else (SearchIntent.UNKNOWN, None)
        )
        weight_map = self.intent_classifier.get_weight_map(group_name)

        # 기준 게임 벡터 / Target vectors
        target_vec = build_weighted_vector(target_game.metrics, weight_map)
        target_emb = self._parse_embedding(target_game.metrics)

        # 후보 게임 조회 (기준 게임 제외) / Candidates excluding target
        stmt = (
            select(Game)
            .options(selectinload(Game.metrics))
            .where(Game.is_active == True)    # noqa: E712
            .where(Game.is_analyzed == True)  # noqa: E712
            .where(Game.app_id != app_id)     # 기준 게임 제외
        )
        if exclude_same_developer and target_game.developer:
            stmt = stmt.where(Game.developer != target_game.developer)

        result = await db.execute(stmt)
        candidates = result.scalars().all()

        # 활성 지표 수 (가중치 > 0인 지표) / Count active metrics
        n_active = sum(1 for w in weight_map.values() if w > 0)

        # 점수 계산 / Compute scores
        scored: List[Dict] = []
        for game in candidates:
            if not game.metrics:
                continue

            cand_vec = build_weighted_vector(game.metrics, weight_map)
            cand_emb = self._parse_embedding(game.metrics)

            # 지표 점수 / Metric score
            metric_score = compute_metric_score(target_vec, cand_vec, n_active)

            # 임베딩 점수 / Embedding score
            if target_emb is not None and cand_emb is not None:
                emb_score = cosine_similarity(target_emb, cand_emb)
                raw_score = metric_score * 0.60 + emb_score * 0.40
            else:
                emb_score = 0.0
                raw_score = metric_score

            # gem 보너스 / gem bonus
            gem_bonus = self._calculate_gem_bonus(game, game.metrics)

            # 표시 점수 (0~99) / Display score
            display_score = to_display_score(raw_score, gem_bonus)

            scored.append({
                "game": game,
                "metric": game.metrics,
                "score": display_score,
                "score_breakdown": {
                    "metric_score": round(metric_score * 100, 1),
                    "embedding_score": round(emb_score * 100, 1),
                    "gem_bonus": round(gem_bonus * 5, 1),
                    "final_score": display_score,
                },
                "target_metric": target_game.metrics,
                "weight_map": weight_map,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return target_game, scored[:count]

    async def recommend_by_preference(
        self,
        db: AsyncSession,
        preferences: Dict[str, float],
        required_tags: Optional[List[str]] = None,
        excluded_tags: Optional[List[str]] = None,
        must_not: Optional[Dict[str, float]] = None,
        count: int = 5,
        min_gem_potential: float = 0.0,
        use_masking: bool = True,
    ) -> List[Dict]:
        """
        Preference-based recommendation with four-tier weighting (v5).
        Korean: 4단계 가중치 기반 선호도 추천 v5. 전체 49개 지표 사용.

        preferences 지표 → primary(5x)
        나머지 지표 → neutral(0.5x) 또는 irrelevant(0.1x)
        전체 지표 비교 → 변별력 확보

        Returns:
            [{"game": Game, "metric": GameMetric, "score": float,
              "score_breakdown": dict, "weight_map": dict}, ...]
        """
        required_tags = required_tags or []
        excluded_tags = excluded_tags or []
        must_not = must_not or {}

        # 가중치 맵: preferences 지표 primary / Weight map: preferences = primary
        weight_map = self.intent_classifier.get_weight_map(
            group_name=None,
            preferences=preferences,
        )

        # 타겟 벡터 / Target vector
        target_vec = build_preference_vector(preferences, weight_map)
        n_active = sum(1 for w in weight_map.values() if w >= W_NEUTRAL)

        # 후보 조회 / Fetch candidates
        stmt = (
            select(Game)
            .options(selectinload(Game.metrics))
            .where(Game.is_active == True)    # noqa: E712
            .where(Game.is_analyzed == True)  # noqa: E712
        )
        result = await db.execute(stmt)
        candidates = result.scalars().all()

        scored: List[Dict] = []
        for game in candidates:
            if not game.metrics:
                continue
            if not self._check_tags(game.metrics, required_tags, excluded_tags):
                continue
            if must_not and not self._check_must_not(game.metrics, must_not):
                continue
            if min_gem_potential > 0:
                gp = game.metrics.gem_potential
                if gp is None or gp < min_gem_potential:
                    continue

            cand_vec = build_weighted_vector(game.metrics, weight_map)

            # ===== v6 점수 (Core + X-Factor + Gem) =====
            # juntae 철학: 장르핵심 + 검색의도 + 독창성 + 발굴
            game_metrics_dict = {
                f: float(getattr(game.metrics, f, 5.0) or 5.0)
                for f in NUMERIC_METRIC_FIELDS
            }
            genre = (
                (game.genres or '').split(',')[0].strip()
                if game.genres else ''
            )

            v6_result = calculate_score_v6(
                game_metrics=game_metrics_dict,
                target_metrics=preferences,
                genre=genre,
                review_count=game.review_count or 0,
                positive_ratio=game.steam_positive_ratio or 0.5,
                gem_percentile=float(game.metrics.gem_percentile or 50),
            )
            display_score = v6_result['final_score']

            scored.append({
                "game": game,
                "metric": game.metrics,
                "score": display_score,
                "score_breakdown": {
                    "core_score": v6_result['breakdown']['core_score'],
                    "xfactor_score": v6_result['breakdown']['xfactor_score'],
                    "gem_score": v6_result['breakdown']['gem_score'],
                    "final_score": display_score,
                },
                "v6_identity": v6_result['identity'],
                "v6_strengths": v6_result['unique_strengths'],
                "weight_map": weight_map,
            })



        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:count]

    # ==================== 시맨틱 검색 / Semantic Search ====================

    async def analyze_query(self, query: str) -> Dict:
        """
        Analyze natural language query via GPT.
        Korean: GPT-4.1-mini로 자연어 쿼리 분석 — 영어 번역 + 지표 힌트.
        """
        client = self._get_openai()
        valid_metrics = NUMERIC_METRIC_FIELDS[:20]
        prompt = f"""You are a game recommendation assistant. Analyze this Korean game search query and return JSON.

Query: "{query}"

Return ONLY valid JSON:
{{
  "english_query": "translate to English, focus on game feel/atmosphere",
  "metric_hints": {{"metric_name": score_0_to_10}},
  "reasoning": "brief explanation"
}}

Valid metric names: {valid_metrics}

Examples:
- "혼자 조용히 즐기는 힐링 게임" → {{"english_query": "cozy relaxing solo healing game", "metric_hints": {{"cozy_factor": 9, "horror_factor": 0, "multiplayer_scale": 0}}}}
- "전략적이고 어려운 로그라이크" → {{"english_query": "strategic challenging roguelike", "metric_hints": {{"strategic_depth": 9, "learning_curve": 8, "replay_value": 9}}}}
- "림월드 같은 경영 생존 게임" → {{"english_query": "colony management survival sandbox game like RimWorld", "metric_hints": {{"management_complexity": 9, "freedom_level": 8, "strategic_depth": 8}}}}
"""
        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        try:
            return json.loads(response.choices[0].message.content)
        except Exception:
            return {"english_query": query, "metric_hints": {}}

    async def embed_query(self, query: str) -> np.ndarray:
        """
        Embed query text to 1536D vector.
        Korean: 쿼리 텍스트를 1536차원 임베딩으로 변환.
        """
        client = self._get_openai()
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=query,
        )
        return np.array(response.data[0].embedding, dtype=np.float32)

    async def semantic_search(
        self,
        db: AsyncSession,
        query: str,
        limit: int = 12,
        min_gem_potential: float = 0.0,
    ) -> List[Dict]:
        """
        Natural language semantic search v2 with intent + must_not.
        Korean: 의도 분류 + must_not + 앵커 점수 시스템이 통합된 시맨틱 검색 v2.

        흐름:
            1. 로컬 의도 분류 → must_not 추출
            2. GPT 쿼리 분석 (영어 번역 + 지표 힌트)
            3. 임베딩 생성 + pgvector 검색
            4. must_not 필터 + 지표 힌트 보정
            5. 표시 점수 변환 (0~99)
        """
        # 1. 로컬 의도 분류 + must_not
        _intent, group_name = self.intent_classifier.classify(query)
        must_not = self.intent_classifier.extract_must_not(query)
        weight_map = self.intent_classifier.get_weight_map(group_name)

        # 2. GPT 분석
        analysis = await self.analyze_query(query)
        english_query = analysis.get("english_query", query)
        metric_hints = analysis.get("metric_hints", {})

        # 3. 임베딩 + pgvector
        query_vec = await self.embed_query(english_query)
        query_vec_str = str(query_vec.tolist())

        sql = text("""
            SELECT
                g.id AS game_id,
                g.app_id,
                1 - (gm.embedding <=> :query_vec ::vector) AS emb_similarity,
                COALESCE(gm.gem_percentile, gm.gem_potential, 50) AS gem_score
            FROM game_metrics gm
            JOIN games g ON g.id = gm.game_id
            WHERE g.is_active = true
              AND g.is_analyzed = true
              AND gm.embedding IS NOT NULL
              AND (:min_gem = 0 OR gm.gem_potential >= :min_gem)
            ORDER BY gm.embedding <=> :query_vec ::vector
            LIMIT :limit
        """)

        result = await db.execute(sql, {
            "query_vec": query_vec_str,
            "min_gem": min_gem_potential,
            "limit": limit * 2,
        })
        rows = result.fetchall()
        if not rows:
            return []

        # 게임 정보 조회
        game_ids = [r.game_id for r in rows]
        stmt = (
            select(Game)
            .options(selectinload(Game.metrics))
            .where(Game.id.in_(game_ids))
        )
        games_result = await db.execute(stmt)
        games = games_result.scalars().all()
        games_map = {g.id: g for g in games}

        # 4. 필터 + 점수 계산
        final_scored: List[Dict] = []
        for row in rows:
            game = games_map.get(row.game_id)
            if not game or not game.metrics:
                continue
            if must_not and not self._check_must_not(game.metrics, must_not):
                continue

            emb_score = float(row.emb_similarity)

            # 지표 힌트 보정 / Metric hint adjustment
            hint_score = 0.0
            if metric_hints:
                match = 0.0
                for mname, tval in metric_hints.items():
                    if mname not in NUMERIC_METRIC_FIELDS:
                        continue
                    actual = getattr(game.metrics, mname, None)
                    if actual is None:
                        continue
                    match += max(0, 1.0 - abs(float(actual) - float(tval)) / 10.0)
                hint_score = match / len(metric_hints)

            raw_score = emb_score * 0.85 + hint_score * 0.15
            gem_bonus = self._calculate_gem_bonus(game, game.metrics)
            display_score = to_display_score(raw_score, gem_bonus)

            final_scored.append({
                "game": game,
                "metric": game.metrics,
                "score": display_score,
                "score_breakdown": {
                    "metric_score": round(hint_score * 100, 1),
                    "embedding_score": round(emb_score * 100, 1),
                    "gem_bonus": round(gem_bonus * 5, 1),
                    "final_score": display_score,
                },
                "weight_map": weight_map,
            })

        final_scored.sort(key=lambda x: x["score"], reverse=True)
        return final_scored[:limit]

    # ==================== 응답 포맷팅 / Response Formatting ====================

    def format_recommendations_by_game(
        self,
        results: List[Dict],
    ) -> List[RecommendedGame]:
        """
        Format game-based recommendation results.
        Korean: 게임 기반 추천 결과 포맷팅. score_breakdown 포함.
        """
        formatted = []
        for r in results:
            game = r["game"]
            metric = r["metric"]
            weight_map = r.get("weight_map", {})
            target_metric = r.get("target_metric")

            reasons = (
                self._generate_match_reasons_from_target(target_metric, metric, weight_map)
                if target_metric else []
            )
            formatted.append(RecommendedGame(
                app_id=game.app_id,
                name=game.name or "",
                genres=game.genres or "",
                header_image=game.header_image or "",
                one_line_summary=game.one_line_summary or "",
                marketing_hook=game.marketing_hook or "",
                similarity_score=r["score"],
                gem_potential=metric.gem_percentile or metric.gem_potential,
                match_reasons=reasons,
                key_metrics=self._get_key_metrics(metric),
            ))
        return formatted

    def format_recommendations_by_preference(
        self,
        results: List[Dict],
        preferences: Dict[str, float],
    ) -> List[RecommendedGame]:
        """
        Format preference-based recommendation results.
        Korean: 선호도 기반 추천 결과 포맷팅 — v6 분해 포함.

        v6 추가: score_breakdown / v6_identity / v6_strengths
            scored.append에서 넣은 v6 데이터를 응답에 전달.
        """
        formatted = []
        for r in results:
            game = r["game"]
            metric = r["metric"]
            weight_map = r.get("weight_map", {})
            formatted.append(RecommendedGame(
                app_id=game.app_id,
                name=game.name or "",
                genres=game.genres or "",
                header_image=game.header_image or "",
                one_line_summary=game.one_line_summary or "",
                marketing_hook=game.marketing_hook or "",
                similarity_score=r["score"],
                gem_potential=metric.gem_percentile or metric.gem_potential,
                # v6 분해 (UI 표시용)
                score_breakdown=r.get("score_breakdown", {}),
                v6_identity=r.get("v6_identity", ""),
                v6_strengths=r.get("v6_strengths", []),
                match_reasons=self._generate_match_reasons_from_preferences(
                    metric, preferences, weight_map
                ),
                key_metrics=self._get_key_metrics(metric),
            ))
        return formatted

    def format_semantic_results(
        self,
        results: List[Dict],
    ) -> List[RecommendedGame]:
        """
        Format semantic search results.
        Korean: 시맨틱 검색 결과 포맷팅.
        """
        formatted = []
        for r in results:
            game = r["game"]
            metric = r["metric"]
            formatted.append(RecommendedGame(
                app_id=game.app_id,
                name=game.name or "",
                genres=game.genres or "",
                header_image=game.header_image or "",
                one_line_summary=game.one_line_summary or "",
                marketing_hook=game.marketing_hook or "",
                similarity_score=r["score"],
                gem_potential=metric.gem_percentile or metric.gem_potential,
                match_reasons=[],
                key_metrics=self._get_key_metrics(metric),
            ))
        return formatted


# ==================== 싱글톤 / Singleton ====================

recommender = GameRecommender()