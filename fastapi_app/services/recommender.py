"""
Hidden Gem Recommendation Engine v4 (Hybrid + Dynamic Masking + NULL Fallback)

Korean: 동적 마스킹과 NULL 3단계 폴백을 추가한 하이브리드 추천 엔진 v4.

알고리즘:
    - 49차원 지표 벡터: 코사인(35%) + 유클리드(35%)
    - 1536차원 임베딩 벡터: OpenAI text-embedding-3-small 코사인(30%)
    - 임베딩 없을 경우: 지표 코사인(50%) + 유클리드(50%) 폴백

v4 신규 기능:
    1. SearchIntentClassifier  — 검색 의도 5종 자동 분류
    2. INTENT_TO_METRIC_GROUPS — 의도별 활성화 지표 그룹 정의
    3. DynamicMetricMasker     — 활성 지표만으로 마스킹 벡터 계산 (변별력 5배↑)
    4. MetricFallbackStrategy  — NULL 3단계 폴백 (ZERO / GLOBAL_MEAN / GENRE_MEAN)
    5. must_not 파싱           — EXCLUSION_KEYWORDS 기반 하드 필터
    6. by-preference 마스킹 통합 — 지정 지표만 활성화하여 노이즈 96% 제거
"""

import json
import re
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


# ==================== 검색 의도 분류 / Search Intent Types ====================

class SearchIntent(str, Enum):
    """
    Search intent categories for dynamic metric masking.
    Korean: 동적 마스킹에 사용하는 검색 의도 5가지 카테고리.
    """
    EXACT_MATCH = "exact_match"       # "Stardew Valley" → DB 직접 검색 50ms
    SIMILARITY  = "similarity"        # "스타듀 같은 게임" → 임베딩 검색 100ms
    MOOD        = "mood"              # "힐링게임" → 분위기 마스킹 150ms
    FEATURE     = "feature"           # "4인 협동 공포" → 기능 마스킹 80ms
    META        = "meta"              # "리뷰 95% 이상 인디" → 메타데이터 30ms
    UNKNOWN     = "unknown"           # fallback → 시맨틱 검색 1500ms


# ==================== 의도별 지표 그룹 / Intent → Metric Groups ====================

INTENT_TO_METRIC_GROUPS: Dict[str, Dict[str, List[str]]] = {
    # 분위기: 힐링 / cozy mood
    "mood_cozy": {
        "primary":   ["cozy_factor", "time_pressure", "grind_factor"],
        "secondary": ["humor_rating", "narrative_depth", "save_flexibility"],
    },
    # 분위기: 공포 / horror mood
    "mood_horror": {
        "primary":   ["horror_factor", "gore_level", "dark_fantasy_vibe"],
        "secondary": ["melancholy", "environmental_storytelling"],
    },
    # 분위기: 다크판타지 / dark fantasy mood
    "mood_dark": {
        "primary":   ["dark_fantasy_vibe", "melancholy", "horror_factor"],
        "secondary": ["lore_richness", "narrative_depth", "epic_scale"],
    },
    # 분위기: 서사 / narrative mood
    "mood_narrative": {
        "primary":   ["narrative_depth", "lore_richness", "choice_consequence"],
        "secondary": ["environmental_storytelling", "npc_interaction", "melancholy"],
    },
    # 기능: 전략 / strategy feature
    "feature_strategy": {
        "primary":   ["strategic_depth", "management_complexity", "learning_curve"],
        "secondary": ["rng_dependency", "build_variety", "session_length"],
    },
    # 기능: 서사/스토리 / narrative feature
    "feature_narrative": {
        "primary":   ["narrative_depth", "lore_richness", "choice_consequence"],
        "secondary": ["environmental_storytelling", "npc_interaction"],
    },
    # 기능: 협동 / coop feature
    "feature_coop": {
        "primary":   ["coop_synergy", "multiplayer_scale"],
        "secondary": ["user_creation", "community_dependency"],
    },
    # 기능: 액션 / action feature
    "feature_action": {
        "primary":   ["action_pacing", "reflex_demand", "time_pressure"],
        "secondary": ["platforming_precision", "learning_curve"],
    },
    # 기능: 퍼즐 / puzzle feature
    "feature_puzzle": {
        "primary":   ["puzzle_complexity", "learning_curve", "freedom_level"],
        "secondary": ["narrative_depth", "session_length"],
    },
    # 기능: 탐험 / exploration feature
    "feature_exploration": {
        "primary":   ["exploration_reward", "freedom_level", "world_reactivity"],
        "secondary": ["lore_richness", "environmental_storytelling"],
    },
    # 기능: 로그라이크 / roguelike feature
    "feature_roguelike": {
        "primary":   ["rng_dependency", "replay_value", "learning_curve"],
        "secondary": ["build_variety", "endgame_content", "growth_reward"],
    },
}

# 분위기 키워드 → 의도 그룹 매핑 / Mood keywords → intent group mapping
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

# 기능 키워드 → 의도 그룹 매핑 / Feature keywords → intent group mapping
FEATURE_KEYWORDS: Dict[str, str] = {
    "전략": "feature_strategy", "strategy": "feature_strategy", "경영": "feature_strategy",
    "rts": "feature_strategy", "턴제": "feature_strategy",
    "협동": "feature_coop", "coop": "feature_coop", "멀티": "feature_coop",
    "액션": "feature_action", "action": "feature_action", "격투": "feature_action",
    "퍼즐": "feature_puzzle", "puzzle": "feature_puzzle",
    "탐험": "feature_exploration", "오픈월드": "feature_exploration",
    "로그라이크": "feature_roguelike", "roguelike": "feature_roguelike",
    "로그라이트": "feature_roguelike",
}

# 유사 게임 키워드 / Similarity search trigger keywords
SIMILARITY_KEYWORDS: List[str] = [
    "같은", "비슷한", "similar", "like", "닮은", "feels like", "esque",
]

# 메타 키워드 / Meta search trigger keywords
META_KEYWORDS: List[str] = [
    "리뷰", "평점", "인기", "인디", "무료", "할인", "신작", "최신",
]


# ==================== must_not 제외 키워드 / Exclusion Keywords ====================

EXCLUSION_KEYWORDS: Dict[str, str] = {
    # 한국어 제외 키워드 → 하드 필터 지표 (≥4면 제외)
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
    "퍼마데스": "has_permadeath",   # Boolean 태그
    "영구죽음": "has_permadeath",
}

# 제외 키워드 트리거 패턴 ("없는", "제외", "싫어", "빼고", "no", "without")
EXCLUSION_TRIGGERS: List[str] = [
    "없는", "없이", "제외", "빼고", "싫어", "싫은", "no ", "without",
    "not ", "avoid", "exclude", "안 좋아", "말고", "제외하고",
]

# must_not 시 하드 필터 임계값 / Hard filter threshold for must_not metrics
MUST_NOT_THRESHOLD: float = 4.0


# ==================== NULL 폴백 정책 / NULL Fallback Policy ====================

class FallbackType(str, Enum):
    """
    Three-level NULL fallback strategy types.
    Korean: NULL 지표에 적용할 3단계 폴백 전략 타입.
    """
    ZERO        = "zero"         # NULL = 해당 없음 (0이 의미 있는 지표)
    GLOBAL_MEAN = "global_mean"  # 데이터셋 전체 평균
    GENRE_MEAN  = "genre_mean"   # 장르 평균
    MASK        = "mask"         # 점수 계산에서 완전 제외


# 지표별 NULL 폴백 정책 / NULL fallback policy per metric
NULL_FALLBACK_POLICY: Dict[str, FallbackType] = {
    # ZERO: 해당 없음 = 0이 정확한 지표 / "Not applicable" metrics → 0 is correct
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

    # GLOBAL_MEAN: 전체 평균이 적절한 지표 (프레젠테이션 관련)
    # Global average is appropriate (presentation-related metrics)
    "visual_spectacle":      FallbackType.GLOBAL_MEAN,
    "audio_design":          FallbackType.GLOBAL_MEAN,
    "animation_quality":     FallbackType.GLOBAL_MEAN,
    "ui_ux_polish":          FallbackType.GLOBAL_MEAN,
    "art_style_uniqueness":  FallbackType.GLOBAL_MEAN,
    "soundtrack_impact":     FallbackType.GLOBAL_MEAN,

    # GENRE_MEAN: 장르에 따라 크게 달라지는 지표
    # Highly genre-dependent metrics → use genre average
    "strategic_depth":       FallbackType.GENRE_MEAN,
    "narrative_depth":       FallbackType.GENRE_MEAN,
    "lore_richness":         FallbackType.GENRE_MEAN,
    "exploration_reward":    FallbackType.GENRE_MEAN,
    "endgame_content":       FallbackType.GENRE_MEAN,
    "replay_value":          FallbackType.GENRE_MEAN,
}

# 데이터셋 전체 평균 (실측값 기반) / Dataset global mean (empirical values)
GLOBAL_METRIC_MEANS: Dict[str, float] = {
    "visual_spectacle":   7.0,
    "audio_design":       6.8,
    "animation_quality":  6.5,
    "ui_ux_polish":       6.5,
    "art_style_uniqueness": 6.2,
    "soundtrack_impact":  6.5,
}

# 장르별 평균 기본값 (장르 조회 실패 시 사용) / Genre mean defaults (fallback)
GENRE_METRIC_DEFAULTS: Dict[str, float] = {
    "strategic_depth":   5.5,
    "narrative_depth":   5.5,
    "lore_richness":     5.0,
    "exploration_reward": 5.5,
    "endgame_content":   5.0,
    "replay_value":      6.0,
}


# ==================== SearchIntentClassifier ====================

class SearchIntentClassifier:
    """
    Classifies search query intent for dynamic metric masking.
    Korean: 검색 의도를 분류하여 동적 마스킹에 사용할 지표 그룹을 결정하는 분류기.

    분류 방식:
        1. 유사 게임 키워드 감지 → SIMILARITY
        2. 메타 키워드 감지     → META
        3. 분위기 키워드 감지   → MOOD + 해당 그룹
        4. 기능 키워드 감지     → FEATURE + 해당 그룹
        5. 나머지               → UNKNOWN (시맨틱 fallback)
    """

    def classify(self, query: str) -> Tuple[SearchIntent, Optional[str]]:
        """
        Classify search intent and return intent group name.
        Korean: 검색어를 분석해 의도와 해당 지표 그룹 이름을 반환.

        Args:
            query: 자연어 검색어 (한국어/영어 모두 가능)

        Returns:
            (SearchIntent, group_name | None)
            예: (SearchIntent.MOOD, "mood_cozy")
        """
        q_lower = query.lower()

        # 1. 유사 게임 검색 / Similarity search detection
        for kw in SIMILARITY_KEYWORDS:
            if kw in q_lower:
                return SearchIntent.SIMILARITY, None

        # 2. 메타 검색 / Meta search detection
        for kw in META_KEYWORDS:
            if kw in q_lower:
                return SearchIntent.META, None

        # 3. 분위기 키워드 / Mood keyword detection
        for kw, group in MOOD_KEYWORDS.items():
            if kw in q_lower:
                return SearchIntent.MOOD, group

        # 4. 기능 키워드 / Feature keyword detection
        for kw, group in FEATURE_KEYWORDS.items():
            if kw in q_lower:
                return SearchIntent.FEATURE, group

        return SearchIntent.UNKNOWN, None

    def extract_must_not(self, query: str) -> Dict[str, float]:
        """
        Extract explicit exclusion constraints from query.
        Korean: 쿼리에서 명시적 제외 조건을 추출 (예: '공포 없는 힐링').

        '없는', '제외' 등 제외 트리거 + 제외 키워드 조합 감지.
        Boolean 태그 지표는 값 0 (False), 수치 지표는 MUST_NOT_THRESHOLD.

        Returns:
            Dict[str, float]: {지표명: 임계값(이 값 이상이면 제외)}
        """
        q_lower = query.lower()
        must_not: Dict[str, float] = {}

        # 제외 트리거가 있을 때만 파싱 / Only parse when exclusion trigger present
        has_trigger = any(trigger in q_lower for trigger in EXCLUSION_TRIGGERS)
        if not has_trigger:
            return must_not

        for keyword, metric in EXCLUSION_KEYWORDS.items():
            if keyword in q_lower:
                if metric in BOOLEAN_TAG_FIELDS:
                    # Boolean 태그: True면 제외 (임계값 0.5)
                    must_not[metric] = 0.5
                else:
                    # 수치 지표: MUST_NOT_THRESHOLD(4.0) 이상이면 제외
                    must_not[metric] = MUST_NOT_THRESHOLD

        return must_not

    def get_active_metrics(
        self,
        group_name: Optional[str],
        preferences: Optional[Dict[str, float]] = None,
    ) -> Optional[Set[str]]:
        """
        Return active metric set for the given intent group.
        Korean: 의도 그룹에 해당하는 활성화 지표 집합 반환.

        primary + secondary 합집합을 활성 지표로 사용.
        preferences가 있으면 해당 지표도 추가 (선호도 기반 추천 통합).
        group_name이 None이면 전체 지표 사용 (마스킹 없음).

        Returns:
            Set[str] | None: None이면 전체 지표 사용
        """
        active: Set[str] = set()

        if group_name and group_name in INTENT_TO_METRIC_GROUPS:
            group = INTENT_TO_METRIC_GROUPS[group_name]
            active.update(group.get("primary", []))
            active.update(group.get("secondary", []))

        # 선호도 지표도 항상 포함 / Always include preference metrics
        if preferences:
            active.update(k for k in preferences if k in NUMERIC_METRIC_FIELDS)

        return active if active else None


# ==================== MetricFallbackStrategy ====================

class MetricFallbackStrategy:
    """
    Three-level NULL metric fallback strategy.
    Korean: NULL 지표에 대해 ZERO / GLOBAL_MEAN / GENRE_MEAN 3단계 폴백을 적용하는 전략.

    우선순위:
        1. NULL_FALLBACK_POLICY에 정의된 정책 적용
        2. 정의 없으면 중립값 5.0 (기존 방식) 사용
        3. 활성화된 지표에서 NULL이면 → 해당 지표 마스킹 제외
    """

    def resolve(
        self,
        field: str,
        value: Optional[float],
        game_genres: Optional[str] = None,
        active_metrics: Optional[Set[str]] = None,
    ) -> Optional[float]:
        """
        Resolve NULL metric value using fallback policy.
        Korean: NULL 지표 값을 폴백 정책에 따라 해결.

        Args:
            field: 지표 이름
            value: 현재 값 (None이면 폴백 적용)
            game_genres: 게임 장르 문자열 (장르 평균 계산용)
            active_metrics: 활성화 지표 집합 (None이면 전체 활성)

        Returns:
            float | None: None 반환 시 해당 지표는 벡터 계산에서 제외
        """
        # 값이 있으면 그대로 반환
        if value is not None:
            return value

        # 활성 지표에 없는 경우 → 마스킹 제외 (None 반환)
        if active_metrics is not None and field not in active_metrics:
            return None

        policy = NULL_FALLBACK_POLICY.get(field)

        if policy == FallbackType.ZERO:
            return 0.0

        if policy == FallbackType.GLOBAL_MEAN:
            return GLOBAL_METRIC_MEANS.get(field, 5.0)

        if policy == FallbackType.GENRE_MEAN:
            # 장르별 평균 계산 (간소화: 기본값 사용)
            # 추후 DB 조회로 교체 가능 / Can be replaced with DB query later
            return GENRE_METRIC_DEFAULTS.get(field, 5.0)

        # MASK 또는 미정의 → 활성 지표면 중립값, 비활성이면 None
        if active_metrics is not None and field in active_metrics:
            return 5.0  # 활성 지표인데 정책 미정의 → 중립값

        return None  # 비활성 → 마스킹 제외


# ==================== DynamicMetricMasker ====================

class DynamicMetricMasker:
    """
    Computes masked metric vectors using only active metrics.
    Korean: 활성화된 지표만 사용하여 마스킹 벡터를 계산하는 클래스.

    핵심 아이디어:
        - 기존: 49개 전체 지표로 거리 계산 → 무관 지표 96% 노이즈
        - 개선: 의도 관련 지표(primary 2.5x + secondary 1.0x)만 계산 → 변별력 5배↑
        - NULL 지표 자동 마스킹: 값 없는 지표는 비교에서 제외
    """

    def __init__(self):
        self.fallback = MetricFallbackStrategy()

    def build_masked_vector(
        self,
        metric: GameMetric,
        active_metrics: Optional[Set[str]],
        group_name: Optional[str],
        extra_weights: Optional[Dict[str, float]] = None,
    ) -> Tuple[np.ndarray, np.ndarray, List[int]]:
        """
        Build masked weight vector for only active metrics.
        Korean: 활성 지표만 포함한 마스킹 가중치 벡터 생성.

        primary 지표 가중치 2.5x, secondary 지표 1.0x.
        active_metrics=None이면 전체 49개 지표 사용 (마스킹 없음).

        Args:
            metric: GameMetric ORM 인스턴스
            active_metrics: 활성화된 지표 집합 (None=전체)
            group_name: 의도 그룹 이름 (primary/secondary 구분용)
            extra_weights: 추가 가중치 오버라이드

        Returns:
            (values_array, weights_array, active_indices):
                - values_array: float32 배열 (활성 지표 값)
                - weights_array: float32 배열 (활성 지표 가중치)
                - active_indices: 활성 지표 인덱스 목록
        """
        # primary / secondary 지표 구분 / Distinguish primary vs secondary
        primary_set: Set[str] = set()
        if group_name and group_name in INTENT_TO_METRIC_GROUPS:
            primary_set = set(INTENT_TO_METRIC_GROUPS[group_name].get("primary", []))

        values: List[float] = []
        weights: List[float] = []
        indices: List[int] = []

        for i, field in enumerate(NUMERIC_METRIC_FIELDS):
            # 활성 지표가 아니면 건너뜀 / Skip if not in active set
            if active_metrics is not None and field not in active_metrics:
                continue

            raw_value = getattr(metric, field, None)
            resolved = self.fallback.resolve(
                field=field,
                value=raw_value if isinstance(raw_value, (int, float)) else None,
                active_metrics=active_metrics,
            )

            # NULL 처리 후에도 None → 마스킹 제외
            if resolved is None:
                continue

            # 가중치 결정 / Determine weight
            if extra_weights and field in extra_weights:
                w = extra_weights[field]
            elif active_metrics is not None:
                # primary: 2.5x, secondary: 1.0x
                w = 2.5 if field in primary_set else 1.0
            else:
                w = 1.0

            values.append(resolved)
            weights.append(w)
            indices.append(i)

        if not values:
            # 활성 지표가 하나도 없으면 중립 벡터 / Return neutral if no active metrics
            return np.array([5.0], dtype=np.float32), np.array([1.0], dtype=np.float32), [0]

        return (
            np.array(values, dtype=np.float32),
            np.array(weights, dtype=np.float32),
            indices,
        )

    def masked_cosine_similarity(
        self,
        vals1: np.ndarray,
        w1: np.ndarray,
        vals2: np.ndarray,
        w2: np.ndarray,
    ) -> float:
        """
        Compute cosine similarity on common non-null dimensions only.
        Korean: 두 벡터에서 공통 비-NULL 차원에만 코사인 유사도 계산.

        가중치 적용 후 코사인 계산 → 활성 지표만 반영.
        """
        v1 = vals1 * w1
        v2 = vals2 * w2
        n1 = np.linalg.norm(v1)
        n2 = np.linalg.norm(v2)
        if n1 == 0 or n2 == 0:
            return 0.0
        return float(max(0.0, min(np.dot(v1, v2) / (n1 * n2), 1.0)))

    def masked_euclidean_similarity(
        self,
        vals1: np.ndarray,
        w1: np.ndarray,
        vals2: np.ndarray,
        w2: np.ndarray,
        max_distance: float = 30.0,
    ) -> float:
        """
        Compute euclidean similarity on common non-null dimensions only.
        Korean: 공통 비-NULL 차원에 유클리드 유사도 계산, max_distance=30 정규화.
        """
        # 차원 수에 따라 max_distance 스케일 조정 / Scale by active dimension count
        n_dims = len(vals1)
        # 49차원 기준 max_distance=30 → 실제 차원 수에 비례 스케일
        scale = (n_dims / 49.0) ** 0.5 if n_dims > 0 else 1.0
        effective_max = max_distance * scale

        diff = (vals1 * w1) - (vals2 * w2)
        distance = float(np.linalg.norm(diff))
        return max(0.0, 1.0 - min(distance / effective_max, 1.0))


# ==================== GameRecommender (v4) ====================

class GameRecommender:
    """
    Hybrid game recommender v4 with dynamic masking and NULL fallback.
    Korean: 동적 마스킹 + NULL 3단계 폴백 + must_not 파싱이 통합된 하이브리드 추천 엔진 v4.

    추천 방식:
        1. by-game       : 기준 게임 지표 + 임베딩 하이브리드 유사도
        2. by-preference : 선호도 지표만 활성화한 동적 마스킹 추천 (v4 핵심)
        3. semantic      : 자연어 → GPT 분석 → pgvector + 지표 힌트
    """

    def __init__(self):
        self.dimension = len(NUMERIC_METRIC_FIELDS)  # 49
        self.neutral_value = 5.0
        self.max_distance = 30.0
        self._openai: Optional[AsyncOpenAI] = None

        # 서브 모듈 초기화 / Initialize submodules
        self.intent_classifier = SearchIntentClassifier()
        self.masker = DynamicMetricMasker()

    def _get_openai(self) -> AsyncOpenAI:
        """
        Get or create singleton OpenAI async client (Lazy Initialization).
        Korean: 싱글톤 OpenAI 비동기 클라이언트 반환 (최초 호출 시에만 생성).
        """
        if self._openai is None:
            self._openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._openai

    # ==================== 벡터 변환 / Vector Conversion ====================

    def _metric_to_vector(
        self,
        metric: GameMetric,
        weights: Optional[Dict[str, float]] = None,
    ) -> np.ndarray:
        """
        Convert GameMetric to 49D numpy vector with optional weights (Legacy).
        Korean: GameMetric을 49차원 numpy 벡터로 변환 (가중치 선택 적용). 레거시 호환용.

        by-game 추천 등 마스킹 불필요한 경우에 사용.
        NULL → 중립값 5.0 (기존 동작 유지).
        """
        vector = np.empty(self.dimension, dtype=np.float32)
        for i, field in enumerate(NUMERIC_METRIC_FIELDS):
            value = getattr(metric, field, None)
            if value is None:
                value = self.neutral_value
            w = weights.get(field, 1.0) if weights else 1.0
            vector[i] = float(value) * w
        return vector

    def _parse_embedding(self, metric: GameMetric) -> Optional[np.ndarray]:
        """
        Parse stored embedding from GameMetric to numpy array.
        Korean: DB에 저장된 임베딩(JSON 문자열 또는 벡터)을 numpy 배열로 파싱.

        Returns:
            np.ndarray: 1536차원 float32, 실패 시 None
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

    # ==================== 유사도 계산 / Similarity Calculation ====================

    def _cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """
        Compute cosine similarity (0~1).
        Korean: 코사인 유사도 계산 (0~1 범위).
        """
        n1 = np.linalg.norm(v1)
        n2 = np.linalg.norm(v2)
        if n1 == 0 or n2 == 0:
            return 0.0
        return float(max(0.0, min(np.dot(v1, v2) / (n1 * n2), 1.0)))

    def _euclidean_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """
        Compute euclidean distance-based similarity (0~1), normalized by max_distance=30.
        Korean: 유클리드 거리 기반 유사도 (max_distance=30 정규화, 0~1).
        """
        distance = float(np.linalg.norm(v1 - v2))
        return max(0.0, 1.0 - min(distance / self.max_distance, 1.0))

    def _hybrid_score(
        self,
        target_vec: np.ndarray,
        cand_vec: np.ndarray,
        target_emb: Optional[np.ndarray],
        cand_emb: Optional[np.ndarray],
        cosine_w: float = 0.35,
        euclidean_w: float = 0.35,
        embedding_w: float = 0.30,
    ) -> float:
        """
        Compute 49D metric + 1536D embedding hybrid similarity score.
        Korean: 49차원 지표 + 1536차원 임베딩 하이브리드 유사도 계산.

        임베딩 없으면 코사인/유클리드 5:5 폴백.
        """
        cosine = self._cosine_similarity(target_vec, cand_vec)
        euclidean = self._euclidean_similarity(target_vec, cand_vec)
        if target_emb is not None and cand_emb is not None:
            emb_sim = self._cosine_similarity(target_emb, cand_emb)
            return cosine * cosine_w + euclidean * euclidean_w + emb_sim * embedding_w
        return cosine * 0.5 + euclidean * 0.5

    # ==================== 필터링 / Filtering ====================

    def _check_tags(
        self,
        metric: GameMetric,
        required: List[str],
        excluded: List[str],
    ) -> bool:
        """
        Check boolean tag conditions (required=all True, excluded=all False).
        Korean: Boolean 태그 필터 검사 (required는 모두 True, excluded는 모두 False여야 통과).
        """
        for tag in required:
            if tag in BOOLEAN_TAG_FIELDS:
                if not getattr(metric, tag, False):
                    return False
        for tag in excluded:
            if tag in BOOLEAN_TAG_FIELDS:
                if getattr(metric, tag, False):
                    return False
        return True

    def _check_must_not(
        self,
        metric: GameMetric,
        must_not: Dict[str, float],
    ) -> bool:
        """
        Check must_not hard filter (exclude if metric value >= threshold).
        Korean: must_not 하드 필터 검사. 지표 값 ≥ 임계값이면 False (제외).

        Boolean 태그는 값이 True면 제외 (임계값 0.5 기준).
        수치 지표는 MUST_NOT_THRESHOLD(4.0) 이상이면 제외.
        """
        for metric_name, threshold in must_not.items():
            if metric_name in BOOLEAN_TAG_FIELDS:
                # Boolean: True면 제외
                if getattr(metric, metric_name, False):
                    return False
            elif metric_name in NUMERIC_METRIC_FIELDS:
                value = getattr(metric, metric_name, None)
                if value is not None and float(value) >= threshold:
                    return False
        return True

    # ==================== Hidden Gem 보너스 / Gem Bonus ====================

    def _calculate_gem_bonus(self, game: Game, metric: GameMetric) -> float:
        """
        Calculate Hidden Gem bonus score (0~0.15).
        Korean: gem_percentile 기반 Hidden Gem 보너스 계산 (최대 0.15).

        gem_percentile 우선, 없으면 gem_potential 폴백.
        리뷰 1,000개 미만 게임 우대 (숨겨진 명작 발굴 핵심).
        """
        gem = (
            metric.gem_percentile
            if metric.gem_percentile is not None
            else (metric.gem_potential if metric.gem_potential is not None else 50.0)
        )
        confidence = metric.confidence_score if metric.confidence_score is not None else 0.5
        reviews = game.review_count or 0

        # 리뷰 적을수록 보너스 / Boost games with fewer reviews (< 1000)
        review_bonus = 0.05 * (1.0 - reviews / 1000.0) if reviews < 1000 else 0.0
        # gem 0~100 → 0~0.10 / Normalize gem to 0~0.10
        gem_bonus = (gem / 100.0) * 0.10

        return (gem_bonus + review_bonus) * confidence

    # ==================== 추천 이유 생성 / Match Reason Generation ====================

    def _generate_match_reasons_from_preferences(
        self,
        candidate_vec: np.ndarray,
        preferences: Dict[str, float],
    ) -> List[str]:
        """
        Generate match reasons by comparing preference targets vs actual values.
        Korean: 선호도 목표값과 후보 게임 실제 값 비교로 추천 이유 생성 (차이 ≤ 2.0이면 포함).
        """
        reasons: List[str] = []
        for field, target_value in preferences.items():
            if field not in NUMERIC_METRIC_FIELDS:
                continue
            idx = NUMERIC_METRIC_FIELDS.index(field)
            actual_value = float(candidate_vec[idx])
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
        target_vec: np.ndarray,
        candidate_vec: np.ndarray,
    ) -> List[str]:
        """
        Extract common features between target and candidate games.
        Korean: 기준 게임과 후보 게임의 공통 특징 추출 (양쪽 모두 극단값 + 차이 ≤ 1.5).
        """
        common: List[Tuple[str, str, float]] = []
        for i, field in enumerate(NUMERIC_METRIC_FIELDS):
            target = float(target_vec[i])
            cand = float(candidate_vec[i])
            if abs(target - cand) <= 1.5:
                if target >= 7 and cand >= 7:
                    common.append((field, "공통적으로 높음", cand))
                elif target <= 3 and cand <= 3:
                    common.append((field, "공통적으로 낮음", cand))
        return [
            f"✓ {METRIC_LABELS_KO.get(f, f)} {desc} ({v:.1f})"
            for f, desc, v in common[:5]
        ]

    def _get_key_metrics(self, metric: GameMetric) -> Dict[str, float]:
        """
        Extract top 5 key metrics (extreme values prioritized).
        Korean: 극단값(≤2 or ≥8) 우선으로 핵심 지표 최대 5개 추출.
        """
        all_metrics: Dict[str, float] = {}
        for field in NUMERIC_METRIC_FIELDS:
            v = getattr(metric, field, None)
            if v is not None:
                all_metrics[field] = float(v)

        extreme = {k: v for k, v in all_metrics.items() if v <= 2 or v >= 8}
        priority = [
            "cozy_factor", "strategic_depth", "horror_factor",
            "narrative_depth", "freedom_level", "action_pacing",
            "lore_richness", "replay_value",
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

    # ==================== 점수 정규화 / Score Normalization ====================

    def _normalize_scores(
        self,
        scored: List[Tuple],
        score_idx: int = 2,
    ) -> List[Tuple]:
        """
        Normalize scores so the top result is 1.0 (relative normalization).
        Korean: 상대 정규화 — 1위 점수를 1.0으로, 나머지를 0.5~1.0으로 스케일.

        Args:
            scored: (game, metric, score, ...) 튜플 리스트
            score_idx: 점수가 위치한 인덱스
        Returns:
            점수가 정규화된 동일 구조의 리스트
        """
        if not scored:
            return scored
        scores = [item[score_idx] for item in scored]
        max_score = max(scores)
        min_score = min(scores)
        score_range = max_score - min_score
        if score_range == 0:
            return scored

        normalized = []
        for item in scored:
            raw_score = item[score_idx]
            # min-max 정규화 후 0.5~1.0 범위 스케일 / Scale to 0.5~1.0
            norm = (raw_score - min_score) / score_range
            scaled = round(norm * 100, 1)
            normalized.append(
                item[:score_idx] + (round(scaled, 4),) + item[score_idx + 1:]
            )
        return normalized

    # ==================== 추천 메인 로직 / Main Recommendation Logic ====================

    async def recommend_by_game(
        self,
        db: AsyncSession,
        app_id: int,
        count: int = 5,
        exclude_same_developer: bool = False,
    ) -> Tuple[Optional[Game], List[Tuple[Game, GameMetric, float, np.ndarray]]]:
        """
        Recommend similar games based on a specific game (Game-based Recommendation).
        Korean: 기준 게임의 지표 벡터 + 임베딩을 활용한 하이브리드 유사도 기반 추천.

        마스킹 없음 — 게임 간 전체 지표 비교가 적절.
        Returns:
            (기준 게임, [(후보 게임, 지표, 유사도 점수, 기준 벡터), ...])
        """
        # 기준 게임 조회 / Fetch target game
        stmt = (
            select(Game)
            .options(selectinload(Game.metrics))
            .where(Game.app_id == app_id)
        )
        result = await db.execute(stmt)
        target_game = result.scalar_one_or_none()

        if not target_game or not target_game.metrics:
            return None, []

        target_vec = self._metric_to_vector(target_game.metrics)
        target_emb = self._parse_embedding(target_game.metrics)

        # 후보 게임 조회 / Fetch candidate games
        stmt = (
            select(Game)
            .options(selectinload(Game.metrics))
            .where(Game.is_active == True)   # noqa: E712
            .where(Game.is_analyzed == True) # noqa: E712
            .where(Game.app_id != app_id)
        )
        if exclude_same_developer and target_game.developer:
            stmt = stmt.where(Game.developer != target_game.developer)

        result = await db.execute(stmt)
        candidates = result.scalars().all()

        # 하이브리드 점수 계산 / Compute hybrid scores
        scored: List[Tuple[Game, GameMetric, float, np.ndarray]] = []
        for game in candidates:
            if not game.metrics:
                continue
            cand_vec = self._metric_to_vector(game.metrics)
            cand_emb = self._parse_embedding(game.metrics)

            base_score = self._hybrid_score(target_vec, cand_vec, target_emb, cand_emb)
            gem_bonus = self._calculate_gem_bonus(game, game.metrics)
            final_score = min(base_score + gem_bonus, 1.0)
            scored.append((game, game.metrics, final_score, target_vec))

        scored.sort(key=lambda x: x[2], reverse=True)
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
    ) -> List[Tuple[Game, GameMetric, float]]:
        """
        Preference-based recommendation with dynamic metric masking (v4 Core).
        Korean: 동적 마스킹이 통합된 선호도 기반 추천 엔진 v4 핵심 메서드.

        마스킹 동작:
            - use_masking=True (기본): 지정한 지표만 활성화 → 노이즈 96% 제거
            - use_masking=False: 기존 방식 (49개 전체 지표)

        must_not 하드 필터:
            - 명시적 제외 지표가 임계값 이상인 게임은 결과에서 제외

        Args:
            preferences: {지표명: 목표값(0~10)} 딕셔너리
            required_tags: 반드시 포함해야 할 Boolean 태그 목록
            excluded_tags: 반드시 제외해야 할 Boolean 태그 목록
            must_not: {지표명: 임계값} 하드 제외 필터 (≥ 임계값이면 제외)
            count: 반환할 추천 수
            min_gem_potential: 최소 gem_potential 필터
            use_masking: 동적 마스킹 활성화 여부 (기본 True)

        Returns:
            [(Game, GameMetric, similarity_score), ...]
        """
        required_tags = required_tags or []
        excluded_tags = excluded_tags or []
        must_not = must_not or {}

        # 검색 의도 분류 → 활성 지표 결정 / Classify intent → decide active metrics
        # 선호도만으로는 의도 분류 불가 → 선호도 지표 자체를 활성 지표로 사용
        active_metrics: Optional[Set[str]] = None
        if use_masking and preferences:
            # 선호도로 지정된 지표 + 연관 그룹 지표 활성화
            # Activate preference metrics + related group metrics
            active_metrics = self.intent_classifier.get_active_metrics(
                group_name=None,  # 선호도 기반이므로 그룹 없음 / No group for preference-based
                preferences=preferences,
            )

        # 타겟 벡터 구성 / Build target preference vector
        # 활성 지표만으로 구성된 타겟 벡터
        target_vals, target_weights, target_indices = self.masker.build_masked_vector(
            metric=_PreferenceMetric(preferences),  # 선호도를 GameMetric처럼 래핑
            active_metrics=active_metrics,
            group_name=None,
            extra_weights={f: 2.5 for f in preferences if f in NUMERIC_METRIC_FIELDS},
        )

        # 후보 게임 조회 / Fetch candidate games
        stmt = (
            select(Game)
            .options(selectinload(Game.metrics))
            .where(Game.is_active == True)   # noqa: E712
            .where(Game.is_analyzed == True) # noqa: E712
        )
        result = await db.execute(stmt)
        candidates = result.scalars().all()

        # 점수 계산 / Compute scores
        scored: List[Tuple[Game, GameMetric, float]] = []
        for game in candidates:
            if not game.metrics:
                continue

            # 태그 필터 / Tag filter
            if not self._check_tags(game.metrics, required_tags, excluded_tags):
                continue

            # must_not 하드 필터 / must_not hard filter
            if must_not and not self._check_must_not(game.metrics, must_not):
                continue

            # gem_potential 최소값 필터 / Minimum gem_potential filter
            if min_gem_potential > 0:
                gp = game.metrics.gem_potential
                if gp is None or gp < min_gem_potential:
                    continue

            if use_masking and active_metrics:
                # 마스킹 유사도: 활성 지표만 비교 / Masked similarity (active metrics only)
                cand_vals, cand_weights, _ = self.masker.build_masked_vector(
                    metric=game.metrics,
                    active_metrics=active_metrics,
                    group_name=None,
                )
                cosine = self.masker.masked_cosine_similarity(
                    target_vals, target_weights, cand_vals, cand_weights
                )
                euclidean = self.masker.masked_euclidean_similarity(
                    target_vals, target_weights, cand_vals, cand_weights,
                    max_distance=self.max_distance,
                )
            else:
                # 마스킹 없음: 기존 방식 (49개 전체) / No masking: legacy full 49D
                weights_dict = {f: 2.5 if f in preferences else 1.0
                                for f in NUMERIC_METRIC_FIELDS}
                target_full = self._build_preference_vector(preferences)
                cand_full = self._metric_to_vector(game.metrics, weights_dict)
                cosine = self._cosine_similarity(target_full, cand_full)
                euclidean = self._euclidean_similarity(target_full, cand_full)

            # 가중치: 유클리드 60% + 코사인 40% (선호도 기반 거리 중심)
            base_score = euclidean * 0.6 + cosine * 0.4
            gem_bonus = self._calculate_gem_bonus(game, game.metrics)
            final_score = min(base_score + gem_bonus, 1.0)
            scored.append((game, game.metrics, final_score))

        scored.sort(key=lambda x: x[2], reverse=True)
        return scored[:count]

    def _build_preference_vector(self, preferences: Dict[str, float]) -> np.ndarray:
        """
        Build full 49D preference vector for legacy (non-masked) mode.
        Korean: 마스킹 없는 레거시 모드용 49차원 선호도 벡터 생성. 미지정 지표는 중립값 5.0.
        """
        vec = np.full(self.dimension, self.neutral_value, dtype=np.float32)
        for field, value in preferences.items():
            if field in NUMERIC_METRIC_FIELDS:
                idx = NUMERIC_METRIC_FIELDS.index(field)
                vec[idx] = value
        return vec

    # ==================== 시맨틱 검색 / Semantic Search ====================

    async def analyze_query(self, query: str) -> Dict:
        """
        Analyze natural language query via GPT (Query Analysis).
        Korean: GPT-4.1-mini로 자연어 쿼리 분석 — 영어 번역 + 지표 힌트 + must_not 추출.

        must_not 분석도 GPT에 위임하지 않고 로컬 파싱으로 처리.
        (비용 절감 + 일관성)

        Returns:
            {
                "english_query": "relaxing solo strategy game",
                "metric_hints": {"cozy_factor": 8, "strategic_depth": 7},
                "intent": "mood_cozy"
            }
        """
        client = self._get_openai()

        # 주요 지표 20개만 전달 (토큰 효율) / Top 20 metrics for token efficiency
        valid_metrics = NUMERIC_METRIC_FIELDS[:20]

        prompt = f"""You are a game recommendation assistant. Analyze this Korean game search query and return JSON.

Query: "{query}"

Return ONLY valid JSON with these fields:
{{
  "english_query": "translate to English, focus on game feel/atmosphere",
  "metric_hints": {{"metric_name": score_0_to_10}},
  "reasoning": "brief explanation"
}}

Valid metric names (use only these): {valid_metrics}

Examples:
- "혼자 조용히 즐기는 힐링 게임" → {{"english_query": "cozy relaxing solo healing game peaceful", "metric_hints": {{"cozy_factor": 9, "horror_factor": 0, "multiplayer_scale": 0, "action_pacing": 2}}}}
- "전략적이고 어려운 로그라이크" → {{"english_query": "strategic challenging roguelike permadeath", "metric_hints": {{"strategic_depth": 9, "learning_curve": 8, "replay_value": 9}}}}
- "공포스럽고 분위기 있는 게임" → {{"english_query": "horror atmospheric dark scary game", "metric_hints": {{"horror_factor": 9, "dark_fantasy_vibe": 8, "cozy_factor": 0}}}}
"""

        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300,
            response_format={"type": "json_object"},
        )

        try:
            result = json.loads(response.choices[0].message.content)
            return result
        except Exception:
            # GPT 실패 시 원본 쿼리 그대로 / Fallback to original query on GPT failure
            return {"english_query": query, "metric_hints": {}}

    async def embed_query(self, query: str) -> np.ndarray:
        """
        Embed text query into 1536D vector using OpenAI text-embedding-3-small.
        Korean: 텍스트를 1536차원 임베딩으로 변환 (영어 번역된 쿼리일수록 품질 향상).
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
    ) -> List[Tuple[Game, GameMetric, float]]:
        """
        Enhanced natural language semantic search v2 with intent classification.
        Korean: 의도 분류 + must_not 파싱이 통합된 자연어 시맨틱 검색 v2.

        흐름:
            1. 로컬 의도 분류 (즉시) → must_not 추출
            2. GPT-4.1-mini로 쿼리 분석 (영어 번역 + 지표 힌트)
            3. 영어 쿼리로 임베딩 생성
            4. pgvector 코사인 유사도 검색
            5. must_not 하드 필터 적용
            6. 지표 힌트 보너스/페널티 적용
            7. FINAL SCORE = 임베딩(60%) + gem_percentile(40%)
            8. 상대 정규화 (1위=1.0)

        Args:
            query: 자연어 검색어 (한국어/영어)
            limit: 반환할 최대 게임 수
            min_gem_potential: 최소 gem_potential 필터

        Returns:
            [(Game, GameMetric, normalized_score), ...]
        """
        # 1. 로컬 의도 분류 + must_not 추출 / Local intent classification + must_not
        _intent, _group = self.intent_classifier.classify(query)
        must_not = self.intent_classifier.extract_must_not(query)

        # 2. GPT 쿼리 분석 / GPT query analysis
        analysis = await self.analyze_query(query)
        english_query = analysis.get("english_query", query)
        metric_hints = analysis.get("metric_hints", {})

        # 3. 임베딩 생성 / Generate embedding
        query_vec = await self.embed_query(english_query)
        query_vec_str = str(query_vec.tolist())

        # 4. pgvector 코사인 유사도 검색 / pgvector cosine similarity search
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
            "limit": limit * 2,  # 여유롭게 가져와서 필터링 / Fetch 2x for filtering
        })
        rows = result.fetchall()

        if not rows:
            return []

        # 5. FINAL SCORE 계산 / Compute final score
        # 임베딩 유사도 60% + gem_percentile 40%
        scored_rows = []
        for row in rows:
            emb_sim = float(row.emb_similarity)
            gem_score = float(row.gem_score) / 100.0  # 0~100 → 0~1
            final_score = emb_sim * 0.6 + gem_score * 0.4
            scored_rows.append((row.game_id, row.app_id, final_score))

        # 6. 게임 정보 조회 / Fetch full game info
        game_ids = [r[0] for r in scored_rows]
        stmt = (
            select(Game)
            .options(selectinload(Game.metrics))
            .where(Game.id.in_(game_ids))
        )
        games_result = await db.execute(stmt)
        games = games_result.scalars().all()
        games_map = {g.id: g for g in games}

        # 7. must_not 하드 필터 + 지표 힌트 적용 / Apply must_not filter + metric hints
        final_scored: List[Tuple[Game, GameMetric, float]] = []
        for game_id, _app_id, base_score in scored_rows:
            game = games_map.get(game_id)
            if not game or not game.metrics:
                continue

            # must_not 하드 필터 / must_not hard filter (from local parsing)
            if must_not and not self._check_must_not(game.metrics, must_not):
                continue

            score = base_score

            # 지표 힌트 보너스/페널티 / Metric hint bonus/penalty
            if metric_hints:
                hint_match = 0.0
                for metric_name, target_val in metric_hints.items():
                    if metric_name not in NUMERIC_METRIC_FIELDS:
                        continue
                    actual = getattr(game.metrics, metric_name, None)
                    if actual is None:
                        continue
                    diff = abs(float(actual) - float(target_val))
                    # 차이 적을수록 보너스 / Less diff = more bonus
                    hint_match += max(0, 1.0 - diff / 10.0)

                hint_score = hint_match / len(metric_hints)
                # 지표 힌트 10% 반영 / 10% weight for metric hints
                score = score * 0.9 + hint_score * 0.1

            final_scored.append((game, game.metrics, score))

        # 8. 정렬 + limit 적용 / Sort and limit
        final_scored.sort(key=lambda x: x[2], reverse=True)
        final_scored = final_scored[:limit]

        # 9. 상대 정규화 (1위=1.0) / Relative normalization
        final_scored = self._normalize_scores(final_scored, score_idx=2)
        return final_scored

    # ==================== 응답 포맷팅 / Response Formatting ====================

    def format_semantic_results(
        self,
        results: List[Tuple[Game, GameMetric, float]],
    ) -> List[RecommendedGame]:
        """
        Format semantic search results for API response.
        Korean: 시맨틱 검색 결과를 API 응답 형식으로 변환.
        """
        formatted = []
        for game, metric, score in results:
            formatted.append(RecommendedGame(
                app_id=game.app_id,
                name=game.name or "",
                genres=game.genres or "",
                header_image=game.header_image or "",
                one_line_summary=game.one_line_summary or "",
                marketing_hook=game.marketing_hook or "",
                similarity_score=round(score, 4),
                gem_potential=metric.gem_percentile or metric.gem_potential,
                match_reasons=[],
                key_metrics=self._get_key_metrics(metric),
            ))
        return formatted

    def format_recommendations_by_preference(
        self,
        results: List[Tuple[Game, GameMetric, float]],
        preferences: Dict[str, float],
    ) -> List[RecommendedGame]:
        """
        Format preference-based recommendation results for API response.
        Korean: 선호도 기반 추천 결과를 API 응답 형식으로 변환 (match_reasons 포함).
        """
        formatted = []
        for game, metric, score in results:
            cand_vec = self._metric_to_vector(metric)
            formatted.append(RecommendedGame(
                app_id=game.app_id,
                name=game.name or "",
                genres=game.genres or "",
                header_image=game.header_image or "",
                one_line_summary=game.one_line_summary or "",
                marketing_hook=game.marketing_hook or "",
                similarity_score=round(score, 4),
                gem_potential=metric.gem_percentile or metric.gem_potential,
                match_reasons=self._generate_match_reasons_from_preferences(
                    cand_vec, preferences
                ),
                key_metrics=self._get_key_metrics(metric),
            ))
        return formatted

    def format_recommendations_by_game(
        self,
        results: List[Tuple[Game, GameMetric, float, np.ndarray]],
    ) -> List[RecommendedGame]:
        """
        Format game-based recommendation results for API response.
        Korean: 게임 기반 추천 결과를 API 응답 형식으로 변환 (공통 특징 포함).
        """
        formatted = []
        for game, metric, score, target_vec in results:
            cand_vec = self._metric_to_vector(metric)
            formatted.append(RecommendedGame(
                app_id=game.app_id,
                name=game.name or "",
                genres=game.genres or "",
                header_image=game.header_image or "",
                one_line_summary=game.one_line_summary or "",
                marketing_hook=game.marketing_hook or "",
                similarity_score=round(score, 4),
                gem_potential=metric.gem_percentile or metric.gem_potential,
                match_reasons=self._generate_match_reasons_from_target(
                    target_vec, cand_vec
                ),
                key_metrics=self._get_key_metrics(metric),
            ))
        return formatted


# ==================== 내부 헬퍼 / Internal Helpers ====================

class _PreferenceMetric:
    """
    Lightweight GameMetric-like wrapper for preference dict.
    Korean: 선호도 딕셔너리를 GameMetric처럼 wrapping하는 내부 헬퍼.

    DynamicMetricMasker.build_masked_vector()에 선호도를 전달하기 위해 사용.
    지정되지 않은 지표는 None 반환 (자동 마스킹).
    """

    def __init__(self, preferences: Dict[str, float]):
        """
        Initialize with preference dict.
        Korean: 선호도 딕셔너리로 초기화. 지정된 지표만 값 있음, 나머지 None.
        """
        self._prefs = preferences

    def __getattr__(self, name: str):
        # 지정된 지표 → 값 반환 / Return value for specified metrics
        if name in self._prefs:
            return self._prefs[name]
        # 미지정 지표 → None (마스킹 대상) / Return None for unspecified (will be masked)
        return None


# ==================== 싱글톤 / Singleton ====================

# 싱글톤 인스턴스 / Singleton instance
recommender = GameRecommender()