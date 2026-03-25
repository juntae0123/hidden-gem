import os
import json
import requests
import time
import re
from openai import OpenAI
from sqlalchemy import create_engine, text
from dotenv import load_dotenv, find_dotenv
from tqdm import tqdm

load_dotenv(find_dotenv())
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DB_URL = os.getenv("DATABASE_URL")
engine = create_engine(DB_URL)

def init_db():
    print("🛠️ DB 테이블 세팅 확인 중...")
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS games (
                app_id VARCHAR(50) PRIMARY KEY,
                name VARCHAR(255),
                genres TEXT,
                developer VARCHAR(255),
                description TEXT,
                mania_score INTEGER, story_depth INTEGER, originality INTEGER, 
                difficulty INTEGER, art_style INTEGER, replay_value INTEGER, 
                indie_spirit INTEGER, character_appeal INTEGER, user_friendliness INTEGER, 
                addictiveness INTEGER, emotional_impact INTEGER, atmosphere_intensity INTEGER, 
                soundtrack_prominence INTEGER, gem_potential INTEGER, 
                embedding vector(1536)
            )
        """))
    print("✅ DB 테이블 준비 완료!")

def retry_on_failure(max_retries=3, delay=2):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"⚠️ 재시도 {attempt+1}: {e}")
                        time.sleep(delay * (attempt + 1))
                    else:
                        raise e
        return wrapper
    return decorator

@retry_on_failure()
def analyze_and_embed(name, genres, developer, desc):
    rich_text = f"Title: {name}\nDeveloper: {developer}\nGenres: {genres}\nDescription: {desc}"
    
    metrics = [
        "mania_score", "story_depth", "originality", "difficulty", "art_style",
        "replay_value", "indie_spirit", "character_appeal", "user_friendliness",
        "addictiveness", "emotional_impact", "atmosphere_intensity",
        "soundtrack_prominence", "gem_potential"
    ]
    
    prompt = f"Evaluate the game and output ONLY a JSON object with keys: {', '.join(metrics)}. All values must be integers (0-100)."
    
    chat_response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": rich_text}
        ]
    )
    
    try:
        scores = json.loads(chat_response.choices[0].message.content)
    except json.JSONDecodeError:
        scores = {}
    
    final_scores = {}
    for m in metrics:
        val = scores.get(m, 50)
        try:
            val = int(val)
            val = max(0, min(100, val))
        except (TypeError, ValueError):
            val = 50
        final_scores[m] = val
    
    print(f"✅ 분석 완료: {name} (잠재력: {final_scores['gem_potential']})")
    
    embed_response = client.embeddings.create(
        model="text-embedding-3-small",
        input=rich_text
    )
    return final_scores, embed_response.data[0].embedding

def get_existing_app_ids():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT app_id FROM games"))
            return set(str(row[0]) for row in result)
    except Exception as e:
        print(f"⚠️ DB 조회 실패: {e}")
        return set()

# ============== 🔴 핵심 수정: 스크래핑 함수 대폭 강화 ==============
def get_app_ids_by_scraping(target_new_count, existing_ids):
    """여러 방식으로 스팀 게임 ID를 수집"""
    new_app_ids = set()
    
    print(f"🌐 스팀에서 새 게임 {target_new_count}개 검색 중...")
    print(f"   (현재 DB에 {len(existing_ids)}개 있음, 이건 건너뜀)")
    
    # 🔴 방법 1: 기본 검색 (한국어 지원)
    print("\n📍 방법1: 한국어 지원 게임 검색...")
    start_idx = 0
    while len(new_app_ids) < target_new_count and start_idx < 20000:
        url = f"https://store.steampowered.com/search/results/?query&start={start_idx}&count=100&supportedlang=korean&infinite=1"
        try:
            res = requests.get(url, timeout=20).json()
            found_ids = re.findall(r'data-ds-appid="(\d+)"', res.get('results_html', ''))
            if not found_ids:
                break
            for fid in found_ids:
                if fid not in existing_ids:
                    new_app_ids.add(fid)
            start_idx += 100
            if start_idx % 500 == 0:
                print(f"   📄 {start_idx}개 스캔, 새 게임 {len(new_app_ids)}개 발견")
            time.sleep(0.3)
        except Exception as e:
            print(f"   ⚠️ 에러: {e}")
            time.sleep(1)
            continue
    
    # 🔴 방법 2: 전체 게임 (언어 제한 없이)
    if len(new_app_ids) < target_new_count:
        print(f"\n📍 방법2: 전체 게임 검색 (현재 {len(new_app_ids)}개)...")
        start_idx = 0
        while len(new_app_ids) < target_new_count and start_idx < 30000:
            url = f"https://store.steampowered.com/search/results/?query&start={start_idx}&count=100&infinite=1"
            try:
                res = requests.get(url, timeout=20).json()
                found_ids = re.findall(r'data-ds-appid="(\d+)"', res.get('results_html', ''))
                if not found_ids:
                    break
                for fid in found_ids:
                    if fid not in existing_ids:
                        new_app_ids.add(fid)
                start_idx += 100
                if start_idx % 500 == 0:
                    print(f"   📄 {start_idx}개 스캔, 새 게임 {len(new_app_ids)}개 발견")
                time.sleep(0.3)
            except Exception as e:
                print(f"   ⚠️ 에러: {e}")
                time.sleep(1)
                continue
    
    # 🔴 방법 3: 인기 태그별 검색
    if len(new_app_ids) < target_new_count:
        print(f"\n📍 방법3: 태그별 검색 (현재 {len(new_app_ids)}개)...")
        tags = ["indie", "action", "rpg", "adventure", "strategy", "simulation", "casual", "puzzle", "platformer", "horror"]
        
        for tag in tags:
            if len(new_app_ids) >= target_new_count:
                break
            start_idx = 0
            while start_idx < 5000:
                url = f"https://store.steampowered.com/search/results/?query&start={start_idx}&count=100&tags={tag}&infinite=1"
                try:
                    res = requests.get(url, timeout=20).json()
                    found_ids = re.findall(r'data-ds-appid="(\d+)"', res.get('results_html', ''))
                    if not found_ids:
                        break
                    for fid in found_ids:
                        if fid not in existing_ids:
                            new_app_ids.add(fid)
                    start_idx += 100
                    time.sleep(0.3)
                except:
                    break
            print(f"   🏷️ '{tag}' 완료, 총 {len(new_app_ids)}개")
    
    # 🔴 방법 4: 출시년도별 검색
    if len(new_app_ids) < target_new_count:
        print(f"\n📍 방법4: 출시년도별 검색 (현재 {len(new_app_ids)}개)...")
        years = ["2024", "2023", "2022", "2021", "2020", "2019", "2018"]
        
        for year in years:
            if len(new_app_ids) >= target_new_count:
                break
            start_idx = 0
            while start_idx < 5000:
                url = f"https://store.steampowered.com/search/results/?query&start={start_idx}&count=100&category1=998&os=win&filter=topsellers&term={year}&infinite=1"
                try:
                    res = requests.get(url, timeout=20).json()
                    found_ids = re.findall(r'data-ds-appid="(\d+)"', res.get('results_html', ''))
                    if not found_ids:
                        break
                    for fid in found_ids:
                        if fid not in existing_ids:
                            new_app_ids.add(fid)
                    start_idx += 100
                    time.sleep(0.3)
                except:
                    break
            print(f"   📅 '{year}' 완료, 총 {len(new_app_ids)}개")
    
    print(f"\n✅ 총 {len(new_app_ids)}개의 새 게임 ID 확보!")
    return list(new_app_ids)[:target_new_count]

def collect_and_store(total_target=5000):
    print("=" * 60)
    print("🚀 스팀 보석 수집기 v3.0 (강화된 스크래핑)")
    print("=" * 60)
    
    init_db()
    
    existing_ids = get_existing_app_ids()
    current_count = len(existing_ids)
    print(f"📊 현재 DB: {current_count}개 / 목표: {total_target}개")
    
    remaining = total_target - current_count
    if remaining <= 0:
        print("🎉 이미 목표 달성!")
        return
    
    print(f"🔥 추가 수집 필요: {remaining}개")
    
    final_app_ids = get_app_ids_by_scraping(remaining, existing_ids)
    
    if not final_app_ids:
        print("⚠️ 수집할 게임이 없습니다.")
        return
    
    print(f"\n🎮 {len(final_app_ids)}개 게임 분석 시작...")
    
    saved_count = 0
    error_count = 0
    skip_count = 0
    
    for app_id in tqdm(final_app_ids, desc="🎮 분석 중"):
        try:
            res = requests.get(
                f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=korean",
                timeout=15
            ).json()
            
            if not res or not res.get(str(app_id), {}).get('success'):
                skip_count += 1
                continue
                
            data = res[str(app_id)]['data']
            
            if data.get('type') != 'game':
                skip_count += 1
                continue
            if len(data.get('short_description', "")) < 40:
                skip_count += 1
                continue

            genres_list = data.get('genres', [])
            genres_str = ", ".join([g['description'] for g in genres_list]) if genres_list else "Unknown"
            dev_list = data.get('developers', [])
            dev_str = dev_list[0] if dev_list else "Unknown"

            scores, vector = analyze_and_embed(
                data['name'],
                genres_str,
                dev_str,
                data['short_description']
            )

            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO games (
                        app_id, name, genres, developer, description,
                        mania_score, story_depth, originality, difficulty, art_style,
                        replay_value, indie_spirit, character_appeal, user_friendliness,
                        addictiveness, emotional_impact, atmosphere_intensity,
                        soundtrack_prominence, gem_potential, embedding
                    ) VALUES (
                        :aid, :n, :g, :d, :desc,
                        :m, :s, :o, :df, :a,
                        :r, :i, :c, :u,
                        :ad, :e, :at,
                        :sp, :gp, :v
                    )
                    ON CONFLICT (app_id) DO UPDATE SET
                        gem_potential = EXCLUDED.gem_potential,
                        embedding = EXCLUDED.embedding
                """), {
                    "aid": str(app_id),
                    "n": data['name'][:200],
                    "g": genres_str[:500],
                    "d": dev_str[:200],
                    "desc": data['short_description'][:2000],
                    "m": scores['mania_score'],
                    "s": scores['story_depth'],
                    "o": scores['originality'],
                    "df": scores['difficulty'],
                    "a": scores['art_style'],
                    "r": scores['replay_value'],
                    "i": scores['indie_spirit'],
                    "c": scores['character_appeal'],
                    "u": scores['user_friendliness'],
                    "ad": scores['addictiveness'],
                    "e": scores['emotional_impact'],
                    "at": scores['atmosphere_intensity'],
                    "sp": scores['soundtrack_prominence'],
                    "gp": scores['gem_potential'],
                    "v": str(vector)
                })
            
            saved_count += 1
            
            if saved_count % 100 == 0:
                print(f"\n💾 중간 저장: {saved_count}개 완료 (스킵: {skip_count}, 에러: {error_count})")
            
            time.sleep(0.8)
            
        except Exception as e:
            error_count += 1
            if error_count % 10 == 0:
                print(f"❌ 에러 {error_count}건 ({app_id}): {str(e)[:50]}")
            continue
    
    print("\n" + "=" * 60)
    print(f"🎊 수집 완료!")
    print(f"   ✅ 성공: {saved_count}개")
    print(f"   ⏭️ 스킵: {skip_count}개 (게임 아님/설명 부족)")
    print(f"   ❌ 에러: {error_count}개")
    print(f"   📊 DB 총: {current_count + saved_count}개")
    print("=" * 60)


if __name__ == "__main__":
    collect_and_store(total_target=5000)
