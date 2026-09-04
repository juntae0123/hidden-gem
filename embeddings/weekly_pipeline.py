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
    5. refresh_reviews      Steam 리뷰 수 조회 + 노출 게이트(is_active) 적용
    6. recalc_percentile    gem_percentile 전체 재계산 (루프 끝 1회)
    7. refresh_reviews --recheck  비활성 신작 30일 주기 재평가

사용법:
    # 수동 실행 (기본: 최근 7일, 최대 50개)
    python -m embeddings.weekly_pipeline

    # 옵션 지정
    python -m embeddings.weekly_pipeline --days 14 --limit 100 --model gpt-4o-mini

    # 크롤링까지만 (배치 제출 안 함)
    python -m embeddings.weekly_pipeline --crawl-only

    # 백필 루프: 3월 16일 이후 전량을 500개씩, 신작이 더 없을 때까지 반복
    python -m embeddings.weekly_pipeline --from 2026-03-16 --limit 500 --loop

동작 원칙:
    - 매 회차 크롤 후, DB에 pending(미분석)으로 남은 게임을 CSV에 합쳐 재큐잉한다.
      배치 straggler로 빠진 게임이 다음 회차에 자동 소화되는 구조.
    - 배치는 --wait-timeout(기본 45분) 내 미완료면 취소 후 완료분만 수거한다.
    - 루프 모드에선 percentile 재계산을 마지막에 1회만 돈다.
    - 멈추기: data/STOP_BACKFILL 파일을 만들면 다음 회차 시작 전에 정상 종료한다 (컨테이너 접근 불필요).

스케줄 등록 (Windows):
    PowerShell -ExecutionPolicy Bypass -File scripts/pipeline/setup_weekly_task.ps1

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
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

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


def load_pending_games() -> list[dict]:
    """DB에 등록됐지만 아직 지표가 없는 게임 (크롤러가 등록만 하고 배치에서 빠진 것들)."""
    engine = create_engine(os.getenv("DATABASE_URL"))
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT app_id, name, genres, description
            FROM games
            WHERE is_analyzed = FALSE
              AND analysis_method = 'pending'
              AND COALESCE(description, '') <> ''
            ORDER BY created_at DESC
        """)).mappings().all()
    return [dict(r) for r in rows]


def merge_pending_into_csv(limit: int) -> int:
    """pending 게임을 new_games.csv에 합친다 (중복 제외). 합쳐진 수 반환.

    한도는 신작과 별도로 pending 최대 limit개 - 신작만으로 한도가 차서
    pending이 백필 끝까지 밀리는 일이 없게 한다 (회차 최대 = 신작 limit + pending limit).
    """
    existing: list[dict] = []
    if NEW_GAMES_CSV.exists():
        with open(NEW_GAMES_CSV, encoding="utf-8") as f:
            existing = list(csv.DictReader(f))
    seen = {str(r["app_id"]) for r in existing}

    added = 0
    for g in load_pending_games():
        if added >= limit:
            break
        if str(g["app_id"]) in seen:
            continue
        existing.append({k: g[k] for k in ("app_id", "name", "genres", "description")})
        seen.add(str(g["app_id"]))
        added += 1

    if existing:
        with open(NEW_GAMES_CSV, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["app_id", "name", "genres", "description"])
            w.writeheader()
            w.writerows(existing)
    return added


def latest_batch_output() -> Path | None:
    files = sorted(glob.glob(str(DATA_DIR / "batch_output_*.jsonl")), key=os.path.getmtime)
    return Path(files[-1]) if files else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Hidden Gem weekly ingestion pipeline")
    parser.add_argument("--days", type=int, default=7, help="최근 N일 출시작 수집 (기본 7)")
    parser.add_argument("--from", dest="date_from", help="백필 시작일 YYYY-MM-DD (--days 대신)")
    parser.add_argument("--to", dest="date_to", help="백필 종료일 YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=50, help="주당 최대 처리 게임 수 (기본 50)")
    parser.add_argument("--model", default="gpt-5.4-mini",
                        help="학생 모델 (캘리브레이션 실측: gpt-4o-mini는 gem 분포가 뭉개짐)")
    parser.add_argument("--fewshot", default=str(DEFAULT_FEWSHOT), help="few-shot 예시 jsonl")
    parser.add_argument("--fewshot-n", type=int, default=12)
    parser.add_argument("--crawl-only", action="store_true", help="크롤링까지만 실행")
    parser.add_argument("--sync", action="store_true",
                        help="Batch API 대신 동기 호출 (배치 장애 시 폴백, 비용 2배)")
    parser.add_argument("--wait-timeout", type=int, default=45,
                        help="배치 최대 대기 분. 초과 시 취소 후 완료분만 수거 (기본 45)")
    parser.add_argument("--loop", action="store_true",
                        help="신작/pending이 더 없을 때까지 회차 반복 (백필용)")
    parser.add_argument("--max-loops", type=int, default=60, help="루프 상한 (기본 60)")
    args = parser.parse_args()

    py = sys.executable
    started = datetime.now()
    period = f"{args.date_from}~{args.date_to or 'today'}" if args.date_from else f"최근 {args.days}일"
    notify(f"파이프라인 시작 ({period}, limit={args.limit}, model={args.model}"
           + (", loop" if args.loop else "") + ")")

    # few-shot 파일은 배치 품질의 전제조건 - 없으면 시작하지 않는다
    if not args.crawl_only and not Path(args.fewshot).exists():
        notify(f"few-shot 파일 없음: {args.fewshot} — 중단. fewshot_sampler.py로 먼저 생성할 것.")
        sys.exit(1)

    stuck_state: dict = {}

    def run_iteration(i: int) -> int:
        """1회차: crawl → pending 병합 → batch → load → embed. 처리한 게임 수 반환(0이면 더 없음)."""
        if NEW_GAMES_CSV.exists():
            NEW_GAMES_CSV.unlink()

        crawl_cmd = [py, "-m", "embeddings.steam_crawler", "--limit", str(args.limit)]
        if args.date_from:
            date_to = args.date_to or datetime.now().strftime("%Y-%m-%d")
            crawl_cmd += ["--from", args.date_from, "--to", date_to, "--candidates", "20000"]
        else:
            crawl_cmd += ["--days", str(args.days)]
        run_step(f"crawl#{i}", crawl_cmd)

        crawled = count_csv_rows(NEW_GAMES_CSV)
        pending_added = merge_pending_into_csv(args.limit)
        total = count_csv_rows(NEW_GAMES_CSV)
        log(f"회차 {i}: 신작 {crawled} + pending 재큐잉 {pending_added} = {total}개")
        if total == 0:
            return 0

        # 신작은 없고 pending만 같은 집합으로 반복되면(분석 자체가 계속 실패하는 게임) 무한 루프 차단
        if crawled == 0:
            with open(NEW_GAMES_CSV, encoding="utf-8") as f:
                ids = frozenset(r["app_id"] for r in csv.DictReader(f))
            if ids == stuck_state.get("ids"):
                notify(f"회차 {i}: pending {len(ids)}개가 두 번 연속 미해결 — 수동 확인 필요, 루프 종료")
                return 0
            stuck_state["ids"] = ids
        if args.crawl_only:
            notify(f"crawl-only 완료: {total}개 (data/new_games.csv)")
            return total

        before = latest_batch_output()
        batch_cmd = [py, "-m", "embeddings.batch_generator",
                     "--csv", str(NEW_GAMES_CSV), "--full", "--yes",
                     "--model", args.model,
                     "--fewshot", args.fewshot, "--fewshot-n", str(args.fewshot_n)]
        batch_cmd += ["--sync"] if args.sync else ["--upload", "--wait", "--wait-timeout", str(args.wait_timeout)]
        run_step(f"batch#{i}", batch_cmd)

        output = latest_batch_output()
        if output is None or output == before:
            notify(f"회차 {i}: 배치 결과 파일 없음 — 이번 회차 적재 생략 (pending으로 남아 다음 회차 재시도)")
            return total

        # 학생 모델 결과는 fewshot_5.4based 라벨이어야 embed 단계가 대상으로 잡는다
        run_step(f"load#{i}", [py, "-m", "embeddings.batch_processor", str(output), "--yes",
                               "--version", "fewshot_5.4based"])
        run_step(f"embed#{i}", [py, "-m", "embeddings.generate_embeddings"])
        # 리뷰 수 조회 → 노출 게이트(review_count >= MIN_REVIEWS_FOR_EXPOSURE) 적용.
        # 게이트 미달은 데이터 보존 + is_active=FALSE, 이후 --recheck 로 재평가된다.
        run_step(f"reviews#{i}", [py, "-m", "embeddings.refresh_reviews", "--new"])
        return total

    processed_total = 0
    iterations = 0
    while True:
        if (DATA_DIR / "STOP_BACKFILL").exists():
            notify("STOP_BACKFILL 파일 감지 — 다음 회차 진행 없이 종료 (재개: 파일 삭제 후 재실행)")
            break
        iterations += 1
        n = run_iteration(iterations)
        processed_total += n
        if n == 0:
            notify("신작/pending 없음 — 종료" if iterations == 1 else f"더 처리할 게임 없음 (총 {iterations - 1}회차)")
            break
        if args.crawl_only or not args.loop:
            break
        if iterations >= args.max_loops:
            notify(f"루프 상한 {args.max_loops}회 도달 — 종료 (다시 실행하면 이어서 진행)")
            break
        time.sleep(10)

    if processed_total and not args.crawl_only:
        # gem_percentile은 전체 분포 재계산이라 루프 끝에 1회
        run_step("percentile", [py, "-m", "embeddings.recalc_percentile", "--yes"])

    if not args.crawl_only:
        # 게이트에 걸려 비활성인 신작 중 30일 넘게 재조회 안 한 것 — 리뷰가 붙었으면 다시 켠다
        run_step("recheck", [py, "-m", "embeddings.refresh_reviews", "--recheck", "--stale-days", "30"])

    elapsed = datetime.now() - started
    notify(f"파이프라인 완료: {iterations}회차, 처리 {processed_total}개 (소요 {elapsed})")


if __name__ == "__main__":
    main()
