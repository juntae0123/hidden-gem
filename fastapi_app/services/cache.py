"""
Redis Cache Layer for Search and Recommendation Results
Redis 캐시 레이어 - 검색/추천 결과 캐싱

캐시 키 전략:
    semantic:{VER}:{hash(query,min_gem)}:{limit}      : 시맨틱 검색 결과
    rec:game:{VER}:{app_id}:{count}:{a|x}          : 게임 기반 추천 (x = 같은 개발사 제외)
    rec:pref:{VER}:{hash(pref,must_not,masking,max_reviews,tags,min_gem)}:{count}

v4 변경:
    by_preference_key()에 must_not, use_masking 인자 추가.
    must_not + use_masking을 해시에 포함해 조건이 다르면 다른 캐시 키 생성.

캐시 무효화:
    daily_update 실행 시 invalidate_all() 호출로 전체 초기화.
"""

import hashlib
import json
import logging
import re
from typing import Any, List, Optional

# 점수 로직을 바꾸면 이 값을 올린다. 키에 들어가므로 옛 결과가 살아남지 못한다.
# (2026-09-04 스냅샷 캐시 오염 사고: 키에 로직 버전이 없어 변경 전 결과가 그대로 돌아왔다)
CACHE_VERSION = "v7a"


def _key_version() -> str:
    """캐시 키에 들어가는 버전 조각: CACHE_VERSION + 결과를 바꾸는 운영 플래그 전부.
    SCORE_VERSION(v6/v7)·GEM_SOURCE(legacy/evidence) 만 바꾸고 캐시를 안 비워도 옛 결과가 살아남지 않게 (E-6 확장, 2026-09-05).
    세 경로(semantic / by_game / by_preference) 모두 이 조각을 쓴다."""
    return f"{CACHE_VERSION}-{settings.SCORE_VERSION}-{settings.GEM_SOURCE}"

import redis.asyncio as aioredis

from config import settings

logger = logging.getLogger(__name__)


class RecommendationCache:
    """
    Search and recommendation result Redis cache (Recommendation Redis Cache).
    Korean: 검색/추천 결과 Redis 캐시. 캐시 키 생성 + GET/SET + 무효화 담당.

    캐시 키 전략:
        semantic:{query_hash}:{limit}  : 시맨틱 검색 결과
        rec:game:{app_id}:{count}      : 게임 기반 추천
        rec:pref:{pref_hash}:{count}   : 선호도 기반 추천 (v4: must_not + use_masking 해시 포함)

    캐시 무효화:
        daily_update 실행 시 invalidate_all() 호출로 전체 초기화.
    """

    def __init__(self, redis_url: str = None):
        # settings에서 Redis URL 주입 / Inject Redis URL from settings
        self._redis_url = redis_url or settings.REDIS_CONNECTION_URL
        self._redis: Optional[aioredis.Redis] = None

        # TTL settings에서 주입 / TTL from settings
        self.TTL_SEMANTIC = settings.CACHE_TTL_SEMANTIC
        self.TTL_BY_GAME = settings.CACHE_TTL_BY_GAME
        self.TTL_BY_PREFERENCE = settings.CACHE_TTL_BY_PREFERENCE

    async def _get_redis(self) -> aioredis.Redis:
        """
        Get or create singleton Redis connection (Lazy Redis Connection).
        Korean: 싱글톤 Redis 연결 반환. 최초 호출 시에만 연결 생성.
        """
        if self._redis is None:
            self._redis = await aioredis.from_url(
                self._redis_url, decode_responses=True
            )
        return self._redis

    # ==================== 키 생성 / Key Generation ====================

    @staticmethod
    def _normalize_query(query: str) -> str:
        """
        Normalize search query for consistent cache key generation.
        Korean: 검색어 정규화 — 캐시 적중률 향상.

        "힐링게임", "힐링 게임 ", "힐링GAME" → 동일 캐시 키.
        """
        normalized = query.lower().strip()
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = re.sub(r"[^\w\s가-힣]", "", normalized)
        return normalized

    @staticmethod
    def _hash(text: str) -> str:
        """
        Generate 8-character MD5 hash from string.
        Korean: 문자열 → 8자리 MD5 해시 (캐시 키 단축용).
        """
        return hashlib.md5(text.encode()).hexdigest()[:8]

    def semantic_key(self, query: str, limit: int, min_gem_potential: float = 0.0,
                     include_new: bool = False) -> str:
        """
        Generate cache key for semantic search results.
        Korean: 시맨틱 검색 결과 캐시 키 생성.
        """
        norm = self._normalize_query(query)
        payload = json.dumps({"q": norm, "min_gem": min_gem_potential, "new": include_new}, sort_keys=True)
        return f"semantic:{_key_version()}:{self._hash(payload)}:{limit}"

    def by_game_key(self, app_id: int, count: int, exclude_same_developer: bool = False,
                    include_new: bool = False) -> str:
        """
        Generate cache key for game-based recommendation results.
        Korean: 게임 기반 추천 결과 캐시 키 생성.
        """
        flag = ("x" if exclude_same_developer else "a") + ("n" if include_new else "")   # 결과를 바꾸는 조건은 전부 키에
        return f"rec:game:{_key_version()}:{app_id}:{count}:{flag}"

    def by_preference_key(
        self,
        preferences: dict,
        count: int,
        must_not: Optional[dict] = None,
        use_masking: bool = True,
        max_review_count: Optional[int] = None,
        required_tags: Optional[List[str]] = None,
        excluded_tags: Optional[List[str]] = None,
        min_gem_potential: float = 0.0,
        include_new: bool = False,
        new_only: bool = False,
    ) -> str:
        """
        Generate cache key for preference-based recommendation results (v4).
        Korean: 선호도 기반 추천 캐시 키 생성 (v4: must_not + use_masking 해시 포함).

        v4 변경: must_not, use_masking이 다르면 다른 캐시 키 생성.
        동일 preferences라도 must_not/use_masking이 다르면 결과가 달라지므로
        캐시 키에 반드시 포함해야 함.

        Args:
            preferences: 선호도 딕셔너리 {지표명: 값}
            count: 추천 수
            must_not: 제외 조건 딕셔너리 {지표명: 임계값} (기본 None = 빈 dict)
            use_masking: 동적 마스킹 활성화 여부 (기본 True)
        """
        payload = {
            "pref": dict(sorted(preferences.items())),
            "must_not": dict(sorted((must_not or {}).items())),
            "masking": use_masking,
            "max_reviews": max_review_count,
            # 결과를 바꾸는 조건 3개가 빠져 있었다 (2026-09-04 검토)
            "req_tags": sorted(required_tags or []),
            "exc_tags": sorted(excluded_tags or []),
            "min_gem": min_gem_potential,
            "new": include_new,
            "new_only": new_only,
            # 채점기 버전은 _key_version() 접두에도 들어가지만 payload 에도 남긴다 (검토 E-6, 이중 안전)
            "score_version": settings.SCORE_VERSION,
            "gem_source": settings.GEM_SOURCE,
        }
        pref_str = json.dumps(payload, sort_keys=True)
        return f"rec:pref:{_key_version()}:{self._hash(pref_str)}:{count}"

    # ==================== GET / SET ====================

    async def get(self, key: str) -> Optional[Any]:
        """
        Get cached value by key (Cache Get).
        Korean: 캐시 조회. Redis 장애 시 None 반환 (fail open).
        """
        try:
            r = await self._get_redis()
            raw = await r.get(key)
            if raw is None:
                return None
            logger.debug(f"[Cache] HIT {key}")
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"[Cache] GET 실패 ({key}): {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int) -> bool:
        """
        Store value in cache with TTL (Cache Set).
        Korean: 캐시 저장. 직렬화 실패 시 조용히 스킵.
        """
        try:
            r = await self._get_redis()
            serialized = json.dumps(value, ensure_ascii=False, default=str)
            await r.setex(key, ttl, serialized)
            logger.debug(f"[Cache] SET {key} (TTL={ttl}s)")
            return True
        except Exception as e:
            logger.warning(f"[Cache] SET 실패 ({key}): {e}")
            return False

    # ==================== 무효화 / Invalidation ====================

    async def invalidate_all(self) -> int:
        """
        Invalidate all cache entries (Full Cache Invalidation).
        Korean: 전체 캐시 초기화. daily_update.py 신작 추가 후 호출.

        Returns:
            int: 삭제된 키 수
        """
        try:
            r = await self._get_redis()
            patterns = ["semantic:*", "rec:game:*", "rec:pref:*", "rank:*"]   # rank 누락 시 리뷰 갱신 후에도 옛 순위 (검토 E-7)
            # prefemb:* / qa:* 는 의도적으로 제외 — 선호 문장 임베딩·질의 분석(LLM)은 채점 로직과 무관한 입력 변환이고,
            # 비우면 회차마다 LLM 흔들림이 측정에 섞인다. 프롬프트를 바꾸면 CACHE_VERSION 을 올려서 자연 만료시킨다.
            total_deleted = 0

            for pattern in patterns:
                keys = await r.keys(pattern)
                if keys:
                    deleted = await r.delete(*keys)
                    total_deleted += deleted
                    logger.info(f"[Cache] 패턴 {pattern} → {deleted}개 삭제")

            logger.info(f"[Cache] 전체 초기화 완료: {total_deleted}개")
            return total_deleted

        except Exception as e:
            logger.error(f"[Cache] 전체 초기화 실패: {e}")
            return 0

    async def invalidate_game(self, app_id: int):
        """
        Invalidate all cache entries for a specific game.
        Korean: 특정 게임 관련 캐시 삭제. 게임 지표 업데이트 시 호출.
        """
        try:
            r = await self._get_redis()
            keys = await r.keys(f"rec:game:*:{app_id}:*")   # 키에 CACHE_VERSION 이 들어가므로 와일드카드
            if keys:
                await r.delete(*keys)
                logger.info(f"[Cache] 게임 {app_id} 캐시 삭제: {len(keys)}개")
        except Exception as e:
            logger.warning(f"[Cache] 게임 캐시 삭제 실패: {e}")

    # ==================== 통계 / Stats ====================

    async def get_stats(self) -> dict:
        """
        Get cache statistics for operations dashboard.
        Korean: 캐시 통계 조회. 운영 대시보드 및 /ops/cache 엔드포인트용.
        """
        try:
            r = await self._get_redis()
            info = await r.info()  # 전체 info (버그 수정: "stats" 제거)

            semantic_keys = len(await r.keys("semantic:*"))
            game_keys = len(await r.keys("rec:game:*"))
            pref_keys = len(await r.keys("rec:pref:*"))
            rank_keys = len(await r.keys("rank:*"))

            hits = info.get("keyspace_hits", 0)
            misses = info.get("keyspace_misses", 0)

            return {
                "total_keys": semantic_keys + game_keys + pref_keys + rank_keys,
                "semantic_keys": semantic_keys,
                "game_keys": game_keys,
                "preference_keys": pref_keys,
                "ranking_keys": rank_keys,
                "hit_rate_pct": round(hits / max(hits + misses, 1) * 100, 2),
                "total_hits": hits,
                "total_misses": misses,
            }
        except Exception as e:
            logger.warning(f"[Cache] 통계 조회 실패: {e}")
            return {"error": str(e)}


# 싱글톤 인스턴스 / Singleton instance
recommendation_cache = RecommendationCache()