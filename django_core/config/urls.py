# django_core/config/urls.py
"""
URL 라우팅 설정 (URL Routing Configuration)

v1 → v2: Google OAuth2 + JWT 인증 URL 추가
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from apps.users.views import GoogleLoginCallbackView, UserMeView

urlpatterns = [
    path('admin/', admin.site.urls),

    # ==================== 인증 / Auth ====================
    # Google OAuth2 (allauth)
    path('accounts/', include('allauth.urls')),

    # JWT 토큰 갱신
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Google 로그인 콜백 → JWT 발급 후 프론트로 리다이렉트
    path('api/auth/google/callback/', GoogleLoginCallbackView.as_view(), name='google_callback'),

    # 현재 유저 정보 조회 (프론트에서 로그인 상태 확인용)
    path('api/auth/me/', UserMeView.as_view(), name='user_me'),
]