# django_core/apps/users/models.py
"""
Hidden Gem - Django 유저 모델 + UserAction 행동 로그

v1 → v2 변경사항:
    - UserAction 모델 추가 (Phase 1.5 데이터 수집 인프라)
    - 행동 로그 수집만, 취향 학습 로직은 Phase 2+
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """커스텀 유저 모델"""

    # Steam 연동
    steam_id = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Steam ID"
    )

    # 닉네임 (Steam에서 가져오거나 직접 설정)
    nickname = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="닉네임"
    )

    # 취향 DNA (FastAPI에서 관리, Django에서는 조회만)
    taste_dna_json = models.JSONField(
        null=True,
        blank=True,
        verbose_name="취향 DNA (JSON)"
    )

    # 통계
    total_searches = models.IntegerField(default=0, verbose_name="총 검색 수")
    total_clicks = models.IntegerField(default=0, verbose_name="총 클릭 수")
    total_ratings = models.IntegerField(default=0, verbose_name="총 평가 수")

    # 활동
    last_active_at = models.DateTimeField(null=True, blank=True, verbose_name="마지막 활동")

    class Meta:
        db_table = 'users'
        verbose_name = '유저'
        verbose_name_plural = '유저들'

    def __str__(self):
        return self.nickname or self.username or f"User {self.id}"


class UserAction(models.Model):
    """
    User behavior log for taste learning (Phase 1.5 — data collection only).
    Korean: 취향 학습용 사용자 행동 로그. Phase 1.5는 수집만, 학습 로직은 Phase 2+.

    설계 원칙:
        - 비로그인 유저도 session_id로 추적 가능
        - context JSONB에 모든 컨텍스트 저장 → 나중에 어떤 분석이든 가능
        - 가중치 숫자 지금 정하지 않음 (데이터 1만 건 후 실증적으로 도출)
    """

    class ActionType(models.TextChoices):
        SEARCH               = "search",       "검색어 입력"
        DETAIL_VIEW          = "detail_view",  "게임 상세 조회"
        RECOMMENDATION_CLICK = "rec_click",    "추천 결과 클릭"
        SEARCH_CLICK         = "search_click", "검색 결과 클릭"
        STEAM_CLICK          = "steam_click",  "Steam으로 이동"
        LIKE                 = "like",         "좋아요"
        NEGATIVE_FEEDBACK    = "neg_feedback", "취향 안 맞음 피드백"
        REVISIT              = "revisit",      "재방문 (같은 게임)"

    # 사용자 (비로그인이면 null)
    user = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="actions",
        db_index=True,
        verbose_name="유저",
    )

    # 비로그인 추적용 세션 ID
    session_id = models.CharField(
        max_length=64,
        db_index=True,
        verbose_name="세션 ID",
    )

    # 대상 게임 (검색 행동이면 null)
    app_id = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Steam App ID",
    )

    # 행동 종류
    action_type = models.CharField(
        max_length=30,
        choices=ActionType.choices,
        db_index=True,
        verbose_name="행동 종류",
    )

    # 컨텍스트 (분석용 — 지금 뭘 쓸지 몰라도 다 저장)
    # 예시:
    # {
    #   "search_query": "힐링 게임",
    #   "click_position": 3,          # 화면에서 몇 번째 위치
    #   "time_to_click_ms": 1500,     # 화면 진입 후 클릭까지 시간
    #   "displayed_score": 82.5,      # 클릭 시점 화면의 매치 점수
    #   "referrer": "/search",        # 어디서 왔나
    #   "session_game_views": 4,      # 이 세션에서 몇 번째 게임 조회
    # }
    context = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="컨텍스트",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="발생 시각",
    )

    class Meta:
        db_table = "user_actions"
        verbose_name = "유저 행동"
        verbose_name_plural = "유저 행동 목록"
        ordering = ["-created_at"]
        indexes = [
            # 유저별 시간순 (취향 계산용)
            models.Index(fields=["user", "-created_at"], name="idx_ua_user_time"),
            # 게임별 행동 집계 (인기도 분석용)
            models.Index(fields=["app_id", "action_type"], name="idx_ua_app_action"),
            # 세션별 행동 (비로그인 추적용)
            models.Index(fields=["session_id", "-created_at"], name="idx_ua_session_time"),
        ]

    def __str__(self):
        return f"UserAction({self.action_type}, app_id={self.app_id}, user={self.user_id})"