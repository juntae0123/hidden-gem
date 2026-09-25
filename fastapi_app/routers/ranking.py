"""
랭킹 API — 사용자 무관 지표로 정렬 (docs/lifecycle_split_spec_0905.md §3, decisions R-12)

    GET /api/v1/games/ranking?type=steady|rising|new&genre=&limit=30

steady  스테디 히든젬  established, 리뷰 ≥ 30, Wilson ≥ 0.5     → 발굴 지수(Wilson × 무명도) desc
rising  요즘 뜨는      established+new, 30일 Δ ≥ 20, Wilson ≥ 0.5 → 30일 상대 증가율 desc  (review_history 필요)
new     신작           출시 ≤ 180일, 리뷰 ≥ 3, Wilson ≥ 0.70      → 누적 리뷰 수 desc, 동률 Wilson  (R-17, 2026-09-05 변경)
                       (이전: 속도 = 리뷰/출시일수. 생애 평균 속도는 D+3~16 출시작의 초기 스파이크에 편향돼
                        AAA 신작이 상위를 채웠다 — s6 실측: 낚시 방법 3,180/일(D+16) > 메챠 카멜레온 995/일(D+88, 누적 8.7만).
                        '지금의 속도'는 review_history 30일 Δ 가 쌓이면 rising 이 맡는다. new 는 '이번 시즌 가장 많이 검증된 신작'.)
new_quiet 조용한 신작   위 조건 + 리뷰 < 100                      → Wilson desc, 동률 속도 — 아직 소리 없는 신생 게임의 쇼케이스

개발자 취지(2026-09-05): "신작으로 신생 게임을 보호해서 그들만의 리그를 만들고 보여주자."
신작은 정착 게임과 발굴 지수로 경쟁하지 않는다. 신작끼리 경쟁하고, 조용한 신작은 따로 보여준다.

지금까지 /ranking 화면은 장르 프리셋 by-preference 결과였다 — 랭킹이 아니었다. 이것이 첫 랭킹이다.
카나리아(개발자 지정): MECCHA CHAMELEON(app 4704690, 리뷰 8.7만, 출시 ≤180일)은 **신작 후보에 들어가야** 한다
(리뷰 수로 먼저 나누면 '유명'으로 빠져 사라진다). 개발자 원문은 "신작랭킹 1위가 아니면 말이 안 된다" — 누적 리뷰 정렬(R-17)에서는
180일 안에 더 많이 검증받은 신작이 나오면 1위가 바뀌는 게 정상이고, 그때는 그 게임이 새 카나리아다. rec_snapshot 이 회차마다 1위를 찍는다.
"""

import logging
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
from services.lifecycle import lifecycle, days_since_release, is_famous, NEW, ESTABLISHED

logger = logging.getLogger(__name__)
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
    is_famous: bool = False
    days_since_release: Optional[int] = None
    gem_evidence: Optional[float] = None      # steady
    velocity_per_day: Optional[float] = None  # new
    delta_30d: Optional[int] = None           # rising
    growth_30d_pct: Optional[float] = None    # rising
    window_days: Optional[int] = None         # rising: 실제 비교 구간(일). 30일 이력이 없으면 7~29일 (R-27)
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
        lifecycle=lc, is_famous=is_famous(g.review_count), days_since_release=days_since_release(g.release_date),
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


NEW_RANK_MIN_WILSON = 0.70          # 쇼케이스 기준 — Steam '대체로 긍정적'(70%) 하한. 노출 게이트(R-4, 0.35)와는 목적이 다르다
NEW_QUIET_MIN_WILSON = 0.35         # 조용한 신작은 보호 목적 — 노출 게이트와 같게


def new_rank_key(review_count: int, wilson: float, velocity: Optional[float], quiet: bool) -> tuple:
    """정렬 키(내림차순). new: 누적 리뷰 → Wilson → 속도. new_quiet: Wilson → 속도 → 누적 (평가 먼저).
    순수 함수 — 테스트에서 직접 검증한다 (test_lifecycle::test_new_rank_key_*)."""
    v = velocity or 0.0
    if quiet:
        return (wilson, v, review_count)
    return (review_count, wilson, v)


async def rank_new(db, genre, limit, quiet: bool = False):
    pool = await _base_pool(db, genre)
    rows = []
    for g in pool:
        if lifecycle(g.review_count, g.release_date) != NEW:
            continue
        rc = g.review_count or 0
        if rc < 3:
            continue
        if quiet and rc >= settings.LIFECYCLE_NEW_MIN_REVIEWS:
            continue                                   # 조용한 신작: 리뷰 100 미만만
        w = wilson_lower(g.steam_positive_ratio, g.review_count)
        if w < (NEW_QUIET_MIN_WILSON if quiet else NEW_RANK_MIN_WILSON):
            continue
        v = velocity_per_day(g.review_count, days_since_release(g.release_date))
        if v is None:
            continue
        rows.append((new_rank_key(rc, w, v, quiet), v, g))
    rows.sort(key=lambda r: r[0], reverse=True)
    return [_item(i + 1, g, "new", velocity_per_day=v) for i, (_, v, g) in enumerate(rows[:limit])]


RISING_MIN_GAP_DAYS = 7        # 이보다 짧은 구간은 노이즈 — 비교하지 않는다
RISING_TARGET_DAYS = 30        # 목표 구간. 이력이 모자라면 7일 이상 중 30일에 가장 가까운 시점을 쓴다 (R-27)
RISING_MIN_DELTA_30D = 20      # 30일 환산 Δ 기준
RISING_RELAXED_DELTA_30D = 5   # 기준 통과가 RISING_MIN_FILL 미만이면 이 값으로 완화
RISING_MIN_FILL = 10


async def rank_rising(db, genre, limit):
    """review_history(app_id, refreshed_at, total_reviews) 에서 최근 구간 Δ.
    30일 전 시점이 없으면 7일 이상 떨어진 시점 중 30일에 가장 가까운 것을 쓰고, 정렬은 30일 환산 증가율로 한다 (R-27).
    표시는 실제 구간·실제 건수 그대로(window_days) — 환산값을 실측처럼 보이지 않게.
    7일 이상 떨어진 이력쌍이 하나도 없을 때만 신작 속도 랭킹으로 임시 대체한다(빈 탭 방지, note 로 명시).
    테이블 부재만 'collecting' 으로 처리한다 — 그 외 SQL 오류를 삼키면 장애가 '데이터 쌓는 중'으로 위장된다 (검토 E-8)."""
    exists = (await db.execute(text("SELECT to_regclass('review_history')"))).scalar()
    if exists is None:
        return [], "collecting", "리뷰 이력 테이블이 없다 — refresh_reviews 가 append-only 이력을 쌓기 시작한 뒤 생긴다"
    try:
        sql = text(f"""
            WITH latest AS (
                SELECT DISTINCT ON (app_id) app_id, refreshed_at, total_reviews
                FROM review_history ORDER BY app_id, refreshed_at DESC
            ),
            past AS (
                SELECT DISTINCT ON (h.app_id) h.app_id, h.total_reviews AS past_total,
                       EXTRACT(EPOCH FROM (l.refreshed_at - h.refreshed_at)) / 86400.0 AS gap_days
                FROM review_history h JOIN latest l ON l.app_id = h.app_id
                WHERE h.refreshed_at <= l.refreshed_at - INTERVAL '{RISING_MIN_GAP_DAYS} days'
                ORDER BY h.app_id,
                         ABS(EXTRACT(EPOCH FROM (l.refreshed_at - h.refreshed_at)) / 86400.0 - {RISING_TARGET_DAYS}),
                         h.refreshed_at DESC
            )
            SELECT l.app_id, l.total_reviews, p.past_total, p.gap_days,
                   (l.total_reviews - p.past_total) AS delta
            FROM latest l JOIN past p ON p.app_id = l.app_id
            WHERE l.total_reviews - p.past_total > 0
        """)
        rows = (await db.execute(sql)).fetchall()   # 상수만 f-string 으로 넣는다 (사용자 입력 없음)
    except Exception as e:
        await db.rollback()
        logger.exception("rank_rising SQL 실패")
        raise HTTPException(status_code=500, detail=f"요즘 뜨는 랭킹 계산 실패: {type(e).__name__}")
    if not rows:
        items = await rank_new(db, genre, limit)
        return items, "ok", "리뷰 이력이 아직 일주일치가 안 된다 — 쌓이는 동안 출시 초기 속도 기준으로 대신 보여준다"
    deltas = {r.app_id: (int(r.delta), int(r.past_total), float(r.gap_days)) for r in rows}
    pool = await _base_pool(db, genre)
    cands = []
    for g in pool:
        if g.app_id not in deltas:
            continue
        if lifecycle(g.review_count, g.release_date) not in (NEW, ESTABLISHED):
            continue                                   # famous(리뷰 2만+)·upcoming 제외 — 탭 정의 "유명작 독식 방지" (검토 C-4)
        w = wilson_lower(g.steam_positive_ratio, g.review_count)
        if w < 0.5:
            continue
        delta, past, gap = deltas[g.app_id]
        scale = RISING_TARGET_DAYS / max(gap, RISING_MIN_GAP_DAYS)
        d30 = delta * scale
        growth30 = delta / max(past, 50) * 100.0 * scale   # 절대 건수면 유명작이 독식 → 상대 증가율 (30일 환산)
        cands.append((growth30, d30, delta, gap, g))
    scored = [c for c in cands if c[1] >= RISING_MIN_DELTA_30D]
    relaxed = False
    if len(scored) < min(limit, RISING_MIN_FILL):
        scored = [c for c in cands if c[1] >= RISING_RELAXED_DELTA_30D]
        relaxed = True
    scored.sort(key=lambda r: (r[0], r[1]), reverse=True)
    top = scored[:limit]
    items = [_item(i + 1, g, "rising", delta_30d=delta,
                   growth_30d_pct=round(delta / max(deltas[g.app_id][1], 50) * 100.0, 1),
                   window_days=int(round(gap)))
             for i, (_, _, delta, gap, g) in enumerate(top)]
    note = ""
    if top:
        gaps = sorted(int(round(c[3])) for c in top)
        med = gaps[len(gaps) // 2]
        if med < RISING_TARGET_DAYS - 2:
            note = f"한 달치 이력이 쌓이는 중이라 최근 약 {med}일 기준으로 계산했다 (순위는 30일 환산)"
        if relaxed:
            note = (note + " · " if note else "") + "기준을 낮춰 표본을 채웠다"
    return items, "ok", note


@router.get("/ranking", response_model=RankingResponse)
async def ranking(
    type: str = Query("steady", pattern="^(steady|rising|new|new_quiet)$"),
    genre: Optional[str] = Query(None, description="장르 부분 일치 (예: 전략)"),
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    key = f"rank2:{CACHE_VERSION}:{type}:{genre or '-'}:{limit}"
    cached = await recommendation_cache.get(key)
    if cached:
        return RankingResponse(**cached)

    status, note = "ok", ""
    if type == "steady":
        items = await rank_steady(db, genre, limit)
    elif type == "new":
        items = await rank_new(db, genre, limit)
    elif type == "new_quiet":
        items = await rank_new(db, genre, limit, quiet=True)
    else:
        items, status, note = await rank_rising(db, genre, limit)

    resp = RankingResponse(type=type, genre=genre, total=len(items), status=status, note=note, items=items)
    # rising 은 이력 갱신(주 1회, ~2.5h) 직후 바로 반영되도록 짧게 — 6h 캐시가 갱신 전 결과를 붙잡고 있지 않게 (R-27)
    ttl = min(settings.CACHE_TTL_RANKING, 1800) if type == "rising" else settings.CACHE_TTL_RANKING
    await recommendation_cache.set(key, resp.model_dump(), ttl=ttl)
    return resp
