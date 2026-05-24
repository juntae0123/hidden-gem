"""
Hidden Gem User Taste System - Phase 1 (Data Collection Infrastructure Only)

Korean: 사용자 취향 학습 시스템 Phase 1 — 데이터 수집 인프라만 구현.

Phase 별 구현 계획:
    Phase 1 (지금, 배포 전):
        - UserAction DB 스키마 (Django 모델)
        - 행동 로그 수집 FastAPI 엔드포인트
        - 컨텍스트 풍부하게 저장 (나중 분석용)
        - UserWeightStrategy (인터페이스 정의, 로직 미구현)
        ❌ 취향 벡터 계산 로직 → 미구현 (데이터 없어 검증 불가)
        ❌ 이상 행동 감지 → 미구현 (혼동 변수 문제)
        ❌ 추천 점수 보정 → 미구현 (Phase 3)

    Phase 2 (유저 100명+, 행동 1만 건+):
        - 행동 데이터 상관관계 분석
        - 실증적 가중치 도출
        - TastePreferenceLearner 구현

    Phase 3 (유저 500명+):
        - 취향 벡터 → 추천 점수 보정 합산
        - Steam 연동 즉시 개인화
        - 스와이프 온보딩 연동

데이터 철학:
    "가중치 숫자를 지금 정하지 않는다."
    클릭 = 재밌다는 의미가 아닐 수 있음 (호기심, 시각적 매력, 실수 등)
    데이터 1만 건 쌓인 후 실증적으로 도출.
"""

# ==================== Django 모델 (django_core/apps/users/models.py에 추가) ====================
# 아래 코드는 Django 모델 정의. FastAPI models/game.py와 무관.

DJANGO_USER_ACTION_MODEL = '''
# django_core/apps/users/models.py 에 추가할 코드
# =====================================================

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class UserAction(models.Model):
    """
    User behavior log for taste learning (Phase 1 — data collection only).
    Korean: 취향 학습용 사용자 행동 로그. Phase 1은 수집만, 학습 로직은 Phase 2+.

    비로그인 유저도 session_id로 추적 가능.
    context JSONB에 모든 컨텍스트 저장 → 나중에 어떤 분석이든 가능.
    """

    class ActionType(models.TextChoices):
        SEARCH          = "search",       "검색어 입력"
        DETAIL_VIEW     = "detail_view",  "게임 상세 조회"
        RECOMMENDATION_CLICK = "rec_click", "추천 결과 클릭"
        SEARCH_CLICK    = "search_click", "검색 결과 클릭"
        STEAM_CLICK     = "steam_click",  "Steam으로 이동"
        LIKE            = "like",         "좋아요"
        NEGATIVE_FEEDBACK = "neg_feedback", "취향 안 맞음 피드백"
        REVISIT         = "revisit",      "재방문 (같은 게임)"

    # 사용자 (비로그인이면 null)
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="actions",
        db_index=True,
    )
    # 비로그인 추적용 세션 ID
    session_id = models.CharField(max_length=64, db_index=True)

    # 대상 게임 (검색 행동이면 null)
    app_id = models.IntegerField(null=True, blank=True, db_index=True)

    # 행동 종류
    action_type = models.CharField(
        max_length=30,
        choices=ActionType.choices,
        db_index=True,
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
    context = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "user_actions"
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
'''


# ==================== FastAPI 행동 수집 엔드포인트 ====================
# fastapi_app/routers/taste.py 로 저장

FASTAPI_TASTE_ROUTER = '''
# fastapi_app/routers/taste.py
# =====================================================

"""
User Behavior Collection Router (Phase 1 — Collection Only)

Korean: 사용자 행동 수집 엔드포인트. Phase 1은 수집만.
        취향 학습/추천 보정은 Phase 2+.

Endpoints:
    POST /taste/action          — 행동 이벤트 기록
    GET  /taste/summary/{user}  — Phase 2+ (stub 반환)
"""

import httpx
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/taste", tags=["UserTaste"])

DJANGO_BASE_URL = "http://django:8001"  # Docker 내부 통신


class ActionRequest(BaseModel):
    """
    User action event request schema.
    Korean: 행동 이벤트 요청 스키마.
    """
    session_id: str = Field(..., min_length=8, max_length=64, description="세션 ID")
    app_id: Optional[int] = Field(None, description="대상 게임 App ID (검색 행동이면 null)")
    action_type: str = Field(
        ...,
        description=(
            "행동 종류: search / detail_view / rec_click / "
            "search_click / steam_click / like / neg_feedback / revisit"
        ),
    )
    context: dict = Field(
        default_factory=dict,
        description=(
            "컨텍스트 딕셔너리. 예) "
            "{search_query, click_position, displayed_score, time_to_click_ms, referrer}"
        ),
    )
    user_id: Optional[int] = Field(None, description="로그인 유저 ID (없으면 null)")


@router.post("/action", status_code=201)
async def record_action(
    request: ActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Record user behavior event (Phase 1 — store only).
    Korean: 행동 이벤트 기록. Phase 1은 Django DB에 저장만.
    취향 학습은 Phase 2에서 구현.
    """
    valid_actions = {
        "search", "detail_view", "rec_click", "search_click",
        "steam_click", "like", "neg_feedback", "revisit",
    }
    if request.action_type not in valid_actions:
        raise HTTPException(
            status_code=400,
            detail=f"알 수 없는 action_type: {request.action_type}",
        )

    # Django API로 저장 / Save via Django API
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(
                f"{DJANGO_BASE_URL}/api/taste/action/",
                json={
                    "session_id": request.session_id,
                    "app_id": request.app_id,
                    "action_type": request.action_type,
                    "user_id": request.user_id,
                    "context": {
                        **request.context,
                        "recorded_at": datetime.utcnow().isoformat(),
                    },
                },
            )
            if resp.status_code not in (200, 201):
                logger.warning(f"[TasteRouter] Django 저장 실패: {resp.status_code}")
    except Exception as e:
        # 행동 수집 실패해도 서비스 중단 X / Non-blocking — never fail the main service
        logger.warning(f"[TasteRouter] 행동 기록 실패 (무시): {e}")

    return {"ok": True}


@router.get("/summary/{session_id}")
async def get_taste_summary(session_id: str):
    """
    Get taste summary (Phase 1 — stub).
    Korean: 취향 요약 stub. Phase 2에서 실제 구현.
    """
    return {
        "phase": 1,
        "status": "collecting",
        "message": "취향을 학습 중이에요. 곧 맞춤 추천이 시작됩니다!",
        "session_id": session_id,
    }
'''


# ==================== user_weight 전략 (인터페이스 정의) ====================

class UserWeightStrategy:
    """
    User personalization weight calculator (interface only — Phase 1).
    Korean: 유저 개인화 가중치 계산기. Phase 1은 인터페이스 정의만.
    실제 가중치 숫자는 Phase 2에서 실증 데이터로 결정.

    cold start 전략:
        Steam 연동  → 즉시 0.3 (플레이타임 = 강력한 취향 신호)
        온보딩 완료 → 즉시 0.2 (10개 게임 평가 = 충분한 시그널)
        행동 기반   → 점진적 (3개 → 0.05, 10개 → 0.15, 30개 → 0.3)
        신규 유저   → 0.0 (개인화 없음, 기본 추천만)

    Phase 2 TODO:
        - 실제 행동-만족도 상관관계 분석 후 가중치 재조정
        - Steam 플레이타임 기반 취향 벡터 생성
    """

    @staticmethod
    def calculate(
        action_count: int,
        has_steam_linked: bool = False,
        onboarding_done: bool = False,
    ) -> float:
        """
        Calculate user_weight for personalization blending.
        Korean: 개인화 블렌딩 비율 계산.

        Args:
            action_count: 총 행동 이벤트 수
            has_steam_linked: Steam 계정 연동 여부
            onboarding_done: 스와이프 온보딩 완료 여부

        Returns:
            float: 0.0 ~ 0.3 (추천 점수에서 개인화 반영 비율)
        """
        # Steam 연동: 즉시 강한 개인화 (플레이타임 = 수백 개 행동 데이터)
        if has_steam_linked:
            return 0.3

        # 온보딩 완료: 10개 게임 평가 = 충분한 초기 시그널
        if onboarding_done:
            return 0.2

        # 행동 기반 점진적 개인화
        if action_count >= 30:
            return 0.3
        elif action_count >= 10:
            return 0.15
        elif action_count >= 3:
            return 0.05  # 약하게라도 반영
        else:
            return 0.0  # 완전 신규 → 개인화 없음

    @staticmethod
    def get_phase() -> int:
        """
        Return current implementation phase.
        Korean: 현재 구현 Phase 반환. Phase 2에서 2로 바꾸면 됨.
        """
        return 1  # Phase 1: 수집만


# ==================== Phase 2+ 취향 학습 플레이스홀더 ====================

class TastePreferenceLearner:
    """
    Taste preference learner — Phase 2+ placeholder.
    Korean: 취향 선호도 학습기. Phase 2에서 구현.

    Phase 2 구현 내용:
        - 행동 로그 → 49차원 취향 벡터 변환
        - 실증적 신호 강도 도출 (가중치 숫자 데이터 기반)
        - 지표 겹침 횟수 → 확신도 계산

    Phase 2 조건:
        - 유저 100명+
        - 행동 이벤트 1만 건+
        - steam_click / revisit 상관관계 분석 완료

    지금 이 클래스 건드리지 말 것.
    """

    async def calculate_taste_vector(self, user_id: int) -> dict:
        """
        Calculate 49D taste vector from behavior log.
        Korean: 행동 로그로부터 49차원 취향 벡터 계산. Phase 2에서 구현.
        """
        raise NotImplementedError("Phase 2에서 구현 예정. 데이터 1만 건 후 시작.")

    async def get_reliable_signal_weights(self) -> dict:
        """
        Derive signal weights from empirical data analysis.
        Korean: 실증 데이터 분석으로 신호 가중치 도출. Phase 2에서 구현.

        분석할 것:
            - detail_view 후 steam_click 비율
            - revisit 3회+ 게임과 steam_click 상관관계
            - neg_feedback 이후 행동 패턴
            → 이 데이터로 신호 강도 결정 (지금 임의로 정하지 않음)
        """
        raise NotImplementedError("Phase 2에서 구현 예정.")


class RecommendationScoreAdjuster:
    """
    Score adjuster for taste-based personalization — Phase 3 placeholder.
    Korean: 취향 기반 점수 보정기. Phase 3에서 구현.

    최종 점수 공식 (Phase 3):
        final_score =
            base_score × (1 - user_weight)      # 현재 시스템 (v5 recommender)
            + taste_match_score × user_weight    # 취향 보정

    Phase 3 조건:
        - 유저 500명+
        - TastePreferenceLearner 검증 완료
        - A/B 테스트로 취향 보정 효과 검증
    """

    def adjust(
        self,
        base_score: float,
        taste_match: float,
        user_weight: float,
    ) -> float:
        """
        Adjust base score with taste match. Phase 3에서 구현.
        Korean: 기본 점수에 취향 매칭 합산. Phase 3에서 구현.
        """
        raise NotImplementedError("Phase 3에서 구현 예정.")