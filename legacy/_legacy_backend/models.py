"""
Hidden Gem - SQLAlchemy Models
"""

from sqlalchemy import Column, Integer, String, Float, Text
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from backend.database import Base  # ← 상대 임포트로 변경

class Game(Base):
    __tablename__ = "games"
    
    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    genres = Column(String)
    developer = Column(String)
    description = Column(Text)
    
    # 14개 AI 분석 지표 (기존)
    mania_score = Column(Float, default=0.0)
    story_depth = Column(Float, default=0.0)
    originality = Column(Float, default=0.0)
    difficulty = Column(Float, default=0.0)
    art_style = Column(Float, default=0.0)
    replay_value = Column(Float, default=0.0)
    indie_spirit = Column(Float, default=0.0)
    character_appeal = Column(Float, default=0.0)
    user_friendliness = Column(Float, default=0.0)
    addictiveness = Column(Float, default=0.0)
    emotional_impact = Column(Float, default=0.0)
    atmosphere_intensity = Column(Float, default=0.0)
    soundtrack_prominence = Column(Float, default=0.0)
    gem_potential = Column(Float, default=0.0)
    
    # 52개 지표 (v5.0 신규) - JSONB
    metrics = Column(JSONB, default={})
    tags = Column(JSONB, default={})
    content = Column(JSONB, default={})
    reasoning = Column(JSONB, default={})
    extraction_meta = Column(JSONB, default={})
    
    # OpenAI 1536차원 임베딩
    embedding = Column(Vector(1536))
