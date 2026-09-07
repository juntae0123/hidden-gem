"""
Hidden Gem Core Tests — P0/P1 우선순위 순서

Korean: 배포 전 반드시 통과해야 할 핵심 테스트 23개.
        위험도 순서: P0 (비용/크래시) → P1 (기능/품질)

위치: fastapi_app/tests/test_core.py

실행:
    cd C:/Hidden-Gem-project/fastapi_app
    pytest tests/test_core.py -v          # 전체
    pytest tests/test_core.py -v -m p0   # P0만
    pytest tests/test_core.py -v -m p1   # P1만
"""

import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch


# ==================== P0-1: 비용 가드 (가장 위험) ====================

@pytest.mark.p0
class TestCostGuardBlocksOverLimit:
    """
    P0-1: OpenAI cost guard prevents billing explosion.
    Korean: OpenAI 비용 가드가 한도 초과 시 차단하는지 검증.
    깨지면: OpenAI 청구서 폭탄 (진짜 위험).

    구조: check_before_request()가 _get_redis() → r.get("openai_cost_today") 직접 호출
    → _get_redis()를 mock하여 Redis 반환값 제어.
    """

    def _make_mock_redis(self, daily: float = 0.0, hourly: float = 0.0) -> AsyncMock:
        """
        Create mock Redis that returns given cost values.
        Korean: daily/hourly 비용을 반환하는 Redis mock 생성.
        """
        r = AsyncMock()
        async def mock_get(key):
            if key == "openai_cost_today":
                return str(daily)
            if key == "openai_cost_hour":
                return str(hourly)
            return None
        r.get = mock_get
        return r

    @pytest.mark.asyncio
    async def test_allows_request_under_daily_limit(self):
        """Under daily limit → request allowed."""
        from services.cost_guard import cost_guard

        mock_redis = self._make_mock_redis(daily=0.0, hourly=0.0)
        with patch.object(cost_guard, "_get_redis", return_value=mock_redis):
            allowed, reason = await cost_guard.check_before_request("gpt-4.1-mini")
            assert allowed is True, f"한도 내에서 차단됨: {reason}"

    @pytest.mark.asyncio
    async def test_blocks_request_over_daily_limit(self):
        """Over daily limit → request blocked immediately."""
        from services.cost_guard import cost_guard
        from config import settings

        over = settings.OPENAI_DAILY_LIMIT_USD + 1.0
        mock_redis = self._make_mock_redis(daily=over, hourly=0.0)

        with patch.object(cost_guard, "_get_redis", return_value=mock_redis):
            with patch.object(cost_guard, "_send_alert", new_callable=AsyncMock):
                allowed, reason = await cost_guard.check_before_request("gpt-4.1-mini")
                assert allowed is False, "일일 한도 초과에도 허용 (차단 실패)"
                assert reason and reason != "ok", "차단 이유 메시지 없음"

    @pytest.mark.asyncio
    async def test_blocks_hourly_spike(self):
        """Over hourly spike limit → blocked even if daily is OK."""
        from services.cost_guard import cost_guard
        from config import settings

        over_hourly = settings.OPENAI_HOURLY_LIMIT_USD + 1.0
        mock_redis = self._make_mock_redis(daily=0.0, hourly=over_hourly)

        with patch.object(cost_guard, "_get_redis", return_value=mock_redis):
            with patch.object(cost_guard, "_send_alert", new_callable=AsyncMock):
                allowed, reason = await cost_guard.check_before_request("gpt-4.1-mini")
                assert allowed is False, "시간당 스파이크에도 허용 (차단 실패)"

    def test_daily_limit_config_is_sane(self):
        """Daily limit must be > 0 and <= $500."""
        from config import settings
        assert settings.OPENAI_DAILY_LIMIT_USD > 0
        assert settings.OPENAI_DAILY_LIMIT_USD <= 500, (
            f"일일 한도 위험하게 높음: ${settings.OPENAI_DAILY_LIMIT_USD}"
        )
        assert settings.OPENAI_HOURLY_LIMIT_USD > 0
        assert settings.OPENAI_HOURLY_LIMIT_USD < settings.OPENAI_DAILY_LIMIT_USD, (
            "시간당 한도 >= 일일 한도: 시간당이 더 작아야 함"
        )

    def test_warn_threshold_below_hard_limit(self):
        """Warn threshold must be strictly lower than hard limit."""
        from config import settings
        assert settings.OPENAI_DAILY_WARN_USD < settings.OPENAI_DAILY_LIMIT_USD
        assert settings.OPENAI_HOURLY_WARN_USD < settings.OPENAI_HOURLY_LIMIT_USD

    @pytest.mark.asyncio
    async def test_redis_failure_is_fail_open(self):
        """Redis failure → fail open (allow request, don't crash service)."""
        from services.cost_guard import cost_guard

        # Redis 연결 자체가 예외를 던지는 상황
        async def broken_redis():
            raise ConnectionError("Redis 연결 끊김")

        with patch.object(cost_guard, "_get_redis", side_effect=ConnectionError("Redis down")):
            allowed, reason = await cost_guard.check_before_request("gpt-4.1-mini")
            # fail-open: Redis 장애 시 서비스 중단 없이 허용
            assert allowed is True, "Redis 장애 시 서비스 중단됨 (fail-open 실패)"
            assert "redis_error" in reason or reason == "redis_error_passthrough"


# ==================== P0-2: NULL 지표 안전성 ====================

@pytest.mark.p0
class TestNullMetricsDontCrash:
    """
    P0-2: NULL metric values handled safely — no 500 errors.
    Korean: NULL 지표가 크래시 없이 안전하게 처리되는지 검증.
    깨지면: 추천 API 500 에러 → 서비스 다운.
    """

    def test_resolve_null_zero_policy(self):
        """ZERO policy: horror_factor NULL → 0.0 (공포 없음 = 0이 맞음)."""
        from services.recommender import resolve_null
        assert resolve_null("horror_factor", None) == 0.0
        assert resolve_null("multiplayer_scale", None) == 0.0
        assert resolve_null("gore_level", None) == 0.0

    def test_resolve_null_global_mean_policy(self):
        """GLOBAL_MEAN policy: visual_spectacle NULL → dataset mean."""
        from services.recommender import resolve_null, GLOBAL_METRIC_MEANS
        result = resolve_null("visual_spectacle", None)
        assert result == GLOBAL_METRIC_MEANS["visual_spectacle"]

    def test_resolve_null_genre_mean_policy(self):
        """GENRE_MEAN policy: narrative_depth NULL → genre default."""
        from services.recommender import resolve_null, GENRE_METRIC_DEFAULTS
        result = resolve_null("narrative_depth", None)
        assert result == GENRE_METRIC_DEFAULTS["narrative_depth"]

    def test_resolve_null_unknown_field_returns_neutral(self):
        """Unknown field NULL → neutral 5.0 (not crash)."""
        from services.recommender import resolve_null
        assert resolve_null("nonexistent_field_xyz", None) == 5.0

    def test_build_vector_all_nulls_no_crash(self, null_metric):
        """ALL-NULL metric → vector built without crash, no NaN/inf."""
        from services.recommender import (
            build_weighted_vector, SearchIntentClassifier, NUMERIC_METRIC_FIELDS
        )
        weight_map = SearchIntentClassifier().get_weight_map(None)

        try:
            vec = build_weighted_vector(null_metric, weight_map)
        except Exception as e:
            pytest.fail(f"ALL-NULL 크래시: {e}")

        assert len(vec) == len(NUMERIC_METRIC_FIELDS)
        assert not np.any(np.isnan(vec)), "NaN 발생"
        assert not np.any(np.isinf(vec)), "inf 발생"

    def test_score_computation_partial_nulls_no_crash(self):
        """Partial NULL metric → score computed without crash, in 0~99."""
        from services.recommender import (
            build_weighted_vector, compute_metric_score,
            to_display_score, SearchIntentClassifier, NUMERIC_METRIC_FIELDS,
        )
        partial = MagicMock()
        for i, f in enumerate(NUMERIC_METRIC_FIELDS):
            setattr(partial, f, None if i % 2 == 0 else 5.0)

        weight_map = SearchIntentClassifier().get_weight_map(None)
        n_active = sum(1 for w in weight_map.values() if w > 0)

        try:
            v1 = build_weighted_vector(partial, weight_map)
            v2 = build_weighted_vector(partial, weight_map)
            score = compute_metric_score(v1, v2, n_active)
            display = to_display_score(score, 0.0)
            assert 0.0 <= display <= 99.0
        except Exception as e:
            pytest.fail(f"부분 NULL 점수 계산 크래시: {e}")


# ==================== P0-3: 추천 결과 형식 ====================

@pytest.mark.p0
class TestRecommendationReturnsValidResults:
    """
    P0-3: Recommendation API returns valid structure and score range.
    Korean: 추천 API가 올바른 구조와 0~99 점수를 반환하는지 검증.
    깨지면: 프론트 렌더링 오류, 점수 표시 비정상.
    """

    def test_score_always_0_to_99(self):
        """to_display_score must always return 0~99, never 100+."""
        from services.recommender import to_display_score
        cases = [
            (0.0, 0.0), (1.0, 1.0), (0.95, 0.8),
            (0.5, 0.5), (0.0, 1.0), (1.0, 0.0),
        ]
        for raw, gem in cases:
            score = to_display_score(raw, gem)
            assert 0.0 <= score <= 99.0, f"범위 초과: raw={raw}, gem={gem} → {score}"

    def test_anchor_and_max_constants(self):
        """SCORE_ANCHOR=100, SCORE_MAX=99."""
        from services.recommender import SCORE_ANCHOR, SCORE_MAX
        assert SCORE_ANCHOR == 100.0, "앵커 점수 ≠ 100"
        assert SCORE_MAX == 99.0, "최대 점수 ≠ 99"

    def test_perfect_match_still_under_100(self):
        """Perfect raw_score=1.0 + max gem_bonus must not exceed 99."""
        from services.recommender import to_display_score
        assert to_display_score(1.0, 1.0) <= 99.0

    def test_score_breakdown_has_all_fields(self, mock_game, cozy_metric):
        """score_breakdown dict must contain all 4 required fields."""
        from services.recommender import (
            GameRecommender, build_weighted_vector,
            compute_metric_score, to_display_score,
        )
        rec = GameRecommender()
        wm = rec.intent_classifier.get_weight_map(None)
        v = build_weighted_vector(cozy_metric, wm)
        n = sum(1 for w in wm.values() if w > 0)
        ms = compute_metric_score(v, v, n)
        gb = rec._calculate_gem_bonus(mock_game, cozy_metric)
        ds = to_display_score(ms, gb)

        breakdown = {
            "metric_score": round(ms * 100, 1),
            "embedding_score": 0.0,
            "gem_bonus": round(gb * 5, 1),
            "final_score": ds,
        }
        assert {"metric_score", "embedding_score", "gem_bonus", "final_score"} == set(breakdown.keys())
        assert 0.0 <= breakdown["final_score"] <= 99.0


# ==================== P1-1: Rate Limit ====================

@pytest.mark.p1
class TestRateLimitEnforced:
    """
    P1-1: Rate limiting configuration is valid.
    Korean: Rate Limit 설정이 올바른지 검증.
    깨지면: 어뷰징 방어 실패.
    """

    def test_rate_limit_settings_exist(self):
        """Rate limit settings must exist in config."""
        from config import settings
        assert hasattr(settings, "RATE_LIMIT_SEARCH_ANON")
        assert hasattr(settings, "RATE_LIMIT_DEFAULT")

    def test_rate_limit_format_valid(self):
        """Rate limit format must be 'N/unit'."""
        from config import settings
        for attr in ["RATE_LIMIT_SEARCH_ANON", "RATE_LIMIT_DEFAULT"]:
            rate = getattr(settings, attr)
            parts = rate.split("/")
            assert len(parts) == 2, f"{attr} 형식 오류: {rate}"
            assert parts[0].isdigit(), f"{attr} 숫자 부분 오류"
            assert parts[1] in ("second", "minute", "hour"), f"{attr} 단위 오류"

    def test_rate_limit_values_reasonable(self):
        """Rate limit values must be in reasonable range."""
        from config import settings
        def parse(s): return int(s.split("/")[0])
        assert 1 <= parse(settings.RATE_LIMIT_SEARCH_ANON) <= 100
        assert 1 <= parse(settings.RATE_LIMIT_DEFAULT) <= 1000

    def test_anonymous_limit_lte_authenticated(self):
        """Anonymous rate limit must be <= authenticated."""
        from config import settings
        def parse(s): return int(s.split("/")[0])
        assert parse(settings.RATE_LIMIT_SEARCH_ANON) <= parse(settings.RATE_LIMIT_SEARCH_AUTH)


# ==================== P1-2: 가중치 변별력 ====================

@pytest.mark.p1
class TestWeightingDifferentiatesScores:
    """
    P1-2: Four-tier weighting produces meaningful score differences.
    Korean: 4단계 가중치가 의미 있는 변별력을 제공하는지 검증.
    깨지면: 추천 품질 저하 (점수가 다 비슷해짐).
    """

    def test_weight_ratio_at_least_10x(self):
        """Primary(5x) / Irrelevant(0.1x) must be >= 10x."""
        from services.recommender import W_PRIMARY, W_IRRELEVANT
        assert W_PRIMARY / W_IRRELEVANT >= 10.0, (
            f"변별력 부족: {W_PRIMARY}/{W_IRRELEVANT} = {W_PRIMARY/W_IRRELEVANT:.1f}x"
        )

    def test_mood_cozy_assigns_correct_tiers(self):
        """mood_cozy: cozy_factor=primary, humor=secondary, strategic=irrelevant."""
        from services.recommender import SearchIntentClassifier, W_PRIMARY, W_SECONDARY, W_IRRELEVANT
        wm = SearchIntentClassifier().get_weight_map("mood_cozy")
        assert wm["cozy_factor"] == W_PRIMARY
        assert wm["time_pressure"] == W_PRIMARY
        assert wm["humor_rating"] == W_SECONDARY
        assert wm["strategic_depth"] == W_IRRELEVANT, (
            f"strategic_depth가 mood_cozy에서 irrelevant여야 함: {wm['strategic_depth']}"
        )

    def test_similar_game_scores_higher_than_dissimilar(self):
        """Cozy game must score higher against cozy target than horror game."""
        from services.recommender import (
            GameRecommender, build_weighted_vector,
            compute_metric_score, NUMERIC_METRIC_FIELDS,
        )
        rec = GameRecommender()
        wm = rec.intent_classifier.get_weight_map("mood_cozy")
        n = sum(1 for w in wm.values() if w > 0)

        def make(overrides):
            m = MagicMock()
            for f in NUMERIC_METRIC_FIELDS:
                setattr(m, f, 5.0)
            for k, v in overrides.items():
                setattr(m, k, v)
            return m

        target     = make({"cozy_factor": 9.0, "horror_factor": 0.0, "time_pressure": 1.0})
        similar    = make({"cozy_factor": 8.0, "horror_factor": 1.0, "time_pressure": 2.0})
        dissimilar = make({"cozy_factor": 1.0, "horror_factor": 9.0, "time_pressure": 8.0})

        tv = build_weighted_vector(target, wm)
        sv = build_weighted_vector(similar, wm)
        dv = build_weighted_vector(dissimilar, wm)

        sim_score = compute_metric_score(tv, sv, n)
        dis_score = compute_metric_score(tv, dv, n)

        assert sim_score > dis_score, (
            f"변별력 실패: 유사({sim_score:.3f}) <= 다름({dis_score:.3f})"
        )
        assert (sim_score - dis_score) >= 0.05, (
            f"변별력 부족: 차이 {sim_score - dis_score:.3f} (최소 0.05)"
        )

    def test_preference_metrics_always_primary(self):
        """User preference metrics always get W_PRIMARY regardless of group."""
        from services.recommender import SearchIntentClassifier, W_PRIMARY
        wm = SearchIntentClassifier().get_weight_map(
            group_name=None,
            preferences={"narrative_depth": 9.0, "lore_richness": 8.0},
        )
        assert wm["narrative_depth"] == W_PRIMARY
        assert wm["lore_richness"] == W_PRIMARY

# ==================== 레이트 리밋이 실제로 붙었는가 (2026-09-07) ====================
# 기존 테스트는 settings.RATE_LIMIT_* 의 존재와 값만 검사했다. 그래서 값이 정의돼 있고
# 테스트가 통과하는데도 **어떤 엔드포인트에도 적용되지 않은** 상태를 반년간 통과시켰다.
# 설정이 아니라 '적용'을 검사한다.
#
# `main` 을 import 하지 않는다 — 호스트 venv 엔 sentry_sdk 가, 컨테이너엔 pytest 가 없어
# main 은 어느 환경에서도 테스트로 import 되지 않는다. 라우터 모듈을 직접 본다.

def _dep_names(route) -> str:
    return " ".join(
        f"{getattr(d.call, '__module__', '')}.{getattr(d.call, '__qualname__', '')}"
        for d in route.dependant.dependencies
    )


class TestRateLimitApplied:
    """LLM·임베딩을 호출하는 경로에 레이트 리밋 의존성이 실제로 걸려 있는지."""

    PROTECTED = [
        ("/games/search/semantic", "POST"),
        ("/games/recommend/by-game", "POST"),
        ("/games/recommend/by-preference", "POST"),
        ("/games/recommend/by-vibe", "POST"),
        ("/games/search", "GET"),
    ]

    def test_llm_endpoints_have_rate_limit(self):
        from routers.games import router

        by_key = {(r.path, m): r for r in router.routes for m in getattr(r, "methods", [])}
        missing = []
        for path, method in self.PROTECTED:
            route = by_key.get((path, method))
            assert route is not None, f"라우트를 찾지 못했다: {method} {path}"
            if "ratelimit" not in _dep_names(route):
                missing.append(f"{method} {path}")
        assert not missing, f"레이트 리밋이 붙지 않은 엔드포인트: {missing}"

    def test_ops_endpoints_require_token(self):
        """/ops/* 는 전부 토큰 게이트가 걸려 있어야 한다 (C-15)."""
        from routers.ops import router

        routes = [r for r in router.routes if hasattr(r, "dependant")]
        assert len(routes) >= 3, f"/ops 라우트가 {len(routes)}개뿐이다"
        for r in routes:
            assert "require_ops_token" in _dep_names(r), f"토큰 게이트 없음: {r.path}"

    def test_ops_token_fail_closed(self):
        """토큰이 비어 있고 DEBUG 가 아니면 503 — 열린 채로 남지 않는다."""
        import asyncio
        from fastapi import HTTPException
        from routers.ops import require_ops_token
        from config import settings

        saved = (settings.OPS_TOKEN, settings.DEBUG)
        try:
            settings.OPS_TOKEN, settings.DEBUG = "", False
            try:
                asyncio.run(require_ops_token(None))
                assert False, "토큰 미설정인데 통과했다"
            except HTTPException as e:
                assert e.status_code == 503
            settings.OPS_TOKEN = "abc"
            try:
                asyncio.run(require_ops_token("wrong"))
                assert False, "잘못된 토큰이 통과했다"
            except HTTPException as e:
                assert e.status_code == 401
            asyncio.run(require_ops_token("abc"))  # 정상 토큰은 통과
        finally:
            settings.OPS_TOKEN, settings.DEBUG = saved
