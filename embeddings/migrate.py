"""
Hidden Gem - 단순 SQL 마이그레이션 실행기 (Alembic 없이, 멱등 SQL 파일만)
========================================================================
마이그레이션 파일은 embeddings/migrations/ 에 둔다 — batch 컨테이너에는 embeddings/·data/·fastapi_app/ 만 마운트되어
deploy/ 는 보이지 않는다 (첫 실행에서 FileNotFoundError 로 확인).

사용법:
    docker compose exec batch python -m embeddings.migrate --file 20260905_gem_evidence_columns.sql
    docker compose exec batch python -m embeddings.migrate --list
    docker compose exec batch python -m embeddings.migrate --file ... --dry-run     # 실행할 문장만 출력
운영 DB 는 DATABASE_URL 을 운영 값으로 바꿔 같은 명령 (또는 Railway psql 로 파일 직접 실행).
"""
import argparse
import sys
from pathlib import Path

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from embeddings.batch_processor import engine  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="파일명 또는 경로 (embeddings/migrations/ 안에서 먼저 찾는다)")
    ap.add_argument("--list", action="store_true", help="사용 가능한 마이그레이션 파일 목록")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    mig_dir = Path(__file__).parent / "migrations"
    if a.list or not a.file:
        for f in sorted(mig_dir.glob("*.sql")):
            print("  ", f.name)
        return 0
    path = mig_dir / Path(a.file).name
    if not path.exists():
        path = Path(a.file)
    if not path.exists():
        path = PROJECT_ROOT / a.file
    if not path.exists():
        print(f"파일 없음: {a.file}  (--list 로 확인)"); return 1
    stmts = [s.strip() for s in path.read_text(encoding="utf-8").split(";")
             if s.strip() and not all(l.strip().startswith("--") or not l.strip() for l in s.strip().splitlines())]
    print(f"{path.name}: {len(stmts)} 문장")
    for s in stmts:
        clean = "\n".join(l for l in s.splitlines() if not l.strip().startswith("--")).strip()
        print("  ", clean.splitlines()[0][:100])
        if not a.dry_run and clean:
            with engine.begin() as conn:
                conn.execute(text(clean))
    print("완료" if not a.dry_run else "dry-run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
