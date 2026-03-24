import os
import json
import requests
import time
import random
import re
from openai import OpenAI
from sqlalchemy import create_engine, text
from dotenv import load_dotenv, find_dotenv
from tqdm import tqdm

load_dotenv(find_dotenv())
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DB_URL = os.getenv("DATABASE_URL")
engine = create_engine(DB_URL)

def analyze_and_embed(name, genres, developer, desc):
    """GPT-4o-mini 분석 (지표 누락 및 에러 방지 강화)"""
    rich_text = f"Title: {name}\nDeveloper: {developer}\nGenres: {genres}\nDescription: {desc}"
    
    # 지표 리스트 (이 이름 그대로 JSON을 달라고 강요합니다)
    metrics = [
        "mania_score", "story_depth", "originality", "difficulty", "art_style",
        "replay_value", "indie_spirit", "character_appeal", "user_friendliness",
        "addictiveness", "emotional_impact", "atmosphere_intensity",
        "soundtrack_prominence", "gem_potential"
    ]
    
    prompt = f"""
    Evaluate the game and output ONLY a JSON object with these keys: {', '.join(metrics)}.
    All values must be integers (0-100). Output ONLY valid JSON.
    """
    
    chat_response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={ "type": "json_object" },
        messages=[{"role": "system", "content": prompt}, {"role": "user", "content": rich_text}]
    )
    
    raw_content = chat_response.choices[0].message.content
    scores = json.loads(raw_content)
    
    # 🛑 핵심: GPT가 키를 다르게 줬을 경우를 대비해 '필터링'을 거칩니다.
    # 만약 키가 없으면 0이 아니라 최소 50점이라도 넣거나 에러를 띄워야 합니다.
    final_scores = {}
    for m in metrics:
        # GPT가 대소문자나 오타를 낼 수 있으므로 안전하게 가져오기
        val = scores.get(m, 50) # 기본값을 50으로 설정해 0점 도배 방지
        final_scores[m] = int(val)

    print(f"✅ 분석 완료: {name} (잠재력: {final_scores['gem_potential']})")

    embed_response = client.embeddings.create(model="text-embedding-3-small", input=rich_text)
    return final_scores, embed_response.data[0].embedding

def get_app_ids_by_scraping(limit=5000):
    app_ids = []
    print("🌐 스팀 상점에서 게임 ID 추출 중...")
    while len(app_ids) < limit:
        url = f"https://store.steampowered.com/search/results/?query&start={len(app_ids)}&count=50&term&supportedlang=korean&infinite=1"
        try:
            res = requests.get(url, timeout=10).json()
            found_ids = re.findall(r'data-ds-appid="(\d+)"', res['results_html'])
            if not found_ids: break
            app_ids.extend(found_ids)
            time.sleep(0.5)
        except: break
    return list(set(app_ids))[:limit]

def collect_and_store(limit=5000):
    print("🚀 수집 엔진 가동 (데이터 덮어쓰기 모드)...")
    final_app_ids = get_app_ids_by_scraping(limit=limit)

    saved_count = 0
    for app_id in tqdm(final_app_ids, desc="분석 중"):
        try:
            detail_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=korean"
            res = requests.get(detail_url, timeout=10).json()
            
            if not res or not res.get(str(app_id), {}).get('success'): continue
            data = res[str(app_id)]['data']
            if data.get('type') != 'game' or len(data.get('short_description', "")) < 40: continue

            # AI 분석
            scores, vector = analyze_and_embed(data['name'], 
                                             ", ".join([g['description'] for g in data.get('genres', [])]), 
                                             data.get('developers', ["Unknown"])[0], 
                                             data['short_description'])

            with engine.begin() as conn:
                # 🛑 ON CONFLICT DO UPDATE: 이미 0점으로 들어간 데이터를 진짜 점수로 업데이트!
                query = text("""
                    INSERT INTO games (app_id, name, genres, developer, description, 
                    mania_score, story_depth, originality, difficulty, art_style, 
                    replay_value, indie_spirit, character_appeal, user_friendliness, 
                    addictiveness, emotional_impact, atmosphere_intensity, 
                    soundtrack_prominence, gem_potential, embedding)
                    VALUES (:aid, :n, :g, :d, :desc, :m, :s, :o, :df, :a, :r, :i, :c, :u, :ad, :e, :at, :sp, :gp, :v)
                    ON CONFLICT (app_id) DO UPDATE SET
                    mania_score = EXCLUDED.mania_score,
                    gem_potential = EXCLUDED.gem_potential,
                    story_depth = EXCLUDED.story_depth,
                    originality = EXCLUDED.originality,
                    difficulty = EXCLUDED.difficulty,
                    art_style = EXCLUDED.art_style,
                    replay_value = EXCLUDED.replay_value,
                    indie_spirit = EXCLUDED.indie_spirit,
                    character_appeal = EXCLUDED.character_appeal,
                    user_friendliness = EXCLUDED.user_friendliness,
                    addictiveness = EXCLUDED.addictiveness,
                    emotional_impact = EXCLUDED.emotional_impact,
                    atmosphere_intensity = EXCLUDED.atmosphere_intensity,
                    soundtrack_prominence = EXCLUDED.soundtrack_prominence,
                    embedding = EXCLUDED.embedding
                """)
                conn.execute(query, {
                    "aid": str(app_id), "n": data['name'], "g": ", ".join([g['description'] for g in data.get('genres', [])]),
                    "d": data.get('developers', ["Unknown"])[0], "desc": data['short_description'],
                    "m": scores['mania_score'], "s": scores['story_depth'], "o": scores['originality'],
                    "df": scores['difficulty'], "a": scores['art_style'], "r": scores['replay_value'],
                    "i": scores['indie_spirit'], "c": scores['character_appeal'], "u": scores['user_friendliness'],
                    "ad": scores['addictiveness'], "e": scores['emotional_impact'], "at": scores['atmosphere_intensity'],
                    "sp": scores['soundtrack_prominence'], "gp": scores['gem_potential'], "v": str(vector)
                })
            saved_count += 1
            time.sleep(0.8)
        except Exception as e:
            print(f"❌ 에러: {e}")
            continue

if __name__ == "__main__":
    collect_and_store(limit=5000)