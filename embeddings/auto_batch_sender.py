import os
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

# 1. 경로 및 환경 설정
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# OpenAI 클라이언트 초기화 (보안 유지!)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def write_log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def run_real_upload(file_path):
    write_log(f"🚀 [진짜 업로드 시작] {file_path.name}")
    
    try:
        # A. 파일 업로드 (OpenAI 서버로 파일 전송)
        with open(file_path, "rb") as f:
            uploaded_file = client.files.create(file=f, purpose="batch")
        
        file_id = uploaded_file.id
        write_log(f"   ✅ 파일 서버 도착 (ID: {file_id})")

        # B. 배치 작업 생성 (서버에게 "일 시작해!"라고 명령)
        batch_job = client.batches.create(
            input_file_id=file_id,
            endpoint="/v1/chat/completions",
            completion_window="24h"
        )
        
        write_log(f"   🎊 배치 생성 성공! (Batch ID: {batch_job.id})")
        return True
    except Exception as e:
        write_log(f"   ❌ 업로드 실패: {str(e)}")
        return False

# 파일 목록 수집
DATA_DIR = PROJECT_ROOT / "data"
PART_FILES = sorted(list(DATA_DIR.glob("*_part*.jsonl")))

def main():
    if not PART_FILES:
        print(f"❌ '{DATA_DIR}' 폴더에 쪼개진 파일이 없습니다.")
        return

    write_log("==================================================")
    write_log("🎮 Hidden Gem '진짜' 자동 업로드 시스템 가동")
    write_log("==================================================")
    
    for i, file_path in enumerate(PART_FILES):
        if run_real_upload(file_path):
            if i < len(PART_FILES) - 1:
                write_log(f"💤 1시간 대기 중... (다음: {PART_FILES[i+1].name})")
                time.sleep(3600)
        else:
            write_log("⚠️ 실패 발생으로 중단합니다.")
            break
    
    write_log("🏁 모든 파트 전송 완료!")

if __name__ == "__main__":
    main()