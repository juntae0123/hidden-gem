#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
병합 결과 검증 스크립트 (Merge Validation Script)

merge_metrics.py가 생성한 final_master_games.jsonl의 데이터 완전성을 검증.
무작위 샘플 출력 + 전체 통계 리포트로 지표 결측치 현황 파악.

검증 항목:
    - 기존 31개 지표 존재 여부 (vibe/demands/mechanics 등)
    - 신규 18개 지표 존재 여부 (extended)
    - 완전 병합(Batch 결과 있음) vs 중립값 채움 비율

사용법:
    python scripts/validate_merge.py -i final_master_games.jsonl
    python scripts/validate_merge.py -i final_master_games.jsonl --detailed
"""
import json
import argparse
import random
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import defaultdict

ORIGINAL_NUMERIC_METRICS: List[str] = [
    "cozy_factor",
    "horror_factor",
    "gore_level",
    "humor_rating",
    "dark_fantasy_vibe",
    "epic_scale",
    "melancholy",
    "reflex_demand",
    "strategic_depth",
    "grind_factor",
    "time_pressure",
    "learning_curve",
    "freedom_level",
    "action_pacing",
    "rng_dependency",
    "growth_reward",
    "exploration_reward",
    "management_complexity",
    "stealth_importance",
    "session_length",
    "narrative_linearity",
    "coop_synergy",
    "competitive_stress",
    "npc_interaction",
    "user_creation",
    "multiplayer_scale",
    "lore_richness",
    "choice_consequence",
    "visual_spectacle",
    "environmental_storytelling",
    "soundtrack_impact",
]

NEW_METRICS: List[str] = [
    "build_variety",
    "progression_clarity",
    "save_flexibility",
    "difficulty_accessibility",
    "tutorial_quality",
    "ui_ux_polish",
    "modding_support",
    "art_style_uniqueness",
    "audio_design",
    "animation_quality",
    "puzzle_complexity",
    "platforming_precision",
    "world_reactivity",
    "community_dependency",
    "narrative_depth",
    "replay_value",
    "endgame_content",
    "monetization_fairness",
]

ALL_NUMERIC_METRICS: List[str] = ORIGINAL_NUMERIC_METRICS + NEW_METRICS

BOOLEAN_TAGS: List[str] = [
    "is_turn_based",
    "is_real_time",
    "is_first_person",
    "is_third_person",
    "has_permadeath",
    "has_base_building",
    "has_crafting",
    "is_anime_style",
    "is_retro_aesthetic",
]

ORIGINAL_CATEGORIES: Dict[str, List[str]] = {
    "vibe": ["cozy_factor", "horror_factor", "gore_level", "humor_rating", "dark_fantasy_vibe", "epic_scale", "melancholy"],
    "demands": ["reflex_demand", "strategic_depth", "grind_factor", "time_pressure", "learning_curve"],
    "mechanics": ["freedom_level", "action_pacing", "rng_dependency", "growth_reward", "exploration_reward", "management_complexity", "stealth_importance", "session_length", "narrative_linearity"],
    "social": ["coop_synergy", "competitive_stress", "npc_interaction", "user_creation", "multiplayer_scale"],
    "presentation": ["lore_richness", "choice_consequence", "visual_spectacle", "environmental_storytelling", "soundtrack_impact"],
}


def extract_all_metrics(data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    게임 데이터에서 기존/신규 지표를 분리 추출 (Metric Extraction Helper)

    Args:
        data: 게임 JSONL 레코드 딕셔너리

    Returns:
        (original, new) 튜플:
            original = {지표명: 값} - 기존 31개 지표 (카테고리별 평탄화)
            new = {지표명: 값}       - 신규 18개 지표 (metrics.extended에서 추출)
    """
    metrics = data.get("metrics", {})

    # 기존 31개: vibe/demands/mechanics/social/presentation 카테고리에서 평탄화
    original = {}
    for category, metric_names in ORIGINAL_CATEGORIES.items():
        category_data = metrics.get(category, {})
        for name in metric_names:
            original[name] = category_data.get(name)

    # 신규 18개: metrics.extended 하위에 위치 (merge_metrics.py가 이 위치에 저장)
    extended = metrics.get("extended", {})
    new = {}
    for name in NEW_METRICS:
        new[name] = extended.get(name)

    return original, new


def print_sample(data: Dict[str, Any], sample_num: int):
    app_id = data.get("app_id", "N/A")
    name = data.get("name", "Unknown")[:40]
    
    original, new = extract_all_metrics(data)
    
    original_filled = sum(1 for v in original.values() if v is not None)
    new_filled = sum(1 for v in new.values() if v is not None)
    total_filled = original_filled + new_filled
    
    merge_meta = data.get("_merge_meta", {})
    has_extended = merge_meta.get("has_extended_metrics", False)
    
    print(f"\n{'='*60}")
    print(f"샘플 #{sample_num}: [{app_id}] {name}")
    print(f"{'='*60}")
    print(f"수치 지표 카운트:")
    if original_filled == 31:
        print(f"  기존 31개: {original_filled}/31 OK")
    else:
        print(f"  기존 31개: {original_filled}/31 WARNING")
    if new_filled == 18:
        print(f"  신규 18개: {new_filled}/18 OK")
    else:
        print(f"  신규 18개: {new_filled}/18 WARNING")
    if total_filled == 49:
        print(f"  총합 49개: {total_filled}/49 OK")
    else:
        print(f"  총합 49개: {total_filled}/49 FAIL")
    
    if has_extended:
        print(f"Batch 병합 상태: 완전 병합")
    else:
        print(f"Batch 병합 상태: 중립값 채움")
    
    print(f"\n기존 지표 샘플 (VIBE):")
    for name in ORIGINAL_CATEGORIES["vibe"][:4]:
        value = original.get(name)
        print(f"  {name}: {value}")
    
    print(f"\n신규 지표 샘플 (EXTENDED):")
    for name in NEW_METRICS[:4]:
        value = new.get(name)
        print(f"  {name}: {value}")


def generate_report(all_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    전체 데이터에 대한 검증 통계 리포트 생성 (Validation Report Generator)

    complete_merge(실제 배치 결과) vs filled_merge(중립값) 비율과
    지표별 결측치 카운트를 집계하여 반환.

    Args:
        all_data: 전체 게임 레코드 리스트

    Returns:
        통계 딕셔너리 {total_count, complete_merge, perfect_games, original_nulls, ...}
    """
    total_count = len(all_data)
    
    original_nulls: Dict[str, int] = defaultdict(int)
    new_nulls: Dict[str, int] = defaultdict(int)
    tag_nulls: Dict[str, int] = defaultdict(int)
    
    complete_merge = 0
    filled_merge = 0
    perfect_games = 0
    
    for data in all_data:
        original, new = extract_all_metrics(data)
        tags = data.get("tags", {})
        merge_meta = data.get("_merge_meta", {})
        
        if merge_meta.get("has_extended_metrics", False):
            complete_merge += 1
        else:
            filled_merge += 1
        
        for name in ORIGINAL_NUMERIC_METRICS:
            if original.get(name) is None:
                original_nulls[name] += 1
        
        for name in NEW_METRICS:
            if new.get(name) is None:
                new_nulls[name] += 1
        
        for name in BOOLEAN_TAGS:
            if name not in tags:
                tag_nulls[name] += 1
        
        original_filled = sum(1 for v in original.values() if v is not None)
        new_filled = sum(1 for v in new.values() if v is not None)
        if original_filled == 31 and new_filled == 18:
            perfect_games += 1
    
    return {
        "total_count": total_count,
        "complete_merge": complete_merge,
        "filled_merge": filled_merge,
        "perfect_games": perfect_games,
        "original_nulls": dict(original_nulls),
        "new_nulls": dict(new_nulls),
        "tag_nulls": dict(tag_nulls),
    }


def print_report(report: Dict[str, Any]):
    total = report["total_count"]
    complete = report["complete_merge"]
    filled = report["filled_merge"]
    perfect = report["perfect_games"]
    
    print(f"\n{'='*60}")
    print(f"병합 검증 리포트")
    print(f"{'='*60}")
    print(f"전체 게임 수: {total:,}개")
    print(f"\n병합 상태:")
    print(f"  완전 병합 (Batch 결과 있음): {complete:,}개 ({complete/total*100:.1f}%)")
    print(f"  중립값 채움 (Batch 결과 없음): {filled:,}개 ({filled/total*100:.1f}%)")
    print(f"\n완벽한 게임 (49개 지표 모두 존재): {perfect:,}개 ({perfect/total*100:.1f}%)")
    
    print(f"\n기존 31개 지표 결측치:")
    original_nulls = report["original_nulls"]
    if original_nulls:
        sorted_nulls = sorted(original_nulls.items(), key=lambda x: x[1], reverse=True)
        for name, count in sorted_nulls[:5]:
            pct = count / total * 100
            print(f"  {name}: {count:,}개 ({pct:.1f}%)")
        if len(sorted_nulls) > 5:
            print(f"  ... 외 {len(sorted_nulls) - 5}개")
    else:
        print(f"  결측치 없음!")
    
    print(f"\n신규 18개 지표 결측치:")
    new_nulls = report["new_nulls"]
    if new_nulls:
        sorted_nulls = sorted(new_nulls.items(), key=lambda x: x[1], reverse=True)
        for name, count in sorted_nulls[:5]:
            pct = count / total * 100
            print(f"  {name}: {count:,}개 ({pct:.1f}%)")
        if len(sorted_nulls) > 5:
            print(f"  ... 외 {len(sorted_nulls) - 5}개")
    else:
        print(f"  결측치 없음!")
    
    print(f"\n최종 판정:")
    if perfect == total:
        print(f"  완벽! 모든 게임이 49개 지표를 보유!")
    elif perfect / total >= 0.95:
        print(f"  우수! 95% 이상의 게임이 완전함")
    elif perfect / total >= 0.80:
        print(f"  양호. 일부 게임에 결측치 있음")
    else:
        print(f"  주의! 상당수 게임에 결측치 존재")


def main():
    """
    병합 검증 메인 로직 (Validation Main)

    JSONL을 전부 메모리에 로드 후 무작위 샘플 출력 → 전체 리포트 순으로 실행.
    --detailed 옵션으로 49개 지표 전체의 결측치 현황을 상세 출력.
    """
    parser = argparse.ArgumentParser(description="병합된 마스터 파일 검증")
    parser.add_argument("--input", "-i", type=str, required=True, help="final_master_games.jsonl 경로")
    parser.add_argument("--samples", "-s", type=int, default=3, help="출력할 샘플 수")
    parser.add_argument("--detailed", action="store_true", help="상세 결측치 리포트 출력")
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if not input_path.exists():
        print(f"파일 없음: {input_path}")
        return 1
    
    print(f"입력: {input_path}")
    print(f"예상 지표: 수치 49개 + 태그 9개 = 60개")
    
    print("\n데이터 로딩...")
    all_data = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    all_data.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    
    print(f"로드 완료: {len(all_data):,}개 게임")
    
    random.seed(args.seed)
    sample_indices = random.sample(range(len(all_data)), min(args.samples, len(all_data)))
    
    print(f"\n무작위 샘플 {args.samples}개 검증")
    
    for i, idx in enumerate(sample_indices, 1):
        print_sample(all_data[idx], i)
    
    report = generate_report(all_data)
    print_report(report)
    
    if args.detailed:
        print(f"\n{'='*60}")
        print(f"상세 결측치 목록")
        print(f"{'='*60}")
        
        print("\n기존 31개 지표:")
        for name in ORIGINAL_NUMERIC_METRICS:
            count = report["original_nulls"].get(name, 0)
            if count == 0:
                status = "OK"
            else:
                status = f"{count:,}개 결측"
            print(f"  {name}: {status}")
        
        print("\n신규 18개 지표:")
        for name in NEW_METRICS:
            count = report["new_nulls"].get(name, 0)
            if count == 0:
                status = "OK"
            else:
                status = f"{count:,}개 결측"
            print(f"  {name}: {status}")
    
    return 0


if __name__ == "__main__":
    exit(main())
