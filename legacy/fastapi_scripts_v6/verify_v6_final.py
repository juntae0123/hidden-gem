"""
v6 final verification — 3 checks (Witcher breakdown + PvZ trap + must_not).
v6 추천 품질 종료를 위한 마지막 검증 3개: X-Factor 거품 / 대형작 함정 / must_not 하드필터.
"""
import asyncio
import sys
sys.path.insert(0, '/app')

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database import AsyncSessionLocal  # config.database/async_session → database/AsyncSessionLocal (실제 정의명)
from models.game import Game, NUMERIC_METRIC_FIELDS
from services.score_v6 import calculate_score_v6


def safe_name(nm: str) -> str:
    """ASCII-safe truncated name for console output.
    한글 게임명 콘솔 출력 시 인코딩 깨짐 방지 (ascii replace + 28자 컷)."""
    try:
        return nm.encode('ascii', 'replace').decode()[:28]
    except Exception:
        return '???'


async def score_all(db, preferences: dict, must_not: dict | None = None):
    """Score every analyzed game with v6 + optional must_not hard filter.
    전체 분석완료 게임을 v6로 채점하고, must_not 지정 시 임계값 이상이면 하드 제외."""
    stmt = (
        select(Game).options(selectinload(Game.metrics))
        .where(Game.is_active == True).where(Game.is_analyzed == True)
    )
    games = (await db.execute(stmt)).scalars().all()
    scored = []
    filtered_out = 0
    for game in games:
        if not game.metrics:
            continue
        gm = {f: float(getattr(game.metrics, f, 5.0) or 5.0)
              for f in NUMERIC_METRIC_FIELDS}

        # must_not 하드필터 / hard exclusion
        if must_not:
            skip = False
            for mf, thr in must_not.items():
                if gm.get(mf, 0) >= thr:
                    skip = True
                    break
            if skip:
                filtered_out += 1
                continue

        genre = (game.genres or '').split(',')[0].strip()
        r = calculate_score_v6(
            game_metrics=gm, target_metrics=preferences, genre=genre,
            review_count=game.review_count or 0,
            positive_ratio=game.steam_positive_ratio or 0.5,
            gem_percentile=float(game.metrics.gem_percentile or 50),
        )
        scored.append((r['final_score'], game.name, r['breakdown'],
                       game.review_count or 0, gm))
    scored.sort(key=lambda x: -x[0])
    return scored, filtered_out


async def main():
    async with AsyncSessionLocal() as db:

        # ═══ 검증 A: Witcher 50.4 분해 (X-Factor 거품 체크) ═══
        print("=" * 60)
        print("[검증A] Witcher 힐링검색 분해 — X-Factor 거품?")
        print("=" * 60)
        scored, _ = await score_all(db, {'cozy_factor': 9, 'horror_factor': 0})
        w = next(((sc, nm, bd, rv, gm) for sc, nm, bd, rv, gm in scored
                  if 'Witcher' in nm), None)
        if w:
            sc, nm, bd, rv, gm = w
            rank = next((i + 1 for i, x in enumerate(scored) if 'Witcher' in x[1]), -1)
            print(f"  Witcher 힐링: {sc:.1f}점 ({rank}위)")
            print(f"    Core: {bd['core_score']:.1f}  X-Factor: {bd['xfactor_score']:.1f}  Gem: {bd['gem_score']:.1f}")
            if bd['xfactor_score'] > bd['core_score']:
                print(f"    X-Factor > Core → 거품 위험!")
                print(f"       힐링 안 맞는데 독창성으로 점수 띄움")
            else:
                print(f"    Core 기반 (X-Factor 거품 아님)")
            cozy = gm.get('cozy_factor', 0)
            print(f"    cozy_factor(힐링): {cozy} (낮아야 정상)")
            # 1877위 주변 5개 — 거품 게임 군집 확인
            print("  Witcher 주변 (앞2 / 뒤2):")
            for i in range(max(0, rank - 3), min(len(scored), rank + 2)):
                s2, n2, b2, r2, g2 = scored[i]
                print(f"    {i+1:>5}위 {s2:5.1f}  C:{b2['core_score']:4.1f} X:{b2['xfactor_score']:4.1f} G:{b2['gem_score']:3.1f}  {safe_name(n2)}")
        else:
            print("  Witcher 못 찾음 (DB에 없거나 이름 불일치)")

        # ═══ 검증 B: 숨겨진 보석 — PvZ 함정 ═══
        print("\n" + "=" * 60)
        print("[검증B] 숨겨진 보석 — PvZ 등 대형작 거르나")
        print("=" * 60)
        scored, _ = await score_all(db, {'art_style_uniqueness': 9, 'narrative_depth': 8})
        print("  Top 10:")
        big_keywords = ['Plants vs', 'Witcher', 'Hollow', 'Terraria',
                        'Stardew', 'Counter', 'Dota', 'PUBG']
        found_big = []
        for sc, nm, bd, rv, gm in scored[:10]:
            is_big = any(k in nm for k in big_keywords)
            mark = " 대형작" if is_big else ""
            if is_big:
                found_big.append(safe_name(nm))
            print(f"    {sc:5.1f}  C:{bd['core_score']:4.1f} X:{bd['xfactor_score']:4.1f} G:{bd['gem_score']:3.1f}  rv:{rv:>7}  {safe_name(nm)}{mark}")
        print(f"\n  [판정] 대형작 상위: {found_big if found_big else '없음 '}")
        s = [x[0] for x in scored]
        print(f"  분산: 1위{s[0]:.1f} ~ 끝{s[-1]:.1f} = {s[0]-s[-1]:.1f}점")

        # ═══ 검증 C: 공포 없는 힐링 — must_not 하드필터 ═══
        print("\n" + "=" * 60)
        print("[검증C] 공포 없는 힐링 — must_not 필터 작동?")
        print("=" * 60)
        no_filter, _ = await score_all(db, {'cozy_factor': 9})
        horror_in_top = sum(1 for sc, nm, bd, rv, gm in no_filter[:20]
                            if gm.get('horror_factor', 0) >= 7)
        with_filter, filtered = await score_all(
            db, {'cozy_factor': 9}, must_not={'horror_factor': 7})
        horror_after = sum(1 for sc, nm, bd, rv, gm in with_filter[:20]
                           if gm.get('horror_factor', 0) >= 7)
        print(f"  필터 전 Top20 공포게임: {horror_in_top}개")
        print(f"  필터 후 Top20 공포게임: {horror_after}개")
        print(f"  제외된 게임 수: {filtered}개")
        if horror_after == 0:
            print(f"  [판정] must_not 작동 (공포 완전 제외)")
        else:
            print(f"  [판정] 공포게임 {horror_after}개 남음")

    print("\n" + "=" * 60)
    print("검증 3개 완료")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())