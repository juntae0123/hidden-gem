"""
Hidden Gem Games API Router v5 (Anchor Score System)

Korean: 앵커 점수 시스템 + 4단계 가중치가 통합된 게임 API 라우터 v5.

v4 → v5 변경사항:
    - recommend_by_game: query_hint 파라미터 추가 (의도 기반 가중치)
    - 반환 타입 List[Tuple] → List[Dict] (score_breakdown 포함)
    - format_* 함수 호출 방식 업데이트
    - RecommendByGameRequest: query_hint 필드 추가
    - 기존 SemanticSearchRequest, 캐시, cost_guard 패턴 완전 유지

Endpoints:
    GET  /games/search                   - 이름/장르/개발사 텍스트 검색
    POST /games/search/semantic          - 자연어 시맨틱 검색
    GET  /games/stats/overview           - DB 통계
    GET  /games/metrics/list             - 지표 목록
    GET  /games/{app_id}                 - 게임 상세 + 60개 지표
    POST /games/recommend/by-game        - 특정 게임 기반 유사 게임 추천 (v5: 앵커 100점)
    POST /games/recommend/by-preference  - 유저 선호도 기반 맞춤 추천
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel, Field

from database import get_db
from models.game import (
    Game, GameMetric,
    NUMERIC_METRIC_FIELDS, BOOLEAN_TAG_FIELDS, METRIC_CATEGORIES
)
from schemas.game import (
    GameWithMetrics, GameSearchResult,
    RecommendByGameRequest, RecommendByPreferenceRequest,
    RecommendationResponse, RecommendedGame,
)
from services.recommender import recommender, EXCLUSION_KEYWORDS
from services.vibe_config import get_vibe_list, get_vibe_preferences  # ← 추가

from services.cache import recommendation_cache
from services.cost_guard import cost_guard

router = APIRouter(prefix="/games", tags=["Games"])


# ==================== 요청 스키마 / Request Schemas ====================

class SemanticSearchRequest(BaseModel):
    """
    Semantic search request schema.
    Korean: 자연어 시맨틱 검색 요청 스키마.
    """
    query: str = Field(
        ..., min_length=1, max_length=200,
        description="자연어 검색어 / Natural language search query",
    )
    limit: int = Field(default=12, ge=1, le=50)
    min_gem_potential: float = Field(default=0.0, ge=0.0, le=100.0)


# ==================== 검색 / Search ====================

@router.get("/search", response_model=List[GameSearchResult])
async def search_games(
    q: Optional[str] = Query(None, min_length=1, description="검색어 (이름/장르/개발사)"),
    genre: Optional[str] = Query(None, description="장르 필터"),
    min_gem: Optional[float] = Query(None, ge=0, le=100, description="최소 gem_potential"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    텍스트 기반 게임 검색 (Text-based Game Search)
    이름/장르/개발사 ilike 검색. 리뷰 수 내림차순 정렬.
    """
    stmt = (
        select(Game)
        .options(selectinload(Game.metrics))
        .where(Game.is_active == True)   # noqa: E712
        .where(Game.is_analyzed == True) # noqa: E712
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
        if min_gem is not None and (gem is None or gem < min_gem):
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


@router.post("/search/semantic", response_model=RecommendationResponse)
async def semantic_search(
    request: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    자연어 시맨틱 검색 v2 (Natural Language Semantic Search)
    캐시 → 비용가드 → GPT + pgvector → must_not 필터 → 앵커 점수.
    """
    # 1. 캐시 확인
    cache_key = recommendation_cache.semantic_key(request.query, request.limit)
    cached = await recommendation_cache.get(cache_key)
    if cached:
        return RecommendationResponse(**cached)

    # 2. 비용 가드
    allowed, reason = await cost_guard.check_before_request("gpt-4.1-mini")
    if not allowed:
        raise HTTPException(status_code=503, detail=f"서비스 일시 제한: {reason}")

    # 3. 시맨틱 검색 (v5: List[Dict] 반환)
    try:
        results = await recommender.semantic_search(
            db=db,
            query=request.query,
            limit=request.limit,
            min_gem_potential=request.min_gem_potential,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시맨틱 검색 실패: {str(e)}")

    # 4. 비용 추적
    await cost_guard.track_usage(model="gpt-4.1-mini", input_tokens=500, output_tokens=100)
    await cost_guard.track_usage(model="text-embedding-3-small", input_tokens=100)

    # 5. 포맷 + 캐시 저장
    recommendations = recommender.format_semantic_results(results)
    reference_game = results[0].get("reference_game") if results else None
    response = RecommendationResponse(
        query_type="semantic_by_reference" if reference_game else "semantic",
        reference_game=reference_game,
        total_candidates=len(recommendations),
        recommendations=recommendations,
    )
    await recommendation_cache.set(
        cache_key, response.model_dump(), ttl=recommendation_cache.TTL_SEMANTIC,
    )
    return response


# ==================== 통계 / Stats ====================

@router.get("/stats/overview")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """DB 통계 요약 (Database Overview Statistics)"""
    total_result = await db.execute(select(func.count(Game.id)))
    total = total_result.scalar()
    analyzed_result = await db.execute(
        select(func.count(Game.id)).where(Game.is_analyzed == True)  # noqa: E712
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
    """사용 가능한 지표 목록 반환 (Available Metrics List)"""
    return {
        "numeric_metrics": NUMERIC_METRIC_FIELDS,
        "boolean_tags": BOOLEAN_TAG_FIELDS,
        "categories": METRIC_CATEGORIES,
        "total_numeric": len(NUMERIC_METRIC_FIELDS),
        "total_tags": len(BOOLEAN_TAG_FIELDS),
        "exclusion_keywords": list(EXCLUSION_KEYWORDS.keys()),
    }


@router.get("/vibes")
async def list_vibes():
    """
    List 12 macro vibes for chip UI.
    Korean: 12개 Macro Vibe 목록 (칩 UI용).

    경로: /api/v1/games/vibes (prefix=/games)
    """
    return {"vibes": get_vibe_list()}


# ==================== 게임 상세 / Game Detail ====================

@router.get("/{app_id}", response_model=GameWithMetrics)
async def get_game_detail(app_id: int, db: AsyncSession = Depends(get_db)):
    """게임 상세 정보 + 60개 지표 반환 (Game Detail with All Metrics)"""
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


# ==================== 추천 / Recommendation ====================

@router.post("/recommend/by-game", response_model=RecommendationResponse)
async def recommend_by_game(
    request: RecommendByGameRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    특정 게임 기반 유사 게임 추천 v5 (Game-Based Recommendation with Anchor Score)

    v5 변경사항:
        - 기준 게임 = 100점 앵커, 결과에서 제외
        - query_hint: 의도 기반 가중치 (예: "림월드 같은 게임")
        - 4단계 가중치 적용 (관련 5x / 연관 2x / 중립 0.5x / 무관 0.1x)
        - 점수 범위 0~99 (기준 게임만 100)

    Request body example:
        {"app_id": 1086940, "count": 5, "query_hint": "림월드 같은 경영 게임"}
    """
    # 1. 캐시 확인 (query_hint 포함 키)
    cache_key = recommendation_cache.by_game_key(request.app_id, request.count)
    cached = await recommendation_cache.get(cache_key)
    if cached:
        return RecommendationResponse(**cached)

    # 2. 추천 계산 (v5: List[Dict] 반환)
    target_game, results = await recommender.recommend_by_game(
        db=db,
        app_id=request.app_id,
        count=request.count,
        exclude_same_developer=request.exclude_same_developer,
        query_hint=getattr(request, "query_hint", None),
    )

    if not target_game:
        raise HTTPException(
            status_code=404,
            detail=f"Game not found or has no metrics: {request.app_id}"
        )

    # 3. 포맷 + 캐시 저장
    recommendations = recommender.format_recommendations_by_game(results)
    response = RecommendationResponse(
        query_type="by_game",
        reference_game=target_game.name,
        total_candidates=len(results),
        recommendations=recommendations,
    )
    await recommendation_cache.set(
        cache_key, response.model_dump(), ttl=recommendation_cache.TTL_BY_GAME,
    )
    return response


@router.post("/recommend/by-preference", response_model=RecommendationResponse)
async def recommend_by_preference(
    request: RecommendByPreferenceRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    유저 선호도 기반 맞춤 추천 v5 (Preference-Based Recommendation)

    v5: 4단계 가중치로 전체 49개 지표 비교. must_not 하드 필터.
    점수 0~99 (절대 점수).
    """
    # 1. 캐시 확인
    cache_key = recommendation_cache.by_preference_key(
        request.preferences,
        request.count,
        must_not=request.must_not or {},
        use_masking=request.use_masking,
        max_review_count=request.max_review_count,
    )
    cached = await recommendation_cache.get(cache_key)
    if cached:
        return RecommendationResponse(**cached)

    # 2. 지표명 검증
    valid_metrics = set(NUMERIC_METRIC_FIELDS)
    invalid = [f for f in request.preferences.keys() if f not in valid_metrics]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown metrics: {invalid}. See /games/metrics/list"
        )

    # 3. 태그명 검증
    valid_tags = set(BOOLEAN_TAG_FIELDS)
    invalid_tags = [
        t for t in (request.required_tags + request.excluded_tags)
        if t not in valid_tags
    ]
    if invalid_tags:
        raise HTTPException(status_code=400, detail=f"Unknown tags: {invalid_tags}")

    # 4. must_not 검증
    must_not = request.must_not or {}
    invalid_must_not = [
        k for k in must_not if k not in valid_metrics and k not in valid_tags
    ]
    if invalid_must_not:
        raise HTTPException(
            status_code=400,
            detail=f"must_not에 알 수 없는 지표/태그: {invalid_must_not}"
        )
    for field, threshold in must_not.items():
        if field in valid_metrics and not (0.0 <= threshold <= 10.0):
            raise HTTPException(
                status_code=400,
                detail=f"must_not 임계값 오류: {field}={threshold} (0~10)"
            )

    # 5. 추천 계산 (v5: List[Dict] 반환)
    results = await recommender.recommend_by_preference(
        db=db,
        preferences=request.preferences,
        required_tags=request.required_tags,
        excluded_tags=request.excluded_tags,
        must_not=must_not,
        count=request.count,
        min_gem_potential=request.min_gem_potential,
        use_masking=request.use_masking,
        max_review_count=request.max_review_count,
    )

    # 6. 포맷 + 캐시 저장
    recommendations = recommender.format_recommendations_by_preference(
        results, preferences=request.preferences
    )
    response = RecommendationResponse(
        query_type="by_preference",
        reference_game=None,
        total_candidates=len(results),
        recommendations=recommendations,
    )
    await recommendation_cache.set(
        cache_key, response.model_dump(), ttl=recommendation_cache.TTL_BY_PREFERENCE,
    )
    return response
# ==================== Vibe Cluster (Phase 2-A) ====================


@router.post("/recommend/by-vibe")
async def recommend_by_vibe(
    vibe_key: str = Query(..., description="Vibe key (예: cozy_escape)"),
    count: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Recommend games by vibe chip (v6 by-preference 재사용).
    Korean: Vibe 칩 클릭 → 해당 preferences로 v6 추천.

    경로: /api/v1/games/recommend/by-vibe?vibe_key=cozy_escape
    """
    prefs = get_vibe_preferences(vibe_key)
    if not prefs:
        raise HTTPException(404, f"Unknown vibe: {vibe_key}")

    results = await recommender.recommend_by_preference(
        db=db, preferences=prefs, count=count,
    )
    recommendations = recommender.format_recommendations_by_preference(
        results, prefs,
    )
    return {
        "vibe": vibe_key,
        "total_candidates": len(recommendations),
        "recommendations": recommendations,
    }
