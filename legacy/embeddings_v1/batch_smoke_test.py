"""
OpenAI Batch 최소 재현 테스트.

1줄짜리 초소형 배치를 제출해 "Cannot find file" 에러가
파일 크기/내용 문제인지, 키/프로젝트 권한 문제인지 가른다.

실행:
    docker compose exec batch python -m embeddings.batch_smoke_test
"""

import io
import json
import time

from embeddings.batch_generator import client


def main() -> None:
    # 1. 키가 보는 스코프 확인
    me = client.models.list()
    print(f"[1] 모델 목록 조회 OK ({len(me.data)}개) — 키 인증 정상")

    # 2. 1줄짜리 배치 입력 업로드
    line = json.dumps({
        "custom_id": "smoke-1",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {"model": "gpt-4o-mini", "max_tokens": 5,
                 "messages": [{"role": "user", "content": "hi"}]},
    })
    f = client.files.create(file=("smoke.jsonl", io.BytesIO(line.encode())), purpose="batch")
    print(f"[2] 업로드 OK: {f.id}")

    for _ in range(24):
        info = client.files.retrieve(f.id)
        if getattr(info, "status", "processed") == "processed":
            break
        time.sleep(5)
    print(f"[3] 파일 상태: {getattr(info, 'status', '?')}, bytes={info.bytes}")

    # 3. 배치 생성 + 3분 폴링
    batch = client.batches.create(input_file_id=f.id,
                                  endpoint="/v1/chat/completions",
                                  completion_window="24h")
    print(f"[4] 배치 생성: {batch.id} ({batch.status})")

    for _ in range(12):
        time.sleep(15)
        b = client.batches.retrieve(batch.id)
        print(f"    {b.status} | {b.request_counts.completed}/{b.request_counts.total}")
        if b.status in ("completed", "failed", "expired", "cancelled"):
            break

    if b.status == "failed" and b.errors and getattr(b.errors, "data", None):
        print("[5] 실패 원인:")
        for e in b.errors.data[:5]:
            print(f"    - [{getattr(e, 'code', '?')}] {getattr(e, 'message', e)}")
    elif b.status == "completed":
        print("[5] 초소형 배치 성공 — 키/권한 정상, 원본 파일 쪽 문제로 좁혀짐")


if __name__ == "__main__":
    main()
