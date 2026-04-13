# fastapi_app/models/game.py
"""
Hidden Gem - 게임 모델
Two-Tower 검색을 위한 pure_embedding 설계
"""

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean,
    DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from datetime import datetime

from database import Base


class Game(Base):
    """게임 기본 정보"""
    
    __tablename__ = "games"
    
    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, unique=True, nullable=False, index=True)
    
    # 기본 정보
    name = Column(String(500), nullable=False, index=True)
    genres = Column(String(1000), default="")
    developer = Column(String(500), default="")
    publisher = Column(String(500), default="")
    description = Column(Text, default="")
    short_description = Column(Text, default="")
    header_image = Column(String(500), nullable=True)
    release_date = Column(DateTime, nullable=True)
    
    # 스팀 데이터
    steam_positive_ratio = Column(Float, nullable=True)
    review_count = Column(Integer, default=0)
    price = Column(Float, nullable=True)
    is_free = Column(Boolean, default=False)
    
    # 분류
    is_indie = Column(Boolean, default=True)
    is_early_access = Column(Boolean, default=False)
    
    # 분석 상태
    is_analyzed = Column(Boolean, default=False, index=True)
    analysis_method = Column(String(50), default="pending")
    analyzed_at = Column(DateTime, nullable=True)
    
    # AI 생성 콘텐츠
    ai_curation_summary = Column(Text, nullable=True)
    marketing_hook = Column(Text, nullable=True)
    one_line_summary = Column(Text, nullable=True)
    target_personas = Column(JSONB, default=list)
    not_for_personas = Column(JSONB, default=list)
    similar_games = Column(JSONB, default=list)
    unique_selling_points = Column(JSONB, default=list)
    
    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계
    metrics = relationship("GameMetric", back_populates="game", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Game {self.app_id}: {self.name}>"


class GameMetric(Base):
    """게임 52개 지표 + 벡터 임베딩"""
    
    __tablename__ = "game_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # VIBE (7개)
    cozy_factor = Column(Float, nullable=True)
    horror_factor = Column(Float, nullable=True)
    gore_level = Column(Float, nullable=True)
    humor_rating = Column(Float, nullable=True)
    dark_fantasy_vibe = Column(Float, nullable=True)
    epic_scale = Column(Float, nullable=True)
    melancholy = Column(Float, nullable=True)
    
    # DEMANDS (5개)
    reflex_demand = Column(Float, nullable=True)
    strategic_depth = Column(Float, nullable=True)
    grind_factor = Column(Float, nullable=True)
    time_pressure = Column(Float, nullable=True)
    learning_curve = Column(Float, nullable=True)
    
    # MECHANICS (11개)
    freedom_level = Column(Float, nullable=True)
    action_pacing = Column(Float, nullable=True)
    rng_dependency = Column(Float, nullable=True)
    growth_reward = Column(Float, nullable=True)
    exploration_reward = Column(Float, nullable=True)
    management_complexity = Column(Float, nullable=True)
    stealth_importance = Column(Float, nullable=True)
    session_length = Column(Float, nullable=True)
    narrative_linearity = Column(Float, nullable=True)
    puzzle_complexity = Column(Float, nullable=True)
    platforming_precision = Column(Float, nullable=True)
    
    # SOCIAL (5개)
    coop_synergy = Column(Float, nullable=True)
    competitive_stress = Column(Float, nullable=True)
    npc_interaction = Column(Float, nullable=True)
    user_creation = Column(Float, nullable=True)
    multiplayer_scale = Column(Float, nullable=True)
    
    # PRESENTATION (5개)
    lore_richness = Column(Float, nullable=True)
    choice_consequence = Column(Float, nullable=True)
    visual_spectacle = Column(Float, nullable=True)
    environmental_storytelling = Column(Float, nullable=True)
    soundtrack_impact = Column(Float, nullable=True)
    
    # TAGS (9개 Boolean)
    is_turn_based = Column(Boolean, default=False)
    is_real_time = Column(Boolean, default=False)
    is_first_person = Column(Boolean, default=False)
    is_third_person = Column(Boolean, default=False)
    has_permadeath = Column(Boolean, default=False)
    has_base_building = Column(Boolean, default=False)
    has_crafting = Column(Boolean, default=False)
    is_anime_style = Column(Boolean, default=False)
    is_retro_aesthetic = Column(Boolean, default=False)
    
    # AI 평가
    gem_potential = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    
    # 벡터 임베딩 (33개 수치 지표)
    pure_embedding = Column(Vector(33), nullable=True)
    
    # 메타
    extraction_version = Column(String(50), default="gpt5.4-batch-v1")
    raw_content = Column(JSONB, nullable=True)
    raw_reasoning = Column(JSONB, nullable=True)
    
    # 관계
    game = relationship("Game", back_populates="metrics")
    
    # HNSW 인덱스
    __table_args__ = (
        Index(
            'ix_game_metrics_pure_embedding_hnsw',
            pure_embedding,
            postgresql_using='hnsw',
            postgresql_with={'m': 16, 'ef_construction': 64},
            postgresql_ops={'pure_embedding': 'vector_l2_ops'}
        ),
    )
    
    def to_vector(self) -> list:
        """지표를 벡터로 변환"""
        return [
            self.cozy_factor or 5.0,
            self.horror_factor or 5.0,
            self.gore_level or 5.0,
            self.humor_rating or 5.0,
            self.dark_fantasy_vibe or 5.0,
            self.epic_scale or 5.0,
            self.melancholy or 5.0,
            self.reflex_demand or 5.0,
            self.strategic_depth or 5.0,
            self.grind_factor or 5.0,
            self.time_pressure or 5.0,
            self.learning_curve or 5.0,
            self.freedom_level or 5.0,
            self.action_pacing or 5.0,
            self.rng_dependency or 5.0,
            self.growth_reward or 5.0,
            self.exploration_reward or 5.0,
            self.management_complexity or 5.0,
            self.stealth_importance or 5.0,
            self.session_length or 5.0,
            self.narrative_linearity or 5.0,
            self.puzzle_complexity or 5.0,
            self.platforming_precision or 5.0,
            self.coop_synergy or 5.0,
            self.competitive_stress or 5.0,
            self.npc_interaction or 5.0,
            self.user_creation or 5.0,
            self.multiplayer_scale or 5.0,
            self.lore_richness or 5.0,
            self.choice_consequence or 5.0,
            self.visual_spectacle or 5.0,
            self.environmental_storytelling or 5.0,
            self.soundtrack_impact or 5.0,
        ]
