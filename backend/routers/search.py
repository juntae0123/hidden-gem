"""
Hidden Gem - Search Router
===========================
/search 엔드포인트 처리
"""

import logging
from fastapi import APIRouter, HTTPException

from backend.schemas.requests import SearchRequest, SearchResponse
from backend.services.intent_extractor import extract_user_intent_v2
from backend.services.vector_search import hybrid_search_with_fallback
from backend.services.vector_search import get_popular_games

logger = logging.getLogger("hidden_gem.search")
router = APIRouter()

@router.post("/search", response_model=SearchResponse)
def hybrid_search(request: SearchRequest):
    """
    하이브리드 검색 엔드포인트
    
    - 의도 추출 → 벡터 검색 → 점수 계산 → 결과 반환
    - 3단계 Fallback으로 빈 결과 방지
    """
    try:
        # 1. 의도 추출
        intent = extract_user_intent_v2(request.query)
        
        # 2. 검색 실행 (Fallback 포함)
        search_result = hybrid_search_with_fallback(
            query=request.query,
            intent=intent,
            top_k=request.top_k,
            include_maniac=request.include_maniac
        )
        
        # 3. Intent 객체 변환
        intent_objects = intent.get_intent_objects()
        
        # 4. 응답 구성
        return SearchResponse(
            query=request.query,
            intents=intent_objects,
            gems=search_result["gems"],
            maniacs=search_result["maniacs"],
            total_candidates=search_result["total_candidates"],
            algorithm_version="v3.0.0",
            scoring_formula="(Similarity×65) + (GenreDNA×35) + Synergy",
            fallback_activated=search_result["search_stage"] > 1,
            fallback_message=search_result["fallback_message"],
            search_stage=search_result["search_stage"],
            genre_analysis={
                "required_genres": list(intent.required_genres)[:10],
                "negative_genres": list(intent.negative_genres)[:5],
                "preferred_keywords": intent.preferred_keywords[:5],
                "core_keywords": intent.core_keywords,
                "reference_game": intent.reference_game,
                "strictness": intent.genre_strictness
            },
            is_recommendation_mode=search_result.get("is_recommendation_mode", False)
        )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        
        # 최후의 Fallback: 인기 게임 반환
        popular = get_popular_games(limit=request.top_k)
        return SearchResponse(
            query=request.query,
            intents=[],
            gems=popular,
            maniacs=[],
            total_candidates=len(popular),
            algorithm_version="v3.0.0",
            scoring_formula="(Similarity×65) + (GenreDNA×35) + Synergy",
            fallback_activated=True,
            fallback_message="🔥 검색 중 오류 발생 - 인기 명작 추천",
            search_stage=3,
            genre_analysis={
                "required_genres": [],
                "negative_genres": [],
                "preferred_keywords": [],
                "core_keywords": [],
                "reference_game": None,
                "strictness": 0.0
            },
            is_recommendation_mode=True,
            error=str(e)[:100]
        )
