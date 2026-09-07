"""
운영 엔드포인트 — /ops/cost, /ops/cache, /ops/cache/invalidate

2026-09-07: main.py 에서 분리. 이유 둘.
  ① 이 세 경로는 인증이 전혀 없었고(공개 저장소라 경로는 누구나 안다) POST 한 번으로 운영 캐시를
     통째로 비울 수 있었다 → 토큰 게이트. 토큰 미설정 시 운영에서는 503 으로 **막는다(fail closed)**.
  ② `main` 을 import 하지 않고도 게이트가 붙었는지 테스트하려면 라우터가 독립 모듈이어야 한다
     (호스트 venv 엔 sentry_sdk 가, 컨테이너엔 pytest 가 없어 main 은 어디서도 테스트로 import 되지 않았다).

호출: 헤더 `X-Ops-Token: <settings.OPS_TOKEN>`. rec_snapshot 등 도구는 OPS_TOKEN 환경변수로 보낸다.
"""

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException

from config import settings

router = APIRouter(prefix="/ops", tags=["Ops"])


async def require_ops_token(x_ops_token: str | None = Header(default=None)) -> None:
    """운영 엔드포인트 게이트. 토큰 미설정이면 운영에서는 막고, 로컬(DEBUG)만 통과."""
    expected = (settings.OPS_TOKEN or "").strip()
    if not expected:
        if settings.DEBUG:
            return
        raise HTTPException(status_code=503, detail="OPS_TOKEN 미설정 — 운영 엔드포인트 비활성")
    if not x_ops_token or not secrets.compare_digest(x_ops_token, expected):
        raise HTTPException(status_code=401, detail="유효한 X-Ops-Token 필요")


@router.get("/cost", dependencies=[Depends(require_ops_token)])
async def get_cost_stats():
    """OpenAI 비용 현황 조회"""
    from services.cost_guard import cost_guard
    return await cost_guard.get_stats()


@router.get("/cache", dependencies=[Depends(require_ops_token)])
async def get_cache_stats():
    """Redis 캐시 현황 조회"""
    from services.cache import recommendation_cache
    return await recommendation_cache.get_stats()


@router.post("/cache/invalidate", dependencies=[Depends(require_ops_token)])
async def invalidate_cache():
    """전체 캐시 초기화"""
    from services.cache import recommendation_cache
    deleted = await recommendation_cache.invalidate_all()
    return {"deleted_keys": deleted, "message": f"{deleted}개 캐시 삭제 완료"}
