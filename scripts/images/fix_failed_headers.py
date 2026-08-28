"""
Steam API를 이용한 header_image 복구 스크립트 (Failed Header Image Fixer)

fill_header_images.py + verify_header_images.py 이후에도 header_image가
빈 게임들을 Steam Store API(/api/appdetails)로 직접 조회하여 복구.

대상: header_image == "" 또는 null 인 활성 게임
전략: Steam API에서 data.header_image 필드 추출 후 DB 업데이트
     API도 실패하면 삭제/비공개 게임으로 간주 (header_image="" 유지)

실행:
    python scripts/fix_failed_headers.py
    python scripts/fix_failed_headers.py --concurrency 10 --dry-run
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
from tqdm.asyncio import tqdm as tqdm_asyncio

from database import AsyncSessionLocal
from models.game import Game


STEAM_API = "https://store.steampowered.com/api/appdetails?appids={app_id}&filters=basic"


async def fetch_steam_header(
    session: aiohttp.ClientSession,
    app_id: int,
    sem: asyncio.Semaphore,
) -> Optional[str]:
    """
    Steam Store API에서 단일 게임의 header_image URL 조회 (Steam API Fetch)

    Semaphore로 동시 요청 수를 제한하여 Steam API 레이트 리밋 방지.
    API 응답에서 success=false(삭제/비공개)이면 None 반환.

    Args:
        session: 재사용 aiohttp 클라이언트 세션
        app_id: 조회할 Steam App ID
        sem: 동시 요청 제한 Semaphore

    Returns:
        header_image URL 문자열 또는 None (실패/비공개 게임)
    """
    url = STEAM_API.format(app_id=app_id)
    async with sem:  # 동시 요청 수 제한 (Steam CDN 매너)
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)
                app_data = data.get(str(app_id), {})
                if not app_data.get("success"):
                    return None  # 삭제된 게임 또는 비공개 앱
                return app_data.get("data", {}).get("header_image")
        except Exception as e:
            print(f"\n app_id={app_id} 요청 실패: {e}")
            return None


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()

    print("=" * 60)
    print("Hidden Gem - Failed Header Image Fixer (Steam API)")
    print("=" * 60)

    # 1. 빈 게임 조회
    async with AsyncSessionLocal() as db:
        stmt = (
            select(Game.id, Game.app_id, Game.name)
            .where((Game.header_image == "") | (Game.header_image.is_(None)))
            .where(Game.is_active == True)
            .order_by(Game.id)
        )
        result = await db.execute(stmt)
        targets = [(r.id, r.app_id, r.name) for r in result]

    print(f"\n대상 게임: {len(targets)}개\n")
    if not targets:
        print("복구할 게임 없음!")
        return

    # 2. Steam API 호출 (한 번만)
    sem = asyncio.Semaphore(args.concurrency)
    headers = {"User-Agent": "HiddenGem/1.0"}

    async with aiohttp.ClientSession(headers=headers) as http:
        tasks = [
            fetch_steam_header(http, app_id, sem)
            for _, app_id, _ in targets
        ]
        urls = await tqdm_asyncio.gather(*tasks, desc="🌐 Steam API 호출 중")

    # 3. 결과 정리
    success = [
        (targets[i][0], targets[i][1], targets[i][2], urls[i])
        for i in range(len(targets)) if urls[i]
    ]
    failed = [
        (targets[i][1], targets[i][2])
        for i in range(len(targets)) if not urls[i]
    ]

    print(f"\nURL 확보: {len(success)}개")
    print(f"API도 실패: {len(failed)}개")

    if success:
        print("\n확보된 URL 샘플:")
        for game_id, app_id, name, url in success[:3]:
            print(f"  [{app_id}] {name}")
            print(f"       {url}")

    if failed:
        print(f"\nAPI도 실패한 게임 (삭제/비공개 가능성) - 처음 10개:")
        for app_id, name in failed[:10]:
            print(f"  [{app_id}] {name}")

    if args.dry_run:
        print("\n --dry-run 모드: 실제 DB 변경 없음")
        return

    # 4. DB 업데이트
    if success:
        async with AsyncSessionLocal() as db:
            for game_id, app_id, name, url in success:
                stmt = (
                    update(Game)
                    .where(Game.id == game_id)
                    .values(header_image=url)
                )
                await db.execute(stmt)
            await db.commit()
        print(f"\nDB 업데이트 완료: {len(success)}개")

    print("\n작업 완료!")
    print(f"   복구 성공: {len(success)}개")
    print(f"   복구 불가 (삭제/비공개): {len(failed)}개")


if __name__ == "__main__":
    asyncio.run(main())