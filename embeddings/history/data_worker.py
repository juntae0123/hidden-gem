import os
import json
from typing import List, Dict, Optional, Tuple
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from dotenv import load_dotenv, find_dotenv
from openai import OpenAI

# 환경 변수 로드
load_dotenv(find_dotenv())

# 초기화
app = FastAPI(title="Hidden Gem API", version="2.2")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DB_URL = os.getenv("DATABASE_URL")
engine = create_engine(DB_URL)

# CORS 설정
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ============== 상수 정의 ==============
# 패치: DROP 컷오프 기본 65점, 최소 마지노선 60점 (동적 완화용)
DROP_THRESHOLD = 65
MIN_FALLBACK_THRESHOLD = 60 

MANIAC_AVG_THRESHOLD = 65
MANIAC_S_TIER_THRESHOLD = 85

# 부스팅 설정
INTENT_BASE_WEIGHT = 1.5      
BOOST_CAP = 1.7               
MAX_TOTAL_WEIGHT = 2.55       

ALL_METRICS = [
    "mania_score", "story_depth", "originality", "difficulty", "art_style",
    "replay_value", "indie_spirit", "character_appeal", "user_friendliness",
    "addictiveness", "emotional_impact", "atmosphere_intensity",
    "soundtrack_prominence", "gem_potential"
]

GENRE_WEIGHTS = {
    "Action": {"S": ["addictiveness", "difficulty"], "A": ["replay_value", "art_style", "mania_score"], "B": ["user_friendliness", "originality", "atmosphere_intensity", "character_appeal", "soundtrack_prominence"]},
    "RPG": {"S": ["story_depth", "character_appeal"], "A": ["replay_value", "originality", "emotional_impact"], "B": ["art_style", "soundtrack_prominence", "atmosphere_intensity", "difficulty", "addictiveness"]},
    "Adventure": {"S": ["story_depth", "atmosphere_intensity"], "A": ["emotional_impact", "art_style", "originality"], "B": ["soundtrack_prominence", "character_appeal", "user_friendliness", "indie_spirit", "gem_potential"]},
    "Strategy": {"S": ["difficulty", "replay_value"], "A": ["originality", "addictiveness", "user_friendliness"], "B": ["mania_score", "story_depth", "art_style", "atmosphere_intensity", "indie_spirit"]},
    "Simulation": {"S": ["replay_value", "addictiveness"], "A": ["user_friendliness", "originality", "art_style"], "B": ["atmosphere_intensity", "mania_score", "indie_spirit", "character_appeal", "story_depth"]},
    "Indie": {"S": ["indie_spirit", "originality"], "A": ["art_style", "emotional_impact", "gem_potential"], "B": ["story_depth", "atmosphere_intensity", "soundtrack_prominence", "character_appeal", "user_friendliness"]},
    "Horror": {"S": ["atmosphere_intensity", "emotional_impact"], "A": ["story_depth", "soundtrack_prominence", "art_style"], "B": ["difficulty", "originality", "character_appeal", "mania_score", "indie_spirit"]}
}

EXCLUDED_GENRES = [
    "Utilities", "Software", "Video Production", "Photo Editing",
    "Audio Production", "Design & Illustration", "Web Publishing",
    "Education", "Accounting", "Animation & Modeling"
]

# ============== 요청/응답 모델 ==============
class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    include_maniac: bool = True

class GameResult(BaseModel):
    app_id: str
    name: str
    genres: str
    developer: str
    description: str
    final_score: float
    status: str
    similarity: float
    matched_intents: List[str]
    boost_info: Dict[str, float]
    boost_reason: str  # 프론트엔드 노출용 친절한 설명 추가
    scores: Dict[str, int]

class SearchResponse(BaseModel):
    query: str
    intents: List[str]
    gems: List[GameResult]
    maniacs: List[GameResult]
    total_candidates: int
    algorithm_version: str

# ============== 1단계: 의도 추출 엔진 ==============
def extract_user_intent(query: str) -> List[str]:
    prompt = f"""
    사용자의 게임 검색 쿼리를 분석하여 가장 중요한 게임 평가 지표를 추출하세요.
    사용 가능한 지표 목록:
    - mania_score: 마니아적 매력, 컬트적 인기
    - story_depth: 스토리 깊이, 서사
    - originality: 독창성, 참신함
    - difficulty: 난이도, 도전적
    - art_style: 아트 스타일, 그래픽
    - replay_value: 리플레이 가치, 회차
    - indie_spirit: 인디 감성
    - character_appeal: 캐릭터 매력
    - user_friendliness: 유저 친화성, 접근성
    - addictiveness: 중독성
    - emotional_impact: 감정적 임팩트, 감동, 여운
    - atmosphere_intensity: 분위기 몰입도
    - soundtrack_prominence: 음악, BGM, OST
    - gem_potential: 숨겨진 명작 잠재력
    
    쿼리: "{query}"
    위 지표 중 쿼리와 가장 관련 있는 1~4개를 JSON 형식으로 반환하세요. 형식: {{"intents": ["지표1", "지표2"]}}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "게임 검색 의도 분석 전문가입니다. JSON만 출력하세요."},
                {"role": "user", "content": prompt}
            ]
        )
        result = json.loads(response.choices[0].message.content)
        intents = result.get("intents", [])
        if isinstance(intents, str): intents = [intents]
        return [i for i in intents if i in ALL_METRICS][:4]
    except Exception:
        return []

# ============== 2단계: 장르별 가중치 계산 ==============
def get_genre_weight_map(genres: str) -> Dict[str, float]:
    weight_map = {m: 1.0 for m in ALL_METRICS}
    for genre in [g.strip() for g in genres.split(",")]:
        for genre_key, tier_config in GENRE_WEIGHTS.items():
            if genre_key.lower() in genre.lower():
                for m in tier_config.get("S", []): weight_map[m] = max(weight_map[m], 1.5)
                for m in tier_config.get("A", []): weight_map[m] = max(weight_map[m], 1.3)
                for m in tier_config.get("B", []): weight_map[m] = max(weight_map[m], 1.1)
    return weight_map

def get_s_tier_metrics(genres: str) -> List[str]:
    s_tier = set()
    for genre in [g.strip() for g in genres.split(",")]:
        for genre_key, tier_config in GENRE_WEIGHTS.items():
            if genre_key.lower() in genre.lower():
                s_tier.update(tier_config.get("S", []))
    return list(s_tier)

# ============== 3단계: 동적 가중치 부스팅 ==============
def apply_dynamic_boosting(scores: Dict[str, int], weight_map: Dict[str, float], user_intents: List[str]) -> Tuple[Dict[str, float], Dict[str, float]]:
    boost_info = {}
    if not user_intents:
        return weight_map, boost_info
        
    boosted_map = weight_map.copy()
    for metric in user_intents:
        if metric in boosted_map:
            boosted_map[metric] = weight_map.get(metric, 1.0) * INTENT_BASE_WEIGHT
            boost_info[metric] = {"base": weight_map.get(metric, 1.0), "after_base_boost": boosted_map[metric]}

    group_a_metrics = [m for m in user_intents if m in scores]
    group_b_metrics = [m for m in ALL_METRICS if m not in user_intents and m in scores]
    
    if not group_a_metrics or len(group_b_metrics) < 2:
        return boosted_map, boost_info

    group_a_avg = sum([scores[m] * boosted_map[m] for m in group_a_metrics]) / len(group_a_metrics)
    group_b_contributions = sorted([scores[m] * boosted_map[m] for m in group_b_metrics], reverse=True)
    group_b_2nd = group_b_contributions[1] if len(group_b_contributions) > 1 else group_b_contributions[0]

    additional_boost = 1.0
    if group_a_avg < group_b_2nd and group_a_avg > 0:
        required_boost = group_b_2nd / group_a_avg
        additional_boost = min(BOOST_CAP, max(1.0, required_boost))
        
        for metric in group_a_metrics:
            new_weight = boosted_map[metric] * additional_boost
            boosted_map[metric] = min(MAX_TOTAL_WEIGHT, new_weight)
            boost_info[metric]["additional_boost"] = additional_boost
            boost_info[metric]["final_weight"] = boosted_map[metric]
            
    return boosted_map, boost_info

# ============== 4단계: 점수 계산 및 상태 분류 ==============
def calculate_final_score(scores: Dict[str, int], genres: str, user_intents: List[str]) -> Tuple[float, str, Dict]:
    weight_map = get_genre_weight_map(genres)
    boosted_map, boost_info = apply_dynamic_boosting(scores, weight_map, user_intents)

    weighted_scores = [scores[m] * boosted_map.get(m, 1.0) for m in ALL_METRICS if m in scores]
    total_weight = sum([boosted_map.get(m, 1.0) for m in ALL_METRICS if m in scores])
    
    base_score = sum(weighted_scores) / total_weight if total_weight > 0 else 50.0

    synergy_bonus = 0
    s_tier_metrics = get_s_tier_metrics(genres)
    if s_tier_metrics and all(scores.get(m, 0) >= MANIAC_S_TIER_THRESHOLD for m in s_tier_metrics):
        synergy_bonus += 4 if user_intents else 8
        
    if user_intents and all(scores.get(m, 0) >= 80 for m in user_intents):
        synergy_bonus += len(user_intents) * 3

    final_score = base_score + synergy_bonus

    if final_score < DROP_THRESHOLD:
        plain_avg = sum(scores.values()) / len(scores) if scores else 0
        if s_tier_metrics and all(scores.get(m, 0) >= MANIAC_S_TIER_THRESHOLD for m in s_tier_metrics) and plain_avg < MANIAC_AVG_THRESHOLD:
            status = "MANIAC"
        else:
            status = "DROP"
    else:
        status = "GEM"

    debug_info = {"base_score": base_score, "synergy_bonus": synergy_bonus, "final_score": final_score, "boost_info": boost_info}
    return final_score, status, debug_info

def is_excluded_genre(genres: str) -> bool:
    return any(excluded.lower() in genres.lower() for excluded in EXCLUDED_GENRES)

def parse_scores_from_row(row) -> Dict[str, int]:
    return {m: row[i+5] or 50 for i, m in enumerate(ALL_METRICS)}

# ============== API 엔드포인트 ==============
@app.post("/search", response_model=SearchResponse)
def hybrid_search(request: SearchRequest):
    try:
        user_intents = extract_user_intent(request.query)
        query_vector = client.embeddings.create(model="text-embedding-3-small", input=request.query).data[0].embedding
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT app_id, name, genres, developer, description,
                       mania_score, story_depth, originality, difficulty, art_style,
                       replay_value, indie_spirit, character_appeal, user_friendliness,
                       addictiveness, emotional_impact, atmosphere_intensity,
                       soundtrack_prominence, gem_potential,
                       1 - (embedding <=> :vec::vector) as similarity
                FROM games ORDER BY embedding <=> :vec::vector LIMIT 50
            """), {"vec": str(query_vector)})
            candidates = list(result)

        evaluated_games = []
        
        for row in candidates:
            genres = row[2] or ""
            if is_excluded_genre(genres): continue
            
            scores = parse_scores_from_row(row)
            final_score, status, debug = calculate_final_score(scores, genres, user_intents)
            
            # 프론트엔드용 친절한 설명 (Boost Reason) 생성
            boost_reasons = []
            for metric, info in debug.get("boost_info", {}).items():
                if info.get("additional_boost", 1.0) > 1.0:
                    boost_reasons.append(f"[{metric}] 취향 집중 반영 (가중치 {round(info['final_weight'], 2)}배 폭발! 🚀)")
            boost_reason_str = " | ".join(boost_reasons)

            evaluated_games.append({
                "app_id": row[0], "name": row[1], "genres": genres,
                "developer": row[3] or "Unknown", "description": row[4] or "",
                "final_score": round(final_score, 2), "status": status,
                "similarity": round(float(row[19]), 4), "matched_intents": user_intents,
                "boost_info": debug.get("boost_info", {}), "boost_reason": boost_reason_str,
                "scores": scores
            })

        gems = [g for g in evaluated_games if g["status"] == "GEM"]
        maniacs = [g for g in evaluated_games if g["status"] == "MANIAC"]

        # 동적 컷오프 완화 (심폐소생술 로직)
        if len(gems) < 5:
            resurrected = [g for g in evaluated_games if g["status"] == "DROP" and MIN_FALLBACK_THRESHOLD <= g["final_score"] < DROP_THRESHOLD]
            for r in resurrected:
                r["status"] = "GEM"
                r["boost_reason"] = "💡 검색 결과가 적어 기준을 완화하여 발굴된 아까운 보석입니다! " + r["boost_reason"]
                gems.append(r)

        gems.sort(key=lambda x: x["final_score"], reverse=True)
        maniacs.sort(key=lambda x: x["final_score"], reverse=True)

        return {
            "query": request.query, "intents": user_intents,
            "gems": gems[:request.top_k],
            "maniacs": maniacs[:5] if request.include_maniac else [],
            "total_candidates": len(candidates),
            "algorithm_version": "v2.2-Dynamic-UX"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)