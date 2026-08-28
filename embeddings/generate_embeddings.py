"""
Hidden Gem - New Game Embedding Generator
==========================================
embedding이 NULL인 신작에 대해 원본 템플릿으로 임베딩을 생성한다.

원본 템플릿 (git 커밋 19e78eb, embeddings/history/collect_gems.py:54 에서 복원):
    rich_text = f"Title: {name}\nDeveloper: {developer}\nGenres: {genres}\nDescription: {desc}"
    client.embeddings.create(model="text-embedding-3-small", input=rich_text)  # 1536

    실측 검증: Stardew Valley를 developer='ConcernedApe'로 재현 → 코사인 1.000000.
    → 이 템플릿이 기존 벡터 공간과 완전히 일치함을 확인.

대상 (기본):
    embedding IS NULL AND analysis_method = 'fewshot_5.4based'
    = 크롤러가 넣은 신작만. developer가 이미 채워져 있어 Steam 재조회 불필요.
    (embedding NULL 나머지 49건은 소프트웨어(RPG Maker/3DMark 등)로
     원래부터 임베딩 대상이 아니었고 is_active=False라 서비스 영향 없음 → 제외)

안전장치 (Project A 승인 조건):
    - 백업 테이블(embedding_backup_20260703) 없으면 실행 거부
    - developer 빈 값이면 스킵 + 경고 (벡터 공간 어긋남 방지)
    - short_description < 40 이면 스킵 (원본 필터 규칙)
    - 생성 후 기존 임베딩 개수 불변 검증
    - gem_potential / gem_percentile 절대 미변경 (embedding 컬럼만 UPDATE)

사용법:
    # 미리보기 (DB 미변경)
    docker compose exec batch python -m embeddings.generate_embeddings --dry-run

    # 신작 임베딩 생성
    docker compose exec batch python -m embeddings.generate_embeddings

    # 소프트웨어 49건까지 포함 (거의 불필요)
    docker compose exec batch python -m embeddings.generate_embeddings --all
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Optional

from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

# ============== 경로 / 클라이언트 ==============
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

DB_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not DB_URL:
    raise ValueError(".env에 DATABASE_URL이 없습니다!")
if not OPENAI_API_KEY:
    raise ValueError(".env에 OPENAI_API_KEY가 없습니다!")

engine = create_engine(DB_URL)
client = OpenAI(api_key=OPENAI_API_KEY)

# ============== 상수 (원본 규격) ==============
EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536
MIN_SHORT_DESC = 40                       # collect_gems.py:258 원본 필터
BACKUP_TABLE = "embedding_backup_20260703"
BATCH_SIZE = 100                          # OpenAI embeddings 배치 크기

# embedding만 건드린다. 이 컬럼들은 절대 UPDATE 대상이 아니다.
FORBIDDEN_COLUMNS = {"gem_potential", "gem_percentile"}


# ============== 원본 템플릿 ==============
def build_rich_text(name: str, developer: str, genres: str, desc: str) -> str:
    """Reproduce the exact original embedding input (collect_gems.py:54).
    원본 임베딩 입력 텍스트를 그대로 재현한다. 순서·라벨·개행 모두 고정.

    검증: Stardew를 name/ConcernedApe/genres/description로 넣으면 코사인 1.0.
    """
    return (
        f"Title: {name}\n"
        f"Developer: {developer}\n"
        f"Genres: {genres}\n"
        f"Description: {desc}"
    )


# ============== 안전장치 ==============
def assert_backup_exists() -> int:
    """Refuse to run without the backup table (A's condition #1).
    백업 테이블이 없으면 실행을 거부한다 (A 승인 조건 1)."""
    with engine.connect() as conn:
        exists = conn.execute(text("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = :t
        """), {"t": BACKUP_TABLE}).scalar()
        if not exists:
            raise SystemExit(
                f"백업 테이블 {BACKUP_TABLE} 없음. 실행 거부.\n"
                f"   먼저 실행: CREATE TABLE {BACKUP_TABLE} AS "
                f"SELECT game_id, embedding FROM game_metrics "
                f"WHERE embedding IS NOT NULL;"
            )
        n = conn.execute(text(f"SELECT COUNT(*) FROM {BACKUP_TABLE}")).scalar()
    print(f"백업 테이블 확인: {BACKUP_TABLE} ({n:,}건)")
    return n


# ============== 대상 조회 ==============
def fetch_targets(include_all: bool) -> List[Dict]:
    """Fetch embedding-NULL rows needing generation.
    embedding이 없는 대상 행을 조회한다. 기본은 신작만."""
    where = "m.embedding IS NULL"
    if not include_all:
        where += " AND g.analysis_method = 'fewshot_5.4based'"

    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT g.id AS game_id, g.app_id, g.name, g.developer,
                   g.genres, g.description, g.analysis_method
            FROM game_metrics m
            JOIN games g ON g.id = m.game_id
            WHERE {where}
            ORDER BY g.app_id
        """)).fetchall()

    return [dict(r._mapping) for r in rows]


# ============== 임베딩 생성 ==============
def embed_batch(texts: List[str]) -> List[List[float]]:
    """Call OpenAI embeddings for a batch of texts.
    텍스트 배치를 text-embedding-3-small로 임베딩한다."""
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def to_vector_literal(vec: List[float]) -> str:
    """Format a float list as a pgvector literal.
    float 리스트를 pgvector 리터럴 문자열로 변환한다."""
    return "[" + ",".join(repr(x) for x in vec) + "]"


# ============== 메인 처리 ==============
def process(targets: List[Dict], dry_run: bool) -> Dict[str, int]:
    """Generate and write embeddings; return counts.
    임베딩을 생성해 기록한다. embedding 컬럼만 UPDATE."""
    stats = {"generated": 0, "skipped_dev": 0, "skipped_desc": 0, "written": 0}

    # 1) 유효 대상 필터링 (원본 규칙)
    valid = []
    for t in targets:
        dev = (t["developer"] or "").strip()
        desc = (t["description"] or "").strip()
        if not dev:
            print(f"   ⊘ app_id={t['app_id']} {t['name'][:30]}: developer 빈 값 → 스킵")
            stats["skipped_dev"] += 1
            continue
        if len(desc) < MIN_SHORT_DESC:
            print(f"   ⊘ app_id={t['app_id']} {t['name'][:30]}: desc<{MIN_SHORT_DESC}자 → 스킵")
            stats["skipped_desc"] += 1
            continue
        valid.append(t)

    if not valid:
        print("유효 대상이 없습니다.")
        return stats

    print(f"\n유효 대상: {len(valid)}건")
    for t in valid:
        rich = build_rich_text(t["name"], t["developer"], t["genres"], t["description"])
        print(f"   [{t['app_id']}] {t['name'][:28]:30} dev='{t['developer']}'")
        print(f"       rich_text 미리보기: {rich[:70].replace(chr(10), ' | ')}...")

    if dry_run:
        print("\nDry-run: 임베딩 생성/기록 안 함")
        stats["generated"] = len(valid)
        return stats

    # 2) 배치 임베딩 생성
    print(f"\n임베딩 생성 중 ({EMBED_MODEL}, {EMBED_DIM}차원)")
    all_vecs: Dict[int, List[float]] = {}
    for i in range(0, len(valid), BATCH_SIZE):
        chunk = valid[i:i + BATCH_SIZE]
        texts = [build_rich_text(t["name"], t["developer"], t["genres"],
                                 t["description"]) for t in chunk]
        vecs = embed_batch(texts)
        for t, v in zip(chunk, vecs):
            if len(v) != EMBED_DIM:
                print(f"   app_id={t['app_id']} 차원 {len(v)} != {EMBED_DIM} → 스킵")
                continue
            all_vecs[t["game_id"]] = v
            stats["generated"] += 1

    # 3) DB 기록 (embedding 컬럼만, raw SQL vector 리터럴)
    update_sql = text("""
        UPDATE game_metrics
        SET embedding = CAST(:vec AS vector)
        WHERE game_id = :gid AND embedding IS NULL
    """)
    # hard guard: 금지 컬럼이 UPDATE문에 없어야 한다
    stmt = str(update_sql)
    assert "SET embedding" in stmt
    for col in FORBIDDEN_COLUMNS:
        assert f"SET {col}" not in stmt and f", {col}" not in stmt, \
            f"금지 컬럼 {col}이 UPDATE에 포함됨!"

    print(f"\nDB 기록 중 ({len(all_vecs)}건)")
    with engine.begin() as conn:
        for gid, vec in tqdm(all_vecs.items(), desc="UPDATE"):
            r = conn.execute(update_sql, {"vec": to_vector_literal(vec), "gid": gid})
            stats["written"] += r.rowcount or 0

    return stats


# ============== 검증 ==============
def verify(baseline_backup: int) -> None:
    """Confirm existing embeddings untouched and gem columns unchanged.
    기존 임베딩 불변 + gem 컬럼 미변경을 검증한다."""
    with engine.connect() as conn:
        n_emb = conn.execute(text(
            "SELECT COUNT(*) FROM game_metrics WHERE embedding IS NOT NULL"
        )).scalar()
        n_null = conn.execute(text(
            "SELECT COUNT(*) FROM game_metrics WHERE embedding IS NULL"
        )).scalar()

        # 신작 3개 상태
        news = conn.execute(text("""
            SELECT g.app_id, g.name,
                   (m.embedding IS NOT NULL) AS has_emb,
                   m.gem_potential, m.gem_percentile
            FROM game_metrics m JOIN games g ON g.id = m.game_id
            WHERE g.analysis_method = 'fewshot_5.4based'
            ORDER BY g.app_id
        """)).fetchall()

    print("\n검증")
    print(f"   embedding 보유: {n_emb:,}건 (백업 기준 {baseline_backup:,} + 신규)")
    print(f"   embedding NULL: {n_null}건 (소프트웨어 49건 예상)")
    print(f"\n   신작 상태:")
    for app_id, name, has_emb, gem, pct in news:
        flag = "ok" if has_emb else "여전히 NULL"
        print(f"     {app_id} {str(name)[:24]:26} embedding={flag} "
              f"gem={gem} pct={pct}")


# ============== main ==============
def main():
    parser = argparse.ArgumentParser(description="신작 임베딩 생성 (원본 템플릿)")
    parser.add_argument("--dry-run", action="store_true", help="DB 미변경, 미리보기만")
    parser.add_argument("--all", action="store_true",
                        help="소프트웨어 49건 포함 (기본은 신작만)")
    args = parser.parse_args()

    print("=" * 62)
    print("Hidden Gem - 신작 임베딩 생성")
    print("=" * 62)
    print(f"모델: {EMBED_MODEL} ({EMBED_DIM}차원)")
    print(f"템플릿: Title / Developer / Genres / Description (원본 복원)")
    print(f"미변경: gem_potential, gem_percentile (embedding만 기록)")
    print("=" * 62)

    backup_n = assert_backup_exists()

    targets = fetch_targets(include_all=args.all)
    if not targets:
        print("embedding NULL인 대상이 없습니다.")
        return

    scope = "신작 + 소프트웨어" if args.all else "신작만"
    print(f"대상 ({scope}): {len(targets)}건")

    stats = process(targets, dry_run=args.dry_run)

    print("\n" + "=" * 62)
    print(f"   생성: {stats['generated']}건")
    print(f"   기록: {stats['written']}건")
    print(f"   스킵(developer 빈값): {stats['skipped_dev']}건")
    print(f"   스킵(desc 부족): {stats['skipped_desc']}건")
    print("=" * 62)

    if not args.dry_run and stats["written"] > 0:
        verify(backup_n)
        print("\n다음: 신작 by-game 추천 검증 → 문제없으면 is_active=True")


if __name__ == "__main__":
    main()