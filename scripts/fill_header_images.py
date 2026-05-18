"""
Steam Header Image URL 일괄 채우기 스크립트 Phase A (Header Image Filler)

app_id를 기반으로 표준 Steam CDN URL을 생성하여 games.header_image 컬럼을 채움.
CDN URL은 실제 요청 없이 app_id만으로 결정론적으로 생성 (네트워크 없이 빠른 처리).
URL 유효성 검증은 Phase B(verify_header_images.py)에서 별도 수행.

사용 흐름:
    Phase A: [fill_header_images.py]  - CDN URL 규칙으로 일괄 생성 (빠름)
    Phase B: verify_header_images.py  - HEAD 요청으로 404 확인 및 대체 URL 탐색

실행:
    cd C:\\Hidden-Gem-project
    python scripts/fill_header_images.py
    python scripts/fill_header_images.py --force   # 기존 값도 덮어쓰기
    python scripts/fill_header_images.py --dry-run # 실제 UPDATE 안 함
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import List, Tuple

# fastapi_app 경로 추가 (database, models 재사용)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "fastapi_app"))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from tqdm import tqdm

from database import AsyncSessionLocal
from models.game import Game


STEAM_CDN_TEMPLATE = (
    "https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg"
)


def build_url(app_id: int) -> str:
    """app_id → 표준 Steam CDN header.jpg URL"""
    return STEAM_CDN_TEMPLATE.format(app_id=app_id)


async def fetch_targets(
    db: AsyncSession,
    force: bool,
) -> List[Tuple[int, int, str]]:
    """
    업데이트 대상 게임 조회 (Fetch Target Games)

    기본적으로 header_image가 빈 게임만 조회.
    --force 옵션 시 이미 채워진 게임도 포함하여 전체 덮어쓰기.

    Args:
        db: 비동기 DB 세션
        force: True면 기존 header_image 있어도 포함

    Returns:
        [(game.id, app_id, current_header_image), ...] 리스트
    """
    stmt = select(Game.id, Game.app_id, Game.header_image).where(
        Game.is_active == True
    )
    if not force:
        # 기본: header_image가 비어있거나 null인 게임만 대상
        stmt = stmt.where(
            (Game.header_image == "") | (Game.header_image.is_(None))
        )

    stmt = stmt.order_by(Game.id)
    result = await db.execute(stmt)
    return [(row.id, row.app_id, row.header_image or "") for row in result]


async def bulk_update_headers(
    db: AsyncSession,
    targets: List[Tuple[int, int, str]],
    batch_size: int = 500,
    dry_run: bool = False,
) -> int:
    """
    배치 단위로 header_image UPDATE 실행 (Bulk Update Headers)

    batch_size 단위로 커밋하여 트랜잭션 범위를 제한.
    배치 실패 시 해당 배치만 롤백하고 예외를 다시 던져 전파.

    Args:
        db: 비동기 DB 세션
        targets: fetch_targets()의 반환값
        batch_size: 1회 커밋당 처리 게임 수 (기본 500)
        dry_run: True면 실제 DB 변경 없이 카운트만 증가

    Returns:
        실제 업데이트된(또는 dry-run 집계) row 수
    """
    updated = 0
    
    with tqdm(total=len(targets), desc="🖼️  Filling headers", unit="game") as pbar:
        for i in range(0, len(targets), batch_size):
            batch = targets[i : i + batch_size]
            
            try:
                for game_id, app_id, _ in batch:
                    url = build_url(app_id)
                    
                    if dry_run:
                        pbar.update(1)
                        updated += 1
                        continue
                    
                    stmt = (
                        update(Game)
                        .where(Game.id == game_id)
                        .values(header_image=url)
                    )
                    await db.execute(stmt)
                    updated += 1
                    pbar.update(1)
                
                if not dry_run:
                    await db.commit()
            
            except Exception as e:
                await db.rollback()
                pbar.write(f"❌ Batch {i//batch_size} 실패: {e}")
                raise
    
    return updated


async def main():
    parser = argparse.ArgumentParser(description="Steam header image 일괄 채우기")
    parser.add_argument(
        "--force",
        action="store_true",
        help="이미 채워진 header_image도 덮어쓰기",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 UPDATE 없이 시뮬레이션만",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="배치 단위 커밋 크기 (기본 500)",
    )
    args = parser.parse_args()
    
    print("=" * 60)
    print("🖼️  Hidden Gem - Steam Header Image Filler (Phase A)")
    print("=" * 60)
    print(f"   force      : {args.force}")
    print(f"   dry_run    : {args.dry_run}")
    print(f"   batch_size : {args.batch_size}")
    print("=" * 60)
    
    async with AsyncSessionLocal() as db:
        # 1. 대상 조회
        print("\n1️⃣  업데이트 대상 조회 중...")
        targets = await fetch_targets(db, force=args.force)
        print(f"   → 대상 게임: {len(targets):,}개")
        
        if not targets:
            print("\n✅ 채울 게임이 없습니다. (이미 모두 채워진 상태)")
            print("   덮어쓰려면 --force 옵션을 사용하세요.")
            return
        
        # 2. 샘플 미리보기
        print("\n2️⃣  샘플 URL 미리보기 (처음 3개):")
        for game_id, app_id, current in targets[:3]:
            print(f"   [{game_id}] app_id={app_id}")
            print(f"        old: {current or '(empty)'}")
            print(f"        new: {build_url(app_id)}")
        
        # 3. 실행
        print(f"\n3️⃣  업데이트 시작...")
        updated = await bulk_update_headers(
            db, targets, batch_size=args.batch_size, dry_run=args.dry_run
        )
        
        print(f"\n✅ 완료! {updated:,}개 게임 업데이트")
        if args.dry_run:
            print("   ⚠️  --dry-run 모드라서 실제 DB는 변경되지 않았습니다.")


if __name__ == "__main__":
    asyncio.run(main())