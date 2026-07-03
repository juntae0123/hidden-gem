# fastapi_app/scripts/test_score_v6.py
"""
v6 점수 시스템 테스트 — 변별력 + 차별화 검증.
"""
import sys
sys.path.insert(0, '/app')

from services.score_v6 import calculate_score_v6, GENRE_CORE_METRICS


def test_witcher_vs_others():
    """다크판타지 RPG 검색 시나리오."""
    print("=" * 60)
    print("시나리오: '다크판타지 명작 RPG' 검색")
    print("=" * 60)

    # 검색 의도 (다크판타지 RPG)
    target = {
        'narrative_depth': 9, 'growth_reward': 8,
        'choice_consequence': 8, 'lore_richness': 9,
        'dark_fantasy_vibe': 9,
    }

    games = {
        'Witcher 3': {
            'metrics': {
                'narrative_depth': 9, 'growth_reward': 8,
                'choice_consequence': 8, 'lore_richness': 9,
                'exploration_reward': 9, 'dark_fantasy_vibe': 9,
                'world_reactivity': 8, 'epic_scale': 9,
            },
            'reviews': 500000, 'positive': 0.97, 'gem': 100,
        },
        'Pentiment (숨은명작)': {
            'metrics': {
                'narrative_depth': 10, 'choice_consequence': 9,
                'lore_richness': 9, 'environmental_storytelling': 9,
                'art_style_uniqueness': 9, 'dark_fantasy_vibe': 6,
            },
            'reviews': 8000, 'positive': 0.95, 'gem': 95,
        },
        'Hades': {
            'metrics': {
                'narrative_depth': 8, 'replay_value': 10,
                'action_pacing': 9, 'dark_fantasy_vibe': 5,
                'art_style_uniqueness': 9,
            },
            'reviews': 300000, 'positive': 0.98, 'gem': 90,
        },
        'Stardew (안맞음)': {
            'metrics': {
                'cozy_factor': 10, 'management_complexity': 7,
                'narrative_depth': 6, 'dark_fantasy_vibe': 0,
            },
            'reviews': 500000, 'positive': 0.98, 'gem': 95,
        },
    }

    results = []
    for name, g in games.items():
        score = calculate_score_v6(
            game_metrics=g['metrics'],
            target_metrics=target,
            genre='RPG',
            review_count=g['reviews'],
            positive_ratio=g['positive'],
            gem_percentile=g['gem'],
        )
        results.append((name, score))

    # 점수순 정렬
    results.sort(key=lambda x: -x[1]['final_score'])

    for name, score in results:
        print(f"\n🎮 {name}")
        print(f"   최종: {score['final_score']}점")
        print(f"   ├ Core: {score['breakdown']['core_score']}")
        print(f"   ├ X-Factor: {score['breakdown']['xfactor_score']}")
        print(f"   └ Gem: {score['breakdown']['gem_score']}")
        print(f"   💎 정체성: {score['identity']}")
        if score['is_hidden_gem']:
            print(f"   ⭐ 숨은 명작!")

    scores = [s['final_score'] for _, s in results]
    print(f"\n{'=' * 60}")
    print(f"점수 분포: {scores}")
    print(f"변별력 (최대-최소): {max(scores) - min(scores):.1f}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    test_witcher_vs_others()
