#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenAI Batch API 상태 확인 스크립트 (Batch Status Checker)

submit_batches.py로 제출한 배치 작업들의 현재 상태를 폴링하고
완료된 배치의 output_file_id를 batch_jobs.json에 기록.

사용법:
    python scripts/check_batches.py
    python scripts/check_batches.py --jobs custom_jobs.json

상태 종류:
    completed  - 완료 (output_file_id 기록됨)
    in_progress/validating - 처리 중 (done/total 진행률 표시)
    failed/cancelled - 실패 또는 취소
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
    배치 상태 확인 메인 로직 (Batch Status Check Main)

    batch_jobs.json의 모든 배치 ID에 대해 OpenAI API로 상태를 조회하고
    완료된 배치의 output_file_id를 jobs 파일에 저장.
    실행 후 output_file_id가 채워진 파일로 download_outputs.py 실행 가능.
    """
    parser = argparse.ArgumentParser(description="Batch 상태 확인")
    parser.add_argument("--jobs", "-j", type=str, default="batch_jobs.json", help="배치 작업 정보 파일")

    args = parser.parse_args()

    jobs_path = Path(args.jobs)

    if not jobs_path.exists():
        print(f"파일 없음: {jobs_path}")
        return 1

    with open(jobs_path, "r", encoding="utf-8") as f:
        jobs = json.load(f)

    client = OpenAI(api_key=api_key)

    print(f"배치 상태 확인 ({len(jobs)}개)")
    print("=" * 70)

    completed = 0
    failed = 0
    in_progress = 0

    for job in jobs:
        if "batch_id" not in job:
            # batch_id 없는 레코드는 제출 자체가 실패한 케이스
            print(f"{job['file_name']}: 오류 - {job.get('error', 'unknown')}")
            failed += 1
            continue

        try:
            batch = client.batches.retrieve(job["batch_id"])
            status = batch.status

            if status == "completed":
                completed += 1
                output_file_id = batch.output_file_id
                print(f"{job['file_name']}: 완료 (output: {output_file_id})")
                job["output_file_id"] = output_file_id  # 이후 다운로드에 사용
            elif status == "failed":
                failed += 1
                print(f"{job['file_name']}: 실패")
            elif status == "cancelled":
                failed += 1
                print(f"{job['file_name']}: 취소됨")
            else:
                # in_progress, validating 등 처리 중 상태 - 진행률 표시
                in_progress += 1
                request_counts = batch.request_counts
                done = request_counts.completed if request_counts else 0
                total = request_counts.total if request_counts else 0
                print(f"{job['file_name']}: {status} ({done}/{total})")

            job["status"] = status  # 현재 상태를 jobs 파일에 반영

        except Exception as e:
            print(f"{job['file_name']}: 확인 실패 - {e}")
            failed += 1

    print("=" * 70)
    print(f"완료: {completed}, 진행중: {in_progress}, 실패/취소: {failed}")

    # 상태 업데이트된 jobs 파일 덮어쓰기
    with open(jobs_path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)

    if completed == len(jobs):
        print("\n모든 배치 완료!")

    return 0


if __name__ == "__main__":
    exit(main())
