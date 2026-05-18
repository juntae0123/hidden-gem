"""
🖼️ Steam Header Image 일괄 채우기 (Phase A)

전략:
- app_id 기반 표준 Steam CDN URL 생성
- 4,190개 게임에 일괄 UPDATE
- 이미 채워진 게임은 스킵 (--force로 덮어쓰기 가능)
- 트랜잭션 단위 커밋 + 실패 시 롤백
- tqdm 진행률 표시

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
    업데이트 대상 조회
    
    Returns:
        [(id, app_id, current_header_image), ...]
    """
    stmt = select(Game.id, Game.app_id, Game.header_image).where(
        Game.is_active == True
    )
    if not force:
        # 비어있는 것만
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
    배치 단위로 UPDATE 실행
    
    Returns:
        실제 업데이트된 row 수
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