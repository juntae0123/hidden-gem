# fastapi_app/services/cache_service.py
"""
Hidden Gem - Semantic Cache
OpenAI Embedding + Redis를 활용한 의미 기반 캐싱

핵심:
- 동일한 검색어 → 정확 매칭
- 유사한 검색어 → 임베딩 유사도로 캐시 히트
- 비용 절감 + 응답 속도 향상
"""

import json
import hashlib
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import asyncio

import redis.asyncio as redis
from openai import AsyncOpenAI

from config import settings


class SemanticCache:
    """
    Semantic Cache
    
    구조:
    - 정확 매칭: hash(query) → cached_result
    - 의미 매칭: query_embedding → 유사 쿼리 검색 → cached_result
    
    Redis 키 구조:
    - hg:cache:exact:{hash}     → JSON result
    - hg:cache:embed:{hash}     → embedding vector
    - hg:cache:meta:{hash}      → metadata (ttl, hits, etc.)
    """
    
    PREFIX = "hg:cache"
    
    def __init__(
        self,
        redis_url: str,
        openai_api_key: str,
        embedding_model: str = "text-embedding-3-small",
        embedding_dims: int = 512,
        similarity_threshold: float = 0.92,
        ttl_seconds: int = 3600,
    ):
        self.redis_url = redis_url
        self.openai = AsyncOpenAI(api_key=openai_api_key)
        self.embedding_model = embedding_model
        self.embedding_dims = embedding_dims
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds
        
        self._redis: Optional[redis.Redis] = None
        self._embedding_cache: Dict[str, np.ndarray] = {}  # 로컬 메모리 캐시
    
    async def get_redis(self) -> redis.Redis:
        """Redis 연결 (lazy)"""
        if self._redis is None:
            self._redis = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis
    
    async def get(self, query: str) -> Optional[Dict[str, Any]]:
        """
        캐시 조회
        
        1. 정확 매칭 시도
        2. Semantic 매칭 시도
        
        Returns:
            캐시된 결과 또는 None
        """
        
        r = await self.get_redis()
        query_hash = self._hash(query)
        
        # 1. 정확 매칭
        exact_key = f"{self.PREFIX}:exact:{query_hash}"
        cached = await r.get(exact_key)
        
        if cached:
            # 히트 카운트 증가
            await r.hincrby(f"{self.PREFIX}:meta:{query_hash}", "hits", 1)
            return json.loads(cached)
        
        # 2. Semantic 매칭
        query_embedding = await self._get_embedding(query)
        
        similar = await self._find_similar(query_embedding)
        if similar:
            similar_hash, similarity = similar
            
            # 유사 쿼리의 캐시 반환
            similar_cached = await r.get(f"{self.PREFIX}:exact:{similar_hash}")
            if similar_cached:
                result = json.loads(similar_cached)
                result["_cache_meta"] = {
                    "type": "semantic",
                    "similarity": similarity,
                    "original_hash": similar_hash,
                }
                return result
        
        return None
    
    async def set(
        self,
        query: str,
        result: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> None:
        """
        캐시 저장
        
        - 정확 매칭 키
        - 임베딩 벡터
        - 메타데이터
        """
        
        r = await self.get_redis()
        query_hash = self._hash(query)
        ttl = ttl or self.ttl_seconds
        
        # 1. 결과 저장
        exact_key = f"{self.PREFIX}:exact:{query_hash}"
        await r.setex(exact_key, ttl, json.dumps(result))
        
        # 2. 임베딩 저장
        embedding = await self._get_embedding(query)
        embed_key = f"{self.PREFIX}:embed:{query_hash}"
        await r.setex(embed_key, ttl, json.dumps(embedding.tolist()))
        
        # 3. 메타데이터 저장
        meta_key = f"{self.PREFIX}:meta:{query_hash}"
        await r.hset(meta_key, mapping={
            "query": query,
            "created_at": datetime.utcnow().isoformat(),
            "hits": 0,
        })
        await r.expire(meta_key, ttl)
        
        # 4. 인덱스에 추가 (semantic 검색용)
        await r.sadd(f"{self.PREFIX}:index", query_hash)
    
    async def invalidate(self, query: str) -> None:
        """캐시 무효화"""
        r = await self.get_redis()
        query_hash = self._hash(query)
        
        await r.delete(
            f"{self.PREFIX}:exact:{query_hash}",
            f"{self.PREFIX}:embed:{query_hash}",
            f"{self.PREFIX}:meta:{query_hash}",
        )
        await r.srem(f"{self.PREFIX}:index", query_hash)
    
    async def _get_embedding(self, text: str) -> np.ndarray:
        """임베딩 생성 (캐시 활용)"""
        
        text_hash = self._hash(text)
        
        # 로컬 캐시 확인
        if text_hash in self._embedding_cache:
            return self._embedding_cache[text_hash]
        
        # OpenAI API 호출
        response = await self.openai.embeddings.create(
            model=self.embedding_model,
            input=text,
            dimensions=self.embedding_dims,
        )
        
        embedding = np.array(response.data[0].embedding, dtype=np.float32)
        
        # 정규화
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        # 로컬 캐시 저장
        self._embedding_cache[text_hash] = embedding
        
        # 캐시 크기 제한
        if len(self._embedding_cache) > 1000:
            # 가장 오래된 것 제거 (간단한 FIFO)
            oldest = next(iter(self._embedding_cache))
            del self._embedding_cache[oldest]
        
        return embedding
    
    async def _find_similar(
        self,
        query_embedding: np.ndarray,
    ) -> Optional[Tuple[str, float]]:
        """
        유사한 캐시된 쿼리 찾기
        
        Returns:
            (hash, similarity) 또는 None
        """
        
        r = await self.get_redis()
        
        # 인덱스에서 모든 캐시된 쿼리 해시 가져오기
        cached_hashes = await r.smembers(f"{self.PREFIX}:index")
        
        if not cached_hashes:
            return None
        
        best_match = None
        best_similarity = 0.0
        
        # 각 캐시된 임베딩과 비교
        for cache_hash in cached_hashes:
            embed_key = f"{self.PREFIX}:embed:{cache_hash}"
            cached_embed_str = await r.get(embed_key)
            
            if not cached_embed_str:
                continue
            
            cached_embed = np.array(json.loads(cached_embed_str), dtype=np.float32)
            
            # 코사인 유사도 (정규화된 벡터이므로 내적)
            similarity = float(np.dot(query_embedding, cached_embed))
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = cache_hash
        
        if best_match and best_similarity >= self.similarity_threshold:
            return (best_match, best_similarity)
        
        return None
    
    def _hash(self, text: str) -> str:
        """텍스트 해시"""
        return hashlib.sha256(text.lower().strip().encode()).hexdigest()[:16]
    
    async def get_stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        r = await self.get_redis()
        
        index_size = await r.scard(f"{self.PREFIX}:index")
        
        return {
            "total_cached_queries": index_size,
            "local_embedding_cache_size": len(self._embedding_cache),
        }
    
    async def close(self) -> None:
        """연결 종료"""
        if self._redis:
            await self._redis.close()


# 싱글톤 인스턴스
_cache_instance: Optional[SemanticCache] = None


async def get_semantic_cache() -> SemanticCache:
    """SemanticCache 싱글톤"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SemanticCache(
            redis_url=settings.REDIS_URL,
            openai_api_key=settings.OPENAI_API_KEY,
            embedding_model=settings.EMBEDDING_MODEL,
            embedding_dims=settings.EMBEDDING_DIMENSIONS,
            similarity_threshold=settings.CACHE_SIMILARITY_THRESHOLD,
            ttl_seconds=settings.CACHE_TTL_SECONDS,
        )
    return _cache_instance
