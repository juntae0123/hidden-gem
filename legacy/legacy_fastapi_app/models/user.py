# fastapi_app/models/user.py
"""
Hidden Gem - 유저 모델
취향 DNA + Personal Bias 시스템
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, ForeignKey, Text, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from datetime import datetime
import numpy as np

from database import Base


class User(Base):
    """유저 모델"""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 기본 정보
    external_id = Column(String(100), unique=True, nullable=True, index=True)
    steam_id = Column(String(50), unique=True, nullable=True, index=True)
    nickname = Column(String(100), nullable=True)
    email = Column(String(255), unique=True, nullable=True)
    
    # 취향 DNA (33차원)
    taste_dna = Column(Vector(33), nullable=True)
    taste_confidence = Column(JSONB, default=dict)
    
    # 개인화 설정
    explicit_preferences = Column(JSONB, default=dict)
    category_weights = Column(JSONB, nullable=True)
    hard_avoid = Column(JSONB, default=list)
    
    # 통계
    total_searches = Column(Integer, default=0)
    total_clicks = Column(Integer, default=0)
    total_ratings = Column(Integer, default=0)
    
    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_active_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    feedbacks = relationship("UserFeedback", back_populates="user", cascade="all, delete-orphan")
    search_logs = relationship("SearchLog", back_populates="user", cascade="all, delete-orphan")
    
    def get_personal_bias(self) -> dict:
        """Personal Bias 계산"""
        return {
            "category_boosts": self.category_weights or {},
            "metric_adjustments": {},
            "discovery_preference": 0.5,
        }


class SearchLog(Base):
    """검색 로그"""
    
    __tablename__ = "search_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(String(36), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # 검색 정보
    query = Column(Text, nullable=False)
    search_type = Column(String(50), nullable=False)
    parsed_metrics = Column(JSONB, nullable=True)
    interpretation = Column(Text, nullable=True)
    
    # 결과
    result_count = Column(Integer, default=0)
    top_results = Column(JSONB, nullable=True)
    
    # 성능
    processing_time_ms = Column(Float, nullable=True)
    llm_model_used = Column(String(50), nullable=True)
    cache_hit = Column(Boolean, default=False)
    
    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # 관계
    user = relationship("User", back_populates="search_logs")
    feedbacks = relationship("UserFeedback", back_populates="search_log")


class UserFeedback(Base):
    """유저 피드백"""
    
    __tablename__ = "user_feedbacks"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    search_id = Column(String(36), ForeignKey("search_logs.search_id", ondelete="SET NULL"), nullable=True, index=True)
    game_app_id = Column(Integer, nullable=False, index=True)
    
    # 피드백
    feedback_type = Column(String(20), nullable=False)
    rating = Column(Float, nullable=True)
    result_position = Column(Integer, nullable=True)
    match_score = Column(Float, nullable=True)
    
    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # 관계
    user = relationship("User", back_populates="feedbacks")
    search_log = relationship("SearchLog", back_populates="feedbacks")
    
    __table_args__ = (
        Index('ix_feedback_user_game', user_id, game_app_id),
    )
