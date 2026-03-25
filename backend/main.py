import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from dotenv import load_dotenv, find_dotenv
from openai import OpenAI

# 환경 변수 로드
load_dotenv(find_dotenv())

# 초기화
app = FastAPI(title="Hidden Gem API", version="1.0")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DB_URL = os.getenv("DATABASE_URL")
engine = create_engine(DB_URL)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== 요청/응답 모델 ==============
class SearchRequest(BaseModel):
    query: str
    top_k: int = 10

class GameResponse(BaseModel):
    app_id: str
    name: str
    genres: str
    developer: str
    description: str
    gem_potential: int

# ============== API 엔드포인트 ==============

@app.get("/")
def root():
    return {"message": "Hidden Gem API is running!", "version": "1.0"}

@app.get("/health")
def health_check():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM games"))
            count = result.scalar()
        return {"status": "healthy", "game_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/games/top")
def get_top_games(limit: int = 20):
    """잠재력 높은 게임 TOP N"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT app_id, name, genres, developer, description, gem_potential
                FROM games
                ORDER BY gem_potential DESC
                LIMIT :limit
            """), {"limit": limit})
            
            games = [
                {
                    "app_id": row[0],
                    "name": row[1],
                    "genres": row[2],
                    "developer": row[3],
                    "description": row[4],
                    "gem_potential": row[5]
                }
                for row in result
            ]
        return {"games": games}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/games/{app_id}")
def get_game_detail(app_id: str):
    """게임 상세 정보"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT app_id, name, genres, developer, description,
                       mania_score, story_depth, originality, difficulty, art_style,
                       replay_value, indie_spirit, character_appeal, user_friendliness,
                       addictiveness, emotional_impact, atmosphere_intensity,
                       soundtrack_prominence, gem_potential
                FROM games WHERE app_id = :aid
            """), {"aid": app_id})
            
            row = result.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Game not found")
            
            return {
                "app_id": row[0],
                "name": row[1],
                "genres": row[2],
                "developer": row[3],
                "description": row[4],
                "scores": {
                    "mania_score": row[5],
                    "story_depth": row[6],
                    "originality": row[7],
                    "difficulty": row[8],
                    "art_style": row[9],
                    "replay_value": row[10],
                    "indie_spirit": row[11],
                    "character_appeal": row[12],
                    "user_friendliness": row[13],
                    "addictiveness": row[14],
                    "emotional_impact": row[15],
                    "atmosphere_intensity": row[16],
                    "soundtrack_prominence": row[17],
                    "gem_potential": row[18]
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
def semantic_search(request: SearchRequest):
    """의미 기반 게임 검색 (임베딩 활용)"""
    try:
        # 쿼리 임베딩 생성
        embed_response = client.embeddings.create(
            model="text-embedding-3-small",
            input=request.query
        )
        query_vector = embed_response.data[0].embedding
        
        # 벡터 유사도 검색
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT app_id, name, genres, developer, description, gem_potential,
                       1 - (embedding <=> :vec::vector) as similarity
                FROM games
                ORDER BY embedding <=> :vec::vector
                LIMIT :k
            """), {"vec": str(query_vector), "k": request.top_k})
            
            games = [
                {
                    "app_id": row[0],
                    "name": row[1],
                    "genres": row[2],
                    "developer": row[3],
                    "description": row[4],
                    "gem_potential": row[5],
                    "similarity": round(float(row[6]), 4)
                }
                for row in result
            ]
        
        return {"query": request.query, "results": games}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/games/filter")
def filter_games(
    min_gem: int = 0,
    max_gem: int = 100,
    genre: str = None,
    limit: int = 20
):
    """필터링 검색"""
    try:
        query = """
            SELECT app_id, name, genres, developer, description, gem_potential
            FROM games
            WHERE gem_potential BETWEEN :min AND :max
        """
        params = {"min": min_gem, "max": max_gem, "limit": limit}
        
        if genre:
            query += " AND genres ILIKE :genre"
            params["genre"] = f"%{genre}%"
        
        query += " ORDER BY gem_potential DESC LIMIT :limit"
        
        with engine.connect() as conn:
            result = conn.execute(text(query), params)
            games = [
                {
                    "app_id": row[0],
                    "name": row[1],
                    "genres": row[2],
                    "developer": row[3],
                    "description": row[4],
                    "gem_potential": row[5]
                }
                for row in result
            ]
        
        return {"games": games}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 서버 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
