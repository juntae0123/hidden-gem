"""
랭킹 API — 사용자 무관 지표로 정렬 (docs/lifecycle_split_spec_0905.md §3, decisions R-12)

    GET /api/v1/games/ranking?type=steady|rising|new&genre=&limit=30

steady  스테디 히든젬  established, 리뷰 ≥ 30, Wilson ≥ 0.5     → 발굴 지수(Wilson × 무명도) desc
rising  요즘 뜨는      established+new, 30일 Δ ≥ 20, Wilson ≥ 0.5 → 30일 상대 증가율 desc  (review_history 필요)
new     신작           출시 ≤ 180일, 리뷰 ≥ 3, Wilson ≥ 0.35      → 초기 속도(리뷰/일) desc, 동률 Wilson

지금까지 /ranking 화면은 장르 프리셋 by-preference 결과였다 — 랭킹이 아니었다. 이것이 첫 랭킹이다.
카나리아(개발자 지정): 신작 랭킹 1위는 MECCHA CHAMELEON(app 4704690, 리뷰 8.7만)이어야 한다.
그렇지 않으면 정렬 정의가 틀린 것이다 — 정의를 고치지 카나리아를 빼지 않는다.
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models.game import Game
from services.cache import recommendation_cache, CACHE_VERSION
from services.evidence import gem_evidence, velocity_per_day, wilson_lower
from services.lifecycle import lifecycle, days_since_release, NEW, ESTABLISHED

router = APIRouter(prefix="/games", tags=["Ranking"])

CANARY_NEW_TOP = 4704690   # MECCHA CHAMELEON


class RankingItem(BaseModel):
    rank: int
    app_id: int
    name: str
    genres: str = ""
    header_image: str = ""
    one_line_summary: str = ""
    review_count: Optional[int] = None
    positive_ratio: Optional[float] = None
    wilson_lower: Optional[float] = None
    lifecycle: str
    days_since_release: Optional[int] = None
    gem_evidence: Optional[float] = None      # steady
    velocity_per_day: Optional[float] = None  # new
    delta_30d: Optional[int] = None           # rising
    growth_30d_pct: Optional[float] = None    # rising
    badge: str = ""                           # "히든젬" | "주목" | "떠오르는" | "신작" | ""


class RankingResponse(BaseModel):
    type: str
    genre: Optional[str] = None
    total: int
    status: str = "ok"                        # "ok" | "collecting" (rising: 이력 부족)
    note: str = ""
    items: List[RankingItem]


def _badge(kind: str, ev: Optional[float], rc: int) -> str:
    if kind == "steady":
        if ev is not None and ev >= 60 and rc >= 30:
            return "히든젬"
        if ev is not None and ev >= 45:
            return "주목"
        return ""
    if kind == "new":
        return "신작"
    if kind == "rising":
        return "떠오르는"
    return ""


async def _base_pool(db: AsyncSession, genre: Optional[str]):
    stmt = (
        select(Game)
        .where(Game.is_active == True)    # noqa: E712
        .where(Game.is_analyzed == True)  # noqa: E712
        .where(Game.review_count.isnot(None))
    )
    if genre:
        stmt = stmt.where(Game.genres.ilike(f"%{genre}%"))
    return (await db.execute(stmt)).scalars().all()


def _item(rank: int, g: Game, kind: str, **extra) -> RankingItem:
    rc = g.review_count or 0
    lc = lifecycle(g.review_count, g.release_date)
    return RankingItem(
        rank=rank, app_id=g.app_id, name=g.name or "", genres=g.genres or "",
        header_image=g.header_image or "", one_line_summary=g.one_line_summary or "",
        review_count=g.review_count, positive_ratio=g.steam_positive_ratio,
        wilson_lower=round(wilson_lower(g.steam_positive_ratio, g.review_count), 3),
        lifecycle=lc, days_since_release=days_since_release(g.release_date),
        badge=_badge(kind, extra.get("gem_evidence"), rc), **extra,
    )


async def rank_steady(db, genre, limit):
    pool = await _base_pool(db, genre)
    rows = []
    for g in pool:
        if lifecycle(g.review_count, g.release_date) != ESTABLISHED:
            continue
        if (g.review_count or 0) < 30:
            continue
        w = wilson_lower(g.steam_positive_ratio, g.review_count)
        if w < 0.5:
            continue
        ev = gem_evidence(g.steam_positive_ratio, g.review_count)
        if ev is None:
            continue
        rows.append((ev, w, -(g.review_count or 0), g))
    rows.sort(key=lambda r: (r[0], r[1], r[2]), reverse=True)
    return [_item(i + 1, g, "steady", gem_evidence=ev) for i, (ev, _, _, g) in enumerate(rows[:limit])]


async def rank_new(db, genre, limit):
    pool = await _base_pool(db, genre)
    rows = []
    for g in pool:
        if lifecycle(g.review_count, g.release_date) != NEW:
            continue
        if (g.review_count or 0) < 3:
            continue
        w = wilson_lower(g.steam_positive_ratio, g.review_count)
        if w < 0.35:
            continue
        v = velocity_per_day(g.review_count, days_since_release(g.release_date))
        if v is None:
            continue
        rows.append((v, w, g))
    rows.sort(key=lambda r: (r[0], r[1]), reverse=True)
    return [_item(i + 1, g, "new", velocity_per_day=v) for i, (v, _, g) in enumerate(rows[:limit])]


async def rank_rising(db, genre, limit):
    """review_history(app_id, refreshed_at, total_reviews) 에서 30일 Δ. 테이블이 없거나 이력이 1회분이면 collecting."""
    try:
        sql = text("""
            WITH latest AS (
                SELECT DISTINCT ON (app_id) app_id, refreshed_at, total_reviews
                FROM review_history ORDER BY app_id, refreshed_at DESC
            ),
            past AS (
                SELECT DISTINCT ON (h.app_id) h.app_id, h.total_reviews AS past_total, h.refreshed_at AS past_at
                FROM review_history h
                WHERE h.refreshed_at <= NOW() - INTERVAL '30 days'
                ORDER BY h.app_id, h.refreshed_at DESC
            )
            SELECT l.app_id, l.total_reviews, p.past_total,
                   (l.total_reviews - p.past_total) AS delta
            FROM latest l JOIN past p ON p.app_id = l.app_id
            WHERE l.total_reviews - p.past_total >= 20
        """)
        rows = (await db.execute(sql)).fetchall()
    except Exception:
        await db.rollback()
        return [], "collecting", "리뷰 이력 테이블이 없다 — refresh_reviews 가 append-only 이력을 쌓기 시작한 뒤 생긴다"
    if not rows:
        return [], "collecting", "30일 전 이력이 아직 없다 — 주간 리뷰 갱신 4~5회 뒤부터 계산된다"
    deltas = {r.app_id: (int(r.delta), int(r.past_total)) for r in rows}
    pool = await _base_pool(db, genre)
    scored = []
    for g in pool:
        if g.app_id not in deltas:
            continue
        w = wilson_lower(g.steam_positive_ratio, g.review_count)
        if w < 0.5:
            continue
        delta, past = deltas[g.app_id]
        growth = delta / max(past, 50) * 100.0      # 절대 건수면 유명작이 독식 → 상대 증가율
        scored.append((growth, delta, g))
    scored.sort(key=lambda r: (r[0], r[1]), reverse=True)
    items = [_item(i + 1, g, "rising", delta_30d=d, growth_30d_pct=round(gr, 1))
             for i, (gr, d, g) in enumerate(scored[:limit])]
    return items, "ok", ""


@router.get("/ranking", response_model=RankingResponse)
async def ranking(
    type: str = Query("steady", pattern="^(steady|rising|new)$"),
    genre: Optional[str] = Query(None, description="장르 부분 일치 (예: 전략)"),
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    key = f"rank:{CACHE_VERSION}:{type}:{genre or '-'}:{limit}"
    cached = await recommendation_cache.get(key)
    if cached:
        return RankingResponse(**cached)

    status, note = "ok", ""
    if type == "steady":
        items = await rank_steady(db, genre, limit)
    elif type == "new":
        items = await rank_new(db, genre, limit)
    else:
        items, status, note = await rank_rising(db, genre, limit)

    resp = RankingResponse(type=type, genre=genre, total=len(items), status=status, note=note, items=items)
    await recommendation_cache.set(key, resp.model_dump(), ttl=settings.CACHE_TTL_RANKING)
    return resp
