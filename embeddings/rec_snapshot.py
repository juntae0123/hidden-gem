"""
Hidden Gem - 추천 결과 스냅샷 / 회귀 비교
=========================================
gem_percentile 정의 변경처럼 점수 체계를 건드리는 작업의 안전장치.
실행 중인 FastAPI에 고정 시나리오를 던져 상위 결과를 저장하고(before), 변경 후 다시
저장해(after) 두 스냅샷을 diff 한다. "분포가 괜찮다"가 아니라 "실제 추천 결과가
어떻게 달라졌나"를 눈으로 확인하고 넘어가기 위한 도구.

시나리오는 서비스의 주요 동선을 덮는다: 취향 프리셋 5개(힐링/전략/서사/액션/공포),
히든젬 필터 유무, 참조 게임 기반(by-game), 시맨틱 검색 3개.

[측정 신뢰성 — 2026-09-04 외부 검토 반영]
    1) 캐시 오염이 이 도구의 1순위 위험이다. 추천/검색 결과는 Redis 에 캐시되고
       캐시 키에 점수 로직 버전이 들어있지 않다. 따라서 s0 을 찍은 뒤 코드를 고치고
       s1 을 찍으면 s1 이 s0 의 캐시를 그대로 돌려받아 "변화 없음"으로 보인다.
       → --save 는 매번 캐시를 비우고, 비운 것을 통계로 확인한 뒤에만 수집한다.
          확인 실패 시 스냅샷을 쓰지 않고 종료 코드 2 로 죽는다.
    2) 스냅샷은 '합계 상위 N'만 담는다. 여기서 계산한 σ 는 전체 풀의 변별력이 아니다.
       (선택 절단 / collider) --variance 의 [측정 한계] 절을 반드시 함께 읽어야 한다.

사용법 (batch 컨테이너 안, fastapi 컨테이너가 떠 있어야 함):
    docker compose exec batch python -m embeddings.rec_snapshot --save s0_before
    # ... gem_evidence --apply 등 변경 수행 ...
    docker compose exec batch python -m embeddings.rec_snapshot --save s1_after_gate
    docker compose exec batch python -m embeddings.rec_snapshot --diff s0_before s1_after_gate
    docker compose exec batch python -m embeddings.rec_snapshot --variance s1_after_gate
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SNAP_DIR = DATA_DIR / "audit" / "snapshots"
API = os.getenv("FASTAPI_BASE", "http://fastapi:8000/api/v1")
# /ops/* 는 api prefix 밖에 있다 (main.py 에 직접 매달려 있음)
API_ROOT = API.split("/api/")[0]
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
RANKING_TYPES = ("steady", "new", "rising")          # new_quiet 는 리뷰<30 신작이라 회차마다 흔들려 제외


def _get(path: str, params: dict) -> dict:
    try:
        r = requests.get(f"{API}{path}", params=params, timeout=60)
        return r.json() if r.status_code == 200 else {"_error": f"HTTP {r.status_code}: {r.text[:200]}"}
    except requests.RequestException as e:
        return {"_error": str(e)[:200]}


def _post(path: str, payload: dict) -> dict:
    try:
        r = requests.post(f"{API}{path}", json=payload, timeout=60)
        return r.json() if r.status_code == 200 else {"_error": f"HTTP {r.status_code}: {r.text[:200]}"}
    except requests.RequestException as e:
        return {"_error": str(e)[:200]}


# ==================== 캐시 오염 차단 ====================

def clear_cache() -> dict:
    """추천/검색 캐시를 비우고, 실제로 비었는지 통계로 확인한다.

    invalidate_all() 은 '키가 없었음'과 'Redis 예외'를 모두 0 으로 돌려주기 때문에
    반환값만으로는 성공을 알 수 없다(cache.py:170-195). 그래서 삭제 후 /ops/cache 로
    total_keys 를 직접 읽어 0 인지 확인한다. get_stats 는 실패 시 {"error": ...} 를
    돌려주므로 'Redis 죽음'과 '키 0개'가 구분된다.

    Returns: {"ok": bool, "deleted": int, "before": dict|None, "after": dict|None, "why": str}
    """
    out = {"ok": False, "deleted": None, "before": None, "after": None, "why": ""}
    # fastapi 재시작 직후 호출되는 경우가 잦다(restart 0.9s 뒤 uvicorn 부팅 수 초). 최대 45초 기다린다.
    last_err = None
    for attempt in range(15):
        try:
            b = requests.get(f"{API_ROOT}/ops/cache", timeout=20)
            out["before"] = b.json() if b.status_code == 200 else {"error": f"HTTP {b.status_code}"}
            last_err = None
            break
        except requests.RequestException as e:
            last_err = e
            if attempt == 0:
                print("fastapi 응답 없음 — 부팅 대기 중 (최대 45초)…")
            time.sleep(3)
    if last_err is not None:
        out["why"] = f"캐시 통계 조회 불가(45초 대기 후): {str(last_err)[:120]}"
        return out

    if not isinstance(out["before"], dict) or "error" in out["before"]:
        out["why"] = f"캐시 통계가 오류를 돌려줬다: {out['before']}"
        return out

    try:
        r = requests.post(f"{API_ROOT}/ops/cache/invalidate", timeout=30)
        if r.status_code != 200:
            out["why"] = f"무효화 엔드포인트 HTTP {r.status_code}: {r.text[:120]}"
            return out
        out["deleted"] = (r.json() or {}).get("deleted_keys")
    except requests.RequestException as e:
        out["why"] = f"무효화 호출 실패: {str(e)[:120]}"
        return out

    try:
        a = requests.get(f"{API_ROOT}/ops/cache", timeout=20)
        out["after"] = a.json() if a.status_code == 200 else {"error": f"HTTP {a.status_code}"}
    except requests.RequestException as e:
        out["why"] = f"삭제 후 통계 조회 불가: {str(e)[:120]}"
        return out

    after = out["after"]
    if not isinstance(after, dict) or "error" in after:
        out["why"] = f"삭제 후 통계가 오류를 돌려줬다: {after}"
        return out
    remaining = after.get("total_keys")
    if remaining is None:
        out["why"] = f"삭제 후 total_keys 를 읽을 수 없다: {after}"
        return out
    if remaining != 0:
        out["why"] = f"삭제 후에도 캐시 키 {remaining}개 남아있다 — 무효화가 일부만 먹었다"
        return out
    out["ok"] = True
    return out


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
    # R-11 랭킹 3종 — 카나리아: 신작 랭킹 1위는 메챠 카멜레온이어야 한다 (사용자 명시). 회차마다 기록해 diff 로 본다.
    for kind in RANKING_TYPES:
        out["scenarios"][f"ranking:{kind}"] = _get("/games/ranking", {"type": kind, "limit": TOP_N})
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


def _gem_contrib(sb: dict) -> Optional[float]:
    """표시 점수에 실제로 더해진 gem 기여분.

    경로마다 키가 다르다:
        경로 A score_v6            → score_breakdown["gem_score"]   (최대 6.0)
        경로 B/C recommender       → score_breakdown["gem_bonus"]   (×5.0)
    `sb.get("gem_score") or sb.get("gem_bonus")` 로 쓰면 실제 값 0.0 이
    fallback 으로 넘어가 버리므로 키 존재 여부로 분기한다.
    """
    if "gem_score" in sb:
        return sb.get("gem_score")
    if "gem_bonus" in sb:
        return sb.get("gem_bonus")
    return None


def _rows(res: dict, enrich: bool = False) -> List[dict]:
    if not isinstance(res, dict) or "_error" in res:
        return []
    items = res.get("recommendations") or res.get("results") or res.get("games") or res.get("items") or []
    rows = []
    for it in items:
        if not isinstance(it, dict):
            continue
        sb = it.get("score_breakdown") or {}
        row = {
            "app_id": it.get("app_id"),
            "name": (it.get("name") or "")[:40],
            # 랭킹 응답은 점수 대신 rank/gem_evidence/velocity_per_day 를 가진다 → 순위를 점수 자리에 (변동 비교용)
            "score": it.get("similarity_score", it.get("match_score", it.get("score", it.get("rank")))),
            "gem_bonus": _gem_contrib(sb),             # 표시 점수에 더해진 gem 기여분 (경로별 키 흡수)
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


def save(label: str, overwrite: bool = False, skip_cache_clear: bool = False) -> int:
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAP_DIR / f"{label}.json"
    if path.exists() and not overwrite:
        print(f"이미 있는 스냅샷을 덮어쓰려 한다: {path}")
        print("증거를 지우는 실수를 막기 위해 거부한다. 다른 라벨을 쓰거나 --overwrite 를 붙여라.")
        return 2

    cache = {"skipped": True, "ok": False, "why": "--no-cache-clear 로 생략"}
    if skip_cache_clear:
        print("경고: 캐시 무효화를 생략했다. 이 스냅샷은 이전 회차의 캐시를 그대로")
        print("      돌려받았을 수 있어 '변화 없음' 판정의 증거로 쓸 수 없다.")
    else:
        cache = clear_cache()
        cache["skipped"] = False
        if not cache["ok"]:
            print(f"캐시 무효화 확인 실패 — 스냅샷을 쓰지 않고 중단한다.\n  이유: {cache['why']}")
            print("  캐시 키에는 점수 로직 버전이 없다. 캐시가 살아있으면 변경 전 결과가 그대로")
            print("  돌아와 회귀 비교가 무의미해진다. fastapi/redis 상태를 먼저 확인하라.")
            return 2
        print(f"캐시 무효화 확인: 삭제 {cache['deleted']}개 / 잔여 0개 "
              f"(직전 적재 {cache['before'].get('total_keys')}개)")

    data = collect()
    data["meta"] = {"label": label, "top_n": TOP_N, "api": API, "cache_clear": cache}
    total = len(data["scenarios"])
    ok = sum(1 for v in data["scenarios"].values() if "_error" not in v)
    print(f"수집: 시나리오 {ok}/{total} 성공")
    # 리뷰 수/백분위를 상세 엔드포인트로 채워 스냅샷에 함께 저장 (나중 판정용)
    enriched = {}
    for k, v in data["scenarios"].items():
        enriched[k] = _rows(v, enrich=True)
    data["rows"] = enriched
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"저장: {path}")

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
    # R-11 카나리아: 신작 랭킹 1위 = 메챠 카멜레온 (사용자: "메챠카멜레온이 신작랭킹 1위가 아니면 말이 안 된다")
    new_rows = enriched.get("ranking:new") or []
    if new_rows:
        pos = next((i + 1 for i, x in enumerate(new_rows)
                    if "카멜레온" in (x.get("name") or "") or "CHAMELEON" in (x.get("name") or "").upper()), None)
        top = (new_rows[0].get("name") or "")[:30]
        print(f"   카나리아: 신작 1위 {top} / 메챠 카멜레온 {('%d위' % pos) if pos else '상위 %d 밖 — 신작 후보 조건(R-11)을 먼저 본다' % TOP_N}")
    # 유명작 필터가 실제로 작동하는지 즉시 판정
    for name in [k for k in enriched if k.endswith(":히든젬")]:
        base = name.replace(":히든젬", ":전체")
        if base in enriched:
            a = [x["app_id"] for x in enriched[base]]
            b = [x["app_id"] for x in enriched[name]]
            if a == b:
                print(f"   주의: {base} 와 {name} 결과가 동일 — max_review_count 가 아무것도 "
                      f"걸러내지 못했다 (상위권에 2만 초과 게임이 없거나 review_count 가 비어있음)")

    if ok != total:
        print(f"\n실패한 시나리오가 {total - ok}개 있다. 일부만 성공한 스냅샷은 회귀 비교의")
        print("기준으로 쓸 수 없으므로 실패로 종료한다 (파일은 진단용으로 남겨둔다).")
        return 1
    if skip_cache_clear:
        print("\n주의: 캐시 무효화를 건너뛴 스냅샷이다. 비교 증거로 쓰지 말 것.")
    return 0


def diff(a: str, b: str) -> int:
    pa = json.loads((SNAP_DIR / f"{a}.json").read_text(encoding="utf-8"))
    pb = json.loads((SNAP_DIR / f"{b}.json").read_text(encoding="utf-8"))
    for lbl, p in ((a, pa), (b, pb)):
        cc = ((p.get("meta") or {}).get("cache_clear") or {})
        if cc.get("skipped") or (cc and not cc.get("ok")):
            print(f"경고: [{lbl}] 은 캐시 무효화가 확인되지 않은 스냅샷이다 — 아래 '변화 없음'은 증거가 아니다.")
        if not cc:
            print(f"경고: [{lbl}] 에 캐시 무효화 기록이 없다 (구버전 스냅샷). 캐시 오염 가능성을 배제할 수 없다.")
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
        print("주의: X-Factor 제거처럼 '선택 게이트'를 건드리는 변경에는 위 '상위 유지' 기준을")
        print("      적용하지 마라. 그 변경은 순위가 크게 바뀌는 것이 정상 예측이다.")
    return 0


def variance(label: str) -> int:
    """점수 구성요소의 실측 편차 — 상위 N 표본 안에서의 편차일 뿐이다.

    이 함수는 '어떤 항이 순위를 지배하는가'를 답하지 못한다. 답할 수 있는 것은
    '저장된 상위 N 안에서 각 항이 얼마나 흩어져 있는가' 뿐이고, 그 표본은 합계
    상위로 잘라낸 것이라 구성요소 간 음의 공분산이 인공적으로 끼어든다(선택 절단).
    순위 영향력은 구성요소를 끄고 전체 풀을 재정렬해 Kendall τ/RBO 로 재야 한다.
    아래 [측정 한계] 절을 반드시 함께 읽을 것.
    """
    import statistics as st
    path = SNAP_DIR / f"{label}.json"
    if not path.exists():
        print(f"스냅샷 없음: {path}"); return 1
    d = json.loads(path.read_text(encoding="utf-8"))
    cc = ((d.get("meta") or {}).get("cache_clear") or {})
    if cc.get("skipped") or (cc and not cc.get("ok")):
        print("경고: 캐시 무효화가 확인되지 않은 스냅샷이다 — 아래 수치는 이전 회차 결과일 수 있다.\n")
    elif not cc:
        print("경고: 캐시 무효화 기록이 없는 구버전 스냅샷이다.\n")

    BUDGET = {"core_score": 75.0, "xfactor_score": 18.0, "gem_score": 6.0, "final_score": 99.0}
    comp = {k: [] for k in BUDGET}
    per_sc = {}
    seen_games = set()
    dup_rows = 0
    for k, v in d["scenarios"].items():
        items = (v or {}).get("recommendations") or []
        rows = [it.get("score_breakdown") or {} for it in items]
        rows = [r for r in rows if "core_score" in r]      # 경로 A 만 이 구성을 가진다
        if not rows:
            continue
        per_sc[k] = rows
        for it in items:
            aid = it.get("app_id")
            if aid is None:
                continue
            if aid in seen_games:
                dup_rows += 1
            seen_games.add(aid)
        for c in comp:
            comp[c] += [r[c] for r in rows if r.get(c) is not None]
    if not per_sc:
        print("경로 A(score_v6) 시나리오가 없다 — by-preference 결과가 있는 스냅샷인지 확인"); return 1

    n = sum(len(r) for r in per_sc.values())
    print(f"[{label}] 경로 A 시나리오 {len(per_sc)}개 / 결과 {n}건 "
          f"(고유 게임 {len(seen_games)}개, 시나리오 간 중복 등장 {dup_rows}건)\n")
    print(f"{'구성요소':>14} {'예산':>6} {'평균':>7} {'σ':>7} {'최소':>7} {'최대':>7} {'관측최대비':>10}")
    sds = {}
    for c in ("core_score", "xfactor_score", "gem_score", "final_score"):
        v = comp[c]
        if not v:
            continue
        sd = st.pstdev(v); sds[c] = sd
        obs_max = max(v)
        # 명목 예산 기준 포화율은 오해를 부른다. Core 는 시그모이드 상한 때문에 75 에
        # 도달할 수 없어(거리 0 에서도 0.8176) 명목 기준으로는 영원히 0% 로 보인다.
        # 그래서 '관측된 최대의 97% 이상인 비율' 로 바꿔 보고한다.
        sat = sum(1 for x in v if obs_max > 0 and x >= obs_max * 0.97) / len(v) * 100
        print(f"{c:>14} {BUDGET[c]:>6.0f} {st.mean(v):>7.2f} {sd:>7.2f} {min(v):>7.1f} {obs_max:>7.1f} {sat:>9.0f}%")
    print("  * 관측최대비 = 이 표본에서 관측된 최대값의 97% 이상인 결과의 비율.")
    print("    명목 예산(75/18/6) 기준 포화율은 쓰지 않는다 — Core 는 시그모이드 상한 때문에")
    print("    75 에 도달할 수 없어 명목 기준으로는 항상 0% 로 보이고, 반대로 X-Factor 는")
    print("    실제 도달 가능한 상한에 붙어 있는데도 예산 기준으로는 덜 포화된 것처럼 보인다.")

    tot = sum(sds.get(c, 0) for c in ("core_score", "xfactor_score", "gem_score"))
    if tot:
        print("\n표본 내 편차 비중 — 예산 비중 vs 실측 σ 비중 (이것은 '지배력'이 아니다)")
        for c in ("core_score", "xfactor_score", "gem_score"):
            print(f"   {c:>14}: 예산 {BUDGET[c]/99*100:>5.1f}%  →  실측 σ {sds.get(c, 0)/tot*100:>5.1f}%")

    print("\n시나리오별 (상위 결과 안에서 무엇이 흩어져 있는가)")
    print(f"{'시나리오':>18} {'Core σ':>8} {'X-F σ':>8} {'Gem σ':>8} {'Core 폭':>9} {'X-F 폭':>8} {'Gem 폭':>8}")
    within = {"core_score": [], "xfactor_score": [], "gem_score": []}
    for k, rows in per_sc.items():
        co = [r["core_score"] for r in rows]
        xf = [r.get("xfactor_score", 0) for r in rows]
        gm = [r.get("gem_score", 0) for r in rows]
        within["core_score"].append(st.pstdev(co))
        within["xfactor_score"].append(st.pstdev(xf))
        within["gem_score"].append(st.pstdev(gm))
        print(f"{k[:18]:>18} {st.pstdev(co):>8.2f} {st.pstdev(xf):>8.2f} {st.pstdev(gm):>8.2f} "
              f"{max(co)-min(co):>9.1f} {max(xf)-min(xf):>8.1f} {max(gm)-min(gm):>8.1f}")
    print("\n시나리오 내 평균 σ (합산 σ 와 달리 시나리오 간 평균 차이가 섞이지 않는다)")
    for c in ("core_score", "xfactor_score", "gem_score"):
        vals = within[c]
        if vals:
            print(f"   {c:>14}: {sum(vals)/len(vals):>6.2f}")

    print("\n[측정 한계 — 반드시 읽을 것]")
    print("  1) 위 σ 비중은 '랭킹 지배력'이 아니다. 단순 σ 비율일 뿐이다. 순위 영향력을 재려면")
    print("     구성요소를 0으로 놓고 전체 후보를 재정렬해 Kendall τ/RBO 를 비교하는 절제 실험이")
    print("     필요하다 (스냅샷은 상위 N만 담고 있어 불가능 — 채점 쪽에서 전체 풀을 돌려야 한다).")
    print("  2) 이 표본은 '합계 상위 N'이라 선택 절단에 오염됐다. σ_final ≈ σ_core 이면 구성요소")
    print("     간 음의 공분산이 크다는 뜻이고, 그건 게임의 성질이 아니라 상위 N 선택의 인공물이다.")
    print("     → 상위 N의 σ는 전체 풀의 변별력을 과소평가한다.")
    print("  3) 관측최대비가 높은 항은 '순위에 영향이 없다'가 아니라 '선택 게이트로 작동한다'는")
    print("     가설을 세워야 한다(확정이 아니다). 다른 항의 승자 폭이 좁으면, 그 항이 낮은 후보는")
    print("     상위권 진입 자체가 막힐 수 있다. 확인은 절제 실험으로만 가능하다.")
    print("  4) 합산 σ 는 시나리오를 한 통에 섞은 값이라 시나리오 간 평균 차이가 σ 에 들어간다.")
    print("     반대로 시나리오 내 편차만 보면 과소평가된다. 편향 방향이 정해져 있지 않으므로")
    print("     두 값을 함께 보고 어느 쪽으로도 단정하지 않는다.")
    print(f"  5) 같은 게임이 여러 시나리오에 중복 등장한다(중복 {dup_rows}건 / 고유 {len(seen_games)}개).")
    print("     표본은 독립이 아니다 — 유의성 검정에 쓸 수 없다.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="추천 결과 스냅샷/회귀 비교")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--save", metavar="LABEL")
    g.add_argument("--diff", nargs=2, metavar=("BEFORE", "AFTER"))
    g.add_argument("--variance", metavar="LABEL",
                   help="저장된 스냅샷의 점수 구성요소 편차 분석 (해석 한계 함께 출력)")
    ap.add_argument("--overwrite", action="store_true",
                    help="같은 라벨의 기존 스냅샷을 덮어쓴다 (기본은 거부)")
    ap.add_argument("--no-cache-clear", action="store_true",
                    help="캐시 무효화를 생략한다. 스냅샷에 '증거 불가' 표시가 박힌다")
    a = ap.parse_args()
    if a.save:
        return save(a.save, overwrite=a.overwrite, skip_cache_clear=a.no_cache_clear)
    if a.diff:
        return diff(*a.diff)
    return variance(a.variance)


if __name__ == "__main__":
    sys.exit(main() or 0)
