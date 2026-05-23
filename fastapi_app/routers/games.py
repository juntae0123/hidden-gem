"""
Hidden Gem Games API Router v4 (Dynamic Masking + must_not Integration)

Korean: 원본 v3 구조를 완전히 유지하면서 동적 마스킹 + must_not 하드 필터만 추가한 v4.

v3 → v4 변경사항:
    - recommend_by_preference: must_not 검증 추가, recommender 호출 시 must_not/use_masking 전달
    - recommendation_cache.by_preference_key(): must_not + use_masking 반영
    - /games/metrics/list: exclusion_keywords 필드 추가
    - SemanticSearchRequest, 캐시 패턴, cost_guard 패턴 모두 원본 유지

Endpoints:
    GET  /games/search                   - 이름/장르/개발사 텍스트 검색
    POST /games/search/semantic          - 자연어 시맨틱 검색 (임베딩 기반)
    GET  /games/stats/overview           - DB 통계
    GET  /games/metrics/list             - 사용 가능한 지표 목록
    GET  /games/{app_id}                 - 게임 상세 + 60개 지표
    POST /games/recommend/by-game        - 특정 게임 기반 유사 게임 추천
    POST /games/recommend/by-preference  - 유저 선호도 기반 맞춤 추천 (v4: must_not 지원)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
from services.cache import recommendation_cache
from services.cost_guard import cost_guard

router = APIRouter(prefix="/games", tags=["Games"])


# ==================== 요청 스키마 / Request Schemas ====================

class SemanticSearchRequest(BaseModel):
    """
    Semantic search request schema.
    Korean: 자연어 시맨틱 검색 요청 스키마. 분위기/느낌/유사 게임 설명 자유 입력 가능.

    Example:
        {"query": "혼자 조용히 즐기는 전략 게임", "limit": 12}
        {"query": "Stardew Valley 같은 힐링겜", "limit": 9}
    """
    query: str = Field(
        ...,
        min_length=1,
        max_length=200,
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
    결과는 리뷰 수 내림차순 정렬 (인기 게임 우선).
    """
    stmt = (
        select(Game)
        .options(selectinload(Game.metrics))
        .where(Game.is_active == True)   # noqa: E712
        .where(Game.is_analyzed == True) # noqa: E712
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

        # min_gem 필터 - Python 레벨에서 처리 (JOIN 복잡성 회피)
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

    캐시 확인 → 비용 가드 확인 → GPT 번역 + pgvector 검색 순으로 실행.
    동일 검색어는 1시간 캐시로 OpenAI 비용 절감.
    v4: 검색어에서 must_not 자동 파싱 (예: "공포 없는 힐링" → horror 하드 필터)

    검색 예시:
        - "혼자 조용히 즐기는 전략 게임"
        - "Stardew Valley 같은 힐링겜"
        - "공포 없는 힐링 게임"  ← v4: horror_factor >= 4 자동 제외
        - "죽으면 처음부터인데 중독되는 게임"
    """
    # 1. 캐시 확인 / Check cache first (비용 발생 없음)
    cache_key = recommendation_cache.semantic_key(request.query, request.limit)
    cached = await recommendation_cache.get(cache_key)
    if cached:
        return RecommendationResponse(**cached)

    # 2. 비용 가드 확인 / Check cost guard before OpenAI call
    allowed, reason = await cost_guard.check_before_request("gpt-4.1-mini")
    if not allowed:
        raise HTTPException(
            status_code=503,
            detail=f"서비스 일시 제한: {reason}"
        )

    # 3. 시맨틱 검색 실행 / Execute semantic search
    # v4: semantic_search 내부에서 must_not 자동 파싱 + 하드 필터 적용
    try:
        results = await recommender.semantic_search(
            db=db,
            query=request.query,
            limit=request.limit,
            min_gem_potential=request.min_gem_potential,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시맨틱 검색 실패: {str(e)}")

    # 4. 비용 추적 / Track OpenAI cost (GPT 번역 + 임베딩 추정)
    # GPT-4.1-mini 번역: ~500 토큰, 임베딩: ~100 토큰
    await cost_guard.track_usage(
        model="gpt-4.1-mini",
        input_tokens=500,
        output_tokens=100,
    )
    await cost_guard.track_usage(
        model="text-embedding-3-small",
        input_tokens=100,
    )

    # 5. 포맷 + 캐시 저장 / Format and cache
    recommendations = recommender.format_semantic_results(results)
    response = RecommendationResponse(
        query_type="semantic",
        reference_game=None,
        total_candidates=len(recommendations),
        recommendations=recommendations,
    )

    # 캐시 저장 (직렬화 가능한 dict로) / Save to cache
    await recommendation_cache.set(
        cache_key,
        response.model_dump(),
        ttl=recommendation_cache.TTL_SEMANTIC,
    )

    return response


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
        select(func.count(Game.id)).where(Game.is_analyzed == True)  # noqa: E712
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
    v4: exclusion_keywords 추가 — must_not 자동 완성용.
    """
    return {
        "numeric_metrics": NUMERIC_METRIC_FIELDS,  # 0~10 스케일 수치 지표 49개
        "boolean_tags": BOOLEAN_TAG_FIELDS,        # True/False 태그 9개
        "categories": METRIC_CATEGORIES,           # 카테고리별 분류 (UI 표시용)
        "total_numeric": len(NUMERIC_METRIC_FIELDS),
        "total_tags": len(BOOLEAN_TAG_FIELDS),
        # v4 추가: must_not에 사용 가능한 한국어 키워드 목록
        # v4 new: available Korean exclusion keywords for must_not auto-complete
        "exclusion_keywords": list(EXCLUSION_KEYWORDS.keys()),
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

    캐시 확인 → 추천 계산 → 캐시 저장 순으로 실행.
    기준 게임의 49D 지표 + 1536D 임베딩 하이브리드 유사도로 추천.

    Request body example:
        {"app_id": 1086940, "count": 5, "exclude_same_developer": false}
    """
    # 1. 캐시 확인 / Check cache
    cache_key = recommendation_cache.by_game_key(request.app_id, request.count)
    cached = await recommendation_cache.get(cache_key)
    if cached:
        return RecommendationResponse(**cached)

    # 2. 추천 계산 / Calculate recommendations
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

    # 3. 포맷 + 캐시 저장 / Format and cache
    recommendations = recommender.format_recommendations_by_game(results)
    response = RecommendationResponse(
        query_type="by_game",
        reference_game=target_game.name,
        total_candidates=len(results),
        recommendations=recommendations,
    )

    await recommendation_cache.set(
        cache_key,
        response.model_dump(),
        ttl=recommendation_cache.TTL_BY_GAME,
    )

    return response


@router.post("/recommend/by-preference", response_model=RecommendationResponse)
async def recommend_by_preference(
    request: RecommendByPreferenceRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    유저 선호도 기반 맞춤 추천 v4 (Preference-Based Recommendation with Dynamic Masking)

    캐시 확인 → 지표명 검증 → 추천 계산 → 캐시 저장 순으로 실행.

    v4 변경사항:
        - must_not: 명시적 제외 조건 ({지표명: 임계값}). 해당 지표 >= 임계값이면 게임 제외.
        - use_masking: 동적 마스킹 활성화 (기본 True). 지정 지표만 활성화 → 변별력 5배 향상.
        - 캐시 키에 must_not + use_masking 해시 포함.

    Request body example (v4):
        {
            "preferences": {"cozy_factor": 8, "strategic_depth": 7},
            "required_tags": ["has_crafting"],
            "excluded_tags": ["has_permadeath"],
            "must_not": {"horror_factor": 4.0},
            "count": 5,
            "min_gem_potential": 60,
            "use_masking": true
        }
    """
    # 1. 캐시 확인 / Check cache
    # must_not, use_masking 포함하여 캐시 키 생성
    cache_key = recommendation_cache.by_preference_key(
        request.preferences,
        request.count,
        must_not=request.must_not or {},
        use_masking=request.use_masking,
    )
    cached = await recommendation_cache.get(cache_key)
    if cached:
        return RecommendationResponse(**cached)

    # 2. 지표명 사전 검증 / Validate metric field names
    valid_metrics = set(NUMERIC_METRIC_FIELDS)
    invalid = [f for f in request.preferences.keys() if f not in valid_metrics]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown metrics: {invalid}. See /games/metrics/list"
        )

    # 3. 태그명 검증 / Validate tag names
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

    # 4. must_not 검증 / Validate must_not
    # 수치 지표 또는 Boolean 태그만 허용, 임계값 범위 체크
    must_not = request.must_not or {}
    invalid_must_not = [
        k for k in must_not
        if k not in valid_metrics and k not in valid_tags
    ]
    if invalid_must_not:
        raise HTTPException(
            status_code=400,
            detail=f"must_not에 알 수 없는 지표/태그: {invalid_must_not}. See /games/metrics/list"
        )
    # 수치 지표 임계값 범위 검증 (0~10)
    for field, threshold in must_not.items():
        if field in valid_metrics and not (0.0 <= threshold <= 10.0):
            raise HTTPException(
                status_code=400,
                detail=f"must_not 임계값 오류: {field}={threshold} (0~10 범위여야 함)"
            )

    # 5. 추천 계산 / Calculate recommendations
    # v4: must_not + use_masking 파라미터 전달
    results = await recommender.recommend_by_preference(
        db=db,
        preferences=request.preferences,
        required_tags=request.required_tags,
        excluded_tags=request.excluded_tags,
        must_not=must_not,
        count=request.count,
        min_gem_potential=request.min_gem_potential,
        use_masking=request.use_masking,
    )

    # 6. 포맷 + 캐시 저장 / Format and cache
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
        cache_key,
        response.model_dump(),
        ttl=recommendation_cache.TTL_BY_PREFERENCE,
    )

    return response