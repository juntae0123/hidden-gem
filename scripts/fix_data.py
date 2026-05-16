# scripts/fix_data.py
import json
import pandas as pd
from pathlib import Path

# 경로 설정
csv_path = '../data/hidden_gem_data.csv'
input_jsonl = '../data/final/final_master_games.jsonl'
output_jsonl = '../data/final/final_master_games_fixed.jsonl'

# 원본 스팀 데이터 읽기
print(f"📂 원본 스팀 데이터 읽는 중... ({csv_path})")
df = pd.read_csv(csv_path)
print(f"   CSV 컬럼: {list(df.columns)}")
print(f"   CSV 게임 수: {len(df)}")

steam_dict = df.set_index('app_id').to_dict('index')

# 병합 시작
print("\n🔄 AI 데이터에 스팀 메타데이터 + gem_potential 병합 중...")
merged_count = 0
missing_count = 0
gem_count = 0

with open(input_jsonl, 'r', encoding='utf-8') as f_in, \
     open(output_jsonl, 'w', encoding='utf-8') as f_out:
    
    for line in f_in:
        data = json.loads(line)
        app_id = data.get('app_id')
        
        if app_id in steam_dict:
            steam_info = steam_dict[app_id]
            
            # 기본 메타데이터
            data['name'] = steam_info.get('name', '') if pd.notna(steam_info.get('name')) else ''
            data['genres'] = steam_info.get('genres', '') if pd.notna(steam_info.get('genres')) else ''
            data['developer'] = steam_info.get('developer', '') if pd.notna(steam_info.get('developer')) else ''
            data['description'] = steam_info.get('description', '') if pd.notna(steam_info.get('description')) else ''
            
            # 🌟 gem_potential을 metrics에 주입! (load_games.py가 여기서 읽음)
            gem = steam_info.get('gem_potential')
            if pd.notna(gem):
                if 'metrics' not in data:
                    data['metrics'] = {}
                data['metrics']['gem_potential'] = float(gem)
                gem_count += 1
            
            # 추가 CSV 지표도 reasoning에 백업 (참고용)
            data['_csv_extra'] = {
                'mania_score': float(steam_info['mania_score']) if pd.notna(steam_info.get('mania_score')) else None,
                'story_depth': float(steam_info['story_depth']) if pd.notna(steam_info.get('story_depth')) else None,
                'originality': float(steam_info['originality']) if pd.notna(steam_info.get('originality')) else None,
                'art_style': float(steam_info['art_style']) if pd.notna(steam_info.get('art_style')) else None,
                'indie_spirit': float(steam_info['indie_spirit']) if pd.notna(steam_info.get('indie_spirit')) else None,
            }
            
            merged_count += 1
        else:
            missing_count += 1
            
        f_out.write(json.dumps(data, ensure_ascii=False) + '\n')

print(f"\n✅ 병합 완료!")
print(f"   - 정상 병합: {merged_count}개")
print(f"   - gem_potential 채워짐: {gem_count}개")
print(f"   - CSV에 없는 데이터: {missing_count}개")
print(f"\n🎉 새 파일: {output_jsonl}")
