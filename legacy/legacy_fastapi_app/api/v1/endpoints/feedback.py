# fastapi_app/api/v1/endpoints/feedback.py
"""
Hidden Gem - 피드백 API

유저 행동 추적 및 취향 DNA 학습:
- 클릭: 관심 표현
- 별점: 명시적 평가
- 위시리스트: 강한 관심
- 구매: 최종 전환

취향 DNA 업데이트 로직 포함
"""

import numpy as np
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.feedback import (
    FeedbackRequest,
    FeedbackResponse,
    BatchFeedbackRequest,
    FeedbackType,
    UserTasteProfile,
)
from models.user import User, UserFeedback, SearchLog
from models.game import Game, GameMetric
from core.constants import ALL_NUMERIC_METRICS
from database import get_db


router = APIRouter(prefix="/feedback", tags=["Feedback"])


# ============================================================
# 피드백 가중치 설정
# ============================================================

FEEDBACK_WEIGHTS = {
    FeedbackType.CLICK: 0.1,           # 클릭: 약한 긍정 신호
    FeedbackType.RATING: 1.0,          # 별점: 강한 신호 (값에 따라 조정)
    FeedbackType.WISHLIST: 0.5,        # 위시리스트: 중간 긍정 신호
    FeedbackType.NOT_INTERESTED: -0.3, # 관심없음: 부정 신호
    FeedbackType.PURCHASE: 0.8,        # 구매: 강한 긍정 신호
}


# ============================================================
# 피드백 기록 엔드포인트
# ============================================================

@router.post(
    "/",
    response_model=FeedbackResponse,
    summary="피드백 기록",
    description="유저 피드백(클릭, 별점 등)을 기록하고 취향 DNA 업데이트",
)
async def record_feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    피드백 기록
    
    1. 피드백 저장
    2. 유저 통계 업데이트
    3. 취향 DNA 업데이트 (로그인 유저)
    
    Returns:
        FeedbackResponse: 피드백 ID 및 DNA 업데이트 여부
    """
    
    # 1. 피드백 저장
    feedback = UserFeedback(
        user_id=request.user_id,
        search_id=request.search_id,
        game_app_id=request.game_app_id,
        feedback_type=request.feedback_type.value,
        rating=request.rating if request.feedback_type == FeedbackType.RATING else None,
        result_position=request.result_position,
    )
    
    db.add(feedback)
    await db.flush()  # ID 생성
    
    taste_dna_updated = False
    
    # 2. 유저 통계 업데이트 + 취향 DNA (로그인 유저)
    if request.user_id:
        # 유저 조회
        result = await db.execute(select(User).where(User.id == request.user_id))
        user = result.scalar_one_or_none()
        
        if user:
            # 통계 업데이트
            if request.feedback_type == FeedbackType.CLICK:
                user.total_clicks += 1
            elif request.feedback_type == FeedbackType.RATING:
                user.total_ratings += 1
            
            user.last_active_at = datetime.utcnow()
            
            # 취향 DNA 업데이트
            taste_dna_updated = await _update_taste_dna(
                db=db,
                user=user,
                game_app_id=request.game_app_id,
                feedback_type=request.feedback_type,
                rating=request.rating,
            )
    
    await db.commit()
    
    return FeedbackResponse(
        success=True,
        feedback_id=feedback.id,
        message="피드백이 기록되었습니다.",
        taste_dna_updated=taste_dna_updated,
    )


@router.post(
    "/batch",
    response_model=List[FeedbackResponse],
    summary="배치 피드백 기록",
)
async def record_batch_feedback(
    request: BatchFeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """여러 피드백을 한번에 기록"""
    
    responses = []
    
    for fb in request.feedbacks:
        try:
            response = await record_feedback(fb, db)
            responses.append(response)
        except Exception as e:
            responses.append(FeedbackResponse(
                success=False,
                feedback_id=0,
                message=f"피드백 기록 실패: {str(e)}",
                taste_dna_updated=False,
            ))
    
    return responses


# ============================================================
# 유저 취향 프로필 조회
# ============================================================

@router.get(
    "/profile/{user_id}",
    response_model=UserTasteProfile,
    summary="유저 취향 프로필 조회",
)
async def get_user_profile(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """유저의 취향 프로필 조회"""
    
    # 유저 조회
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    
    # 취향 DNA 분석
    top_preferred = []
    top_avoided = []
    
    if user.taste_dna is not None:
        dna = np.array(user.taste_dna)
        
        # 높은 값 (선호)
        high_indices = np.argsort(dna)[-5:][::-1]
        top_preferred = [ALL_NUMERIC_METRICS[i] for i in high_indices if dna[i] > 5.5]
        
        # 낮은 값 (기피)
        low_indices = np.argsort(dna)[:5]
        top_avoided = [ALL_NUMERIC_METRICS[i] for i in low_indices if dna[i] < 4.5]
    
    # 평균 별점 계산
    rating_result = await db.execute(
        select(UserFeedback.rating)
        .where(UserFeedback.user_id == user_id)
        .where(UserFeedback.rating.isnot(None))
    )
    ratings = [r[0] for r in rating_result.fetchall() if r[0]]
    average_rating = sum(ratings) / len(ratings) if ratings else None
    
    return UserTasteProfile(
        user_id=user_id,
        top_preferred_metrics=top_preferred,
        top_avoided_metrics=top_avoided,
        total_searches=user.total_searches,
        total_clicks=user.total_clicks,
        total_ratings=user.total_ratings,
        average_rating=round(average_rating, 2) if average_rating else None,
        last_active_at=user.last_active_at,
    )


# ============================================================
# 취향 DNA 업데이트 로직
# ============================================================

async def _update_taste_dna(
    db: AsyncSession,
    user: User,
    game_app_id: int,
    feedback_type: FeedbackType,
    rating: Optional[float],
) -> bool:
    """
    취향 DNA 업데이트
    
    알고리즘:
    1. 게임의 지표 벡터 가져오기
    2. 피드백 유형에 따른 학습률 결정
    3. DNA 벡터 업데이트 (Exponential Moving Average)
    
    수식:
    new_dna = (1 - α) × old_dna + α × game_vector × signal
    
    - α (학습률): 피드백 강도에 비례
    - signal: 긍정(+) 또는 부정(-)
    """
    
    # 1. 게임 지표 조회
    result = await db.execute(
        select(GameMetric)
        .join(Game)
        .where(Game.app_id == game_app_id)
    )
    game_metric = result.scalar_one_or_none()
    
    if not game_metric:
        return False
    
    # 게임 벡터
    game_vector = np.array(game_metric.to_vector(), dtype=np.float32)
    
    # 2. 기존 DNA (없으면 중립값 5.0)
    if user.taste_dna is not None:
        current_dna = np.array(user.taste_dna, dtype=np.float32)
    else:
        current_dna = np.full(len(ALL_NUMERIC_METRICS), 5.0, dtype=np.float32)
    
    # 3. 학습 신호 결정
    base_weight = FEEDBACK_WEIGHTS.get(feedback_type, 0.1)
    
    if feedback_type == FeedbackType.RATING and rating is not None:
        # 별점: 1~5 → -1.0 ~ +1.0
        signal = (rating - 3.0) / 2.0
        learning_rate = abs(signal) * base_weight * 0.1
        direction = np.sign(signal)
    elif feedback_type == FeedbackType.NOT_INTERESTED:
        # 관심없음: 부정 방향으로 학습
        learning_rate = abs(base_weight) * 0.05
        direction = -1.0
    else:
        # 클릭, 위시리스트, 구매: 긍정 방향
        learning_rate = base_weight * 0.05
        direction = 1.0
    
    # 4. DNA 업데이트 (EMA)
    # new_dna = (1 - α) × current_dna + α × (current_dna + direction × (game_vector - current_dna))
    # 간소화: new_dna = current_dna + α × direction × (game_vector - current_dna)
    
    delta = direction * (game_vector - current_dna)
    new_dna = current_dna + learning_rate * delta
    
    # 범위 클리핑 (0~10)
    new_dna = np.clip(new_dna, 0, 10)
    
    # 5. 저장
    user.taste_dna = new_dna.tolist()
    
    # 확신도 업데이트
    confidence = user.taste_confidence or {}
    for i, metric_name in enumerate(ALL_NUMERIC_METRICS):
        current_conf = confidence.get(metric_name, 0.0)
        # 피드백이 쌓일수록 확신도 증가 (최대 1.0)
        new_conf = min(1.0, current_conf + learning_rate * 0.5)
        confidence[metric_name] = round(new_conf, 4)
    
    user.taste_confidence = confidence
    
    return True


# ============================================================
# 피드백 통계 엔드포인트
# ============================================================

@router.get(
    "/stats/{search_id}",
    summary="검색별 피드백 통계",
)
async def get_search_feedback_stats(
    search_id: str,
    db: AsyncSession = Depends(get_db),
):
    """특정 검색의 피드백 통계"""
    
    # 검색 로그 조회
    result = await db.execute(
        select(SearchLog).where(SearchLog.search_id == search_id)
    )
    search_log = result.scalar_one_or_none()
    
    if not search_log:
        raise HTTPException(status_code=404, detail="검색 기록을 찾을 수 없습니다.")
    
    # 피드백 조회
    feedback_result = await db.execute(
        select(UserFeedback).where(UserFeedback.search_id == search_id)
    )
    feedbacks = feedback_result.scalars().all()
    
    # 통계 집계
    stats = {
        "search_id": search_id,
        "query": search_log.query,
        "result_count": search_log.result_count,
        "feedbacks": {
            "total": len(feedbacks),
            "clicks": len([f for f in feedbacks if f.feedback_type == "click"]),
            "ratings": len([f for f in feedbacks if f.feedback_type == "rating"]),
            "wishlists": len([f for f in feedbacks if f.feedback_type == "wishlist"]),
            "not_interested": len([f for f in feedbacks if f.feedback_type == "not_interested"]),
        },
        "ctr": len([f for f in feedbacks if f.feedback_type == "click"]) / max(search_log.result_count, 1),
    }
    
    return stats
