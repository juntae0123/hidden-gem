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
