# django_core/apps/users/views.py
"""
Hidden Gem 유저 인증 뷰 (User Auth Views)

v3 → v4 변경사항:
    - GoogleLoginCallbackView 제거 (name 충돌 + 죽은 코드)
    - allauth 표준 흐름 사용
    - JWT 발급은 다음 단계에서 JWTSocialAccountAdapter로 처리

현재 흐름 (Phase 1.6-A):
    1. 프론트 → /accounts/google/login/ (allauth)
    2. Google 인증 → /accounts/google/login/callback/ (allauth 표준 콜백)
    3. allauth가 user 자동 생성/로그인
    4. LOGIN_REDIRECT_URL='/' 로 리다이렉트 (JWT는 다음 단계)

다음 단계 (Phase 1.6-B):
    - JWTSocialAccountAdapter 추가
    - 로그인 후 JWT 발급 + FRONTEND_URL/auth/callback으로 리다이렉트
"""

import logging
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.users.serializers import UserSerializer

logger = logging.getLogger(__name__)
User = get_user_model()


class UserMeView(APIView):
    """
    Get current user info — requires JWT authentication.
    Korean: 현재 로그인 유저 정보 조회 — JWT 인증 필요.

    프론트에서 로그인 상태 확인 + 유저 정보 표시.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
