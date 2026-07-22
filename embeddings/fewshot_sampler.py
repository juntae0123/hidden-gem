"""
Hidden Gem - Few-Shot Representative Sampler
층화 추출로 few-shot 대표 예시를 뽑는다 (명작 편향 제거)

목적:
    교사 데이터(전체 merged jsonl)에서 few-shot 예시를 뽑되,
    gem_potential 분포를 골고루(하/중/상) + 장르 다양성을 확보한다.
    지금까지 쓰던 sample_10은 gem 95~100 명작만이라 few-shot용으로 편향됨.

입력 포맷 (각 줄 = 1 게임, sample_10_fixed.jsonl 과 동일 구조):
    {
      "metrics": {"vibe":{...}, "demands":{...}, "mechanics":{...},
                  "social":{...}, "presentation":{...}, "extended":{...18...},
                  "gem_potential": <0-100>},
      "tags": {...9...},
      "content": {...}, "reasoning": {"confidence_score": <0-1>, ...},
      "app_id": <int>, "name": "...", "genres": "장르1, 장르2", "description": "..."
    }

사용법:
    python fewshot_sampler.py \
        --input  data/merged/all_4190.jsonl \
        --output data/fewshot/fewshot_examples.jsonl \
        --n 24 --bins 6 --min-desc 80 --min-conf 0.6 --seed 42

    # 실측 검증(작게):
    python fewshot_sampler.py --input sample_10_fixed.jsonl \
        --output /tmp/fs_test.jsonl --n 6 --bins 3 --min-desc 0 --min-conf 0.0
"""

import os
import sys
import json
import random
import argparse
from pathlib import Path
from collections import Counter, defaultdict

# Numeric metric groups that must all be present for a "complete" gold example.
# 60지표 완전체 판정을 위한 수치 그룹 (합계 49개 필드)
NUMERIC_GROUPS = {
    "vibe": 7, "demands": 5, "mechanics": 9,
    "social": 5, "presentation": 5, "extended": 18,
}
TAG_COUNT = 9

# Non-game software present in the teacher corpus (~110 rows: Blender, OBS,
# VEGAS Pro...). They score low on gem_potential and hijack the low bins,
# teaching the student "low score == tool" instead of "low score == weak game".
# 교사 정본에 섞인 비게임 소프트웨어. gem이 낮아 저점 구간을 독식하므로 제외한다.
NON_GAME_GENRES = {
    "유틸리티", "애니메이션과 모델링", "디자인과 일러스트레이션",
    "게임 개발", "동영상 제작", "사진 편집", "웹 퍼블리싱",
    "오디오 제작", "소프트웨어 교육", "교육",
}


# ============== Loading & validation ==============
def load_records(path: Path):
    """Load jsonl, keep only structurally-complete 60-metric records.
    jsonl을 읽어 60지표 완전체 레코드만 남긴다 (깨진 줄/불완전 줄은 리포트)."""
    total = ok = bad_json = incomplete = mojibake = 0
    records = []
    C1 = set(range(0x80, 0xA0))   # double-encoding corruption signature

    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            total += 1
            # skip mojibake-tainted records so they never poison few-shot
            # 모지바케 손상 레코드는 few-shot 오염 방지를 위해 제외
            if any(ord(c) in C1 for c in line):
                mojibake += 1
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                bad_json += 1
                continue

            m = d.get("metrics", {})
            # verify every numeric group exists with the exact field count
            # 각 수치 그룹이 정확한 개수로 존재하는지 검증
            complete = all(
                isinstance(m.get(g), dict) and len(m.get(g)) == cnt
                for g, cnt in NUMERIC_GROUPS.items()
            )
            gem = m.get("gem_potential", d.get("gem_potential"))
            tags = d.get("tags", {})
            if not complete or gem is None or len(tags) != TAG_COUNT:
                incomplete += 1
                continue

            records.append(_summarize(d, line, gem))
            ok += 1

    print(f"  총 {total}줄 | 완전체 {ok} | JSON깨짐 {bad_json} | 불완전 {incomplete} | 모지바케제외 {mojibake}")
    return records


def _summarize(d: dict, raw_line: str, gem):
    """Attach the fields we sample on, keep the raw line for verbatim output.
    추출 기준 필드만 뽑고, 출력은 원본 줄을 그대로 보존한다."""
    genres_raw = (d.get("genres") or "").strip()
    genres = [g.strip() for g in genres_raw.split(",") if g.strip()]
    conf = (d.get("reasoning") or {}).get("confidence_score")
    return {
        "app_id": d.get("app_id"),
        "name": d.get("name") or "Unknown",
        "genres": genres,                       # list[str]
        "primary_genre": genres[0] if genres else "Unknown",
        "gem": float(gem),                      # 0-100 scale
        "conf": float(conf) if conf is not None else 0.0,
        "desc_len": len(d.get("description") or ""),
        "raw": raw_line,                        # verbatim line for output
    }


# ============== Filtering ==============
def apply_quality_filter(records, min_desc: int, min_conf: float, allow_software: bool):
    """Drop thin descriptions, low-confidence rows, and non-game software.
    설명 빈약·저신뢰·비게임 소프트웨어를 제외한다 (few-shot 품질 보호)."""
    kept, seen = [], set()
    dropped_sw = 0
    for r in records:
        if r["desc_len"] < min_desc:
            continue
        if r["conf"] < min_conf:
            continue
        # any non-game genre token disqualifies the row
        if not allow_software and (set(r["genres"]) & NON_GAME_GENRES):
            dropped_sw += 1
            continue
        if r["app_id"] in seen:          # dedupe by app_id
            continue
        seen.add(r["app_id"])
        kept.append(r)
    print(f"  품질필터 통과: {len(kept)} (min_desc={min_desc}, min_conf={min_conf})")
    if dropped_sw:
        print(f"  비게임 소프트웨어 제외: {dropped_sw}개")
    return kept


# ============== Stratified + genre-diverse selection ==============
def stratified_select(records, n: int, bins: int, seed: int):
    """Split gem_potential into `bins` equal-width buckets, take ~n/bins from
    each, greedily preferring unused genres and higher confidence.
    gem_potential을 등폭 bins로 나눠 각 구간에서 균등 추출하되,
    미사용 장르 우선 + 고신뢰 우선의 그리디로 다양성을 확보한다."""
    if not records:
        return []

    rng = random.Random(seed)

    # gem_potential is defined on a fixed 0-100 scale; bin over that, not over
    # the observed min/max (which skews bins toward the corpus mean of ~76).
    # gem_potential은 0-100 고정 스케일이므로 관측 min/max가 아닌 고정 구간으로 나눈다.
    lo, hi = 0.0, 100.0
    span = hi - lo

    # assign each record to a bin
    buckets = defaultdict(list)
    for r in records:
        idx = int((r["gem"] - lo) / span * bins)
        idx = min(idx, bins - 1)          # hi edge falls into last bin
        buckets[idx].append(r)

    per_bin = max(1, n // bins)
    used_genres = Counter()
    picked, picked_ids = [], set()

    # first pass: even quota per bin
    for b in range(bins):
        pool = buckets.get(b, [])
        rng.shuffle(pool)                 # deterministic shuffle for tie-break
        taken = 0
        used_gems = Counter()             # spread gem values *within* the bin
        # greedy: prefer unused gem values, then unused genres, then confidence
        while pool and taken < per_bin:
            pool.sort(key=lambda r: (
                used_gems[round(r["gem"])],            # avoid repeating same gem
                used_genres[r["primary_genre"]],       # then diversify genre
                -r["conf"],                            # then prefer confident
            ))
            r = pool.pop(0)
            if r["app_id"] in picked_ids:
                continue
            picked.append(r)
            picked_ids.add(r["app_id"])
            used_genres[r["primary_genre"]] += 1
            used_gems[round(r["gem"])] += 1
            taken += 1

    # second pass: fill remaining slots from the global leftover pool
    if len(picked) < n:
        leftover = [r for r in records if r["app_id"] not in picked_ids]
        leftover.sort(key=lambda r: (used_genres[r["primary_genre"]], -r["conf"]))
        for r in leftover:
            if len(picked) >= n:
                break
            picked.append(r)
            picked_ids.add(r["app_id"])
            used_genres[r["primary_genre"]] += 1

    return picked[:n]


# ============== Report ==============
def print_report(picked, bins):
    """Show gem distribution + genre spread so the selection is verifiable.
    선택 결과의 gem 분포·장르 분포를 출력해 눈으로 검증 가능하게 한다."""
    if not picked:
        print("  ⚠️ 선택된 예시 없음 — 필터가 너무 빡세거나 입력이 비었음")
        return
    print("\n  === 선택 결과 ===")
    gem_buckets = Counter()
    for r in sorted(picked, key=lambda r: r["gem"]):
        band = int(r["gem"] // 10) * 10
        gem_buckets[band] += 1
        print(f"    [{r['app_id']:>8}] gem={r['gem']:>5.1f} conf={r['conf']:.2f} "
              f"{r['primary_genre'][:12]:<12} {r['name'][:30]}")
    print("\n  gem 분포(10점 구간):",
          {f"{k}-{k+9}": v for k, v in sorted(gem_buckets.items())})
    print("  장르 분포:", dict(Counter(r["primary_genre"] for r in picked)))


# ============== Main ==============
def main():
    ap = argparse.ArgumentParser(description="Few-shot representative sampler")
    ap.add_argument("--input", required=True, help="전체 merged jsonl 경로")
    ap.add_argument("--output", required=True, help="few-shot 예시 출력 jsonl")
    ap.add_argument("--n", type=int, default=24, help="뽑을 예시 총 개수")
    ap.add_argument("--bins", type=int, default=6, help="gem_potential 층화 구간 수")
    ap.add_argument("--min-desc", type=int, default=80, help="description 최소 길이")
    ap.add_argument("--min-conf", type=float, default=0.6, help="confidence 최소값")
    ap.add_argument("--seed", type=int, default=42, help="결정론적 seed")
    ap.add_argument("--allow-software", action="store_true",
                    help="비게임 소프트웨어(유틸리티/영상편집 등)도 예시로 허용")
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"❌ 입력 없음: {in_path}")
        sys.exit(1)

    print("=" * 60)
    print("🎯 Few-Shot Representative Sampler")
    print("=" * 60)
    print(f"📂 입력: {in_path}")

    records = load_records(in_path)
    records = apply_quality_filter(records, args.min_desc, args.min_conf,
                                   allow_software=args.allow_software)
    picked = stratified_select(records, args.n, args.bins, args.seed)
    print_report(picked, args.bins)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in picked:
            f.write(r["raw"] + "\n")     # verbatim → 입력+출력 전체 보존

    print(f"\n✅ 저장: {out_path}  ({len(picked)}개)")
    print("=" * 60)


if __name__ == "__main__":
    main()