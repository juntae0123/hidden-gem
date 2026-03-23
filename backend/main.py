from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_PATH = "../data/hidden_gem_bulk_data.csv"
df = pd.DataFrame() 

@app.on_event("startup")
def load_data():
    global df
    if os.path.exists(DATA_PATH):
        df = pd.read_csv(DATA_PATH)
        print(f"✅ 데이터 로드 성공! 총 {len(df)}개의 게임 데이터를 불러왔습니다.")
        # 💡 데이터에 무슨 항목들이 있는지 백엔드 터미널에 찍어봅니다.
        print(f"📊 현재 보유한 데이터 항목들: {list(df.columns)}") 
    else:
        print("❌ 데이터를 찾을 수 없습니다! 경로를 다시 확인해주세요.")

@app.get("/")
def home():
    return {"message": "Hidden-Gem Backend is running!"}

@app.get("/recommend")
def recommend(query: str = ""):
    if df.empty or 'name' not in df.columns:
        return []
    
    search_term = query.lower()
    filtered_df = df[df['name'].astype(str).str.lower().str.contains(search_term, na=False)].copy()
    
    if filtered_df.empty:
        return []
        
    # 💡 [핵심 해결책] 'added'나 'rating' 데이터가 없으면 0으로 처리해서 에러를 막습니다!
    rating_score = filtered_df['rating'].fillna(0) if 'rating' in filtered_df.columns else 0
    added_score = filtered_df['added'].fillna(0) if 'added' in filtered_df.columns else 0
    
    filtered_df['final_score'] = (rating_score * 0.8) + (added_score / 10000 * 0.2)
    filtered_df = filtered_df.sort_values(by='final_score', ascending=False).head(6)
    
    # 있는 데이터만 포장해서 프론트엔드로 보냅니다.
    cols = ['name', 'final_score']
    if 'rating' in filtered_df.columns: cols.append('rating')
    if 'added' in filtered_df.columns: cols.append('added')
        
    results = filtered_df[cols].to_dict(orient='records')
    return results