# fastapi_app/services/query_parser.py
"""
Hidden Gem - LLM 쿼리 파서 (프로덕션 레벨)

Features:
1. OpenAI Structured Outputs 사용
2. gpt-4o-mini → gpt-4o Fallback
3. 캐시된 패턴 매칭 (비용 절감)
4. 게임명 추출
"""

import json
import re
from typing import Dict, Optional, Any
from dataclasses import dataclass
import asyncio
from openai import AsyncOpenAI

from config import settings
from schemas.search import MetricPreference, PreferenceType
from core.exceptions import GameUnrelatedQueryError, QueryParsingError, LLMServiceError

@dataclass
class ParsedQuery:
    """파싱 결과"""
    metrics: Dict[str, MetricPreference]
    tags: Dict[str, Any]
    interpretation: str
    is_game_related: bool
    confidence: float
    detected_game_name: Optional[str] = None
    model_used: str = ""
    from_cache: bool = False

# ============================================================
# 캐시된 쿼리 패턴 (자주 쓰는 검색어 - LLM 호출 없이 처리)
# ============================================================
CACHED_PATTERNS: Dict[str, Dict[str, Any]] = {
    "힐링 게임": {
        "metrics": {"cozy_factor": (8, "MUST_HIGH"), "horror_factor": (2, "MUST_LOW")},
        "interpretation": "편안하고 아늑한 힐링 게임",
    },
    "힐링": {
        "metrics": {"cozy_factor": (8, "MUST_HIGH"), "horror_factor": (2, "MUST_LOW")},
        "interpretation": "힐링되는 게임",
    },
    "공포 게임": {
        "metrics": {"horror_factor": (8, "MUST_HIGH"), "cozy_factor": (2, "MUST_LOW")},
        "interpretation": "무서운 공포 게임",
    },
    "호러 게임": {
        "metrics": {"horror_factor": (8, "MUST_HIGH"), "cozy_factor": (2, "MUST_LOW")},
        "interpretation": "무서운 공포 게임",
    },
    "액션 게임": {
        "metrics": {"action_pacing": (8, "MUST_HIGH"), "reflex_demand": (7, "MUST_HIGH")},
        "interpretation": "빠른 액션 게임",
    },
    "타격감 좋은 게임": {
        "metrics": {"action_pacing": (8, "MUST_HIGH"), "visual_spectacle": (7, "MUST_HIGH")},
        "interpretation": "타격감이 시원한 게임",
    },
    "스토리 게임": {
        "metrics": {"lore_richness": (8, "MUST_HIGH"), "choice_consequence": (7, "MUST_HIGH")},
        "interpretation": "스토리가 풍부한 게임",
    },
    "퍼즐 게임": {
        "metrics": {"puzzle_complexity": (7, "MUST_HIGH"), "strategic_depth": (6, "MUST_HIGH")},
        "interpretation": "머리 쓰는 퍼즐 게임",
    },
    "협동 게임": {
        "metrics": {"coop_synergy": (8, "MUST_HIGH"), "multiplayer_scale": (5, "MUST_HIGH")},
        "interpretation": "친구와 함께하는 협동 게임",
    },
    "로그라이크": {
        "metrics": {"learning_curve": (7, "MUST_HIGH"), "rng_dependency": (6, "MUST_EXACT")},
        "tags": {"has_permadeath": True},
        "interpretation": "로그라이크 게임",
    },
    "하드코어 게임": {
        "metrics": {"learning_curve": (9, "MUST_HIGH"), "reflex_demand": (8, "MUST_HIGH")},
        "interpretation": "고난이도 하드코어 게임",
    },
    "쉬운 게임": {
        "metrics": {"learning_curve": (3, "MUST_LOW"), "time_pressure": (3, "MUST_LOW")},
        "interpretation": "쉽고 편한 게임",
    },
    "노가다 없는 게임": {
        "metrics": {"grind_factor": (2, "MUST_LOW")},
        "interpretation": "반복 플레이가 적은 게임",
    },
    "짧은 게임": {
        "metrics": {"session_length": (3, "MUST_LOW")},
        "interpretation": "짧게 즐길 수 있는 게임",
    },
}

# ============================================================
# LLM 시스템 프롬프트
# ============================================================
SYSTEM_PROMPT = """당신은 Steam 게임 검색 전문가입니다. 유저의 검색어를 분석하여 게임 추천에 사용할 지표로 변환합니다.

## 중요: 문맥 인식
- "신작" = 새로운 게임 (New) ✓ 게임 검색
- "신비한" = 미스터리한 분위기 ✓ 게임 검색
- "하나님", "교회 가야해" = 종교 ✗ 게임 무관

## 지표 목록 (0~10 점수)
**VIBE**: cozy_factor(아늑함), horror_factor(공포), gore_level(잔인함), humor_rating(유머), dark_fantasy_vibe, epic_scale, melancholy
**DEMANDS**: reflex_demand(반사신경), strategic_depth(전략), grind_factor(노가다), time_pressure(시간압박), learning_curve(난이도)
**MECHANICS**: freedom_level, action_pacing(액션템포), rng_dependency, growth_reward, exploration_reward, management_complexity, stealth_importance, session_length, narrative_linearity, puzzle_complexity, platforming_precision
**SOCIAL**: coop_synergy(협동), competitive_stress(경쟁), npc_interaction, user_creation, multiplayer_scale
**PRESENTATION**: lore_richness(로어), choice_consequence, visual_spectacle, environmental_storytelling, soundtrack_impact

## 출력 (JSON)
{
  "is_game_related": true,
  "detected_game_name": null,
  "confidence": 0.85,
  "interpretation": "유저 의도 요약",
  "metrics": {
    "cozy_factor": {"value": 8, "type": "MUST_HIGH"},
    "horror_factor": {"value": 2, "type": "MUST_LOW"}
  },
  "tags": {}
}
type: "MUST_HIGH"(이상), "MUST_LOW"(이하), "MUST_EXACT"(근처), "NEUTRAL"
언급되지 않은 지표는 포함하지 마세요."""

class QueryParser:
    """LLM 쿼리 파서"""
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.primary_model = "gpt-4o-mini"
        self.fallback_model = "gpt-4o"
        self.min_confidence = 0.6
        
        # 게임명 패턴
        self._game_name_patterns = [
            r"(.+?)\s*(같은|비슷한|류|스타일)\s*(게임|거)?",
            r"(.+?)\s*추천",
        ]

    async def parse(self, query: str) -> ParsedQuery:
        """
        쿼리 파싱
        1. 캐시 확인
        2. 게임명 추출
        3. LLM 파싱 (필요시)
        """
        # 1. 캐시 확인
        cached = self._check_cache(query)
        if cached:
            return cached
        
        # 2. 게임명 추출
        detected_game = self._extract_game_name(query)
        
        # 3. LLM 파싱
        result = await self._parse_with_llm(query)
        
        # 게임명 오버라이드
        if detected_game and not result.detected_game_name:
            result.detected_game_name = detected_game
        
        # 게임 무관 체크
        if not result.is_game_related:
            raise GameUnrelatedQueryError(
                detected_topic=result.interpretation
            )
        
        return result

    def _check_cache(self, query: str) -> Optional[ParsedQuery]:
        """캐시된 패턴 확인"""
        normalized = query.lower().strip()
        
        # 정확 매칭
        if normalized in CACHED_PATTERNS:
            return self._build_from_cache(CACHED_PATTERNS[normalized])
        
        # 부분 매칭
        for pattern, data in CACHED_PATTERNS.items():
            if pattern in normalized:
                return self._build_from_cache(data)
        
        return None

    def _build_from_cache(self, data: dict) -> ParsedQuery:
        """캐시 데이터 → ParsedQuery"""
        metrics = {}
        for name, (value, ptype) in data.get("metrics", {}).items():
            metrics[name] = MetricPreference(
                value=value,
                type=PreferenceType(ptype),
                confidence=0.95
            )
        
        return ParsedQuery(
            metrics=metrics,
            tags=data.get("tags", {}),
            interpretation=data.get("interpretation", ""),
            is_game_related=True,
            confidence=0.95,
            model_used="cache",
            from_cache=True,
        )

    def _extract_game_name(self, query: str) -> Optional[str]:
        """게임명 추출"""
        for pattern in self._game_name_patterns:
            match = re.match(pattern, query, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if len(name) >= 2 and name not in ["재밌는", "좋은", "인디", "신작"]:
                    return name
        return None

    async def _parse_with_llm(self, query: str) -> ParsedQuery:
        """LLM으로 파싱"""
        # 1차: gpt-4o-mini
        result = await self._call_llm(query, self.primary_model)
        
        # confidence 낮으면 fallback
        if result.confidence < self.min_confidence:
            result = await self._call_llm(query, self.fallback_model)
        
        return result

    async def _call_llm(self, query: str, model: str) -> ParsedQuery:
        """LLM API 호출"""
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f'검색어: "{query}"'}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3,
                    max_tokens=1000,
                ),
                timeout=30.0
            )
            
            content = response.choices[0].message.content
            data = json.loads(content)
            
            return self._build_from_llm(data, model)
        
        except asyncio.TimeoutError:
            raise LLMServiceError(model, "Timeout")
        except json.JSONDecodeError:
            raise LLMServiceError(model, "Invalid JSON")
        except Exception as e:
            raise LLMServiceError(model, str(e))

    def _build_from_llm(self, data: dict, model: str) -> ParsedQuery:
        """LLM 응답 → ParsedQuery"""
        metrics = {}
        
        for name, metric_data in data.get("metrics", {}).items():
            if isinstance(metric_data, dict) and "value" in metric_data:
                metrics[name] = MetricPreference(
                    value=metric_data["value"],
                    type=PreferenceType(metric_data.get("type", "NEUTRAL")),
                    confidence=metric_data.get("confidence", 0.8)
                )
        
        return ParsedQuery(
            metrics=metrics,
            tags=data.get("tags", {}),
            interpretation=data.get("interpretation", ""),
            is_game_related=data.get("is_game_related", True),
            confidence=data.get("confidence", 0.8),
            detected_game_name=data.get("detected_game_name"),
            model_used=model,
            from_cache=False,
        )

# ============================================================
# 싱글톤
# ============================================================
_parser_instance: Optional[QueryParser] = None

def get_query_parser(api_key: str) -> QueryParser:
    """QueryParser 싱글톤 인스턴스 반환"""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = QueryParser(api_key=api_key)
    return _parser_instance