"""
Hidden Gem - 단순 SQL 마이그레이션 실행기 (Alembic 없이, 멱등 SQL 파일만)
========================================================================
사용법:
    docker compose exec batch python -m embeddings.migrate --file deploy/migrations/20260905_gem_evidence_columns.sql
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
    ap.add_argument("--file", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    path = Path(a.file)
    if not path.exists():
        path = PROJECT_ROOT / a.file
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
