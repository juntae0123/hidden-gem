"""
Hidden Gem - Steam 리뷰 수 갱신 + 노출 게이트 적용
=================================================
크롤러는 games 등록 시 review_count=0, steam_positive_ratio=NULL로 넣는다
(appdetails에는 리뷰 집계가 없다). 이 스크립트가 Steam appreviews 요약 API로
실제 리뷰 수/긍정 비율을 채우고, exposure_policy 게이트로 is_active를 정리한다.

대상 선택:
    --new              아직 한 번도 리뷰를 조회하지 않은 신작 (기본)
    --recheck          게이트에 걸려 비활성인 신작 중 마지막 조회가 --stale-days 이전인 것
                       (리뷰가 붙었으면 다시 켜준다 — 가능성 보존)
    --all-new          신작 전부 재조회
    --app-id N ...     특정 게임만

조회 이력은 review_refresh_log(app_id, refreshed_at, total_reviews)에 남긴다.
games 스키마는 건드리지 않는다.

사용법:
    docker compose exec batch python -m embeddings.refresh_reviews --new
    docker compose exec batch python -m embeddings.refresh_reviews --recheck --stale-days 30
    docker compose exec batch python -m embeddings.refresh_reviews --new --dry-run
    docker compose exec batch python -m embeddings.refresh_reviews --gate-only   # 조회 없이 게이트만

속도: 요청 간 1.0s (undocumented 엔드포인트, 429 시 백오프). 500개 ≈ 9분, 8,000개 ≈ 2.5시간.
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from embeddings.steam_crawler import request_with_backoff  # noqa: E402
from embeddings.exposure_policy import (  # noqa: E402
    MIN_REVIEWS_FOR_EXPOSURE, STUDENT_VERSION, apply_gate, print_distribution,
    threshold_report,
)

DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise ValueError(".env에 DATABASE_URL이 없습니다!")
engine = create_engine(DB_URL)

APPREVIEWS_URL = "https://store.steampowered.com/appreviews/{app_id}"
REQUEST_DELAY_SEC = 1.0
LOG_TABLE = "review_refresh_log"


# ============== 스키마 ==============
def ensure_log_table() -> None:
    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {LOG_TABLE} (
                app_id        BIGINT PRIMARY KEY,
                refreshed_at  TIMESTAMP NOT NULL,
                total_reviews INTEGER NOT NULL
            )
        """))


# ============== 대상 ==============
TEACHER_VERSION = "gpt5.4_batch"


def _cohort_clause(cohort: str) -> tuple:
    """대상 코호트. 근거 기반 gem 지수를 쓰려면 교사 4,190개도 리뷰 데이터가 있어야 한다."""
    if cohort == "teacher":
        return "g.analysis_method = :ver", {"ver": TEACHER_VERSION}
    if cohort == "all":
        return "g.analysis_method IN (:ver, :ver2)", {"ver": STUDENT_VERSION, "ver2": TEACHER_VERSION}
    return "g.analysis_method = :ver", {"ver": STUDENT_VERSION}


def fetch_targets(mode: str, stale_days: int, limit: Optional[int],
                  app_ids: Optional[List[int]], cohort: str = "student") -> List[Dict]:
    base, params = _cohort_clause(cohort)
    if app_ids:
        where, params = "g.app_id = ANY(:ids)", {"ids": app_ids}
    elif mode == "all-new":
        where = base
    elif mode == "recheck":
        where = (base + """ AND g.is_active = FALSE AND g.is_analyzed = TRUE
                   AND (l.refreshed_at IS NULL OR l.refreshed_at < NOW() - (:days || ' days')::interval)""")
        params = {**params, "days": str(stale_days)}
    else:  # new
        where = base + " AND l.app_id IS NULL"

    sql = f"""
        SELECT g.app_id, g.name, g.review_count, g.is_active
        FROM games g LEFT JOIN {LOG_TABLE} l ON l.app_id = g.app_id
        WHERE {where}
        ORDER BY g.release_date DESC NULLS LAST, g.app_id
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(text(sql), params).fetchall()]


# ============== Steam ==============
def fetch_review_summary(app_id: int) -> Optional[Dict]:
    """appreviews 요약. 반환: {total, positive, negative} 또는 None(조회 실패)."""
    resp = request_with_backoff(
        APPREVIEWS_URL.format(app_id=app_id),
        {"json": 1, "language": "all", "purchase_type": "all",
         "num_per_page": 0, "filter": "recent"},
        label="appreviews",
    )
    if resp is None:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    if data.get("success") != 1:
        return None
    s = data.get("query_summary") or {}
    total = int(s.get("total_reviews") or 0)
    positive = int(s.get("total_positive") or 0)
    negative = int(s.get("total_negative") or 0)
    return {"total": total, "positive": positive, "negative": negative}


# ============== 갱신 ==============
def update_game(conn, app_id: int, summary: Dict) -> None:
    total = summary["total"]
    ratio = (summary["positive"] / total) if total > 0 else None   # 0.0~1.0, 리뷰 없으면 NULL
    conn.execute(text("""
        UPDATE games SET review_count = :rc, steam_positive_ratio = :ratio, updated_at = NOW()
        WHERE app_id = :app_id
    """), {"rc": total, "ratio": ratio, "app_id": app_id})
    conn.execute(text(f"""
        INSERT INTO {LOG_TABLE} (app_id, refreshed_at, total_reviews)
        VALUES (:app_id, :now, :rc)
        ON CONFLICT (app_id) DO UPDATE
            SET refreshed_at = EXCLUDED.refreshed_at, total_reviews = EXCLUDED.total_reviews
    """), {"app_id": app_id, "now": datetime.now(), "rc": total})


def run(targets: List[Dict], dry_run: bool) -> Dict[str, int]:
    stats = {"fetched": 0, "failed": 0, "with_reviews": 0}
    n = len(targets)
    for i, t in enumerate(targets, 1):
        summary = fetch_review_summary(t["app_id"])
        if summary is None:
            stats["failed"] += 1
            print(f"   [{i:>5}/{n}] {t['app_id']:<9} {str(t['name'])[:30]:32} 조회 실패")
        else:
            stats["fetched"] += 1
            if summary["total"] > 0:
                stats["with_reviews"] += 1
            if not dry_run:
                with engine.begin() as conn:
                    update_game(conn, t["app_id"], summary)
            if i <= 20 or i % 50 == 0 or summary["total"] >= MIN_REVIEWS_FOR_EXPOSURE:
                mark = "게이트 통과" if summary["total"] >= MIN_REVIEWS_FOR_EXPOSURE else ""
                print(f"   [{i:>5}/{n}] {t['app_id']:<9} {str(t['name'])[:30]:32} "
                      f"리뷰 {summary['total']:>6,}  +{summary['positive']:,}/-{summary['negative']:,}  {mark}")
        time.sleep(REQUEST_DELAY_SEC)
    return stats


# ============== main ==============
def main():
    parser = argparse.ArgumentParser(description="Steam 리뷰 수 갱신 + 노출 게이트")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--new", action="store_true", help="미조회 신작 (기본)")
    mode.add_argument("--recheck", action="store_true", help="비활성 신작 재조회 (--stale-days)")
    mode.add_argument("--all-new", action="store_true", help="신작 전부 재조회")
    mode.add_argument("--gate-only", action="store_true", help="조회 없이 게이트만 적용")
    mode.add_argument("--threshold-report", action="store_true",
                      help="조회·변경 없이 후보 임계값별 통과 수만 출력 (기준 결정용)")
    parser.add_argument("--app-id", type=int, nargs="*", help="특정 app_id만")
    parser.add_argument("--stale-days", type=int, default=30)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--min-reviews", type=int, default=MIN_REVIEWS_FOR_EXPOSURE,
                        help=f"노출 게이트 (기본 {MIN_REVIEWS_FOR_EXPOSURE}, .env MIN_REVIEWS_FOR_EXPOSURE)")
    parser.add_argument("--cohort", choices=["student", "teacher", "all"], default="student",
                        help="대상 코호트. teacher/all 은 기존 4,190개(교사)도 리뷰를 채운다 — "
                             "근거 기반 gem 지수를 한 스케일로 쓰려면 필요")
    parser.add_argument("--dry-run", action="store_true", help="DB 미변경")
    parser.add_argument("--no-gate", action="store_true", help="조회만 하고 is_active는 건드리지 않음")
    args = parser.parse_args()

    print("=" * 62)
    print("Hidden Gem - 리뷰 수 갱신 + 노출 게이트")
    print("=" * 62)
    print(f"게이트: review_count >= {args.min_reviews}")
    ensure_log_table()

    if args.threshold_report:
        with engine.connect() as conn:
            threshold_report(conn)
            print_distribution(conn, args.min_reviews)
        return

    if not args.gate_only and not args.threshold_report:
        m = "recheck" if args.recheck else "all-new" if args.all_new else "new"
        targets = fetch_targets(m, args.stale_days, args.limit, args.app_id, args.cohort)
        est_min = len(targets) * (REQUEST_DELAY_SEC + 0.3) / 60
        print(f"대상 ({m}, {args.cohort}): {len(targets):,}건, 예상 {est_min:.0f}분")
        if targets:
            stats = run(targets, args.dry_run)
            print(f"\n조회 {stats['fetched']:,}건 (리뷰 있음 {stats['with_reviews']:,}) / 실패 {stats['failed']}건")

    if args.dry_run:
        print("\nDry-run: DB 미변경")
        return

    with engine.begin() as conn:
        if not args.no_gate and args.cohort != "teacher":
            r = apply_gate(conn, args.min_reviews)
            print(f"\n게이트 적용: 비활성화 {r['deactivated']:,}건, 활성화 {r['activated']:,}건")
        print_distribution(conn, args.min_reviews)


if __name__ == "__main__":
    main()
