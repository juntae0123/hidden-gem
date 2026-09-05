# fastapi_app/services/score_v7.py
"""
Score System v7 — 질의 마스크 + 가중 RMSE
Korean: 점수 시스템 v7 — 사용자가 말한 지표만, 말한 값 그대로.

왜 v7 인가 (2026-09-05, docs/final_verdict_0905.md D-26 / docs/decisions_0905.md R-1):
    v6 의 Core 는 장르 핵심 지표를 목표값 5.0 과 비교했다. 호출자가 sparse preferences 를
    넘기는데 `target_metrics.get(f, 5.0)` 이 조용히 메웠기 때문이다. 그 결과 Core 의 65% 가
    "사용자가 원한 것에 가깝나"가 아니라 "자기 장르에서 얼마나 평범한가"를 재고 있었다
    (힐링 cozy 9: 장르핵심 전부 5 → 66.1, 전부 9 → 50.0). 또 `v >= 7` 임계가 0~10 의 아래
    절반을 버렸고, X-Factor 18점은 질의와 무관한 상수였다.

v7 규칙:
    P      = preferences 의 모든 키 (임계 없음. 0 도 9 도 목표다)
    w_f    = 1 + |pref_f − 5| / 5                      (1.0 ~ 2.0, 극단 선호를 더 세게)
    dist   = sqrt( Σ w_f (pref_f − game_f)² / Σ w_f )   (0 ~ 10, 가중 RMSE — 가중치가 제곱되지 않는다)
    match  = exp( −(dist / TAU)² )                      (dist 0 → 정확히 1.0)
    core   = match × SCORE_CORE_MAX(93)
    final  = core + gem(≤ 6)                            (0 ~ 99)

    사용자가 말하지 않은 지표는 거리에 들어가지 않는다. 장르 핵심 지표도 점수에 없다.
    X-Factor 는 없다. identity / strengths 는 정보용으로만 만든다 (점수 아님).
    gem 은 당분간 v6 의 compute_gem_bonus 를 그대로 쓴다 — 증거 지수 전환(R-3)은 별도 단계.

전환: settings.SCORE_VERSION == "v7" 일 때만 recommend_by_preference 가 이 모듈을 쓴다.
      기본값은 v6. 절제 도구(embeddings/ablation.py)로 전체 풀을 비교한 뒤 기본값을 올린다.
"""

import math
from typing import Dict, Optional

from config import settings
from models.game import NUMERIC_METRIC_FIELDS
from services.score_v6 import (
    IDENTITY_PHRASES,
    SCORE_GEM_MAX,
    SCORE_MAX,
    XFACTOR_RARE,
    XFACTOR_THRESHOLD,
    compute_gem_bonus,
)

SCORE_CORE_MAX = 93.0     # legacy gem(6) 모드. evidence 모드에선 99 − GEM_MAX_V7_EVIDENCE (= 87)


def budgets() -> tuple[float, float]:
    """(core_max, gem_max) — GEM_SOURCE 에 따라. evidence: 87 + 12 / legacy: 93 + 6."""
    if settings.GEM_SOURCE == "evidence":
        g = float(settings.GEM_MAX_V7_EVIDENCE)
        return SCORE_MAX - g, g
    return SCORE_CORE_MAX, SCORE_GEM_MAX

# identity(정보용) 후보에서도 제외 — 홀드아웃 r 0.36~0.61. 값은 DB 에 보존 (decisions R-5)
UNRELIABLE_IDENTITY_FIELDS = frozenset({"modding_support", "community_dependency", "monetization_fairness"})
TAU = 3.5                 # 가우시안 폭. dist 1→0.92, 2→0.72, 3→0.48, 4→0.27, 6→0.05
                          # 초기값. 절제 도구 실측 후 조정 가능 (decisions R-1)


def preference_weight(pref_value: float) -> float:
    """극단 선호에 더 큰 가중치. 5(중립) → 1.0, 0 또는 10 → 2.0."""
    return 1.0 + abs(float(pref_value) - 5.0) / 5.0


def weighted_rmse(
    game_metrics: Dict[str, float],
    preferences: Dict[str, float],
    secondary: Optional[Dict[str, float]] = None,
    secondary_weight: float = 0.5,
) -> tuple[float, int]:
    """
    사용자가 말한 지표만으로 가중 RMSE. (dist, 비교에 들어간 지표 수) 반환.
    secondary: Vibe 정의가 말한 부수 목표값 (R-1'). primary 에 같은 키가 있으면 primary 가 이긴다. 가중치 ×secondary_weight.
    preferences 가 비었거나 유효 지표가 없으면 dist=10 (최대 거리) — 근거 없는 후보는 만점을 받지 않는다.
    game_metrics 는 폴백이 끝난 완전한 dict 여야 한다 (resolve_null 통과). 따라서 '비교 수'는 '관측 수'가 아니다 —
    후보 값이 NULL 이었으면 정책 폴백값과 비교한 것이다.
    """
    num = 0.0
    den = 0.0
    used = 0
    items = [(f, v, 1.0) for f, v in preferences.items()]
    if secondary:
        items += [(f, v, secondary_weight) for f, v in secondary.items() if f not in preferences]
    for f, pref, scale in items:
        if f not in NUMERIC_METRIC_FIELDS:
            continue
        g = game_metrics.get(f)
        if g is None:
            continue
        w = preference_weight(pref) * scale
        d = float(pref) - float(g)
        num += w * d * d
        den += w
        used += 1
    if used == 0 or den == 0.0:
        return 10.0, 0
    return math.sqrt(num / den), used


def match_from_distance(dist: float, tau: float = TAU) -> float:
    """가우시안 커널. dist 0 → 1.0, 단조 감소, 0 초과."""
    return math.exp(-((dist / tau) ** 2))


def compute_core_v7(
    game_metrics: Dict[str, float],
    preferences: Dict[str, float],
    secondary: Optional[Dict[str, float]] = None,
    secondary_weight: float = 0.5,
) -> tuple[float, dict]:
    dist, used = weighted_rmse(game_metrics, preferences, secondary, secondary_weight)
    match = match_from_distance(dist)
    core = match * budgets()[0]
    matched = [
        {"metric": f, "value": game_metrics.get(f), "target": v}
        for f, v in preferences.items()
        if f in NUMERIC_METRIC_FIELDS and game_metrics.get(f) is not None
        and abs(float(v) - float(game_metrics[f])) <= 1.5
    ]
    return core, {
        "distance": round(dist, 3),
        "match": round(match, 4),
        "fields_used": used,
        "matched_strengths": matched,
    }


def describe_strengths(game_metrics: Dict[str, float]) -> tuple[str, list]:
    """정보용 정체성 문구. 점수에 영향 없음. 8+ 지표 상위 3개."""
    top = sorted(
        ((f, v) for f, v in game_metrics.items()
         if f in NUMERIC_METRIC_FIELDS and f not in UNRELIABLE_IDENTITY_FIELDS
         and v is not None and v >= XFACTOR_THRESHOLD),
        key=lambda x: -x[1],
    )[:3]
    strengths = [
        {
            "metric": f,
            "value": v,
            "label": IDENTITY_PHRASES.get(f, f),
            "is_exceptional": v >= XFACTOR_RARE,
        }
        for f, v in top
    ]
    phrases = [IDENTITY_PHRASES.get(f, "") for f, _ in top[:2]]
    phrases = [p for p in phrases if p]
    identity = " + ".join(phrases) if phrases else "독특한 매력"
    return identity, strengths


def calculate_score_v7(
    game_metrics: Dict[str, float],
    target_metrics: Dict[str, float],
    genre: str = "",
    review_count: Optional[int] = None,
    positive_ratio: Optional[float] = None,
    gem_percentile: Optional[float] = None,
    gem_factor: float = 1.0,
    secondary: Optional[Dict[str, float]] = None,
    secondary_weight: float = 0.5,
    gem_evidence: Optional[float] = None,
) -> dict:
    """
    v6 와 같은 반환 형태 + raw_final_score / raw_core_score. breakdown 에 xfactor_score 는 항상 0.0 (필드 호환).
    genre 는 받기만 하고 점수에 쓰지 않는다 (호출부 시그니처 호환).
    """
    core_score, core_detail = compute_core_v7(game_metrics, target_metrics, secondary, secondary_weight)
    if settings.GEM_SOURCE == "evidence":
        # R-3: 리뷰 실측 지수만. NULL(근거 없음) 은 0 — 폴백 없음, review_bonus 없음, confidence 없음
        gem_max = budgets()[1]
        gem_score = (float(gem_evidence) / 100.0 * gem_max) if gem_evidence is not None else 0.0
        gem_detail = {"is_hidden_gem": gem_evidence is not None and gem_evidence >= 60, "source": "evidence"}
    else:
        gem_score, gem_detail = compute_gem_bonus(review_count, positive_ratio, gem_percentile)
    gem_score *= gem_factor          # 생애주기 계수 (established 만 1.0). 호출자가 lifecycle.gem_factor 로 결정
    final = min(core_score + gem_score, SCORE_MAX)
    identity, strengths = describe_strengths(game_metrics)
    return {
        "final_score": round(final, 1),      # 표시용. 정렬은 raw_final_score 로 — 반올림 동점에 gem 이 두 번 개입하던 문제
        "raw_final_score": final,
        "raw_core_score": core_score,
        "breakdown": {
            "core_score": round(core_score, 1),
            "xfactor_score": 0.0,
            "gem_score": round(gem_score, 1),
            "distance": core_detail["distance"],
            # 'fields_compared': 비교에 들어간 선호 지표 수. 후보 값이 NULL 이면 폴백값과 비교했으므로 '관측' 수는 아니다
            "fields_compared": core_detail["fields_used"],
        },
        "identity": identity,
        "unique_strengths": strengths,
        "matched_strengths": core_detail["matched_strengths"],
        "is_hidden_gem": gem_detail["is_hidden_gem"],
    }
