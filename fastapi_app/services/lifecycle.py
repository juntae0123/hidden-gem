# fastapi_app/services/lifecycle.py
"""
게임 생애주기 — 신작 / 정착 / 유명 (docs/lifecycle_split_spec_0905.md, decisions R-11)

취향 일치(Core)는 모든 게임에 같은 척도지만, 발굴·랭킹은 생애주기마다 다른 질문을 던진다.
    new          출시 ≤ LIFECYCLE_NEW_DAYS. 리뷰 수와 무관 — 8만 리뷰짜리 신작도 신작이다
                 (개발자 기준: "메챠 카멜레온이 신작 랭킹 1위가 아니면 말이 안 된다").
    established  그 외, 리뷰 < LIFECYCLE_FAMOUS_REVIEWS — "품질 있는데 묻혔나"가 성립하는 구간
    famous       출시 180일 초과 + 리뷰 ≥ LIFECYCLE_FAMOUS_REVIEWS — 이미 발견됨. 발굴 질문 안 함
release_date 가 없으면 established 로 본다 (크롤러가 못 읽은 구간; 신작일 가능성은 낮다).

메인 추천의 기본 제외는 "신작"이 아니라 **"근거가 얇은 신작"** 이다:
    new AND review_count < LIFECYCLE_NEW_MIN_REVIEWS(100) → include_new=False 일 때 제외.
    리뷰 수천 개짜리 신작은 데이터 부족이 아니므로 기본 포함된다.
"""

from datetime import date, datetime
from typing import Optional

from config import settings

NEW = "new"
ESTABLISHED = "established"
FAMOUS = "famous"
UPCOMING = "upcoming"   # 출시일이 미래 — 예약 페이지. 랭킹·기본 추천에서 제외


def _as_date(d):
    if isinstance(d, datetime):
        return d.date()
    return d


def days_since_release(release_date, today: Optional[date] = None) -> Optional[int]:
    if release_date is None:
        return None
    return ((today or date.today()) - _as_date(release_date)).days


def lifecycle(review_count: Optional[int], release_date, today: Optional[date] = None) -> str:
    age = days_since_release(release_date, today)
    if age is not None and age < 0:
        return UPCOMING
    if age is not None and age <= settings.LIFECYCLE_NEW_DAYS:
        return NEW
    if (review_count or 0) >= settings.LIFECYCLE_FAMOUS_REVIEWS:
        return FAMOUS
    return ESTABLISHED


def thin_new(review_count: Optional[int], release_date, today: Optional[date] = None) -> bool:
    """근거가 얇은 신작 — 메인 추천에서 include_new=False 일 때 빠지는 대상. 미출시(upcoming)도 포함."""
    lc = lifecycle(review_count, release_date, today)
    if lc == UPCOMING:
        return True
    return lc == NEW and (review_count or 0) < settings.LIFECYCLE_NEW_MIN_REVIEWS


def is_famous(review_count: Optional[int]) -> bool:
    """인지도 축 — 생애주기(나이 축)와 별개. 리뷰 8.7만짜리 신작은 new 이면서 famous 다."""
    return (review_count or 0) >= settings.LIFECYCLE_FAMOUS_REVIEWS


def gem_factor(review_count: Optional[int], release_date, today: Optional[date] = None) -> float:
    """서빙 gem 보너스 계수. 발굴 질문은 established 에서만 성립한다 (R-11).
    new: 시간이 없어서 무명 / famous: 이미 발견됨 / upcoming: 근거 없음 → 전부 0."""
    return 1.0 if lifecycle(review_count, release_date, today) == ESTABLISHED else 0.0


def admit(review_count: Optional[int], release_date, include_new: bool = False,
          new_only: bool = False, today: Optional[date] = None) -> bool:
    """추천 후보 입장 규칙 — 3경로와 절제 도구가 **같은 함수**를 쓴다 (서빙/실험 모집단 불일치 방지).
    new_only  : 신작 리그. new 만. (upcoming 제외)
    default   : 근거 얇은 신작(new & 리뷰<100)·upcoming 제외
    include_new: 전부 입장 (upcoming 제외)
    """
    lc = lifecycle(review_count, release_date, today)
    if lc == UPCOMING:
        return False
    if new_only:
        return lc == NEW
    if include_new:
        return True
    return not thin_new(review_count, release_date, today)
