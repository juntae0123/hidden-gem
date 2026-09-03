"""
Vibe distribution check — Macro 12개가 4190개를 고르게 덮나.
각 vibe 70점+ 게임 수 / 커버리지 / 겹침 측정.
"""
import sys
import io
import asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '/app')

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database import AsyncSessionLocal
from models.game import Game, NUMERIC_METRIC_FIELDS
from services.score_v6 import calculate_score_v6

VIBES = {
    'cozy_escape': {'cozy_factor': 9, 'horror_factor': 0},
    'dark_narrative': {'dark_fantasy_vibe': 9, 'narrative_depth': 9},
    'brain_strategy': {'strategic_depth': 9, 'management_complexity': 8},
    'action_thrill': {'action_pacing': 9, 'reflex_demand': 8},
    'exploration_wonder': {'exploration_reward': 9, 'freedom_level': 8},
    'horror_tension': {'horror_factor': 9},
    'emotional_journey': {'melancholy': 9, 'narrative_depth': 8},
    'challenge_master': {'learning_curve': 9, 'reflex_demand': 8},
    'creative_sandbox': {'user_creation': 9, 'freedom_level': 9},
    'roguelike_loop': {'rng_dependency': 8, 'replay_value': 9},
    'artistic_vision': {'art_style_uniqueness': 9, 'soundtrack_impact': 8},
    'coop_fun': {'coop_synergy': 9},
}


async def main():
    """Measure vibe coverage and overlap across all analyzed games.
    전체 분석완료 게임에 대해 각 vibe 70점+ 수, 미커버, 겹침을 측정."""
    async with AsyncSessionLocal() as db:
        games = (await db.execute(
            select(Game).options(selectinload(Game.metrics))
            .where(Game.is_active == True).where(Game.is_analyzed == True)
        )).scalars().all()
        print(f'전체 {len(games)}개\n')

        game_vibe_count = {}
        vibe_counts = {v: 0 for v in VIBES}

        for g in games:
            if not g.metrics:
                continue
            gm = {f: float(getattr(g.metrics, f, 5.0) or 5.0)
                  for f in NUMERIC_METRIC_FIELDS}
            genre = (g.genres or '').split(',')[0].strip()
            n_belong = 0
            for vibe, prefs in VIBES.items():
                r = calculate_score_v6(
                    gm, prefs, genre,
                    g.review_count or 0,
                    g.steam_positive_ratio or 0.5,
                    float(g.metrics.gem_percentile or 50),
                )
                if r['final_score'] >= 70:
                    vibe_counts[vibe] += 1
                    n_belong += 1
            game_vibe_count[g.app_id] = n_belong

        print('=== Vibe별 70점+ (PRD: 50~500) ===')
        cnts = [v for v in vibe_counts.values() if v > 0]
        for vibe, cnt in sorted(vibe_counts.items(), key=lambda x: -x[1]):
            status = 'OK' if 50 <= cnt <= 500 else ('적음' if cnt < 50 else '과밀')
            print(f'  {vibe:20} {cnt:5}개  [{status}]')
        if cnts:
            print(f'\n  최대/최소: {max(cnts)/max(min(cnts),1):.1f}:1  (PRD <10:1)')

        belongs = [n for n in game_vibe_count.values() if n > 0]
        none_cnt = sum(1 for n in game_vibe_count.values() if n == 0)
        over3 = sum(1 for n in game_vibe_count.values() if n >= 4)
        print(f'\n=== 겹침 ===')
        print(f'  커버 안 됨(0 vibe): {none_cnt}개')
        print(f'  4개+ 동시소속: {over3}개 (변별 약함)')
        if belongs:
            print(f'  평균 소속: {sum(belongs)/len(belongs):.1f}개')


if __name__ == '__main__':
    asyncio.run(main())