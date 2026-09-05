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
    """검토 지적(테스트 1): quality 만 보면 0 과 0.5 폴백을 구분 못 한다 — 실제 사용값을 직접 본다."""
    _, d0 = score_v6.compute_gem_bonus(500, 0.0, 60.0)
    _, dnull = score_v6.compute_gem_bonus(500, None, 60.0)
    assert d0["positive_used"] == 0.0            # 0.0 그대로 (예전 `or 0.5` 면 0.5 가 된다)
    assert dnull["positive_used"] == 0.5         # NULL 만 폴백
    _, dz = score_v6.compute_gem_bonus(500, 0.9, 0.0)
    assert dz["gem_pct_used"] == 0.0
    _, dr = score_v6.compute_gem_bonus(0, 0.9, 60.0)
    assert dr["reviews_used"] == 0


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
    assert c1 == c2 == pytest.approx(score_v7.budgets()[0])
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
    assert c == pytest.approx(score_v7.budgets()[0])
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
    """가중치는 제곱차에 곱한다 (D-20). 검토 지적(테스트 2): 단일 지표는 가중치가 상쇄되므로 두 지표로 검증."""
    assert score_v7.preference_weight(5) == 1.0
    assert score_v7.preference_weight(0) == 2.0 == score_v7.preference_weight(10)
    prefs = {"cozy_factor": 10, "time_pressure": 6}          # w = 2.0, 1.2
    game = _metrics(cozy_factor=6, time_pressure=5)           # diff = 4, 1
    d, used = score_v7.weighted_rmse(game, prefs)
    assert used == 2
    assert d == pytest.approx(math.sqrt((2.0 * 16 + 1.2 * 1) / 3.2), abs=1e-6)   # ≈ 3.221
    # 가중치가 제곱됐다면 (4·16 + 1.44·1)/5.44 → 3.47 이 나와야 한다 — 그게 아님을 확인
    assert d != pytest.approx(math.sqrt((4.0 * 16 + 1.44) / 5.44), abs=1e-3)


def test_v7_empty_preferences_do_not_score_full():
    d, used = score_v7.weighted_rmse(_metrics(), {})
    assert used == 0 and d == 10.0
    c, _ = score_v7.compute_core_v7(_metrics(), {})
    assert c < 1.0


def test_v7_secondary_is_half_weight_and_primary_wins():
    """R-1': Vibe secondary 는 ×0.5, primary 에 같은 키가 있으면 primary 가 이긴다."""
    prefs = {"cozy_factor": 9}
    sec = {"time_pressure": 1, "cozy_factor": 0}              # cozy 는 primary 와 충돌 → 무시
    game = _metrics(cozy_factor=9, time_pressure=9)
    d_no, u_no = score_v7.weighted_rmse(game, prefs)
    d_sec, u_sec = score_v7.weighted_rmse(game, prefs, sec, 0.5)
    assert (d_no, u_no) == (0.0, 1)
    assert u_sec == 2 and d_sec > 0
    # time_pressure: w = 1.8×0.5 = 0.9, diff 8 → sqrt(0.9·64 / (2.0 + 0.9))... primary cozy w=1.8, diff 0
    assert d_sec == pytest.approx(math.sqrt((0.9 * 64) / (1.8 + 0.9)), abs=1e-6)


def test_gem_factor_zeroes_gem_but_keeps_core():
    """R-11: 신작·유명작은 gem 0. v6/v7 모두 gem_factor 가 적용되고 raw 점수가 함께 나온다."""
    r7 = score_v7.calculate_score_v7(_metrics(cozy_factor=9), {"cozy_factor": 9}, "", 300, 0.95, 80.0, gem_factor=0.0)
    assert r7["breakdown"]["gem_score"] == 0.0 and r7["raw_core_score"] == pytest.approx(score_v7.budgets()[0])
    r7g = score_v7.calculate_score_v7(_metrics(cozy_factor=9), {"cozy_factor": 9}, "", 300, 0.95, 80.0, gem_factor=1.0)
    assert r7g["breakdown"]["gem_score"] > 0
    r6 = score_v6.calculate_score_v6(_metrics(cozy_factor=9), {"cozy_factor": 9}, "", 300, 0.95, 80.0, gem_factor=0.0)
    assert r6["breakdown"]["gem_score"] == 0.0 and "raw_final_score" in r6


def test_raw_score_is_not_rounded():
    """검토 E-1: 정렬은 raw, 표시만 0.1 반올림."""
    r = score_v7.calculate_score_v7(_metrics(cozy_factor=8), {"cozy_factor": 9}, "", 300, 0.95, 80.0)
    assert r["final_score"] == round(r["raw_final_score"], 1)
    assert isinstance(r["raw_final_score"], float)


def test_identity_excludes_unreliable_metrics():
    """R-5 / 검토 E-4: 신뢰 불가 3개는 정체성 문구에도 안 나온다."""
    identity, strengths = score_v7.describe_strengths(_metrics(modding_support=9, monetization_fairness=9, cozy_factor=8))
    names = {s["metric"] for s in strengths}
    assert "modding_support" not in names and "monetization_fairness" not in names
    assert "cozy_factor" in names


def test_v7_result_shape_matches_v6():
    r = score_v7.calculate_score_v7(_metrics(cozy_factor=9), {"cozy_factor": 9}, "인디", 100, 0.9, 70.0)
    for k in ("final_score", "breakdown", "identity", "unique_strengths", "matched_strengths", "is_hidden_gem"):
        assert k in r
    for k in ("core_score", "xfactor_score", "gem_score", "fields_compared"):
        assert k in r["breakdown"]
    assert r["breakdown"]["xfactor_score"] == 0.0
    assert r["final_score"] <= 99.0


# ---------- 동점 처리 ----------

def test_wilson_lower_bound():
    assert _wilson_lower(None, 100) == 0.0
    assert _wilson_lower(1.0, 0) == 0.0
    assert 0.6 < _wilson_lower(1.0, 10) < 0.75      # 10/10 → 약 0.72
    assert _wilson_lower(0.9, 1000) > _wilson_lower(0.9, 10)


# ---------- R-3 evidence 모드 ----------

def test_gem_evidence_mode_budgets_and_null(monkeypatch):
    """GEM_SOURCE=evidence: Core 87 + gem 12, 근거 NULL 은 0(폴백 없음), 60 이면 7.2, established 만."""
    from config import settings
    monkeypatch.setattr(settings, "GEM_SOURCE", "evidence")
    monkeypatch.setattr(settings, "GEM_MAX_V7_EVIDENCE", 12.0)
    core_max, gem_max = score_v7.budgets()
    assert (core_max, gem_max) == (87.0, 12.0)
    r_null = score_v7.calculate_score_v7(_metrics(cozy_factor=9), {"cozy_factor": 9}, "", 300, 0.95, 80.0, gem_evidence=None)
    assert r_null["breakdown"]["gem_score"] == 0.0 and r_null["raw_core_score"] == pytest.approx(87.0)
    r60 = score_v7.calculate_score_v7(_metrics(cozy_factor=9), {"cozy_factor": 9}, "", 300, 0.95, 80.0, gem_evidence=60.0)
    assert r60["breakdown"]["gem_score"] == pytest.approx(7.2)
    assert r60["final_score"] == pytest.approx(94.2, abs=0.05)
    r_new = score_v7.calculate_score_v7(_metrics(cozy_factor=9), {"cozy_factor": 9}, "", 300, 0.95, 80.0, gem_evidence=60.0, gem_factor=0.0)
    assert r_new["breakdown"]["gem_score"] == 0.0
    # LLM 계보 값(gem_percentile 80)은 evidence 모드에서 아무 영향이 없어야 한다
    r_llm = score_v7.calculate_score_v7(_metrics(cozy_factor=9), {"cozy_factor": 9}, "", 300, 0.95, 99.0, gem_evidence=None)
    assert r_llm["breakdown"]["gem_score"] == 0.0


def test_v6_follows_gem_source_flag(monkeypatch):
    """v6 도 GEM_SOURCE=evidence 를 따른다: gem = evidence/100 × 6, NULL→0, LLM gem_percentile 무시.
    (v7 만 바꾸면 SCORE_VERSION=v6 상태에서 경로 A 만 legacy 로 남아 B/C 와 발굴 기준이 갈렸다 — 2026-09-05)"""
    from config import settings
    m = _metrics(cozy_factor=9); prefs = {"cozy_factor": 9}
    legacy = score_v6.calculate_score_v6(m, prefs, "", 300, 0.95, 99.0, gem_evidence=None)
    assert legacy["breakdown"]["gem_score"] > 0.0                      # legacy: gem_percentile 99 → 보너스 있음
    monkeypatch.setattr(settings, "GEM_SOURCE", "evidence")
    r_null = score_v6.calculate_score_v6(m, prefs, "", 300, 0.95, 99.0, gem_evidence=None)
    assert r_null["breakdown"]["gem_score"] == 0.0                      # 같은 입력, 근거 NULL → 0 (폴백 없음)
    r60 = score_v6.calculate_score_v6(m, prefs, "", 300, 0.95, 99.0, gem_evidence=60.0)
    assert r60["breakdown"]["gem_score"] == pytest.approx(3.6) and r60["is_hidden_gem"] is True
    r45 = score_v6.calculate_score_v6(m, prefs, "", 300, 0.95, 99.0, gem_evidence=45.0)
    assert r45["is_hidden_gem"] is False
    r_new = score_v6.calculate_score_v6(m, prefs, "", 300, 0.95, 99.0, gem_evidence=60.0, gem_factor=0.0)
    assert r_new["breakdown"]["gem_score"] == 0.0                       # 신작·유명작은 계수 0


def test_legacy_mode_unchanged_by_default():
    from config import settings
    assert settings.GEM_SOURCE == "legacy"
    assert score_v7.budgets() == (93.0, 6.0)
