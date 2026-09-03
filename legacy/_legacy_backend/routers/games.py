"""
Hidden Gem - Games Router
==========================
/games 관련 엔드포인트 처리
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from backend.database import engine
from backend.services.scoring_engine import generate_scores_from_genres

router = APIRouter()

def row_to_game_dict(row, similarity: float = 0.5):
    """DB 행을 게임 딕셔너리로 변환"""
    game_id = str(row[0])
    name = row[1] or "Unknown Game"
    genres = row[2] or ""
    description = row[3] or ""
    gem_potential = row[4] if len(row) > 4 and row[4] is not None else 50
    
    scores = generate_scores_from_genres(genres)
    if gem_potential:
        scores["gem_potential"] = int(gem_potential)
    
    return {
        "app_id": game_id,
        "name": name,
        "genres": genres,
        "developer": "Unknown",
        "description": description,
        "scores": scores,
        "similarity": similarity
    }

@router.get("/top")
def get_top_games(limit: int = 20):
    """인기 게임 목록 조회"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, name, genres, description, gem_potential
                FROM games 
                WHERE gem_potential IS NOT NULL
                ORDER BY gem_potential DESC 
                LIMIT :limit
            """), {"limit": limit})
            
            games = []
            for row in result:
                game_dict = row_to_game_dict(row)
                games.append({
                    "app_id": game_dict["app_id"],
                    "name": game_dict["name"],
                    "genres": game_dict["genres"],
                    "developer": game_dict["developer"],
                    "description": game_dict["description"],
                    "gem_potential": game_dict["scores"].get("gem_potential", 50)
                })
            
        return {"games": games, "count": len(games)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{app_id}")
def get_game_detail(app_id: str):
    """특정 게임 상세 조회"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, name, genres, description, gem_potential
                FROM games WHERE id = :aid
            """), {"aid": app_id})
            row = result.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Game not found")
            
            return row_to_game_dict(row)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/filter")
def filter_games(
    min_gem: int = 0,
    max_gem: int = 100,
    genre: Optional[str] = None,
    limit: int = 20
):
    """조건별 게임 필터링"""
    try:
        query_str = """
            SELECT id, name, genres, description, gem_potential 
            FROM games 
            WHERE gem_potential IS NOT NULL 
              AND gem_potential BETWEEN :min AND :max
        """
        params = {"min": min_gem, "max": max_gem, "limit": limit}
        
        if genre:
            query_str += " AND genres ILIKE :genre"
            params["genre"] = f"%{genre}%"
        
        query_str += " ORDER BY gem_potential DESC LIMIT :limit"
        
        with engine.connect() as conn:
            result = conn.execute(text(query_str), params)
            games = [row_to_game_dict(row) for row in result]
        
        return {"games": games, "count": len(games)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
