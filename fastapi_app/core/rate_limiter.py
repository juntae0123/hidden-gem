# fastapi_app/core/rate_limiter.py
"""
Hidden Gem - Rate Limiter
Token Bucket 알고리즘
"""

import time
from typing import Dict, Tuple
from dataclasses import dataclass, field
from threading import Lock
from fastapi import Request

from config import settings


@dataclass
class TokenBucket:
    """토큰 버킷"""
    tokens: float
    last_update: float
    capacity: int
    refill_rate: float  # tokens per second


class RateLimiter:
    """Thread-safe Rate Limiter"""
    
    def __init__(
        self,
        capacity: int = 60,
        refill_rate: float = 1.0,
        burst: int = 10,
    ):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.burst = burst
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = Lock()
    
    def check(self, request: Request) -> Tuple[bool, int]:
        """
        요청 허용 여부 확인
        
        Returns:
            (allowed, retry_after_seconds)
        """
        client_ip = self._get_client_ip(request)
        
        with self._lock:
            bucket = self._get_or_create_bucket(client_ip)
            self._refill(bucket)
            
            if bucket.tokens >= 1:
                bucket.tokens -= 1
                return True, 0
            else:
                retry_after = int((1 - bucket.tokens) / self.refill_rate) + 1
                return False, retry_after
    
    def _get_client_ip(self, request: Request) -> str:
        """클라이언트 IP 추출"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    def _get_or_create_bucket(self, key: str) -> TokenBucket:
        """버킷 가져오기/생성"""
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(
                tokens=float(self.capacity),
                last_update=time.time(),
                capacity=self.capacity,
                refill_rate=self.refill_rate,
            )
        return self._buckets[key]
    
    def _refill(self, bucket: TokenBucket) -> None:
        """토큰 리필"""
        now = time.time()
        elapsed = now - bucket.last_update
        
        new_tokens = elapsed * bucket.refill_rate
        bucket.tokens = min(bucket.capacity, bucket.tokens + new_tokens)
        bucket.last_update = now


# 싱글톤
rate_limit_middleware = RateLimiter(
    capacity=getattr(settings, 'RATE_LIMIT_PER_MINUTE', 60),
    refill_rate=1.0,
)
