"""
생애주기·근거 지표 불변식 (decisions R-11/R-12, docs/lifecycle_split_spec_0905.md)
실행: cd fastapi_app && pytest tests/test_lifecycle.py -v
"""
from datetime import date, timedelta

from services.lifecycle import lifecycle, thin_new, days_since_release, NEW, ESTABLISHED, FAMOUS
from services.evidence import gem_evidence, velocity_per_day, wilson_lower, obscurity

TODAY = date(2026, 9, 5)


def test_new_is_age_first_even_with_huge_reviews():
    """카나리아: MECCHA CHAMELEON (리뷰 8.7만, 출시 ~170일) 은 '신작'이다. 유명작이 아니다."""
    released = TODAY - timedelta(days=170)
    assert lifecycle(87_553, released, TODAY) == NEW
    assert thin_new(87_553, released, TODAY) is False        # 근거가 얇지 않다 → 메인 추천 기본 포함


def test_thin_new_is_excluded_by_default_only_below_threshold():
    released = TODAY - timedelta(days=40)
    assert thin_new(18, released, TODAY) is True
    assert thin_new(209, released, TODAY) is False


def test_famous_requires_age():
    old = TODAY - timedelta(days=400)
    assert lifecycle(25_000, old, TODAY) == FAMOUS
    assert lifecycle(19_999, old, TODAY) == ESTABLISHED
    assert lifecycle(25_000, None, TODAY) == FAMOUS           # 출시일 없어도 리뷰 2만+ 면 유명


def test_unknown_release_date_is_established():
    assert lifecycle(30, None, TODAY) == ESTABLISHED
    assert thin_new(3, None, TODAY) is False                  # 출시일 모르면 신작 취급 안 함


def test_boundary_180_days():
    assert lifecycle(10, TODAY - timedelta(days=180), TODAY) == NEW
    assert lifecycle(10, TODAY - timedelta(days=181), TODAY) == ESTABLISHED


def test_gem_evidence_none_without_reviews():
    """근거 없음은 None 이다. 0 이 아니다 (C-5)."""
    assert gem_evidence(None, 0) is None
    assert gem_evidence(0.9, 0) is None
    assert gem_evidence(0.9, 500) is not None


def test_gem_evidence_shape():
    """무명 + 좋은 평가가 높고, 유명(≥ cap) 은 0, 리뷰 2건은 floor 50 덕에 과대평가되지 않는다."""
    hidden = gem_evidence(0.95, 300)
    famous = gem_evidence(0.95, 50_000)
    tiny = gem_evidence(1.0, 2)
    assert famous == 0.0
    assert hidden > tiny                                      # 300@95% > 2@100%
    assert obscurity(50) == obscurity(10)                     # floor 아래는 동일 무명도


def test_velocity():
    assert velocity_per_day(87_553, 170) == round(87_553 / 170, 3)
    assert velocity_per_day(100, 3) == round(100 / 7, 3)      # 7일 미만은 7일로
    assert velocity_per_day(100, None) is None


def test_wilson_monotone_in_n():
    assert wilson_lower(0.9, 1000) > wilson_lower(0.9, 30) > wilson_lower(0.9, 3)
    assert wilson_lower(1.0, 3) < 0.5                         # 3/3 도 0.5 를 못 넘는다 — 스테디 진입 불가
    assert wilson_lower(1.0, 3) >= 0.35                       # 신작 노출 기준은 통과
