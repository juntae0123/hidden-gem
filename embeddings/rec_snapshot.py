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


def _rows(res: dict) -> List[dict]:
    if not isinstance(res, dict) or "_error" in res:
        return []
    items = res.get("recommendations") or res.get("results") or res.get("games") or []
    rows = []
    for it in items:
        if not isinstance(it, dict):
            continue
        rows.append({
            "app_id": it.get("app_id"),
            "name": (it.get("name") or "")[:40],
            "score": it.get("match_score", it.get("score")),
            "gem": it.get("gem_percentile", it.get("gem_score")),
            "reviews": it.get("review_count"),
        })
    return rows


def save(label: str) -> int:
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    data = collect()
    path = SNAP_DIR / f"{label}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for v in data["scenarios"].values() if "_error" not in v)
    print(f"저장: {path}  (시나리오 {ok}/{len(data['scenarios'])} 성공)")
    for k, v in data["scenarios"].items():
        if "_error" in v:
            print(f"   실패 {k}: {v['_error']}")
        else:
            r = _rows(v)
            print(f"   {k:28} {len(r)}건  1위 {r[0]['name'] if r else '-'}")
    return 0 if ok else 1


def diff(a: str, b: str) -> int:
    pa = json.loads((SNAP_DIR / f"{a}.json").read_text(encoding="utf-8"))
    pb = json.loads((SNAP_DIR / f"{b}.json").read_text(encoding="utf-8"))
    keys = [k for k in pa["scenarios"] if k in pb["scenarios"]]
    print(f"{a} → {b}  시나리오 {len(keys)}개\n")
    tot_over = tot_move = 0
    for k in keys:
        ra, rb = _rows(pa["scenarios"][k]), _rows(pb["scenarios"][k])
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
                print(f"     빠짐: {x['name'][:30]:32} 점수 {x['score']} gem {x['gem']} 리뷰 {x['reviews']}")
            for x in new[:3]:
                print(f"     들어옴: {x['name'][:30]:32} 점수 {x['score']} gem {x['gem']} 리뷰 {x['reviews']}")
        # 같은 게임의 점수 변화
        sa = {x["app_id"]: x["score"] for x in ra if x["score"] is not None}
        sb = {x["app_id"]: x["score"] for x in rb if x["score"] is not None}
        both = [(sb[i] - sa[i]) for i in sa if i in sb]
        if both:
            print(f"     공통 게임 점수 변화 평균 {sum(both)/len(both):+.2f} "
                  f"(최대 {max(both):+.1f} / 최소 {min(both):+.1f})")
    n = len(keys)
    if n:
        print(f"\n요약: 시나리오당 평균 상위{TOP_N} 유지 {tot_over/n:.1f}개, 순서변동 {tot_move/n:.1f}개")
        print("판단 기준: 히든젬 시나리오에서 무명작이 올라오고 유명작이 빠지는 방향이면 의도대로.")
        print("           힐링/전략 같은 취향 시나리오의 상위가 통째로 뒤집히면 과도한 변화 — 재검토.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="추천 결과 스냅샷/회귀 비교")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--save", metavar="LABEL")
    g.add_argument("--diff", nargs=2, metavar=("BEFORE", "AFTER"))
    a = ap.parse_args()
    return save(a.save) if a.save else diff(*a.diff)


if __name__ == "__main__":
    sys.exit(main() or 0)
