"""
임베딩 pkl 파일 → PostgreSQL vector 컬럼 적재 스크립트 (Embedding Loader)

hidden_gem_data.pkl의 1536차원 임베딩(text-embedding-3-small)을
game_metrics.embedding(pgvector vector(1536)) 컬럼에 배치 업데이트.

완료 후 HNSW 인덱스를 자동 생성하여 코사인 유사도 검색을 가속화.

사전 조건:
    - PostgreSQL pgvector 확장 설치 필요
    - game_metrics 테이블에 embedding vector(1536) 컬럼 존재
    - pkl 파일의 embedding 컬럼은 JSON 문자열 또는 리스트 형식

실행:
    python scripts/load_embeddings.py
    python scripts/load_embeddings.py --dry-run
    python scripts/load_embeddings.py --pkl data/hidden_gem_data.pkl --batch-size 200
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
import pickle

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "fastapi_app"))

from sqlalchemy import select, text
from tqdm import tqdm

from database import AsyncSessionLocal
from models.game import Game


async def main():
    """
    임베딩 적재 메인 로직 (Embedding Load Main)

    4단계 파이프라인:
        1) pkl 로드 → 유효한 1536차원 임베딩 딕셔너리 구성
        2) DB 매핑 → app_id ↔ game_id(PK) 매핑 조회
        3) 배치 UPDATE → raw SQL로 vector 컬럼 업데이트 (ORM 우회)
        4) HNSW 인덱스 생성 → 코사인 유사도 검색 가속화

    Note:
        ORM 대신 raw SQL 사용: pgvector의 vector 타입을 SQLAlchemy ORM이 직렬화하는
        방식이 버전별로 불안정하여 str(emb) → postgres vector 리터럴로 직접 전달.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--pkl", type=str, default="data/hidden_gem_data.pkl")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()

    print("=" * 60)
    print("Hidden Gem - Embedding Loader")
    print("=" * 60)

    # 1단계: pkl 파일에서 1536차원 임베딩 추출
    print("\n1️⃣  pkl 로딩 중...")
    with open(args.pkl, "rb") as f:
        df = pickle.load(f)
    print(f"   → {len(df)}개 게임 로드")

    emb_dict = {}
    for _, row in df.iterrows():
        app_id = int(row["app_id"])
        emb_raw = row["embedding"]
        if emb_raw is None:
            continue
        try:
            # JSON 문자열 또는 리스트 형태 모두 처리
            emb = json.loads(emb_raw) if isinstance(emb_raw, str) else list(emb_raw)
            if len(emb) == 1536:  # text-embedding-3-small 차원 검증
                emb_dict[app_id] = emb
        except Exception:
            continue

    print(f"   → 유효한 임베딩: {len(emb_dict)}개")

    # 2단계: DB에서 app_id → game.id(PK) 매핑 조회
    print("\n2️⃣  DB 매핑 조회 중...")
    async with AsyncSessionLocal() as db:
        stmt = select(Game.app_id, Game.id).where(Game.is_active == True)
        result = await db.execute(stmt)
        app_to_game_id = {row.app_id: row.id for row in result}

    print(f"   → DB 게임 수: {len(app_to_game_id)}개")

    # pkl과 DB 교집합만 적재 대상
    targets = [
        (app_id, app_to_game_id[app_id], emb)
        for app_id, emb in emb_dict.items()
        if app_id in app_to_game_id
    ]
    print(f"   → 적재 대상: {len(targets)}개")

    if args.dry_run:
        print("\n dry-run 모드: 실제 DB 변경 없음")
        print(f"   샘플 app_id: {targets[0][0]}, 임베딩 차원: {len(targets[0][2])}")
        return

    # 3단계: 배치 단위 raw SQL UPDATE (ORM 우회로 pgvector 직렬화 안정성 확보)
    print(f"\n3️⃣  임베딩 적재 중 (batch={args.batch_size})...")
    updated = 0

    with tqdm(total=len(targets), desc="Loading embeddings", unit="game") as pbar:
        for i in range(0, len(targets), args.batch_size):
            batch = targets[i: i + args.batch_size]
            async with AsyncSessionLocal() as db:
                for app_id, game_id, emb in batch:
                    # str(emb)로 Python 리스트를 PostgreSQL vector 리터럴로 변환
                    await db.execute(
                        text("UPDATE game_metrics SET embedding = :emb WHERE game_id = :gid"),
                        {"emb": str(emb), "gid": game_id}
                    )
                    updated += 1
                    pbar.update(1)
                await db.commit()  # 배치 단위 커밋 (중간 실패 시 해당 배치만 재시도 가능)

    print(f"\n임베딩 적재 완료: {updated:,}개")

    # 4단계: HNSW 인덱스 생성 (cosine 유사도 검색 가속)
    # m=16, ef_construction=64는 정확도/성능 균형을 위한 경험적 값
    print("\n4️⃣  HNSW 인덱스 생성 중...")
    async with AsyncSessionLocal() as db:
        await db.execute(text("""
            CREATE INDEX IF NOT EXISTS game_metrics_embedding_hnsw
            ON game_metrics
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """))
        await db.commit()
    print("   → 인덱스 생성 완료!")

    print("\n전체 완료!")
    print(f"   적재된 임베딩: {updated:,}개")
    print(f"   HNSW 인덱스: game_metrics_embedding_hnsw")


if __name__ == "__main__":
    asyncio.run(main())