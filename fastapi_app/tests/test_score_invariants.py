"""
점수 불변식 테스트 — docs/system_invariants.md C-1·C-5·C-10, docs/decisions_0905.md R-1
Korean: 깨지면 안 되는 채점 규칙. 순수 함수만 다루므로 DB·Redis 없이 돈다.

실행: cd fastapi_app && pytest tests/test_score_invariants.py -v
"""

import math
import pytest

from services import score_v6, score_v7
from services.recommender import resolve_null, to_display_score, _gem_display, _wilson_lower


class _M:
    def __init__(self, pct=None, pot=None):
        self.gem_percentile = pct
        self.gem_potential = pot


# ---------- 0 과 NULL 은 다르다 (C-5, D-2, D-10, D-24) ----------

def test_gem_percentile_zero_is_not_fifty():
    """gem_percentile 0 은 0 으로 읽혀야 한다 — 증거 지수 전환의 핵심."""
    b0, d0 = score_v6.compute_gem_bonus(500, 0.9, 0.0)
    b50, d50 = score_v6.compute_gem_bonus(500, 0.9, 50.0)
    bnull, dnull = score_v6.compute_gem_bonus(500, 0.9, None)
    assert d0["gem_signal"] == 0.0
    assert b0 < b50
    assert bnull == b50            # NULL 만 50 으로 폴백


def test_positive_ratio_zero_is_not_half():
    _, d0 = score_v6.compute_gem_bonus(500, 0.0, 60.0)
    _, dnull = score_v6.compute_gem_bonus(500, None, 60.0)
    assert d0["quality"] == 0.0 and dnull["quality"] == 0.0
    # 0.0 은 유효값: is_hidden_gem 판정에 들어간다 (0.5 로 바뀌면 안 됨)
    assert d0["is_hidden_gem"] is False


def test_quality_is_clamped():
    """0~100 스케일 값이 유입돼도 전원 만점이 되지 않는다 (D-18)."""
    _, d = score_v6.compute_gem_bonus(500, 95.0, 50.0)
    assert d["quality"] == 1.0


def test_resolve_null_preserves_zero():
    """진짜 0.0 은 0.0 이다. `or 5.0` 은 이걸 깨뜨렸다 (D-10)."""
    assert resolve_null("horror_factor", 0.0) == 0.0
    assert resolve_null("cozy_factor", 0) == 0.0
    assert resolve_null("horror_factor", None) == 0.0        # ZERO 정책
    assert resolve_null("visual_spectacle", None) == 7.0     # GLOBAL_MEAN
    assert resolve_null("unknown_metric", None) == 5.0


def test_gem_display_prefers_percentile_even_when_zero():
    assert _gem_display(_M(pct=0.0, pot=88.0)) == 0.0
    assert _gem_display(_M(pct=None, pot=88.0)) == 88.0
    assert _gem_display(_M(pct=None, pot=None)) is None


def test_display_score_has_floor_zero():
    """경로 C 의 emb_score 는 음수가 될 수 있다 — 표시 점수는 0 아래로 안 간다."""
    assert to_display_score(-0.3, 0.0) == 0.0
    assert to_display_score(1.0, 1.0) == 99.0


# ---------- v7 규칙 (R-1) ----------

def _metrics(**over):
    m = {f: 5.0 for f in score_v7.NUMERIC_METRIC_FIELDS}
    m.update(over)
    return m


def test_v7_ignores_genre_core_and_unmentioned_metrics():
    """D-26: 말하지 않은 지표는 점수에 들어가지 않는다. 장르 핵심에서 뛰어나도 페널티 없음."""
    prefs = {"cozy_factor": 9}
    plain = _metrics(cozy_factor=9)                                   # 나머지 전부 5
    excellent = _metrics(cozy_factor=9, narrative_depth=9, replay_value=9,
                         art_style_uniqueness=9, audio_design=9, exploration_reward=9)
    c1, _ = score_v7.compute_core_v7(plain, prefs)
    c2, _ = score_v7.compute_core_v7(excellent, prefs)
    assert c1 == c2 == pytest.approx(score_v7.SCORE_CORE_MAX)
    # 같은 입력에서 v6 는 뛰어난 쪽을 깎았다 (회귀 방지용 기록)
    v6_plain, _ = score_v6.compute_core_score(plain, prefs, "캐주얼")
    v6_exc, _ = score_v6.compute_core_score(excellent, prefs, "캐주얼")
    assert v6_exc < v6_plain - 10


def test_v7_low_preferences_count():
    """`v >= 7` 임계 제거: 낮은 선호(time_pressure 1)가 점수에 들어간다."""
    prefs = {"cozy_factor": 9, "time_pressure": 1}
    calm = _metrics(cozy_factor=9, time_pressure=1)
    rushed = _metrics(cozy_factor=9, time_pressure=9)
    c_calm, _ = score_v7.compute_core_v7(calm, prefs)
    c_rush, _ = score_v7.compute_core_v7(rushed, prefs)
    assert c_calm > c_rush + 30
    # v6 에서는 둘이 같았다 (time_pressure 1 은 버려졌다)
    v6_calm, _ = score_v6.compute_core_score(calm, prefs, "캐주얼")
    v6_rush, _ = score_v6.compute_core_score(rushed, prefs, "캐주얼")
    assert v6_calm == pytest.approx(v6_rush)


def test_v7_perfect_match_is_full_core():
    prefs = {"horror_factor": 9, "melancholy": 6, "cozy_factor": 0}
    game = _metrics(horror_factor=9, melancholy=6, cozy_factor=0)
    c, d = score_v7.compute_core_v7(game, prefs)
    assert c == pytest.approx(score_v7.SCORE_CORE_MAX)
    assert d["distance"] == 0.0 and d["fields_used"] == 3


def test_v7_zero_preference_is_a_target():
    """cozy 0 을 원하면 cozy 9 게임은 크게 깎인다 (D-8)."""
    prefs = {"horror_factor": 9, "cozy_factor": 0}
    good = _metrics(horror_factor=9, cozy_factor=0)
    bad = _metrics(horror_factor=9, cozy_factor=9)
    c_good, _ = score_v7.compute_core_v7(good, prefs)
    c_bad, _ = score_v7.compute_core_v7(bad, prefs)
    assert c_bad < c_good * 0.5


def test_v7_weight_is_linear_not_squared():
    """가중치는 제곱차에 곱한다 → 극단 선호 2배, 50배·2500배 같은 폭주 없음 (D-20)."""
    assert score_v7.preference_weight(5) == 1.0
    assert score_v7.preference_weight(0) == 2.0 == score_v7.preference_weight(10)
    d, used = score_v7.weighted_rmse(_metrics(cozy_factor=5), {"cozy_factor": 9})
    assert d == pytest.approx(4.0) and used == 1     # 단일 지표면 거리 = |차이|


def test_v7_empty_preferences_do_not_score_full():
    d, used = score_v7.weighted_rmse(_metrics(), {})
    assert used == 0 and d == 10.0
    c, _ = score_v7.compute_core_v7(_metrics(), {})
    assert c < 1.0


def test_v7_result_shape_matches_v6():
    r = score_v7.calculate_score_v7(_metrics(cozy_factor=9), {"cozy_factor": 9}, "인디", 100, 0.9, 70.0)
    for k in ("final_score", "breakdown", "identity", "unique_strengths", "matched_strengths", "is_hidden_gem"):
        assert k in r
    for k in ("core_score", "xfactor_score", "gem_score"):
        assert k in r["breakdown"]
    assert r["breakdown"]["xfactor_score"] == 0.0
    assert r["final_score"] <= 99.0


# ---------- 동점 처리 ----------

def test_wilson_lower_bound():
    assert _wilson_lower(None, 100) == 0.0
    assert _wilson_lower(1.0, 0) == 0.0
    assert 0.6 < _wilson_lower(1.0, 10) < 0.75      # 10/10 → 약 0.72
    assert _wilson_lower(0.9, 1000) > _wilson_lower(0.9, 10)
