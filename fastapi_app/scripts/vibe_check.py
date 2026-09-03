"""Vibe distribution check (70점 컷) — 정의 수정 후 재측정 + 쌍별 겹침."""
import sys, io, asyncio
from itertools import combinations
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '/app')
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database import AsyncSessionLocal
from models.game import Game, NUMERIC_METRIC_FIELDS
from services.score_v6 import calculate_score_v6

VIBES = {
    'cozy_escape': {'cozy_factor': 9, 'horror_factor': 0},
    'dark_narrative': {'dark_fantasy_vibe': 9, 'choice_consequence': 9, 'lore_richness': 8},
    'brain_strategy': {'strategic_depth': 9, 'management_complexity': 8},
    'action_thrill': {'action_pacing': 9, 'reflex_demand': 8, 'time_pressure': 7},
    'exploration_wonder': {'exploration_reward': 9, 'freedom_level': 8},
    'horror_tension': {'horror_factor': 9, 'environmental_storytelling': 7},
    'emotional_journey': {'melancholy': 9, 'soundtrack_impact': 9},
    'challenge_master': {'learning_curve': 9, 'strategic_depth': 8, 'grind_factor': 7},
    'creative_sandbox': {'user_creation': 9, 'freedom_level': 9},
    'roguelike_loop': {'rng_dependency': 8, 'replay_value': 9, 'build_variety': 8},
    'artistic_vision': {'art_style_uniqueness': 9, 'soundtrack_impact': 8},
    'coop_fun': {'coop_synergy': 9, 'multiplayer_scale': 7},
}

async def main():
    async with AsyncSessionLocal() as db:
        games = (await db.execute(
            select(Game).options(selectinload(Game.metrics))
            .where(Game.is_active == True).where(Game.is_analyzed == True)
        )).scalars().all()
        print(f'전체 {len(games)}개\n')

        game_vibe_count = {}
        vibe_counts = {v: 0 for v in VIBES}
        # 게임별 70+ 걸린 vibe 집합 (쌍별 겹침용)
        game_vibes = {}

        for g in games:
            if not g.metrics: continue
            gm = {f: float(getattr(g.metrics, f, 5.0) or 5.0) for f in NUMERIC_METRIC_FIELDS}
            genre = (g.genres or '').split(',')[0].strip()
            hit = []
            for vibe, prefs in VIBES.items():
                r = calculate_score_v6(gm, prefs, genre,
                    g.review_count or 0, g.steam_positive_ratio or 0.5,
                    float(g.metrics.gem_percentile or 50))
                if r['final_score'] >= 70:
                    vibe_counts[vibe] += 1
                    hit.append(vibe)
            game_vibe_count[g.app_id] = len(hit)
            game_vibes[g.app_id] = hit

        print('=== 70점 컷 (PRD: 50~500) ===')
        cnts = [v for v in vibe_counts.values() if v > 0]
        for vibe, cnt in sorted(vibe_counts.items(), key=lambda x: -x[1]):
            s = 'OK' if 50 <= cnt <= 500 else ('적음' if cnt < 50 else '과밀')
            print(f'  {vibe:20} {cnt:5}개  [{s}]')
        if cnts:
            print(f'\n  최대/최소: {max(cnts)/max(min(cnts),1):.1f}:1  (PRD <10:1)')

        none = sum(1 for n in game_vibe_count.values() if n == 0)
        over3 = sum(1 for n in game_vibe_count.values() if n >= 4)
        belongs = [n for n in game_vibe_count.values() if n > 0]
        print(f'\n=== 겹침 ===')
        print(f'  커버 안 됨: {none}개 ({none/len(games)*100:.0f}%)')
        print(f'  4개+ 겹침: {over3}개')
        if belongs:
            print(f'  평균 소속: {sum(belongs)/len(belongs):.1f}개')

        # 쌍별 겹침: 두 vibe에 동시 70+ 게임 수 Top5
        pair = {}
        for vibes in game_vibes.values():
            for a, b in combinations(sorted(vibes), 2):
                pair[(a, b)] = pair.get((a, b), 0) + 1
        print(f'\n=== 쌍별 겹침 Top5 (동시 70+) ===')
        for (a, b), c in sorted(pair.items(), key=lambda x: -x[1])[:5]:
            print(f'  {a} ∩ {b}: {c}개')

if __name__ == '__main__':
    asyncio.run(main())