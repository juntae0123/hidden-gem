"""
v6 변별력 실측 — DB 직접 (API 인코딩 우회).
"""
import asyncio
import sys
sys.path.insert(0, '/app')

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database import AsyncSessionLocal
from models.game import Game, NUMERIC_METRIC_FIELDS
from services.score_v6 import calculate_score_v6


async def measure(preferences: dict, label: str):
    async with AsyncSessionLocal() as db:
        stmt = (
            select(Game)
            .options(selectinload(Game.metrics))
            .where(Game.is_active == True)
            .where(Game.is_analyzed == True)
        )
        games = (await db.execute(stmt)).scalars().all()

        scored = []
        for game in games:
            if not game.metrics:
                continue
            gm = {f: float(getattr(game.metrics, f, 5.0) or 5.0)
                  for f in NUMERIC_METRIC_FIELDS}
            genre = (game.genres or '').split(',')[0].strip()
            r = calculate_score_v6(
                game_metrics=gm,
                target_metrics=preferences,
                genre=genre,
                review_count=game.review_count or 0,
                positive_ratio=game.steam_positive_ratio or 0.5,
                gem_percentile=float(game.metrics.gem_percentile or 50),
            )
            scored.append((r['final_score'], game.name, r['breakdown']))

        scored.sort(key=lambda x: -x[0])
        s = [x[0] for x in scored]

        print(f"\n{'='*55}")
        print(f"[{label}] 전체 {len(scored)}개")
        print(f"{'='*55}")
        for i in [0, 9, 49, len(scored)//2, -1]:
            sc, nm, bd = scored[i]
            rank = i+1 if i >= 0 else len(scored)
            try:
                nm_safe = nm.encode('ascii', 'replace').decode()[:25]
            except:
                nm_safe = '???'
            print(f"  {rank:3}위 {sc:5.1f}  C:{bd['core_score']:4.1f} X:{bd['xfactor_score']:4.1f} G:{bd['gem_score']:3.1f}  {nm_safe}")

        print(f"\n  Top10 분포: {s[0]-s[9]:.1f}점")
        print(f"  1위-끝: {s[0]-s[-1]:.1f}점  {'✅진짜변별력' if s[0]-s[-1]>30 else '❌부족'}")

        # Witcher 추적
        w = next(((sc, nm, scored.index((sc,nm,bd))+1)
                  for sc, nm, bd in scored if 'Witcher' in nm), None)
        if w:
            print(f"  Witcher: {w[0]:.1f}점 ({w[2]}위)")
        else:
            print(f"  Witcher: 밖")

        return scored


async def main():
    # 다크판타지
    dark = await measure(
        {'dark_fantasy_vibe': 9, 'narrative_depth': 9}, '다크판타지'
    )
    # 힐링 (Witcher 밀려야)
    cozy = await measure(
        {'cozy_factor': 9, 'horror_factor': 0}, '힐링'
    )

    # 일관성: Witcher 다크 vs 힐링
    print(f"\n{'='*55}")
    print("[검색 일관성] Witcher")
    print(f"{'='*55}")
    wd = next((sc for sc, nm, _ in dark if 'Witcher' in nm), None)
    wc = next((sc for sc, nm, _ in cozy if 'Witcher' in nm), None)
    print(f"  다크판타지: {wd:.1f} / 힐링: {wc:.1f}")
    print(f"  차이: {abs(wd-wc):.1f}점  {'✅의도매칭' if abs(wd-wc)>20 else '⚠️약함'}")


if __name__ == '__main__':
    asyncio.run(main())