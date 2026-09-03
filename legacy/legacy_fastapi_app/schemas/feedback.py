# fastapi_app/schemas/feedback.py
"""
Hidden Gem - 피드백 API 스키마

유저 행동 추적:
- 클릭
- 별점
- 위시리스트 추가
- 구매
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class FeedbackType(str, Enum):
    """피드백 유형"""
    CLICK = "click"              # 게임 클릭 (상세보기)
    RATING = "rating"            # 별점 (1~5)
    WISHLIST = "wishlist"        # 위시리스트 추가
    NOT_INTERESTED = "not_interested"  # 관심없음
    PURCHASE = "purchase"        # 구매


class FeedbackRequest(BaseModel):
    """피드백 요청"""
    
    # 필수
    search_id: str = Field(..., description="검색 ID (Traceability)")
    game_app_id: int = Field(..., description="게임 Steam App ID")
    feedback_type: FeedbackType = Field(..., description="피드백 유형")
    
    # 선택적
    rating: Optional[float] = Field(None, ge=1, le=5, description="별점 (1~5)")
    result_position: Optional[int] = Field(None, ge=0, description="검색 결과 순위")
    
    # 유저 정보 (로그인 시)
    user_id: Optional[int] = Field(None, description="유저 ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "search_id": "550e8400-e29b-41d4-a716-446655440000",
                "game_app_id": 1145360,
                "feedback_type": "click",
                "result_position": 0
            }
        }


class FeedbackResponse(BaseModel):
    """피드백 응답"""
    success: bool = Field(True)
    feedback_id: int = Field(..., description="생성된 피드백 ID")
    message: str = Field("피드백이 기록되었습니다.")
    
    # 취향 DNA 업데이트 여부
    taste_dna_updated: bool = Field(False, description="취향 DNA 업데이트 여부")


class BatchFeedbackRequest(BaseModel):
    """배치 피드백 요청 (여러 피드백 한번에)"""
    feedbacks: List[FeedbackRequest] = Field(..., min_length=1, max_length=100)


class UserTasteProfile(BaseModel):
    """유저 취향 프로필 (조회용)"""
    user_id: int
    
    # 취향 DNA 요약
    top_preferred_metrics: List[str] = Field(default_factory=list, description="선호 지표 Top 5")
    top_avoided_metrics: List[str] = Field(default_factory=list, description="기피 지표 Top 5")
    
    # 통계
    total_searches: int = 0
    total_clicks: int = 0
    total_ratings: int = 0
    average_rating: Optional[float] = None
    
    # 마지막 활동
    last_active_at: Optional[datetime] = None
