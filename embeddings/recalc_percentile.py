"""
Hidden Gem - gem_percentile Full Recalculation (task 5)
=======================================================
신작 적재로 모수가 바뀌면 gem_percentile을 전체 재계산한다.

공식 (기존 DB에서 역추적해 확정):
    gem_percentile = ROUND(PERCENT_RANK() OVER (ORDER BY gem_potential) * 100)

    실측 대조 (4,190개 기준):
        gem= 5  → PERCENT_RANK  0.02 / CUME_DIST  0.05 / 실제   0.0
        gem= 40 → PERCENT_RANK  0.72 / CUME_DIST  1.55 / 실제   1.0
        gem= 70 → PERCENT_RANK 16.87 / CUME_DIST 31.90 / 실제  17.0
        gem=100 → PERCENT_RANK 99.88 / CUME_DIST 100.0 / 실제 100.0
    → PERCENT_RANK * 100 을 정수 반올림한 값과 일치. CUME_DIST 아님.

모수 규칙 (기존과 동일하게 유지 - 절대 바꾸지 말 것):
    - gem_potential IS NOT NULL 인 모든 행 (4,190건)
    - is_active / is_analyzed 필터 없음
    - 비게임 소프트웨어(3DMark gem=0, VEGAS Pro gem=5)도 모수에 포함

이 컬럼은 Project A의 추천 엔진(score_v6)이 직접 읽는다.
   공식이나 모수를 바꾸면 A의 점수 스케일이 통째로 이동한다.
   재계산을 실행하면 반드시 A에 알리고 score_v6 재검증을 요청할 것.

embedding 컬럼은 건드리지 않는다 (임베딩 파이프라인 전담).

사용법:
    # 변경 예상만 확인 (DB 미변경) - 항상 이것부터
    docker compose exec batch python -m embeddings.recalc_percentile --dry-run

    # 실제 재계산
    docker compose exec batch python -m embeddings.recalc_percentile
"""

import os
import re
import sys
import argparse
from pathlib import Path
from typing import Tuple

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# ============== 경로 / DB ==============
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise ValueError(".env에 DATABASE_URL이 없습니다!")

engine = create_engine(DB_URL)

# Columns this script must never touch.
FORBIDDEN_COLUMNS = {"embedding", "gem_potential"}

# The one and only formula. Verified against the live DB (see docstring).
PERCENTILE_EXPR = "ROUND((PERCENT_RANK() OVER (ORDER BY gem_potential) * 100)::numeric)"


# ============== 현황 ==============
def show_current_state() -> Tuple[int, int]:
    """Report how many rows have gem_potential vs gem_percentile.
    gem_potential 대비 gem_percentile 보유 현황을 출력한다."""
    with engine.connect() as conn:
        n_gem = conn.execute(text(
            "SELECT COUNT(*) FROM game_metrics WHERE gem_potential IS NOT NULL"
        )).scalar()
        n_pct = conn.execute(text(
            "SELECT COUNT(*) FROM game_metrics WHERE gem_percentile IS NOT NULL"
        )).scalar()
        mn, mx, avg = conn.execute(text(
            "SELECT MIN(gem_percentile), MAX(gem_percentile), AVG(gem_percentile) "
            "FROM game_metrics WHERE gem_percentile IS NOT NULL"
        )).one()

    print("현재 상태")
    print(f"   gem_potential 보유: {n_gem:,}건  ← 재계산 모수")
    print(f"   gem_percentile 보유: {n_pct:,}건  (NULL: {n_gem - n_pct:,}건)")
    if mn is not None:
        print(f"   percentile 범위: {mn} ~ {mx} (avg {avg:.2f})")
    return n_gem, n_pct


# ============== 변경 미리보기 ==============
def preview_changes(limit: int = 15) -> int:
    """Show rows whose percentile would move, without writing anything.
    DB를 건드리지 않고 percentile이 이동할 행을 보여준다."""
    sql = text(f"""
        WITH computed AS (
            SELECT game_id,
                   gem_potential,
                   {PERCENTILE_EXPR} AS new_pct
            FROM game_metrics
            WHERE gem_potential IS NOT NULL
        )
        SELECT c.game_id, g.app_id, g.name,
               c.gem_potential, m.gem_percentile AS old_pct, c.new_pct
        FROM computed c
        JOIN game_metrics m ON m.game_id = c.game_id
        JOIN games g ON g.id = c.game_id
        WHERE m.gem_percentile IS DISTINCT FROM c.new_pct
        ORDER BY ABS(COALESCE(m.gem_percentile, -1) - c.new_pct) DESC
        LIMIT :limit
    """)

    count_sql = text(f"""
        WITH computed AS (
            SELECT game_id, {PERCENTILE_EXPR} AS new_pct
            FROM game_metrics WHERE gem_potential IS NOT NULL
        )
        SELECT COUNT(*)
        FROM computed c
        JOIN game_metrics m ON m.game_id = c.game_id
        WHERE m.gem_percentile IS DISTINCT FROM c.new_pct
    """)

    with engine.connect() as conn:
        total_changed = conn.execute(count_sql).scalar()
        rows = conn.execute(sql, {"limit": limit}).fetchall()

    print(f"\n변경 예정: {total_changed:,}건")
    if rows:
        print(f"\n   변동폭 큰 순 상위 {len(rows)}건:")
        print(f"   {'app_id':>9} {'게임':<28} {'gem':>6} {'기존':>7} → {'신규':>6}")
        print("   " + "-" * 66)
        for game_id, app_id, name, gem, old, new in rows:
            old_s = "NULL" if old is None else f"{old:.0f}"
            print(f"   {app_id:>9} {str(name)[:28]:<28} {gem:>6} {old_s:>7} → {new:>6}")

    return total_changed


# ============== 재계산 ==============
def recalculate() -> int:
    """Recompute gem_percentile for every row that has a gem_potential.
    gem_potential이 있는 모든 행의 gem_percentile을 재계산한다.

    Only gem_percentile is written. embedding / gem_potential stay untouched.
    """
    update_sql = text(f"""
        UPDATE game_metrics AS m
        SET gem_percentile = c.new_pct
        FROM (
            SELECT game_id,
                   {PERCENTILE_EXPR} AS new_pct
            FROM game_metrics
            WHERE gem_potential IS NOT NULL
        ) AS c
        WHERE m.game_id = c.game_id
          AND m.gem_percentile IS DISTINCT FROM c.new_pct
    """)

    # hard guard: the statement must not mention forbidden columns as targets
    stmt = str(update_sql)
    assert "SET gem_percentile" in stmt, "SET 대상이 gem_percentile이 아님!"
    for col in FORBIDDEN_COLUMNS:
        assert f"SET {col}" not in stmt and f", {col} =" not in stmt, \
            f"금지 컬럼 {col}이 UPDATE 대상에 포함됨!"

    with engine.begin() as conn:
        result = conn.execute(update_sql)

    return result.rowcount or 0


# ============== 검증 ==============
def verify_after() -> None:
    """Read back distribution and confirm the formula held.
    재계산 결과를 되읽어 분포와 공식 정합성을 확인한다."""
    with engine.connect() as conn:
        n_pct, mn, mx, avg = conn.execute(text("""
            SELECT COUNT(*), MIN(gem_percentile), MAX(gem_percentile), AVG(gem_percentile)
            FROM game_metrics WHERE gem_percentile IS NOT NULL
        """)).one()

        remaining = conn.execute(text("""
            SELECT COUNT(*) FROM game_metrics
            WHERE gem_potential IS NOT NULL AND gem_percentile IS NULL
        """)).scalar()

        # embedding must be untouched
        emb = conn.execute(text("""
            SELECT COUNT(*) FROM game_metrics WHERE embedding IS NOT NULL
        """)).scalar()

        samples = conn.execute(text("""
            SELECT g.app_id, g.name, m.gem_potential, m.gem_percentile, g.analysis_method
            FROM game_metrics m JOIN games g ON g.id = m.game_id
            WHERE m.gem_potential IS NOT NULL
            ORDER BY m.gem_potential DESC LIMIT 3
        """)).fetchall()

    print("\n재계산 후 검증")
    print(f"   percentile 보유: {n_pct:,}건 | 범위 {mn} ~ {mx} (avg {avg:.2f})")
    print(f"   gem_potential 있는데 percentile NULL: {remaining}건 (0이어야 정상)")
    print(f"   embedding 보유(불변 확인): {emb:,}건")
    print("\n   상위 3건:")
    for app_id, name, gem, pct, method in samples:
        print(f"     {app_id:>9} {str(name)[:26]:<28} gem={gem:>5} pct={pct:>5} [{method}]")


# ============== main ==============
def main():
    parser = argparse.ArgumentParser(
        description="gem_percentile 전체 재계산 (task 5)")
    parser.add_argument("--dry-run", action="store_true",
                        help="DB 미변경, 변경 예정 건수만 확인")
    parser.add_argument("--yes", action="store_true", help="확인 프롬프트 생략")
    args = parser.parse_args()

    print("=" * 64)
    print("Hidden Gem - gem_percentile 전체 재계산")
    print("=" * 64)
    masked_db = re.sub(r"://([^:]+):[^@]+@", r"://\1:***@", DB_URL)   # 비밀번호는 로그에 남기지 않는다
    print(f"DB: {masked_db}")
    print("공식: ROUND(PERCENT_RANK() OVER (ORDER BY gem_potential) * 100)")
    print("미변경 컬럼: embedding, gem_potential")
    print("=" * 64)

    show_current_state()
    changed = preview_changes()

    if args.dry_run:
        print("\nDry-run 모드: DB 변경 없음")
        return

    if changed == 0:
        print("\n변경할 행이 없습니다 (이미 최신 상태)")
        return

    print("\n이 컬럼은 Project A의 score_v6가 직접 읽습니다.")
    print("   재계산 후 A에 알리고 점수 스케일 재검증을 요청하세요.")

    if not args.yes:
        confirm = input(f"\n{changed:,}건의 gem_percentile을 갱신할까요? (y/n): ").strip().lower()
        if confirm != "y":
            print("취소됨")
            return

    updated = recalculate()
    print(f"\n갱신 완료: {updated:,}건")

    verify_after()

    print("\n" + "=" * 64)
    print("Project A에 알릴 것:")
    print(f"   - gem_percentile {updated:,}건 갱신됨 (모수 변경)")
    print("   - score_v6 점수 스케일 재검증 필요")
    print("=" * 64)


if __name__ == "__main__":
    main()
