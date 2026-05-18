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
    """HEAD 요청으로 이미지 존재 확인"""
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
    """app_id에 대해 유효한 이미지 URL을 순차 탐색"""
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
    """단일 게임 처리"""
    async with sem:
        valid_url = await find_valid_url(http, app_id)
    
    if valid_url is None:
        return game_id, None
    
    # 검증된 URL이 기본 header.jpg가 아니라면 DB 업데이트
    # 기본이라면 이미 같은 값이라 스킵
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