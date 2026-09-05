# fastapi_app/services/evidence.py
"""
리뷰 근거 지표 — 서빙 계층용 (embeddings/gem_evidence.py 와 같은 공식, 같은 기본값)
Korean: Wilson 하한 / 로그 무명도 / 발굴 지수 / 초기 속도.

두 곳에 같은 공식이 있는 이유: 배치(embeddings)는 컬럼을 채우고, 서빙(fastapi)은 랭킹을 즉석 계산한다.
기본값을 바꾸면 **양쪽을 같이** 바꾼다 (system_invariants C-2 계열 — 같은 정보가 두 번 정의됨).
"""

import math
from typing import Optional

Z95 = 1.96
OBSCURITY_CAP = 20000
OBSCURITY_EXP = 0.5
OBSCURITY_FLOOR = 50


def wilson_lower(positive_ratio: Optional[float], total: Optional[int], z: float = Z95) -> float:
    if not total or total <= 0 or positive_ratio is None:
        return 0.0
    n = float(total)
    p = min(1.0, max(0.0, float(positive_ratio)))
    d = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / d)


def obscurity(total: Optional[int], cap: int = OBSCURITY_CAP, exp: float = OBSCURITY_EXP,
              floor: int = OBSCURITY_FLOOR) -> float:
    m = max(total or 0, floor)
    if m >= cap:
        return 0.0
    return (1.0 - math.log1p(m) / math.log1p(cap)) ** exp


def gem_evidence(positive_ratio: Optional[float], total: Optional[int]) -> Optional[float]:
    """발굴 지수 0~100. 리뷰 없으면 None (0 이 아니다 — 근거 없음)."""
    if not total or total <= 0 or positive_ratio is None:
        return None
    return round(100.0 * wilson_lower(positive_ratio, total) * obscurity(total), 1)


def velocity_per_day(total: Optional[int], days_since_release: Optional[int], min_days: int = 7) -> Optional[float]:
    """신작 초기 속도: 리뷰/일. 출시 7일 미만은 7일로 나눠 초기 폭발을 완화한다."""
    if days_since_release is None or total is None:
        return None
    return round(total / max(days_since_release, min_days), 3)
