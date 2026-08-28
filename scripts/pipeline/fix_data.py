# scripts/fix_data.py
"""
AI 분석 데이터에 Steam CSV 메타데이터 보완 스크립트 (Data Fix & Enrichment)

merge_metrics.py로 생성된 JSONL에 Steam CSV(hidden_gem_data.csv)의
메타데이터(name, genres, developer)와 gem_potential을 병합.

핵심 역할:
    - gem_potential: CSV의 값을 data.metrics.gem_potential에 주입
      (load_games.py의 _get_metric()이 이 위치에서 읽음)
    - _csv_extra: mania_score, indie_spirit 등 추가 CSV 지표 백업 (참고용)

사용법:
    python scripts/fix_data.py  (경로는 스크립트 내 고정)

Pipeline 위치:
    merge_metrics.py → [fix_data.py] → load_games.py
"""
import json
import pandas as pd
from pathlib import Path

# ---- 경로 설정 ----
csv_path = '../data/hidden_gem_data.csv'
input_jsonl = '../data/final/final_master_games.jsonl'
output_jsonl = '../data/final/final_master_games_fixed.jsonl'

# ---- Steam CSV 로드 및 app_id 인덱싱 ----
print(f"원본 스팀 데이터 읽는 중... ({csv_path})")
df = pd.read_csv(csv_path)
print(f"   CSV 컬럼: {list(df.columns)}")
print(f"   CSV 게임 수: {len(df)}")

# app_id를 키로 빠른 조회를 위해 딕셔너리로 변환
steam_dict = df.set_index('app_id').to_dict('index')

# ---- JSONL 라인별 스트리밍 병합 ----
print("\nAI 데이터에 스팀 메타데이터 + gem_potential 병합 중...")
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

            # 기본 메타데이터 - pandas NaN 처리 필수 (json.dumps에서 NaN 직렬화 불가)
            data['name'] = steam_info.get('name', '') if pd.notna(steam_info.get('name')) else ''
            data['genres'] = steam_info.get('genres', '') if pd.notna(steam_info.get('genres')) else ''
            data['developer'] = steam_info.get('developer', '') if pd.notna(steam_info.get('developer')) else ''
            data['description'] = steam_info.get('description', '') if pd.notna(steam_info.get('description')) else ''

            # gem_potential 주입 - load_games.py의 _get_metric([m, r, data], 'gem_potential')에서 여기서 읽음
            gem = steam_info.get('gem_potential')
            if pd.notna(gem):
                if 'metrics' not in data:
                    data['metrics'] = {}
                data['metrics']['gem_potential'] = float(gem)
                gem_count += 1

            # 추가 CSV 지표 백업 (extract_sample.py에서 indie_spirit 정렬에 활용)
            data['_csv_extra'] = {
                'mania_score': float(steam_info['mania_score']) if pd.notna(steam_info.get('mania_score')) else None,
                'story_depth': float(steam_info['story_depth']) if pd.notna(steam_info.get('story_depth')) else None,
                'originality': float(steam_info['originality']) if pd.notna(steam_info.get('originality')) else None,
                'art_style': float(steam_info['art_style']) if pd.notna(steam_info.get('art_style')) else None,
                'indie_spirit': float(steam_info['indie_spirit']) if pd.notna(steam_info.get('indie_spirit')) else None,
            }

            merged_count += 1
        else:
            missing_count += 1  # CSV에 없는 게임은 AI 데이터만 그대로 유지

        f_out.write(json.dumps(data, ensure_ascii=False) + '\n')

print(f"\n병합 완료!")
print(f"   - 정상 병합: {merged_count}개")
print(f"   - gem_potential 채워짐: {gem_count}개")
print(f"   - CSV에 없는 데이터: {missing_count}개")
print(f"\n새 파일: {output_jsonl}")
