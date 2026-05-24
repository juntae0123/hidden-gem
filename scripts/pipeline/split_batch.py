#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch 요청 파일 분할 스크립트 (Batch Request File Splitter)

make_diet_batch.py가 생성한 단일 JSONL 파일을 OpenAI Batch API 제한에 맞게 분할.
OpenAI Batch API는 파일당 최대 50,000 요청 / 100MB 제한이 있음.

사용법:
    python scripts/split_batch.py -i diet_batch_requests.jsonl -o batch_requests/ -c 1000

Pipeline 위치:
    make_diet_batch.py → [split_batch.py] → submit_batches.py
"""
import json
import argparse
from pathlib import Path
from typing import List, Any


def split_jsonl(input_path: Path, output_dir: Path, chunk_size: int = 1000):
    """
    JSONL 파일을 chunk_size 단위로 분할 (JSONL File Splitter)

    파일을 전부 메모리에 읽은 뒤 청크 단위로 diet_batch_NNN.jsonl 파일로 저장.
    파일명은 3자리 제로패딩 (diet_batch_001.jsonl, ...) → 정렬 보장.

    Args:
        input_path: 분할할 원본 JSONL 파일
        output_dir: 분할 파일 저장 디렉토리
        chunk_size: 파일당 최대 요청 수 (기본 1,000)

    Returns:
        생성된 파일 경로 리스트
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    all_lines = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                all_lines.append(line.strip())

    total = len(all_lines)
    # 올림 나눗셈으로 마지막 청크까지 포함
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
