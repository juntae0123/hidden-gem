"""
new_games.csv에서 아직 metrics가 적재되지 않은 게임만 추려
data/retry_games.csv를 만든다 (배치 straggler 잔여분 재처리용).

사용법:
    python -m embeddings.make_retry_csv
    python -m embeddings.batch_generator --csv data/retry_games.csv --full --yes --sync \
        --model gpt-4o-mini --fewshot data/fewshot/fewshot_examples.jsonl
"""

import csv
import os
from pathlib import Path

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

SRC = PROJECT_ROOT / "data" / "new_games.csv"
DST = PROJECT_ROOT / "data" / "retry_games.csv"


def main() -> None:
    engine = create_engine(os.getenv("DATABASE_URL"))
    rows = list(csv.DictReader(open(SRC, encoding="utf-8")))
    app_ids = [int(r["app_id"]) for r in rows]

    with engine.connect() as conn:
        done = {
            r[0] for r in conn.execute(text(
                "SELECT g.app_id FROM games g "
                "JOIN game_metrics m ON m.game_id = g.id "
                "WHERE g.app_id = ANY(:ids)"
            ), {"ids": app_ids})
        }

    missing = [r for r in rows if int(r["app_id"]) not in done]
    print(f"CSV {len(rows)}개 중 적재 완료 {len(done)}개 / 미적재 {len(missing)}개")

    if not missing:
        print("재처리할 게임 없음")
        return

    with open(DST, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["app_id", "name", "genres", "description"])
        writer.writeheader()
        writer.writerows(missing)
    print(f"저장: {DST} ({len(missing)}행)")


if __name__ == "__main__":
    main()
