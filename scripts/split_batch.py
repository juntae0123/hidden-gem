#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import argparse
from pathlib import Path
from typing import List, Any

def split_jsonl(input_path: Path, output_dir: Path, chunk_size: int = 1000):
    output_dir.mkdir(parents=True, exist_ok=True)
    
    all_lines = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                all_lines.append(line.strip())
    
    total = len(all_lines)
    num_chunks = (total + chunk_size - 1) // chunk_size
    
    print(f"총 요청: {total}개")
    print(f"청크 크기: {chunk_size}개")
    print(f"생성될 파일: {num_chunks}개")
    
    created_files = []
    
    for i in range(num_chunks):
        start_idx = i * chunk_size
        end_idx = min((i + 1) * chunk_size, total)
        chunk = all_lines[start_idx:end_idx]
        
        output_file = output_dir / f"diet_batch_{i+1:03d}.jsonl"
        
        with open(output_file, "w", encoding="utf-8") as f:
            for line in chunk:
                f.write(line + "\n")
        
        file_size = output_file.stat().st_size / 1024
        print(f"  {output_file.name}: {len(chunk)}개 요청 ({file_size:.1f} KB)")
        created_files.append(output_file)
    
    print(f"\n분할 완료! {num_chunks}개 파일 생성됨")
    print(f"저장 위치: {output_dir}")
    
    return created_files


def main():
    parser = argparse.ArgumentParser(description="Batch 요청 파일 분할")
    parser.add_argument("--input", "-i", type=str, required=True, help="전체 요청 파일")
    parser.add_argument("--output-dir", "-o", type=str, default="batch_requests", help="출력 폴더")
    parser.add_argument("--chunk-size", "-c", type=int, default=1000, help="청크당 요청 수")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    
    if not input_path.exists():
        print(f"파일 없음: {input_path}")
        return 1
    
    split_jsonl(input_path, output_dir, args.chunk_size)
    return 0


if __name__ == "__main__":
    exit(main())
