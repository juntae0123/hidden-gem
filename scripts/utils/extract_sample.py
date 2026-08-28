"""
마스터 파일에서 상위 10개 샘플 추출 스크립트 (Top-10 Sample Extractor)

fix_data.py로 생성된 final_master_games_fixed.jsonl에서
gem_potential + indie_spirit 점수 기준 상위 10개 게임을 추출.
데이터 품질 검증이나 추천 엔진 테스트용 샘플 제작에 사용.

정렬 기준 (우선순위):
    1. gem_potential (높을수록 숨겨진 명작)
    2. _csv_extra.indie_spirit (인디 정신 점수)

사용법:
    python scripts/extract_sample.py  (경로는 스크립트 내 고정)
"""
import json

input_path = r"C:\Hidden-Gem-project\data\final\final_master_games_fixed.jsonl"
output_path = r"C:\Hidden-Gem-project\data\sample_10_fixed.jsonl"

# utf-8-sig: BOM 있는 UTF-8 파일도 처리 (Excel에서 저장된 CSV 대응)
games = []
with open(input_path, "r", encoding="utf-8-sig") as f:
    for line in f:
        line = line.strip()
        if line:
            games.append(json.loads(line))

# gem_potential 우선, 동점 시 indie_spirit 기준으로 상위 10개 선택
samples = sorted(
    games,
    key=lambda x: (
        x.get("gem_potential") or x.get("metrics", {}).get("gem_potential", 0),
        x.get("_csv_extra", {}).get("indie_spirit", 0)
    ),
    reverse=True
)[:10]

with open(output_path, "w", encoding="utf-8") as f:
    for game in samples:
        f.write(json.dumps(game, ensure_ascii=False) + "\n")

print(f"완료: {len(samples)}개 추출")
for g in samples:
    print(f"  - {g.get('name')} | gem_potential: {g.get('metrics', {}).get('gem_potential')}")
