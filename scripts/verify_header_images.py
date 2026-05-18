"""
🔍 Steam Header Image URL 검증 (Phase B)

전략:
- 모든 게임의 header_image에 비동기 HEAD 요청
- 404면 대체 URL 시도 (capsule_184x69, library_600x900 등)
- 모두 실패하면 빈 문자열로 마킹
- Semaphore로 동시 요청 제한 (Steam CDN 매너)

실행:
    python scripts/verify_header_images.py
    python scripts/verify_header_images.py --concurrency 20
    python scripts/verify_header_images.py --limit 100   # 테스트용
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "fastapi_app"))

import aiohttp
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from tqdm.asyncio import tqdm as tqdm_asyncio

from database import AsyncSessionLocal
from models.game import Game


CDN_BASE = "https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}"

# 우선순위 순서대로 시도할 이미지 패턴
URL_CANDIDATES = [
    "/header.jpg",
    "/capsule_616x353.jpg",
    "/capsule_467x181.jpg",
    "/capsule_231x87.jpg",
    "/library_600x900.jpg",
]


async def check_url(
    session: aiohttp.ClientSession,
    url: str,
    timeout: float = 5.0,
) -> bool:
    """
    HTTP HEAD 요청으로 이미지 URL 유효성 확인 (URL Validity Check)

    GET 대신 HEAD를 사용하여 이미지 본문 다운로드 없이 상태 코드만 확인.
    타임아웃 또는 네트워크 오류 시 False 반환 (조용히 실패).

    Args:
        url: 확인할 이미지 URL
        timeout: 요청 타임아웃 (초, 기본 5.0)

    Returns:
        True = HTTP 200 (이미지 존재), False = 그 외 (404, 타임아웃 등)
    """
    try:
        async with session.head(
            url, timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=True
        ) as resp:
            return resp.status == 200
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return False


async def find_valid_url(
    session: aiohttp.ClientSession,
    app_id: int,
) -> Optional[str]:
    """
    app_id에 대해 유효한 이미지 URL을 우선순위 순으로 탐색 (URL Candidate Search)

    URL_CANDIDATES 목록 순서대로 HEAD 요청을 보내 200 응답이 오면 즉시 반환.
    header.jpg → capsule_616x353.jpg → ... 순으로 시도하며 모두 실패하면 None.

    Args:
        session: 재사용 aiohttp 세션
        app_id: Steam App ID

    Returns:
        유효한 이미지 URL 또는 None (모든 후보 실패)
    """
    base = CDN_BASE.format(app_id=app_id)
    for suffix in URL_CANDIDATES:
        url = base + suffix
        if await check_url(session, url):
            return url
    return None


async def process_game(
    sem: asyncio.Semaphore,
    http: aiohttp.ClientSession,
    db_session_factory,
    app_id: int,
    game_id: int,
) -> Tuple[int, Optional[str]]:
    """
    단일 게임 처리 - URL 탐색 + DB 업데이트 (Single Game Processing)

    Semaphore로 동시 요청을 제한하여 Steam CDN 레이트 리밋 방지.
    유효 URL 발견 시 즉시 DB UPDATE 처리 (배치가 아닌 개별 처리로 빠른 반영).

    Args:
        sem: 동시 요청 제한 Semaphore
        http: aiohttp 세션
        db_session_factory: AsyncSessionLocal 팩토리
        app_id: 처리할 Steam App ID
        game_id: games 테이블의 PK

    Returns:
        (game_id, 유효URL or None) 튜플
    """
    async with sem:
        valid_url = await find_valid_url(http, app_id)

    if valid_url is None:
        return game_id, None

    # 유효 URL이 확인된 게임만 DB 업데이트 (실패 게임은 main에서 일괄 처리)
    async with db_session_factory() as db:
        stmt = (
            update(Game)
            .where(Game.id == game_id)
            .values(header_image=valid_url)
        )
        await db.execute(stmt)
        await db.commit()

    return game_id, valid_url


async def main():
    parser = argparse.ArgumentParser(description="Steam header image 검증")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=15,
        help="동시 요청 수 (기본 15, 너무 높이면 차단 위험)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="처리할 최대 게임 수 (0=전체)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="HEAD 요청 타임아웃 (초)",
    )
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔍 Hidden Gem - Header Image Verifier (Phase B)")
    print("=" * 60)
    print(f"   concurrency : {args.concurrency}")
    print(f"   limit       : {args.limit or 'ALL'}")
    print(f"   timeout     : {args.timeout}s")
    print("=" * 60)
    
    # 대상 조회
    async with AsyncSessionLocal() as db:
        stmt = select(Game.id, Game.app_id).where(Game.is_active == True).order_by(Game.id)
        if args.limit > 0:
            stmt = stmt.limit(args.limit)
        result = await db.execute(stmt)
        rows = [(r.id, r.app_id) for r in result]
    
    print(f"\n1️⃣  검증 대상: {len(rows):,}개\n")
    
    sem = asyncio.Semaphore(args.concurrency)
    
    headers = {"User-Agent": "HiddenGem/1.0 (verification bot)"}
    connector = aiohttp.TCPConnector(limit=args.concurrency * 2)
    
    failed: List[int] = []
    succeeded = 0
    
    async with aiohttp.ClientSession(headers=headers, connector=connector) as http:
        tasks = [
            process_game(sem, http, AsyncSessionLocal, app_id, game_id)
            for game_id, app_id in rows
        ]
        
        for coro in tqdm_asyncio.as_completed(tasks, total=len(tasks), desc="🔍 Verifying"):
            game_id, url = await coro
            if url is None:
                failed.append(game_id)
            else:
                succeeded += 1
    
    print(f"\n✅ 성공: {succeeded:,}개")
    print(f"❌ 실패: {len(failed):,}개")
    
    if failed:
        print(f"\n실패한 game.id (처음 20개): {failed[:20]}")
        # 실패한 게임은 header_image를 빈 문자열로 마킹 (프론트에서 onError 처리)
        async with AsyncSessionLocal() as db:
            stmt = (
                update(Game)
                .where(Game.id.in_(failed))
                .values(header_image="")
            )
            await db.execute(stmt)
            await db.commit()
        print(f"   → 실패한 게임은 header_image='' 로 마킹했습니다.")


if __name__ == "__main__":
    asyncio.run(main())