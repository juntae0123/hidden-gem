"""
Hidden Gem - Weekly New-Game Ingestion Pipeline
================================================
신작 발견 -> few-shot 배치 분석 -> DB 적재 -> 임베딩 -> percentile 재계산을
한 번에 실행하는 오케스트레이터. 각 단계는 기존 스크립트를 그대로 subprocess로
호출하므로, 단계별 스크립트의 계약(입출력 경로)이 바뀌면 여기도 같이 수정한다.

단계:
    1. steam_crawler        최근 N일 신작 -> data/new_games.csv (DB 중복 제거 포함)
    2. batch_generator      new_games.csv + few-shot -> OpenAI Batch 제출/대기/다운로드
    3. batch_processor      결과 JSONL -> game_metrics UPSERT
    4. generate_embeddings  embedding NULL 신작 임베딩 생성
    5. recalc_percentile    gem_percentile 전체 재계산

사용법:
    # 수동 실행 (기본: 최근 7일, 최대 50개)
    python -m embeddings.weekly_pipeline

    # 옵션 지정
    python -m embeddings.weekly_pipeline --days 14 --limit 100 --model gpt-4o-mini

    # 크롤링까지만 (배치 제출 안 함)
    python -m embeddings.weekly_pipeline --crawl-only

스케줄 등록 (Windows):
    PowerShell -ExecutionPolicy Bypass -File scripts\pipeline\setup_weekly_task.ps1

주의:
    - OpenAI Batch는 최대 24시간까지 걸릴 수 있다. --wait로 폴링하며 대기하므로
      스케줄러 실행 시간 제한을 넉넉히 둘 것.
    - few-shot 예시 파일이 없으면 중단한다 (신작 품질 = few-shot 품질).
"""

import os
import sys
import csv
import glob
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"
NEW_GAMES_CSV = DATA_DIR / "new_games.csv"
DEFAULT_FEWSHOT = DATA_DIR / "fewshot" / "fewshot_examples.jsonl"

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    LOG_DIR.mkdir(exist_ok=True)
    with open(LOG_DIR / "weekly_pipeline.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def notify(msg: str) -> None:
    log(msg)
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": f"[weekly-pipeline] {msg}"}, timeout=10)
    except requests.RequestException:
        log("Discord 알림 실패 (무시하고 진행)")


def run_step(name: str, cmd: list[str]) -> None:
    log(f"STEP {name}: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        notify(f"{name} 단계 실패 (exit {result.returncode}) — 파이프라인 중단")
        sys.exit(result.returncode)


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as f:
        return max(0, sum(1 for _ in csv.reader(f)) - 1)  # 헤더 제외


def latest_batch_output() -> Path | None:
    files = sorted(glob.glob(str(DATA_DIR / "batch_output_*.jsonl")), key=os.path.getmtime)
    return Path(files[-1]) if files else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Hidden Gem weekly ingestion pipeline")
    parser.add_argument("--days", type=int, default=7, help="최근 N일 출시작 수집 (기본 7)")
    parser.add_argument("--from", dest="date_from", help="백필 시작일 YYYY-MM-DD (--days 대신)")
    parser.add_argument("--to", dest="date_to", help="백필 종료일 YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=50, help="주당 최대 처리 게임 수 (기본 50)")
    parser.add_argument("--model", default="gpt-4o-mini", help="학생 모델")
    parser.add_argument("--fewshot", default=str(DEFAULT_FEWSHOT), help="few-shot 예시 jsonl")
    parser.add_argument("--fewshot-n", type=int, default=6)
    parser.add_argument("--crawl-only", action="store_true", help="크롤링까지만 실행")
    parser.add_argument("--sync", action="store_true",
                        help="Batch API 대신 동기 호출 (배치 장애 시 폴백, 비용 2배)")
    args = parser.parse_args()

    py = sys.executable
    started = datetime.now()
    period = f"{args.date_from}~{args.date_to or 'today'}" if args.date_from else f"최근 {args.days}일"
    notify(f"주간 파이프라인 시작 ({period}, limit={args.limit}, model={args.model})")

    # few-shot 파일은 배치 품질의 전제조건 - 없으면 시작하지 않는다
    if not args.crawl_only and not Path(args.fewshot).exists():
        notify(f"few-shot 파일 없음: {args.fewshot} — 중단. "
               f"fewshot_sampler.py로 먼저 생성할 것.")
        sys.exit(1)

    # 이전 실행의 CSV가 남아 있으면 "신작 0개"인데도 그걸로 배치가 도는 사고가 남
    if NEW_GAMES_CSV.exists():
        NEW_GAMES_CSV.unlink()

    # 1. 신작 발견 (DB 중복 자동 제외). --from/--to가 있으면 백필 모드.
    crawl_cmd = [py, "-m", "embeddings.steam_crawler", "--limit", str(args.limit)]
    if args.date_from:
        # 크롤러는 --from/--to를 쌍으로 요구 - 종료일 생략 시 오늘로
        date_to = args.date_to or datetime.now().strftime("%Y-%m-%d")
        # 백필: 이미 적재된 최신 게임들이 후보를 소진하므로 후보 풀을 크게 잡는다
        # (중복은 appdetails 호출 없이 걸러져 추가 비용 없음, 페이징만 몇 분 더)
        crawl_cmd += ["--from", args.date_from, "--to", date_to, "--candidates", "20000"]
    else:
        crawl_cmd += ["--days", str(args.days)]
    run_step("crawl", crawl_cmd)

    new_count = count_csv_rows(NEW_GAMES_CSV)
    if new_count == 0:
        notify("신작 없음 — 이번 주는 여기서 종료")
        return
    log(f"신작 {new_count}개 발견")

    if args.crawl_only:
        notify(f"crawl-only 완료: 신작 {new_count}개 (data/new_games.csv)")
        return

    # 2. 배치 생성 + 업로드 + 완료 대기 + 결과 다운로드
    before = latest_batch_output()
    batch_cmd = [py, "-m", "embeddings.batch_generator",
                 "--csv", str(NEW_GAMES_CSV), "--full", "--yes",
                 "--model", args.model,
                 "--fewshot", args.fewshot, "--fewshot-n", str(args.fewshot_n)]
    batch_cmd += ["--sync"] if args.sync else ["--upload", "--wait"]
    run_step("batch", batch_cmd)

    output = latest_batch_output()
    if output is None or output == before:
        notify("배치 결과 파일을 찾지 못함 — batch_processor 수동 실행 필요")
        sys.exit(1)

    # 3. game_metrics UPSERT
    run_step("load", [py, "-m", "embeddings.batch_processor", str(output), "--yes"])

    # 4. 신작 임베딩 생성 (embedding IS NULL 대상)
    run_step("embed", [py, "-m", "embeddings.generate_embeddings"])

    # 5. gem_percentile 재계산 (신작 유입으로 분포가 바뀜)
    run_step("percentile", [py, "-m", "embeddings.recalc_percentile", "--yes"])

    elapsed = datetime.now() - started
    notify(f"주간 파이프라인 완료: 신작 {new_count}개 적재 (소요 {elapsed})")


if __name__ == "__main__":
    main()
