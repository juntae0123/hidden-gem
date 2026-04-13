# fastapi_app/schemas/llm_outputs.py
"""
Hidden Gem - LLM Structured Outputs

OpenAI의 Structured Outputs 기능을 활용한 강제 스키마 매핑
client.beta.chat.completions.parse() 사용

핵심:
- Pydantic 모델로 LLM 출력 강제
- 파싱 오류 최소화
- 타입 안전성 보장
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


# ============================================================
# 기본 Enum 정의
# ============================================================

class PreferenceTypeEnum(str, Enum):
    """선호도 유형"""
    MUST_HIGH = "MUST_HIGH"
    MUST_LOW = "MUST_LOW"
    MUST_EXACT = "MUST_EXACT"
    NEUTRAL = "NEUTRAL"


class TagTypeEnum(str, Enum):
    """태그 유형"""
    MUST = "MUST"
    EXCLUDE = "EXCLUDE"
    PREFER = "PREFER"
    NEUTRAL = "NEUTRAL"


# ============================================================
# LLM 출력 스키마 - 쿼리 파싱
# ============================================================

class MetricOutput(BaseModel):
    """개별 지표 파싱 결과"""
    value: Optional[float] = Field(
        None,
        ge=0,
        le=10,
        description="0~10 사이의 선호 값"
    )
    type: PreferenceTypeEnum = Field(
        PreferenceTypeEnum.NEUTRAL,
        description="선호 유형"
    )
    confidence: float = Field(
        0.8,
        ge=0,
        le=1,
        description="해석 확신도"
    )


class TagOutput(BaseModel):
    """개별 태그 파싱 결과"""
    value: Optional[bool] = Field(
        None,
        description="원하는 값"
    )
    type: TagTypeEnum = Field(
        TagTypeEnum.NEUTRAL,
        description="태그 유형"
    )
    confidence: float = Field(
        0.8,
        ge=0,
        le=1,
        description="해석 확신도"
    )


class MetricsOutput(BaseModel):
    """전체 지표 파싱 결과 (52개 지표)"""
    
    # VIBE
    cozy_factor: Optional[MetricOutput] = None
    horror_factor: Optional[MetricOutput] = None
    gore_level: Optional[MetricOutput] = None
    humor_rating: Optional[MetricOutput] = None
    dark_fantasy_vibe: Optional[MetricOutput] = None
    epic_scale: Optional[MetricOutput] = None
    melancholy: Optional[MetricOutput] = None
    
    # DEMANDS
    reflex_demand: Optional[MetricOutput] = None
    strategic_depth: Optional[MetricOutput] = None
    grind_factor: Optional[MetricOutput] = None
    time_pressure: Optional[MetricOutput] = None
    learning_curve: Optional[MetricOutput] = None
    
    # MECHANICS
    freedom_level: Optional[MetricOutput] = None
    action_pacing: Optional[MetricOutput] = None
    rng_dependency: Optional[MetricOutput] = None
    growth_reward: Optional[MetricOutput] = None
    exploration_reward: Optional[MetricOutput] = None
    management_complexity: Optional[MetricOutput] = None
    stealth_importance: Optional[MetricOutput] = None
    session_length: Optional[MetricOutput] = None
    narrative_linearity: Optional[MetricOutput] = None
    puzzle_complexity: Optional[MetricOutput] = None
    platforming_precision: Optional[MetricOutput] = None
    
    # SOCIAL
    coop_synergy: Optional[MetricOutput] = None
    competitive_stress: Optional[MetricOutput] = None
    npc_interaction: Optional[MetricOutput] = None
    user_creation: Optional[MetricOutput] = None
    multiplayer_scale: Optional[MetricOutput] = None
    
    # PRESENTATION
    lore_richness: Optional[MetricOutput] = None
    choice_consequence: Optional[MetricOutput] = None
    visual_spectacle: Optional[MetricOutput] = None
    environmental_storytelling: Optional[MetricOutput] = None
    soundtrack_impact: Optional[MetricOutput] = None
    
    def to_dict(self) -> Dict[str, MetricOutput]:
        """None이 아닌 지표만 딕셔너리로 변환"""
        return {
            k: v for k, v in self.model_dump().items()
            if v is not None
        }


class TagsOutput(BaseModel):
    """전체 태그 파싱 결과"""
    is_turn_based: Optional[TagOutput] = None
    is_real_time: Optional[TagOutput] = None
    is_first_person: Optional[TagOutput] = None
    is_third_person: Optional[TagOutput] = None
    has_permadeath: Optional[TagOutput] = None
    has_base_building: Optional[TagOutput] = None
    has_crafting: Optional[TagOutput] = None
    is_anime_style: Optional[TagOutput] = None
    is_retro_aesthetic: Optional[TagOutput] = None
    
    def to_dict(self) -> Dict[str, TagOutput]:
        """None이 아닌 태그만 딕셔너리로 변환"""
        return {
            k: v for k, v in self.model_dump().items()
            if v is not None
        }


class QueryParseOutput(BaseModel):
    """
    쿼리 파싱 최종 출력 스키마
    
    OpenAI Structured Outputs에서 이 스키마로 강제 매핑
    """
    
    is_game_related: bool = Field(
        True,
        description="게임 추천 요청인지 여부"
    )
    
    rejection_reason: Optional[str] = Field(
        None,
        description="게임 무관 시 거부 이유"
    )
    
    detected_game_name: Optional[str] = Field(
        None,
        description="언급된 게임명 (있을 경우)"
    )
    
    confidence: float = Field(
        0.8,
        ge=0,
        le=1,
        description="전체 해석 확신도"
    )
    
    interpretation: str = Field(
        "",
        description="검색 의도 한 줄 요약"
    )
    
    metrics: MetricsOutput = Field(
        default_factory=MetricsOutput,
        description="수치 지표 파싱 결과"
    )
    
    tags: TagsOutput = Field(
        default_factory=TagsOutput,
        description="태그 파싱 결과"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "is_game_related": True,
                "rejection_reason": None,
                "detected_game_name": "Hades",
                "confidence": 0.92,
                "interpretation": "Hades와 유사한 액션 로그라이크 게임",
                "metrics": {
                    "action_pacing": {"value": 8, "type": "MUST_HIGH", "confidence": 0.9},
                    "horror_factor": {"value": 2, "type": "MUST_LOW", "confidence": 0.85}
                },
                "tags": {
                    "has_permadeath": {"value": True, "type": "MUST", "confidence": 0.95}
                }
            }
        }


# ============================================================
# LLM 파서 클래스 (Structured Outputs 사용)
# ============================================================

class StructuredQueryParser:
    """
    OpenAI Structured Outputs를 사용한 쿼리 파서
    
    핵심:
    - client.beta.chat.completions.parse() 사용
    - Pydantic 모델로 출력 강제
    - 파싱 실패 시 자동 재시도
    """
    
    SYSTEM_PROMPT = """당신은 Steam 게임 검색 쿼리를 분석하는 전문가입니다.

## 중요: 문맥 인식
- "신작" = 새로운 게임 (New)
- "신비한" = 미스터리한 분위기
- "교회가 나오는 호러 게임" = 게임 검색 (교회 = 게임 내 장소)

## 지표 안내

### 수치 지표 (0~10)
- cozy_factor: 아늑함/힐링
- horror_factor: 공포 강도
- gore_level: 잔인함
- humor_rating: 유머
- action_pacing: 액션 템포 (높을수록 빠름)
- strategic_depth: 전략적 깊이
- grind_factor: 노가다/반복
- learning_curve: 난이도/학습곡선
... (33개 전체)

### 태그 (Boolean)
- is_turn_based: 턴제
- has_permadeath: 영구 사망
- is_anime_style: 애니메풍
... (9개 전체)

## 규칙
1. 언급되지 않은 지표는 null로 두세요
2. 게임과 무관한 검색이면 is_game_related: false
3. 특정 게임명이 언급되면 detected_game_name에 추출
4. 확신이 낮으면 confidence를 낮게"""

    def __init__(self, openai_client):
        self.client = openai_client
    
    async def parse(self, query: str) -> QueryParseOutput:
        """
        쿼리 파싱 (Structured Outputs)
        
        Args:
            query: 검색 쿼리
            
        Returns:
            QueryParseOutput: 파싱 결과 (Pydantic 모델)
        """
        
        try:
            # Structured Outputs 사용
            completion = await self.client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"다음 검색어를 분석하세요:\n\n\"{query}\""}
                ],
                response_format=QueryParseOutput,
                temperature=0.3,
            )
            
            # 파싱된 결과 반환
            return completion.choices[0].message.parsed
        
        except Exception as e:
            # 파싱 실패 시 기본값 반환
            return QueryParseOutput(
                is_game_related=True,
                confidence=0.5,
                interpretation=f"파싱 실패: {query}",
            )
