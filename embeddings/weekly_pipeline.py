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
    7'. refresh_reviews --stale --cohort all --no-gate   활성 게임 주간 리뷰 이력 (rising 재료, ~2.5h)
    8. gem_evidence --fill         리뷰 실측 기반 발굴 지수 갱신 (R-3, 서빙 GEM_SOURCE=evidence 의 입력)
    0. db_space --limit-gb          시작 전 DB 용량 점검 — 한도 70% 이상이면 Discord 알림 후 중단 (C-13)

대상 DB (R-18, 2026-09-06): 기본 **운영**(`--target prod`, .env 의 PROD_DATABASE_URL). 지금까지 파이프라인이 로컬 db 에만
쓰고 있어서 운영이 4,193건에 멈춰 있었다. 로컬은 `--target local` 로 명시할 때만. 어느 쪽이든 시작 로그에 대상이 찍힌다.

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
    - 멈추기: data/STOP_BACKFILL 은 --loop(백필)만, data/STOP_PIPELINE 은 주간 실행까지 전부 멈춘다 (컨테이너 접근 불필요).

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


def _mask(url: str) -> str:
    import re
    return re.sub(r"://([^:]+):[^@]+@", r"://\1:***@", url or "")


def select_target_db(target: str) -> str:
    """하위 단계 전부가 읽는 DATABASE_URL 을 대상에 맞게 고정한다 (각 스크립트의 load_dotenv 는 기존 env 를 덮지 않는다)."""
    if target == "prod":
        url = os.getenv("PROD_DATABASE_URL")
        if not url:
            print("PROD_DATABASE_URL 이 없다 — .env 에 운영 DATABASE_PUBLIC_URL 을 넣고 batch 컨테이너를 다시 만들어라 (up -d batch)")
            sys.exit(1)
        os.environ["DATABASE_URL"] = url
    else:
        url = os.getenv("DATABASE_URL")
    return url


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
    """단계 실행. 자식 출력도 로그 파일로 넘긴다 — `exec -d` 로 띄우면 stdout 이 버려져
    STEP 줄만 남고 진행 상황이 안 보이던 것 (2026-09-06)."""
    log(f"STEP {name}: {' '.join(cmd)}")
    LOG_DIR.mkdir(exist_ok=True)
    with open(LOG_DIR / "weekly_pipeline.log", "a", encoding="utf-8") as lf:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, stdout=lf, stderr=subprocess.STDOUT)
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
    parser.add_argument("--audit-n", type=int, default=0,
                        help="루프 종료 후 교사 게임 N개로 품질 드리프트 점검 (0=끔, 권장 30, 약 $0.2)")
    parser.add_argument("--max-loops", type=int, default=60, help="루프 상한 (기본 60)")
    parser.add_argument("--target", choices=["prod", "local"], default="prod",
                        help="대상 DB. 기본 prod(.env PROD_DATABASE_URL). local 은 개발 미러 갱신용")
    parser.add_argument("--volume-gb", type=float, default=float(os.getenv("DB_VOLUME_GB", "5")),
                        help="운영 볼륨 한도(GB) — db_space 사용률 계산용 (기본 5, env DB_VOLUME_GB)")
    parser.add_argument("--skip-space-check", action="store_true")
    parser.add_argument("--skip-history", action="store_true", help="주간 리뷰 이력 갱신(활성 전체, ~2.5h) 생략")
    args = parser.parse_args()

    target_url = select_target_db(args.target)
    log(f"대상 DB [{args.target}]: {_mask(target_url)}")

    py = sys.executable
    started = datetime.now()
    period = f"{args.date_from}~{args.date_to or 'today'}" if args.date_from else f"최근 {args.days}일"
    notify(f"파이프라인 시작 ({period}, limit={args.limit}, model={args.model}"
           + (", loop" if args.loop else "") + ")")

    # few-shot 파일은 배치 품질의 전제조건 - 없으면 시작하지 않는다
    if not args.crawl_only and not Path(args.fewshot).exists():
        notify(f"few-shot 파일 없음: {args.fewshot} — 중단. fewshot_sampler.py로 먼저 생성할 것.")
        sys.exit(1)

    # 0. 용량 점검 (C-13): 한도 70% 이상이면 쓰기 시작 전에 멈춘다
    if not args.skip_space_check:
        r = subprocess.run([py, "-m", "embeddings.db_space", "--limit-gb", str(args.volume_gb), "--alert-pct", "70"],
                           cwd=PROJECT_ROOT)
        if r.returncode == 2:
            notify(f"DB 용량 한도 70% 이상 ({args.target}) — 파이프라인 중단. 볼륨 증설 또는 정리 후 재실행")
            sys.exit(2)
        if r.returncode != 0:
            notify(f"DB 용량 점검 실패 (exit {r.returncode}) — 중단")
            sys.exit(r.returncode)

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

        before_set = set(DATA_DIR.glob("batch_output_*.jsonl"))
        batch_cmd = [py, "-m", "embeddings.batch_generator",
                     "--csv", str(NEW_GAMES_CSV), "--full", "--yes",
                     "--model", args.model,
                     "--fewshot", args.fewshot, "--fewshot-n", str(args.fewshot_n)]
        batch_cmd += ["--sync"] if args.sync else ["--upload", "--wait", "--wait-timeout", str(args.wait_timeout)]
        run_step(f"batch#{i}", batch_cmd)

        # mtime 기준 '가장 최신'을 쓰면 감사/홀드아웃 산출물(교사 게임 결과)을 집어와
        # 교사 데이터를 학생 값으로 덮어쓸 수 있다. 이번 실행에서 새로 생긴 파일만 인정한다.
        new_files = [p for p in DATA_DIR.glob("batch_output_*.jsonl") if p not in before_set]
        output = max(new_files, key=lambda p: p.stat().st_mtime) if new_files else None
        if output is None:
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
        # 킬 스위치 둘: STOP_PIPELINE 은 전부 멈춤, STOP_BACKFILL 은 --loop(백필)만 멈춤.
        # 09-04 비용 사고 때 만든 STOP_BACKFILL 이 주간 1회차까지 막아 운영 갱신이 조용히 0건이 되던 것 (2026-09-06 발견).
        if (DATA_DIR / "STOP_PIPELINE").exists():
            notify("STOP_PIPELINE 파일 감지 — 종료 (재개: data/STOP_PIPELINE 삭제)")
            break
        if args.loop and (DATA_DIR / "STOP_BACKFILL").exists():
            notify("STOP_BACKFILL 파일 감지 — 백필 루프 진행 없이 종료 (재개: 파일 삭제 후 재실행)")
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
        # 주간 리뷰 이력 (R-11 rising 의 재료): 활성 게임 전부, 마지막 조회 7일 초과분. 1.3초/건 → 활성 7천 건이면 ~2.5h.
        # 게이트는 건드리지 않는다(--no-gate) — 노출 규칙 변경은 R-4 가 따로 정한다.
        if not args.skip_history:
            run_step("history", [py, "-m", "embeddings.refresh_reviews", "--stale", "--stale-days", "7",
                                 "--cohort", "all", "--no-gate"])
        # 발굴 지수 갱신 (R-3): 리뷰 수가 바뀐 만큼 Wilson×무명도도 바뀐다. 전 게임 재계산, 수 초.
        run_step("gem", [py, "-m", "embeddings.gem_evidence", "--fill", "--yes"])

    if args.audit_n and processed_total:
        # 품질 드리프트 게이트: 교사 게임 N개를 학생 모델로 다시 매겨 기준선과 대조한다.
        # 학생 모델/few-shot/프롬프트가 조용히 바뀌어 데이터 품질이 내려가는 것을 잡는 장치.
        # N=30 이면 비용 $0.2 수준. 회귀가 감지되면 audit_student 가 exit 3 → 알림 후 중단.
        log(f"품질 드리프트 점검 (교사 {args.audit_n}건 재분석 후 기준선 대조)")
        run_step("audit-make", [py, "-m", "embeddings.audit_student",
                               "--make-holdout", str(args.audit_n)])
        before_audit = latest_batch_output()
        run_step("audit-batch", [py, "-m", "embeddings.batch_generator",
                                 "--csv", str(DATA_DIR / "audit" / "holdout.csv"),
                                 "--full", "--yes", "--model", args.model,
                                 "--fewshot", args.fewshot, "--fewshot-n", str(args.fewshot_n), "--sync"])
        audit_out = latest_batch_output()
        if audit_out and audit_out != before_audit:
            result = subprocess.run([py, "-m", "embeddings.audit_student", "--compare", str(audit_out)],
                                    cwd=PROJECT_ROOT)
            if result.returncode == 3:
                notify("품질 드리프트 감지 — 신작 지표 품질이 기준선보다 악화됨. "
                       "data/audit/quality_last.json 확인 후 few-shot/모델 점검 필요")
            elif result.returncode != 0:
                notify(f"품질 점검 단계 실패 (exit {result.returncode})")
        else:
            notify("품질 점검용 배치 결과 없음 — 점검 생략")

    elapsed = datetime.now() - started
    notify(f"파이프라인 완료: {iterations}회차, 처리 {processed_total}개 (소요 {elapsed})")


if __name__ == "__main__":
    main()
