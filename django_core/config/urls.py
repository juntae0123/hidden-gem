# django_core/config/urls.py
"""
URL 라우팅 설정 (URL Routing Configuration)

v3 → v4: name 충돌 해결
    - GoogleLoginCallbackView 라우트 제거
    - allauth.urls의 'google_callback' name과 충돌하던 문제 해결
    - allauth 표준 흐름 사용

allauth 표준 콜백: /accounts/google/login/callback/
    → 이 URL이 Google에 redirect_uri로 전송됨
    → Google Cloud Console에 등록 필요
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenBlacklistView,
)
from apps.users.views import UserMeView

urlpatterns = [
    path('admin/', admin.site.urls),

    # ==================== 인증 / Auth ====================
    # Google OAuth (allauth 표준 흐름)
    # 자동 라우트:
    #   /accounts/google/login/           - 로그인 시작
    #   /accounts/google/login/callback/  - Google 콜백 (redirect_uri)
    path('accounts/', include('allauth.urls')),

    # JWT 토큰 관리
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/logout/', TokenBlacklistView.as_view(), name='token_blacklist'),

    # 현재 유저 정보 (프론트에서 로그인 상태 확인)
    path('api/auth/me/', UserMeView.as_view(), name='user_me'),
]
