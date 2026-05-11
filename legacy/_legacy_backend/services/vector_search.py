"""
Hidden Gem - Vector Search Service
===================================
벡터 검색 및 Fallback 로직
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple, Set

from openai import OpenAI
from sqlalchemy import text
from dotenv import load_dotenv

from backend.database import engine
from backend.config import (
    DROP_THRESHOLD, DROP_THRESHOLD_FALLBACK, DROP_THRESHOLD_EMERGENCY,
    MIN_RESULTS_BEFORE_FALLBACK, MIN_RESULTS_ABSOLUTE, EXCLUDED_GENRES
)
from backend.services.intent_extractor import ExtractedIntent
from backend.services.scoring_engine import (
    generate_scores_from_genres, calculate_final_score
)

load_dotenv()
logger = logging.getLogger("hidden_gem.vector_search")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ============== 유틸리티 ==============
def is_excluded_genre(genres: str) -> bool:
    if not genres:
        return False
    return any(ex.lower() in genres.lower() for ex in EXCLUDED_GENRES)

def row_to_game_dict(row, similarity: float = 0.5) -> Dict[str, Any]:
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

# ============== 임베딩 생성 ==============
def create_query_embedding(query: str) -> List[float]:
    embed_response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query,
        timeout=15.0
    )
    return embed_response.data[0].embedding

# ============== 벡터 검색 ==============
def execute_vector_search(query_vector: List[float], limit: int = 100) -> List[Dict]:
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, name, genres, description, gem_potential,
                       1 - (embedding <=> CAST(:vec AS vector)) as similarity
                FROM games
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT :lim
            """), {"vec": str(query_vector), "lim": limit})
            
            games = []
            for row in result:
                similarity = float(row[5]) if row[5] is not None else 0.5
                game_dict = row_to_game_dict(row, similarity)
                games.append(game_dict)
            
            return games
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return []

# ============== 인기 게임 조회 ==============
def get_popular_games(limit: int = 10, genre_filter: Optional[Set[str]] = None) -> List[Dict]:
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, name, genres, description, gem_potential
                FROM games
                WHERE gem_potential IS NOT NULL AND gem_potential >= 60
                ORDER BY gem_potential DESC
                LIMIT :lim
            """), {"lim": limit * 3})
            
            games = []
            for row in result:
                genres = row[2] or ""
                if is_excluded_genre(genres):
                    continue
                
                if genre_filter:
                    genre_lower = genres.lower()
                    if not any(g.lower() in genre_lower for g in genre_filter):
                        continue
                
                game_dict = row_to_game_dict(row, similarity=0.5)
                game_dict["is_popular_fallback"] = True
                game_dict["boost_reason"] = "🌟 인기 명작"
                games.append(game_dict)
                
                if len(games) >= limit:
                    break
            
            return games
    except Exception as e:
        logger.error(f"Popular games failed: {e}")
        return []

# ============== 후보 처리 ==============
def process_candidates_lenient(
    candidates: List[Dict],
    intent: ExtractedIntent,
    drop_threshold: int
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    gems, maniacs, dropped = [], [], []
    
    for game_data in candidates:
        genres = game_data.get("genres", "")
        if is_excluded_genre(genres):
            continue
        
        scores = game_data.get("scores", {})
        similarity = game_data.get("similarity", 0.5)
        
        final_score, status, boost_details, boost_reason, genre_mult, genre_reason = calculate_final_score(
            scores=scores,
            genres=genres,
            intent=intent,
            similarity=similarity,
            drop_threshold=drop_threshold
        )
        
        game_result = {
            "app_id": game_data.get("app_id"),
            "name": game_data.get("name"),
            "genres": genres,
            "developer": game_data.get("developer", "Unknown"),
            "description": game_data.get("description", ""),
            "final_score": round(final_score, 2),
            "status": status,
            "similarity": round(similarity, 4),
            "matched_intents": intent.metrics,
            "boost_reason": boost_reason,
            "boost_info": boost_details,
            "scores": scores,
            "genre_match": {
                "multiplier": round(genre_mult, 2),
                "reason": genre_reason,
                "is_match": genre_mult >= 0.9
            }
        }
        
        if status == "GEM":
            gems.append(game_result)
        elif status == "MANIAC":
            maniacs.append(game_result)
        else:
            dropped.append(game_result)
    
    return gems, maniacs, dropped

# ============== 3단계 무적 Fallback 검색 ==============
def hybrid_search_with_fallback(
    query: str,
    intent: ExtractedIntent,
    top_k: int = 10,
    include_maniac: bool = False
) -> Dict:
    error_log = []
    all_candidates = []
    gems, maniacs = [], []
    
    # ========== 1단계: 전체 쿼리 검색 ==========
    logger.info(f"[Stage 1] Query: '{query}'")
    try:
        query_vector = create_query_embedding(query)
        candidates = execute_vector_search(query_vector, limit=200)
        all_candidates = candidates
        
        gems, maniacs, dropped = process_candidates_lenient(candidates, intent, DROP_THRESHOLD)
        
        if len(gems) >= MIN_RESULTS_BEFORE_FALLBACK:
            gems.sort(key=lambda x: x["final_score"], reverse=True)
            maniacs.sort(key=lambda x: x["final_score"], reverse=True)
            
            return {
                "success": True,
                "search_stage": 1,
                "gems": gems[:top_k],
                "maniacs": maniacs[:5] if include_maniac else [],
                "total_candidates": len(candidates),
                "fallback_message": None,
                "error_log": error_log
            }
        
        error_log.append(f"1단계: {len(gems)}개 결과")
        
    except Exception as e:
        logger.error(f"[Stage 1] Failed: {e}")
        error_log.append(f"1단계 실패: {str(e)[:50]}")
    
    # ========== 2단계: 완화된 기준 ==========
    logger.info(f"[Stage 2] Relaxed threshold")
    
    try:
        intent_relaxed = ExtractedIntent()
        intent_relaxed.metrics = intent.metrics
        intent_relaxed.required_genres = set()
        intent_relaxed.genre_strictness = 0.1
        
        gems_2, maniacs_2, dropped_2 = process_candidates_lenient(
            all_candidates, intent_relaxed, DROP_THRESHOLD_FALLBACK
        )
        
        existing_ids = {g["app_id"] for g in gems}
        for g in gems_2:
            if g["app_id"] not in existing_ids:
                g["fallback_rescued"] = True
                gems.append(g)
                existing_ids.add(g["app_id"])
        
        if len(gems) >= MIN_RESULTS_BEFORE_FALLBACK:
            gems.sort(key=lambda x: x["final_score"], reverse=True)
            return {
                "success": True,
                "search_stage": 2,
                "gems": gems[:top_k],
                "maniacs": maniacs[:5] if include_maniac else [],
                "total_candidates": len(all_candidates),
                "fallback_message": "💡 검색 기준을 완화하여 발굴했습니다",
                "error_log": error_log
            }
        
        error_log.append(f"2단계: {len(gems)}개 결과")
        
    except Exception as e:
        logger.error(f"[Stage 2] Failed: {e}")
        error_log.append(f"2단계 실패: {str(e)[:50]}")
    
    # ========== 3단계: 무적 Fallback ==========
    logger.info("[Stage 3] Emergency fallback")
    
    try:
        existing_ids = {g["app_id"] for g in gems}
        
        # 유사도 높은 게임 추가
        if all_candidates:
            intent_emergency = ExtractedIntent()
            gems_e, _, dropped_e = process_candidates_lenient(
                all_candidates, intent_emergency, DROP_THRESHOLD_EMERGENCY
            )
            
            all_results = gems_e + dropped_e
            all_results.sort(key=lambda x: x["similarity"], reverse=True)
            
            for g in all_results:
                if g["app_id"] not in existing_ids and len(gems) < top_k:
                    g["fallback_rescued"] = True
                    g["status"] = "GEM"
                    gems.append(g)
                    existing_ids.add(g["app_id"])
        
        # 인기 게임 추가
        if len(gems) < MIN_RESULTS_ABSOLUTE:
            popular = get_popular_games(limit=top_k, genre_filter=intent.required_genres if intent.required_genres else None)
            
            for pg in popular:
                if pg["app_id"] not in existing_ids and len(gems) < top_k:
                    pg["fallback_rescued"] = True
                    gems.append(pg)
                    existing_ids.add(pg["app_id"])
        
        gems.sort(key=lambda x: x["final_score"], reverse=True)
        
        return {
            "success": True,
            "search_stage": 3,
            "gems": gems[:top_k],
            "maniacs": maniacs[:5] if include_maniac else [],
            "total_candidates": len(all_candidates) if all_candidates else len(gems),
            "fallback_message": "🔥 유사한 게임 + 인기 명작을 함께 추천합니다",
            "is_recommendation_mode": True,
            "error_log": error_log
        }
        
    except Exception as e:
        logger.error(f"[Stage 3] Failed: {e}")
        
        popular = get_popular_games(limit=top_k)
        return {
            "success": True,
            "search_stage": 3,
            "gems": popular,
            "maniacs": [],
            "total_candidates": len(popular),
            "fallback_message": "😢 검색에 문제가 있어 인기 게임을 추천합니다",
            "is_recommendation_mode": True,
            "error_log": error_log
        }
