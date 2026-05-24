#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenAI Batch API 결과 다운로드 스크립트 (Batch Output Downloader)

check_batches.py 실행 후 output_file_id가 채워진 batch_jobs.json을 기반으로
완료된 배치의 결과 파일을 로컬 폴더에 저장.
미완료(status != completed) 배치는 건너뜀.

사용법:
    python scripts/download_outputs.py
    python scripts/download_outputs.py --jobs batch_jobs.json --output-dir batch_outputs/

Pipeline 위치:
    submit_batches.py → check_batches.py → [download_outputs.py] → combine_outputs.py
"""
import json
import os
import argparse
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("OPENAI_API_KEY 없음!")
    exit(1)

from openai import OpenAI


def main():
    """
    배치 결과 다운로드 메인 로직 (Download Batch Outputs)

    batch_jobs.json의 각 항목에서 batch_id를 조회하고,
    completed 상태의 배치만 output_NNN.jsonl 형식으로 저장.
    """
    parser = argparse.ArgumentParser(description="Batch 결과 다운로드")
    parser.add_argument("--jobs", "-j", type=str, default="batch_jobs.json", help="배치 작업 정보 파일")
    parser.add_argument("--output-dir", "-o", type=str, default="batch_outputs", help="결과 저장 폴더")
    
    args = parser.parse_args()
    
    jobs_path = Path(args.jobs)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not jobs_path.exists():
        print(f"파일 없음: {jobs_path}")
        return 1
    
    with open(jobs_path, "r", encoding="utf-8") as f:
        jobs = json.load(f)
    
    client = OpenAI(api_key=api_key)
    
    print(f"결과 다운로드 ({len(jobs)}개)")
    print("=" * 70)
    
    downloaded = 0
    
    for i, job in enumerate(jobs):
        batch_id = job.get("batch_id")
        if not batch_id:
            print(f"{job['file_name']}: batch_id 없음")
            continue
        
        try:
            batch = client.batches.retrieve(batch_id)
            
            if batch.status != "completed":
                print(f"{job['file_name']}: 아직 완료되지 않음 ({batch.status})")
                continue
            
            output_file_id = batch.output_file_id
            if not output_file_id:
                print(f"{job['file_name']}: output_file_id 없음")
                continue
            
            file_content = client.files.content(output_file_id)
            
            output_name = f"output_{i+1:03d}.jsonl"
            output_path = output_dir / output_name
            
            with open(output_path, "wb") as f:
                f.write(file_content.content)
            
            file_size = output_path.stat().st_size / 1024
            print(f"{job['file_name']} -> {output_name} ({file_size:.1f} KB)")
            downloaded += 1
            
        except Exception as e:
            print(f"{job['file_name']}: 다운로드 실패 - {e}")
    
    print("=" * 70)
    print(f"다운로드 완료: {downloaded}/{len(jobs)}개")
    print(f"저장 위치: {output_dir}")
    
    return 0


if __name__ == "__main__":
    exit(main())
