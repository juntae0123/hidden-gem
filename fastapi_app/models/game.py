"""
SQLAlchemy ORM 모델 - Django의 games, game_metrics 테이블 매핑

⚠️ 주의: Django가 생성한 컬럼명과 정확히 일치해야 함
- games 테이블: 4,190개 게임
- game_metrics 테이블: 60개 지표 (49 수치 + 9 태그 + 2 평가)
"""
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean,
    Date, DateTime, JSON, ForeignKey, Numeric
)
from sqlalchemy.orm import relationship
from database import Base


class Game(Base):
    """games 테이블"""
    __tablename__ = "games"
    
    # 기본 정보
    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, unique=True, index=True, nullable=False)
    name = Column(String(255), index=True, default='')
    genres = Column(String(500), default='')
    developer = Column(String(255), default='')
    publisher = Column(String(255), default='')
    description = Column(Text, default='')
    short_description = Column(Text, default='')
    header_image = Column(String(500), default='')
    release_date = Column(Date, nullable=True)
    price = Column(Numeric(10, 2), nullable=True)
    
    # 스팀 데이터
    steam_positive_ratio = Column(Float, nullable=True)
    review_count = Column(Integer, default=0)
    is_free = Column(Boolean, default=False)
    is_indie = Column(Boolean, default=True)
    is_early_access = Column(Boolean, default=False)
    
    # AI 생성 콘텐츠
    ai_curation_summary = Column(Text, default='')
    marketing_hook = Column(Text, default='')
    one_line_summary = Column(Text, default='')
    target_personas = Column(JSON, default=list)
    not_for_personas = Column(JSON, default=list)
    similar_games = Column(JSON, default=list)
    unique_selling_points = Column(JSON, default=list)
    
    # 분석 상태
    is_analyzed = Column(Boolean, default=False)
    analysis_method = Column(String(50), default='pending')
    analyzed_at = Column(DateTime, nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    
    # 1:1 관계
    metrics = relationship(
        "GameMetric", 
        back_populates="game", 
        uselist=False,
        lazy="select"
    )


class GameMetric(Base):
    """game_metrics 테이블 - 60개 지표"""
    __tablename__ = "game_metrics"
    
    # PK = FK
    game_id = Column(Integer, ForeignKey("games.id"), primary_key=True)
    
    # ========== VIBE (7) ==========
    cozy_factor = Column(Float, nullable=True)
    horror_factor = Column(Float, nullable=True)
    gore_level = Column(Float, nullable=True)
    humor_rating = Column(Float, nullable=True)
    dark_fantasy_vibe = Column(Float, nullable=True)
    epic_scale = Column(Float, nullable=True)
    melancholy = Column(Float, nullable=True)
    
    # ========== DEMANDS (5) ==========
    reflex_demand = Column(Float, nullable=True)
    strategic_depth = Column(Float, nullable=True)
    grind_factor = Column(Float, nullable=True)
    time_pressure = Column(Float, nullable=True)
    learning_curve = Column(Float, nullable=True)
    
    # ========== MECHANICS (9) ==========
    freedom_level = Column(Float, nullable=True)
    action_pacing = Column(Float, nullable=True)
    rng_dependency = Column(Float, nullable=True)
    growth_reward = Column(Float, nullable=True)
    exploration_reward = Column(Float, nullable=True)
    management_complexity = Column(Float, nullable=True)
    stealth_importance = Column(Float, nullable=True)
    session_length = Column(Float, nullable=True)
    narrative_linearity = Column(Float, nullable=True)
    
    # ========== MECHANICS EXTRA (2) ==========
    puzzle_complexity = Column(Float, nullable=True)
    platforming_precision = Column(Float, nullable=True)
    
    # ========== SOCIAL (5) ==========
    coop_synergy = Column(Float, nullable=True)
    competitive_stress = Column(Float, nullable=True)
    npc_interaction = Column(Float, nullable=True)
    user_creation = Column(Float, nullable=True)
    multiplayer_scale = Column(Float, nullable=True)
    
    # ========== PRESENTATION (5) ==========
    lore_richness = Column(Float, nullable=True)
    choice_consequence = Column(Float, nullable=True)
    visual_spectacle = Column(Float, nullable=True)
    environmental_storytelling = Column(Float, nullable=True)
    soundtrack_impact = Column(Float, nullable=True)
    
    # ========== SYSTEM/UX (7) - 신규 ==========
    build_variety = Column(Float, nullable=True)
    progression_clarity = Column(Float, nullable=True)
    save_flexibility = Column(Float, nullable=True)
    difficulty_accessibility = Column(Float, nullable=True)
    tutorial_quality = Column(Float, nullable=True)
    ui_ux_polish = Column(Float, nullable=True)
    modding_support = Column(Float, nullable=True)
    
    # ========== ART/AUDIO (3) - 신규 ==========
    art_style_uniqueness = Column(Float, nullable=True)
    audio_design = Column(Float, nullable=True)
    animation_quality = Column(Float, nullable=True)
    
    # ========== OTHER (2) - 신규 ==========
    world_reactivity = Column(Float, nullable=True)
    community_dependency = Column(Float, nullable=True)
    
    # ========== NEW (4) - 신규 ==========
    narrative_depth = Column(Float, nullable=True)
    replay_value = Column(Float, nullable=True)
    endgame_content = Column(Float, nullable=True)
    monetization_fairness = Column(Float, nullable=True)
    
    # ========== TAGS (9 Boolean) ==========
    is_turn_based = Column(Boolean, default=False)
    is_real_time = Column(Boolean, default=False)
    is_first_person = Column(Boolean, default=False)
    is_third_person = Column(Boolean, default=False)
    has_permadeath = Column(Boolean, default=False)
    has_base_building = Column(Boolean, default=False)
    has_crafting = Column(Boolean, default=False)
    is_anime_style = Column(Boolean, default=False)
    is_retro_aesthetic = Column(Boolean, default=False)
    
    # ========== EVAL (2) ==========
    gem_potential = Column(Float, nullable=True)
    gem_percentile = Column(Float, nullable=True)  # 백분위 기반 정규화 점수 / Percentile-normalized gem score
    confidence_score = Column(Float, nullable=True)
    
    # ========== REASONING ==========
    analysis_summary = Column(Text, default='')
    genre_classification = Column(String(255), default='')
    core_loop = Column(Text, default='')
    metric_justifications = Column(JSON, default=dict)
    data_limitations = Column(Text, default='')
    
    # ========== 원본 데이터 ==========
    raw_content = Column(JSON, default=dict)
    raw_reasoning = Column(JSON, default=dict)
    
    # ========== EMBEDDING ==========
    embedding = Column(Vector(1536), nullable=True)

    # ========== META ==========
    extraction_version = Column(String(50), default='gpt5.4-batch-v1')
    extracted_at = Column(DateTime)
    updated_at = Column(DateTime)
    
    # 관계
    game = relationship("Game", back_populates="metrics")


# ============================================================
# 49개 수치 지표 (추천 알고리즘 벡터화에 사용)
# ============================================================
NUMERIC_METRIC_FIELDS = [
    # VIBE (7)
    'cozy_factor', 'horror_factor', 'gore_level', 'humor_rating',
    'dark_fantasy_vibe', 'epic_scale', 'melancholy',
    # DEMANDS (5)
    'reflex_demand', 'strategic_depth', 'grind_factor', 
    'time_pressure', 'learning_curve',
    # MECHANICS (9)
    'freedom_level', 'action_pacing', 'rng_dependency', 'growth_reward',
    'exploration_reward', 'management_complexity', 'stealth_importance',
    'session_length', 'narrative_linearity',
    # MECHANICS EXTRA (2)
    'puzzle_complexity', 'platforming_precision',
    # SOCIAL (5)
    'coop_synergy', 'competitive_stress', 'npc_interaction', 
    'user_creation', 'multiplayer_scale',
    # PRESENTATION (5)
    'lore_richness', 'choice_consequence', 'visual_spectacle',
    'environmental_storytelling', 'soundtrack_impact',
    # SYSTEM/UX (7)
    'build_variety', 'progression_clarity', 'save_flexibility',
    'difficulty_accessibility', 'tutorial_quality', 'ui_ux_polish', 
    'modding_support',
    # ART/AUDIO (3)
    'art_style_uniqueness', 'audio_design', 'animation_quality',
    # OTHER (2)
    'world_reactivity', 'community_dependency',
    # NEW (4)
    'narrative_depth', 'replay_value', 'endgame_content', 
    'monetization_fairness',
]

# 9개 Boolean 태그
BOOLEAN_TAG_FIELDS = [
    'is_turn_based', 'is_real_time', 'is_first_person', 'is_third_person',
    'has_permadeath', 'has_base_building', 'has_crafting',
    'is_anime_style', 'is_retro_aesthetic',
]

# 카테고리 분류 (UI 표시용)
METRIC_CATEGORIES = {
    'vibe': ['cozy_factor', 'horror_factor', 'gore_level', 'humor_rating',
             'dark_fantasy_vibe', 'epic_scale', 'melancholy'],
    'demands': ['reflex_demand', 'strategic_depth', 'grind_factor',
                'time_pressure', 'learning_curve'],
    'mechanics': ['freedom_level', 'action_pacing', 'rng_dependency', 
                  'growth_reward', 'exploration_reward', 'management_complexity', 
                  'stealth_importance', 'session_length', 'narrative_linearity'],
    'mechanics_extra': ['puzzle_complexity', 'platforming_precision'],
    'social': ['coop_synergy', 'competitive_stress', 'npc_interaction',
               'user_creation', 'multiplayer_scale'],
    'presentation': ['lore_richness', 'choice_consequence', 'visual_spectacle',
                     'environmental_storytelling', 'soundtrack_impact'],
    'system_ux': ['build_variety', 'progression_clarity', 'save_flexibility',
                  'difficulty_accessibility', 'tutorial_quality', 'ui_ux_polish',
                  'modding_support'],
    'art_audio': ['art_style_uniqueness', 'audio_design', 'animation_quality'],
    'other': ['world_reactivity', 'community_dependency'],
    'new': ['narrative_depth', 'replay_value', 'endgame_content', 
            'monetization_fairness'],
}
