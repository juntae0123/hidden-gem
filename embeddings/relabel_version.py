"""
Hidden Gem - extraction_version / analysis_method 재라벨링
=========================================================
batch_processor에 --version을 잘못 주고(또는 생략하고) 적재한 결과를 복구한다.

배경:
    2026-09-03 백필 1회차에서 gpt-5.4-mini 결과 999건이 --version 미지정으로
    교사 라벨(gpt5.4-batch-v1)을 달고 들어갔다. generate_embeddings는
    analysis_method='fewshot_5.4based'만 임베딩 대상으로 보기 때문에
    이 999건은 임베딩도, 활성화도 되지 않은 채 남았다.

동작:
    배치 결과 JSONL의 custom_id에서 app_id를 뽑아, 해당 게임의
    games.analysis_method 와 game_metrics.extraction_version 을 --version 값으로 바꾼다.
    다른 컬럼은 건드리지 않는다. 멱등.

사용법:
    docker compose exec batch python -m embeddings.relabel_version \\
        data/batch_output_20260903_190201.jsonl --yes
    # 기본 --version fewshot_5.4based, --dry-run 으로 미리보기 가능
"""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from embeddings.batch_processor import DATA_DIR, engine, extract_app_id  # noqa: E402


def load_app_ids(result_file: Path) -> list:
    ids = set()
    with open(result_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            app_id = extract_app_id(item.get("custom_id", ""))
            if app_id is not None:
                ids.add(app_id)
    return sorted(ids)


def main():
    parser = argparse.ArgumentParser(description="적재된 배치 결과의 버전 라벨 재지정")
    parser.add_argument("result_file", help="Batch API 결과 JSONL 경로")
    parser.add_argument("--version", default="fewshot_5.4based",
                        help="새 라벨 (기본 fewshot_5.4based)")
    parser.add_argument("--dry-run", action="store_true", help="DB 미변경, 대상 건수만 출력")
    parser.add_argument("--yes", action="store_true", help="확인 프롬프트 생략")
    args = parser.parse_args()

    path = Path(args.result_file)
    if not path.exists():
        path = DATA_DIR / args.result_file
    if not path.exists():
        print(f"파일을 찾을 수 없습니다: {args.result_file}")
        return 1

    app_ids = load_app_ids(path)
    print(f"결과 파일: {path}")
    print(f"대상 app_id: {len(app_ids)}건 → 라벨 '{args.version}'")

    with engine.connect() as conn:
        current = conn.execute(text("""
            SELECT g.analysis_method, m.extraction_version, COUNT(*)
            FROM games g JOIN game_metrics m ON m.game_id = g.id
            WHERE g.app_id = ANY(:ids)
            GROUP BY 1, 2 ORDER BY 3 DESC
        """), {"ids": app_ids}).fetchall()
    print("현재 라벨 분포:")
    for method, ver, n in current:
        print(f"   games.analysis_method={method} / metrics.extraction_version={ver}: {n}건")

    if args.dry_run:
        print("\nDry-run: DB 미변경")
        return 0
    if not args.yes:
        if input("\n재라벨링할까요? (y/n): ").strip().lower() != "y":
            print("취소됨")
            return 0

    with engine.begin() as conn:
        r1 = conn.execute(text("""
            UPDATE games SET analysis_method = :v, updated_at = NOW()
            WHERE app_id = ANY(:ids) AND analysis_method IS DISTINCT FROM :v
        """), {"ids": app_ids, "v": args.version})
        r2 = conn.execute(text("""
            UPDATE game_metrics m SET extraction_version = :v
            FROM games g
            WHERE m.game_id = g.id AND g.app_id = ANY(:ids)
              AND m.extraction_version IS DISTINCT FROM :v
        """), {"ids": app_ids, "v": args.version})

    print(f"\n완료: games {r1.rowcount}건, game_metrics {r2.rowcount}건 재라벨링")
    print("다음: python -m embeddings.generate_embeddings  (임베딩 생성 + 활성화)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
