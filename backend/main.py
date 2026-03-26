import os
import json
import re
import time
import logging
from typing import List, Dict, Optional, Tuple, Set, Any
from functools import wraps
from dataclasses import dataclass, field
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv, find_dotenv
from openai import OpenAI, APIError, RateLimitError, APITimeoutError

# ============== 로깅 설정 ==============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("hidden_gem")

# 환경 변수 로드
load_dotenv(find_dotenv())

# 초기화
app = FastAPI(title="Hidden Gem API", version="4.0")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DB_URL = os.getenv("DATABASE_URL")
engine = create_engine(DB_URL, pool_pre_ping=True, pool_recycle=300)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== v4.0 핵심 상수 ==============
# 점수 기준 (100점 돌파 허용)
LEGENDARY_THRESHOLD = 100              # 이 이상이면 LEGENDARY
DROP_THRESHOLD = 40                    # 이 미만은 DROP
MIN_RESULTS = 5                        # 최소 결과 수

# 🔥 Limit Break 공식 가중치
METADATA_WEIGHT = 0.8                  # 메타데이터 점수 × 0.8
SIMILARITY_WEIGHT = 0.4                # 유사도 보정 × 0.4
# 최대 이론치: 100×0.8 + 100×0.4 = 120점

# 유사도 스케일링 (0.45~0.85 → 0~100)
SIMILARITY_MIN = 0.45
SIMILARITY_MAX = 0.85

# 🔥 Exact Match 상수 (시리즈물 도배 방지)
EXACT_MATCH_BOOST = 50                 # 완전 일치: +50점
PARTIAL_MATCH_BOOST_MAX = 5            # 부분 일치: 최대 +5점
EXACT_MATCH_QUERY_MAX_LEN = 15         # 15자 이내만 Exact Match 적용

# S/A/B 티어 가중치
WEIGHT_S_TIER = 1.8
WEIGHT_A_TIER = 1.4
WEIGHT_B_TIER = 1.1

MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0

# ============== 14개 감성 지표 ==============
METRIC_KOREAN: Dict[str, str] = {
    "mania_score": "마니아 매력",
    "story_depth": "스토리 깊이",
    "originality": "독창성",
    "difficulty": "난이도",
    "art_style": "아트 스타일",
    "replay_value": "리플레이 가치",
    "indie_spirit": "인디 감성",
    "character_appeal": "캐릭터 매력",
    "user_friendliness": "접근성",
    "addictiveness": "중독성",
    "emotional_impact": "감정적 임팩트",
    "atmosphere_intensity": "분위기 몰입",
    "soundtrack_prominence": "사운드트랙",
    "gem_potential": "숨겨진 명작"
}

ALL_METRICS: List[str] = list(METRIC_KOREAN.keys())

# ============== 장르별 S/A/B 티어 가중치 ==============
GENRE_WEIGHTS: Dict[str, Dict[str, List[str]]] = {
    "Action": {
        "S": ["addictiveness", "difficulty"],
        "A": ["replay_value", "art_style", "mania_score"],
        "B": ["user_friendliness", "originality", "atmosphere_intensity"]
    },
    "RPG": {
        "S": ["story_depth", "character_appeal"],
        "A": ["replay_value", "originality", "emotional_impact"],
        "B": ["art_style", "soundtrack_prominence", "atmosphere_intensity"]
    },
    "Adventure": {
        "S": ["story_depth", "atmosphere_intensity"],
        "A": ["emotional_impact", "art_style", "originality"],
        "B": ["soundtrack_prominence", "character_appeal", "user_friendliness"]
    },
    "Strategy": {
        "S": ["difficulty", "replay_value"],
        "A": ["originality", "addictiveness", "user_friendliness"],
        "B": ["mania_score", "story_depth", "art_style"]
    },
    "Simulation": {
        "S": ["replay_value", "addictiveness"],
        "A": ["user_friendliness", "originality", "art_style"],
        "B": ["atmosphere_intensity", "mania_score", "indie_spirit"]
    },
    "Survival": {
        "S": ["addictiveness", "difficulty"],
        "A": ["replay_value", "atmosphere_intensity", "originality"],
        "B": ["user_friendliness", "indie_spirit", "mania_score"]
    },
    "Roguelike": {
        "S": ["difficulty", "replay_value"],
        "A": ["addictiveness", "originality", "mania_score"],
        "B": ["art_style", "atmosphere_intensity", "indie_spirit"]
    },
    "Sandbox": {
        "S": ["replay_value", "originality"],
        "A": ["addictiveness", "user_friendliness", "indie_spirit"],
        "B": ["art_style", "atmosphere_intensity", "difficulty"]
    },
    "Colony Sim": {
        "S": ["replay_value", "addictiveness", "difficulty"],
        "A": ["originality", "mania_score", "atmosphere_intensity"],
        "B": ["art_style", "indie_spirit", "user_friendliness"]
    },
    "Base Building": {
        "S": ["replay_value", "addictiveness"],
        "A": ["difficulty", "originality", "atmosphere_intensity"],
        "B": ["art_style", "user_friendliness", "indie_spirit"]
    },
    "City Builder": {
        "S": ["replay_value", "addictiveness"],
        "A": ["originality", "user_friendliness", "difficulty"],
        "B": ["art_style", "atmosphere_intensity", "indie_spirit"]
    },
    "Horror": {
        "S": ["atmosphere_intensity", "emotional_impact"],
        "A": ["story_depth", "soundtrack_prominence", "art_style"],
        "B": ["difficulty", "originality", "character_appeal"]
    },
    "Puzzle": {
        "S": ["originality", "difficulty"],
        "A": ["user_friendliness", "art_style", "addictiveness"],
        "B": ["atmosphere_intensity", "soundtrack_prominence", "indie_spirit"]
    },
    "Platformer": {
        "S": ["difficulty", "art_style"],
        "A": ["addictiveness", "replay_value", "originality"],
        "B": ["soundtrack_prominence", "user_friendliness", "atmosphere_intensity"]
    },
    "Metroidvania": {
        "S": ["difficulty", "atmosphere_intensity"],
        "A": ["art_style", "originality", "replay_value"],
        "B": ["soundtrack_prominence", "addictiveness", "indie_spirit"]
    },
    "Souls-like": {
        "S": ["difficulty", "atmosphere_intensity"],
        "A": ["mania_score", "replay_value", "originality"],
        "B": ["art_style", "story_depth", "soundtrack_prominence"]
    },
    "Visual Novel": {
        "S": ["story_depth", "emotional_impact"],
        "A": ["character_appeal", "art_style", "soundtrack_prominence"],
        "B": ["originality", "atmosphere_intensity", "user_friendliness"]
    },
    "Card Game": {
        "S": ["replay_value", "addictiveness"],
        "A": ["originality", "difficulty", "mania_score"],
        "B": ["art_style", "user_friendliness", "indie_spirit"]
    },
    "Shooter": {
        "S": ["addictiveness", "difficulty"],
        "A": ["replay_value", "atmosphere_intensity", "art_style"],
        "B": ["originality", "soundtrack_prominence", "user_friendliness"]
    },
    "Open World": {
        "S": ["replay_value", "atmosphere_intensity"],
        "A": ["story_depth", "originality", "addictiveness"],
        "B": ["art_style", "character_appeal", "user_friendliness"]
    },
    "Indie": {
        "S": ["indie_spirit", "originality"],
        "A": ["art_style", "emotional_impact", "gem_potential"],
        "B": ["story_depth", "atmosphere_intensity", "soundtrack_prominence"]
    },
    "Automation": {
        "S": ["addictiveness", "replay_value", "originality"],
        "A": ["difficulty", "mania_score", "user_friendliness"],
        "B": ["art_style", "atmosphere_intensity", "indie_spirit"]
    },
    "Management": {
        "S": ["addictiveness", "replay_value"],
        "A": ["difficulty", "originality", "user_friendliness"],
        "B": ["art_style", "atmosphere_intensity", "indie_spirit"]
    },
    "Crafting": {
        "S": ["addictiveness", "replay_value"],
        "A": ["originality", "difficulty", "user_friendliness"],
        "B": ["atmosphere_intensity", "indie_spirit", "art_style"]
    },
}

# ============== 코어 장르 매핑 (한글 → Steam 장르) ==============
CORE_GENRE_MAPPING: Dict[str, List[str]] = {
    # 건설/관리 계열
    "건설": ["Simulation", "Strategy", "City Builder", "Base Building", "Colony Sim", "Sandbox"],
    "생존": ["Survival", "Crafting", "Open World Survival Craft", "Base Building"],
    "관리": ["Management", "Simulation", "Tycoon", "City Builder"],
    "샌드박스": ["Sandbox", "Open World", "Crafting", "Building"],
    "식민지": ["Colony Sim", "Base Building", "Simulation", "Survival"],
    "기지건설": ["Base Building", "Survival", "Strategy", "Colony Sim"],
    "자동화": ["Automation", "Factory", "Simulation"],
    
    # 액션/전투 계열
    "액션": ["Action", "Action-Adventure", "Hack and Slash"],
    "슈팅": ["Shooter", "FPS", "Third-Person Shooter"],
    "격투": ["Fighting", "Beat 'em up"],
    
    # RPG/스토리 계열
    "rpg": ["RPG", "JRPG", "Action RPG", "CRPG"],
    "롤플레잉": ["RPG", "Role-Playing"],
    "스토리": ["Adventure", "Visual Novel", "Narrative", "Story Rich"],
    "어드벤처": ["Adventure", "Action-Adventure"],
    
    # 전략 계열
    "전략": ["Strategy", "Turn-Based Strategy", "Real-Time Strategy", "4X"],
    "턴제": ["Turn-Based", "Turn-Based Strategy", "Tactical"],
    
    # 특수 장르
    "로그라이크": ["Roguelike", "Roguelite"],
    "메트로배니아": ["Metroidvania", "Platformer"],
    "소울라이크": ["Souls-like", "Action RPG", "Difficult"],
    "플랫폼": ["Platformer", "2D Platformer", "3D Platformer"],
    "퍼즐": ["Puzzle", "Puzzle Platformer"],
    "호러": ["Horror", "Psychological Horror", "Survival Horror"],
    "공포": ["Horror", "Survival Horror"],
    
    # 분위기/테마
    "인디": ["Indie"],
    "힐링": ["Relaxing", "Casual", "Cozy"],
    "오픈월드": ["Open World", "Exploration"],
    "협동": ["Co-op", "Multiplayer"],
    "멀티": ["Multiplayer", "Online Co-Op", "PvP"],
    
    # 테마
    "우주": ["Space", "Sci-fi"],
    "중세": ["Medieval", "Fantasy"],
    "판타지": ["Fantasy", "Magic"],
}

# ============== 제외 장르 ==============
EXCLUDED_GENRES: List[str] = [
    "Utilities", "Software", "Video Production", "Photo Editing",
    "Audio Production", "Design & Illustration", "Web Publishing",
    "Education", "Accounting", "Animation & Modeling", "Game Development",
    "Tutorial", "Documentary"
]

# ============== Pydantic 요청/응답 모델 ==============
class SearchRequest(BaseModel):
    query: str
    top_k: int = 10

class GameResult(BaseModel):
    app_id: str
    name: str
    genres: str
    developer: str
    description: str
    final_score: float
    status: str
    similarity: float
    is_genre_match: bool
    is_exact_match: bool
    matched_intents: List[Dict[str, str]]
    scores: Dict[str, int]

# ============== v4.0 인텐트 데이터 클래스 ==============
@dataclass
class ExtractedIntent:
    # 1. Guardrail
    is_game_search: bool = True
    rejection_reason: str = ""
    
    # 2. 압축 쿼리
    summary_query: str = ""
    
    # 3. 지표 (무제한)
    metrics: List[str] = field(default_factory=list)
    
    # 4. 코어 장르
    core_genres: List[str] = field(default_factory=list)
    
    def get_intent_objects(self) -> List[Dict[str, str]]:
        return [{"id": m, "name": METRIC_KOREAN.get(m, m)} for m in self.metrics]

# ============== 재시도 데코레이터 ==============
def retry_on_failure(max_retries: int = MAX_RETRIES, delay_base: float = RETRY_DELAY_BASE):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (RateLimitError, APITimeoutError, APIError) as e:
                    last_exception = e
                    wait_time = delay_base * (2 ** attempt)
                    logger.warning(f"API error, retrying in {wait_time}s")
                    time.sleep(wait_time)
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                    raise
            if last_exception:
                raise last_exception
            return None
        return wrapper
    return decorator

# ============== 🔥 v4.0 GPT 인텐트 추출 ==============
@retry_on_failure()
def extract_intent_with_gpt(query: str) -> Dict[str, Any]:
    """
    v4.0 GPT 인텐트 추출
    
    반환 스키마:
    - is_game_search: 게임 검색인지
    - summary_query: 벡터 검색용 압축 쿼리
    - metrics: 관련 지표 (무제한)
    - core_genres: 코어 장르
    """
    
    prompt = f"""당신은 게임 추천 서비스의 쿼리 분석 전문가입니다.

사용자 입력: "{query}"

아래 JSON 스키마로 분석 결과를 반환하세요:

{{
    "is_game_search": true/false,
    "rejection_reason": "",
    "summary_query": "",
    "metrics": [],
    "core_genres": []
}}

**필드 설명:**

1. is_game_search: 게임 추천/검색 관련이면 true, 아니면 false
   - true: "림월드 같은 게임", "스토리 좋은 RPG", "어려운 로그라이크"
   - false: "오늘 점심 뭐 먹지", "파이썬 코드 짜줘", "내일 날씨"

2. rejection_reason: is_game_search가 false일 때 이유 (한글)

3. summary_query: 벡터 검색에 최적화된 핵심 문장 (20자 내외)
   - 예: "우주 식민지 건설 생존 시뮬레이션"
   - 예: "스토리 중심 감성 인디 어드벤처"

4. metrics: 관련 감성 지표 (해당되는 것 모두)
   가능한 값: {', '.join(ALL_METRICS)}

5. core_genres: 유저가 원하는 큰 틀의 장르 (한글, 최대 5개)
   가능한 값: 건설, 생존, 관리, 샌드박스, 액션, RPG, 전략, 로그라이크, 퍼즐, 호러, 인디, 오픈월드, 협동 등
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "게임 검색 쿼리 분석 전문가. JSON만 출력."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            timeout=15.0
        )
        
        result = json.loads(response.choices[0].message.content)
        
        # 필드 검증 및 정규화
        result["is_game_search"] = result.get("is_game_search", True)
        result["rejection_reason"] = result.get("rejection_reason", "")
        result["summary_query"] = result.get("summary_query", query)[:50]
        
        metrics = result.get("metrics", [])
        if isinstance(metrics, str):
            metrics = [metrics]
        result["metrics"] = [m for m in metrics if m in ALL_METRICS]
        
        core_genres = result.get("core_genres", [])
        if isinstance(core_genres, str):
            core_genres = [core_genres]
        result["core_genres"] = core_genres[:5]
        
        return result
        
    except Exception as e:
        logger.warning(f"GPT extraction failed: {e}")
        return {
            "is_game_search": True,
            "rejection_reason": "",
            "summary_query": query,
            "metrics": [],
            "core_genres": []
        }

# ============== 로컬 장르 추출 (보조) ==============
def extract_genres_local(query: str) -> List[str]:
    """쿼리에서 로컬로 장르 키워드 추출"""
    query_lower = query.lower()
    found_genres = []
    
    for keyword in CORE_GENRE_MAPPING.keys():
        if keyword in query_lower:
            found_genres.append(keyword)
    
    return found_genres

# ============== v4.0 인텐트 추출 메인 ==============
def extract_user_intent(query: str) -> ExtractedIntent:
    """v4.0 인텐트 추출 메인 함수"""
    intent = ExtractedIntent()
    
    # 1. GPT로 인텐트 추출
    gpt_result = extract_intent_with_gpt(query)
    
    # 2. Guardrail 체크
    intent.is_game_search = gpt_result.get("is_game_search", True)
    intent.rejection_reason = gpt_result.get("rejection_reason", "")
    
    if not intent.is_game_search:
        logger.info(f"[Guardrail] Not a game search: {intent.rejection_reason}")
        return intent
    
    # 3. 압축 쿼리
    intent.summary_query = gpt_result.get("summary_query", query)
    
    # 4. 지표 (무제한)
    intent.metrics = gpt_result.get("metrics", [])
    
    # 5. 코어 장르 (GPT + 로컬 보완)
    gpt_genres = gpt_result.get("core_genres", [])
    local_genres = extract_genres_local(query)
    
    # 합치고 중복 제거
    all_genres = list(dict.fromkeys(gpt_genres + local_genres))
    intent.core_genres = all_genres[:5]
    
    logger.info(f"[Intent] summary='{intent.summary_query}', genres={intent.core_genres}, metrics={intent.metrics[:5]}")
    
    return intent

# ============== 🔥 장르 매칭 (점수에 영향 없음!) ==============
# ============== 🔥 장르 매칭 수정판 ==============
def check_genre_match(game_genres: str, core_genres: List[str]) -> bool:
    if not core_genres:
        return True 
    
    game_genres_lower = game_genres.lower()
    
    for user_genre in core_genres:
        # 1. 유저가 입력한 한글 단어 자체가 DB 장르에 있는지 확인
        if user_genre.lower() in game_genres_lower:
            return True
            
        # 2. 영어로 매핑된 장르가 있는지도 확인
        steam_genres = CORE_GENRE_MAPPING.get(user_genre, [user_genre])
        for steam_genre in steam_genres:
            if steam_genre.lower() in game_genres_lower:
                return True
                
    return False

# ============== 🔥 Exact Match 계산 (시리즈물 도배 방지) ==============
def calculate_exact_match_boost(game_name: str, query: str) -> Tuple[int, bool]:
    """
    Exact Match 보너스 계산
    
    규칙:
    1. query가 15자 이내 + name과 완전 일치 → +50점, is_exact=True
    2. query가 name에 포함 → 최대 +5점, is_exact=False
    3. 그 외 → 0점
    
    Returns:
        (boost_points, is_exact_match)
    """
    query_clean = query.strip().lower()
    name_clean = game_name.strip().lower()
    
    # 1. Exact Match: 15자 이내 + 완전 일치
    if len(query_clean) <= EXACT_MATCH_QUERY_MAX_LEN:
        if query_clean == name_clean:
            return EXACT_MATCH_BOOST, True
        
        # 공백 제거 후 비교
        if query_clean.replace(" ", "") == name_clean.replace(" ", ""):
            return EXACT_MATCH_BOOST, True
    
    # 2. Partial Match: 쿼리가 이름에 포함 (최대 +5점)
    if query_clean in name_clean:
        return PARTIAL_MATCH_BOOST_MAX, False
    
    # 3. 이름의 핵심 단어가 쿼리에 포함 (최대 +3점)
    name_words = set(name_clean.split())
    query_words = set(query_clean.split())
    
    # 2글자 이상 단어만
    name_words = {w for w in name_words if len(w) >= 2}
    query_words = {w for w in query_words if len(w) >= 2}
    
    if name_words and query_words:
        overlap = len(name_words & query_words)
        if overlap >= 1:
            return min(3, overlap * 2), False
    
    return 0, False

# ============== 유사도 스케일링 ==============
def scale_similarity(similarity: float) -> float:
    """
    코사인 유사도 0.45~0.85 → 0~100 스케일링
    """
    if similarity <= SIMILARITY_MIN:
        return 0.0
    if similarity >= SIMILARITY_MAX:
        return 100.0
    
    return (similarity - SIMILARITY_MIN) / (SIMILARITY_MAX - SIMILARITY_MIN) * 100

# ============== S/A/B 티어 가중치 맵 ==============
def get_tier_weight_map(genres: str) -> Dict[str, float]:
    """장르별 S/A/B 티어 가중치 생성"""
    weight_map = {m: 1.0 for m in ALL_METRICS}
    
    for genre in [g.strip() for g in genres.split(",")]:
        for genre_key, tier_config in GENRE_WEIGHTS.items():
            if genre_key.lower() in genre.lower():
                for metric in tier_config.get("S", []):
                    weight_map[metric] = max(weight_map[metric], WEIGHT_S_TIER)
                for metric in tier_config.get("A", []):
                    weight_map[metric] = max(weight_map[metric], WEIGHT_A_TIER)
                for metric in tier_config.get("B", []):
                    weight_map[metric] = max(weight_map[metric], WEIGHT_B_TIER)
    
    return weight_map

# ============== 🔥🔥🔥 v4.0 최종 점수 계산 (Limit Break) ==============
def calculate_final_score(
    game_name: str,
    genres: str,
    scores: Dict[str, int],
    similarity: float,
    query: str,
    intent: ExtractedIntent
) -> Tuple[float, str, bool, bool]:
    """
    v4.0 Limit Break 점수 계산
    
    공식: (메타데이터 × 0.8) + (유사도 보정 × 0.4) + Exact Match 보너스
    
    Returns:
        (final_score, status, is_genre_match, is_exact_match)
    """
    
    # 1. 메타데이터 점수 (S/A/B 가중 평균)
    weight_map = get_tier_weight_map(genres)
    
    weighted_sum = 0.0
    total_weight = 0.0
    for metric in ALL_METRICS:
        if metric in scores:
            w = weight_map.get(metric, 1.0)
            weighted_sum += scores[metric] * w
            total_weight += w
    
    metadata_score = weighted_sum / total_weight if total_weight > 0 else 50.0
    
    # 2. 유사도 보정 점수 (0~100 스케일)
    similarity_scaled = scale_similarity(similarity)
    
    # 3. 🔥 Limit Break 공식
    base_score = (metadata_score * METADATA_WEIGHT) + (similarity_scaled * SIMILARITY_WEIGHT)
    
    # 4. Exact Match 보너스
    exact_boost, is_exact_match = calculate_exact_match_boost(game_name, query)
    
    # 5. 최종 점수 (100점 돌파 허용!)
    final_score = base_score + exact_boost
    
    # 6. 장르 매칭 (점수에 영향 없음!)
    is_genre_match = check_genre_match(genres, intent.core_genres)
    
    # 7. Status 결정
    if final_score >= LEGENDARY_THRESHOLD:
        status = "LEGENDARY"
    elif final_score >= 80:
        status = "MYTHIC"
    elif final_score >= 65:
        status = "EPIC"
    elif final_score >= 50:
        status = "RARE"
    elif final_score >= DROP_THRESHOLD:
        status = "UNCOMMON"
    else:
        status = "DROP"
    
    return final_score, status, is_genre_match, is_exact_match

# ============== 유틸리티 함수들 ==============
def is_excluded_genre(genres: str) -> bool:
    if not genres:
        return False
    return any(ex.lower() in genres.lower() for ex in EXCLUDED_GENRES)

def parse_scores_from_row(row) -> Dict[str, int]:
    return {
        "mania_score": row[5] or 50,
        "story_depth": row[6] or 50,
        "originality": row[7] or 50,
        "difficulty": row[8] or 50,
        "art_style": row[9] or 50,
        "replay_value": row[10] or 50,
        "indie_spirit": row[11] or 50,
        "character_appeal": row[12] or 50,
        "user_friendliness": row[13] or 50,
        "addictiveness": row[14] or 50,
        "emotional_impact": row[15] or 50,
        "atmosphere_intensity": row[16] or 50,
        "soundtrack_prominence": row[17] or 50,
        "gem_potential": row[18] or 50
    }

# ============== 임베딩 생성 ==============
@retry_on_failure()
def create_query_embedding(query: str) -> List[float]:
    """summary_query로 1536차원 임베딩 생성"""
    embed_response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query,
        timeout=15.0
    )
    return embed_response.data[0].embedding

# ============== 벡터 검색 ==============
def execute_vector_search(query_vector: List[float], limit: int = 100) -> List:
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT app_id, name, genres, developer, description,
                       mania_score, story_depth, originality, difficulty, art_style,
                       replay_value, indie_spirit, character_appeal, user_friendliness,
                       addictiveness, emotional_impact, atmosphere_intensity,
                       soundtrack_prominence, gem_potential,
                       1 - (embedding <=> CAST(:vec AS vector)) as similarity
                FROM games
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT :lim
            """), {"vec": str(query_vector), "lim": limit})
            return list(result)
    except SQLAlchemyError as e:
        logger.error(f"Vector search failed: {e}")
        return []

# ============== Fallback: 인기 게임 ==============
def get_popular_games(limit: int = 10, core_genres: List[str] = None) -> List[Dict]:
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT app_id, name, genres, developer, description,
                       mania_score, story_depth, originality, difficulty, art_style,
                       replay_value, indie_spirit, character_appeal, user_friendliness,
                       addictiveness, emotional_impact, atmosphere_intensity,
                       soundtrack_prominence, gem_potential
                FROM games
                WHERE gem_potential >= 70
                ORDER BY gem_potential DESC
                LIMIT :lim
            """), {"lim": limit * 3})
            
            games = []
            for row in result:
                genres = row[2] or ""
                if is_excluded_genre(genres):
                    continue
                
                is_match = check_genre_match(genres, core_genres) if core_genres else True
                
                games.append({
                    "app_id": row[0],
                    "name": row[1],
                    "genres": genres,
                    "developer": row[3] or "Unknown",
                    "description": row[4] or "",
                    "final_score": float(row[18] or 70),
                    "status": "RARE",
                    "similarity": 0.5,
                    "is_genre_match": is_match,
                    "is_exact_match": False,
                    "matched_intents": [],
                    "scores": parse_scores_from_row(row),
                    "is_fallback": True
                })
                
                if len(games) >= limit:
                    break
            
            return games
    except Exception as e:
        logger.error(f"Popular games failed: {e}")
        return []

# ============== 🔥🔥🔥 v4.0 메인 검색 함수 ==============
def search_games(
    query: str,
    intent: ExtractedIntent,
    top_k: int = 10
) -> Dict:
    """
    v4.0 메인 검색
    
    반환:
    - main_results: 장르 매칭 O
    - alternative_results: 장르 매칭 X (점수는 높음)
    """
    
    main_results = []
    alternative_results = []
    seen_ids = set()
    
    # 🔥 벡터 검색 (summary_query 사용!)
    logger.info(f"[Search] Vector search: '{intent.summary_query}'")
    
    try:
        query_vector = create_query_embedding(intent.summary_query)
        candidates = execute_vector_search(query_vector, limit=150)
        
        for row in candidates:
            app_id = row[0]
            if app_id in seen_ids:
                continue
            
            genres = row[2] or ""
            if is_excluded_genre(genres):
                continue
            
            scores = parse_scores_from_row(row)
            similarity = float(row[19]) if len(row) > 19 else 0.5
            
            # 🔥 v4.0 점수 계산
            final_score, status, is_genre_match, is_exact_match = calculate_final_score(
                game_name=row[1],
                genres=genres,
                scores=scores,
                similarity=similarity,
                query=query,
                intent=intent
            )
            
            # DROP 필터링
            if status == "DROP":
                continue
            
            game_result = {
                "app_id": app_id,
                "name": row[1],
                "genres": genres,
                "developer": row[3] or "Unknown",
                "description": row[4] or "",
                "final_score": round(final_score, 2),
                "status": status,
                "similarity": round(similarity, 4),
                "is_genre_match": is_genre_match,
                "is_exact_match": is_exact_match,
                "matched_intents": intent.get_intent_objects(),
                "scores": scores
            }
            
            # 🔥 장르별 분류 (점수에 영향 없음!)
            if is_exact_match or is_genre_match:
                game_result["is_genre_match"] = True
                main_results.append(game_result)
            else:
                alternative_results.append(game_result)
            
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
    
    # 점수순 정렬
    main_results.sort(key=lambda x: (-x["is_exact_match"], -x["final_score"]))
    alternative_results.sort(key=lambda x: -x["final_score"])
    
    # Fallback
    if len(main_results) < MIN_RESULTS:
        logger.info(f"[Search] Fallback: only {len(main_results)} main results")
        fallback = get_popular_games(limit=top_k, core_genres=intent.core_genres)
        
        for fg in fallback:
            if fg["app_id"] not in seen_ids and len(main_results) < top_k:
                main_results.append(fg)
                seen_ids.add(fg["app_id"])
    
    logger.info(f"[Search] Done: {len(main_results)} main, {len(alternative_results)} alt")
    
    return {
        "success": True,
        "main_results": main_results[:top_k],
        "alternative_results": alternative_results[:5],
        "total_found": len(main_results) + len(alternative_results)
    }

# ============== API 엔드포인트 ==============
@app.get("/")
def root():
    return {
        "message": "Hidden Gem API v4.0 - Architecture Overhaul",
        "version": "4.0",
        "scoring_formula": "(metadata × 0.8) + (similarity × 0.4) + exact_match_boost",
        "max_score": "120 (Limit Break)",
        "features": [
            "🛡️ is_game_search guardrail",
            "📝 summary_query compression",
            "🔥 Limit Break scoring (100점 돌파)",
            "🎯 main_results / alternative_results 분리",
            "⚔️ Exact Match (+50) / Partial Match (+5)"
        ]
    }

@app.get("/health")
def health_check():
    try:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM games")).scalar()
        return {"status": "healthy", "game_count": count, "version": "4.0"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
def search_endpoint(request: SearchRequest):
    """
    🔥 v4.0 검색 API
    
    응답 스키마:
    - main_results: 장르 매칭 게임
    - alternative_results: 장르 다르지만 추천
    """
    try:
        # 1. 인텐트 추출
        intent = extract_user_intent(request.query)
        
        # 🛡️ 2. Guardrail (Early Exit)
        if not intent.is_game_search:
            logger.info(f"[Guardrail] Rejected: {intent.rejection_reason}")
            return {
                "success": False,
                "is_game_search": False,
                "error": "게임과 관련된 질문을 해주세요! 🎮",
                "rejection_reason": intent.rejection_reason,
                "suggestion": "예: '림월드 같은 건설 생존 게임', '스토리 좋은 인디 RPG'",
                "main_results": [],
                "alternative_results": [],
                "intents": []
            }
        
        # 3. 검색 실행
        search_result = search_games(
            query=request.query,
            intent=intent,
            top_k=request.top_k
        )
        
        # 4. 응답 구성
        return {
            "success": True,
            "is_game_search": True,
            "query": request.query,
            "summary_query": intent.summary_query,
            "intents": intent.get_intent_objects(),
            "core_genres": intent.core_genres,
            "main_results": search_result["main_results"],
            "alternative_results": search_result["alternative_results"],
            "total_found": search_result["total_found"],
            "algorithm_version": "v4.0",
            "scoring_info": {
                "formula": "(metadata×0.8) + (similarity×0.4) + exact_boost",
                "legendary_threshold": LEGENDARY_THRESHOLD,
                "exact_match_boost": EXACT_MATCH_BOOST
            }
        }
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        
        fallback = get_popular_games(limit=request.top_k)
        return {
            "success": True,
            "is_game_search": True,
            "query": request.query,
            "main_results": fallback,
            "alternative_results": [],
            "total_found": len(fallback),
            "algorithm_version": "v4.0",
            "fallback_reason": str(e)[:100],
            "intents": []
        }

@app.get("/games/top")
def get_top_games(limit: int = 20):
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT app_id, name, genres, developer, description, gem_potential
                FROM games ORDER BY gem_potential DESC LIMIT :limit
            """), {"limit": limit})
            games = [{"app_id": r[0], "name": r[1], "genres": r[2], "developer": r[3], "description": r[4], "gem_potential": r[5]} for r in result]
        return {"games": games}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/games/{app_id}")
def get_game_detail(app_id: str):
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT app_id, name, genres, developer, description,
                       mania_score, story_depth, originality, difficulty, art_style,
                       replay_value, indie_spirit, character_appeal, user_friendliness,
                       addictiveness, emotional_impact, atmosphere_intensity,
                       soundtrack_prominence, gem_potential
                FROM games WHERE app_id = :aid
            """), {"aid": app_id})
            row = result.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Game not found")
            return {
                "app_id": row[0],
                "name": row[1],
                "genres": row[2],
                "developer": row[3],
                "description": row[4],
                "scores": parse_scores_from_row(row)
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/debug/intent")
def debug_intent(request: SearchRequest):
    """인텐트 추출 디버깅"""
    intent = extract_user_intent(request.query)
    return {
        "query": request.query,
        "is_game_search": intent.is_game_search,
        "rejection_reason": intent.rejection_reason,
        "summary_query": intent.summary_query,
        "metrics": intent.metrics,
        "intent_objects": intent.get_intent_objects(),
        "core_genres": intent.core_genres
    }

@app.post("/debug/score")
def debug_score(request: SearchRequest):
    """점수 계산 디버깅"""
    try:
        intent = extract_user_intent(request.query)
        
        if not intent.is_game_search:
            return {"error": "Not a game search", "reason": intent.rejection_reason}
        
        query_vector = create_query_embedding(intent.summary_query)
        candidates = execute_vector_search(query_vector, limit=10)
        
        debug_results = []
        for row in candidates:
            scores = parse_scores_from_row(row)
            similarity = float(row[19])
            
            final_score, status, is_genre_match, is_exact_match = calculate_final_score(
                game_name=row[1],
                genres=row[2] or "",
                scores=scores,
                similarity=similarity,
                query=request.query,
                intent=intent
            )
            
            # 점수 구성 분해
            weight_map = get_tier_weight_map(row[2] or "")
            weighted_sum = sum(scores[m] * weight_map.get(m, 1.0) for m in scores)
            total_weight = sum(weight_map.get(m, 1.0) for m in scores)
            metadata_score = weighted_sum / total_weight if total_weight > 0 else 50
            similarity_scaled = scale_similarity(similarity)
            exact_boost, _ = calculate_exact_match_boost(row[1], request.query)
            
            debug_results.append({
                "name": row[1],
                "genres": row[2],
                "similarity_raw": round(similarity, 4),
                "similarity_scaled": round(similarity_scaled, 2),
                "metadata_score": round(metadata_score, 2),
                "metadata_contribution": round(metadata_score * METADATA_WEIGHT, 2),
                "similarity_contribution": round(similarity_scaled * SIMILARITY_WEIGHT, 2),
                "exact_match_boost": exact_boost,
                "final_score": round(final_score, 2),
                "status": status,
                "is_genre_match": is_genre_match,
                "is_exact_match": is_exact_match
            })
        
        return {
            "query": request.query,
            "summary_query": intent.summary_query,
            "core_genres": intent.core_genres,
            "formula": f"(meta×{METADATA_WEIGHT}) + (sim×{SIMILARITY_WEIGHT}) + exact_boost",
            "results": debug_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============== 서버 실행 ==============
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
