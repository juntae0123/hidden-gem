"""
IP 단위 고정 창(fixed window) 레이트 리밋 — FastAPI 의존성으로 붙인다.

왜 slowapi 데코레이터를 쓰지 않는가 (2026-09-07):
    slowapi 의 `@limiter.limit` 은 엔드포인트 시그니처에 **`request` 라는 이름의 starlette Request**
    를 요구한다. 그런데 games.py 의 엔드포인트들은 `request` 를 **본문(pydantic) 파라미터 이름**으로
    이미 쓰고 있어 데코레이터를 붙이면 깨진다. 의존성은 자기 시그니처를 따로 가지므로 충돌이 없다.

왜 만들었나:
    `settings.RATE_LIMIT_*` 는 정의돼 있고 테스트도 "설정이 존재하고 값이 합리적인가"를 검사했지만,
    **어떤 엔드포인트에도 적용돼 있지 않았다**(taste.py 만 예외). LLM·임베딩을 호출하는
    `/games/search/semantic` 이 무제한이라, 서로 다른 질의를 반복하면 qa 캐시를 우회해
    호출당 비용이 그대로 발생한다. 비용 가드(일 $50/시 $5)는 피해 상한이지 예방이 아니다.

Redis 장애 시 정책: **통과시킨다(fail open)**. 이유는 비용 상한이 cost_guard 로 이미 이중으로 걸려 있고,
    Redis 가 죽었을 때 검색 전체를 막으면 장애가 더 커지기 때문. `/ops/*` 처럼 파괴적 작업이 아니다.
"""

import logging
import time
from typing import Callable

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

_PERIODS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}


def _parse(spec: str) -> tuple[int, int]:
    """'10/minute' → (10, 60). 형식이 깨지면 보수적으로 (10, 60)."""
    try:
        n, period = spec.split("/", 1)
        return int(n), _PERIODS[period.strip().lower().rstrip("s")]
    except Exception:
        logger.warning(f"[RateLimit] 형식 오류 '{spec}' → 10/minute 로 대체")
        return 10, 60


def rate_limit(scope: str, spec_getter: Callable[[], str]):
    """의존성 팩토리. `dependencies=[Depends(rate_limit('semantic', lambda: settings.X))]` 로 사용."""

    async def _dep(req: Request) -> None:
        limit, window = _parse(spec_getter())
        ip = (req.client.host if req.client else "unknown")
        bucket = int(time.time()) // window
        key = f"rl:{scope}:{ip}:{bucket}"
        try:
            from services.cache import recommendation_cache

            r = await recommendation_cache._get_redis()
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, window + 1)
        except Exception as exc:                      # Redis 장애 → 통과 (위 주석의 근거)
            logger.warning(f"[RateLimit] 카운터 실패({scope}) — 통과시킴: {exc}")
            return
        if count > limit:
            raise HTTPException(
                status_code=429,
                detail=f"요청이 너무 많습니다. 잠시 후 다시 시도해 주세요 ({limit}/{window}s)",
                headers={"Retry-After": str(window - int(time.time()) % window)},
            )

    return _dep
