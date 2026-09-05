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

사용법 (R-3, 2026-09-05 이후 — 별도 컬럼에 쓴다):
    docker compose exec batch python -m embeddings.migrate --file 20260905_gem_evidence_columns.sql
    docker compose exec batch python -m embeddings.gem_evidence                # 미리보기(분포/샘플)
    docker compose exec batch python -m embeddings.gem_evidence --fill --yes   # gem_evidence_score / _status 채움 (전 게임)
    # 서빙 전환: .env GEM_SOURCE=evidence → fastapi 재시작. 되돌리기: GEM_SOURCE=legacy (컬럼은 그대로)

    --fill 은 gem_potential / gem_percentile 을 건드리지 않는다. 상태 분류(생애주기 = fastapi services/lifecycle.py 와 같은 규칙):
        no_reviews    리뷰 0 또는 긍정률 NULL      → score NULL
        insufficient  리뷰 1~2                     → score NULL
        too_new       출시 ≤ LIFECYCLE_NEW_DAYS     → score 계산해 저장하되 서빙은 gem 0 (정보용)
        famous        리뷰 ≥ CAP (무명도 0)          → score 0
        ok            그 외                          → score = 100 × Wilson × 무명도

    (구) --apply 는 gem_percentile 을 덮어쓰는 이전 방식 — 더 이상 권하지 않는다. --legacy-percentile 을 함께 줘야 동작.
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


def obscurity(total: int, cap: int, exp: float, floor: int = 0) -> float:
    """무명도 0~1. 리뷰 cap 이상이면 0.

    floor: 이 리뷰 수 미만은 모두 floor 로 취급한다. 리뷰가 더 적을수록 무명도가
    계속 올라가면 리뷰 2~3개짜리가 상위를 독식하고(실측: 리뷰 2개 100% → 51.8),
    같은 리뷰 수 구간이 동점으로 뭉친다. 하한을 두면 그 구간에서는 Wilson(=표본이
    많을수록 높다)만 남아 "적은 리뷰가 유리"라는 역인센티브가 사라진다.
    """
    m = max(total, floor)
    if m >= cap:
        return 0.0
    return (1.0 - math.log1p(max(m, 0)) / math.log1p(cap)) ** exp


def gem_score(positive: int, total: int, cap: int, exp: float, z: float, floor: int = 0) -> float:
    return 100.0 * wilson_lower(positive, total, z) * obscurity(total, cap, exp, floor)


def fetch_rows() -> List[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT g.app_id, g.name, g.analysis_method, g.is_active, g.release_date,
                   COALESCE(g.review_count, 0) AS reviews,
                   g.steam_positive_ratio AS ratio,
                   m.game_id, m.gem_potential, m.gem_percentile, m.confidence_score AS confidence
            FROM games g JOIN game_metrics m ON m.game_id = g.id
        """)).fetchall()
    return [dict(r._mapping) for r in rows]


def compute(rows: List[dict], cap: int, exp: float, z: float,
            floor: int = 0) -> Tuple[List[dict], List[dict]]:
    scored, no_evidence = [], []
    for r in rows:
        n = int(r["reviews"] or 0)
        ratio = r["ratio"]
        if n <= 0 or ratio is None:
            no_evidence.append(r); continue
        r["gem_evidence"] = gem_score(int(round(ratio * n)), n, cap, exp, z, floor)
        scored.append(r)
    scored.sort(key=lambda x: x["gem_evidence"])
    n = len(scored)
    for i, r in enumerate(scored):
        r["new_pct"] = round(i / (n - 1) * 100) if n > 1 else 50   # PERCENT_RANK 와 동일 정의
    return scored, no_evidence


def gem_bonus(gem: float, reviews: int, confidence: float, with_review_bonus: bool = True) -> float:
    """score_v6 _gem_bonus 재현 (표시 점수에 최대 +5). 전환 전/후 실제 영향을 보기 위함."""
    rb = 0.3 * (1.0 - reviews / 1000.0) if (with_review_bonus and reviews < 1000) else 0.0
    return min((gem / 100.0 * 0.7 + rb) * (confidence if confidence is not None else 0.5), 1.0)


def report(scored: List[dict], no_evidence: List[dict], cap: int, exp: float, z: float,
           floor: int = 0) -> None:
    import statistics as st
    print(f"\n근거 보유 {len(scored):,}건 / 근거 없음(리뷰 0 또는 비율 NULL) {len(no_evidence):,}건")
    print(f"공식: 100 x Wilson하한(z={z}) x 무명도^{exp}   (CAP={cap:,}, 무명도 하한 리뷰 {floor})")
    ne_by = {}
    for r in no_evidence:
        ne_by[r["analysis_method"]] = ne_by.get(r["analysis_method"], 0) + 1
    if ne_by:
        print("   근거 없음 코호트 분포: " + ", ".join(f"{k}={v:,}" for k, v in sorted(ne_by.items())))
        if ne_by.get(TEACHER, 0) > 100:
            print(f"   경고: 교사 코호트 {ne_by[TEACHER]:,}건에 리뷰 데이터가 없다. 이 상태로 적용하면")
            print(f"         기존 카탈로그 전체가 gem 0 이 되고, max_review_count 유명작 필터도 무력하다.")
            print(f"         먼저 실행: refresh_reviews --cohort teacher --new")

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

    # ===== 전환 괴리 (여기가 '적용하면 뭐가 달라지나'의 답) =====
    print("\n" + "=" * 62)
    print("전환 괴리 분석 — 현재 gem_percentile → 근거 지수")
    print("=" * 62)
    have_old = [r for r in scored if r["gem_percentile"] is not None]
    if have_old:
        deltas = [r["gem_evidence"] - float(r["gem_percentile"]) for r in have_old]
        print(f"값 변화 ({len(have_old):,}건): 평균 {st.mean(deltas):+.1f}  중앙 {st.median(deltas):+.1f}  "
              f"|Δ|>20 인 게임 {sum(1 for d in deltas if abs(d) > 20):,}건 "
              f"({sum(1 for d in deltas if abs(d) > 20)/len(deltas)*100:.0f}%)")
        for label, sel in (("교사", TEACHER), ("신작", STUDENT)):
            sub = [r for r in have_old if r["analysis_method"] == sel]
            if sub:
                d = [r["gem_evidence"] - float(r["gem_percentile"]) for r in sub]
                print(f"   {label}: 현재 μ {st.mean([float(r['gem_percentile']) for r in sub]):5.1f} "
                      f"→ 근거 μ {st.mean([r['gem_evidence'] for r in sub]):5.1f}  (Δ {st.mean(d):+.1f})")

        gain = [r for r in have_old if r["gem_evidence"] >= 70 > float(r["gem_percentile"])]
        lose = [r for r in have_old if float(r["gem_percentile"]) >= 70 > r["gem_evidence"]]
        keep = sum(1 for r in have_old if r["gem_evidence"] >= 70 and float(r["gem_percentile"]) >= 70)
        print(f"\n뱃지(70+) 변동: 유지 {keep:,} / 신규 획득 {len(gain):,} / 상실 {len(lose):,}")
        print("   상실 상위 10건 (유명작이 빠지는 게 의도 — 아닌 게 섞였는지 확인)")
        for r in sorted(lose, key=lambda x: -float(x["gem_percentile"]))[:10]:
            print(f"      {float(r['gem_percentile']):5.1f} → {r['gem_evidence']:5.1f}  "
                  f"리뷰 {int(r['reviews']):>7,}  {str(r['name'])[:34]}")
        print("   신규 상위 10건")
        for r in sorted(gain, key=lambda x: -x["gem_evidence"])[:10]:
            print(f"      {float(r['gem_percentile']):5.1f} → {r['gem_evidence']:5.1f}  "
                  f"리뷰 {int(r['reviews']):>7,}  {r['ratio']*100:5.1f}%  {str(r['name'])[:34]}")

        # 실제 추천 점수에 미치는 영향 (+5 보너스 항)
        b_old = [gem_bonus(float(r["gem_percentile"]), int(r["reviews"]), r.get("confidence"), True) * 5
                 for r in have_old]
        b_new = [gem_bonus(r["gem_evidence"], int(r["reviews"]), r.get("confidence"), True) * 5
                 for r in have_old]
        b_new_fix = [gem_bonus(r["gem_evidence"], int(r["reviews"]), r.get("confidence"), False) * 5
                     for r in have_old]
        print(f"\n표시 점수의 gem 보너스(최대 +5) 영향")
        print(f"   현재            μ {st.mean(b_old):.2f}  σ {st.pstdev(b_old):.2f}")
        print(f"   근거 지수 그대로 μ {st.mean(b_new):.2f}  σ {st.pstdev(b_new):.2f}  ← review_bonus 이중 계상 상태")
        print(f"   review_bonus 제거 μ {st.mean(b_new_fix):.2f}  σ {st.pstdev(b_new_fix):.2f}  ← 권장")

    if no_evidence:
        ne_old = [float(r["gem_percentile"]) for r in no_evidence if r["gem_percentile"] is not None]
        print(f"\n근거 없음 {len(no_evidence):,}건 (리뷰 0 또는 비율 NULL)")
        if ne_old:
            print(f"   이들은 --no-evidence 정책에 따름. 현재 gem_percentile μ {st.mean(ne_old):.1f} "
                  f"(keep 이면 LLM 스케일이 그대로 남아 한 컬럼에 두 기준이 섞인다)")
        act = sum(1 for r in no_evidence if r["is_active"])
        print(f"   그중 서비스 노출 중(is_active): {act:,}건 "
              f"{'← 리뷰 게이트가 정상 동작하면 0이어야 한다' if act else '(정상)'}")


# 생애주기 경계 — fastapi/config.py 기본값과 같다. 바꾸면 양쪽을 같이 (.env 로 동일 키 사용)
import os
from datetime import date, datetime
LIFECYCLE_NEW_DAYS = int(os.getenv("LIFECYCLE_NEW_DAYS", "180"))
LIFECYCLE_FAMOUS_REVIEWS = int(os.getenv("LIFECYCLE_FAMOUS_REVIEWS", "20000"))


def classify(r: dict, cap: int, exp: float, z: float, floor: int, today: date = None) -> Tuple[str, float]:
    """(status, score|None). services/evidence.py·lifecycle.py 와 같은 규칙 — 서빙과 배치가 같은 상태를 봐야 한다."""
    today = today or date.today()
    n = int(r["reviews"] or 0)
    ratio = r["ratio"]
    rd = r.get("release_date")
    if isinstance(rd, datetime):
        rd = rd.date()
    if n <= 0 or ratio is None:
        return "no_reviews", None
    if n < 3:
        return "insufficient", None
    if rd is not None and (today - rd).days < 0:
        return "upcoming", None                     # 출시 전 — 근거로 치지 않는다
    score = gem_score(int(round(ratio * n)), n, cap, exp, z, floor)
    if rd is not None and (today - rd).days <= LIFECYCLE_NEW_DAYS:
        return "too_new", round(score, 1)          # 값은 남기되 서빙은 gem 0 (lifecycle.gem_factor)
    if n >= max(cap, LIFECYCLE_FAMOUS_REVIEWS):
        return "famous", 0.0
    return "ok", round(score, 1)


def fill(rows: List[dict], cap: int, exp: float, z: float, floor: int, yes: bool, dry_run: bool) -> int:
    """gem_evidence_score / gem_evidence_status 채움. gem_potential·gem_percentile 무접촉. 멱등."""
    import statistics as st
    classified = [(r, *classify(r, cap, exp, z, floor)) for r in rows]
    by_status = {}
    for _, st_, _ in classified:
        by_status[st_] = by_status.get(st_, 0) + 1
    print(f"\n[--fill] 대상 {len(classified):,}건  상태 분포: " + ", ".join(f"{k}={v:,}" for k, v in sorted(by_status.items())))
    ok_scores = [sc for _, st_, sc in classified if st_ == "ok" and sc is not None]
    if ok_scores:
        qs = st.quantiles(ok_scores, n=10)
        print(f"   ok 점수: n={len(ok_scores):,} μ={st.mean(ok_scores):.1f} 중앙={st.median(ok_scores):.1f} "
              f"p90={qs[8]:.1f} 최대={max(ok_scores):.1f}  (뱃지 히든젬 ≥60: {sum(1 for x in ok_scores if x >= 60):,}건 / 주목 45~60: {sum(1 for x in ok_scores if 45 <= x < 60):,}건)")
    for coh in (TEACHER, STUDENT):
        sub = [sc for r, st_, sc in classified if r["analysis_method"] == coh and st_ == "ok" and sc is not None]
        if sub:
            print(f"   {coh:18} ok {len(sub):,}건 μ={st.mean(sub):.1f} ≥60: {sum(1 for x in sub if x >= 60):,}")
    if dry_run:
        print("dry-run: DB 미변경"); return 0
    if not yes and input("\n채울까요? (y/n): ").strip().lower() != "y":
        print("취소됨 — 아무것도 쓰지 않았습니다"); return 1
    now = datetime.now()
    with engine.begin() as conn:
        for i in range(0, len(classified), 1000):
            chunk = classified[i:i + 1000]
            conn.execute(
                text("""UPDATE game_metrics SET gem_evidence_score = :sc, gem_evidence_status = :st,
                        gem_evidence_updated_at = :now WHERE game_id = :gid"""),
                [{"sc": sc, "st": st_, "now": now, "gid": r["game_id"]} for r, st_, sc in chunk],
            )
    print(f"완료 {len(classified):,}건. gem_potential/gem_percentile/embedding 무접촉.")
    print("다음: .env 에 GEM_SOURCE=evidence → docker compose restart fastapi → rec_snapshot --save s5_gem_evidence → --diff s4_hnsw s5_gem_evidence")
    return 0


def apply(scored: List[dict], yes: bool, write: str) -> int:
    """gem_percentile 컬럼에 기록. write=raw 면 근거 지수 원점수, percentile 이면 백분위.

    기본 raw 를 권한다: 원점수는 절대 기준("인지도 대비 품질" 0~100)이라 뱃지 임계값
    70/80/90 이 의미를 갖고, 코퍼스에 게임이 추가돼도 기존 게임 점수가 흔들리지 않는다.
    백분위는 나쁜 게임이 늘어나면 좋은 게임의 값이 올라가는 상대 지표라 시간에 따라 흔들린다.
    """
    label = "근거 지수 원점수" if write == "raw" else "근거 지수 백분위"
    if not yes and input(f"\n{len(scored):,}건의 gem_percentile 을 {label}로 갱신할까요? (y/n): ").strip().lower() != "y":
        print("취소됨 — 아무것도 쓰지 않았습니다")
        return 1        # 0을 돌려주면 호출부가 성공으로 보고 무근거 게임 0 쓰기를 이어서 실행한다
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
    ap.add_argument("--confidence", choices=["90", "95"], default="95", help="Wilson 하한 신뢰수준")
    ap.add_argument("--obscurity-floor", type=int, default=50,
                    help="이 리뷰 수 미만은 무명도를 동일 취급 (기본 50). 0 이면 하한 없음 — "
                         "리뷰 2~3개짜리가 상위를 독식하므로 권장하지 않음")
    ap.add_argument("--fill", action="store_true",
                    help="R-3: gem_evidence_score/_status 컬럼을 전 게임에 채운다 (권장). 마이그레이션 먼저")
    ap.add_argument("--dry-run", action="store_true", help="--fill 의 분포만 출력, DB 미변경")
    ap.add_argument("--legacy-percentile", action="store_true",
                    help="(구) --apply 가 gem_percentile 을 덮어쓰게 허용. R-3 이후 권하지 않음")
    ap.add_argument("--apply", action="store_true", help="(구) gem_percentile 갱신 — --legacy-percentile 필요")
    ap.add_argument("--write", choices=["raw", "percentile"], default="raw",
                    help="raw(기본): 근거 지수 원점수 0~100 — 절대 기준, 코퍼스 변동에 안 흔들림. "
                         "percentile: 근거 지수의 백분위")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="교사 코호트 리뷰 근거가 없어도 적용 (스케일 혼재 감수)")
    ap.add_argument("--no-evidence", choices=["keep", "zero"], default="zero",
                    help="리뷰 근거가 없는 게임 처리. zero(기본): gem_percentile=0 으로 통일해 "
                         "한 컬럼에 두 기준이 섞이는 것을 막는다(노출 게이트로 어차피 비노출). "
                         "keep: 기존 LLM 기반 값 유지")
    a = ap.parse_args()
    z = Z_90 if a.confidence == "90" else Z_95

    print("=" * 62)
    print("Hidden Gem - 근거 기반 히든젬 지수")
    print("=" * 62)
    rows = fetch_rows()
    if a.fill:
        return fill(rows, a.cap, a.obscurity_exp, z, a.obscurity_floor, a.yes, a.dry_run)
    if a.apply and not a.legacy_percentile:
        print("--apply 는 gem_percentile 을 덮어쓰는 구 방식입니다. R-3 이후엔 --fill 을 쓰세요. (강행: --legacy-percentile)")
        return 2
    rows = [r for r in rows if r.get("gem_potential") is not None]   # 구 경로는 LLM gem 보유 게임만 다뤘다
    scored, none_ = compute(rows, a.cap, a.obscurity_exp, z, a.obscurity_floor)
    report(scored, none_, a.cap, a.obscurity_exp, z, a.obscurity_floor)

    # 교사 코호트에 리뷰 근거가 없으면 적용을 하드 거부한다.
    # 그 상태로 쓰면 한 컬럼에 (교사=LLM 백분위 0~100) + (학생=근거 지수 0~72) + (0) 세 스케일이
    # 섞이고, 뱃지 70+ 는 거의 교사 게임만 뽑게 되어 의도와 정반대가 된다.
    teacher_blind = sum(1 for r in none_ if r["analysis_method"] == TEACHER)
    if a.apply and teacher_blind > 100 and not a.force:
        print(f"\n적용 거부: 교사 코호트 {teacher_blind:,}건에 리뷰 근거가 없습니다.")
        print("   먼저 실행: python -m embeddings.refresh_reviews --cohort teacher --new")
        print("   (그래도 진행하려면 --force — 스케일 혼재를 감수한다는 뜻)")
        return 2

    if a.apply:
        rc = apply(scored, a.yes, a.write)
        if rc == 0 and a.no_evidence == "zero" and none_:
            # 학생 코호트만 0으로. 교사는 리뷰를 아직 조회하지 않은 것일 수 있고,
            # 그 상태로 0을 박으면 기존 카탈로그 전체가 gem 보너스를 잃는다.
            target = [r for r in none_ if r["analysis_method"] == STUDENT]
            skipped = len(none_) - len(target)
            with engine.begin() as conn:
                for i in range(0, len(target), 1000):
                    conn.execute(
                        text("UPDATE game_metrics SET gem_percentile = 0 WHERE game_id = :gid"),
                        [{"gid": r["game_id"]} for r in target[i:i + 1000]],
                    )
            print(f"근거 없음 학생 {len(target):,}건 → gem_percentile = 0 (스케일 혼재 방지)")
            if skipped:
                print(f"   교사 등 {skipped:,}건은 건드리지 않음 — 리뷰 조회 후 재실행할 것")
        return rc
    print("\n미리보기만 수행 (--apply 로 반영). 파라미터를 바꿔가며 분포를 먼저 확인할 것.")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
