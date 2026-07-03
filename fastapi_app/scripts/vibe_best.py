"""Vibe best-assignment check — 게임마다 최고점 vibe 1개 배정 시 분포 (참고용)."""
import sys, io, asyncio
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
    async with AsyncSessionLocal() as db:
        games = (await db.execute(
            select(Game).options(selectinload(Game.metrics))
            .where(Game.is_active == True).where(Game.is_analyzed == True)
        )).scalars().all()
        best_vibe = {v: 0 for v in VIBES}
        # 배정된 게임의 그 vibe 점수도 같이 모음 (품질 확인)
        best_scores = {v: [] for v in VIBES}
        for g in games:
            if not g.metrics:
                continue
            gm = {f: float(getattr(g.metrics, f, 5.0) or 5.0) for f in NUMERIC_METRIC_FIELDS}
            genre = (g.genres or '').split(',')[0].strip()
            scores = {}
            for vibe, prefs in VIBES.items():
                r = calculate_score_v6(gm, prefs, genre,
                    g.review_count or 0, g.steam_positive_ratio or 0.5,
                    float(g.metrics.gem_percentile or 50))
                scores[vibe] = r['final_score']
            top = max(scores, key=scores.get)
            best_vibe[top] += 1
            best_scores[top].append(scores[top])
        print('=== 최고 vibe 배정 (커버 100%) ===')
        cnts = list(best_vibe.values())
        for vibe, cnt in sorted(best_vibe.items(), key=lambda x: -x[1]):
            pct = cnt / len(games) * 100
            avg = sum(best_scores[vibe]) / len(best_scores[vibe]) if best_scores[vibe] else 0
            # 배정됐지만 점수 낮은 게임 = 억지 배정
            weak = sum(1 for s in best_scores[vibe] if s < 50)
            print(f'  {vibe:20} {cnt:5}개 ({pct:4.1f}%)  평균{avg:4.1f}  50미만(억지){weak:4}개')
        print(f'\n  합계: {sum(cnts)} / {len(games)}')
        print(f'  최대/최소: {max(cnts)/max(min(cnts),1):.1f}:1')

if __name__ == '__main__':
    asyncio.run(main())