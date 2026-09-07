# django_core/config/urls.py
"""
URL 라우팅 — allauth 표준 흐름.

v5 → v6 정석:
    - GoogleCallbackView 완전 제거 (name 충돌 + 불필요)
    - allauth가 /accounts/google/login/callback/ 자동 처리
    - JWT는 JWTSocialAccountAdapter.get_login_redirect_url에서 발급
"""
from django.contrib import admin
from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenBlacklistView,
)
from apps.users.dashboard import dashboard as ops_dashboard
from apps.users.views import (
    UserMeView, OnboardingView, RecentGamesView,
    PendingSurveyView, SubmitSurveyView,
    FavoriteToggleView, FavoriteListView,
    TastePreferenceView, DeleteAccountView, SteamLibraryView,
    SafeSteamCallbackView,
)

urlpatterns = [
    # 운영 대시보드 — admin.site.urls 보다 먼저 (staff 로그인 필요)
    path('admin/dashboard/', ops_dashboard, name='ops_dashboard'),
    path('admin/', admin.site.urls),

    # 스팀 콜백만 우리 뷰로 가로챈다 — allauth include 보다 **먼저** 놓아야 이긴다.
    # (Steam API 실패 시 500 대신 로그인 화면으로: SafeSteamCallbackView 주석 참고)
    # URL 문자열은 allauth 의 'steam_callback' 과 동일하므로 return_to 검증에 영향 없음.
    path('accounts/steam/callback/', csrf_exempt(SafeSteamCallbackView.as_view())),

    # Google OAuth (allauth 표준)
    # /accounts/google/login/           - 로그인 시작
    # /accounts/google/login/callback/  - Google 콜백 (redirect_uri, 자동)
    path('accounts/', include('allauth.urls')),

    # JWT 관리
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/logout/', TokenBlacklistView.as_view(), name='token_blacklist'),

    # 유저 정보
    path('api/auth/me/', UserMeView.as_view(), name='user_me'),
    path('api/auth/onboarding/', OnboardingView.as_view(), name='onboarding'),
    path('api/auth/recent-games/', RecentGamesView.as_view(), name='recent_games'),
    path('api/auth/pending-survey/', PendingSurveyView.as_view(), name='pending_survey'),
    path('api/auth/submit-survey/', SubmitSurveyView.as_view(), name='submit_survey'),
    path('api/auth/favorite/toggle/', FavoriteToggleView.as_view(), name='favorite_toggle'),
    path('api/auth/favorites/', FavoriteListView.as_view(), name='favorite_list'),
    path('api/auth/taste-preference/', TastePreferenceView.as_view(), name='taste_preference'),
    path('api/auth/delete-account/', DeleteAccountView.as_view(), name='delete_account'),
    path('api/auth/steam-library/', SteamLibraryView.as_view(), name='steam_library'),
]
