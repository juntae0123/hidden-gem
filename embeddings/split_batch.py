import os
from pathlib import Path

# 1. 경로 설정 (현재 파일의 위치를 기준으로 상위 폴더의 data를 찾음)
# embeddings/split_batch.py 기준 -> 상위로 가서 data 폴더 탐색
current_file_path = Path(__file__).resolve()
project_root = current_file_path.parent.parent
data_dir = project_root / "data"

print(f"📂 프로젝트 루트: {project_root}")
print(f"🔍 탐색 중인 폴더: {data_dir.absolute()}")

# 2. data 폴더 확인
if not data_dir.exists():
    print(f"❌ '{data_dir}' 폴더가 없습니다. 경로를 다시 확인해주세요!")
    exit()

# 3. 쪼갤 원본 찾기 (part01 같은거 제외, 가장 큰 .jsonl 파일)
all_jsonl = [f for f in data_dir.glob("*.jsonl") if "_part" not in f.name]

if not all_jsonl:
    print("❌ 쪼갤 .jsonl 파일을 찾지 못했습니다.")
    print(f"📂 data 폴더 실제 파일들: {[f.name for f in data_dir.iterdir()]}")
else:
    target_file = max(all_jsonl, key=lambda f: f.stat().st_size)
    print("=" * 50)
    print(f"🎯 썰기 대상 발견: {target_file.name}")
    print(f"📦 용량: {target_file.stat().st_size / 1024:.1f} KB")
    print("=" * 50)

    # 4. 250개씩 썰기
    CHUNK_SIZE = 250 
    with open(target_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    total_chunks = (len(lines) + CHUNK_SIZE - 1) // CHUNK_SIZE

    for i in range(0, len(lines), CHUNK_SIZE):
        chunk = lines[i : i + CHUNK_SIZE]
        chunk_num = (i // CHUNK_SIZE) + 1
        
        # 결과물도 data 폴더 안에 생성
        out_name = data_dir / f"{target_file.stem}_part{chunk_num:02d}.jsonl"
        
        with open(out_name, 'w', encoding='utf-8') as out_f:
            out_f.writelines(chunk)
        print(f" ✅ {out_name.name} 생성 완료 ({len(chunk)}개)")

    print("=" * 50)
    print(f"🎉 총 {total_chunks}개 파트로 썰기 끝! 이제 발사 준비 완료!")