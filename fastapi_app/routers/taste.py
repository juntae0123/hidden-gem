"""
Hidden Gem Taste Action API Router (Phase 1.5)

Korean: 유저 행동 로그 수집 라우터 — 취향 학습 데이터 수집 인프라.

v1 → v2 개선:
    - Raw SQL → SQLAlchemy ORM (일관성 + 타입 안전)
    - session_id 검증 강화 (min_length 16, 영숫자만)
    - action_type → Pydantic Literal (422 자동 처리)
    - context 크기 제한 (8KB)
    - /stats 어드민 Basic Auth 보호
    - Rate Limit 적용 (60/minute)

Endpoints:
    POST /taste/action   - 유저 행동 로그 기록 (Rate Limit 60/min)
    GET  /taste/stats    - 행동 로그 통계 (Admin only)
"""

import json
from datetime import datetime, timezone
import logging
import re
import secrets
from typing import Optional, Any, Literal
from services.auth import get_optional_user_id

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models.user_action import UserAction
from services.auth import get_optional_user_id

logger = logging.getLogger(__name__)

router  = APIRouter(prefix="/taste", tags=["Taste"])
limiter = Limiter(key_func=get_remote_address)
security = HTTPBasic()


# ==================== 액션 타입 / Action Types ====================

ActionTypeLiteral = Literal[
    'search',        # 검색어 입력
    'detail_view',   # 게임 상세 조회
    'rec_click',     # 추천 결과 클릭
    'search_click',  # 검색 결과 클릭
    'steam_click',   # Steam으로 이동
    'like',          # 좋아요
    'neg_feedback',  # 취향 안 맞음
    'revisit',       # 재방문
]


# ==================== 스키마 / Schemas ====================

class TasteActionRequest(BaseModel):
    """
    User action log request schema.
    Korean: 유저 행동 로그 요청 스키마.

    Example:
        {
            "session_id": "abc123def456ghi789",
            "app_id": 1086940,
            "action_type": "rec_click",
            "context": {
                "click_position": 2,
                "displayed_score": 87.5,
                "referrer": "/"
            }
        }
    """
    session_id: str = Field(
        ..., min_length=16, max_length=64,
        description="세션 ID (16~64자, 영숫자/_/- 만)",
    )
    app_id: Optional[int] = Field(
        default=None, ge=1,
        description="대상 게임 app_id (검색 행동이면 null)",
    )
    action_type: ActionTypeLiteral = Field(
        ..., description="행동 타입",
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="행동 컨텍스트 (최대 8KB)",
    )

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        """Validate session_id format — alphanumeric + _ + - only."""
        if not re.match(r'^[a-zA-Z0-9_-]{16,64}$', v):
            raise ValueError("session_id는 영숫자/_/- 만 허용 (16~64자)")
        return v

    @field_validator("context")
    @classmethod
    def validate_context_size(cls, v: dict) -> dict:
        """Validate context size — max 8KB."""
        if v and len(json.dumps(v)) > 8192:
            raise ValueError("context 크기 초과 (max 8KB)")
        return v


class TasteActionResponse(BaseModel):
    """
    User action log response schema.
    Korean: 행동 로그 응답 스키마.
    """
    success:   bool
    action_id: Optional[int] = None
    message:   str = "기록 완료"


# ==================== 어드민 인증 / Admin Auth ====================

def verify_admin(credentials: HTTPBasicCredentials = Security(security)):
    """
    Verify admin credentials for operational endpoints.
    Korean: 운영 엔드포인트 어드민 Basic Auth 검증.
    """
    admin_user = getattr(settings, "ADMIN_USERNAME", "")
    admin_pw   = getattr(settings, "ADMIN_PASSWORD", "")

    if not admin_user or not admin_pw:
        raise HTTPException(503, "Admin credentials not configured")

    ok = (
        secrets.compare_digest(credentials.username, admin_user) and
        secrets.compare_digest(credentials.password, admin_pw)
    )
    if not ok:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )


# ==================== 엔드포인트 / Endpoints ====================

@router.post("/action", response_model=TasteActionResponse)
@limiter.limit(getattr(settings, "RATE_LIMIT_TASTE", "60/minute"))
async def record_action(
    request: Request,         # slowapi rate limit 필수
    body: TasteActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Record user behavior for taste learning (Phase 2 — user_id 연결됨).
    Korean: 취향 학습용 유저 행동 기록.
    로그인 유저면 JWT에서 user_id 추출해 함께 저장, 비로그인은 None(익명).
    Fire-and-forget: 실패해도 서비스 영향 없이 조용히 처리.
    """
    # 로그인 유저면 user_id 추출, 비로그인이면 None (익명 수집 유지)
    user_id = get_optional_user_id(request)

    try:
        action = UserAction(
            created_at=datetime.now(timezone.utc),
            user_id=user_id,                # ← Phase 2: 로그인 유저 연결
            session_id=body.session_id,
            app_id=body.app_id,
            action_type=body.action_type,
            context=body.context,  # JSONB는 dict 직접 저장
        )
        db.add(action)
        await db.commit()
        await db.refresh(action)
        logger.debug(
            f"TasteAction 기록: id={action.id} user={user_id} "
            f"type={body.action_type} app={body.app_id}"
        )
        return TasteActionResponse(success=True, action_id=action.id)
    except Exception as e:
        await db.rollback()
        logger.warning(f"TasteAction 기록 실패 (무시됨): {e}", exc_info=True)
        return TasteActionResponse(
            success=False,
            message="기록 실패 (서비스는 정상)",
        )


@router.get("/stats", dependencies=[Depends(verify_admin)])
async def get_taste_stats(db: AsyncSession = Depends(get_db)):
    """
    Taste action statistics — admin only.
    Korean: 행동 로그 통계 — 어드민 전용 (Basic Auth 필요).
    """
    try:
        stmt = (
            select(
                UserAction.action_type,
                func.count().label("count"),
                func.count(func.distinct(UserAction.session_id)).label("unique_sessions"),
                func.max(UserAction.created_at).label("last_at"),
            )
            .group_by(UserAction.action_type)
            .order_by(func.count().desc())
        )
        result = await db.execute(stmt)
        rows = result.all()

        total = await db.execute(select(func.count(UserAction.id)))

        return {
            "total_actions": total.scalar(),
            "by_type": [
                {
                    "action_type":     row.action_type,
                    "count":           row.count,
                    "unique_sessions": row.unique_sessions,
                    "last_at":         row.last_at,
                }
                for row in rows
            ],
        }
    except Exception as e:
        logger.error(f"TasteStats 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="통계 조회 실패")