"""
Hidden Gem - 추천 결과 스냅샷 / 회귀 비교
=========================================
gem_percentile 정의 변경처럼 점수 체계를 건드리는 작업의 안전장치.
실행 중인 FastAPI에 고정 시나리오를 던져 상위 결과를 저장하고(before), 변경 후 다시
저장해(after) 두 스냅샷을 diff 한다. "분포가 괜찮다"가 아니라 "실제 추천 결과가
어떻게 달라졌나"를 눈으로 확인하고 넘어가기 위한 도구.

시나리오는 서비스의 주요 동선을 덮는다: 취향 프리셋 5개(힐링/전략/서사/액션/공포),
히든젬 필터 유무, 참조 게임 기반(by-game), 시맨틱 검색 3개.

사용법 (batch 컨테이너 안, fastapi 컨테이너가 떠 있어야 함):
    docker compose exec batch python -m embeddings.rec_snapshot --save before
    # ... gem_evidence --apply 등 변경 수행 ...
    docker compose exec batch python -m embeddings.rec_snapshot --save after
    docker compose exec batch python -m embeddings.rec_snapshot --diff before after
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SNAP_DIR = DATA_DIR / "audit" / "snapshots"
API = os.getenv("FASTAPI_BASE", "http://fastapi:8000/api/v1")
TOP_N = 10

PRESETS: Dict[str, Dict[str, float]] = {
    "힐링": {"cozy_factor": 9, "time_pressure": 1, "reflex_demand": 2, "melancholy": 3},
    "전략": {"strategic_depth": 9, "management_complexity": 8, "reflex_demand": 2},
    "서사": {"narrative_depth": 9, "lore_richness": 8, "choice_consequence": 8},
    "액션": {"reflex_demand": 9, "action_pacing": 9, "time_pressure": 7},
    "공포": {"horror_factor": 9, "melancholy": 6, "cozy_factor": 0},
}
SEMANTIC = ["스토리 좋은 힐링게임", "짧게 즐기는 로그라이크", "위쳐 같은 게임"]
BY_GAME_APPIDS: List[int] = [413150, 620, 391540]   # Stardew, Portal 2, Undertale (있으면 사용)


def _post(path: str, payload: dict) -> dict:
    try:
        r = requests.post(f"{API}{path}", json=payload, timeout=60)
        return r.json() if r.status_code == 200 else {"_error": f"HTTP {r.status_code}: {r.text[:200]}"}
    except requests.RequestException as e:
        return {"_error": str(e)[:200]}


def collect() -> dict:
    out = {"scenarios": {}}
    for name, prefs in PRESETS.items():
        for tag, extra in (("전체", {}), ("히든젬", {"max_review_count": 20000})):
            key = f"pref:{name}:{tag}"
            out["scenarios"][key] = _post("/games/recommend/by-preference",
                                          {"preferences": prefs, "count": TOP_N, **extra})
    for q in SEMANTIC:
        out["scenarios"][f"semantic:{q}"] = _post("/games/search/semantic", {"query": q, "limit": TOP_N})
    for app_id in BY_GAME_APPIDS:
        out["scenarios"][f"bygame:{app_id}"] = _post("/games/recommend/by-game",
                                                     {"app_id": app_id, "count": TOP_N})
    return out


_DETAIL_CACHE: Dict[int, dict] = {}


def _detail(app_id: int) -> dict:
    """리뷰 수는 추천 응답에 없어 상세 엔드포인트로 채운다 (유명작 필터 판정에 필요)."""
    if app_id in _DETAIL_CACHE:
        return _DETAIL_CACHE[app_id]
    try:
        r = requests.get(f"{API}/games/{app_id}", timeout=20)
        d = r.json() if r.status_code == 200 else {}
    except requests.RequestException:
        d = {}
    _DETAIL_CACHE[app_id] = d
    return d


def _rows(res: dict, enrich: bool = False) -> List[dict]:
    if not isinstance(res, dict) or "_error" in res:
        return []
    items = res.get("recommendations") or res.get("results") or res.get("games") or []
    rows = []
    for it in items:
        if not isinstance(it, dict):
            continue
        sb = it.get("score_breakdown") or {}
        row = {
            "app_id": it.get("app_id"),
            "name": (it.get("name") or "")[:40],
            "score": it.get("similarity_score", it.get("match_score", it.get("score"))),
            "gem_bonus": sb.get("gem_score"),          # 표시 점수에 실제로 더해진 gem 기여분
            "gem_potential": it.get("gem_potential"),  # 응답이 노출하는 gem 값
            "reviews": it.get("review_count"),
        }
        if enrich and row["reviews"] is None and row["app_id"]:
            d = _detail(row["app_id"])
            row["reviews"] = d.get("review_count")
            row["ratio"] = d.get("steam_positive_ratio")
            m = d.get("metrics") or {}
            row["gem_percentile"] = m.get("gem_percentile") if isinstance(m, dict) else None
        rows.append(row)
    return rows


def save(label: str) -> int:
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    data = collect()
    path = SNAP_DIR / f"{label}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for v in data["scenarios"].values() if "_error" not in v)
    print(f"저장: {path}  (시나리오 {ok}/{len(data['scenarios'])} 성공)")
    # 리뷰 수/백분위를 상세 엔드포인트로 채워 스냅샷에 함께 저장 (나중 판정용)
    enriched = {}
    for k, v in data["scenarios"].items():
        enriched[k] = _rows(v, enrich=True)
    data["rows"] = enriched
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    for k, v in data["scenarios"].items():
        if "_error" in v:
            print(f"   실패 {k}: {v['_error']}")
            continue
        r = enriched[k]
        rev = [x["reviews"] for x in r if x.get("reviews") is not None]
        over = sum(1 for x in rev if x > 20000)
        print(f"   {k:28} {len(r)}건  1위 {r[0]['name'][:24] if r else '-':26} "
              f"리뷰중앙 {sorted(rev)[len(rev)//2] if rev else '-':>7}  2만초과 {over}건"
              f"{'  리뷰데이터 없음' if not rev else ''}")
    # 유명작 필터가 실제로 작동하는지 즉시 판정
    for name in [k for k in enriched if k.endswith(":히든젬")]:
        base = name.replace(":히든젬", ":전체")
        if base in enriched:
            a = [x["app_id"] for x in enriched[base]]
            b = [x["app_id"] for x in enriched[name]]
            if a == b:
                print(f"   주의: {base} 와 {name} 결과가 동일 — max_review_count 가 아무것도 "
                      f"걸러내지 못했다 (상위권에 2만 초과 게임이 없거나 review_count 가 비어있음)")
    return 0 if ok else 1


def diff(a: str, b: str) -> int:
    pa = json.loads((SNAP_DIR / f"{a}.json").read_text(encoding="utf-8"))
    pb = json.loads((SNAP_DIR / f"{b}.json").read_text(encoding="utf-8"))
    keys = [k for k in pa["scenarios"] if k in pb["scenarios"]]
    print(f"{a} → {b}  시나리오 {len(keys)}개\n")
    tot_over = tot_move = 0
    for k in keys:
        ra = pa.get("rows", {}).get(k) or _rows(pa["scenarios"][k])
        rb = pb.get("rows", {}).get(k) or _rows(pb["scenarios"][k])
        if not ra or not rb:
            print(f"[{k}] 비교 불가 (한쪽 결과 없음)"); continue
        ida = [x["app_id"] for x in ra]; idb = [x["app_id"] for x in rb]
        overlap = len(set(ida) & set(idb))
        moved = sum(1 for i, x in enumerate(idb) if x in ida and ida.index(x) != i)
        tot_over += overlap; tot_move += moved
        print(f"[{k}]  상위{TOP_N} 유지 {overlap}/{min(len(ida), len(idb))}  순서변동 {moved}")
        if overlap < len(idb):
            gone = [x for x in ra if x["app_id"] not in idb]
            new = [x for x in rb if x["app_id"] not in ida]
            for x in gone[:3]:
                print(f"     빠짐:   {x['name'][:30]:32} 점수 {x['score']} gem보너스 {x.get('gem_bonus')} 리뷰 {x.get('reviews')}")
            for x in new[:3]:
                print(f"     들어옴: {x['name'][:30]:32} 점수 {x['score']} gem보너스 {x.get('gem_bonus')} 리뷰 {x.get('reviews')}")
        # 같은 게임의 점수 변화
        sa = {x["app_id"]: x["score"] for x in ra if x["score"] is not None}
        sb = {x["app_id"]: x["score"] for x in rb if x["score"] is not None}
        both = [(sb[i] - sa[i]) for i in sa if i in sb]
        if both:
            print(f"     공통 게임 점수 변화 평균 {sum(both)/len(both):+.2f} "
                  f"(최대 {max(both):+.1f} / 최소 {min(both):+.1f})")
        ga = {x["app_id"]: x.get("gem_bonus") for x in ra if x.get("gem_bonus") is not None}
        gb = {x["app_id"]: x.get("gem_bonus") for x in rb if x.get("gem_bonus") is not None}
        gd = [gb[i] - ga[i] for i in ga if i in gb]
        if gd:
            print(f"     공통 게임 gem 보너스 변화 평균 {sum(gd)/len(gd):+.2f} "
                  f"(최대 {max(gd):+.1f} / 최소 {min(gd):+.1f})")
    n = len(keys)
    if n:
        print(f"\n요약: 시나리오당 평균 상위{TOP_N} 유지 {tot_over/n:.1f}개, 순서변동 {tot_move/n:.1f}개")
        print("판단 기준: 히든젬 시나리오에서 무명작이 올라오고 유명작이 빠지는 방향이면 의도대로.")
        print("           힐링/전략 같은 취향 시나리오의 상위가 통째로 뒤집히면 과도한 변화 — 재검토.")
    return 0


def variance(label: str) -> int:
    """점수 구성요소의 실측 분산 — 명목 예산이 아니라 이게 순위를 결정한다.

    예산이 Core 75 / X-Factor 18 / Gem 6 이어도, 어떤 항이 상한에 포화되어 있으면
    그 항은 순위에 아무 영향을 주지 않는다(모든 후보에 같은 점수를 더할 뿐).
    반대로 예산이 작아도 편차가 크면 그 항이 실질적으로 순위를 가른다.
    """
    import statistics as st
    path = SNAP_DIR / f"{label}.json"
    if not path.exists():
        print(f"스냅샷 없음: {path}"); return 1
    d = json.loads(path.read_text(encoding="utf-8"))
    BUDGET = {"core_score": 75.0, "xfactor_score": 18.0, "gem_score": 6.0, "final_score": 99.0}
    comp = {k: [] for k in BUDGET}
    per_sc = {}
    for k, v in d["scenarios"].items():
        items = (v or {}).get("recommendations") or []
        rows = [it.get("score_breakdown") or {} for it in items]
        rows = [r for r in rows if "core_score" in r]      # 경로 A 만 이 구성을 가진다
        if not rows:
            continue
        per_sc[k] = rows
        for c in comp:
            comp[c] += [r[c] for r in rows if r.get(c) is not None]
    if not per_sc:
        print("경로 A(score_v6) 시나리오가 없다 — by-preference 결과가 있는 스냅샷인지 확인"); return 1

    n = sum(len(r) for r in per_sc.values())
    print(f"[{label}] 경로 A 시나리오 {len(per_sc)}개 / 결과 {n}건\n")
    print(f"{'구성요소':>14} {'예산':>6} {'평균':>7} {'σ':>7} {'최소':>7} {'최대':>7} {'포화율':>7}")
    sds = {}
    for c in ("core_score", "xfactor_score", "gem_score", "final_score"):
        v = comp[c]
        if not v:
            continue
        sd = st.pstdev(v); sds[c] = sd
        sat = sum(1 for x in v if x >= BUDGET[c] * 0.97) / len(v) * 100
        print(f"{c:>14} {BUDGET[c]:>6.0f} {st.mean(v):>7.2f} {sd:>7.2f} {min(v):>7.1f} {max(v):>7.1f} {sat:>6.0f}%")

    tot = sum(sds.get(c, 0) for c in ("core_score", "xfactor_score", "gem_score"))
    if tot:
        print("\n랭킹 지배력 — 예산 비중 vs 실측 σ 비중 (σ 비중이 실제 영향력이다)")
        for c in ("core_score", "xfactor_score", "gem_score"):
            print(f"   {c:>14}: 예산 {BUDGET[c]/99*100:>5.1f}%  →  실측 {sds.get(c, 0)/tot*100:>5.1f}%")

    print("\n시나리오별 (상위 결과 안에서 무엇이 순위를 가르는가)")
    print(f"{'시나리오':>18} {'Core σ':>8} {'X-F σ':>8} {'Gem σ':>8} {'Core 폭':>9} {'X-F 폭':>8} {'Gem 폭':>8}")
    for k, rows in per_sc.items():
        co = [r["core_score"] for r in rows]
        xf = [r.get("xfactor_score", 0) for r in rows]
        gm = [r.get("gem_score", 0) for r in rows]
        print(f"{k[:18]:>18} {st.pstdev(co):>8.2f} {st.pstdev(xf):>8.2f} {st.pstdev(gm):>8.2f} "
              f"{max(co)-min(co):>9.1f} {max(xf)-min(xf):>8.1f} {max(gm)-min(gm):>8.1f}")
    print("\n[측정 한계 — 반드시 읽을 것]")
    print("  1) 위 σ 비중은 '랭킹 지배력'이 아니다. 단순 σ 비율일 뿐이다. 순위 영향력을 재려면")
    print("     구성요소를 0으로 놓고 전체 후보를 재정렬해 Kendall τ/RBO 를 비교하는 절제 실험이")
    print("     필요하다 (스냅샷은 상위 N만 담고 있어 불가능 — 채점 쪽에서 전체 풀을 돌려야 한다).")
    print("  2) 이 표본은 '합계 상위 N'이라 선택 절단에 오염됐다. σ_final ≈ σ_core 이면 구성요소")
    print("     간 음의 공분산이 크다는 뜻이고, 그건 게임의 성질이 아니라 상위 N 선택의 인공물이다.")
    print("     → 상위 N의 σ는 전체 풀의 변별력을 과소평가한다.")
    print("  3) 포화율이 높은 항은 '순위에 영향이 없다'가 아니라 '선택 게이트로 작동한다'고 읽어야")
    print("     한다. 다른 항의 승자 폭이 좁으면, 그 항이 낮은 후보는 상위권 진입 자체가 막힌다.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="추천 결과 스냅샷/회귀 비교")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--save", metavar="LABEL")
    g.add_argument("--diff", nargs=2, metavar=("BEFORE", "AFTER"))
    g.add_argument("--variance", metavar="LABEL",
                   help="저장된 스냅샷의 점수 구성요소 분산 분석 (명목 예산 vs 실측 영향력)")
    a = ap.parse_args()
    if a.save:
        return save(a.save)
    if a.diff:
        return diff(*a.diff)
    return variance(a.variance)


if __name__ == "__main__":
    sys.exit(main() or 0)
