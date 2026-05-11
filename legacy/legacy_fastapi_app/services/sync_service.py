# fastapi_app/services/sync_service.py
"""
Hidden Gem - 데이터 동기화 서비스
Redis Pub/Sub으로 Django 변경사항 수신
"""

import asyncio
import json
from typing import Optional
from datetime import datetime

import redis.asyncio as aioredis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np

from config import settings
from database import async_session


CHANNEL = "hidden_gem:game_updates"


class RedisPubSubHandler:
    """Redis Pub/Sub 기반 동기화"""
    
    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._pubsub = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Pub/Sub 구독 시작"""
        try:
            self._redis = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            self._pubsub = self._redis.pubsub()
            await self._pubsub.subscribe(CHANNEL)
            
            self._running = True
            self._task = asyncio.create_task(self._listen())
            
            print(f"🔔 [Sync] Redis Pub/Sub 구독 시작: {CHANNEL}")
        except Exception as e:
            print(f"⚠️ [Sync] Redis 연결 실패: {e}")
            self._running = False
    
    async def stop(self) -> None:
        """Pub/Sub 구독 종료"""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        if self._pubsub:
            await self._pubsub.unsubscribe(CHANNEL)
            await self._pubsub.close()
        
        if self._redis:
            await self._redis.close()
        
        print("⚪ [Sync] Redis Pub/Sub 구독 종료")
    
    async def _listen(self) -> None:
        """메시지 수신 루프"""
        while self._running:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0
                )
                
                if message and message.get("type") == "message":
                    data = json.loads(message["data"])
                    await self._handle_event(data)
            
            except asyncio.CancelledError:
                break
            except json.JSONDecodeError as e:
                print(f"⚠️ [Sync] JSON 파싱 오류: {e}")
            except Exception as e:
                print(f"❌ [Sync] 메시지 처리 오류: {e}")
                await asyncio.sleep(1)
    
    async def _handle_event(self, data: dict) -> None:
        """이벤트 처리"""
        event = data.get("event")
        app_id = data.get("app_id")
        
        print(f"📨 [Sync] 이벤트 수신: {event} (app_id={app_id})")
        
        if event in ["game_created", "game_updated"]:
            # 게임 생성/수정 → 필요시 캐시 무효화
            await self._invalidate_cache_for_game(app_id)
        
        elif event in ["metric_created", "metric_updated"]:
            # 지표 수정 → 벡터 재계산
            if data.get("requires_embedding_refresh"):
                await self._refresh_embedding(app_id)
        
        elif event == "game_deleted":
            # 게임 삭제 → 캐시 정리
            await self._invalidate_cache_for_game(app_id)
    
    async def _invalidate_cache_for_game(self, app_id: int) -> None:
        """게임 관련 캐시 무효화"""
        # 향후 구현: Semantic Cache에서 관련 항목 삭제
        print(f"🗑️ [Sync] 캐시 무효화: app_id={app_id}")
    
    async def _refresh_embedding(self, app_id: int) -> None:
        """게임 임베딩 재계산"""
        from models.game import Game, GameMetric
        
        try:
            async with async_session() as db:
                # 게임 및 지표 조회
                result = await db.execute(
                    select(GameMetric)
                    .join(Game)
                    .where(Game.app_id == app_id)
                )
                metric = result.scalar_one_or_none()
                
                if metric:
                    # pure_embedding 재계산
                    vector = np.array(metric.to_vector(), dtype=np.float32)
                    norm = np.linalg.norm(vector)
                    if norm > 0:
                        vector = vector / norm
                    
                    metric.pure_embedding = vector.tolist()
                    await db.commit()
                    
                    print(f"✅ [Sync] 임베딩 갱신 완료: app_id={app_id}")
                else:
                    print(f"⚠️ [Sync] 게임 없음: app_id={app_id}")
        except Exception as e:
            print(f"❌ [Sync] 임베딩 갱신 실패: {e}")


# 싱글톤
sync_handler = RedisPubSubHandler()


async def start_sync() -> None:
    """동기화 시작"""
    if not settings.DEBUG:
        await sync_handler.start()
    else:
        print("⚪ [Sync] DEBUG 모드 - Pub/Sub 비활성화 (필요시 수동 활성화)")


async def stop_sync() -> None:
    """동기화 종료"""
    await sync_handler.stop()
