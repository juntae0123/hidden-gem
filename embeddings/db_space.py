"""
db_space — DB 용량 진단 + (옵션) VACUUM. 운영 디스크 꽉 찼을 때 첫 번째로 돌린다.

2026-09-05 심야: prod_sync 로 game_metrics 를 넣다가 운영 Postgres 가 DiskFull (No space left on device).
롤백된 8,100행은 죽은 튜플로 디스크에 남아 있어 VACUUM 으로 재사용 가능 공간으로 돌려야 한다 (파일 크기는 줄지 않음).

실행 (대상 = DATABASE_URL — 운영이면 -e 로 덮어쓴다):
    docker compose exec -e DATABASE_URL="$PROD_DB" batch python -m embeddings.db_space            # 진단만
    docker compose exec -e DATABASE_URL="$PROD_DB" batch python -m embeddings.db_space --vacuum   # + VACUUM games, game_metrics
    docker compose exec batch python -m embeddings.db_space                                        # 로컬 (필요 용량 견적)
"""

import argparse
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).parent.parent / ".env")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vacuum", action="store_true", help="VACUUM (ANALYZE) games, game_metrics — 잠금 없음, 죽은 튜플 재사용")
    ap.add_argument("--limit-gb", type=float, default=None, help="볼륨 한도(GB). 주면 사용률을 찍는다")
    ap.add_argument("--alert-pct", type=float, default=None, help="사용률이 이 값 이상이면 exit 2 (파이프라인 게이트, C-13)")
    args = ap.parse_args()
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL 필요")
    print("대상:", re.sub(r"://([^:]+):[^@]+@", r"://\1:***@", url))
    eng = create_engine(url).execution_options(isolation_level="AUTOCOMMIT")
    with eng.connect() as c:
        q = lambda s, **kw: c.execute(text(s), kw).fetchall()
        size_bytes = q("SELECT pg_database_size(current_database())")[0][0]
        print("DB 전체:", q("SELECT pg_size_pretty(pg_database_size(current_database()))")[0][0])
        over = False
        if args.limit_gb:
            # WAL(기본 최대 1GB)은 pg_database_size 에 안 잡힌다 — 볼륨 사용률은 DB 크기 + 1GB 로 보수적으로 본다 (C-13)
            pct = (size_bytes + 1024 ** 3) / (args.limit_gb * 1024 ** 3) * 100
            print(f"볼륨 사용률(추정, DB+WAL 1GB / 한도 {args.limit_gb:g}GB): {pct:.0f}%")
            over = args.alert_pct is not None and pct >= args.alert_pct
        print("테이블(총 크기, 인덱스 포함):")
        for name, size, tbl, idx in q("""
            SELECT c.relname, pg_size_pretty(pg_total_relation_size(c.oid)),
                   pg_size_pretty(pg_relation_size(c.oid)), pg_size_pretty(pg_indexes_size(c.oid))
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r' AND n.nspname = 'public'
            ORDER BY pg_total_relation_size(c.oid) DESC LIMIT 10"""):
            print(f"   {name:28} {size:>10}  (본체 {tbl}, 인덱스 {idx})")
        print("행/죽은 튜플:")
        for name, live, dead, lv, la in q("""
            SELECT relname, n_live_tup, n_dead_tup, last_vacuum, last_autovacuum
            FROM pg_stat_user_tables WHERE relname IN ('games','game_metrics','review_history','user_actions')
            ORDER BY relname"""):
            print(f"   {name:28} live {live:>8,}  dead {dead:>8,}  vacuum {lv or '-'} / auto {la or '-'}")
        if args.vacuum:
            for t in ("game_metrics", "games"):
                c.execute(text(f"VACUUM (ANALYZE) {t}"))
                print(f"VACUUM {t} 완료")
            for name, live, dead in q("""SELECT relname, n_live_tup, n_dead_tup FROM pg_stat_user_tables
                                          WHERE relname IN ('games','game_metrics') ORDER BY relname"""):
                print(f"   {name:28} live {live:>8,}  dead {dead:>8,}")
            print("주의: VACUUM 은 공간을 '재사용 가능'으로 돌릴 뿐 파일 크기(볼륨 사용량)는 줄이지 않는다. 볼륨이 꽉 찼으면 Railway 에서 볼륨을 늘려야 한다.")
        if over:
            print(f"경고: 사용률이 {args.alert_pct:g}% 이상 — exit 2")
            sys.exit(2)


if __name__ == "__main__":
    main()
