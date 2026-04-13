# fastapi_app/core/constants.py
"""
Hidden Gem - 52개 지표 상수 정의
"""

# 수치 지표 (33개)
ALL_NUMERIC_METRICS = [
    # VIBE (7)
    "cozy_factor",
    "horror_factor",
    "gore_level",
    "humor_rating",
    "dark_fantasy_vibe",
    "epic_scale",
    "melancholy",
    # DEMANDS (5)
    "reflex_demand",
    "strategic_depth",
    "grind_factor",
    "time_pressure",
    "learning_curve",
    # MECHANICS (11)
    "freedom_level",
    "action_pacing",
    "rng_dependency",
    "growth_reward",
    "exploration_reward",
    "management_complexity",
    "stealth_importance",
    "session_length",
    "narrative_linearity",
    "puzzle_complexity",
    "platforming_precision",
    # SOCIAL (5)
    "coop_synergy",
    "competitive_stress",
    "npc_interaction",
    "user_creation",
    "multiplayer_scale",
    # PRESENTATION (5)
    "lore_richness",
    "choice_consequence",
    "visual_spectacle",
    "environmental_storytelling",
    "soundtrack_impact",
]

# 태그 지표 (9개)
TAG_METRICS = [
    "is_turn_based",
    "is_real_time",
    "is_first_person",
    "is_third_person",
    "has_permadeath",
    "has_base_building",
    "has_crafting",
    "is_anime_style",
    "is_retro_aesthetic",
]

# 카테고리별 지표 분류
CATEGORY_METRICS = {
    "vibe": [
        "cozy_factor", "horror_factor", "gore_level", "humor_rating",
        "dark_fantasy_vibe", "epic_scale", "melancholy"
    ],
    "demands": [
        "reflex_demand", "strategic_depth", "grind_factor",
        "time_pressure", "learning_curve"
    ],
    "mechanics": [
        "freedom_level", "action_pacing", "rng_dependency", "growth_reward",
        "exploration_reward", "management_complexity", "stealth_importance",
        "session_length", "narrative_linearity", "puzzle_complexity",
        "platforming_precision"
    ],
    "social": [
        "coop_synergy", "competitive_stress", "npc_interaction",
        "user_creation", "multiplayer_scale"
    ],
    "presentation": [
        "lore_richness", "choice_consequence", "visual_spectacle",
        "environmental_storytelling", "soundtrack_impact"
    ],
}
