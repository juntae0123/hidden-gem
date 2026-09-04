"""
Hidden Gem - 노출 정책 (is_active 게이트)
========================================
신작(학생 라벨 fewshot_5.4based)을 서비스에 노출할지 결정하는 규칙을 한곳에 둔다.
generate_embeddings(임베딩 직후)와 refresh_reviews(리뷰 수 갱신 직후)가 같은 규칙을 쓴다.

원칙:
    - 데이터는 지우지 않는다. 게이트에 걸린 게임도 metrics/embedding은 그대로 두고
      is_active=FALSE로만 내린다. 리뷰가 붙으면 다시 켠다 (가능성 보존).
    - 노출 조건 = metrics 완비 AND embedding 존재 AND description 비어있지 않음
                  AND review_count >= MIN_REVIEWS_FOR_EXPOSURE
    - 기존 4,190개(교사 라벨)는 수집 당시 인기/리뷰 기준을 이미 거쳤으므로 건드리지 않는다.
    - 소프트웨어 49건(교사 라벨, embedding 없음)도 대상 밖.

MIN_REVIEWS_FOR_EXPOSURE 기본 10:
    Steam이 리뷰 점수(긍정/복합/부정)를 표시하기 시작하는 최소 개수와 같다.
    그 아래는 "히든젬"인지 "미검증"인지 판단할 근거 자체가 없다.
    .env 의 MIN_REVIEWS_FOR_EXPOSURE 로 조정.
"""

import math
import os
from typing import Dict, List, Tuple

from sqlalchemy import text

STUDENT_VERSION = "fewshot_5.4based"
MIN_REVIEWS_FOR_EXPOSURE = int(os.getenv("MIN_REVIEWS_FOR_EXPOSURE", "10"))

# 리뷰 수 분포 구간 (보고용)
REVIEW_BUCKETS: List[Tuple[str, int, int]] = [
    ("0", 0, 0), ("1-2", 1, 2), ("3-9", 3, 9), ("10-49", 10, 49),
    ("50-199", 50, 199), ("200-999", 200, 999), ("1000+", 1000, 10**9),
]


MIN_WILSON_FOR_EXPOSURE = float(os.getenv("MIN_WILSON_FOR_EXPOSURE", "0") or 0)
BADGE_MIN_REVIEWS = int(os.getenv("BADGE_MIN_REVIEWS", "30"))
Z95 = 1.96


def wilson_lower(positive: int, total: int, z: float = Z95) -> float:
    """긍정 비율의 Wilson 하한. 표본이 작으면 자동으로 보수적으로 내려간다."""
    if total <= 0:
        return 0.0
    p = positive / total
    d = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return max(0.0, (centre - margin) / d)


def threshold_report(conn) -> None:
    """후보 임계값별로 몇 건이 통과하는지 실측 표를 뽑는다.

    개수 기준은 '리뷰가 많으면 나쁜 평가라도 통과'하고 '리뷰가 적으면 만점이라도 탈락'한다.
    Wilson 기준은 두 축을 한 번에 본다 — 리뷰 3개 만점(0.438)은 통과, 리뷰 10개 60%(0.313)는 탈락.
    이 표를 보고 노출 기준과 뱃지 기준을 각각 정한다.
    """
    rows = conn.execute(text("""
        SELECT COALESCE(review_count, 0) AS rc, steam_positive_ratio AS ratio
        FROM games WHERE analysis_method = :ver
    """), {"ver": STUDENT_VERSION}).fetchall()
    total = len(rows)
    prepared = [(int(rc), wilson_lower(int(round((ratio or 0) * rc)), int(rc)) if rc else 0.0)
                for rc, ratio in rows]
    print(f"\n신작 {total:,}건 — 임계값별 통과 수")
    print(f"{'기준':>18} {'통과':>8} {'비율':>7}")
    for n in (1, 3, 5, 10, 20, 30, 50, 100):
        k = sum(1 for rc, _ in prepared if rc >= n)
        print(f"{'리뷰 >= ' + str(n):>18} {k:>8,} {k/total*100:>6.1f}%")
    for w in (0.30, 0.35, 0.40, 0.50, 0.60):
        k = sum(1 for _, wl in prepared if wl >= w)
        print(f"{'Wilson >= ' + f'{w:.2f}':>18} {k:>8,} {k/total*100:>6.1f}%")
    print(f"{'리뷰>=3 & W>=0.35':>18} "
          f"{sum(1 for rc, wl in prepared if rc >= 3 and wl >= 0.35):>8,}")
    print(f"{'리뷰>=10 & W>=0.35':>18} "
          f"{sum(1 for rc, wl in prepared if rc >= 10 and wl >= 0.35):>8,}")


def activate_eligible(conn, min_reviews: int = MIN_REVIEWS_FOR_EXPOSURE) -> int:
    """조건을 모두 갖춘 비활성 신작을 켠다. 멱등."""
    result = conn.execute(text("""
        UPDATE games g SET is_active = TRUE, updated_at = NOW()
        FROM game_metrics m
        WHERE m.game_id = g.id
          AND g.analysis_method = :ver
          AND g.is_active = FALSE
          AND g.is_analyzed = TRUE
          AND m.embedding IS NOT NULL
          AND COALESCE(g.description, '') <> ''
          AND COALESCE(g.review_count, 0) >= :min_reviews
    """), {"ver": STUDENT_VERSION, "min_reviews": min_reviews})
    return result.rowcount or 0


def deactivate_below_gate(conn, min_reviews: int = MIN_REVIEWS_FOR_EXPOSURE) -> int:
    """게이트 미달인데 켜져 있는 신작을 내린다 (데이터는 보존). 멱등."""
    result = conn.execute(text("""
        UPDATE games SET is_active = FALSE, updated_at = NOW()
        WHERE analysis_method = :ver
          AND is_active = TRUE
          AND COALESCE(review_count, 0) < :min_reviews
    """), {"ver": STUDENT_VERSION, "min_reviews": min_reviews})
    return result.rowcount or 0


def apply_gate(conn, min_reviews: int = MIN_REVIEWS_FOR_EXPOSURE) -> Dict[str, int]:
    """내리기 → 켜기 순서로 게이트를 전체 적용한다."""
    down = deactivate_below_gate(conn, min_reviews)
    up = activate_eligible(conn, min_reviews)
    return {"deactivated": down, "activated": up}


def review_distribution(conn) -> List[Tuple[str, int, int]]:
    """신작의 리뷰 수 구간별 (구간, 전체, 활성) 건수."""
    rows = conn.execute(text("""
        SELECT COALESCE(review_count, 0) AS rc, is_active
        FROM games WHERE analysis_method = :ver
    """), {"ver": STUDENT_VERSION}).fetchall()
    out = []
    for label, lo, hi in REVIEW_BUCKETS:
        total = sum(1 for rc, _ in rows if lo <= rc <= hi)
        active = sum(1 for rc, a in rows if lo <= rc <= hi and a)
        out.append((label, total, active))
    return out


def print_distribution(conn, min_reviews: int = MIN_REVIEWS_FOR_EXPOSURE) -> None:
    dist = review_distribution(conn)
    total = sum(t for _, t, _ in dist)
    active = sum(a for _, _, a in dist)
    print(f"\n신작 리뷰 수 분포 (게이트 >= {min_reviews}) — 전체 {total:,} / 활성 {active:,}")
    for label, t, a in dist:
        bar = "#" * min(40, round(40 * t / total)) if total else ""
        print(f"   {label:>8} | {t:6,} (활성 {a:5,}) {bar}")
