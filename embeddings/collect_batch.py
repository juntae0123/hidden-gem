"""
Stuck/완료 배치 수동 회수 도구.

배치가 일부 요청에서 몇 시간씩 멈추는 경우(straggler), 취소하면
완료된 요청까지의 결과는 output 파일로 받을 수 있다.

사용법:
    # 상태만 확인
    python -m embeddings.collect_batch batch_xxx

    # 취소 후 완료분(부분 결과) 다운로드
    python -m embeddings.collect_batch batch_xxx --cancel

    # 이미 completed/expired/cancelled면 그냥 다운로드
    python -m embeddings.collect_batch batch_xxx --download
"""

import sys
import time
import argparse
from datetime import datetime

from embeddings.batch_generator import client, DATA_DIR

TERMINAL = ("completed", "failed", "expired", "cancelled")


def download_output(batch) -> None:
    if not batch.output_file_id:
        print("output 파일 없음 — 완료된 요청이 0건이거나 아직 정리 중")
        return
    content = client.files.content(batch.output_file_id)
    path = DATA_DIR / f"batch_output_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    path.write_bytes(content.content)
    lines = sum(1 for _ in open(path, encoding='utf-8'))
    print(f"다운로드 완료: {path} ({lines}건)")
    print(f"다음 단계: python -m embeddings.batch_processor {path} --yes")
    if batch.error_file_id:
        print(f"(실패 요청 error file: {batch.error_file_id})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("batch_id")
    parser.add_argument("--cancel", action="store_true", help="취소 후 완료분 다운로드")
    parser.add_argument("--download", action="store_true", help="터미널 상태면 다운로드")
    args = parser.parse_args()

    batch = client.batches.retrieve(args.batch_id)
    rc = batch.request_counts
    print(f"상태: {batch.status} | {rc.completed}/{rc.total} 완료, {rc.failed} 실패")

    if args.cancel and batch.status not in TERMINAL:
        print("배치 취소 요청... (완료분은 보존됨)")
        client.batches.cancel(args.batch_id)
        # cancelling -> cancelled 까지 최대 ~10분
        for _ in range(60):
            time.sleep(15)
            batch = client.batches.retrieve(args.batch_id)
            rc = batch.request_counts
            print(f"   {batch.status} | {rc.completed}/{rc.total}")
            if batch.status in TERMINAL:
                break

    if batch.status in TERMINAL:
        download_output(batch)
    elif not args.cancel:
        print("아직 진행 중 — 취소하고 완료분만 받으려면 --cancel")


if __name__ == "__main__":
    main()
