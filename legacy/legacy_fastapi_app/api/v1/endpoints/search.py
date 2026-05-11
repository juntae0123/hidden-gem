# fastapi_app/api/v1/endpoints/search.py
"""
Hidden Gem - 검색 API 엔드포인트

전체 파이프라인 통합:
Validator → Parser → Retriever → Reranker → Scorer

Traceability: search_id (UUID) 발급
"""

import time
from uuid import uuid4
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.search import (
    SearchRequest,
    SearchResponse,
    SimilarGameRequest,
    GameResult,
    MatchScoreResult,
    QualityBonusDetail,
    PersonalBiasDetail,
    ScoreBreakdown,
    SearchMetrics,
    SearchType,
    MetricPreference,
    PreferenceType,
)
from schemas.llm_outputs import QueryParseOutput

from services.query_validator import query_validator, ValidationResult
from services.query_parser import get_query_parser
from services.cache_service import get_semantic_cache
from services.retriever import retriever
from services.reranker import reranker
from services.scorer import scorer
from services.fallback_handler import fallback_handler

from models.user import User, SearchLog
from core.rate_limiter import rate_limit_middleware
from core.security import prompt_injection_filter
from core.exceptions import (
    RateLimitExceededError,
    GameUnrelatedQueryError,
    QueryParsingError,
)
from database import get_db
from config import settings


router = APIRouter(prefix="/search", tags=["Search"])


# ============================================================
# 의존성
# ============================================================

async def check_rate_limit(request: Request):
    """Rate Limit 체크"""
    allowed, retry_after = rate_limit_middleware.check(request)
    if not allowed:
        raise RateLimitExceededError(retry_after_seconds=retry_after)


async def get_optional_user(
    db: AsyncSession = Depends(get_db),
    user_id: Optional[int] = None,
) -> Optional[User]:
    """선택적 유저 조회"""
    if user_id:
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    return None


# ============================================================
# 메인 검색 엔드포인트
# ============================================================

@router.post(
    "/",
    response_model=SearchResponse,
    summary="통합 게임 검색",
    description="자연어 또는 게임명으로 게임 검색. search_id로 피드백 추적 가능.",
)
async def search_games(
    request: SearchRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(check_rate_limit),
):
    """
    통합 검색 API
    
    Pipeline:
    1. Rate Limit 체크
    2. Prompt Injection 방어
    3. 쿼리 검증
    4. Semantic Cache 확인
    5. LLM 파싱
    6. Two-Tower ANN 검색
    7. NumPy 벡터화 재정렬
    8. Bayesian Scoring
    9. 결과 반환 + 로깅
    
    Returns:
        SearchResponse: search_id 포함된 검색 결과
    """
    
    # 고유 검색 ID 생성 (Traceability)
    search_id = str(uuid4())
    
    metrics = SearchMetrics()
    start_time = time.time()
    
    try:
        # ========== 1. Prompt Injection 방어 ==========
        security_check = prompt_injection_filter.check(request.query)
        if not security_check.is_safe:
            return _create_error_response(
                search_id=search_id,
                query=request.query,
                error_type="security_blocked",
                message="안전하지 않은 검색어입니다.",
            )
        
        working_query = security_check.sanitized_input or request.query
        
        # ========== 2. 쿼리 검증 ==========
        t0 = time.time()
        validation = query_validator.validate(working_query)
        metrics.validation_time_ms = (time.time() - t0) * 1000
        
        if not validation.is_valid:
            return _create_validation_error_response(
                search_id=search_id,
                query=request.query,
                validation=validation,
                metrics=metrics,
            )
        
        working_query = validation.sanitized_query or working_query
        
        # ========== 3. Semantic Cache 확인 ==========
        cache = await get_semantic_cache()
        cached_result = await cache.get(working_query)
        
        if cached_result:
            # 캐시 히트!
            cached_result["search_id"] = search_id
            cached_result["cache_hit"] = True
            cached_result["timestamp"] = datetime.utcnow().isoformat()
            
            # 검색 로그 저장
            await _log_search(
                db=db,
                search_id=search_id,
                user_id=request.user_id,
                query=request.query,
                search_type="cache",
                result_count=cached_result.get("result_count", 0),
                cache_hit=True,
            )
            
            return SearchResponse(**cached_result)
        
        # ========== 4. LLM 파싱 ==========
        t1 = time.time()
        
        parser = get_query_parser(settings.OPENAI_API_KEY)
        
        try:
            parsed = await parser.parse(working_query)
        except GameUnrelatedQueryError as e:
            return _create_irrelevant_response(
                search_id=search_id,
                query=request.query,
                message=str(e),
            )
        except QueryParsingError:
            fallback = fallback_handler.handle_parsing_failure()
            return _create_fallback_response(
                search_id=search_id,
                query=request.query,
                fallback=fallback,
                metrics=metrics,
            )
        
        metrics.parsing_time_ms = (time.time() - t1) * 1000
        
        # ========== 5. 유저 개인화 정보 ==========
        user = await get_optional_user(db, request.user_id)
        personal_bias = user.get_personal_bias() if user else {}
        user_taste_dna = user.taste_dna if user else None
        
        # ========== 6. 검색 유형 분기 ==========
        reference_game = None
        
        if parsed.detected_game_name:
            # Type A: 게임명 기반 검색
            search_result = await _search_by_game_name(
                db=db,
                game_name=parsed.detected_game_name,
                parsed=parsed,
                request=request,
                metrics=metrics,
                personal_bias=personal_bias,
                user_taste_dna=user_taste_dna,
            )
            
            if search_result.get("not_found"):
                fallback = search_result["fallback"]
                return _create_fallback_response(
                    search_id=search_id,
                    query=request.query,
                    fallback=fallback,
                    metrics=metrics,
                )
            
            reference_game = search_result.get("reference_game")
            scored_results = search_result.get("results", [])
            total_candidates = search_result.get("total_candidates", 0)
            search_type = SearchType.GAME_NAME
        
        else:
            # Type B/C: 자연어 검색
            search_result = await _search_natural_language(
                db=db,
                parsed=parsed,
                request=request,
                metrics=metrics,
                personal_bias=personal_bias,
                user_taste_dna=user_taste_dna,
            )
            
            scored_results = search_result.get("results", [])
            total_candidates = search_result.get("total_candidates", 0)
            search_type = SearchType.NATURAL_LANGUAGE
        
        # ========== 7. 결과 필터링 ==========
        filtered_results = [
            r for r in scored_results
            if r.final_score.final_match_score >= request.min_score
        ][:request.limit]
        
        # 결과 없음 → 폴백
        if not filtered_results:
            fallback = fallback_handler.handle_empty_results(
                original_query=request.query,
                strict_conditions=[],  # TODO: parsed에서 추출
            )
            
            return _create_fallback_response(
                search_id=search_id,
                query=request.query,
                fallback=fallback,
                metrics=metrics,
                interpretation=parsed.interpretation,
            )
        
        # ========== 8. 응답 구성 ==========
        game_results = [_to_game_result(r) for r in filtered_results]
        
        metrics.final_results = len(game_results)
        metrics.total_time_ms = (time.time() - start_time) * 1000
        
        response = SearchResponse(
            search_id=search_id,
            success=True,
            query=request.query,
            search_type=search_type,
            interpretation=parsed.interpretation,
            total_candidates=total_candidates,
            result_count=len(game_results),
            results=game_results,
            processing_time_ms=round(metrics.total_time_ms, 2),
            llm_used=parsed.model_used if hasattr(parsed, 'model_used') else "gpt-4o-mini",
            cache_hit=False,
            reference_game=reference_game,
            metrics=metrics,
        )
        
        # ========== 9. 캐시 저장 ==========
        await cache.set(
            query=working_query,
            result=response.model_dump(exclude={"search_id", "timestamp"}),
        )
        
        # ========== 10. 검색 로그 저장 ==========
        await _log_search(
            db=db,
            search_id=search_id,
            user_id=request.user_id,
            query=request.query,
            search_type=search_type.value,
            result_count=len(game_results),
            processing_time_ms=metrics.total_time_ms,
            cache_hit=False,
            top_results=[r.app_id for r in game_results[:5]],
            interpretation=parsed.interpretation,
        )
        
        return response
    
    except RateLimitExceededError as e:
        return JSONResponse(
            status_code=429,
            content={
                "search_id": search_id,
                "success": False,
                "error_code": "rate_limit_exceeded",
                "message": e.user_message,
                "retry_after_seconds": e.retry_after_seconds,
            },
            headers={"Retry-After": str(e.retry_after_seconds)},
        )
    
    except Exception as e:
        # 예상치 못한 에러
        metrics.total_time_ms = (time.time() - start_time) * 1000
        
        return _create_error_response(
            search_id=search_id,
            query=request.query,
            error_type="internal_error",
            message="검색 중 문제가 발생했어요. 잠시 후 다시 시도해주세요.",
            metrics=metrics,
        )


# ============================================================
# 유사 게임 검색 엔드포인트
# ============================================================

@router.get(
    "/game/{app_id}/similar",
    response_model=SearchResponse,
    summary="유사 게임 검색",
)
async def get_similar_games(
    app_id: int,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(check_rate_limit),
):
    """특정 게임과 유사한 게임 검색"""
    
    search_id = str(uuid4())
    start_time = time.time()
    
    try:
        # 게임 조회
        reference_game = await retriever.get_game_by_app_id(db, app_id)
        
        if not reference_game:
            return _create_error_response(
                search_id=search_id,
                query=f"app_id={app_id}",
                error_type="game_not_found",
                message=f"게임을 찾을 수 없습니다 (App ID: {app_id})",
            )
        
        # 유사 게임 검색
        user_metrics = retriever.game_to_user_preferences(reference_game)
        
        candidates = await retriever.retrieve(
            db=db,
            user_metrics=user_metrics,
            exclude_app_ids=[app_id],
        )
        
        # 재정렬 & 점수 계산
        reranked = reranker.rerank(
            candidates=candidates,
            user_metrics=user_metrics,
        )
        
        scored = scorer.score_all(reranked)
        
        # 결과 변환
        game_results = [_to_game_result(r) for r in scored[:limit]]
        
        processing_time = (time.time() - start_time) * 1000
        
        return SearchResponse(
            search_id=search_id,
            success=True,
            query=f"{reference_game.name} 유사 게임",
            search_type=SearchType.SIMILAR,
            interpretation=f"'{reference_game.name}'과(와) 비슷한 게임",
            total_candidates=len(candidates),
            result_count=len(game_results),
            results=game_results,
            processing_time_ms=round(processing_time, 2),
            reference_game=reference_game.name,
        )
    
    except Exception as e:
        return _create_error_response(
            search_id=search_id,
            query=f"app_id={app_id}",
            error_type="internal_error",
            message="유사 게임 검색 중 오류가 발생했습니다.",
        )


# ============================================================
# 내부 헬퍼 함수
# ============================================================

async def _search_by_game_name(
    db: AsyncSession,
    game_name: str,
    parsed,
    request: SearchRequest,
    metrics: SearchMetrics,
    personal_bias: dict,
    user_taste_dna,
) -> dict:
    """게임명 기반 검색"""
    
    # 게임 조회
    reference_game = await retriever.search_game_by_name(db, game_name)
    
    if not reference_game:
        # 오타 교정 시도
        fallback = fallback_handler.handle_game_not_found(game_name)
        
        if fallback.corrected_name:
            reference_game = await retriever.search_game_by_name(db, fallback.corrected_name)
        
        if not reference_game:
            return {"not_found": True, "fallback": fallback}
    
    # 참조 게임의 지표를 유저 선호로 변환
    user_metrics = retriever.game_to_user_preferences(reference_game)
    
    # 검색
    t2 = time.time()
    exclude_ids = list(set(request.exclude_app_ids + [reference_game.app_id]))
    
    candidates = await retriever.retrieve(
        db=db,
        user_metrics=user_metrics,
        personal_bias=personal_bias,
        exclude_app_ids=exclude_ids,
    )
    metrics.retrieval_time_ms = (time.time() - t2) * 1000
    metrics.stage1_candidates = len(candidates)
    
    # 재정렬
    t3 = time.time()
    reranked = reranker.rerank(
        candidates=candidates,
        user_metrics=user_metrics,
        personal_bias=personal_bias,
    )
    metrics.reranking_time_ms = (time.time() - t3) * 1000
    
    # 점수 계산
    t4 = time.time()
    scored = scorer.score_all(
        reranked=reranked,
        user_taste_dna=user_taste_dna,
    )
    metrics.scoring_time_ms = (time.time() - t4) * 1000
    
    return {
        "results": scored,
        "total_candidates": len(candidates),
        "reference_game": reference_game.name,
    }


async def _search_natural_language(
    db: AsyncSession,
    parsed,
    request: SearchRequest,
    metrics: SearchMetrics,
    personal_bias: dict,
    user_taste_dna,
) -> dict:
    """자연어 기반 검색"""
    
    # 파싱 결과 → MetricPreference 변환
    user_metrics = _parsed_to_preferences(parsed)
    user_tags = _parsed_to_tag_preferences(parsed)
    
    # 직접 입력 병합
    if request.metrics:
        user_metrics.update(request.metrics)
    if request.tags:
        user_tags.update(request.tags)
    
    # 검색
    t2 = time.time()
    candidates = await retriever.retrieve(
        db=db,
        user_metrics=user_metrics,
        user_tags=user_tags,
        personal_bias=personal_bias,
        exclude_app_ids=request.exclude_app_ids,
    )
    metrics.retrieval_time_ms = (time.time() - t2) * 1000
    metrics.stage1_candidates = len(candidates)
    
    if not candidates:
        return {"results": [], "total_candidates": 0}
    
    # 재정렬
    t3 = time.time()
    reranked = reranker.rerank(
        candidates=candidates,
        user_metrics=user_metrics,
        personal_bias=personal_bias,
    )
    metrics.reranking_time_ms = (time.time() - t3) * 1000
    
    # 점수 계산
    t4 = time.time()
    scored = scorer.score_all(
        reranked=reranked,
        user_taste_dna=user_taste_dna,
    )
    metrics.scoring_time_ms = (time.time() - t4) * 1000
    
    return {
        "results": scored,
        "total_candidates": len(candidates),
    }


def _parsed_to_preferences(parsed) -> dict:
    """파싱 결과 → MetricPreference 변환"""
    preferences = {}
    
    if hasattr(parsed, 'metrics') and parsed.metrics:
        metrics_dict = parsed.metrics.to_dict() if hasattr(parsed.metrics, 'to_dict') else {}
        
        for metric_name, metric_data in metrics_dict.items():
            if metric_data and metric_data.get("value") is not None:
                preferences[metric_name] = MetricPreference(
                    value=metric_data["value"],
                    type=PreferenceType(metric_data.get("type", "NEUTRAL")),
                    confidence=metric_data.get("confidence", 0.8),
                )
    
    return preferences


def _parsed_to_tag_preferences(parsed) -> dict:
    """파싱 결과 → TagPreference 변환"""
    from schemas.search import TagPreference
    
    tags = {}
    
    if hasattr(parsed, 'tags') and parsed.tags:
        tags_dict = parsed.tags.to_dict() if hasattr(parsed.tags, 'to_dict') else {}
        
        for tag_name, tag_data in tags_dict.items():
            if tag_data and tag_data.get("value") is not None:
                tags[tag_name] = TagPreference(
                    value=tag_data["value"],
                    type=tag_data.get("type", "NEUTRAL"),
                    confidence=tag_data.get("confidence", 0.8),
                )
    
    return tags


def _to_game_result(scored) -> GameResult:
    """ScoredCandidate → GameResult 변환"""
    
    candidate = scored.reranked.candidate
    final = scored.final_score
    reranked = scored.reranked
    
    return GameResult(
        app_id=candidate.app_id,
        name=candidate.name,
        genres=candidate.genres,
        description=candidate.description[:500] if candidate.description else "",
        header_image=candidate.header_image,
        score=MatchScoreResult(
            base_match_score=final.base_match_score,
            quality_bonus=QualityBonusDetail(
                bayesian_score=final.quality_bonus.bayesian_score,
                gem_potential=final.quality_bonus.gem_potential,
                review_count=final.quality_bonus.review_count,
                popularity_modifier=final.quality_bonus.popularity_modifier,
                discovery_bonus=final.quality_bonus.discovery_bonus,
                final_multiplier=final.quality_bonus.final_multiplier,
            ),
            personal_bias=PersonalBiasDetail(
                taste_similarity=final.personal_bias.taste_similarity,
                history_boost=final.personal_bias.history_boost,
                total_adjustment=final.personal_bias.total_adjustment,
            ),
            final_gem_score=final.final_match_score,
            breakdown=ScoreBreakdown(
                category_scores=reranked.category_scores,
                penalty_details=reranked.penalty_details,
                matched_metrics=reranked.matched_metrics,
                mismatched_metrics=reranked.mismatched_metrics,
            ),
        ),
        ai_curation_summary=final.ai_summary,
        match_reasons=scored.match_reasons,
        caution_reasons=scored.caution_reasons,
        tags=candidate.tags,
        analysis_method=candidate.analysis_method,
    )


async def _log_search(
    db: AsyncSession,
    search_id: str,
    user_id: Optional[int],
    query: str,
    search_type: str,
    result_count: int,
    processing_time_ms: float = 0,
    cache_hit: bool = False,
    top_results: List[int] = None,
    interpretation: str = None,
):
    """검색 로그 저장"""
    
    log = SearchLog(
        search_id=search_id,
        user_id=user_id,
        query=query,
        search_type=search_type,
        result_count=result_count,
        processing_time_ms=processing_time_ms,
        cache_hit=cache_hit,
        top_results=top_results or [],
        interpretation=interpretation,
    )
    
    db.add(log)
    await db.commit()


# ============================================================
# 응답 헬퍼 함수
# ============================================================

def _create_error_response(
    search_id: str,
    query: str,
    error_type: str,
    message: str,
    metrics: SearchMetrics = None,
) -> SearchResponse:
    """에러 응답 생성"""
    
    return SearchResponse(
        search_id=search_id,
        success=False,
        query=query,
        search_type=SearchType.FALLBACK,
        interpretation=None,
        total_candidates=0,
        result_count=0,
        results=[],
        processing_time_ms=metrics.total_time_ms if metrics else 0,
        fallback_message=message,
        fallback_suggestions=["다른 검색어로 시도해보세요"],
    )


def _create_validation_error_response(
    search_id: str,
    query: str,
    validation,
    metrics: SearchMetrics,
) -> SearchResponse:
    """검증 에러 응답"""
    
    return SearchResponse(
        search_id=search_id,
        success=False,
        query=query,
        search_type=SearchType.FALLBACK,
        total_candidates=0,
        result_count=0,
        results=[],
        processing_time_ms=metrics.validation_time_ms,
        fallback_message=validation.message,
        fallback_suggestions=[validation.suggestion] if validation.suggestion else [],
    )


def _create_irrelevant_response(
    search_id: str,
    query: str,
    message: str,
) -> SearchResponse:
    """게임 무관 검색 응답"""
    
    return SearchResponse(
        search_id=search_id,
        success=False,
        query=query,
        search_type=SearchType.FALLBACK,
        interpretation="게임과 무관한 검색",
        total_candidates=0,
        result_count=0,
        results=[],
        fallback_message="저는 게임 추천 전문이에요! 🎮",
        fallback_suggestions=[
            "어떤 게임을 찾으시나요?",
            "예: '힐링 게임', 'Hades 같은 거'"
        ],
    )


def _create_fallback_response(
    search_id: str,
    query: str,
    fallback,
    metrics: SearchMetrics,
    interpretation: str = None,
) -> SearchResponse:
    """폴백 응답"""
    
    # 인기 게임 추천을 GameResult로 변환
    fallback_results = []
    if hasattr(fallback, 'recommended_games'):
        for game in fallback.recommended_games[:5]:
            fallback_results.append(GameResult(
                app_id=game.app_id,
                name=game.name,
                genres=game.genres,
                description=game.reason,
                score=MatchScoreResult(
                    base_match_score=0,
                    final_gem_score=0,
                    quality_bonus=QualityBonusDetail(),
                    personal_bias=PersonalBiasDetail(),
                ),
                match_reasons=[f"💡 {game.reason}"],
                is_fallback=True,
            ))
    
    return SearchResponse(
        search_id=search_id,
        success=True,  # 검색은 성공, 결과만 없음
        query=query,
        search_type=SearchType.FALLBACK,
        interpretation=interpretation,
        total_candidates=0,
        result_count=len(fallback_results),
        results=fallback_results,
        processing_time_ms=metrics.total_time_ms if metrics else 0,
        fallback_message=fallback.message,
        fallback_suggestions=fallback.suggestions if hasattr(fallback, 'suggestions') else [],
    )
