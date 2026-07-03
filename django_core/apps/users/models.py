# django_core/apps/users/models.py
"""
Hidden Gem - Django 유저 모델 + UserAction 행동 로그 + 게임 설문

v1 → v2: UserAction 추가 (Phase 1.5 데이터 수집)
v2 → v3: 온보딩 필드 (gender/age_group/onboarding_completed)
v3 → v4: 게임 설문 (GameSurvey/MetricRating — 지표 검증 수집 인프라)
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

    # 온보딩 — 데이터 수집용 (성별/나이대)
    GENDER_CHOICES = [
        ('male', '남성'),
        ('female', '여성'),
        ('other', '기타'),
        ('no_answer', '응답 안 함'),
    ]
    gender = models.CharField(
        max_length=20,
        choices=GENDER_CHOICES,
        null=True,
        blank=True,
        verbose_name="성별"
    )

    AGE_GROUP_CHOICES = [
        ('10s', '10대'),
        ('20s', '20대'),
        ('30s', '30대'),
        ('40s', '40대'),
        ('50s_plus', '50대 이상'),
    ]
    age_group = models.CharField(
        max_length=20,
        choices=AGE_GROUP_CHOICES,
        null=True,
        blank=True,
        verbose_name="나이대"
    )

    # 온보딩 완료 여부 (신규 가입 → 온보딩 분기에 사용)
    onboarding_completed = models.BooleanField(
        default=False,
        verbose_name="온보딩 완료"
    )

# 취향 DNA (FastAPI에서 관리, Django에서는 조회만)
    taste_dna_json = models.JSONField(
        null=True,
        blank=True,
        verbose_name="취향 DNA (JSON)"
    )

    # 선호 장르 (취향 설정 — 복수 선택) / Preferred genres
    preferred_genres = models.JSONField(
        default=list,
        blank=True,
        verbose_name="선호 장르",
        help_text="예: ['액션', 'RPG', '전략']"
    )

    # 지표별 선호 점수 (취향 설정 — 1~5, 낮을수록 비선호) / Metric preferences
    metric_preferences = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="지표 선호도",
        help_text="예: {'cozy_factor': 5, 'horror_factor': 1}"
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


class GameSurvey(models.Model):
    """
    Game survey response — step 1 (played or not) + meta.
    Korean: 게임 설문 — 1단계(즐겼나) + 메타. 지표별 평가는 MetricRating.
    1주일 전 detail_view+steam_click 한 게임에 대해 재방문 시 수집.
    """
    user = models.ForeignKey(
        CustomUser,
        null=True,                      # 탈퇴 시 익명화 (user만 NULL, 데이터 유지)
        blank=True,
        on_delete=models.SET_NULL,      # 유저 삭제돼도 설문은 익명으로 남김
        related_name='surveys',
        verbose_name="유저",
    )
    app_id = models.IntegerField(db_index=True, verbose_name="게임 app_id")
    played = models.BooleanField(
        verbose_name="플레이 여부",
        help_text="True=해봤어요, False=안 해봤어요",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "game_surveys"
        verbose_name = "게임 설문"
        verbose_name_plural = "게임 설문 목록"
        ordering = ["-created_at"]
        # 한 유저가 같은 게임 중복 설문 방지
        constraints = [
            models.UniqueConstraint(
                fields=["user", "app_id"],
                name="uq_user_game_survey",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "app_id"], name="idx_survey_user_game"),
        ]

    def __str__(self):
        return f"GameSurvey(user={self.user_id}, app={self.app_id}, played={self.played})"


class MetricRating(models.Model):
    """
    Per-metric felt rating — step 2 (only when played=True).
    Korean: 지표별 체감 점수 — 2단계. 우리 점수(our_score) vs 유저 체감(user_score).
    나중에 GPT 지표 점수 보정의 재료 (Community Validation).
    """
    survey = models.ForeignKey(
        GameSurvey,
        on_delete=models.CASCADE,
        related_name='ratings',
        verbose_name="설문",
    )
    metric = models.CharField(
        max_length=50,
        verbose_name="지표 키",
        help_text="cozy_factor 등 game_metrics 컬럼명",
    )
    our_score = models.FloatField(
        verbose_name="우리 점수",
        help_text="GPT가 매긴 0~10 점수",
    )
    user_score = models.IntegerField(
        verbose_name="유저 체감",
        help_text="유저 슬라이더 응답 1~5",
    )

    

    class Meta:
        db_table = "metric_ratings"
        verbose_name = "지표 평가"
        verbose_name_plural = "지표 평가 목록"
        indexes = [
            # 지표별 보정 분석용 (metric으로 모아서 our vs user 비교)
            models.Index(fields=["metric"], name="idx_rating_metric"),
        ]

    def __str__(self):
        return f"MetricRating({self.metric}: our={self.our_score} user={self.user_score})"

class Favorite(models.Model):
    """
    User's favorited game (wishlist).
    Korean: 유저 찜 게임. 로그인 유저 전용 (비로그인은 로컬 X, DB 저장만).
    같은 유저+게임 중복 방지.
    """
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name="유저",
    )
    app_id = models.IntegerField(db_index=True, verbose_name="게임 app_id")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "favorites"
        verbose_name = "찜"
        verbose_name_plural = "찜 목록"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "app_id"],
                name="uq_user_favorite",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="idx_fav_user_time"),
        ]

    def __str__(self):
        return f"Favorite(user={self.user_id}, app={self.app_id})"