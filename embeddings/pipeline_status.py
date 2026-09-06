"""
pipeline_status — 돌고 있는 주간/백필 파이프라인의 현황을 한 화면에 찍는다.

`docker compose exec -d` 로 띄우면 콘솔이 없어 진행이 안 보인다. 로그 파일 + DB + 프로세스 목록을
합쳐서 "지금 어느 단계인지 / 얼마나 들어왔는지 / 돈이 얼마나 나갔는지"를 본다 (2026-09-06).

실행 (batch 컨테이너):
    docker compose exec batch python -m embeddings.pipeline_status              # 대상 = 운영 (파이프라인 기본과 동일)
    docker compose exec batch python -m embeddings.pipeline_status --target local
    docker compose exec batch python -m embeddings.pipeline_status --tail 30    # 로그 더 보기
"""

import argparse
import csv
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
LOG_FILE = ROOT / "logs" / "weekly_pipeline.log"
load_dotenv(ROOT / ".env")

STEP_RE = re.compile(r"^\[(.+?)\] STEP (\S+):")


def running_steps() -> list[str]:
    """컨테이너 안에서 돌고 있는 embeddings.* 프로세스 (psutil 없이 /proc 만으로)."""
    out = []
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            cmd = (p / "cmdline").read_bytes().decode(errors="replace").replace("\0", " ").strip()
            if "embeddings." not in cmd or "pipeline_status" in cmd:
                continue
            started = datetime.fromtimestamp((p / "stat").stat().st_mtime)
            out.append(f"  [{(datetime.now() - started)!s:.7} 경과] {cmd[:110]}")
        except (OSError, ValueError):
            continue
    return out


def last_step(tail: int) -> tuple[str, list[str]]:
    if not LOG_FILE.exists():
        return "로그 없음", []
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    step = "STEP 기록 없음"
    for line in reversed(lines):
        m = STEP_RE.match(line)
        if m:
            try:
                elapsed = datetime.now() - datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                step = f"{m.group(2)} (시작 {m.group(1)}, {int(elapsed.total_seconds() // 60)}분 경과)"
            except ValueError:
                step = m.group(2)
            break
    return step, lines[-tail:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["prod", "local"], default="prod", help="집계 대상 DB (파이프라인 기본은 prod)")
    ap.add_argument("--tail", type=int, default=12, help="로그 마지막 N줄")
    args = ap.parse_args()

    url = os.getenv("PROD_DATABASE_URL") if args.target == "prod" else os.getenv("DATABASE_URL")
    if not url:
        sys.exit("대상 DB URL 이 없다 (.env PROD_DATABASE_URL / DATABASE_URL)")

    print("=" * 78)
    print(f"파이프라인 현황  {datetime.now():%Y-%m-%d %H:%M:%S}   대상 DB: {args.target}")
    print("=" * 78)

    step, tail_lines = last_step(args.tail)
    print(f"\n[단계] {step}")
    procs = running_steps()
    print("\n[실행 중]")
    print("\n".join(procs) if procs else "  없음 — 파이프라인이 끝났거나 죽었다 (로그 마지막 줄 확인)")

    csv_path = DATA_DIR / "new_games.csv"
    if csv_path.exists():
        with open(csv_path, encoding="utf-8") as f:
            n = max(0, sum(1 for _ in csv.reader(f)) - 1)
        print(f"\n[이번 회차 대상] data/new_games.csv {n:,}건 (수정 {datetime.fromtimestamp(csv_path.stat().st_mtime):%H:%M})")
    else:
        print("\n[이번 회차 대상] new_games.csv 없음 (크롤 진행 중이거나 회차 종료)")

    eng = create_engine(url).execution_options(isolation_level="AUTOCOMMIT")
    with eng.connect() as c:
        q = lambda s: c.execute(text(s)).fetchall()
        total, analyzed, pending, active = q("""
            SELECT COUNT(*), COUNT(*) FILTER (WHERE is_analyzed),
                   COUNT(*) FILTER (WHERE analysis_method = 'pending'),
                   COUNT(*) FILTER (WHERE is_active)
            FROM games
        """)[0]
        today_new, today_done = q("""
            SELECT COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE),
                   COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE AND is_analyzed)
            FROM games
        """)[0]
        print(f"\n[DB] 전체 {total:,} / 분석완료 {analyzed:,} / 미분석(pending) {pending:,} / 활성 {active:,}")
        print(f"     오늘 등록 {today_new:,}건 — 그중 분석완료 {today_done:,}건")
        rows = q("""
            SELECT COALESCE(analysis_method, '-') AS m, COUNT(*)
            FROM games WHERE created_at >= CURRENT_DATE GROUP BY 1 ORDER BY 2 DESC
        """)
        if rows:
            print("     오늘 등록 분해: " + ", ".join(f"{m} {n:,}" for m, n in rows))

    print(f"\n[로그 마지막 {args.tail}줄]")
    for line in tail_lines:
        print("  " + line[:160])
    print("\n비용은 추정하지 않는다 — OpenAI 대시보드 Cost 탭이 1차 출처 (회차당 실측 $2.45).")


if __name__ == "__main__":
    main()
