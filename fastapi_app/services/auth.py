"""
JWT authentication helper for FastAPI.
Korean: Django SimpleJWT 토큰을 검증해 user_id를 추출하는 헬퍼.

Django와 동일한 SECRET_KEY + HS256으로 access token을 검증.
선택적 인증: 토큰 없거나 검증 실패 시 None 반환 (비로그인 허용 — 익명 수집 유지).
"""
import logging
from typing import Optional

import jwt
from fastapi import Request

from config import settings

logger = logging.getLogger(__name__)


def get_optional_user_id(request: Request) -> Optional[int]:
    """
    Extract user_id from JWT if present and valid, else None.
    Korean: Authorization 헤더의 JWT를 검증해 user_id 반환.
            토큰 없음/만료/위조 시 None (비로그인 허용).
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:].strip()
    if not token:
        return None

    try:
        payload = jwt.decode(
            token,
            settings.DJANGO_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        # SimpleJWT access token은 user_id 클레임을 가짐
        user_id = payload.get("user_id")
        if user_id is None:
            return None
        return int(user_id)
    except jwt.ExpiredSignatureError:
        # 만료 토큰 → 익명 처리 (프론트가 갱신 후 재시도)
        return None
    except jwt.InvalidTokenError:
        # 위조/형식 오류 → 익명 처리
        return None
    except (ValueError, TypeError):
        return None