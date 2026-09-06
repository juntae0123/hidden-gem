# fastapi_app/ — 추천·검색 API (포트 8000)

PostgreSQL(+pgvector)·Redis 를 읽어 게임을 점수화하고 추천·검색·랭킹을 돌려준다. 쓰기는 사용자 행동 로그(`/taste/action`)만.
SQLAlchemy async. 스키마 정본은 `models/game.py`(Django 모델은 참조용 — 컬럼을 추가하면 **운영 마이그레이션 → push**, `docs/system_invariants.md` C-12).

## 폴더 구조와 역할

```
fastapi_app/
├── main.py                 앱 진입점 — CORS, lifespan, /health, /ops/cache(무효화·통계)
├── config.py               pydantic Settings. 운영 플래그: SCORE_VERSION(v6|v7) GEM_SOURCE(legacy|evidence)
│                           LIFECYCLE_*(180일·2만·100) VIBE_SECONDARY_* PREF_EMBED_TIEBREAK CACHE_TTL_*
│                           ※ 컨테이너는 루트 .env 를 읽지 않는다 — docker-compose environment 로 넘긴다 (C-11)
├── database.py             비동기 엔진·세션
├── models/game.py          Game / GameMetric(49 수치 + 9 불리언 + gem_potential/percentile + gem_evidence_* + embedding 1536)
├── schemas/game.py         요청·응답 Pydantic (RecommendedGame 에 lifecycle·is_famous·gem_evidence·score_breakdown)
├── routers/
│   ├── games.py            /games/search, /search/semantic, /{app_id}, /recommend/by-game|by-preference|by-vibe,
│   │                       /metrics/list, /vibes, /stats/overview. 검증 순서: 지표명 → 중립(|v−5|<.5) 제거 → 빈 취향 400 (R-8)
│   ├── ranking.py          /games/ranking?type=steady|rising|new|new_quiet — 사용자 무관 지표 (R-11·R-17)
│   └── taste.py            /taste/action(행동 로그), /taste/stats(admin Basic)
├── services/
│   ├── recommender.py      세 경로 오케스트레이션 + 후보 입장(lifecycle.admit) + 캐시 + 타이브레이크
│   ├── score_v7.py         ★ 현재 채점기: 질의 마스크 + 가중 RMSE(w=1+|pref−5|/5) → match=exp(−(d/3.5)²) → Core 87 + gem 12
│   ├── score_v6.py         이전 채점기(Core 75 + X-Factor 18 + Gem 6). SCORE_VERSION=v6 일 때. D-26 결함 기록은 docs/final_verdict_0905
│   ├── lifecycle.py        new(≤180일, 나이 우선) / established / famous(≥2만) / upcoming, thin_new, gem_factor, admit()
│   ├── evidence.py         Wilson 하한·무명도·gem_evidence·velocity (embeddings/gem_evidence.py 와 같은 기본값)
│   ├── cache.py            Redis 키 = {CACHE_VERSION}-{SCORE_VERSION}-{GEM_SOURCE} 접두 + 결과를 바꾸는 조건 전부. invalidate_all 은 qa:*·prefemb:* 제외
│   ├── vibe_config.py      Vibe 12개 → 지표 목표값, secondary 초안(R-1', 플래그 뒤)
│   ├── cost_guard.py       OpenAI 시간/일 한도 초과 시 호출 차단 + Discord
│   ├── auth.py             Django JWT 에서 user_id 선택 추출
│   └── user_taste.py       행동 로그 → 취향 벡터(학습 레이어 골격, 미가동)
├── scripts/ablation.py     전체 풀 절제 실측(v6/v7·항 제거·spearman/kendall/RBO/교사비율) — fastapi 컨테이너에서 `python -m scripts.ablation --pool default`
└── tests/                  test_score_invariants(채점 불변식·플래그 양쪽) / test_lifecycle(생애주기·admit·랭킹 정렬키) / test_core
                            conftest 가 플래그를 코드 기본값으로 고정(.env 무관). 호스트: .venv/Scripts/pytest fastapi_app/tests/... -q
```

## 세 점수 경로 (전부 같은 입장 규칙·gem 소스를 쓴다)

| 경로 | 입력 | 점수 | 파일:함수 |
|---|---|---|---|
| A 취향 / Vibe | 지표 목표값 dict(sparse) | v7: Core(마스크 RMSE) 87 + gem 12 → 정렬 raw, 동점은 선호문장 임베딩 코사인(R-14) | `recommender.recommend_by_preference`, `score_v7.calculate_score_v7` |
| B 게임 기반 | 기준 게임 app_id | 지표 유사도 60% + 임베딩 40% → ×94 + gem×5 | `recommender.recommend_by_game` |
| C 문장 검색 | 자연어 → (LLM) english_query + metric_hints(7일 캐시 `qa:*`) | 임베딩 85% + 힌트 15% → ×94 + gem×5. HNSW `ef_search=400` + 넓은 폴백(R-15) | `recommender.semantic_search` |

gem = `GEM_SOURCE=evidence` 면 `gem_evidence_score/100 × 예산`(NULL→0), 정착(established)만 계수 1.0. 신작·유명작은 0 — 신작은 `new_only`(신작 리그)에서 신작끼리 경쟁.

## 랭킹 (`routers/ranking.py`)
steady = 정착·리뷰≥30·Wilson≥.5 → 발굴 지수 desc (히든젬 뱃지 ≥60&리뷰≥30, 주목 45~60) / new = 출시≤180일·Wilson≥.70 → **누적 리뷰 desc**(R-17) / new_quiet = 리뷰<100 → Wilson desc / rising = `review_history` 30일 Δ(이력 4~5주 필요).

## 실행·검증
```
docker compose up -d fastapi                 # 플래그 바꾼 뒤엔 restart 아님 (env 재독)
docker compose exec fastapi python -c "from config import settings; print(settings.SCORE_VERSION, settings.GEM_SOURCE)"
docker compose exec fastapi python -m scripts.ablation --pool default
.venv/Scripts/pytest fastapi_app/tests/test_score_invariants.py fastapi_app/tests/test_lifecycle.py -q   # 36 passed
```
실측 기록: `docs/ablation_result_0905.md`(§1~7), 결정: `docs/decisions_0905.md`. v6 시절 검증 스크립트는 `legacy/fastapi_scripts_v6/`.
