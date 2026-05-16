import json

input_path = r"C:\Hidden-Gem-project\data\final\final_master_games_fixed.jsonl"
output_path = r"C:\Hidden-Gem-project\data\sample_10_fixed.jsonl"

games = []
with open(input_path, "r", encoding="utf-8-sig") as f:
    for line in f:
        line = line.strip()
        if line:
            games.append(json.loads(line))

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

print(f"✅ 완료: {len(samples)}개 추출")
for g in samples:
    print(f"  - {g.get('name')} | gem_potential: {g.get('metrics', {}).get('gem_potential')}")
