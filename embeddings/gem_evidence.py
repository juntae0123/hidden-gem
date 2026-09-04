"""
Hidden Gem - 근거 기반 히든젬 지수 (Steam 리뷰 실측 → gem_percentile)
=====================================================================
문제: 신작 gem_potential(LLM 추정)은 교사 스케일로 옮길 수 없다. 홀드아웃 150쌍에서
      MAE 19.5 / 스피어만 0.49 / 편향 -18.4 였고, 선형 보정은 기울기 0.33이 나와
      신작 전체를 교사 평균 근처(σ16 → σ5)로 압축하는 퇴화 매핑이 된다.
      근본 원인은 모델이 아니라 검증 데이터다 — 교사가 채점한 4,190개는 인기작 위주라
      gem 40~95(90%가 65+)에 몰려 있고, 무명작 구간에는 교사 기준 자체가 없다.

해결: 뱃지 툴팁이 이미 정의하고 있는 그대로("인지도 대비 품질")를 LLM 추측이 아니라
      Steam 실측으로 계산한다. 두 축 모두 관측 가능하다.

    품질   = 긍정 비율의 Wilson 하한 (표본이 작으면 자동으로 보수적으로 내려간다.
             리뷰 5개 100%가 리뷰 500개 95%보다 높게 잡히는 사고를 구조적으로 막는다)
    무명도 = 1 - log1p(리뷰수)/log1p(CAP)  (로그 스케일, CAP 이상은 0)
    지수   = 100 x 품질 x 무명도^EXP       (EXP<1 이면 리뷰 수 적은 쪽 과대평가 완화)

    두 값의 곱이라 "좋은데 덜 알려진" 게임만 높게 나온다. 유명 명작은 무명도가 0에
    수렴해 자동으로 빠지고(= 히든젬 정체성 필터와 같은 방향), 무명이지만 평가가 나쁜
    게임도 품질에서 걸린다.

교사/학생 구분 없이 같은 공식을 쓰므로 두 코호트가 하나의 스케일에 올라간다.
gem_potential(LLM 원본)은 건드리지 않는다 — 보존하고, 근거가 없는 게임의 폴백으로만 둔다.

사용법:
    docker compose exec batch python -m embeddings.gem_evidence                # 미리보기(분포/샘플)
    docker compose exec batch python -m embeddings.gem_evidence --obscurity-exp 0.5 --cap 20000
    docker compose exec batch python -m embeddings.gem_evidence --apply --yes  # gem_percentile 갱신
    # 되돌리기: python -m embeddings.recalc_percentile --yes  (LLM gem 기준 백분위로 복귀)
"""

import argparse
import math
import sys
from pathlib import Path
from typing import List, Tuple

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from embeddings.batch_processor import engine  # noqa: E402

Z_90, Z_95 = 1.2816, 1.9600
TEACHER, STUDENT = "gpt5.4_batch", "fewshot_5.4based"


def wilson_lower(positive: int, total: int, z: float) -> float:
    """긍정 비율의 Wilson 하한 (0~1). total=0 이면 0 (근거 없음)."""
    if total <= 0:
        return 0.0
    p = positive / total
    d = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return max(0.0, (centre - margin) / d)


def obscurity(total: int, cap: int, exp: float) -> float:
    """무명도 0~1. 리뷰 cap 이상이면 0."""
    if total >= cap:
        return 0.0
    return (1.0 - math.log1p(max(total, 0)) / math.log1p(cap)) ** exp


def gem_score(positive: int, total: int, cap: int, exp: float, z: float) -> float:
    return 100.0 * wilson_lower(positive, total, z) * obscurity(total, cap, exp)


def fetch_rows() -> List[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT g.app_id, g.name, g.analysis_method, g.is_active,
                   COALESCE(g.review_count, 0) AS reviews,
                   g.steam_positive_ratio AS ratio,
                   m.game_id, m.gem_potential, m.gem_percentile
            FROM games g JOIN game_metrics m ON m.game_id = g.id
            WHERE m.gem_potential IS NOT NULL
        """)).fetchall()
    return [dict(r._mapping) for r in rows]


def compute(rows: List[dict], cap: int, exp: float, z: float) -> Tuple[List[dict], List[dict]]:
    scored, no_evidence = [], []
    for r in rows:
        n = int(r["reviews"] or 0)
        ratio = r["ratio"]
        if n <= 0 or ratio is None:
            no_evidence.append(r); continue
        r["gem_evidence"] = gem_score(int(round(ratio * n)), n, cap, exp, z)
        scored.append(r)
    scored.sort(key=lambda x: x["gem_evidence"])
    n = len(scored)
    for i, r in enumerate(scored):
        r["new_pct"] = round(i / (n - 1) * 100) if n > 1 else 50   # PERCENT_RANK 와 동일 정의
    return scored, no_evidence


def report(scored: List[dict], no_evidence: List[dict], cap: int, exp: float, z: float) -> None:
    import statistics as st
    print(f"\n근거 보유 {len(scored):,}건 / 근거 없음(리뷰 0 또는 비율 NULL) {len(no_evidence):,}건")
    print(f"공식: 100 x Wilson하한(z={z}) x 무명도^{exp}   (CAP={cap:,})")

    for label, sel in (("교사(기존 4,190)", TEACHER), ("신작(학생)", STUDENT)):
        sub = [r for r in scored if r["analysis_method"] == sel]
        if not sub:
            continue
        ev = [r["gem_evidence"] for r in sub]
        llm = [r["gem_potential"] for r in sub if r["gem_potential"] is not None]
        print(f"\n[{label}] {len(sub):,}건")
        print(f"   근거 지수  μ {st.mean(ev):5.1f}  중앙 {st.median(ev):5.1f}  "
              f"σ {st.pstdev(ev):4.1f}  범위 {min(ev):.0f}~{max(ev):.0f}")
        print(f"   LLM gem    μ {st.mean(llm):5.1f}  중앙 {st.median(llm):5.1f}")
        edges = [0, 10, 20, 30, 40, 50, 60, 101]
        hist = "  ".join(f"{edges[i]}-{edges[i+1]-1}: {sum(1 for v in ev if edges[i] <= v < edges[i+1])/len(ev)*100:4.1f}%"
                         for i in range(len(edges) - 1))
        print(f"   분포 {hist}")
        if len(llm) > 30:
            pairs = [(r["gem_evidence"], r["gem_potential"]) for r in sub if r["gem_potential"] is not None]
            xs = [p[0] for p in pairs]; ys = [p[1] for p in pairs]
            mx, my = st.mean(xs), st.mean(ys)
            sx, sy = st.pstdev(xs), st.pstdev(ys)
            if sx > 0 and sy > 0:
                cov = sum((a - mx) * (b - my) for a, b in pairs) / len(pairs)
                print(f"   LLM gem 과의 상관 r = {cov / (sx * sy):+.3f}  "
                      f"(낮을수록 LLM이 '인지도 대비 품질'을 못 맞히고 있었다는 뜻)")

    print("\n뱃지 임계값별 대상 수 (뱃지는 70+ = rare, 80+ epic, 90+ legendary)")
    for thr in (70, 80, 90):
        by_pct = sum(1 for r in scored if r["new_pct"] >= thr)
        by_raw = sum(1 for r in scored if r["gem_evidence"] >= thr)
        act = sum(1 for r in scored if r["new_pct"] >= thr and r["is_active"])
        print(f"   {thr}+ : 백분위 기준 {by_pct:,}건(활성 {act:,}) | 원점수 기준 {by_raw:,}건")

    top = sorted(scored, key=lambda r: -r["gem_evidence"])[:15]
    print("\n상위 15건 (근거 지수 / 리뷰 / 긍정률 / LLM gem)")
    for r in top:
        print(f"   {r['gem_evidence']:5.1f}  리뷰 {int(r['reviews']):>6,}  {r['ratio']*100:5.1f}%  "
              f"LLM {r['gem_potential']:>3.0f}  {str(r['name'])[:38]}")
    famous = sorted(scored, key=lambda r: -int(r["reviews"]))[:10]
    print("\n리뷰 최다 10건 (유명작이 자동으로 낮게 나오는지 확인)")
    for r in famous:
        print(f"   {r['gem_evidence']:5.1f}  리뷰 {int(r['reviews']):>7,}  {r['ratio']*100:5.1f}%  "
              f"LLM {r['gem_potential']:>3.0f}  {str(r['name'])[:38]}")


def apply(scored: List[dict], yes: bool, write: str) -> int:
    """gem_percentile 컬럼에 기록. write=raw 면 근거 지수 원점수, percentile 이면 백분위.

    기본 raw 를 권한다: 원점수는 절대 기준("인지도 대비 품질" 0~100)이라 뱃지 임계값
    70/80/90 이 의미를 갖고, 코퍼스에 게임이 추가돼도 기존 게임 점수가 흔들리지 않는다.
    백분위는 나쁜 게임이 늘어나면 좋은 게임의 값이 올라가는 상대 지표라 시간에 따라 흔들린다.
    """
    label = "근거 지수 원점수" if write == "raw" else "근거 지수 백분위"
    if not yes and input(f"\n{len(scored):,}건의 gem_percentile 을 {label}로 갱신할까요? (y/n): ").strip().lower() != "y":
        print("취소됨"); return 0
    key = "gem_evidence" if write == "raw" else "new_pct"
    updated = 0
    with engine.begin() as conn:
        for i in range(0, len(scored), 1000):
            chunk = scored[i:i + 1000]
            conn.execute(
                text("UPDATE game_metrics SET gem_percentile = :pct WHERE game_id = :gid"),
                [{"pct": round(float(r[key]), 1), "gid": r["game_id"]} for r in chunk],
            )
            updated += len(chunk)
            print(f"   {updated:,}/{len(scored):,}")
    print(f"\n갱신 완료 {updated:,}건 ({label}). gem_potential/embedding 무접촉.")
    print("주의: score_v6 의 _gem_bonus 는 gem_percentile 에 review_bonus 를 따로 더한다.")
    print("      근거 지수에 이미 무명도가 들어있어 리뷰 수가 이중 계상되므로, 전환 후에는")
    print("      _gem_bonus 의 review_bonus 항을 제거하거나 축소해야 한다.")
    print("되돌리기: python -m embeddings.recalc_percentile --yes (LLM gem 기준 백분위로 복귀)")
    return 0


def main():
    ap = argparse.ArgumentParser(description="리뷰 실측 기반 히든젬 지수")
    ap.add_argument("--cap", type=int, default=20000, help="이 리뷰 수 이상은 무명도 0 (기본 20000)")
    ap.add_argument("--obscurity-exp", type=float, default=0.5, help="무명도 지수 (기본 0.5)")
    ap.add_argument("--confidence", choices=["90", "95"], default="90", help="Wilson 하한 신뢰수준")
    ap.add_argument("--apply", action="store_true", help="gem_percentile 갱신 (기본은 미리보기)")
    ap.add_argument("--write", choices=["raw", "percentile"], default="raw",
                    help="raw(기본): 근거 지수 원점수 0~100 — 절대 기준, 코퍼스 변동에 안 흔들림. "
                         "percentile: 근거 지수의 백분위")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    z = Z_90 if a.confidence == "90" else Z_95

    print("=" * 62)
    print("Hidden Gem - 근거 기반 히든젬 지수")
    print("=" * 62)
    rows = fetch_rows()
    scored, none_ = compute(rows, a.cap, a.obscurity_exp, z)
    report(scored, none_, a.cap, a.obscurity_exp, z)
    if a.apply:
        return apply(scored, a.yes, a.write)
    print("\n미리보기만 수행 (--apply 로 반영). 파라미터를 바꿔가며 분포를 먼저 확인할 것.")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
