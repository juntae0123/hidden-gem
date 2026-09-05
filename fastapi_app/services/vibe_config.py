# fastapi_app/services/vibe_config.py
"""
Vibe Cluster configuration — 12 Macro Vibes (확정).
Korean: Vibe Cluster 12개 Macro 정의.

분포 검증 완료 (2026-06-17):
    12/12 OK, 비율 7.9:1 (PRD <10:1).
    발견 27% / 미커버 73% (칩=정확도 우선, 평범한 게임은 검색).

각 Vibe = preferences 프리셋 → v6 by-preference 추천 재사용.
"""

MACRO_VIBES: dict[str, dict] = {
    'cozy_escape': {
        'label': '아늑한 휴식', 'emoji': '🌿',
        'description': '스트레스 없이 편하게 즐기는 힐링 게임',
        'preferences': {'cozy_factor': 9, 'horror_factor': 0},
    },
    'dark_narrative': {
        'label': '어두운 서사', 'emoji': '🌑',
        'description': '선택의 무게가 있는 다크 판타지',
        'preferences': {'dark_fantasy_vibe': 9, 'choice_consequence': 9, 'lore_richness': 8},
    },
    'brain_strategy': {
        'label': '두뇌 전략', 'emoji': '🧠',
        'description': '깊이 생각하고 계획하는 전략 게임',
        'preferences': {'strategic_depth': 9, 'management_complexity': 8},
    },
    'action_thrill': {
        'label': '손맛 액션', 'emoji': '⚡',
        'description': '긴박하고 역동적인 액션',
        'preferences': {'action_pacing': 9, 'reflex_demand': 8, 'time_pressure': 7},
    },
    'exploration_wonder': {
        'label': '탐험 발견', 'emoji': '🗺️',
        'description': '자유롭게 세계를 탐험하는 재미',
        'preferences': {'exploration_reward': 9, 'freedom_level': 8},
    },
    'horror_tension': {
        'label': '공포 긴장', 'emoji': '👻',
        'description': '무섭고 긴장감 넘치는 분위기',
        'preferences': {'horror_factor': 9, 'environmental_storytelling': 7},
    },
    'emotional_journey': {
        'label': '감성 여운', 'emoji': '💧',
        'description': '음악과 감성이 가슴에 남는 게임',
        'preferences': {'melancholy': 9, 'soundtrack_impact': 9},
    },
    'challenge_master': {
        'label': '도전 극복', 'emoji': '🔥',
        'description': '깊이 파고드는 어려운 게임',
        'preferences': {'learning_curve': 9, 'strategic_depth': 8, 'grind_factor': 7},
    },
    'creative_sandbox': {
        'label': '창작 자유', 'emoji': '🎨',
        'description': '직접 만들고 꾸미는 자유',
        'preferences': {'user_creation': 9, 'freedom_level': 9},
    },
    'roguelike_loop': {
        'label': '로그라이크', 'emoji': '🎲',
        'description': '죽고 다시 도전하는 반복의 재미',
        'preferences': {'rng_dependency': 8, 'replay_value': 9, 'build_variety': 8},
    },
    'artistic_vision': {
        'label': '예술적', 'emoji': '✨',
        'description': '독창적인 아트와 음악',
        'preferences': {'art_style_uniqueness': 9, 'soundtrack_impact': 8},
    },
    'coop_fun': {
        'label': '함께 즐기기', 'emoji': '🤝',
        'description': '친구와 함께하는 협동 재미',
        'preferences': {'coop_synergy': 9, 'multiplayer_scale': 7},
    },
}


# ==================== Secondary 목표값 (R-1', 초안) ====================
# Vibe 는 지표 2~3개라 v7 에서 동점이 수백 개 생긴다. Vibe *정의*가 말하는 부수 축을 목표값과 함께 적어
# 가중 RMSE 에 절반 가중치(×0.5)로 넣는다. 사용자가 말한 게 아니라 Vibe 정의가 말한 값이므로 D-26(임의 목표 5.0)과 다르다.
#
# ⚠ 아래 숫자는 **초안**이다. settings.VIBE_SECONDARY_ENABLED (기본 False) 가 켜질 때만 쓰인다.
#   켜기 전에 Vibe 당 대표 게임 20개 + 명백한 반례 20개로 순위가 맞는지 확인할 것 (검토 A-4).
#   확정되지 않은 목표값을 점수에 넣는 것은 D-26 과 같은 부류의 위험이다.
VIBE_SECONDARY_DRAFT: dict[str, dict[str, float]] = {
    'cozy_escape':       {'time_pressure': 1, 'gore_level': 0, 'competitive_stress': 0, 'grind_factor': 2, 'difficulty_accessibility': 8},
    'dark_narrative':    {'narrative_depth': 8, 'melancholy': 7, 'humor_rating': 2, 'cozy_factor': 1, 'epic_scale': 7},
    'brain_strategy':    {'reflex_demand': 2, 'learning_curve': 7, 'rng_dependency': 3, 'time_pressure': 3, 'replay_value': 8},
    'action_thrill':     {'cozy_factor': 1, 'visual_spectacle': 7, 'session_length': 4, 'strategic_depth': 4},
    'exploration_wonder': {'environmental_storytelling': 8, 'world_reactivity': 7, 'time_pressure': 2, 'narrative_linearity': 2},
    'horror_tension':    {'cozy_factor': 0, 'humor_rating': 1, 'melancholy': 6, 'time_pressure': 6, 'gore_level': 5},
    'emotional_journey': {'narrative_depth': 8, 'reflex_demand': 2, 'competitive_stress': 0, 'humor_rating': 3},
    'challenge_master':  {'difficulty_accessibility': 2, 'reflex_demand': 6, 'replay_value': 8, 'cozy_factor': 1},
    'creative_sandbox':  {'management_complexity': 6, 'narrative_linearity': 1, 'time_pressure': 1, 'replay_value': 8},
    'roguelike_loop':    {'session_length': 3, 'learning_curve': 7, 'growth_reward': 8, 'narrative_linearity': 1},
    'artistic_vision':   {'audio_design': 8, 'visual_spectacle': 6, 'environmental_storytelling': 6},
    'coop_fun':          {'competitive_stress': 3, 'difficulty_accessibility': 7, 'session_length': 4},
}


def get_vibe_secondary(vibe_key: str) -> dict | None:
    """Vibe 의 secondary 목표값 (초안). 플래그 확인은 호출자가 한다."""
    return VIBE_SECONDARY_DRAFT.get(vibe_key)


def get_vibe_list() -> list[dict]:
    """API용 vibe 목록 (preferences 제외). / Vibe list for API."""
    return [
        {'key': k, 'label': v['label'], 'emoji': v['emoji'],
         'description': v['description']}
        for k, v in MACRO_VIBES.items()
    ]


def get_vibe_preferences(vibe_key: str) -> dict | None:
    """vibe 키 → preferences. / Key to preferences."""
    vibe = MACRO_VIBES.get(vibe_key)
    return vibe['preferences'] if vibe else None
