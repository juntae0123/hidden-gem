# fastapi_app/core/constants.py
"""
Hidden Gem - 52개 지표 상수 정의

⚠️ 중요: ALL_NUMERIC_METRICS 수정 시 EMBEDDING_DIMENSION도 자동 갱신됨
   하지만 DB 스키마(pgvector 차원)는 Django migrate로 별도 변경 필요!
"""

# ============================================================
# 수치 지표 (33개) - 순서 중요! 벡터 인덱스와 매핑됨
# ============================================================
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

# ============================================================
# 임베딩 차원 (자동 계산)
# ============================================================
EMBEDDING_DIMENSION = len(ALL_NUMERIC_METRICS)  # 현재: 33

# Sanity check
assert EMBEDDING_DIMENSION == 33, \
    f"EMBEDDING_DIMENSION changed! Update pgvector schema. Expected 33, got {EMBEDDING_DIMENSION}"


# ============================================================
# 태그 지표 (9개)
# ============================================================
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


# ============================================================
# 카테고리별 지표 분류
# ============================================================
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


# ============================================================
# 검증: 카테고리 지표 합계가 ALL_NUMERIC_METRICS와 일치하는지
# ============================================================
_all_category_metrics = []
for metrics in CATEGORY_METRICS.values():
    _all_category_metrics.extend(metrics)

assert set(_all_category_metrics) == set(ALL_NUMERIC_METRICS), \
    "CATEGORY_METRICS does not match ALL_NUMERIC_METRICS!"

assert len(_all_category_metrics) == len(ALL_NUMERIC_METRICS), \
    "Duplicate metrics in CATEGORY_METRICS!"
