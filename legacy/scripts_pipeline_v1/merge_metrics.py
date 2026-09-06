#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
기존 31개 지표 + 신규 18개 지표 병합 스크립트 (Metrics Merge Script)

GPT-5.4 배치로 추출한 원본 42개 지표 데이터(merged_games.jsonl)와
신규 18개 지표 배치 결과(batch_output_combined.jsonl)를 병합하여
60개 지표 마스터 파일(final_master_games.jsonl)을 생성.

병합 전략:
    - 배치 결과 있음: 실제 18개 신규 지표를 metrics.extended에 추가
    - 배치 결과 없음: 18개 신규 지표를 5.0(중립값)으로 채움 (--fill-missing 기본값)

사용법:
    python scripts/merge_metrics.py -o merged_games.jsonl -b batch_output_combined.jsonl

Pipeline 위치:
    combine_outputs.py → [merge_metrics.py] → fix_data.py → load_games.py
"""
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
    """
    OpenAI Batch API 응답 JSONL 파싱 (Batch Output Parser)

    배치 응답 레코드에서 custom_id(diet-{app_id})로 app_id를 추출하고
    GPT가 생성한 18개 신규 지표 JSON을 파싱.
    파싱 실패 또는 값 없는 지표는 5.0(중립값)으로 대체.

    Args:
        batch_path: 합쳐진 배치 출력 JSONL 파일 경로

    Returns:
        {app_id: {지표명: 값}} 딕셔너리
    """
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

                # custom_id = "diet-{app_id}" 형식으로 app_id 추출
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

                    # 18개 지표 각각 float 변환 + 실패 시 중립값 5.0으로 폴백
                    valid_metrics = {}
                    for metric_name in NEW_METRICS:
                        value = metrics.get(metric_name)
                        if value is not None:
                            try:
                                valid_metrics[metric_name] = float(value)
                            except (ValueError, TypeError):
                                valid_metrics[metric_name] = 5.0  # 변환 실패 → 중립값
                        else:
                            valid_metrics[metric_name] = 5.0  # 누락 → 중립값

                    batch_results[app_id] = valid_metrics

                except json.JSONDecodeError:
                    errors += 1

            except Exception as e:
                errors += 1

    print(f"Batch 결과 파싱: {len(batch_results)}개 성공, {errors}개 에러")
    return batch_results


def merge_game_data(original: Dict[str, Any], new_metrics: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    원본 게임 데이터에 신규 18개 지표 병합 (Merge Game Data)

    원본 딕셔너리를 복사하고 metrics.extended 하위에 18개 신규 지표를 추가.
    메타데이터(_merge_meta)로 병합 시각과 완전 병합 여부를 기록.

    Args:
        original: 원본 게임 JSONL 레코드 딕셔너리
        new_metrics: 배치에서 파싱한 18개 신규 지표 (없으면 None)

    Returns:
        병합된 게임 딕셔너리 (metrics.extended + _merge_meta 추가됨)
    """
    merged = original.copy()

    if "metrics" not in merged:
        merged["metrics"] = {}

    if new_metrics:
        merged["metrics"]["extended"] = new_metrics  # 실제 배치 결과
    else:
        # 배치 결과 없는 게임: 18개 지표를 중립값으로 채워 60개 구조 유지
        merged["metrics"]["extended"] = {metric: 5.0 for metric in NEW_METRICS}

    # 병합 추적 메타데이터 (validate_merge.py에서 활용)
    merged["_merge_meta"] = {
        "merged_at": datetime.utcnow().isoformat(),
        "has_extended_metrics": new_metrics is not None,  # True = 실제 배치 결과 있음
        "extended_metrics_count": len(new_metrics) if new_metrics else 0,
    }

    return merged


def main():
    """
    지표 병합 메인 로직 (Metrics Merge Main)

    원본 파일을 라인별로 스트리밍 처리하여 메모리 효율적으로 병합.
    배치 결과 없는 게임도 --fill-missing(기본 True)으로 포함하여
    최종 마스터 파일이 원본과 동일한 게임 수를 유지.
    """
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
