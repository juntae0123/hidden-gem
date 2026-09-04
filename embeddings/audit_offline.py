"""
Hidden Gem - 교사 vs 학생 오프라인 비교 (DB·API 없이 파일만으로)
================================================================
교사 = data/final/final_master_games_fixed.jsonl (GPT-5.4, 4,190건, 설명 포함)
학생 = data/batch_output_*.jsonl (gpt-5.4-mini few-shot, 백필 결과)

같은 게임을 양쪽이 매긴 값은 없으므로(중복 제외 수집) 직접 MAE는 못 낸다. 대신
모집단 차이(교사=인기순 샘플, 학생=출시작 전수)에 덜 흔들리는 검사들을 한다:

  1. 값 사용 패턴: 지표별 0~10 사용 분포, 표준편차 붕괴(뭉개짐), 극값 회피 여부
  2. 장르 조건부 비교: 같은 장르 토큰(공포/전략/캐주얼/RPG…)을 가진 게임끼리
     핵심 지표 평균 비교 → 모집단 편향을 크게 줄인 비교
  3. 지표 간 상관 구조: 49×49 상관행렬을 양쪽에서 구해 비교
     (horror↔gore, reflex↔action_pacing 같은 "판단의 구조"가 같은지)
  4. confidence 분포, 불리언 태그 비율, gem 히스토그램
  5. 눈검수: 학생 결과에서 이름 있는 게임 몇 개를 설명과 함께 출력

사용법 (컨테이너 없이도 됨):
    python embeddings/audit_offline.py [--since 20260903] [--out data/audit/offline_compare.txt]
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
TEACHER_FILE = DATA_DIR / "final" / "final_master_games_fixed.jsonl"

NUMERIC = [
    'cozy_factor', 'horror_factor', 'gore_level', 'humor_rating', 'dark_fantasy_vibe', 'epic_scale', 'melancholy',
    'reflex_demand', 'strategic_depth', 'grind_factor', 'time_pressure', 'learning_curve',
    'freedom_level', 'action_pacing', 'rng_dependency', 'growth_reward', 'exploration_reward',
    'management_complexity', 'stealth_importance', 'session_length', 'narrative_linearity',
    'puzzle_complexity', 'platforming_precision',
    'coop_synergy', 'competitive_stress', 'npc_interaction', 'user_creation', 'multiplayer_scale',
    'lore_richness', 'choice_consequence', 'visual_spectacle', 'environmental_storytelling', 'soundtrack_impact',
    'build_variety', 'progression_clarity', 'save_flexibility', 'difficulty_accessibility', 'tutorial_quality',
    'ui_ux_polish', 'modding_support', 'art_style_uniqueness', 'audio_design', 'animation_quality',
    'world_reactivity', 'community_dependency', 'narrative_depth', 'replay_value', 'endgame_content',
    'monetization_fairness',
]
BOOLS = ['is_turn_based', 'is_real_time', 'is_first_person', 'is_third_person', 'has_permadeath',
         'has_base_building', 'has_crafting', 'is_anime_style', 'is_retro_aesthetic']

# 장르 토큰 → 그 장르에서 "당연히" 움직여야 하는 지표
GENRE_PROBES = {
    "공포":   ["horror_factor", "gore_level", "cozy_factor"],
    "전략":   ["strategic_depth", "reflex_demand", "management_complexity"],
    "캐주얼": ["learning_curve", "cozy_factor", "session_length"],
    "RPG":    ["narrative_depth", "growth_reward", "lore_richness"],
    "시뮬레이션": ["management_complexity", "freedom_level", "action_pacing"],
    "액션":   ["reflex_demand", "action_pacing", "time_pressure"],
    "어드벤처": ["exploration_reward", "narrative_depth", "puzzle_complexity"],
    "레이싱": ["reflex_demand", "competitive_stress", "narrative_depth"],
    "스포츠": ["competitive_stress", "multiplayer_scale", "narrative_depth"],
}


def flatten(metrics: dict) -> dict:
    flat = {}
    for k, v in metrics.items():
        if isinstance(v, dict):
            flat.update(v)
        else:
            flat[k] = v
    return flat


def load_teacher():
    rows = []
    with open(TEACHER_FILE, encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            flat = flatten(o.get("metrics") or {})
            rows.append({
                "app_id": o.get("app_id"), "name": o.get("name", ""), "genres": o.get("genres", "") or "",
                "desc_len": len(o.get("description") or ""),
                "m": flat, "tags": o.get("tags") or {},
                "conf": (o.get("reasoning") or {}).get("confidence_score"),
            })
    return rows


def load_student(since: str, csv_lookup: dict):
    rows = []
    files = sorted(glob.glob(str(DATA_DIR / "batch_output_*.jsonl")))
    files = [f for f in files if re.search(r"(\d{8})", os.path.basename(f)).group(1) >= since]
    for f in files:
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                body = (o.get("response") or {}).get("body") or {}
                if not body.get("model", "").startswith("gpt-5.4-mini"):
                    continue
                try:
                    content = json.loads(re.sub(r"^```(?:json)?|```$", "", body["choices"][0]["message"]["content"].strip()))
                except Exception:
                    continue
                m = re.search(r"(\d+)", o.get("custom_id", ""))
                app_id = int(m.group(1)) if m else None
                info = csv_lookup.get(app_id, {})
                rows.append({
                    "app_id": app_id, "name": info.get("name", ""), "genres": info.get("genres", ""),
                    "desc_len": len(info.get("description", "")),
                    "m": flatten(content.get("metrics") or {}), "tags": content.get("tags") or {},
                    "conf": (content.get("reasoning") or {}).get("confidence_score"),
                    "content": content.get("content") or {},
                })
    return rows, files


def load_csv_lookup():
    """batch_tasks JSONL(요청 본문)에서 학생 게임의 이름/장르/설명 복원."""
    lookup = {}
    for f in glob.glob(str(DATA_DIR / "batch_tasks_2026090*.jsonl")):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                m = re.search(r"(\d+)", o.get("custom_id", ""))
                if not m:
                    continue
                msgs = (o.get("body") or {}).get("messages") or []
                user = msgs[-1].get("content", "") if msgs else ""
                # 형식: "GAME_DATA:\n{ ...json... }"
                try:
                    data = json.loads(user.split("GAME_DATA:", 1)[-1].strip())
                except (json.JSONDecodeError, IndexError):
                    data = {}
                lookup[int(m.group(1))] = {
                    "name": str(data.get("name", "")),
                    "genres": str(data.get("genres", "")),
                    "description": str(data.get("description", "")),
                }
    return lookup


def matrix(rows):
    X = np.full((len(rows), len(NUMERIC)), np.nan)
    for i, r in enumerate(rows):
        for j, k in enumerate(NUMERIC):
            v = r["m"].get(k)
            if isinstance(v, (int, float)):
                X[i, j] = float(v)
    return X


def corr_matrix(X):
    Xc = np.where(np.isnan(X), np.nanmean(X, axis=0), X)
    sd = Xc.std(axis=0)
    sd[sd == 0] = 1
    Z = (Xc - Xc.mean(axis=0)) / sd
    return (Z.T @ Z) / len(Z)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="20260903")
    ap.add_argument("--out", default=str(DATA_DIR / "audit" / "offline_compare.txt"))
    a = ap.parse_args()
    out_lines = []

    def p(s=""):
        print(s); out_lines.append(s)

    T = load_teacher()
    lookup = load_csv_lookup()
    S, files = load_student(a.since, lookup)
    XT, XS = matrix(T), matrix(S)
    p(f"교사 {len(T):,}건 (GPT-5.4)  |  학생 {len(S):,}건 (gpt-5.4-mini, 파일 {len(files)}개)")
    p(f"학생 이름/장르 복원: {sum(1 for r in S if r['name']):,}건")

    # 0. 스키마 완전성
    miss_t = np.isnan(XT).sum(); miss_s = np.isnan(XS).sum()
    p(f"\n[0] 스키마: 49지표 누락 셀 — 교사 {miss_t} / 학생 {miss_s}")

    # 1. 값 사용 패턴
    p("\n[1] 지표별 분포 (평균±표준편차, 0비율%, 8+비율%)  — 학생 σ가 교사의 60% 미만이면 '뭉개짐' 경고")
    p(f"{'지표':26} {'교사 μ±σ':>14} {'학생 μ±σ':>14} {'교사0%':>7} {'학생0%':>7} {'교사8+%':>8} {'학생8+%':>8}  판정")
    collapsed = []
    for j, k in enumerate(NUMERIC):
        t, s = XT[:, j], XS[:, j]
        t, s = t[~np.isnan(t)], s[~np.isnan(s)]
        flag = ""
        if s.std() < 0.6 * t.std():
            flag = "σ붕괴"; collapsed.append(k)
        p(f"{k:26} {t.mean():6.2f}±{t.std():4.2f}   {s.mean():6.2f}±{s.std():4.2f}   "
          f"{(t==0).mean()*100:6.1f} {(s==0).mean()*100:7.1f} {(t>=8).mean()*100:8.1f} {(s>=8).mean()*100:8.1f}  {flag}")
    p(f"→ σ붕괴 지표 {len(collapsed)}개: {', '.join(collapsed) if collapsed else '없음'}")

    # 2. 장르 조건부
    p("\n[2] 장르 조건부 비교 — 같은 장르 토큰을 가진 게임끼리 (모집단 편향 완화). 차이 |Δ|≥1.5면 표시")
    p(f"{'장르':8} {'교사n':>6} {'학생n':>6}  지표: 교사μ → 학생μ (Δ)")
    big = 0
    for g, probes in GENRE_PROBES.items():
        ti = [i for i, r in enumerate(T) if g in r["genres"]]
        si = [i for i, r in enumerate(S) if g in r["genres"]]
        if len(ti) < 20 or len(si) < 20:
            continue
        parts = []
        for k in probes:
            j = NUMERIC.index(k)
            tm, sm = np.nanmean(XT[ti, j]), np.nanmean(XS[si, j])
            d = sm - tm
            mark = " ◀" if abs(d) >= 1.5 else ""
            big += abs(d) >= 1.5
            parts.append(f"{k} {tm:.1f}→{sm:.1f} ({d:+.1f}){mark}")
        p(f"{g:8} {len(ti):6} {len(si):6}  " + " | ".join(parts))
    p(f"→ |Δ|≥1.5 항목 {big}개 / {sum(len(v) for v in GENRE_PROBES.values())}개")

    # 3. 상관 구조
    CT, CS = corr_matrix(XT), corr_matrix(XS)
    iu = np.triu_indices(len(NUMERIC), 1)
    ct, cs = CT[iu], CS[iu]
    rr = np.corrcoef(ct, cs)[0, 1]
    mad = np.abs(ct - cs).mean()
    p(f"\n[3] 지표 간 상관 구조 (49×49 상관행렬 상삼각 1,176쌍)")
    p(f"    교사 vs 학생 상관계수들의 상관 r = {rr:.3f}  (0.8 이상이면 판단 구조 유사)")
    p(f"    평균 절대 차이 = {mad:.3f}")
    diffs = sorted(((abs(ct[n] - cs[n]), NUMERIC[iu[0][n]], NUMERIC[iu[1][n]], ct[n], cs[n]) for n in range(len(ct))), reverse=True)[:8]
    p("    가장 어긋난 쌍 (교사 r → 학생 r):")
    for d, x, y, a1, b1 in diffs:
        p(f"      {x} ↔ {y}: {a1:+.2f} → {b1:+.2f}")

    # 4. confidence / bool / gem
    ct_ = np.array([r["conf"] for r in T if isinstance(r["conf"], (int, float))], float)
    cs_ = np.array([r["conf"] for r in S if isinstance(r["conf"], (int, float))], float)
    p(f"\n[4] confidence  교사 μ {ct_.mean():.3f} σ {ct_.std():.3f} [{ct_.min():.2f}~{ct_.max():.2f}]"
      f"  |  학생 μ {cs_.mean():.3f} σ {cs_.std():.3f} [{cs_.min():.2f}~{cs_.max():.2f}]")
    p("    분포(교사 / 학생): " + "  ".join(
        f"{lo:.1f}-{lo+0.1:.1f}: {((ct_>=lo)&(ct_<lo+0.1)).mean()*100:4.1f}%/{((cs_>=lo)&(cs_<lo+0.1)).mean()*100:4.1f}%"
        for lo in np.arange(0.4, 1.0, 0.1)))
    p("\n    불리언 태그 TRUE 비율 (교사% / 학생%):")
    for b in BOOLS:
        tb = np.mean([bool(r["tags"].get(b)) for r in T]); sb = np.mean([bool(r["tags"].get(b)) for r in S])
        p(f"      {b:20} {tb*100:5.1f} / {sb*100:5.1f}")
    gt = np.array([r["m"].get("gem_potential") for r in T if isinstance(r["m"].get("gem_potential"), (int, float))], float)
    gs = np.array([r["m"].get("gem_potential") for r in S if isinstance(r["m"].get("gem_potential"), (int, float))], float)
    p(f"\n    gem_potential 교사 μ {gt.mean():.1f} σ {gt.std():.1f} | 학생 μ {gs.mean():.1f} σ {gs.std():.1f}")
    edges = [0, 20, 35, 50, 65, 80, 101]
    p("    히스토그램(교사% / 학생%): " + "  ".join(
        f"{edges[i]}-{edges[i+1]-1}: {((gt>=edges[i])&(gt<edges[i+1])).mean()*100:4.1f}/{((gs>=edges[i])&(gs<edges[i+1])).mean()*100:4.1f}"
        for i in range(len(edges) - 1)))
    p(f"    학생 gem 고유값 수: {len(np.unique(gs))} (교사 {len(np.unique(gt))}) — 값이 5의 배수에 몰리는지: "
      f"학생 {np.isin(gs % 10, [0, 5]).mean()*100:.0f}% / 교사 {np.isin(gt % 10, [0, 5]).mean()*100:.0f}%")

    # 5. 눈검수 후보: 학생 결과 중 gem 상위 8 + 이름 있는 무작위 8
    p("\n[5] 눈검수 (학생) — gem 상위 8건 + 무작위 8건")
    named = [r for r in S if r["name"]]
    top = sorted(named, key=lambda r: -(r["m"].get("gem_potential") or 0))[:8]
    rng = np.random.default_rng(7)
    rnd = [named[i] for i in rng.choice(len(named), 8, replace=False)] if len(named) >= 8 else []
    for grp, rows in (("gem 상위", top), ("무작위", rnd)):
        p(f"  -- {grp}")
        for r in rows:
            m = r["m"]
            p(f"  gem {m.get('gem_potential'):>3}  conf {r['conf']}  {r['name'][:34]:36} [{r['genres'][:30]}]")
            p(f"       reflex {m.get('reflex_demand')} strat {m.get('strategic_depth')} cozy {m.get('cozy_factor')} horror {m.get('horror_factor')} "
              f"narr {m.get('narrative_depth')} visual {m.get('visual_spectacle')} replay {m.get('replay_value')} polish {m.get('ui_ux_polish')}")
            p(f"       {str(r['content'].get('one_line_summary',''))[:110]}")

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(out_lines), encoding="utf-8")
    print(f"\n저장: {a.out}")


if __name__ == "__main__":
    main()
