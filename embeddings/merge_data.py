import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv, find_dotenv

# .env 파일에서 환경변수 로드
load_dotenv(find_dotenv())
DB_URL = os.getenv("DATABASE_URL")

def merge_old_data():
    print("🔄 과거 데이터(pkl)를 DB로 병합합니다...")
    
    # 1. DB 연결
    try:
        engine = create_engine(DB_URL)
        print("✅ DB 연결 성공!")
    except Exception as e:
        print(f"❌ DB 연결 실패: {e}")
        return
        
    # 2. data 폴더 안의 기존 pkl 파일 읽기
    file_path = "../data/hidden_gem_embedded.pkl"
    try:
        df = pd.read_pickle(file_path)
        print(f"✅ 파일 읽기 성공! 총 {len(df)}개의 데이터가 있습니다.")
    except Exception as e:
        print(f"❌ 파일을 읽을 수 없습니다: {e}")
        return
        
    # 3. DB에 안전하게 넣기 (중복 방지)
    success_count = 0
    skip_count = 0
    
    print("🚀 DB에 밀어 넣는 중...")
    with engine.begin() as conn:
        for index, row in df.iterrows():
            try:
                # 리스트 형태의 임베딩 값을 DB가 좋아하는 문자열로 변환
                emb = row.get('embedding', [])
                emb_str = str(list(emb)) if hasattr(emb, '__iter__') else str(emb)
                
                # 기존 컬럼 이름이 description인지 short_description인지 확인 후 가져오기
                desc = row.get('short_description', row.get('description', ''))
                
                conn.execute(text("""
                    INSERT INTO games (
                        app_id, name, genres, developer, description,
                        mania_score, story_depth, originality, difficulty, art_style,
                        replay_value, indie_spirit, character_appeal, user_friendliness,
                        addictiveness, emotional_impact, atmosphere_intensity,
                        soundtrack_prominence, gem_potential, embedding
                    ) VALUES (
                        :aid, :n, :g, :d, :desc,
                        :m, :s, :o, :df, :a,
                        :r, :i, :c, :u,
                        :ad, :e, :at,
                        :sp, :gp, :v
                    )
                    ON CONFLICT (app_id) DO NOTHING
                """), {
                    "aid": str(row['app_id']),
                    "n": str(row['name'])[:200],
                    "g": str(row.get('genres', 'Unknown'))[:500],
                    "d": str(row.get('developer', 'Unknown'))[:200],
                    "desc": str(desc)[:2000],
                    "m": int(row.get('mania_score', 50)),
                    "s": int(row.get('story_depth', 50)),
                    "o": int(row.get('originality', 50)),
                    "df": int(row.get('difficulty', 50)),
                    "a": int(row.get('art_style', 50)),
                    "r": int(row.get('replay_value', 50)),
                    "i": int(row.get('indie_spirit', 50)),
                    "c": int(row.get('character_appeal', 50)),
                    "u": int(row.get('user_friendliness', 50)),
                    "ad": int(row.get('addictiveness', 50)),
                    "e": int(row.get('emotional_impact', 50)),
                    "at": int(row.get('atmosphere_intensity', 50)),
                    "sp": int(row.get('soundtrack_prominence', 50)),
                    "gp": int(row.get('gem_potential', 50)),
                    "v": emb_str
                })
                success_count += 1
            except Exception as e:
                skip_count += 1
                
    print(f"🎉 병합 완료! 새로 추가된 데이터: {success_count}개 (중복/에러 스킵: {skip_count}개)")

if __name__ == "__main__":
    merge_old_data()