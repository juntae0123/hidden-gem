import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv # 💡 추가!

# 1. 경로 설정
CURRENT_FILE_PATH = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE_PATH.parent.parent # C:\Hidden-Gem-project
DATA_DIR = PROJECT_ROOT / "data"
LOG_FILE = PROJECT_ROOT / "upload_log.txt"
ENV_PATH = PROJECT_ROOT / ".env" # 💡 상위 폴더 .env 경로

# 💡 [핵심] 상위 폴더의 .env 파일을 강제로 로드합니다!
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
    print(f"✅ .env 로드 완료: {ENV_PATH}")
else:
    print(f"❌ .env 파일을 찾을 수 없습니다: {ENV_PATH}")

# 2. 업로드할 파트 파일들 수집
PART_FILES = sorted(list(DATA_DIR.glob("*_part*.jsonl")))

def write_log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except: pass
    print(f"[{timestamp}] {message}")

def run_upload(file_path):
    write_log(f"🚀 [업로드 시도] {file_path.name}")
    
    # 환경 변수 설정 (UTF-8 강제 + 현재 시스템 환경 변수 복사)
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    
    cmd = [sys.executable, "-m", "embeddings.batch_processor", str(file_path)]
    
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            encoding="utf-8", 
            errors="replace", 
            env=env, # 💡 여기서 로드된 API KEY가 전달됩니다!
            cwd=str(PROJECT_ROOT)
        )
        
        if result.returncode == 0:
            write_log(f"✅ {file_path.name} 업로드 성공!")
            return True
        else:
            write_log(f"❌ {file_path.name} 업로드 실패!")
            write_log(f"   [에러 상세]: {result.stderr[:300].strip()}...")
            return False
    except Exception as e:
        write_log(f"🔥 예외 발생: {str(e)}")
        return False

def main():
    if not PART_FILES:
        print(f"❌ '{DATA_DIR}' 폴더에 파일이 없습니다.")
        return

    write_log("==================================================")
    write_log(f"🎮 Hidden Gem 자동 업로드 (API KEY 로드 모드)")
    write_log("==================================================")
    
    for i, file_path in enumerate(PART_FILES):
        success = run_upload(file_path)
        if i < len(PART_FILES) - 1:
            write_log(f"💤 1시간 대기 중... (다음: {PART_FILES[i+1].name})")
            time.sleep(3600)
        else:
            write_log("🎊 모든 업로드 완료!")

if __name__ == "__main__":
    main()