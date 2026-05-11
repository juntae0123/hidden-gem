"""
Hidden Gem - Debug Router
==========================
개발/디버그용 엔드포인트
"""

from fastapi import APIRouter

from backend.schemas.requests import SearchRequest
from backend.services.intent_extractor import extract_user_intent_v2
from backend.services.scoring_engine import generate_scores_from_genres

router = APIRouter()

@router.post("/intent")
def debug_intent(request: SearchRequest):
    """의도 추출 디버깅"""
    intent = extract_user_intent_v2(request.query)
    return {
        "query": request.query,
        "metrics": intent.metrics,
        "intent_objects": intent.get_intent_objects(),
        "required_genres": list(intent.required_genres),
        "preferred_keywords": intent.preferred_keywords,
        "negative_genres": list(intent.negative_genres),
        "core_keywords": intent.core_keywords,
        "reference_game": intent.reference_game,
        "genre_strictness": intent.genre_strictness
    }

@router.post("/genre-scores")
def debug_genre_scores(genre: str):
    """장르 DNA 점수 생성 디버깅"""
    scores = generate_scores_from_genres(genre)
    
    s_tier = {k: v for k, v in scores.items() if v >= 85}
    a_tier = {k: v for k, v in scores.items() if 75 <= v < 85}
    b_tier = {k: v for k, v in scores.items() if 65 <= v < 75}
    default = {k: v for k, v in scores.items() if v < 65}
    
    return {
        "input_genre": genre,
        "scores": scores,
        "breakdown": {
            "S_tier (85)": s_tier,
            "A_tier (75)": a_tier,
            "B_tier (65)": b_tier,
            "Default (50)": default
        }
    }
