# fastapi_app/models/game.py
"""
Hidden Gem - 게임 모델
Two-Tower 검색을 위한 pure_embedding 설계
Django와 동일한 스키마 유지

⚠️ 중요: DB 스키마는 Django migrate가 관리
   이 파일은 SQLAlchemy ORM 매핑 전용
"""

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean,
    DateTime, ForeignKey, Index, BigInteger
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from datetime import datetime

from database import Base
from core.constants import EMBEDDING_DIMENSION, ALL_NUMERIC_METRICS


class Game(Base):
    """게임 기본 정보 - Django Game 모델과 동기화"""
    
    __tablename__ = "games"
    
    id = Column(BigInteger, primary_key=True, index=True)
    app_id = Column(Integer, unique=True, nullable=False, index=True)
    
    # 기본 정보
    name = Column(String(255), nullable=False, default='', index=True)
    genres = Column(String(500), default="")
    developer = Column(String(255), default="")
    publisher = Column(String(255), default="")
    description = Column(Text, default="")
    short_description = Column(Text, default="")
    header_image = Column(String(500), nullable=True)
    release_date = Column(DateTime, nullable=True)
    price = Column(Float, nullable=True)
    
    # 스팀 데이터
    steam_positive_ratio = Column(Float, nullable=True)
    review_count = Column(Integer, default=0)
    is_free = Column(Boolean, default=False)
    is_indie = Column(Boolean, default=True)
    is_early_access = Column(Boolean, default=False)
    
    # AI 생성 콘텐츠
    ai_curation_summary = Column(Text, nullable=True)
    marketing_hook = Column(Text, nullable=True)
    one_line_summary = Column(Text, nullable=True)
    target_personas = Column(JSONB, default=list)
    not_for_personas = Column(JSONB, default=list)
    similar_games = Column(JSONB, default=list)
    unique_selling_points = Column(JSONB, default=list)
    
    # 분석 상태
    is_analyzed = Column(Boolean, default=False, index=True)
    analysis_method = Column(String(50), default="pending")
    analyzed_at = Column(DateTime, nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계 - Django와 동일하게 PK 기반 OneToOne
    metrics = relationship(
        "GameMetric", 
        back_populates="game", 
        uselist=False, 
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<Game {self.app_id}: {self.name}>"


class GameMetric(Base):
    """
    게임 52개 지표 + 벡터 임베딩
    Django GameMetric과 동기화 - game_id가 PK
    
    ⚠️ 경고: pure_embedding 차원(EMBEDDING_DIMENSION)은 
       core/constants.py의 ALL_NUMERIC_METRICS 개수와 반드시 일치해야 함!
       현재: 33개 지표 → 33차원 벡터
       
       지표 추가/삭제 시:
       1. core/constants.py의 ALL_NUMERIC_METRICS 수정
       2. Django models.py에 필드 추가
       3. Django makemigrations + migrate 실행
       4. 기존 데이터의 pure_embedding 재계산 필요
    """
    
    __tablename__ = "game_metrics"
    
    # Django와 동일: game_id가 PK (OneToOne)
    game_id = Column(
        BigInteger, 
        ForeignKey("games.id", ondelete="CASCADE"), 
        primary_key=True
    )
    
    # ========== VIBE (7개) ==========
    cozy_factor = Column(Float, nullable=True)
    horror_factor = Column(Float, nullable=True)
    gore_level = Column(Float, nullable=True)
    humor_rating = Column(Float, nullable=True)
    dark_fantasy_vibe = Column(Float, nullable=True)
    epic_scale = Column(Float, nullable=True)
    melancholy = Column(Float, nullable=True)
    
    # ========== DEMANDS (5개) ==========
    reflex_demand = Column(Float, nullable=True)
    strategic_depth = Column(Float, nullable=True)
    grind_factor = Column(Float, nullable=True)
    time_pressure = Column(Float, nullable=True)
    learning_curve = Column(Float, nullable=True)
    
    # ========== MECHANICS (11개) ==========
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
    
    # ========== SOCIAL (5개) ==========
    coop_synergy = Column(Float, nullable=True)
    competitive_stress = Column(Float, nullable=True)
    npc_interaction = Column(Float, nullable=True)
    user_creation = Column(Float, nullable=True)
    multiplayer_scale = Column(Float, nullable=True)
    
    # ========== PRESENTATION (5개) ==========
    lore_richness = Column(Float, nullable=True)
    choice_consequence = Column(Float, nullable=True)
    visual_spectacle = Column(Float, nullable=True)
    environmental_storytelling = Column(Float, nullable=True)
    soundtrack_impact = Column(Float, nullable=True)
    
    # ========== TAGS (9개 Boolean) ==========
    is_turn_based = Column(Boolean, default=False)
    is_real_time = Column(Boolean, default=False)
    is_first_person = Column(Boolean, default=False)
    is_third_person = Column(Boolean, default=False)
    has_permadeath = Column(Boolean, default=False)
    has_base_building = Column(Boolean, default=False)
    has_crafting = Column(Boolean, default=False)
    is_anime_style = Column(Boolean, default=False)
    is_retro_aesthetic = Column(Boolean, default=False)
    
    # ========== AI 평가 ==========
    gem_potential = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    
    # ========== REASONING (Django와 동기화) ==========
    analysis_summary = Column(Text, nullable=True)
    genre_classification = Column(String(255), nullable=True)
    core_loop = Column(Text, nullable=True)
    metric_justifications = Column(JSONB, default=dict)
    data_limitations = Column(Text, nullable=True)
    
    # ========== 벡터 임베딩 ==========
    # ⚠️ 차원은 EMBEDDING_DIMENSION (core/constants.py)에서 관리
    # 현재: 33차원 (ALL_NUMERIC_METRICS 개수)
    pure_embedding = Column(Vector(EMBEDDING_DIMENSION), nullable=True)
    
    # ========== 메타 ==========
    extraction_version = Column(String(50), default="gpt5.4-batch-v1")
    raw_content = Column(JSONB, nullable=True)
    raw_reasoning = Column(JSONB, nullable=True)
    extracted_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
        """
        지표를 벡터로 변환
        
        ⚠️ 순서가 ALL_NUMERIC_METRICS와 반드시 일치해야 함!
        """
        # ALL_NUMERIC_METRICS 순서대로 값 추출
        vector = []
        for metric_name in ALL_NUMERIC_METRICS:
            value = getattr(self, metric_name, None)
            vector.append(value if value is not None else 5.0)
        
        assert len(vector) == EMBEDDING_DIMENSION, \
            f"Vector dimension mismatch! Expected {EMBEDDING_DIMENSION}, got {len(vector)}"
        
        return vector
