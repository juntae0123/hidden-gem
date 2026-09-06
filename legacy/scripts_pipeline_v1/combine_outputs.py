#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
분할된 Batch 결과 파일 합치기 (Batch Output Combiner)

split_batch.py로 분할 제출한 여러 배치의 결과 JSONL 파일들을
하나의 파일로 합쳐 merge_metrics.py에서 처리할 수 있도록 준비.

Pipeline 위치:
    split_batch.py → submit_batches.py → check_batches.py
    → download_outputs.py → [combine_outputs.py] → merge_metrics.py

사용법:
    python scripts/combine_outputs.py -i batch_outputs/ -o batch_output_combined.jsonl
"""
import json
import argparse
from pathlib import Path


def main():
    """
    배치 출력 파일 통합 메인 로직 (Combine Batch Outputs)

    지정 디렉토리의 모든 .jsonl 파일을 알파벳 순서로 읽어
    빈 줄을 제거하고 단일 파일로 병합.
    """
    parser = argparse.ArgumentParser(description="분할된 Batch 결과 합치기")
    parser.add_argument("--input-dir", "-i", type=str, required=True, help="batch_outputs 폴더")
    parser.add_argument("--output", "-o", type=str, default="batch_output_combined.jsonl", help="합친 결과 파일")
    
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_path = Path(args.output)

    if not input_dir.exists():
        print(f"폴더 없음: {input_dir}")
        return 1

    # 알파벳 순 정렬로 output_001.jsonl → output_002.jsonl → ... 순서 보장
    output_files = sorted(input_dir.glob("*.jsonl"))

    if not output_files:
        print(f"jsonl 파일 없음: {input_dir}")
        return 1

    print(f"합칠 파일: {len(output_files)}개")
    for f in output_files:
        print(f"  - {f.name}")

    total_lines = 0

    with open(output_path, "w", encoding="utf-8") as f_out:
        for output_file in output_files:
            file_lines = 0
            with open(output_file, "r", encoding="utf-8") as f_in:
                for line in f_in:
                    if line.strip():  # 빈 줄 제거 후 쓰기
                        f_out.write(line.strip() + "\n")
                        file_lines += 1
                        total_lines += 1
            print(f"  {output_file.name}: {file_lines}개")

    file_size = output_path.stat().st_size / 1024 / 1024

    print(f"\n합치기 완료!")
    print(f"총 결과: {total_lines}개")
    print(f"파일 크기: {file_size:.2f} MB")
    print(f"저장 위치: {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())
