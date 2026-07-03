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
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenBlacklistView,
)
from apps.users.views import (
    UserMeView, OnboardingView, RecentGamesView,
    PendingSurveyView, SubmitSurveyView,
    FavoriteToggleView, FavoriteListView,
    TastePreferenceView, DeleteAccountView,
)

urlpatterns = [
    path('admin/', admin.site.urls),

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
]
