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
    if age is not None and age <= settings.LIFECYCLE_NEW_DAYS:
        return NEW
    if (review_count or 0) >= settings.LIFECYCLE_FAMOUS_REVIEWS:
        return FAMOUS
    return ESTABLISHED


def thin_new(review_count: Optional[int], release_date, today: Optional[date] = None) -> bool:
    """근거가 얇은 신작 — 메인 추천에서 include_new=False 일 때 빠지는 대상."""
    return (
        lifecycle(review_count, release_date, today) == NEW
        and (review_count or 0) < settings.LIFECYCLE_NEW_MIN_REVIEWS
    )
