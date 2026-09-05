"""
절제(ablation) 재랭킹 — 전체 후보 풀에서 점수 구성요소의 순위 영향력을 잰다
====================================================================
스냅샷(상위 10)으로는 순위 영향력을 잴 수 없다(선택 절단). 이 도구는 활성 풀 전체를
채점하고, 구성요소를 하나씩 끄거나 v7 로 바꾼 뒤 원래 순위와 비교한다.

측정치 (시나리오별):
    spearman   전체 풀 순위 상관 (1.0 = 동일 순위)
    kendall    scipy 가 있으면 함께 (없으면 '-')
    rbo@20     상위권 가중 겹침 (p=0.9). 1.0 = 상위 20 동일
    top20 유지  원래 상위 20 중 남은 수
    교사비율    상위 20 중 교사 코호트(gpt5.4_batch) 비율 — 유명작 편향 지표
    리뷰중앙    상위 20 리뷰 수 중앙값
    σ(항)      전체 풀에서 그 항의 표준편차 (상위 N 의 σ 와 비교하라)

후보 풀 (--pool) — **실제 서빙과 같은 입장 규칙(lifecycle.admit)을 쓴다.** 필터를 여기 복제하지 않는다 (검토 E-2).
    default     기본 by-preference 와 동일: 근거 얇은 신작(new & 리뷰<100)·미출시 제외   ← v7 전환 판단은 이걸로
    include-new 신작 포함 토글 ON
    new-only    신작 리그
    hidden-gem  default + max_review_count 20000 (히든젬 화면)
    all         활성·분석 전체 (이전 회차 30/31 과 비교용)

실행 (fastapi 컨테이너 — 의존성·DB 접속이 여기 있다):
    docker compose exec fastapi python -m scripts.ablation --pool default
    docker compose exec fastapi python -m scripts.ablation --pool new-only --top 20 --json /app/data/audit/ablation/x.json
"""

import argparse
import asyncio
import json
import math
import os
import sys
from typing import Dict, List, Optional

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select                          # noqa: E402
from sqlalchemy.orm import selectinload                # noqa: E402

from database import AsyncSessionLocal                 # noqa: E402
from models.game import Game, NUMERIC_METRIC_FIELDS    # noqa: E402
from services.recommender import resolve_null          # noqa: E402
from services.score_v6 import (                        # noqa: E402
    compute_core_score, compute_xfactor_score, compute_gem_bonus, SCORE_MAX,
)
from services.score_v7 import compute_core_v7          # noqa: E402
from services.lifecycle import admit, gem_factor, lifecycle as game_lifecycle   # noqa: E402

try:
    from scipy.stats import kendalltau, spearmanr      # type: ignore
    HAVE_SCIPY = True
except Exception:                                      # pragma: no cover
    HAVE_SCIPY = False

TEACHER = "gpt5.4_batch"

PRESETS: Dict[str, Dict[str, float]] = {
    "힐링": {"cozy_factor": 9, "time_pressure": 1, "reflex_demand": 2, "melancholy": 3},
    "전략": {"strategic_depth": 9, "management_complexity": 8, "reflex_demand": 2},
    "서사": {"narrative_depth": 9, "lore_richness": 8, "choice_consequence": 8},
    "액션": {"reflex_demand": 9, "action_pacing": 9, "time_pressure": 7},
    "공포": {"horror_factor": 9, "melancholy": 6, "cozy_factor": 0},
}


# ---------- 순위 통계 ----------

def ranks(scores: np.ndarray) -> np.ndarray:
    """내림차순 순위(1 = 최고). 동점은 평균 순위."""
    order = np.argsort(-scores, kind="mergesort")
    r = np.empty(len(scores), dtype=float)
    r[order] = np.arange(1, len(scores) + 1)
    # 동점 평균
    s_sorted = scores[order]
    i = 0
    while i < len(s_sorted):
        j = i
        while j + 1 < len(s_sorted) and s_sorted[j + 1] == s_sorted[i]:
            j += 1
        if j > i:
            r[order[i:j + 1]] = (i + 1 + j + 1) / 2.0
        i = j + 1
    return r


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    if HAVE_SCIPY:
        return float(spearmanr(a, b).correlation)
    ra, rb = ranks(a), ranks(b)
    ra -= ra.mean(); rb -= rb.mean()
    d = math.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    return float((ra * rb).sum() / d) if d else float("nan")


def kendall(a: np.ndarray, b: np.ndarray) -> Optional[float]:
    if not HAVE_SCIPY:
        return None
    return float(kendalltau(a, b).correlation)


def rbo(list_a: List[int], list_b: List[int], p: float = 0.9) -> float:
    """Rank-biased overlap (Webber 2010), 유한 깊이 근사."""
    depth = min(len(list_a), len(list_b))
    if depth == 0:
        return 0.0
    sa, sb = set(), set()
    total = 0.0
    for d in range(1, depth + 1):
        sa.add(list_a[d - 1]); sb.add(list_b[d - 1])
        total += (p ** (d - 1)) * len(sa & sb) / d
    # 유한 깊이 정규화: 동일 리스트가 정확히 1.0 이 되게 (미정규화 최대는 1 − p^depth = 0.878@20)
    return (1 - p) * total / (1 - p ** depth)


def top_ids(scores: np.ndarray, ids: List[int], n: int) -> List[int]:
    order = np.argsort(-scores, kind="mergesort")[:n]
    return [ids[i] for i in order]


# ---------- 채점 ----------

POOLS = ("default", "include-new", "new-only", "hidden-gem", "all")


def _admit(g: Game, pool: str) -> bool:
    if pool == "all":
        return True
    if pool == "hidden-gem" and (g.review_count or 0) > 20000:
        return False
    return admit(
        g.review_count, g.release_date,
        include_new=(pool == "include-new"),
        new_only=(pool == "new-only"),
    )


async def load_pool(pool_mode: str = "default"):
    async with AsyncSessionLocal() as db:
        stmt = (
            select(Game)
            .options(selectinload(Game.metrics))
            .where(Game.is_active == True)    # noqa: E712
            .where(Game.is_analyzed == True)  # noqa: E712
        )
        games = (await db.execute(stmt)).scalars().all()
    pool = []
    for g in games:
        if not g.metrics:
            continue
        if not _admit(g, pool_mode):
            continue
        pool.append({
            "app_id": g.app_id,
            "name": g.name or "",
            "cohort": g.analysis_method or "",
            "genre": (g.genres or "").split(",")[0].strip() if g.genres else "",
            "review_count": g.review_count,
            "positive": g.steam_positive_ratio,
            "gem_pct": g.metrics.gem_percentile,
            "gem_factor": gem_factor(g.review_count, g.release_date),   # 서빙과 동일: established 만 gem
            "lifecycle": game_lifecycle(g.review_count, g.release_date),
            "metrics": {f: resolve_null(f, getattr(g.metrics, f, None)) for f in NUMERIC_METRIC_FIELDS},
        })
    return pool


def score_components(pool, prefs):
    n = len(pool)
    core6 = np.zeros(n); xf = np.zeros(n); gem = np.zeros(n); core7 = np.zeros(n)
    for i, g in enumerate(pool):
        c, _ = compute_core_score(g["metrics"], prefs, g["genre"])
        x, _ = compute_xfactor_score(g["metrics"], g["genre"])
        gm, _ = compute_gem_bonus(g["review_count"], g["positive"], g["gem_pct"])
        gm *= g["gem_factor"]                                   # 서빙과 동일 (R-11)
        c7, _ = compute_core_v7(g["metrics"], prefs)
        core6[i], xf[i], gem[i], core7[i] = c, x, gm, c7
    return core6, xf, gem, core7


def summarize(name, base, variant, pool, ids, top_n):
    ta = top_ids(base, ids, top_n); tb = top_ids(variant, ids, top_n)
    keep = len(set(ta) & set(tb))
    idx = {a: i for i, a in enumerate(ids)}
    tb_rows = [pool[idx[a]] for a in tb]
    teacher = sum(1 for r in tb_rows if r["cohort"] == TEACHER) / max(len(tb_rows), 1)
    revs = sorted(r["review_count"] or 0 for r in tb_rows)
    med = revs[len(revs) // 2] if revs else 0
    k = kendall(base, variant)
    top_vals = sorted((float(variant[idx[a]]) for a in tb), reverse=True)
    return {
        "variant": name,
        "top_range": round(top_vals[0] - top_vals[-1], 1) if top_vals else 0.0,   # 상위 N 안의 점수 폭
        "spearman": round(spearman(base, variant), 3),
        "kendall": None if k is None else round(k, 3),
        "rbo20": round(rbo(ta, tb), 3),
        "top_keep": keep,
        "teacher_share": round(teacher, 2),
        "review_median": med,
        "sigma": round(float(np.std(variant)), 2),
        "top": [(pool[idx[a]]["name"][:22], round(float(variant[idx[a]]), 1)) for a in tb[:5]],
    }


async def main():
    ap = argparse.ArgumentParser(description="점수 구성요소 절제 재랭킹")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--json", metavar="PATH", help="결과 JSON 저장 경로")
    ap.add_argument("--prefs", metavar="JSON", help='추가 시나리오 {"이름": {지표: 값}}')
    ap.add_argument("--pool", choices=POOLS, default="default",
                    help="후보 풀 — 서빙 입장 규칙과 동일 (default 가 실제 기본 API). all 은 이전 회차 비교용")
    args = ap.parse_args()

    scenarios = dict(PRESETS)
    if args.prefs:
        scenarios.update(json.loads(args.prefs))

    pool = await load_pool(args.pool)
    ids = [g["app_id"] for g in pool]
    n = len(pool)
    teacher_n = sum(1 for g in pool if g["cohort"] == TEACHER)
    lc_counts = {}
    for g in pool:
        lc_counts[g["lifecycle"]] = lc_counts.get(g["lifecycle"], 0) + 1
    print(f"후보 풀 [{args.pool}] {n:,}건 (교사 {teacher_n:,} / 학생 {n - teacher_n:,})  생애주기 {lc_counts}  "
          f"scipy={'있음' if HAVE_SCIPY else '없음(kendall 생략)'}")
    print(f"교사 비율 기준선 {teacher_n / max(n, 1):.2f} — 상위 N 의 '교사비율'은 이 값과 비교해 읽는다\n")

    out = {"pool_mode": args.pool, "pool": n, "teacher": teacher_n, "lifecycle": lc_counts, "top_n": args.top, "scenarios": {}}
    for sc, prefs in scenarios.items():
        core6, xf, gem, core7 = score_components(pool, prefs)
        v6 = np.minimum(core6 + xf + gem, SCORE_MAX)
        variants = {
            "v6 (기준)":            v6,
            "v6 − X-Factor":        np.minimum(core6 + gem, SCORE_MAX),
            "v6 − Gem":             np.minimum(core6 + xf, SCORE_MAX),
            "v6 Core 만":           core6,
            "v6 X-Factor 만":       xf,
            "v7 (Core93 + Gem)":    np.minimum(core7 + gem, SCORE_MAX),
            "v7 Core 만":           core7,
        }
        rows = [summarize(k, v6, v, pool, ids, args.top) for k, v in variants.items()]
        out["scenarios"][sc] = {
            "prefs": prefs,
            "sigma_full_pool": {"core6": round(float(np.std(core6)), 2), "xfactor": round(float(np.std(xf)), 2),
                                "gem": round(float(np.std(gem)), 2), "core7": round(float(np.std(core7)), 2)},
            "xfactor_below_15_6_pct": round(float((xf < 15.6).mean() * 100), 1),
            "xfactor_saturated_pct": round(float((xf >= 18.0).mean() * 100), 1),
            "rows": rows,
        }
        s = out["scenarios"][sc]
        print(f"=== {sc} {prefs}")
        print(f"    전체 풀 σ: Core6 {s['sigma_full_pool']['core6']} / X-F {s['sigma_full_pool']['xfactor']} / "
              f"Gem {s['sigma_full_pool']['gem']} / Core7 {s['sigma_full_pool']['core7']}   "
              f"X-F<15.6: {s['xfactor_below_15_6_pct']}%  X-F=18: {s['xfactor_saturated_pct']}%")
        print(f"    {'변형':22} {'spearman':>9} {'kendall':>8} {'rbo@N':>7} {'유지':>5} {'교사비율':>7} {'리뷰중앙':>8} {'σ':>6} {'상위N폭':>7}")
        for r in rows:
            k = "-" if r["kendall"] is None else f"{r['kendall']:.3f}"
            print(f"    {r['variant']:22} {r['spearman']:>9.3f} {k:>8} {r['rbo20']:>7.3f} {r['top_keep']:>3}/{args.top:<2} "
                  f"{r['teacher_share']:>7.2f} {r['review_median']:>8} {r['sigma']:>6.2f} {r['top_range']:>7.1f}")
        print(f"    v7 상위 5: {out['scenarios'][sc]['rows'][5]['top']}")
        print()

    print("[읽는 법]")
    print("  · 'v6 − X-Factor' 의 spearman 이 0.98+ 이고 rbo 가 0.9+ 면 X-Factor 는 상수였다. 낮으면 게이트였다.")
    print("    (어느 쪽이든 제거 결론은 같다 — 질의 정보가 없다. 이 수치는 '얼마나 바뀔지'의 예측이다)")
    print("  · 'v7' 의 교사비율·리뷰중앙이 v6 보다 낮아지면 '유명작 상위 금지' 의도 방향이다.")
    print("  · X-F<15.6 비율이 전체 풀에서 몇 % 인지가 '선택 게이트 가설'의 직접 판정이다.")
    print("  · '상위N폭'(상위 N 점수 범위): 가우시안은 거리 0 근처가 평평해 좁게 나온다(v7 1.7~2.8 실측).")
    print("    폭을 넓히려면 τ 를 *내리거나* 커널을 바꿔야 하고, 그러면 어긋남 페널티가 커진다. 참고치일 뿐 판정 기준 아님.")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1, default=str)
        print(f"\n저장: {args.json}")


if __name__ == "__main__":
    asyncio.run(main())
