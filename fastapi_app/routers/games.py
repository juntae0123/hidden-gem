# fastapi_app/routers/games.py
"""
게임 관련 API 엔드포인트 - 49차원 완전체
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List
import numpy as np

from database import get_db
from models.game import Game, GameMetric, NUMERIC_METRIC_FIELDS, BOOLEAN_TAG_FIELDS
from schemas.game import (
    GameWithMetrics, GameSearchResult,
    RecommendByGameRequest, RecommendByPreferenceRequest,
    RecommendationResponse
)
from services.recommender import recommender

router = APIRouter(prefix="/games", tags=["Games"])


# ==================== 검색 API ====================

@router.get("/search", response_model=List[GameSearchResult])
async def search_games(
    q: str = Query(None, min_length=1, description="검색어"),
    genre: str = Query(None, description="장르 필터"),
    min_gem: float = Query(None, ge=0, le=10, description="최소 gem_potential"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """게임 검색 API"""
    stmt = (
        select(Game)
        .options(selectinload(Game.metrics))
        .where(Game.is_active == True)
        .where(Game.is_analyzed == True)
    )
    
    if q:
        search_term = f"%{q}%"
        stmt = stmt.where(
            or_(
                Game.name.ilike(search_term),
                Game.genres.ilike(search_term),
                Game.developer.ilike(search_term)
            )
        )
    
    if genre:
        stmt = stmt.where(Game.genres.ilike(f"%{genre}%"))
    
    stmt = stmt.order_by(Game.review_count.desc())
    stmt = stmt.offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    games = result.scalars().all()
    
    results = []
    for game in games:
        gem = game.metrics.gem_potential if game.metrics else None
        
        if min_gem and (gem is None or gem < min_gem):
            continue
        
        results.append(GameSearchResult(
            app_id=game.app_id,
            name=game.name,
            genres=game.genres,
            header_image=game.header_image,
            one_line_summary=game.one_line_summary or "",
            gem_potential=gem,
            steam_positive_ratio=game.steam_positive_ratio,
            review_count=game.review_count
        ))
    
    return results


@router.get("/{app_id}", response_model=GameWithMetrics)
async def get_game_detail(
    app_id: int,
    db: AsyncSession = Depends(get_db)
):
    """게임 상세 정보 + 60개 지표 조회"""
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


# ==================== 추천 API ====================

@router.post("/recommend/by-game", response_model=RecommendationResponse)
async def recommend_by_game(
    request: RecommendByGameRequest,
    db: AsyncSession = Depends(get_db)
):
    """⭐️ 특정 게임 기반 유사 게임 추천 (49차원 벡터 유사도)"""
    target_game, results = await recommender.recommend_by_game(
        db=db,
        app_id=request.app_id,
        count=request.count,
        exclude_same_developer=request.exclude_same_developer
    )
    
    if not target_game:
        raise HTTPException(
            status_code=404, 
            detail=f"Game not found or has no metrics: {request.app_id}"
        )
    
    target_vector = recommender._metric_to_vector(target_game.metrics)
    
    recommendations = recommender.format_recommendations(
        results, 
        target_vector=target_vector
    )
    
    return RecommendationResponse(
        query_type="by_game",
        reference_game=target_game.name,
        total_candidates=len(results),
        recommendations=recommendations
    )


@router.post("/recommend/by-preference", response_model=RecommendationResponse)
async def recommend_by_preference(
    request: RecommendByPreferenceRequest,
    db: AsyncSession = Depends(get_db)
):
    """⭐️ 유저 선호도 기반 게임 추천 (49차원)"""
    valid_metrics = set(NUMERIC_METRIC_FIELDS)
    for field in request.preferences.keys():
        if field not in valid_metrics:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown metric: {field}"
            )
    
    results = await recommender.recommend_by_preference(
        db=db,
        preferences=request.preferences,
        required_tags=request.required_tags,
        excluded_tags=request.excluded_tags,
        count=request.count,
        min_gem_potential=request.min_gem_potential
    )
    
    recommendations = recommender.format_recommendations(
        results,
        preferences=request.preferences
    )
    
    return RecommendationResponse(
        query_type="by_preference",
        reference_game=None,
        total_candidates=len(results),
        recommendations=recommendations
    )


# ==================== 유틸 API ====================

@router.get("/stats/overview")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """DB 통계 조회"""
    total = await db.execute(select(func.count(Game.id)))
    total_games = total.scalar()
    
    analyzed = await db.execute(
        select(func.count(Game.id)).where(Game.is_analyzed == True)
    )
    analyzed_games = analyzed.scalar()
    
    avg_gem = await db.execute(
        select(func.avg(GameMetric.gem_potential))
    )
    avg_gem_potential = avg_gem.scalar()
    
    return {
        "total_games": total_games,
        "analyzed_games": analyzed_games,
        "average_gem_potential": round(avg_gem_potential, 2) if avg_gem_potential else None,
        "dimension": len(NUMERIC_METRIC_FIELDS),
        "data_source": "GPT-5.4 Batch API"
    }


@router.get("/metrics/list")
async def list_metrics():
    """사용 가능한 지표 목록"""
    return {
        "numeric_metrics": NUMERIC_METRIC_FIELDS,
        "boolean_tags": BOOLEAN_TAG_FIELDS,
        "total": len(NUMERIC_METRIC_FIELDS) + len(BOOLEAN_TAG_FIELDS)
    }
