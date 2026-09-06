# embeddings/ — 데이터 파이프라인 (batch 컨테이너)

게임을 발견하고(Steam) → 분석하고(OpenAI Batch, 교사-학생 증류) → 적재·임베딩하고 → 리뷰 실측으로 노출·발굴 지수를 갱신하는 모든 배치 코드.
서빙(`fastapi_app/`)과 분리된 **batch 컨테이너**에서 돈다: `docker compose exec batch python -m embeddings.<모듈> ...`
(compose 가 `embeddings/`·`data/`·`fastapi_app/`(읽기전용)·`.env` 만 마운트한다 — `deploy/` 같은 다른 폴더는 컨테이너에 없다.)

**대상 DB (R-18, 2026-09-06)**: 주간 파이프라인은 기본 **운영**(`.env PROD_DATABASE_URL`)에 쓴다. 다른 모듈은 `DATABASE_URL`(로컬 db)이 기본이고,
운영에 대고 돌릴 때는 `docker compose exec -e DATABASE_URL="$PROD_DB" batch python -m embeddings.<모듈>` 처럼 덮어쓴다. 시작 로그의 대상 URL 을 확인한다.

## 주간 자동화 (월 03:30, `scripts/pipeline/setup_weekly_task.ps1`)

```
weekly_pipeline ── 0 db_space(용량 70% 게이트) → 1 steam_crawler → 2 batch_generator → 3 batch_processor
                   → 4 generate_embeddings → 5 refresh_reviews --new(게이트) → 6 recalc_percentile
                   → 7 refresh_reviews --recheck(30일) → 7' refresh_reviews --stale --cohort all(주간 이력, ~2.5h)
                   → 8 gem_evidence --fill(발굴 지수)
킬 스위치: data/STOP_PIPELINE(전부) / data/STOP_BACKFILL(--loop 백필만)
```

## 모듈 지도

| 모듈 | 역할 | 핵심 코드 |
|---|---|---|
| `weekly_pipeline.py` | 오케스트레이터. subprocess 로 각 단계 호출, Discord 알림, 루프(백필) 모드 | `select_target_db()` 대상 고정, `run_iteration()` 1회차, 킬 스위치 |
| `steam_crawler.py` | 최근 N일 신작 발견 → `data/new_games.csv` (DB 중복 제외, 429 적응형 스로틀링) | `request_with_backoff()`, `--days`/`--from --to` |
| `batch_generator.py` | 블라인드 CSV + few-shot 12개 → OpenAI Batch 제출/대기/다운로드 (`--sync` 폴백) | 프롬프트 템플릿, `--wait-timeout` 취소 후 부분 수거 |
| `batch_processor.py` | 결과 JSONL → `game_metrics` 60컬럼 UPSERT. 응답 모델명으로 `extraction_version` 판정 | 컬럼 계약(`NUMERIC_METRIC_FIELDS` 와 1:1), `activate_games` |
| `generate_embeddings.py` | embedding NULL 게임 임베딩(text-embedding-3-small 1536) 생성 후 `is_active` 전환 | 원본 템플릿 재사용 |
| `refresh_reviews.py` | Steam appreviews 로 `review_count`·긍정률 갱신, `review_refresh_log`(최신)·`review_history`(append) 기록, 노출 게이트 | 모드 `--new / --recheck / --all-new / --stale`, `apply_gate()` |
| `exposure_policy.py` | 노출 규칙 한곳: `MIN_REVIEWS_FOR_EXPOSURE`(현재 10, R-4 로 3&Wilson≥.35 예정) | `should_expose()` |
| `gem_evidence.py` | **근거 기반 발굴 지수** = Wilson 하한(z 1.96) × 무명도(log, cap 20000, exp .5). `gem_evidence_score/status` 채움 | `classify()` ok/too_new/famous/insufficient/no_reviews, `--fill --dry-run` |
| `recalc_percentile.py` | (legacy gem) `gem_percentile` 전체 재계산 — GEM_SOURCE=legacy 일 때만 의미 | |
| `fewshot_sampler.py` | 교사 데이터에서 gem 구간 층화 + 장르 다양성으로 few-shot 예시 추출 | |
| `audit_student.py` | 교사 게임 N개를 학생 모델로 재분석해 같은 게임 쌍 비교(MAE·상관·gem 혼동표). exit 3 = 드리프트 | `--make-holdout`, `--compare` |
| `audit_offline.py` | DB·API 없이 파일만으로 교사 vs 학생 비교 | |
| `calibrate_student.py` | 학생 지표 선형 보정 도구 — **R-10 철회**, 원점 고정 옵션만 기준선용으로 보존. `--revert` | |
| `usage_report.py` | 배치 결과 JSONL 의 usage 합산 — 비용은 추정 아닌 실측 | |
| `rec_snapshot.py` | 서빙 API 에 고정 시나리오 19개(취향 10·시맨틱 3·by-game 3·랭킹 3)를 던져 저장, `--diff a b` 회귀 비교. 캐시 무효화+확인 강제, 카나리아(신작 1위) 출력 | `collect()`, `diff()`, `_rows()` |
| `migrate.py` | Alembic 없는 멱등 SQL 실행기. 파일은 `embeddings/migrations/` | `--list`, `--file` |
| `prod_sync.py` | 로컬 → 운영 게임 데이터 upsert(games·game_metrics·review_*). 삭제 없음, 사용자 테이블 무접촉, dry-run 기본, 묶음 실행 | `plan()` 공통 컬럼, `upsert_sql()`, `--include-raw` |
| `db_space.py` | DB·테이블 크기, 죽은 튜플, `--vacuum`, `--limit-gb --alert-pct`(파이프라인 게이트) | |
| `post_backfill.py` | 백필 루프 종료 후 후처리 원커맨드 | |
| `collect_batch.py` / `make_retry_csv.py` | 멈춘 배치 수동 회수 / 미적재 잔여분 재시도 CSV | |
| `relabel_version.py` | `extraction_version`·`analysis_method` 잘못 라벨된 적재 복구 | |
| `migrations/` | `20260905_gem_evidence_columns.sql` 등 | |

## 데이터 계보 (한 줄)
교사 4,190(GPT-5.4 Batch, 2-패스 60컬럼) + 학생 8,653(gpt-5.4-mini 12-shot 증류, `fewshot_5.4based`) = 12,843. 홀드아웃 150쌍: 49지표 MAE 0.77(교사급), LLM gem 은 사용 불가(r≈0) → `gem_evidence`.

## 자주 쓰는 명령
```
docker compose exec batch python -m embeddings.weekly_pipeline --crawl-only --limit 5      # 운영 대상, OpenAI 미호출
docker compose exec batch python -m embeddings.rec_snapshot --save s8 ; ... --diff s7_rank_qa s8
docker compose exec -e DATABASE_URL="$PROD_DB" batch python -m embeddings.db_space --limit-gb 5
docker compose exec -e PROD_DATABASE_URL="$PROD_DB" batch python -m embeddings.prod_sync --dry-run
```
규칙·사고 기록: 루트 `CLAUDE.md`, `docs/system_invariants.md`(C-1~C-13), `docs/decisions_0905.md`(R-1~R-18). 옛 파이프라인 코드는 `legacy/embeddings_v1/`, `legacy/scripts_pipeline_v1/`.
