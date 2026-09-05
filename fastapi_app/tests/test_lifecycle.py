"""
생애주기·근거 지표 불변식 (decisions R-11/R-12, docs/lifecycle_split_spec_0905.md)
실행: cd fastapi_app && pytest tests/test_lifecycle.py -v
"""
from datetime import date, timedelta

from services.lifecycle import (
    lifecycle, thin_new, days_since_release, is_famous, gem_factor, admit,
    NEW, ESTABLISHED, FAMOUS, UPCOMING,
)
from services.evidence import gem_evidence, velocity_per_day, wilson_lower, obscurity

TODAY = date(2026, 9, 5)


def test_new_is_age_first_even_with_huge_reviews():
    """카나리아: MECCHA CHAMELEON (리뷰 8.7만, 출시 ~170일) 은 신작 *후보에 들어간다*. 동시에 is_famous 다 (두 축).
    '영구 1위'는 조건이 아니다 — 속도 정렬은 데이터에 따라 바뀐다 (검토 C-5)."""
    released = TODAY - timedelta(days=170)
    assert lifecycle(87_553, released, TODAY) == NEW
    assert is_famous(87_553) is True
    assert thin_new(87_553, released, TODAY) is False        # 근거가 얇지 않다 → 메인 추천 기본 포함
    assert admit(87_553, released, new_only=True, today=TODAY) is True
    assert admit(87_553, released, today=TODAY) is True      # 기본 풀에도 포함 (리뷰 100 이상 신작 정책)


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


def test_upcoming_is_excluded_everywhere():
    """검토 C-3: 출시일이 미래면 new 가 아니라 upcoming. 랭킹·기본 추천·신작 리그 전부 제외."""
    future = TODAY + timedelta(days=10)
    assert lifecycle(50, future, TODAY) == UPCOMING
    assert thin_new(50, future, TODAY) is True
    assert admit(50, future, today=TODAY) is False
    assert admit(50, future, include_new=True, today=TODAY) is False
    assert admit(50, future, new_only=True, today=TODAY) is False
    assert days_since_release(future, TODAY) == -10


def test_gem_factor_only_for_established():
    """R-11 / 검토 C-1: 발굴 보너스는 established 만. 신작·유명작·미출시 0."""
    assert gem_factor(500, TODAY - timedelta(days=400), TODAY) == 1.0
    assert gem_factor(500, TODAY - timedelta(days=40), TODAY) == 0.0        # new
    assert gem_factor(30_000, TODAY - timedelta(days=400), TODAY) == 0.0     # famous
    assert gem_factor(5, TODAY + timedelta(days=3), TODAY) == 0.0            # upcoming


def test_admit_default_vs_include_new_vs_new_only():
    """입장 규칙 한 함수 — 서빙 3경로와 절제 도구가 공유 (검토 E-2)."""
    thin = (18, TODAY - timedelta(days=40))
    fat_new = (5_000, TODAY - timedelta(days=40))
    old = (300, TODAY - timedelta(days=400))
    assert admit(*thin, today=TODAY) is False and admit(*thin, include_new=True, today=TODAY) is True
    assert admit(*fat_new, today=TODAY) is True
    assert admit(*old, today=TODAY) is True and admit(*old, new_only=True, today=TODAY) is False
    assert admit(*thin, new_only=True, today=TODAY) is True


def test_wilson_monotone_in_n():
    assert wilson_lower(0.9, 1000) > wilson_lower(0.9, 30) > wilson_lower(0.9, 3)
    assert wilson_lower(1.0, 3) < 0.5                         # 3/3 도 0.5 를 못 넘는다 — 스테디 진입 불가
    assert wilson_lower(1.0, 3) >= 0.35                       # 신작 노출 기준은 통과
