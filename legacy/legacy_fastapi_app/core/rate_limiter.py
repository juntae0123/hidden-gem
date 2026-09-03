# fastapi_app/core/rate_limiter.py
"""
Hidden Gem - Rate Limiter
Token Bucket 알고리즘 기반 요청 제한

Features:
- IP 기반 제한
- Sliding Window 방식
- Thread-safe
"""

import time
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from threading import Lock

from fastapi import Request


@dataclass
class TokenBucket:
    """토큰 버킷"""
    tokens: float
    last_update: float
    capacity: int
    refill_rate: float  # tokens per second


class RateLimiter:
    """
    Thread-safe Rate Limiter
    
    Token Bucket 알고리즘:
    - 버킷에 토큰이 있으면 요청 허용
    - 시간이 지나면 토큰 자동 충전
    - 토큰 없으면 요청 거부
    """
    
    def __init__(
        self,
        capacity: int = 60,
        refill_rate: float = 1.0,
        burst: int = 10,
    ):
        """
        Args:
            capacity: 최대 토큰 수 (분당 요청 수)
            refill_rate: 초당 충전 토큰 수
            burst: 버스트 허용량 (미사용, 향후 확장용)
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.burst = burst
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = Lock()
        
        # 버킷 정리 주기 (메모리 관리)
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5분
    
    def check(self, request: Request) -> Tuple[bool, int]:
        """
        요청 허용 여부 확인
        
        Args:
            request: FastAPI Request 객체
            
        Returns:
            (allowed, retry_after_seconds)
            - allowed: 요청 허용 여부
            - retry_after_seconds: 거부 시 재시도까지 대기 시간
        """
        client_ip = self._get_client_ip(request)
        
        with self._lock:
            # 주기적 정리
            self._maybe_cleanup()
            
            bucket = self._get_or_create_bucket(client_ip)
            self._refill(bucket)
            
            if bucket.tokens >= 1:
                bucket.tokens -= 1
                return True, 0
            else:
                # 토큰 1개 충전까지 대기 시간
                retry_after = int((1 - bucket.tokens) / self.refill_rate) + 1
                return False, retry_after
    
    def _get_client_ip(self, request: Request) -> str:
        """클라이언트 IP 추출 (프록시 고려)"""
        # X-Forwarded-For 헤더 확인 (로드밸런서/프록시 뒤)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # 첫 번째 IP가 실제 클라이언트
            return forwarded.split(",")[0].strip()
        
        # X-Real-IP 헤더 확인
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        # 직접 연결
        if request.client:
            return request.client.host
        
        return "unknown"
    
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
        
        # 경과 시간에 비례하여 토큰 충전
        new_tokens = elapsed * bucket.refill_rate
        bucket.tokens = min(bucket.capacity, bucket.tokens + new_tokens)
        bucket.last_update = now
    
    def _maybe_cleanup(self) -> None:
        """오래된 버킷 정리 (메모리 관리)"""
        now = time.time()
        
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        # 1시간 이상 미사용 버킷 제거
        expired_threshold = now - 3600
        expired_keys = [
            key for key, bucket in self._buckets.items()
            if bucket.last_update < expired_threshold
        ]
        
        for key in expired_keys:
            del self._buckets[key]
        
        self._last_cleanup = now
        
        if expired_keys:
            print(f"🧹 [RateLimiter] Cleaned up {len(expired_keys)} expired buckets")
    
    def get_remaining(self, request: Request) -> int:
        """남은 토큰 수 조회"""
        client_ip = self._get_client_ip(request)
        
        with self._lock:
            bucket = self._buckets.get(client_ip)
            if bucket:
                self._refill(bucket)
                return int(bucket.tokens)
            return self.capacity
    
    def reset(self, request: Request) -> None:
        """특정 클라이언트 버킷 리셋 (관리용)"""
        client_ip = self._get_client_ip(request)
        
        with self._lock:
            if client_ip in self._buckets:
                del self._buckets[client_ip]


# ============================================================
# 싱글톤 인스턴스
# ============================================================

# 기본 설정으로 생성 (분당 60회, 초당 1토큰 충전)
rate_limit_middleware = RateLimiter(
    capacity=60,
    refill_rate=1.0,
)
