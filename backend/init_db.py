import pandas as pd
import os
from sqlalchemy import text  # 👈 필수!
from database import SessionLocal, engine
import models

def init_db():
    # 1. 파일 경로 확인
    file_path = os.path.join("..", "data", "hidden_gem_embedded.pkl")
    if not os.path.exists(file_path):
        print(f"❌ 파일을 찾을 수 없습니다: {file_path}")
        return

    # 2. 데이터 로드
    df = pd.read_pickle(file_path)
    db = SessionLocal()
    
    try:
        # 💡 [핵심 순서 1] pgvector 기능을 먼저 활성화!
        print("🔧 pgvector 확장을 활성화합니다...")
        db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        db.commit() # 확정(Commit)을 해줘야 다음 단계에서 인식합니다.

        # 💡 [핵심 순서 2] 확장이 활성화된 후 테이블을 생성!
        print("🏗️ 데이터베이스 테이블을 생성합니다...")
        models.Base.metadata.create_all(bind=engine)
        
        # 3. 데이터 적재
        print(f"🔄 {len(df)}개의 데이터를 DB에 적재 시작...")
        for _, row in df.iterrows():
            new_game = models.Game(
                name=row['name'],
                genres=row['genres'],
                description=row['description'],
                mania_score=row.get('mania_score', 5),
                story_depth=row.get('story_depth', 5),
                gem_potential=row.get('gem_potential', 5),
                embedding=row['embedding']
            )
            db.add(new_game)
        
        db.commit()
        print("✅ 모든 데이터가 pgvector DB에 성공적으로 저장되었습니다!")
        
    except Exception as e:
        print(f"⚠️ 오류 발생: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()