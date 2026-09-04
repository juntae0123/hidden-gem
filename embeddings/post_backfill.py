"""
Hidden Gem - 백필 후처리 원커맨드
=================================
weekly_pipeline --loop 백필이 끝난 뒤 해야 할 일을 한 번에 순서대로 돈다.
각 단계 출력은 콘솔과 data/audit/post_backfill_report.txt 에 함께 남는다.

순서 (빠른 것 → 오래 걸리는 것):
    1. relabel     1회차 결과(--version 미지정으로 교사 라벨이 붙은 999건) 학생 라벨로 복구
    2. embed       위 999건 임베딩 생성 (게이트 때문에 활성화는 아직 0건이 정상)
    3. holdout     교사 데이터 150개 층화 샘플 → 학생 모델 블라인드 분석 → 교사 vs 학생 비교
                   (data/audit/holdout_metrics.csv, holdout_compare.csv)
    4. reviews     신작 전체 Steam 리뷰 수 조회 (~1초/건, 8천 개면 2~3시간) + 노출 게이트 적용
    5. sample      신작 gem 상위/하위/무작위 15건씩 눈검수용 CSV

사용법 (데스크탑, 루프가 끝난 뒤):
    docker compose exec -d batch sh -c "python -m embeddings.post_backfill --wait > /app/data/post_backfill.log 2>&1"
    docker compose exec batch tail -n 30 /app/data/post_backfill.log

    --wait          weekly_pipeline 프로세스가 살아 있으면 끝날 때까지 기다렸다가 시작 (기본은 즉시 중단)
    --skip-reviews  4단계 생략 (리뷰 조회는 나중에 refresh_reviews --new 로 따로)
    --skip-holdout  3단계 생략
    --round1-output 1회차 결과 파일 (기본 data/batch_output_20260903_190201.jsonl)
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
AUDIT_DIR = DATA_DIR / "audit"
REPORT = AUDIT_DIR / "post_backfill_report.txt"
FEWSHOT = DATA_DIR / "fewshot" / "fewshot_examples.jsonl"
PY = sys.executable


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(REPORT, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_step(name: str, cmd: List[str], fatal: bool = True) -> int:
    log(f"STEP {name}: {' '.join(cmd)}")
    with open(REPORT, "a", encoding="utf-8") as f:
        proc = subprocess.Popen(cmd, cwd=PROJECT_ROOT, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for line in proc.stdout:
            sys.stdout.write(line); sys.stdout.flush()
            f.write(line)
        proc.wait()
    if proc.returncode != 0:
        log(f"{name} 실패 (exit {proc.returncode})" + (" — 중단" if fatal else " — 건너뛰고 계속"))
        if fatal:
            sys.exit(proc.returncode)
    return proc.returncode


def pipeline_running() -> bool:
    """weekly_pipeline 프로세스가 살아 있는지 (/proc 스캔, ps 불필요).

    /proc이 없는 환경(Windows 호스트 등)에서는 판정할 수 없다. 애초에 루프는 batch
    컨테이너 안에서 도니 호스트에서는 보이지도 않는다 → False를 돌려주고 경고만 남긴다
    (이 스크립트도 컨테이너 안에서 실행하는 것이 정상 경로).
    """
    proc_dir = Path("/proc")
    if not proc_dir.is_dir():
        log("주의: /proc이 없어 실행 중 프로세스를 확인할 수 없습니다 "
            "(컨테이너 밖에서 실행 중). 루프 종료 여부는 data/backfill.log 의 "
            "'파이프라인 완료' 로그로 확인하세요.")
        return False
    try:
        me = Path("/proc/self").resolve().name
        entries = list(proc_dir.iterdir())
    except OSError:
        return False
    for entry in entries:
        if not entry.name.isdigit() or entry.name == me:
            continue
        try:
            cmd = (entry / "cmdline").read_bytes().replace(b"\0", b" ")
        except OSError:
            continue
        if b"embeddings.weekly_pipeline" in cmd:
            return True
    return False


def newest_batch_output(exclude: set) -> Optional[Path]:
    files = [p for p in DATA_DIR.glob("batch_output_*.jsonl") if p not in exclude]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def main() -> None:
    ap = argparse.ArgumentParser(description="백필 후처리 원커맨드")
    ap.add_argument("--wait", action="store_true", help="weekly_pipeline 종료까지 대기")
    ap.add_argument("--skip-reviews", action="store_true")
    ap.add_argument("--skip-holdout", action="store_true")
    ap.add_argument("--holdout-n", type=int, default=150)
    ap.add_argument("--holdout-mode", choices=["sync", "batch"], default="sync",
                    help="sync(기본): 동기+프롬프트 캐시 — 같은 프롬프트라 결과 동일, 대시보드로 동기 단가 실측 겸용. "
                         "batch: Batch API(캐시 할인 없음)")
    ap.add_argument("--round1-output", default=str(DATA_DIR / "batch_output_20260903_190201.jsonl"))
    args = ap.parse_args()

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now()
    log("=" * 60)
    log("백필 후처리 시작")

    if pipeline_running():
        if not args.wait:
            log("weekly_pipeline이 아직 실행 중 — --wait 를 주면 끝날 때까지 기다립니다. 중단.")
            sys.exit(2)
        log("weekly_pipeline 실행 중 → 종료 대기 (60초 간격 확인)")
        while pipeline_running():
            time.sleep(60)
        log("weekly_pipeline 종료 확인 → 후처리 진행")

    # 1. 1회차 라벨 복구
    r1 = Path(args.round1_output)
    if r1.exists():
        run_step("relabel", [PY, "-m", "embeddings.relabel_version", str(r1), "--yes"])
    else:
        log(f"relabel 건너뜀: {r1} 없음")

    # 2. 임베딩 (복구된 999건)
    run_step("embed", [PY, "-m", "embeddings.generate_embeddings"])

    # 3. 홀드아웃 감사 (교사 vs 학생)
    if not args.skip_holdout:
        run_step("holdout-make", [PY, "-m", "embeddings.audit_student", "--make-holdout", str(args.holdout_n)])
        before = set(DATA_DIR.glob("batch_output_*.jsonl"))
        base = [PY, "-m", "embeddings.batch_generator",
                "--csv", str(AUDIT_DIR / "holdout.csv"), "--full", "--yes",
                "--model", "gpt-5.4-mini", "--fewshot", str(FEWSHOT), "--fewshot-n", "12"]
        if args.holdout_mode == "sync":
            log("holdout: 동기 호출 (few-shot 접두부 캐시 적중 → 대시보드 증가분 = 동기 단가 실측)")
            rc = run_step("holdout-sync", base + ["--sync"], fatal=False)
            out = newest_batch_output(before)
        else:
            rc = run_step("holdout-batch", base + ["--upload", "--wait", "--wait-timeout", "40"], fatal=False)
            out = newest_batch_output(before)
            if rc != 0 or out is None:
                log("배치 경로 실패 → 동기 호출로 재시도")
                run_step("holdout-sync", base + ["--sync"], fatal=False)
                out = newest_batch_output(before)
        if out is None:
            log("holdout 결과 파일 없음 — 감사 건너뜀 (나중에 audit_student --compare 로 수동)")
        else:
            run_step("holdout-compare", [PY, "-m", "embeddings.audit_student", "--compare", str(out)], fatal=False)

    # 4. 리뷰 수 + 게이트
    if args.skip_reviews:
        log("reviews 건너뜀 (--skip-reviews). 나중에: python -m embeddings.refresh_reviews --new")
    else:
        run_step("reviews", [PY, "-m", "embeddings.refresh_reviews", "--new"], fatal=False)

    # 5. 눈검수 샘플
    run_step("sample", [PY, "-m", "embeddings.audit_student", "--new-sample"], fatal=False)

    log(f"백필 후처리 완료 (소요 {datetime.now() - started}) — 보고서: {REPORT}")


if __name__ == "__main__":
    main()
