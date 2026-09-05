# fastapi_app/services/score_v6.py
"""
Score System v6 — Core + X-Factor + Gem
Korean: 점수 시스템 v6 — 핵심매칭 + 독창성 + 숨은명작.

설계 철학 (juntae):
    "60개 지표 = 게임 고유성"
    같은 RPG도 감성/액션/스토리가 다름.
    Core(장르핵심 + 검색의도) + X-Factor(독창성) + Gem(발굴)으로 차별화.
    스팀 인기순위와 구분.

v6.2:
    - NUMERIC_METRIC_FIELDS를 models.game에서 import (자체정의 제거, 일치 보장)
    - 검색 의도 주입 (intent_fields)
    - sigmoid 변별력 강화
"""

import math
import numpy as np

# recommender와 동일한 필드 (models.game 출처, 49개, 순환 없음)
from models.game import NUMERIC_METRIC_FIELDS
from config import settings


# ==================== 점수 구간 (합 99) ====================
SCORE_CORE_MAX = 75.0      # 장르핵심 + 의도 매칭
SCORE_XFACTOR_MAX = 18.0   # 독창성 가산
SCORE_GEM_MAX = 6.0        # 숨은 명작
SCORE_MAX = 99.0

# 가중치 (극단 완화 — juntae 우려 반영)
W_PRIMARY = 4.0
W_SECONDARY = 2.0
W_NEUTRAL = 0.7
W_IRRELEVANT = 0.2

# sigmoid (변별력 핵심)
SIGMOID_SCALE = 2.5

# X-Factor 임계
XFACTOR_THRESHOLD = 8.0   # 8+ = 독창적 강점
XFACTOR_RARE = 9.0        # 9+ = 탁월


# ==================== 장르별 핵심지표 ====================
# 모두 models.game NUMERIC_METRIC_FIELDS에 존재하는 필드만 사용
GENRE_CORE_METRICS: dict[str, list[str]] = {
    'RPG': [
        'narrative_depth', 'growth_reward', 'choice_consequence',
        'lore_richness', 'exploration_reward',
    ],
    '전략': [
        'strategic_depth', 'management_complexity', 'replay_value',
        'learning_curve',
    ],
    '액션': [
        'action_pacing', 'reflex_demand', 'visual_spectacle',
        'animation_quality',
    ],
    '시뮬레이션': [
        'management_complexity', 'freedom_level', 'replay_value',
        'progression_clarity',
    ],
    '어드벤처': [
        'exploration_reward', 'narrative_depth', 'environmental_storytelling',
        'world_reactivity',
    ],
    '인디': [
        'art_style_uniqueness', 'narrative_depth', 'audio_design',
    ],
    '로그라이크': [
        'replay_value', 'rng_dependency', 'learning_curve', 'build_variety',
    ],
    '공포': [
        'horror_factor', 'melancholy', 'dark_fantasy_vibe',
    ],
    '퍼즐': [
        'puzzle_complexity', 'strategic_depth',
    ],
}

DEFAULT_CORE_METRICS = [
    'narrative_depth', 'replay_value', 'art_style_uniqueness',
    'audio_design', 'exploration_reward',
]


# ==================== 정체성 설명 매핑 ====================
IDENTITY_PHRASES: dict[str, str] = {
    'dark_fantasy_vibe': '어두운 판타지',
    'world_reactivity': '살아있는 세계',
    'melancholy': '쓸쓸한 감성',
    'cozy_factor': '아늑한 분위기',
    'horror_factor': '공포',
    'humor_rating': '유머',
    'art_style_uniqueness': '독창적 아트',
    'soundtrack_impact': '강렬한 음악',
    'environmental_storytelling': '환경 서사',
    'epic_scale': '대서사',
    'exploration_reward': '탐험의 재미',
    'lore_richness': '깊은 세계관',
    'choice_consequence': '선택의 무게',
    'strategic_depth': '전략적 깊이',
    'puzzle_complexity': '두뇌 퍼즐',
    'replay_value': '높은 리플레이',
    'freedom_level': '자유도',
    'visual_spectacle': '화려한 연출',
    'build_variety': '빌드 다양성',
    'reflex_demand': '빠른 손맛',
    'action_pacing': '경쾌한 액션',
    'growth_reward': '성장의 쾌감',
    'narrative_depth': '깊은 서사',
    'gore_level': '강렬한 고어',
    'stealth_importance': '은신 플레이',
    'coop_synergy': '협동 재미',
    'modding_support': '모딩 자유',
    'npc_interaction': '풍부한 교류',
}


# ==================== 유사도 함수 ====================

def improved_sigmoid(dist: float, n_active: int) -> float:
    """
    Improved sigmoid with strong discrimination.
    Korean: 변별력 강화 sigmoid. 거리가 작을수록 급격히 차별화.

    거리 0  → ~0.92  (거의 동일)
    거리 3  → ~0.65  (유사)
    거리 6  → ~0.30  (다름)
    거리 10 → ~0.08  (매우 다름)
    """
    norm_dist = dist / max(n_active ** 0.5, 1.0)
    raw = 1.0 / (1.0 + math.exp(norm_dist / SIGMOID_SCALE - 1.5))
    return max(0.0, min(1.0, raw))


def cosine_sim(v1: np.ndarray, v2: np.ndarray) -> float:
    """
    Cosine similarity (0~1).
    Korean: 코사인 유사도. 벡터 방향(성격) 비교.
    """
    n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    return float(max(0.0, min(np.dot(v1, v2) / (n1 * n2), 1.0)))


# ==================== Core 점수 (장르핵심 + 의도) ====================

def compute_core_score(
    game_metrics: dict[str, float],
    target_metrics: dict[str, float],
    genre: str,
) -> tuple[float, dict]:
    """
    Genre-core + search intent matching.
    Korean: 장르 핵심지표 + 검색 의도 매칭 (안정적 기반).

    검색 의도(target 7+ 지표)를 Core에 동적 추가 →
    "다크판타지 검색" 시 dark_fantasy가 Core에 포함되어
    의도 맞는 게임이 높은 점수를 받음.
    """
    core_fields = GENRE_CORE_METRICS.get(genre, DEFAULT_CORE_METRICS)
    core_fields = [f for f in core_fields if f in NUMERIC_METRIC_FIELDS]
    if not core_fields:
        core_fields = list(DEFAULT_CORE_METRICS)
    else:
        core_fields = list(core_fields)

    # 검색 의도 지표 추가 (유저가 7+ 로 강하게 지정한 것)
    intent_fields = [
        f for f, v in target_metrics.items()
        if v >= 7 and f in NUMERIC_METRIC_FIELDS and f not in core_fields
    ]
    all_core_fields = core_fields + intent_fields

    if not all_core_fields:
        return 0.0, {
            'core_fields': [], 'intent_fields': [], 'matched_strengths': [],
        }

    # 벡터 + 가중치 (의도 지표는 2배)
    target_vec, game_vec, weights = [], [], []
    for f in all_core_fields:
        target_vec.append(target_metrics.get(f, 5.0))
        game_vec.append(game_metrics.get(f, 5.0))
        weights.append(2.0 if f in intent_fields else 1.0)

    target_vec = np.array(target_vec)
    game_vec = np.array(game_vec)
    weights = np.array(weights)

    # 가중 유클리드 (의도 차이를 크게 반영)
    diff = (target_vec - game_vec) * weights
    dist = float(np.linalg.norm(diff))
    eucl = improved_sigmoid(dist, len(all_core_fields))

    # 가중 코사인 (성격 유사도)
    cos = cosine_sim(target_vec * weights, game_vec * weights)
    core_sim = eucl * 0.65 + cos * 0.35

    core_score = core_sim * SCORE_CORE_MAX

    matched = [
        {'metric': f, 'value': game_metrics.get(f, 0)}
        for f in all_core_fields if game_metrics.get(f, 0) >= 7
    ]

    return core_score, {
        'core_fields': core_fields,
        'intent_fields': intent_fields,
        'core_similarity': round(core_sim, 3),
        'matched_strengths': matched,
    }


# ==================== X-Factor (독창성 가산) ====================

def compute_xfactor_score(
    game_metrics: dict[str, float],
    genre: str,
) -> tuple[float, dict]:
    """
    X-Factor: game's unique standout traits (진짜 차별화).
    Korean: X-Factor — 그 게임만의 독창적 강점.

    juntae 핵심: "장르 핵심 외 그 게임만의 독특한 무언가"
    예: Witcher 3 (RPG) → dark_fantasy(9), world_reactivity(8)
        = "어두운 판타지 + 살아있는 세계"
    """
    core_fields = set(GENRE_CORE_METRICS.get(genre, DEFAULT_CORE_METRICS))

    x_factors = []
    for field in NUMERIC_METRIC_FIELDS:
        if field in core_fields:
            continue
        value = game_metrics.get(field, 0)
        if value >= XFACTOR_THRESHOLD:
            weight = 1.5 if value >= XFACTOR_RARE else 1.0
            x_factors.append({'metric': field, 'value': value, 'weight': weight})

    # 점진적 가산 (극단 X — 7 초과분만, 가중)
    raw_bonus = sum((xf['value'] - 7) * xf['weight'] for xf in x_factors)
    xfactor_score = min(raw_bonus * 1.3, SCORE_XFACTOR_MAX)

    top = sorted(x_factors, key=lambda x: -x['value'])[:3]
    identity = _describe_identity(top)

    return xfactor_score, {
        'xfactor_count': len(x_factors),
        'unique_strengths': [
            {
                'metric': xf['metric'],
                'value': xf['value'],
                'label': IDENTITY_PHRASES.get(xf['metric'], xf['metric']),
                'is_exceptional': xf['value'] >= XFACTOR_RARE,
            }
            for xf in top
        ],
        'identity': identity,
    }


def _describe_identity(top_factors: list) -> str:
    """
    Generate identity from X-Factors.
    Korean: X-Factor → 게임 정체성 설명.
    """
    if not top_factors:
        return "독특한 매력"
    phrases = [IDENTITY_PHRASES.get(xf['metric'], '') for xf in top_factors[:2]]
    phrases = [p for p in phrases if p]
    return ' + '.join(phrases) if phrases else "독특한 매력"


# ==================== Gem 보너스 (숨은 명작) ====================

def compute_gem_bonus(
    review_count,
    positive_ratio,
    gem_percentile,
) -> tuple[float, dict]:
    """
    Hidden gem bonus (발굴 정체성).
    Korean: 숨은 명작 보너스. 인지도 낮지만 품질 높은 게임 우대.

    juntae 정체성: "숨겨진 명작 발굴"
        리뷰 적음 + 평점 높음 + gem_percentile 높음
        스팀 인기순위가 못 잡는 영역.
    """
    # NULL 과 0 을 구분한다 (D-2 / D-24). `or` 는 실제 값 0 을 폴백으로 바꿔버린다.
    reviews = review_count if review_count is not None else 0
    positive = positive_ratio if positive_ratio is not None else 0.5
    gem_pct = gem_percentile if gem_percentile is not None else 50.0

    # 인지도 역수 (적을수록 ↑, 단 최소 신뢰도)
    if reviews < 100:
        discovery = 0.3   # 너무 적으면 신뢰도 부족
    elif reviews < 1000:
        discovery = 1.0   # 진짜 숨은 보석
    elif reviews < 10000:
        discovery = 0.7
    elif reviews < 100000:
        discovery = 0.3
    else:
        discovery = 0.1   # 다 아는 게임

    # 품질 (85%+ 만 인정)
    # 0~1 스케일 전제. 상한 클램프는 0~100 스케일 값이 유입될 때 전원 만점이 되는 것을 막는다 (D-18)
    quality = min(1.0, max(0.0, (positive - 0.85) / 0.15)) if positive >= 0.85 else 0.0
    gem_signal = gem_pct / 100

    bonus = (discovery * 0.4 + quality * 0.3 + gem_signal * 0.3) * SCORE_GEM_MAX

    return min(bonus, SCORE_GEM_MAX), {
        'discovery': round(discovery, 2),
        'quality': round(quality, 2),
        'gem_signal': round(gem_signal, 2),
        'is_hidden_gem': reviews < 10000 and positive >= 0.85,
        # 테스트 관측용: 실제로 어떤 값이 계산에 쓰였나 (0 과 NULL 폴백을 구분해 검증할 수 있게)
        'positive_used': positive,
        'gem_pct_used': gem_pct,
        'reviews_used': reviews,
    }


# ==================== 통합 점수 v6 ====================

def calculate_score_v6(
    game_metrics: dict[str, float],
    target_metrics: dict[str, float],
    genre: str,
    review_count=None,
    positive_ratio=None,
    gem_percentile=None,
    gem_factor: float = 1.0,
    gem_evidence=None,
) -> dict:
    """
    Unified score v6: Core + X-Factor + Gem.
    Korean: 통합 점수 v6 — 핵심매칭 + 독창성 + 숨은명작.

    juntae 철학 완성:
        Core(75) + X-Factor(18) + Gem(6) = 0~99
        스팀 인기순위와 차별화.

    Args:
        game_metrics: 게임 지표 dict (models 필드 49개)
        target_metrics: 검색 의도/선호 (preferences)
        genre: 게임 첫 장르
        review_count: Steam 리뷰 수
        positive_ratio: Steam 긍정 비율 (0~1)
        gem_percentile: gem 백분위 (0~100) — GEM_SOURCE=legacy 에서만 사용
        gem_evidence: game_metrics.gem_evidence_score (0~100, NULL=근거 없음) — GEM_SOURCE=evidence 에서만 사용

    Returns:
        final_score, breakdown, identity, unique_strengths 등
    """
    core_score, core_detail = compute_core_score(
        game_metrics, target_metrics, genre
    )
    xfactor_score, xfactor_detail = compute_xfactor_score(game_metrics, genre)
    if settings.GEM_SOURCE == "evidence":
        # R-3: v6 도 같은 플래그를 따른다 (gem = evidence/100 × 6, NULL→0, 폴백·review_bonus·confidence 없음).
        # v7 만 바꾸면 SCORE_VERSION=v6 상태에서 경로 A 만 legacy 로 남아 B/C 와 발굴 기준이 갈린다 (2026-09-05 발견).
        gem_score = (float(gem_evidence) / 100.0 * SCORE_GEM_MAX) if gem_evidence is not None else 0.0
        gem_detail = {"is_hidden_gem": gem_evidence is not None and gem_evidence >= 60, "source": "evidence"}
    else:
        gem_score, gem_detail = compute_gem_bonus(
            review_count, positive_ratio, gem_percentile
        )
    gem_score *= gem_factor   # 생애주기 계수 — established 만 1.0 (lifecycle.gem_factor)

    final = min(core_score + xfactor_score + gem_score, SCORE_MAX)

    return {
        'final_score': round(final, 1),
        'raw_final_score': final,        # 정렬용. 표시 점수 반올림으로 생기는 동점에 gem 이 다시 개입하지 않게
        'raw_core_score': core_score,
        'breakdown': {
            'core_score': round(core_score, 1),
            'xfactor_score': round(xfactor_score, 1),
            'gem_score': round(gem_score, 1),
        },
        'identity': xfactor_detail['identity'],
        'unique_strengths': xfactor_detail['unique_strengths'],
        'matched_strengths': core_detail['matched_strengths'],
        'is_hidden_gem': gem_detail['is_hidden_gem'],
    }
