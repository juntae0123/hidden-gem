# fastapi_app/services/sync_service.py
"""
Hidden Gem - 데이터 동기화 서비스
환경에 따라 Redis Pub/Sub 또는 Polling 선택
"""

import asyncio
import json
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod

from config import settings


class SyncMode(str, Enum):
    REDIS_PUBSUB = "redis_pubsub"
    POLLING = "polling"
    DISABLED = "disabled"


class SyncHandler(ABC):
    @abstractmethod
    async def start(self) -> None:
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        pass


class DisabledHandler(SyncHandler):
    async def start(self) -> None:
        print("⚪ [Sync] 동기화 비활성화됨")
    
    async def stop(self) -> None:
        pass


class SyncManager:
    def __init__(self):
        self._handler: Optional[SyncHandler] = None
        self._mode: SyncMode = SyncMode.DISABLED
    
    @property
    def mode(self) -> SyncMode:
        return self._mode
    
    @property
    def is_running(self) -> bool:
        return self._handler is not None
    
    async def start(self, mode: Optional[SyncMode] = None) -> None:
        if mode is None:
            mode = SyncMode.POLLING if settings.DEBUG else SyncMode.DISABLED
        
        self._mode = mode
        self._handler = DisabledHandler()
        await self._handler.start()
        print(f"🔄 [Sync] 모드: {mode.value}")
    
    async def stop(self) -> None:
        if self._handler:
            await self._handler.stop()


sync_manager = SyncManager()


async def start_sync() -> None:
    await sync_manager.start()


async def stop_sync() -> None:
    await sync_manager.stop()
