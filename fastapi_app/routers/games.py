"""
게임 API 라우터 v3 (Games API Router)

/api/v1/games 하위 모든 엔드포인트 정의.
검색/상세 조회와 세 가지 추천 방식(by-game, by-preference, semantic)을 제공.

Endpoints:
    GET  /games/search                   - 이름/장르/개발사 텍스트 검색
    POST /games/search/semantic          - 자연어 시맨틱 검색 (임베딩 기반)
    GET  /games/stats/overview           - DB 통계 (전체 게임 수, 평균 gem_potential 등)
    GET  /games/metrics/list             - 사용 가능한 지표 목록
    GET  /games/{app_id}                 - 게임 상세 + 60개 지표
    POST /games/recommend/by-game        - 특정 게임 기반 유사 게임 추천
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
    RecommendationResponse,
)
from services.recommender import recommender

router = APIRouter(prefix="/games", tags=["Games"])


# ==================== 요청 스키마 / Request Schemas ====================

class SemanticSearchRequest(BaseModel):
    """
    시맨틱 검색 요청 스키마 (Semantic Search Request Schema)

    자연어 쿼리와 검색 옵션을 담는 Pydantic 모델.
    query에 게임 이름 대신 느낌, 분위기, 유사 게임 설명 등 자유 형식 입력 가능.

    Example:
        {"query": "혼자 조용히 즐기는 전략 게임", "limit": 12}
        {"query": "Stardew Valley 같은 힐링겜", "limit": 9}
    """
    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="자연어 검색어 / Natural language search query",
    )
    limit: int = Field(
        default=12,
        ge=1,
        le=50,
        description="반환할 최대 게임 수 / Max number of results",
    )
    min_gem_potential: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="최소 gem_potential 필터 / Minimum gem potential filter",
    )


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

    이름/장르/개발사에 대해 대소문자 무관 부분 일치(ilike) 검색.
    자연어/의미 기반 검색은 POST /search/semantic 사용.
    min_gem 필터는 DB 쿼리가 아닌 Python 레벨에서 처리 (JOIN 복잡성 회피).
    결과는 리뷰 수 내림차순 정렬 (인기 게임 우선).
    """
    stmt = (
        select(Game)
        .options(selectinload(Game.metrics))  # metrics JOIN - gem_potential 조회용
        .where(Game.is_active == True)
        .where(Game.is_analyzed == True)
    )

    if q:
        term = f"%{q}%"
        # 이름, 장르, 개발사에 대해 OR 검색 (ilike = 대소문자 무시)
        stmt = stmt.where(
            or_(
                Game.name.ilike(term),
                Game.genres.ilike(term),
                Game.developer.ilike(term),
            )
        )

    if genre:
        stmt = stmt.where(Game.genres.ilike(f"%{genre}%"))

    # 리뷰 많은 게임(= 검증된 게임) 우선 정렬
    stmt = stmt.order_by(Game.review_count.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    games = result.scalars().all()

    results = []
    for game in games:
        gem = game.metrics.gem_potential if game.metrics else None

        # min_gem 필터 - DB 레벨이 아닌 Python 레벨에서 처리
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


@router.post("/search/semantic", response_model=RecommendationResponse)
async def semantic_search(
    request: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    자연어 시맨틱 검색 (Natural Language Semantic Search)

    쿼리를 OpenAI text-embedding-3-small로 임베딩 변환 후
    pgvector 코사인 유사도(<=>)로 관련 게임 검색.

    일반 검색과 달리 게임 이름이 아닌 느낌/분위기/설명으로 검색 가능:
        - "혼자 조용히 즐기는 전략 게임"
        - "Stardew Valley 같은 힐링겜"
        - "죽으면 처음부터인데 중독되는 게임"
        - "Dark Souls 분위기인데 좀 쉬운 거"
    """
    try:
        results = await recommender.semantic_search(
            db=db,
            query=request.query,
            limit=request.limit,
            min_gem_potential=request.min_gem_potential,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시맨틱 검색 실패: {str(e)}")

    recommendations = recommender.format_semantic_results(results)

    return RecommendationResponse(
        query_type="semantic",
        reference_game=None,
        total_candidates=len(recommendations),
        recommendations=recommendations,
    )


# ==================== 통계 / Stats ====================

@router.get("/stats/overview")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """
    DB 통계 요약 (Database Overview Statistics)

    전체/분석완료 게임 수, 평균 gem_potential, 지표 차원 정보를 반환.
    프론트엔드 대시보드 및 API 상태 모니터링용.
    """
    total_result = await db.execute(select(func.count(Game.id)))
    total = total_result.scalar()

    analyzed_result = await db.execute(
        select(func.count(Game.id)).where(Game.is_analyzed == True)
    )
    analyzed = analyzed_result.scalar()

    # 전체 게임의 평균 gem_potential (데이터 품질 지표)
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
    """
    사용 가능한 지표 목록 반환 (Available Metrics List)

    by-preference 추천 요청 시 preferences 키로 사용 가능한 지표명 목록.
    프론트엔드에서 선호도 입력 UI를 동적으로 구성할 때 활용.
    """
    return {
        "numeric_metrics": NUMERIC_METRIC_FIELDS,  # 0~10 스케일 수치 지표 49개
        "boolean_tags": BOOLEAN_TAG_FIELDS,        # True/False 태그 9개
        "categories": METRIC_CATEGORIES,           # 카테고리별 분류 (UI 표시용)
        "total_numeric": len(NUMERIC_METRIC_FIELDS),
        "total_tags": len(BOOLEAN_TAG_FIELDS),
    }


# ==================== 게임 상세 / Game Detail ====================

@router.get("/{app_id}", response_model=GameWithMetrics)
async def get_game_detail(app_id: int, db: AsyncSession = Depends(get_db)):
    """
    게임 상세 정보 + 60개 지표 반환 (Game Detail with All Metrics)

    단일 게임의 기본 정보(Steam 메타데이터, AI 생성 콘텐츠)와
    60개 지표(49 수치 + 9 태그 + 2 평가)를 함께 반환.

    Args:
        app_id: Steam App ID

    Raises:
        404: 해당 app_id의 게임이 DB에 없을 때
    """
    stmt = (
        select(Game)
        .options(selectinload(Game.metrics))  # 지표를 함께 로드 (N+1 방지)
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
    특정 게임 기반 유사 게임 추천 (Game-Based Recommendation)

    기준 게임의 49D 지표 + 1536D 임베딩을 사용한 하이브리드 유사도로
    가장 유사한 게임들을 추천. 각 추천 게임에 공통 특징(match_reasons) 포함.

    Request body example:
        {"app_id": 1086940, "count": 5, "exclude_same_developer": false}
    """
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

    # by-game 전용 포맷: target_vec와 비교해 공통 특징 추출
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
    """
    유저 선호도 기반 맞춤 추천 (Preference-Based Recommendation)

    원하는 게임 특성(지표값)과 태그를 지정하면 그에 맞는 게임 추천.
    지표명은 /games/metrics/list에서 확인 가능.

    Request body example:
        {
            "preferences": {"cozy_factor": 8, "strategic_depth": 7},
            "required_tags": ["has_crafting"],
            "excluded_tags": ["has_permadeath"],
            "count": 5,
            "min_gem_potential": 60
        }
    """
    # 지표명 사전 검증 - 잘못된 키로 조용히 무시되는 것 방지
    valid_metrics = set(NUMERIC_METRIC_FIELDS)
    invalid = [f for f in request.preferences.keys() if f not in valid_metrics]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown metrics: {invalid}. See /games/metrics/list"
        )

    # 태그명 사전 검증
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

    # by-preference 전용 포맷: 선호 지표와 매칭 이유 생성
    recommendations = recommender.format_recommendations_by_preference(
        results, preferences=request.preferences
    )

    return RecommendationResponse(
        query_type="by_preference",
        reference_game=None,
        total_candidates=len(results),
        recommendations=recommendations,
    )