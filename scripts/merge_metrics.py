#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

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

EVAL_METRICS: List[str] = [
    "gem_potential",
    "confidence_score",
]

assert len(ORIGINAL_NUMERIC_METRICS) == 31
assert len(NEW_METRICS) == 18
assert len(ALL_NUMERIC_METRICS) == 49


def parse_batch_output(batch_path: Path) -> Dict[int, Dict[str, Any]]:
    batch_results: Dict[int, Dict[str, Any]] = {}
    errors = 0
    
    with open(batch_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            
            try:
                record = json.loads(line)
                
                custom_id = record.get("custom_id", "")
                if not custom_id.startswith("diet-"):
                    errors += 1
                    continue
                
                app_id = int(custom_id.replace("diet-", ""))
                
                response = record.get("response", {})
                body = response.get("body", {})
                choices = body.get("choices", [])
                
                if not choices:
                    errors += 1
                    continue
                
                content = choices[0].get("message", {}).get("content", "")
                
                if not content:
                    errors += 1
                    continue
                
                try:
                    metrics = json.loads(content)
                    
                    valid_metrics = {}
                    for metric_name in NEW_METRICS:
                        value = metrics.get(metric_name)
                        if value is not None:
                            try:
                                valid_metrics[metric_name] = float(value)
                            except (ValueError, TypeError):
                                valid_metrics[metric_name] = 5.0
                        else:
                            valid_metrics[metric_name] = 5.0
                    
                    batch_results[app_id] = valid_metrics
                    
                except json.JSONDecodeError:
                    errors += 1
                    
            except Exception as e:
                errors += 1
    
    print(f"Batch 결과 파싱: {len(batch_results)}개 성공, {errors}개 에러")
    return batch_results


def merge_game_data(original: Dict[str, Any], new_metrics: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = original.copy()
    
    if "metrics" not in merged:
        merged["metrics"] = {}
    
    if new_metrics:
        merged["metrics"]["extended"] = new_metrics
    else:
        merged["metrics"]["extended"] = {metric: 5.0 for metric in NEW_METRICS}
    
    merged["_merge_meta"] = {
        "merged_at": datetime.utcnow().isoformat(),
        "has_extended_metrics": new_metrics is not None,
        "extended_metrics_count": len(new_metrics) if new_metrics else 0,
    }
    
    return merged


def main():
    parser = argparse.ArgumentParser(description="기존 42개 지표 + 신규 18개 지표 병합")
    parser.add_argument("--original", "-o", type=str, required=True, help="기존 merged_games.jsonl 경로")
    parser.add_argument("--batch", "-b", type=str, required=True, help="Batch 출력 파일 경로")
    parser.add_argument("--output", "-out", type=str, default="final_master_games.jsonl", help="출력 마스터 파일 경로")
    parser.add_argument("--fill-missing", action="store_true", default=True, help="Batch 결과 없는 게임도 중립값으로 포함")
    
    args = parser.parse_args()
    
    original_path = Path(args.original)
    batch_path = Path(args.batch)
    output_path = Path(args.output)
    
    if not original_path.exists():
        print(f"원본 파일 없음: {original_path}")
        return 1
    
    if not batch_path.exists():
        print(f"Batch 출력 파일 없음: {batch_path}")
        return 1
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"원본 (42개 지표): {original_path}")
    print(f"Batch (18개 지표): {batch_path}")
    print(f"출력 (60개 지표): {output_path}")
    
    print("\nStep 1: Batch 결과 파싱...")
    batch_results = parse_batch_output(batch_path)
    
    print("\nStep 2: 데이터 병합...")
    
    merged_count = 0
    missing_count = 0
    total_count = 0
    
    with open(original_path, "r", encoding="utf-8") as f_in:
        with open(output_path, "w", encoding="utf-8") as f_out:
            for line in f_in:
                if not line.strip():
                    continue
                
                try:
                    original_data = json.loads(line)
                    app_id = original_data.get("app_id")
                    
                    if not app_id:
                        continue
                    
                    total_count += 1
                    
                    new_metrics = batch_results.get(app_id)
                    
                    if new_metrics:
                        merged_count += 1
                    else:
                        missing_count += 1
                        if not args.fill_missing:
                            continue
                    
                    merged_data = merge_game_data(original_data, new_metrics)
                    
                    f_out.write(json.dumps(merged_data, ensure_ascii=False) + "\n")
                    
                    if total_count % 500 == 0:
                        print(f"  처리 중... {total_count}개")
                        
                except Exception as e:
                    print(f"처리 실패: {e}")
    
    output_size = output_path.stat().st_size / 1024 / 1024
    
    print(f"\n병합 완료!")
    print(f"전체 게임: {total_count}개")
    print(f"완전 병합: {merged_count}개 ({merged_count/total_count*100:.1f}%)")
    print(f"중립값 채움: {missing_count}개 ({missing_count/total_count*100:.1f}%)")
    print(f"파일 크기: {output_size:.2f} MB")
    print(f"출력 파일: {output_path}")
    
    return 0


if __name__ == "__main__":
    exit(main())
