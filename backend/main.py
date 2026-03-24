import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db  # database.py에서 세션 가져오기
from sentence_transformers import SentenceTransformer

app = FastAPI()

# ✅ [CORS 설정] 프론트엔드(React/Next.js)와 통신 허용
# 이유: 백엔드(FastAPI)와 프론트엔드(Next.js)의 포트가 다르면 브라우저가 보안상 통신을 막기 때문에 이를 허용해줍니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# AI 모델 전역 변수
model = None

@app.on_event("startup")
def load_data():
    global model
    print("🧠 AI 모델 로드 중 (SBERT-384차원)...")
    # 이유: 실시간 웹 서비스에서는 검색 속도가 생명이므로, 무겁지 않고 빠른 'all-MiniLM-L6-v2' 모델을 사용합니다.
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    print("✅ AI 모델 로드 완료!")

@app.get("/recommend")
def recommend(query: str = "", db: Session = Depends(get_db)):
    if not query:
        return []
    
    if model is None:
        raise HTTPException(status_code=500, detail="모델 로드 대기 중입니다.")

    try:
        # 1. 사용자의 질문을 384차원 벡터로 변환
        query_vector = model.encode(query).tolist()

        # 2. DB 검색: 코사인 거리(<=>) 연산자를 사용하여 문맥 유사도 검색
        # 이유: AI 텍스트 임베딩 모델은 방향성을 기준으로 학습되었기 때문에, 단순 직선거리(<->)보다 코사인 거리(<=>)가 문맥을 훨씬 정확히 잡아냅니다.
        search_query = text("""
            SELECT 
                name, genres, description, 
                mania_score, story_depth, gem_potential, 
                originality, difficulty, art_style, replay_value, 
                (embedding <=> :vector) AS distance 
            FROM games
            ORDER BY distance
            LIMIT 30
        """)
        
        result = db.execute(search_query, {"vector": str(query_vector)})
        db_results = result.fetchall()

        if not db_results:
            return []

        # 3. AI 점수 정규화 (Min-Max Scaling) 준비
        # 이유: AI 모델이 뱉어내는 유사도 값의 격차가 너무 작아서 스탯 점수에 먹히는 현상을 방지하기 위해, 점수 격차를 쫙 벌려줍니다.
        distances = [float(row.distance) for row in db_results]
        min_dist = min(distances)
        max_dist = max(distances)

        # 모든 게임의 거리가 같을 경우 0으로 나누는 에러(ZeroDivisionError) 방지
        if max_dist == min_dist:
            max_dist = min_dist + 0.0001 

        games_list = []
        for row in db_results:
            name, genres, desc, m_score, s_depth, g_pot, orig, diff, art, repl, dist = row
            current_dist = float(dist)

            # 4. 정규화 및 메인 점수 계산 (최소 40점 ~ 최대 80점)
            # 가장 가까운 1등은 80점, 꼴등(30등)은 40점을 받게 되어 AI의 검색 변별력이 확실해집니다.
            normalized_ai_score = 1.0 - ((current_dist - min_dist) / (max_dist - min_dist))
            similarity_score = 40.0 + (normalized_ai_score * 40.0)

            # 5. Hidden-Gem 가중치 기반 보너스 점수 (최대 20점)
            # 이유: 뻔한 대작(mania_score가 높은 게임)이 아닌 '숨겨진 보석'을 찾기 위해 gem_potential과 originality에 높은 가중치를 줍니다.
            w_gem = float(g_pot or 0) * 0.40
            w_orig = float(orig or 0) * 0.30
            w_mania = float(m_score or 0) * 0.10
            w_story = float(s_depth or 0) * 0.10
            w_others = (float(diff or 0) + float(art or 0) + float(repl or 0)) / 30.0 * 1.0
            
            bonus_score = ((w_gem + w_orig + w_mania + w_story + w_others) / 10.0) * 20.0 

            # 6. 최종 점수 합산 (총 100점 만점)
            final_score = similarity_score + bonus_score

            games_list.append({
                "name": name,
                "genres": genres,
                "description": desc[:100] + "...", # 프론트엔드 전송량 최적화를 위해 긴 설명 자르기
                "ai_score": round(similarity_score, 1),
                "bonus_score": round(bonus_score, 1),
                "final_score": round(final_score, 1)
            })

        # 7. 최종 점수 기준 상위 12개 결과 반환
        sorted_games = sorted(games_list, key=lambda x: x["final_score"], reverse=True)[:12]
        return sorted_games

    except Exception as e:
        print(f"❌ DB 검색 중 치명적 에러 발생: {e}")
        raise HTTPException(status_code=500, detail=f"DB 검색 실패: {str(e)}")

@app.get("/")
def root():
    return {"message": "Hidden-Gem Finder API is Running! 🚀"}