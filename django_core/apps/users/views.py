# django_core/apps/users/views.py
"""
Hidden Gem 유저 인증 뷰 (User Auth Views)

Google OAuth2 → JWT 발급 → 프론트로 리다이렉트 흐름.

흐름:
    1. 프론트 → /accounts/google/login/ (allauth 처리)
    2. Google 인증 완료 → /api/auth/google/callback/ 리다이렉트
    3. 이 뷰에서 JWT 발급 → 프론트 /auth/callback?token=...으로 리다이렉트
    4. 프론트에서 토큰 저장 + 로그인 상태 설정
"""

import logging
from django.conf import settings
from django.shortcuts import redirect
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from apps.users.serializers import UserSerializer

logger = logging.getLogger(__name__)
User = get_user_model()


def get_jwt_for_user(user) -> dict:
    """
    Generate JWT access + refresh tokens for a user.
    Korean: 유저에 대한 JWT 액세스 + 리프레시 토큰 생성.
    """
    refresh = RefreshToken.for_user(user)
    return {
        'access':  str(refresh.access_token),
        'refresh': str(refresh),
    }


class GoogleLoginCallbackView(APIView):
    """
    Google OAuth2 callback — issue JWT and redirect to frontend.
    Korean: Google 인증 완료 후 JWT 발급 → 프론트로 리다이렉트.

    allauth가 Google 인증을 처리한 후 이 뷰로 리다이렉트됨.
    로그인된 유저에게 JWT를 발급하고 프론트로 전달.
    """
    authentication_classes = []
    permission_classes     = []

    def get(self, request):
        user = request.user

        if not user.is_authenticated:
            # 인증 실패 → 프론트 로그인 페이지로
            logger.warning("GoogleLoginCallback: 인증되지 않은 접근")
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
            return redirect(f"{frontend_url}/login?error=auth_failed")

        # JWT 발급
        tokens = get_jwt_for_user(user)

        # 닉네임 없으면 Google 이름으로 설정
        if not user.nickname:
            user.nickname = (
                user.first_name or
                user.email.split('@')[0] or
                f"User{user.id}"
            )
            user.save(update_fields=['nickname'])

        logger.info(f"Google 로그인 성공: {user.email}")

        # 프론트 /auth/callback으로 토큰 전달
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        return redirect(
            f"{frontend_url}/auth/callback"
            f"?access={tokens['access']}"
            f"&refresh={tokens['refresh']}"
        )


class UserMeView(APIView):
    """
    Get current user info — requires JWT authentication.
    Korean: 현재 로그인 유저 정보 조회 — JWT 인증 필요.

    프론트에서 로그인 상태 확인 및 유저 정보 표시에 사용.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)