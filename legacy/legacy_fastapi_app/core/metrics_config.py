# fastapi_app/core/metrics_config.py
"""
Hidden Gem - 지표별 가중치 및 설정
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class MetricConfig:
    """지표 설정"""
    name: str
    description: str
    weight: float = 1.0
    tolerance: float = 1.5
    scale_factor: float = 1.0
    is_sensitive: bool = False  # 민감 지표 (horror, gore 등)


# 카테고리별 기본 가중치
CATEGORY_BASE_WEIGHTS = {
    "vibe": 0.25,
    "demands": 0.20,
    "mechanics": 0.25,
    "social": 0.15,
    "presentation": 0.15,
}

# 지표별 상세 설정
METRIC_CONFIGS: Dict[str, MetricConfig] = {
    # VIBE
    "cozy_factor": MetricConfig("cozy_factor", "아늑함/힐링", weight=1.2, tolerance=1.5),
    "horror_factor": MetricConfig("horror_factor", "공포 강도", weight=1.5, tolerance=0.5, is_sensitive=True),
    "gore_level": MetricConfig("gore_level", "잔인함", weight=1.3, tolerance=0.5, is_sensitive=True),
    "humor_rating": MetricConfig("humor_rating", "유머", weight=0.8, tolerance=2.0),
    "dark_fantasy_vibe": MetricConfig("dark_fantasy_vibe", "다크 판타지", weight=1.0, tolerance=1.5),
    "epic_scale": MetricConfig("epic_scale", "서사적 규모", weight=0.9, tolerance=2.0),
    "melancholy": MetricConfig("melancholy", "우울함/멜랑콜리", weight=1.0, tolerance=1.5),
    
    # DEMANDS
    "reflex_demand": MetricConfig("reflex_demand", "반사신경 요구", weight=1.2, tolerance=1.5),
    "strategic_depth": MetricConfig("strategic_depth", "전략적 깊이", weight=1.1, tolerance=1.5),
    "grind_factor": MetricConfig("grind_factor", "노가다/반복", weight=1.3, tolerance=1.0, is_sensitive=True),
    "time_pressure": MetricConfig("time_pressure", "시간 압박", weight=1.2, tolerance=1.0),
    "learning_curve": MetricConfig("learning_curve", "학습 곡선/난이도", weight=1.1, tolerance=1.5),
    
    # MECHANICS
    "freedom_level": MetricConfig("freedom_level", "자유도", weight=1.0, tolerance=1.5),
    "action_pacing": MetricConfig("action_pacing", "액션 템포", weight=1.1, tolerance=1.5),
    "rng_dependency": MetricConfig("rng_dependency", "운/랜덤 의존도", weight=1.0, tolerance=1.5),
    "growth_reward": MetricConfig("growth_reward", "성장 보상감", weight=1.1, tolerance=1.5),
    "exploration_reward": MetricConfig("exploration_reward", "탐험 보상", weight=1.0, tolerance=1.5),
    "management_complexity": MetricConfig("management_complexity", "관리 복잡도", weight=0.9, tolerance=1.5),
    "stealth_importance": MetricConfig("stealth_importance", "스텔스 중요도", weight=1.0, tolerance=1.5),
    "session_length": MetricConfig("session_length", "세션 길이", weight=0.8, tolerance=2.0),
    "narrative_linearity": MetricConfig("narrative_linearity", "서사 선형성", weight=0.7, tolerance=2.0),
    "puzzle_complexity": MetricConfig("puzzle_complexity", "퍼즐 복잡도", weight=1.0, tolerance=1.5),
    "platforming_precision": MetricConfig("platforming_precision", "플랫포밍 정밀도", weight=1.0, tolerance=1.5),
    
    # SOCIAL
    "coop_synergy": MetricConfig("coop_synergy", "협동 시너지", weight=1.2, tolerance=1.5),
    "competitive_stress": MetricConfig("competitive_stress", "경쟁 스트레스", weight=1.1, tolerance=1.0),
    "npc_interaction": MetricConfig("npc_interaction", "NPC 상호작용", weight=0.8, tolerance=2.0),
    "user_creation": MetricConfig("user_creation", "유저 창작", weight=0.9, tolerance=2.0),
    "multiplayer_scale": MetricConfig("multiplayer_scale", "멀티 규모", weight=1.0, tolerance=1.5),
    
    # PRESENTATION
    "lore_richness": MetricConfig("lore_richness", "로어/세계관", weight=1.0, tolerance=1.5),
    "choice_consequence": MetricConfig("choice_consequence", "선택의 결과", weight=1.0, tolerance=1.5),
    "visual_spectacle": MetricConfig("visual_spectacle", "시각적 화려함", weight=0.8, tolerance=2.0),
    "environmental_storytelling": MetricConfig("environmental_storytelling", "환경 스토리텔링", weight=0.9, tolerance=2.0),
    "soundtrack_impact": MetricConfig("soundtrack_impact", "사운드트랙", weight=0.8, tolerance=2.0),
}


def get_metric_config(metric_name: str) -> MetricConfig:
    """지표 설정 가져오기"""
    return METRIC_CONFIGS.get(
        metric_name,
        MetricConfig(metric_name, metric_name, weight=1.0, tolerance=1.5)
    )


def get_dynamic_margin(confidence: float, is_sensitive: bool = False) -> float:
    """동적 마진 계산"""
    base_margin = 1.0 if is_sensitive else 2.0
    return base_margin * (1.0 - confidence * 0.5)
