#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenAI Batch API 제출 스크립트 (Batch Submission Script)

split_batch.py로 분할된 diet_batch_NNN.jsonl 파일들을
OpenAI Batch API에 순서대로 제출하고 배치 ID를 batch_jobs.json에 저장.

Batch API 특징:
    - 24시간 완료 보장 (completion_window="24h")
    - 동기 API 대비 50% 비용 절감
    - 제출 간 delay로 레이트 리밋 방지

사용법:
    python scripts/submit_batches.py -i batch_requests/ -o batch_jobs.json

Pipeline 위치:
    make_diet_batch.py → split_batch.py → [submit_batches.py] → check_batches.py
"""
import json
import time
import os
import argparse
from pathlib import Path
from dotenv import load_dotenv

# .env 로드 (여러 경로 시도)
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

# 환경변수 확인
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("OPENAI_API_KEY 환경변수가 없습니다!")
    print(f".env 파일 위치: {project_root / '.env'}")
    print(f"파일 존재 여부: {(project_root / '.env').exists()}")
    exit(1)

from openai import OpenAI


def submit_batch(client: OpenAI, file_path: Path) -> dict:
    """
    단일 JSONL 파일을 OpenAI Batch API에 제출 (Single Batch Submission)

    파일 업로드 → 배치 생성 두 단계로 처리.
    업로드된 파일은 OpenAI Files API에 보관되며 배치 ID로 추적.

    Args:
        client: OpenAI 클라이언트 인스턴스
        file_path: 제출할 diet_batch_NNN.jsonl 파일 경로

    Returns:
        {file_name, file_id, batch_id, status} 딕셔너리
        이후 check_batches.py에서 batch_id로 상태 조회
    """
    print(f"\n파일 업로드 중: {file_path.name}")

    # 1단계: 파일을 OpenAI Files API에 업로드 (purpose="batch" 필수)
    with open(file_path, "rb") as f:
        uploaded_file = client.files.create(file=f, purpose="batch")

    print(f"  파일 ID: {uploaded_file.id}")

    # 2단계: 업로드된 파일로 배치 작업 생성
    batch = client.batches.create(
        input_file_id=uploaded_file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",  # 최대 24시간 내 완료 보장
        metadata={"description": f"Hidden Gem Diet Batch - {file_path.name}"}
    )

    print(f"  배치 ID: {batch.id}")
    print(f"  상태: {batch.status}")

    return {
        "file_name": file_path.name,
        "file_id": uploaded_file.id,
        "batch_id": batch.id,
        "status": batch.status
    }


def main():
    """
    배치 파일 일괄 제출 메인 로직 (Batch Files Submission Main)

    batch_requests/ 폴더의 diet_batch_*.jsonl 파일을 순서대로 제출.
    제출 전 확인 프롬프트로 실수 방지, 제출 간 delay로 레이트 리밋 대응.
    """
    parser = argparse.ArgumentParser(description="분할된 Batch 파일들 제출")
    parser.add_argument("--input-dir", "-i", type=str, required=True, help="batch_requests 폴더")
    parser.add_argument("--output", "-o", type=str, default="batch_jobs.json", help="배치 작업 정보 저장 파일")
    parser.add_argument("--delay", "-d", type=int, default=5, help="제출 간 대기 시간 (초)")
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    
    if not input_dir.exists():
        print(f"폴더 없음: {input_dir}")
        return 1
    
    batch_files = sorted(input_dir.glob("diet_batch_*.jsonl"))
    
    if not batch_files:
        print(f"batch 파일 없음: {input_dir}")
        return 1
    
    print(f"제출할 파일: {len(batch_files)}개")
    for bf in batch_files:
        print(f"  - {bf.name}")
    
    confirm = input("\n제출하시겠습니까? (y/n): ")
    if confirm.lower() != "y":
        print("취소됨")
        return 0
    
    client = OpenAI(api_key=api_key)
    
    results = []
    
    for i, batch_file in enumerate(batch_files):
        print(f"\n[{i+1}/{len(batch_files)}] 처리 중...")
        
        try:
            result = submit_batch(client, batch_file)
            results.append(result)
        except Exception as e:
            print(f"  오류 발생: {e}")
            results.append({
                "file_name": batch_file.name,
                "error": str(e)
            })
        
        if i < len(batch_files) - 1:
            print(f"  {args.delay}초 대기...")
            time.sleep(args.delay)
    
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n제출 완료!")
    print(f"배치 작업 정보 저장됨: {args.output}")
    
    return 0


if __name__ == "__main__":
    exit(main())
