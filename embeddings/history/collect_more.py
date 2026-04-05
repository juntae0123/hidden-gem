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

# 🔴 세션 설정 (브라우저처럼 보이게)
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
})

def get_existing_app_ids():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT app_id FROM games"))
            return set(str(row[0]) for row in result)
    except:
        return set()

def scrape_steam_search(start, count=50):
    """스팀 검색 페이지에서 게임 ID 추출"""
    url = f"https://store.steampowered.com/search/results/?query&start={start}&count={count}&infinite=1"
    
    for attempt in range(5):
        try:
            res = session.get(url, timeout=30)
            
            # HTML이 아닌 JSON 응답인지 확인
            if 'results_html' in res.text:
                data = res.json()
                app_ids = re.findall(r'data-ds-appid="(\d+)"', data.get('results_html', ''))
                return app_ids
            else:
                # HTML 응답이면 직접 파싱
                app_ids = re.findall(r'data-ds-appid="(\d+)"', res.text)
                if app_ids:
                    return app_ids
                    
        except Exception as e:
            pass
        
        # 재시도 전 대기
        wait = (attempt + 1) * 2
        print(f"   ⏳ 재시도 대기 {wait}초...")
        time.sleep(wait)
    
    return []

def get_new_app_ids(target_count, existing_ids):
    """새로운 게임 ID를 목표 개수만큼 수집"""
    new_ids = set()
    
    print(f"🌐 스팀에서 새 게임 {target_count}개 검색 중...")
    print(f"   (DB에 {len(existing_ids)}개 있음, 중복 제외)")
    
    # 여러 필터 조합으로 검색
    search_configs = [
        ("전체 게임", ""),
        ("한국어 지원", "&supportedlang=korean"),
        ("인디 게임", "&tags=492"),  # indie tag
        ("액션 게임", "&tags=19"),   # action tag
        ("RPG 게임", "&tags=122"),   # rpg tag
        ("어드벤처", "&tags=21"),    # adventure tag
        ("전략 게임", "&tags=9"),    # strategy tag
        ("시뮬레이션", "&tags=599"), # simulation tag
        ("캐주얼", "&tags=597"),     # casual tag
        ("퍼즐", "&tags=1664"),      # puzzle tag
        ("플랫포머", "&tags=1625"),  # platformer tag
        ("호러", "&tags=1667"),      # horror tag
        ("2024년 출시", "&category1=998&os=win"),
        ("높은 평가", "&filter=topsellers"),
    ]
    
    for config_name, extra_params in search_configs:
        if len(new_ids) >= target_count:
            break
            
        print(f"\n📍 '{config_name}' 검색 중...")
        consecutive_empty = 0
        
        for start in range(0, 10000, 50):
            if len(new_ids) >= target_count:
                break
            if consecutive_empty >= 3:
                break
                
            url = f"https://store.steampowered.com/search/results/?query&start={start}&count=50{extra_params}&infinite=1"
            
            try:
                res = session.get(url, timeout=30)
                
                if res.status_code != 200:
                    consecutive_empty += 1
                    time.sleep(2)
                    continue
                
                # JSON 파싱 시도
                try:
                    data = res.json()
                    html = data.get('results_html', '')
                except:
                    html = res.text
                
                app_ids = re.findall(r'data-ds-appid="(\d+)"', html)
                
                if not app_ids:
                    consecutive_empty += 1
                    time.sleep(1)
                    continue
                
                consecutive_empty = 0
                
                # 새로운 ID만 추가
                before = len(new_ids)
                for aid in app_ids:
                    if aid not in existing_ids and aid not in new_ids:
                        new_ids.add(aid)
                
                added = len(new_ids) - before
                
                if start % 500 == 0 and start > 0:
                    print(f"   📄 {start}개 스캔, 새 게임 {len(new_ids)}개 확보")
                
                time.sleep(0.8)  # Rate limit 방지
                
            except Exception as e:
                consecutive_empty += 1
                time.sleep(2)
                continue
        
        print(f"   ✅ '{config_name}' 완료 - 현재 {len(new_ids)}개")
    
    print(f"\n🎯 총 {len(new_ids)}개의 새 게임 ID 확보!")
    return list(new_ids)[:target_count * 2]  # 여유분 포함

def analyze_and_embed(name, genres, developer, desc):
    """AI 분석 및 임베딩"""
    rich_text = f"Title: {name}\nDeveloper: {developer}\nGenres: {genres}\nDescription: {desc}"
    
    metrics = [
        "mania_score", "story_depth", "originality", "difficulty", "art_style",
        "replay_value", "indie_spirit", "character_appeal", "user_friendliness",
        "addictiveness", "emotional_impact", "atmosphere_intensity",
        "soundtrack_prominence", "gem_potential"
    ]
    
    prompt = f"Evaluate the game and output ONLY a JSON object with keys: {', '.join(metrics)}. All values must be integers (0-100)."
    
    try:
        chat_response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": rich_text}
            ]
        )
        scores = json.loads(chat_response.choices[0].message.content)
    except Exception as e:
        scores = {}
    
    final_scores = {}
    for m in metrics:
        val = scores.get(m, 50)
        try:
            val = max(0, min(100, int(val)))
        except:
            val = 50
        final_scores[m] = val
    
    try:
        embed_response = client.embeddings.create(
            model="text-embedding-3-small",
            input=rich_text
        )
        embedding = embed_response.data[0].embedding
    except:
        embedding = [0.0] * 1536
    
    return final_scores, embedding

def get_game_details(app_id):
    """게임 상세 정보 가져오기 (재시도 포함)"""
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=korean"
    
    for attempt in range(3):
        try:
            res = session.get(url, timeout=20)
            
            if res.status_code == 200 and res.text:
                try:
                    data = res.json()
                    if data and data.get(str(app_id), {}).get('success'):
                        return data[str(app_id)]['data']
                except:
                    pass
            
            time.sleep(1)
            
        except:
            time.sleep(2)
    
    return None

def collect_games(total_target=5000):
    print("=" * 60)
    print("🚀 스팀 보석 수집기 v5.0")
    print("=" * 60)
    
    existing_ids = get_existing_app_ids()
    current_count = len(existing_ids)
    
    print(f"📊 현재 DB: {current_count}개 / 목표: {total_target}개")
    
    remaining = total_target - current_count
    if remaining <= 0:
        print("🎉 이미 목표 달성!")
        return
    
    print(f"🔥 추가 수집 필요: {remaining}개\n")
    
    # 새로운 게임 ID 수집
    new_app_ids = get_new_app_ids(remaining, existing_ids)
    
    if not new_app_ids:
        print("❌ 수집할 게임이 없습니다.")
        return
    
    print(f"\n🎮 {len(new_app_ids)}개 후보 중 {remaining}개 목표로 분석 시작...")
    print("   (게임당 약 2초 소요)\n")
    
    saved_count = 0
    skip_count = 0
    error_count = 0
    
    for app_id in tqdm(new_app_ids, desc="🎮 분석 중"):
        # 목표 달성시 종료
        if saved_count >= remaining:
            print(f"\n🎯 목표 {remaining}개 달성!")
            break
        
        try:
            # 게임 상세 정보 가져오기
            data = get_game_details(app_id)
            
            if not data:
                skip_count += 1
                continue
            
            # 게임만, 설명 40자 이상
            if data.get('type') != 'game':
                skip_count += 1
                continue
            
            desc = data.get('short_description', '')
            if len(desc) < 40:
                skip_count += 1
                continue
            
            # 장르, 개발사 추출
            genres_list = data.get('genres', [])
            genres_str = ", ".join([g['description'] for g in genres_list]) if genres_list else "Unknown"
            dev_list = data.get('developers', [])
            dev_str = dev_list[0] if dev_list else "Unknown"
            
            # AI 분석
            scores, vector = analyze_and_embed(
                data['name'],
                genres_str,
                dev_str,
                desc
            )
            
            # DB 저장
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
                    ON CONFLICT (app_id) DO NOTHING
                """), {
                    "aid": str(app_id),
                    "n": data['name'][:200],
                    "g": genres_str[:500],
                    "d": dev_str[:200],
                    "desc": desc[:2000],
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
            
            # 진행 상황 출력
            if saved_count % 50 == 0:
                print(f"\n💾 {saved_count}/{remaining} 저장 완료! (스킵: {skip_count})")
            
            time.sleep(1.2)  # Rate limit 방지
            
        except Exception as e:
            error_count += 1
            continue
    
    # 최종 결과
    final_count = current_count + saved_count
    
    print("\n" + "=" * 60)
    print("🎊 수집 완료!")
    print(f"   ✅ 신규 저장: {saved_count}개")
    print(f"   ⏭️ 스킵: {skip_count}개")
    print(f"   ❌ 에러: {error_count}개")
    print(f"   📊 DB 총합: {final_count}개")
    print("=" * 60)
    
    if final_count < total_target:
        print(f"\n⚠️ 아직 {total_target - final_count}개 부족!")
        print("   다시 실행하면 이어서 수집합니다.")


if __name__ == "__main__":
    collect_games(total_target=5000)
