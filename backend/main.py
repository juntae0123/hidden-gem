import os
import json
import requests
import time
import random
from openai import OpenAI
from sqlalchemy import create_engine, text
from dotenv import load_dotenv, find_dotenv
from tqdm import tqdm

# 1. 환경 변수 로드
load_dotenv(find_dotenv())
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
STEAM_API_KEY = os.getenv("STEAM_API_KEY")

DB_URL = os.getenv("DATABASE_URL")
engine = create_engine(DB_URL)

def analyze_and_embed(name, genres, developer, desc):
    rich_text = f"Title: {name}\nDeveloper: {developer}\nGenres: {genres}\nDescription: {desc}"
    
    chat_response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={ "type": "json_object" },
        messages=[
            {"role": "system", "content": "You are a professional game critic. Output ONLY JSON."},
            {"role": "user", "content": rich_text}
        ]
    )
    scores = json.loads(chat_response.choices[0].message.content)

    embed_response = client.embeddings.create(
        model="text-embedding-3-small",
        input=rich_text
    )
    return scores, embed_response.data[0].embedding

def collect_and_store(total_limit=5000):
    print(f"🚀 대작과 고전, 최신작을 아우르는 통합 수집을 시작합니다.")
    
    # [1] 인기 차트 게임 ID 확보 (대작들 포섭)
    chart_url = f"https://api.steampowered.com/ISteamChartsService/GetGamesByConcurrentPlayers/v1/?key={STEAM_API_KEY}"
    chart_res = requests.get(chart_url).json()
    chart_ids = [g['appid'] for g in chart_res['response']['ranks']]
    print(f"🏆 인기 차트에서 {len(chart_ids)}개의 대작 후보 확보")

    # [2] 전체 리스트 확보 및 랜덤 샘플링 (고전~최신 믹스)
    list_url = f"https://api.steampowered.com/ISteamApps/GetAppList/v2/?key={STEAM_API_KEY}"
    all_apps = requests.get(list_url).json()['applist']['apps']
    
    # 중복 제외하고 부족한 만큼 랜덤 샘플링 (AppID 제한 해제!)
    random_limit = total_limit - len(chart_ids)
    random_ids = [a['appid'] for a in random.sample(all_apps, random_limit * 2)] # 여유있게 뽑음

    # 두 리스트 합치기 (순서대로 차트 먼저 분석)
    final_app_ids = list(dict.fromkeys(chart_ids + random_ids))[:total_limit]
    
    print(f"📦 총 {len(final_app_ids)}개의 게임을 검토합니다.")

    saved_count = 0
    for app_id in tqdm(final_app_ids, desc="데이터 분석 중"):
        try:
            url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=korean&key={STEAM_API_KEY}"
            res = requests.get(url, timeout=10).json()
            
            # 성공 여부 확인
            if not res or not res.get(str(app_id)) or not res[str(app_id)]['success']:
                continue
                
            data = res[str(app_id)]['data']
            
            # 🛑 더미 필터링: 게임 타입이 아니거나 설명이 너무 짧으면 버림
            # 문명 4 같은 대작은 설명이 길기 때문에 여기서 살아남습니다.
            if data.get('type') != 'game' or len(data.get('short_description', "")) < 50:
                continue

            name = data['name']
            desc = data['short_description']
            genres = ", ".join([g['description'] for g in data.get('genres', [])])
            developer = data.get('developers', ["Unknown"])[0]

            # AI 분석 및 저장
            scores, vector = analyze_and_embed(name, genres, developer, desc)

            with engine.begin() as conn:
                query = text("""
                    INSERT INTO games (app_id, name, genres, developer, description, 
                    mania_score, story_depth, originality, difficulty, art_style, 
                    replay_value, indie_spirit, character_appeal, user_friendliness, 
                    addictiveness, emotional_impact, atmosphere_intensity, 
                    soundtrack_prominence, gem_potential, embedding)
                    VALUES (:aid, :n, :g, :d, :desc, :m, :s, :o, :df, :a, :r, :i, :c, :u, :ad, :e, :at, :sp, :gp, :v)
                    ON CONFLICT (app_id) DO NOTHING
                """)
                conn.execute(query, {
                    "aid": str(app_id), "n": name, "g": genres, "d": developer, "desc": desc,
                    "m": scores['mania_score'], "s": scores['story_depth'], "o": scores['originality'],
                    "df": scores['difficulty'], "a": scores['art_style'], "r": scores['replay_value'],
                    "i": scores['indie_spirit'], "c": scores['character_appeal'], "u": scores['user_friendliness'],
                    "ad": scores['addictiveness'], "e": scores['emotional_impact'], "at": scores['atmosphere_intensity'],
                    "sp": scores['soundtrack_prominence'], "gp": scores['gem_potential'], "v": str(vector)
                })
            
            saved_count += 1
            time.sleep(0.6) 
            
        except Exception:
            continue

    print(f"\n✅ 수집 완료! (성공: {saved_count}개)")

if __name__ == "__main__":
    collect_and_store(total_limit=5000)