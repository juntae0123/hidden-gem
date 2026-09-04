"""
Hidden Gem - OpenAI 실사용량 리포트 (배치 결과 파일 usage 합산)
==============================================================
추정이 아니라 결과 JSONL에 기록된 usage(prompt/completion/cached tokens)를 더한다.
단가를 알면(.env OPENAI_PRICE_INPUT_PER_M / OPENAI_PRICE_OUTPUT_PER_M, 배치 할인 적용가)
달러로 환산하고, 모르면 토큰만 보여준다. 대시보드 일별 금액과 대조해 요청당 실비용을
역산하는 용도(--spent USD).

사용법:
    docker compose exec batch python -m embeddings.usage_report                 # data/ 전체
    docker compose exec batch python -m embeddings.usage_report --since 20260903
    docker compose exec batch python -m embeddings.usage_report --since 20260903 --spent 28.9
        → 그 기간 결제액을 넣으면 요청당/입력·출력 1M당 실단가 역산 + 남은 회차 예측
"""

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
sys.path.insert(0, str(PROJECT_ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass


def scan(files):
    rows, tot = [], {"req": 0, "in": 0, "out": 0, "cached": 0}
    for f in files:
        r = {"file": os.path.basename(f), "req": 0, "in": 0, "out": 0, "cached": 0, "model": ""}
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                body = (o.get("response") or {}).get("body") or {}
                u = body.get("usage") or {}
                if not u:
                    continue
                r["req"] += 1
                r["in"] += u.get("prompt_tokens", 0)
                r["out"] += u.get("completion_tokens", 0)
                r["cached"] += (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
                r["model"] = r["model"] or body.get("model", "")
        rows.append(r)
        for k in tot:
            tot[k] += r[k]
    return rows, tot


def main():
    ap = argparse.ArgumentParser(description="배치 결과 usage 합산 리포트")
    ap.add_argument("--since", help="파일명 타임스탬프 하한 (YYYYMMDD 또는 YYYYMMDD_HHMMSS)")
    ap.add_argument("--glob", default="batch_output_*.jsonl")
    ap.add_argument("--spent", type=float, help="같은 기간 실제 결제액(USD) → 실단가 역산")
    ap.add_argument("--per-round", type=int, default=500, help="남은 회차 예측용 회차 크기")
    ap.add_argument("--rounds-left", type=int, default=0)
    a = ap.parse_args()

    files = sorted(glob.glob(str(DATA_DIR / a.glob)))
    if a.since:
        files = [f for f in files if re.search(r"(\d{8}(?:_\d{6})?)", os.path.basename(f))
                 and re.search(r"(\d{8}(?:_\d{6})?)", os.path.basename(f)).group(1) >= a.since]
    if not files:
        print("대상 파일 없음")
        return
    rows, tot = scan(files)

    print(f"{'파일':40} {'요청':>6} {'입력(M)':>9} {'캐시(M)':>9} {'출력(M)':>8}  모델")
    for r in rows:
        print(f"{r['file']:40} {r['req']:6,} {r['in']/1e6:9.2f} {r['cached']/1e6:9.2f} {r['out']/1e6:8.2f}  {r['model']}")
    print("-" * 100)
    print(f"{'합계':40} {tot['req']:6,} {tot['in']/1e6:9.1f} {tot['cached']/1e6:9.1f} {tot['out']/1e6:8.2f}")
    if tot["req"]:
        print(f"\n요청당 평균: 입력 {tot['in']/tot['req']:,.0f} tok (캐시 {tot['cached']/max(tot['in'],1)*100:.0f}%), "
              f"출력 {tot['out']/tot['req']:,.0f} tok")

    pin, pout = os.getenv("OPENAI_PRICE_INPUT_PER_M"), os.getenv("OPENAI_PRICE_OUTPUT_PER_M")
    if pin and pout:
        cost = tot["in"] / 1e6 * float(pin) + tot["out"] / 1e6 * float(pout)
        print(f"단가(.env) 입력 ${pin}/M 출력 ${pout}/M → 약 ${cost:.2f} (캐시 할인 미반영, 상한)")

    if a.spent and tot["req"]:
        per_req = a.spent / tot["req"]
        print(f"\n결제액 ${a.spent:.2f} / {tot['req']:,}건 = 요청당 ${per_req:.4f}")
        print(f"   → {a.per_round}건 회차당 약 ${per_req * a.per_round:.2f}")
        if a.rounds_left:
            print(f"   → 남은 {a.rounds_left}회차 약 ${per_req * a.per_round * a.rounds_left:.2f}")
        print("   (주의: 결제액에 다른 호출(검색 쿼리 분석, 임베딩, sync 실험)이 섞여 있으면 상한값)")


if __name__ == "__main__":
    main()
