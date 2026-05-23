"""
OpenAI Cost Guard - API 비용 폭주 방지 시스템
Prevents unexpected OpenAI API cost spikes by enforcing daily/hourly limits.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import redis.asyncio as aioredis

from config import settings

logger = logging.getLogger(__name__)


class OpenAICostGuard:
    """
    OpenAI API 비용 폭주 방지 (OpenAI Cost Guard)

    일일/시간당 한도 초과 시 요청 차단 + Discord 알람.
    한도값은 settings에서 주입받아 .env로 조정 가능.

    Redis 키:
        openai_cost_today     : 오늘 누적 비용 (USD), 자정 만료
        openai_cost_hour      : 현재 시간 누적 비용 (USD), 1시간 만료
        openai_requests_today : 오늘 총 요청 수, 자정 만료
    """

    # 모델별 토큰당 비용 (USD/1K tokens) / Per-model pricing
    MODEL_RATES: dict = {
        "gpt-4.1-mini":           {"input": 0.00015, "output": 0.00060},
        "gpt-4.1":                {"input": 0.00300, "output": 0.01200},
        "text-embedding-3-small": {"input": 0.00002, "output": 0.0},
        "text-embedding-3-large": {"input": 0.00013, "output": 0.0},
    }

    def __init__(self, redis_url: str = None):
        # settings에서 Redis URL 주입 / Inject Redis URL from settings
        self._redis_url = redis_url or settings.REDIS_CONNECTION_URL
        self._redis: Optional[aioredis.Redis] = None

        # 한도값 settings 참조 (환경변수로 조정 가능)
        # Limit values from settings (configurable via env vars)
        self.DAILY_LIMIT_USD = settings.OPENAI_DAILY_LIMIT_USD
        self.DAILY_WARN_USD = settings.OPENAI_DAILY_WARN_USD
        self.HOURLY_LIMIT_USD = settings.OPENAI_HOURLY_LIMIT_USD
        self.HOURLY_WARN_USD = settings.OPENAI_HOURLY_WARN_USD

    async def _get_redis(self) -> aioredis.Redis:
        """Redis 싱글톤 연결 / Lazy Redis connection"""
        if self._redis is None:
            self._redis = await aioredis.from_url(
                self._redis_url, decode_responses=True
            )
        return self._redis

    @staticmethod
    def _seconds_until_midnight() -> int:
        """
        현재 시각부터 자정까지 남은 초 계산 (Seconds Until Midnight)
        자정 정각에도 정확히 다음 자정까지 계산.
        """
        now = datetime.now()
        tomorrow_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return int((tomorrow_midnight - now).total_seconds())

    # ==================== 비용 계산 / Cost Calculation ====================

    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int = 0,
    ) -> float:
        """
        토큰 수 → USD 비용 계산 (Token to USD Cost)
        알 수 없는 모델은 gpt-4.1-mini 기준으로 보수적 추정.
        """
        rates = self.MODEL_RATES.get(model, self.MODEL_RATES["gpt-4.1-mini"])
        cost = (input_tokens / 1000) * rates["input"]
        cost += (output_tokens / 1000) * rates["output"]
        return round(cost, 6)

    # ==================== 한도 확인 / Limit Check ====================

    async def check_before_request(self, model: str = "gpt-4.1-mini") -> tuple[bool, str]:
        """
        OpenAI 호출 전 한도 확인 (Pre-request Cost Check)
        한도 초과 시 (False, 이유) 반환 → 호출 차단.
        Redis 장애 시 fail-open (허용) 처리.

        Returns:
            (allowed: bool, reason: str)
        """
        try:
            r = await self._get_redis()

            daily_cost = float(await r.get("openai_cost_today") or 0)
            hourly_cost = float(await r.get("openai_cost_hour") or 0)

            # 일일 hard limit 초과 / Daily hard limit exceeded
            if daily_cost >= self.DAILY_LIMIT_USD:
                msg = f"일일 OpenAI 비용 한도 초과 (${daily_cost:.2f}/${self.DAILY_LIMIT_USD})"
                logger.critical(f"[CostGuard] {msg}")
                await self._send_alert(msg, level="critical")
                return False, msg

            # 시간당 스파이크 감지 / Hourly spike detection
            if hourly_cost >= self.HOURLY_LIMIT_USD:
                msg = f"시간당 OpenAI 비용 비정상 (${hourly_cost:.2f}/${self.HOURLY_LIMIT_USD})"
                logger.error(f"[CostGuard] {msg}")
                await self._send_alert(msg, level="critical")
                return False, msg

            # 경고 로그 (차단하지 않음) / Warning log (no blocking)
            if daily_cost >= self.DAILY_WARN_USD:
                logger.warning(
                    f"[CostGuard] 일일 비용 경고: ${daily_cost:.2f}/${self.DAILY_LIMIT_USD}"
                )

            return True, "ok"

        except Exception as e:
            # Redis 장애 시 허용 (fail open) / Fail open on Redis error
            logger.warning(f"[CostGuard] Redis 오류, 요청 허용: {e}")
            return True, "redis_error_passthrough"

    # ==================== 비용 추적 / Cost Tracking ====================

    async def track_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int = 0,
    ) -> float:
        """
        API 호출 후 비용 누적 추적 (Post-request Cost Tracking)
        캐시 적중 시 호출하지 않아야 함 (비용 발생 없음).

        Returns:
            float: 이번 요청 비용 (USD)
        """
        cost = self.calculate_cost(model, input_tokens, output_tokens)

        try:
            r = await self._get_redis()
            ttl_midnight = self._seconds_until_midnight()
            pipe = r.pipeline()

            # 일일 누적 / Daily accumulation (자정 만료)
            pipe.incrbyfloat("openai_cost_today", cost)
            pipe.expire("openai_cost_today", ttl_midnight)

            # 시간당 누적 / Hourly accumulation (1시간 만료)
            pipe.incrbyfloat("openai_cost_hour", cost)
            pipe.expire("openai_cost_hour", 3600)

            # 요청 수 카운트 / Request count
            pipe.incr("openai_requests_today")
            pipe.expire("openai_requests_today", ttl_midnight)

            await pipe.execute()

            logger.debug(
                f"[CostGuard] {model} +${cost:.6f} "
                f"(in={input_tokens}, out={output_tokens})"
            )

        except Exception as e:
            logger.warning(f"[CostGuard] 비용 추적 실패: {e}")

        return cost

    # ==================== 통계 조회 / Stats ====================

    async def get_stats(self) -> dict:
        """
        오늘 비용 통계 조회 (Today's Cost Stats)
        운영 대시보드 및 일일 리포트용.
        """
        try:
            r = await self._get_redis()
            daily_cost = float(await r.get("openai_cost_today") or 0)
            hourly_cost = float(await r.get("openai_cost_hour") or 0)
            requests_today = int(await r.get("openai_requests_today") or 0)

            return {
                "daily_cost_usd": round(daily_cost, 4),
                "hourly_cost_usd": round(hourly_cost, 4),
                "daily_limit_usd": self.DAILY_LIMIT_USD,
                "daily_usage_pct": round(daily_cost / self.DAILY_LIMIT_USD * 100, 1),
                "requests_today": requests_today,
                "status": (
                    "critical" if daily_cost >= self.DAILY_LIMIT_USD
                    else "warning" if daily_cost >= self.DAILY_WARN_USD
                    else "ok"
                ),
            }
        except Exception as e:
            logger.warning(f"[CostGuard] 통계 조회 실패: {e}")
            return {"error": str(e)}

    # ==================== 알람 / Alert ====================

    async def _send_alert(self, message: str, level: str = "warning"):
        """
        Discord 웹훅 알람 (Discord Alert)
        DISCORD_WEBHOOK_URL 환경변수 없으면 로그만 출력.
        """
        webhook_url = settings.DISCORD_WEBHOOK_URL
        if not webhook_url:
            return

        try:
            import httpx
            emoji = "🚨" if level == "critical" else "⚠️"
            payload = {
                "content": (
                    f"{emoji} **[Hidden Gem 비용 알람]**\n"
                    f"{message}\n"
                    f"`{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
                )
            }
            async with httpx.AsyncClient() as client:
                await client.post(webhook_url, json=payload, timeout=5)
        except Exception as e:
            logger.warning(f"[CostGuard] Discord 알람 실패: {e}")


# 싱글톤 인스턴스 / Singleton instance
cost_guard = OpenAICostGuard()