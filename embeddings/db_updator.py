"""
Hidden Gem - DB Schema Updater
==============================
52개 지표 저장을 위한 JSONB 컬럼 추가

사용법:
    cd Hidden-Gem-project
    source .venv/Scripts/activate
    python -m embeddings.db_updater
"""

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

DB_URL = os.getenv("DATABASE_URL")
engine = create_engine(DB_URL)


def update_schema():
    """games 테이블에 JSONB 컬럼 추가"""
    
    print("=" * 60)
    print("🔧 Hidden Gem - DB 스키마 업데이트")
    print("=" * 60)
    
    columns_to_add = [
        ("metrics", "JSONB", "{}"),
        ("tags", "JSONB", "{}"),
        ("content", "JSONB", "{}"),
        ("reasoning", "JSONB", "{}"),
        ("extraction_meta", "JSONB", "{}"),
    ]
    
    with engine.begin() as conn:
        for col_name, col_type, default in columns_to_add:
            try:
                # 컬럼 존재 여부 확인
                result = conn.execute(text(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'games' AND column_name = '{col_name}'
                """))
                
                if result.fetchone():
                    print(f"   ✅ {col_name} - 이미 존재")
                else:
                    # 컬럼 추가
                    conn.execute(text(f"""
                        ALTER TABLE games 
                        ADD COLUMN IF NOT EXISTS {col_name} {col_type} DEFAULT '{default}'
                    """))
                    print(f"   🆕 {col_name} - 추가 완료")
                    
            except Exception as e:
                print(f"   ❌ {col_name} - 실패: {e}")
    
    print("\n" + "=" * 60)
    print("✅ 스키마 업데이트 완료!")
    print("=" * 60)


def verify_schema():
    """스키마 확인"""
    print("\n📋 현재 games 테이블 컬럼:")
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'games'
            ORDER BY ordinal_position
        """))
        
        for row in result:
            print(f"   - {row[0]}: {row[1]}")


if __name__ == "__main__":
    update_schema()
    verify_schema()
