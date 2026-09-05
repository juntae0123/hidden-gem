"""
prod_sync — 로컬(소스) DB 의 게임 데이터 테이블을 운영(타깃) DB 로 upsert 한다. 삭제 없음, 사용자 테이블 무접촉.

왜 있나 (2026-09-05 심야, decisions R-18):
    운영 DB 는 4,193건(초기 교사 세트)에 review_count 가 전부 비어 있었다(gem_evidence --fill --dry-run: no_reviews=4,193).
    백필 8,653건·리뷰 갱신·review_history·gem 증거 지수는 전부 로컬 DB 에만 있었다 (.env DATABASE_URL 이 로컬 db 를 가리켰음).
    오늘 배포된 코드(생애주기·랭킹·v7)는 그 데이터를 전제로 한다 → 운영 랭킹이 비어 보인다.

무엇을 옮기나 (app_id 기준, 운영의 id 는 보존):
    games              upsert ON CONFLICT (app_id)   — id 제외 전 공통 컬럼
    game_metrics       upsert ON CONFLICT (game_id)  — 소스 game_id 를 app_id 로 풀어 타깃 games.id 로 다시 매핑 (두 DB 의 id 가 다르다)
    review_refresh_log upsert ON CONFLICT (app_id)
    review_history     INSERT ... ON CONFLICT (app_id, refreshed_at) DO NOTHING  (append-only)
    users / user_actions / game_surveys / metric_ratings / django_* / auth_* 는 절대 건드리지 않는다 (운영이 원본).

컬럼은 두 DB 의 information_schema 교집합만 쓴다. 타깃에 없는 컬럼은 경고로 찍고 건너뛴다 (마이그레이션 먼저 하라는 신호).
pgvector 컬럼(embedding)은 소스에서 ::text 로 읽어 타깃에 CAST(:v AS vector) 로 넣는다.

실행 (batch 컨테이너, 소스 = .env DATABASE_URL(로컬), 타깃 = PROD_DATABASE_URL 환경변수):
    export PROD_DB='postgresql://...'                      # 운영 DATABASE_PUBLIC_URL
    docker compose exec -e PROD_DATABASE_URL="$PROD_DB" batch python -m embeddings.prod_sync --dry-run
    docker compose exec -e PROD_DATABASE_URL="$PROD_DB" batch python -m embeddings.prod_sync --yes
    옵션: --tables games,game_metrics (기본 4개 전부)  --batch 300
안전장치: 소스==타깃이면 거부. --yes 없으면 dry-run. 테이블마다 트랜잭션 — 중간 실패 시 그 테이블만 롤백.
끝나면 운영 fastapi 캐시 무효화 (POST /ops/cache/invalidate) — 옛 결과가 최대 6h 남는다.
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_TABLES = ["games", "game_metrics", "review_refresh_log", "review_history"]
# 테이블별 충돌 키와 (타깃에서) 갱신하지 않을 컬럼
CONFLICT_KEY = {
    "games": ("app_id",),
    "game_metrics": ("game_id",),
    "review_refresh_log": ("app_id",),
    "review_history": ("app_id", "refreshed_at"),
}
NEVER_UPDATE = {"games": {"id", "app_id", "created_at"}, "game_metrics": {"game_id"},
                "review_refresh_log": {"app_id"}, "review_history": set()}


def _mask(url: str) -> str:
    import re
    return re.sub(r"://([^:]+):[^@]+@", r"://\1:***@", url or "")


def columns(conn, table: str) -> Dict[str, Tuple[str, str]]:
    rows = conn.execute(text("""
        SELECT column_name, data_type, udt_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = :t ORDER BY ordinal_position
    """), {"t": table}).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def table_exists(conn, table: str) -> bool:
    return conn.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"public.{table}"}).scalar()


def count(conn, table: str) -> int:
    return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()


def plan(src, dst, table: str) -> dict:
    """공통 컬럼·누락 컬럼·벡터 컬럼을 계산한다. 실제 쓰기는 하지 않는다."""
    with src.connect() as s, dst.connect() as d:
        if not table_exists(s, table):
            return {"skip": f"소스에 {table} 없음"}
        if not table_exists(d, table):
            return {"skip": f"타깃에 {table} 없음 — 먼저 만들어야 한다 (refresh_reviews 가 만드는 테이블이면 운영에서 한 번 실행)"}
        sc, dc = columns(s, table), columns(d, table)
        common = [c for c in sc if c in dc]
        missing_in_dst = [c for c in sc if c not in dc]
        # 텍스트로 읽어 타깃 타입으로 CAST 해야 하는 컬럼: pgvector(embedding)·json/jsonb(target_personas 등 — psycopg2 가 dict/list 를 못 넘긴다)
        cast_cols = {c: dc[c][1] for c in common if dc[c][1] in ("vector", "json", "jsonb")}
        key = CONFLICT_KEY[table]
        for k in key:
            if k not in common:
                return {"skip": f"{table}: 충돌 키 {k} 가 양쪽에 없다"}
        return {"common": common, "missing_in_dst": missing_in_dst, "vector": cast_cols,
                "src_count": count(s, table), "dst_count": count(d, table)}


def fetch_rows(src, table: str, cols: List[str], vector_cols: dict, app_id_join: bool):
    """소스에서 행을 읽는다. game_metrics 는 games.app_id 를 함께 가져와 타깃 id 로 다시 매핑한다."""
    sel = ", ".join(f"t.{c}::text AS {c}" if c in vector_cols else f"t.{c}" for c in cols)
    if app_id_join:
        sql = f"SELECT {sel}, g.app_id AS __app_id FROM {table} t JOIN games g ON g.id = t.game_id"
    else:
        sql = f"SELECT {sel} FROM {table} t"
    with src.connect() as s:
        result = s.execution_options(stream_results=True).execute(text(sql))
        while True:
            chunk = result.fetchmany(1000)
            if not chunk:
                break
            for r in chunk:
                yield dict(r._mapping)


def upsert_sql(table: str, cols: List[str], vector_cols: dict) -> str:
    """vector_cols: {컬럼: 타깃 udt_name} — vector / json / jsonb 는 텍스트를 받아 CAST 한다."""
    key = CONFLICT_KEY[table]
    placeholders = ", ".join(f"CAST(:{c} AS {vector_cols[c]})" if c in vector_cols else f":{c}" for c in cols)
    updatable = [c for c in cols if c not in key and c not in NEVER_UPDATE[table]]
    if table == "review_history" or not updatable:
        action = "DO NOTHING"
    else:
        action = "DO UPDATE SET " + ", ".join(f"{c} = EXCLUDED.{c}" for c in updatable)
    return f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) ON CONFLICT ({', '.join(key)}) {action}"


def sync_table(src, dst, table: str, p: dict, batch: int, dry_run: bool) -> int:
    cols = [c for c in p["common"] if not (table == "games" and c == "id")]
    if table == "game_metrics":
        cols = [c for c in cols if c != "game_id"]        # 타깃 id 로 채운다
    sql = upsert_sql(table, (["game_id"] if table == "game_metrics" else []) + cols, p["vector"])
    n = 0
    t0 = time.time()
    with dst.connect() as d:
        tx = None if dry_run else d.begin()          # dry-run 은 트랜잭션을 열지 않는다 (읽기만)
        id_map = {}
        if table == "game_metrics":
            id_map = {r[0]: r[1] for r in d.execute(text("SELECT app_id, id FROM games")).fetchall()}
        buf: List[dict] = []
        unmapped = 0
        try:
            for row in fetch_rows(src, table, cols, p["vector"], app_id_join=(table == "game_metrics")):
                if table == "game_metrics":
                    gid = id_map.get(row.pop("__app_id"))
                    if gid is None:
                        unmapped += 1
                        continue
                    row["game_id"] = gid
                buf.append(row)
                if len(buf) >= batch:
                    if not dry_run:
                        d.execute(text(sql), buf)
                    n += len(buf); buf = []
                    print(f"   {table}: {n:,}행 {'(dry-run 집계)' if dry_run else ''}  {time.time() - t0:.0f}s", end="\r", flush=True)
            if buf:
                if not dry_run:
                    d.execute(text(sql), buf)
                n += len(buf)
            if tx is not None:
                tx.commit()
        except Exception:
            if tx is not None:
                tx.rollback()
                print(f"\n   {table}: 오류 — 이 테이블은 롤백됨 (이전 테이블은 이미 반영됨)")
            raise
        if unmapped:
            print(f"\n   경고: game_metrics {unmapped:,}행은 타깃 games 에 app_id 가 없어 건너뜀 — games 를 먼저 동기화했는지 확인")
    print(f"\n   {table}: {'집계' if dry_run else '완료'} {n:,}행  {time.time() - t0:.0f}s")
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tables", default=",".join(DEFAULT_TABLES))
    ap.add_argument("--batch", type=int, default=300)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true", help="실제로 쓴다. 없으면 dry-run")
    args = ap.parse_args()
    dry_run = args.dry_run or not args.yes

    src_url = os.getenv("DATABASE_URL")
    dst_url = os.getenv("PROD_DATABASE_URL")
    if not src_url or not dst_url:
        sys.exit("DATABASE_URL(소스, .env)·PROD_DATABASE_URL(타깃, -e 로 전달) 둘 다 필요하다")
    if src_url.split("@")[-1] == dst_url.split("@")[-1]:
        sys.exit("소스와 타깃이 같은 DB 다 — 거부")
    print("=" * 62)
    print(f"prod_sync  {'DRY-RUN (쓰지 않음)' if dry_run else '실행'}")
    print(f"  소스: {_mask(src_url)}\n  타깃: {_mask(dst_url)}")
    print("=" * 62)
    src, dst = create_engine(src_url), create_engine(dst_url)

    tables = [t.strip() for t in args.tables.split(",") if t.strip()]
    for t in tables:
        if t not in CONFLICT_KEY:
            sys.exit(f"지원하지 않는 테이블: {t} (허용: {', '.join(CONFLICT_KEY)})")
    if "game_metrics" in tables and "games" in tables and tables.index("games") > tables.index("game_metrics"):
        sys.exit("games 를 game_metrics 보다 먼저 두어야 한다 (id 매핑)")

    total = 0
    for t in tables:
        p = plan(src, dst, t)
        if "skip" in p:
            print(f"\n[{t}] 건너뜀: {p['skip']}")
            continue
        print(f"\n[{t}] 소스 {p['src_count']:,}행 → 타깃 {p['dst_count']:,}행  공통 컬럼 {len(p['common'])}"
              f"{'  벡터: ' + ','.join(sorted(p['vector'])) if p['vector'] else ''}")
        if p["missing_in_dst"]:
            print(f"   경고: 타깃에 없는 컬럼 {p['missing_in_dst']} — 이 컬럼은 옮기지 않는다 (필요하면 마이그레이션 먼저)")
        total += sync_table(src, dst, t, p, args.batch, dry_run)

    print(f"\n{'집계' if dry_run else '완료'} 총 {total:,}행.")
    if dry_run:
        print("실제 반영: --yes")
    else:
        print("다음: 운영 fastapi 캐시 무효화 (POST /api/v1/ops/cache/invalidate, admin) → 운영 /games/ranking?type=steady 확인")


if __name__ == "__main__":
    main()
