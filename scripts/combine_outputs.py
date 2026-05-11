#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="분할된 Batch 결과 합치기")
    parser.add_argument("--input-dir", "-i", type=str, required=True, help="batch_outputs 폴더")
    parser.add_argument("--output", "-o", type=str, default="batch_output_combined.jsonl", help="합친 결과 파일")
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    output_path = Path(args.output)
    
    if not input_dir.exists():
        print(f"폴더 없음: {input_dir}")
        return 1
    
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
                    if line.strip():
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
