import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv, find_dotenv

# .env 파일에서 환경변수 로드
load_dotenv(find_dotenv())
DB_URL = os.getenv("DATABASE_URL")

def export_data():
    print("📦 DB에서 데이터 추출을 시작합니다...")
    
    # 1. DB 연결
    try:
        engine = create_engine(DB_URL)
        print("✅ DB 연결 성공!")
    except Exception as e:
        print(f"❌ DB 연결 실패: {e}")
        return

    # 2. 모든 데이터 가져오기 (pandas 활용)
    try:
        # SQL 쿼리로 games 테이블의 모든 데이터를 DataFrame으로 불러옵니다.
        df = pd.read_sql("SELECT * FROM games", engine)
        print(f"✅ 총 {len(df)}개의 데이터를 성공적으로 불러왔습니다.")
    except Exception as e:
        print(f"❌ 데이터 불러오기 실패: {e}")
        return

    # 3. CSV 파일로 저장
    try:
        csv_filename = "hidden_gem_data.csv"
        # 인덱스 없이, 한글 깨짐 방지를 위해 utf-8-sig 인코딩 사용
        df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        print(f"🎉 CSV 저장 완료: {csv_filename}")
    except Exception as e:
         print(f"❌ CSV 저장 실패: {e}")

    # 4. PKL (Pickle) 파일로 저장
    try:
        pkl_filename = "hidden_gem_data.pkl"
        df.to_pickle(pkl_filename)
        print(f"🎉 PKL 저장 완료: {pkl_filename}")
    except Exception as e:
         print(f"❌ PKL 저장 실패: {e}")

if __name__ == "__main__":
    export_data()