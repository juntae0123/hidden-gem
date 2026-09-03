"""
Hidden Gem - Intent Extraction Service
=======================================
사용자 쿼리에서 검색 의도 추출
"""

import os
import re
import json
import logging
from typing import List, Tuple, Set, Optional, Dict, Any
from dataclasses import dataclass, field

from openai import OpenAI
from dotenv import load_dotenv

from backend.config import (
    ALL_METRICS, METRIC_KOREAN, GENRE_MAPPING,
    GENRE_CONFLICTS, REFERENCE_GAMES
)

load_dotenv()
logger = logging.getLogger("hidden_gem.intent")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ============== Intent 데이터 클래스 ==============
@dataclass
class ExtractedIntent:
    metrics: List[str] = field(default_factory=list)
    required_genres: Set[str] = field(default_factory=set)
    preferred_keywords: List[str] = field(default_factory=list)
    negative_genres: Set[str] = field(default_factory=set)
    reference_game: Optional[str] = None
    genre_strictness: float = 0.2
    core_keywords: List[str] = field(default_factory=list)
    priority_metrics: List[str] = field(default_factory=list)
    
    def get_intent_objects(self) -> List[Dict[str, str]]:
        return [{"id": m, "name": METRIC_KOREAN.get(m, m)} for m in self.metrics]

# ============== 레퍼런스 게임 추출 ==============
def extract_reference_game(query: str) -> Optional[Dict[str, Any]]:
    query_lower = query.lower()
    patterns = [r"(.+?)\s*같은", r"(.+?)\s*같이", r"(.+?)\s*처럼", r"(.+?)\s*스타일"]
    
    for pattern in patterns:
        match = re.search(pattern, query_lower)
        if match:
            game_name = match.group(1).strip()
            for ref_name, ref_data in REFERENCE_GAMES.items():
                if ref_name in game_name or game_name in ref_name:
                    return {"name": ref_name, **ref_data}
    
    for ref_name, ref_data in REFERENCE_GAMES.items():
        if ref_name in query_lower:
            return {"name": ref_name, **ref_data}
    
    return None

# ============== 장르 키워드 추출 ==============
def extract_genre_keywords(query: str) -> Tuple[Set[str], List[str]]:
    query_lower = query.lower()
    required_genres = set()
    preferred_keywords = []
    
    for keyword, genres in GENRE_MAPPING.items():
        if keyword in query_lower:
            required_genres.update(genres)
            preferred_keywords.append(keyword)
    
    return required_genres, preferred_keywords

# ============== 부정 장르 추출 ==============
def extract_negative_genres(required_keywords: List[str]) -> Set[str]:
    negative_genres = set()
    for keyword in required_keywords:
        if keyword in GENRE_CONFLICTS:
            negative_genres.update(GENRE_CONFLICTS[keyword])
    return negative_genres

# ============== GPT로 지표 추출 ==============
def extract_metrics_with_gpt(query: str) -> Tuple[List[str], List[str]]:
    prompt = f"""게임 검색 쿼리를 분석하세요.

쿼리: "{query}"

JSON으로 반환:
1. intents: 관련 감성 지표 (최대 4개)
   - 가능한 값: {', '.join(ALL_METRICS)}
2. core_keywords: 핵심 키워드 (최대 3개)

예시: {{"intents": ["replay_value", "addictiveness"], "core_keywords": ["건설", "생존"]}}
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "게임 검색 분석가. JSON만 출력."},
                {"role": "user", "content": prompt}
            ],
            timeout=15.0
        )
        result = json.loads(response.choices[0].message.content)
        
        intents = result.get("intents", [])
        if isinstance(intents, str):
            intents = [intents]
        valid_intents = [i for i in intents if i in ALL_METRICS][:4]
        
        core_keywords = result.get("core_keywords", [])
        if isinstance(core_keywords, str):
            core_keywords = [core_keywords]
        
        return valid_intents, core_keywords[:3]
    except Exception as e:
        logger.warning(f"GPT extraction failed: {e}")
        return [], []

# ============== 메인 의도 추출 함수 ==============
def extract_user_intent_v2(query: str) -> ExtractedIntent:
    intent = ExtractedIntent()
    
    # 1. 레퍼런스 게임 추출
    ref_game = extract_reference_game(query)
    if ref_game:
        intent.reference_game = ref_game.get("name")
        intent.required_genres.update(ref_game.get("genres", []))
        intent.preferred_keywords.extend(ref_game.get("keywords", []))
        intent.priority_metrics.extend(ref_game.get("priority_metrics", []))
    
    # 2. 장르 키워드 추출
    genres, keywords = extract_genre_keywords(query)
    intent.required_genres.update(genres)
    intent.preferred_keywords.extend(keywords)
    intent.preferred_keywords = list(set(intent.preferred_keywords))
    
    # 3. 부정 장르 추출
    intent.negative_genres = extract_negative_genres(intent.preferred_keywords)
    intent.genre_strictness = 0.2
    
    # 4. GPT로 지표 추출
    try:
        metrics, core_keywords = extract_metrics_with_gpt(query)
        intent.metrics = metrics if metrics else intent.priority_metrics[:4]
        intent.core_keywords = core_keywords if core_keywords else intent.preferred_keywords[:3]
    except:
        intent.metrics = intent.priority_metrics[:4] if intent.priority_metrics else []
        intent.core_keywords = intent.preferred_keywords[:3]
    
    # 5. 기본 키워드 추출
    if not intent.core_keywords:
        words = query.replace(",", " ").split()
        intent.core_keywords = [w for w in words if len(w) >= 2][:3]
    
    logger.info(f"[Intent] metrics={intent.metrics}, genres={list(intent.required_genres)[:5]}")
    
    return intent
