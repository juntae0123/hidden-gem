"""
게임 API 엔드포인트 v2 - 추천 포맷 개선
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Optional

from database import get_db
from models.game import (
    Game, GameMetric, 
    NUMERIC_METRIC_FIELDS, BOOLEAN_TAG_FIELDS, METRIC_CATEGORIES
)
from schemas.game import (
    GameWithMetrics, GameSearchResult,
    RecommendByGameRequest, RecommendByPreferenceRequest,
    RecommendationResponse,
)
from services.recommender import recommender

router = APIRouter(prefix="/games", tags=["Games"])


# ==================== 검색 / 상세 ====================

@router.get("/search", response_model=List[GameSearchResult])
async def search_games(
    q: Optional[str] = Query(None, min_length=1, description="검색어 (이름/장르/개발사)"),
    genre: Optional[str] = Query(None, description="장르 필터"),
    min_gem: Optional[float] = Query(None, ge=0, le=100, description="최소 gem_potential"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """게임 검색"""
    stmt = (
        select(Game)
        .options(selectinload(Game.metrics))
        .where(Game.is_active == True)
        .where(Game.is_analyzed == True)
    )
    
    if q:
        term = f"%{q}%"
        stmt = stmt.where(
            or_(
                Game.name.ilike(term),
                Game.genres.ilike(term),
                Game.developer.ilike(term),
            )
        )
    
    if genre:
        stmt = stmt.where(Game.genres.ilike(f"%{genre}%"))
    
    stmt = stmt.order_by(Game.review_count.desc()).offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    games = result.scalars().all()
    
    results = []
    for game in games:
        gem = game.metrics.gem_potential if game.metrics else None
        
        if min_gem is not None:
            if gem is None or gem < min_gem:
                continue
        
        results.append(GameSearchResult(
            app_id=game.app_id,
            name=game.name or "",
            genres=game.genres or "",
            header_image=game.header_image or "",
            one_line_summary=game.one_line_summary or "",
            gem_potential=gem,
            steam_positive_ratio=game.steam_positive_ratio,
            review_count=game.review_count or 0,
        ))
    
    return results


@router.get("/stats/overview")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """DB 통계"""
    total_result = await db.execute(select(func.count(Game.id)))
    total = total_result.scalar()
    
    analyzed_result = await db.execute(
        select(func.count(Game.id)).where(Game.is_analyzed == True)
    )
    analyzed = analyzed_result.scalar()
    
    avg_gem_result = await db.execute(select(func.avg(GameMetric.gem_potential)))
    avg_gem = avg_gem_result.scalar()
    
    return {
        "total_games": total,
        "analyzed_games": analyzed,
        "average_gem_potential": round(float(avg_gem), 2) if avg_gem else None,
        "dimension": len(NUMERIC_METRIC_FIELDS),
        "total_metrics": len(NUMERIC_METRIC_FIELDS) + len(BOOLEAN_TAG_FIELDS),
        "data_source": "GPT-5.4 Batch + Steam CSV",
    }


@router.get("/metrics/list")
async def list_metrics():
    """사용 가능한 지표 목록"""
    return {
        "numeric_metrics": NUMERIC_METRIC_FIELDS,
        "boolean_tags": BOOLEAN_TAG_FIELDS,
        "categories": METRIC_CATEGORIES,
        "total_numeric": len(NUMERIC_METRIC_FIELDS),
        "total_tags": len(BOOLEAN_TAG_FIELDS),
    }


@router.get("/{app_id}", response_model=GameWithMetrics)
async def get_game_detail(app_id: int, db: AsyncSession = Depends(get_db)):
    """게임 상세 + 60개 지표"""
    stmt = (
        select(Game)
        .options(selectinload(Game.metrics))
        .where(Game.app_id == app_id)
    )
    result = await db.execute(stmt)
    game = result.scalar_one_or_none()
    
    if not game:
        raise HTTPException(status_code=404, detail=f"Game not found: {app_id}")
    
    return game


# ==================== 추천 ====================

@router.post("/recommend/by-game", response_model=RecommendationResponse)
async def recommend_by_game(
    request: RecommendByGameRequest,
    db: AsyncSession = Depends(get_db),
):
    """⭐️ 특정 게임 기반 유사 게임 추천 (공통 특징 분석 포함)"""
    target_game, results = await recommender.recommend_by_game(
        db=db,
        app_id=request.app_id,
        count=request.count,
        exclude_same_developer=request.exclude_same_developer,
    )
    
    if not target_game:
        raise HTTPException(
            status_code=404,
            detail=f"Game not found or has no metrics: {request.app_id}"
        )
    
    # 🔧 by-game 전용 포맷 (target_vec 비교로 공통 특징 추출)
    recommendations = recommender.format_recommendations_by_game(results)
    
    return RecommendationResponse(
        query_type="by_game",
        reference_game=target_game.name,
        total_candidates=len(results),
        recommendations=recommendations,
    )


@router.post("/recommend/by-preference", response_model=RecommendationResponse)
async def recommend_by_preference(
    request: RecommendByPreferenceRequest,
    db: AsyncSession = Depends(get_db),
):
    """⭐️ 유저 선호도 기반 추천"""
    # 지표명 검증
    valid_metrics = set(NUMERIC_METRIC_FIELDS)
    invalid = [f for f in request.preferences.keys() if f not in valid_metrics]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown metrics: {invalid}. See /games/metrics/list"
        )
    
    # 태그 검증
    valid_tags = set(BOOLEAN_TAG_FIELDS)
    invalid_tags = [
        t for t in (request.required_tags + request.excluded_tags)
        if t not in valid_tags
    ]
    if invalid_tags:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown tags: {invalid_tags}"
        )
    
    results = await recommender.recommend_by_preference(
        db=db,
        preferences=request.preferences,
        required_tags=request.required_tags,
        excluded_tags=request.excluded_tags,
        count=request.count,
        min_gem_potential=request.min_gem_potential,
    )
    
    # 🔧 by-preference 전용 포맷
    recommendations = recommender.format_recommendations_by_preference(
        results, preferences=request.preferences
    )
    
    return RecommendationResponse(
        query_type="by_preference",
        reference_game=None,
        total_candidates=len(results),
        recommendations=recommendations,
    )
