# scripts/

데이터 파이프라인 스크립트 모음. GPT Batch API로 60개 지표를 추출하고,
PostgreSQL에 게임 데이터와 임베딩을 적재하는 전 과정을 자동화한다.

실행 위치: 항상 **프로젝트 루트** (`C:\Hidden-Gem-project\`)
가상환경: `.venv\Scripts\activate` (Windows) / `source .venv/bin/activate` (Mac/Linux)

---

## 폴더 구조

```
scripts/
├── make_diet_batch.py      # [1] GPT Batch 요청 파일 생성
├── split_batch.py          # [2] 1,000개 단위 분할
├── submit_batches.py       # [3] OpenAI Batch API 제출
├── check_batches.py        # [4] Batch 완료 상태 확인
├── download_outputs.py     # [5] 결과 파일 다운로드
├── combine_outputs.py      # [6] 결과 파일 통합
├── merge_metrics.py        # [7] 60개 지표 병합
├── validate_merge.py       # [8] 데이터 품질 검증
├── fix_data.py             # [9] CSV+JSONL 병합 및 보정
├── load_embeddings.py      # pgvector 임베딩 생성 및 적재
├── fill_header_images.py   # [이미지 A] CDN URL 일괄 생성
├── verify_header_images.py # [이미지 B] HEAD 요청으로 404 탐지
├── fix_failed_headers.py   # [이미지 C] Steam API로 URL 복구
└── extract_sample.py       # 유틸리티 — gem_potential 상위 샘플 추출
```

---

## 전체 파이프라인 흐름

```
Steam CSV 원본 데이터
        │
[1] make_diet_batch  ─── 토큰 최적화된 GPT Batch 요청 파일 생성
[2] split_batch      ─── 1,000개 단위 분할 (OpenAI 제한 대응)
[3] submit_batches   ─── OpenAI Batch API 제출 (동기 대비 ~50% 절감)
[4] check_batches    ─── 완료 상태 폴링 (수 시간~24시간 소요)
[5] download_outputs ─── 완료 파일 다운로드
[6] combine_outputs  ─── 분할 결과 단일 JSONL 통합
[7] merge_metrics    ─── 기존 42개 + 신규 18개 = 60개 지표 병합
[8] validate_merge   ─── 결측치 리포트, 범위 검증
[9] fix_data         ─── 이름/gem_potential 주입, 최종 정규화
        │
[Django] manage.py load_games   ─── PostgreSQL 적재
        │
load_embeddings      ─── text-embedding-3-small → pgvector(1536)
        │
     완성 DB ✅

[이미지 파이프라인] (별도)
fill_header_images → verify_header_images → fix_failed_headers
```

---

## 실행 방법

### 데이터 파이프라인 (신규 게임 추가 시)

```bash
# [1] GPT Batch 요청 파일 생성
python scripts/make_diet_batch.py \
  -i data/final/final_master_games.jsonl \
  -o diet_batch_requests.jsonl

# [2] 1,000개 단위 분할
python scripts/split_batch.py \
  -i diet_batch_requests.jsonl \
  -o batch_requests/

# [3] Batch API 제출
python scripts/submit_batches.py -i batch_requests/

# [4] 완료 상태 확인 (완료까지 반복 실행)
python scripts/check_batches.py

# [5] 결과 다운로드
python scripts/download_outputs.py -o batch_outputs/

# [6] 결과 통합
python scripts/combine_outputs.py \
  -i batch_outputs/ \
  -o batch_output_combined.jsonl

# [7] 60개 지표 병합
python scripts/merge_metrics.py \
  -o data/final/final_master_games.jsonl \
  -b batch_output_combined.jsonl \
  -out data/final/final_master_games_merged.jsonl

# [8] 품질 검증
python scripts/validate_merge.py -i data/final/final_master_games_merged.jsonl

# [9] 최종 데이터 보정
python scripts/fix_data.py

# Django 적재
cd django_core
python manage.py load_games --input ../data/final/final_master_games_fixed.jsonl
cd ..

# 임베딩 생성 및 적재
python scripts/load_embeddings.py
```

### 헤더 이미지 파이프라인

```bash
python scripts/fill_header_images.py           # Phase A: CDN URL 생성
python scripts/verify_header_images.py         # Phase B: 404 검증
python scripts/fix_failed_headers.py           # Phase C: Steam API 복구
```

---

## 파일별 상세 설명

### `make_diet_batch.py` — GPT Batch 요청 파일 생성

60개 지표 추출에 필요한 핵심 텍스트만 추려 OpenAI Batch API 형식의 JSONL을 생성.
불필요한 필드 제거로 토큰 비용을 절감한다.

**주요 함수**

| 함수 | 역할 |
|------|------|
| `extract_diet_text(game)` | description, genres, tags 등 핵심 필드만 추출 (토큰 절약) |
| `create_batch_request(game)` | OpenAI Batch API 형식 dict 생성 — `custom_id`: `game_{app_id}` |
| `main()` | JSONL 읽기 → diet 텍스트 생성 → 요청 파일 저장, `--preview` 옵션 지원 |

```bash
python scripts/make_diet_batch.py -i data/final/final_master_games.jsonl -o diet.jsonl
python scripts/make_diet_batch.py -i data/final/final_master_games.jsonl --preview  # 3개 미리보기
```

---

### `split_batch.py` — 파일 분할

OpenAI Batch API 파일 크기 제한(100MB, 50,000행) 대응.
실용적 안전 기준인 1,000개 단위 ceiling division으로 분할.

**주요 함수**

| 함수 | 역할 |
|------|------|
| `split_jsonl(input_path, output_dir, chunk_size)` | JSONL을 chunk_size 단위로 분할, ceiling division으로 파일 수 계산 |
| `main()` | CLI 파싱 후 `split_jsonl()` 호출 |

```bash
python scripts/split_batch.py -i diet.jsonl -o batch_requests/
python scripts/split_batch.py -i diet.jsonl -o batch_requests/ --chunk-size 500
```

출력: `batch_requests/batch_001.jsonl`, `batch_002.jsonl`, ...

---

### `submit_batches.py` — Batch API 제출

분할된 파일을 OpenAI에 순차 제출. 동기 API 대비 ~50% 비용, 처리 시간 최대 24시간.

**주요 함수**

| 함수 | 역할 |
|------|------|
| `submit_batch(file_path)` | 2단계: 파일 업로드 → Batch 생성, Batch ID 반환 |
| `main()` | 디렉토리 내 모든 `.jsonl` 파일 제출, ID를 `batch_ids.json`에 저장 |

```bash
python scripts/submit_batches.py -i batch_requests/
```

---

### `check_batches.py` — 상태 확인

`batch_ids.json`에서 ID를 읽어 각 Batch의 완료 여부를 확인.
완료된 Batch의 `output_file_id`를 `completed_batches.json`에 저장.

**주요 함수**

| 함수 | 역할 |
|------|------|
| `main()` | Batch ID 순회 → 상태 조회 → `output_file_id` 수집 및 저장 |

상태 흐름: `validating` → `in_progress` → `completed`

```bash
python scripts/check_batches.py  # 완료까지 주기적으로 반복 실행
```

---

### `download_outputs.py` — 결과 다운로드

`completed_batches.json`의 `output_file_id`로 결과 JSONL을 다운로드.

**주요 함수**

| 함수 | 역할 |
|------|------|
| `main()` | `output_file_id` 순회 → 파일 내용 다운로드 → 디렉토리 저장 |

```bash
python scripts/download_outputs.py -o batch_outputs/
```

---

### `combine_outputs.py` — 결과 통합

분할 다운로드된 결과 JSONL들을 단일 파일로 통합.
app_id 기준 알파벳 정렬을 보장한다.

**주요 함수**

| 함수 | 역할 |
|------|------|
| `main()` | 디렉토리 내 `*.jsonl` 순차 읽기 → 단일 파일 스트리밍 쓰기 |

```bash
python scripts/combine_outputs.py -i batch_outputs/ -o batch_output_combined.jsonl
```

---

### `merge_metrics.py` — 지표 병합

기존 42개 지표 JSONL + GPT 신규 18개 지표 JSONL → 60개 완성 데이터셋.
누락 지표는 `5.0`(중간값)으로 fallback. 처리 결과를 `_merge_meta` 필드에 기록.

**주요 함수**

| 함수 | 역할 |
|------|------|
| `parse_batch_output(line)` | `custom_id`에서 `app_id` 추출, GPT 응답 JSON 파싱 |
| `merge_game_data(original, batch_result)` | 기존 + 신규 지표 병합, `_merge_meta`에 처리 이력 기록 |
| `main()` | 스트리밍 처리 — 대용량 JSONL을 메모리 효율적으로 처리 |

```bash
python scripts/merge_metrics.py \
  -o data/final/final_master_games.jsonl \
  -b batch_output_combined.jsonl \
  -out data/final/final_master_games_merged.jsonl
```

---

### `validate_merge.py` — 데이터 검증

병합 결과의 결측치 비율, 지표 범위 이상값, 필수 필드 누락을 리포트.
`load_games.py` 실행 전 필수 검증 단계.

**주요 함수**

| 함수 | 역할 |
|------|------|
| `extract_all_metrics(data)` | 게임 dict에서 60개 지표값 추출, (이름, 값, 범위초과 여부) 튜플 반환 |
| `generate_report(games)` | 전체 결측치 비율, 범위 이상, 게임별 요약 리포트 생성 |
| `main()` | JSONL 읽기 → 검증 → 리포트 출력, `--detailed` 옵션으로 게임별 상세 출력 |

```bash
python scripts/validate_merge.py -i data/final/final_master_games_merged.jsonl
python scripts/validate_merge.py -i data/final/final_master_games_merged.jsonl --detailed
```

---

### `fix_data.py` — 최종 데이터 보정

Steam CSV 원본의 게임 이름과 `gem_potential`을 JSONL에 주입.
`load_games.py`가 읽을 수 있는 형식으로 정규화.

**주요 처리**
- NaN 값 정제
- `gem_potential` 위치 정규화 (최상위 필드로 이동 — `load_games.py` 참조용)
- `_csv_extra` 필드에 CSV 원본 데이터 백업

입출력 경로: 스크립트 내부 상수로 고정 (`data/final/` 하위)

```bash
python scripts/fix_data.py
```

---

### `load_embeddings.py` — 임베딩 적재

`text-embedding-3-small`로 게임 임베딩을 생성하고 pgvector `vector(1536)` 컬럼에 적재.
Django ORM 우회하여 SQLAlchemy async로 직접 bulk INSERT.

**주요 함수**

| 함수 | 역할 |
|------|------|
| `main()` | 4단계: 미처리 게임 조회 → 텍스트 구성 → OpenAI API 호출 → pgvector 저장 |

**전제 조건**
- `OPENAI_API_KEY` 환경변수
- `DATABASE_URL` 환경변수
- pgvector 확장 및 `vector(1536)` 컬럼 존재

```bash
python scripts/load_embeddings.py
python scripts/load_embeddings.py --limit 50   # 테스트용
python scripts/load_embeddings.py --force      # 기존 임베딩 재생성
```

---

### `fill_header_images.py` — 헤더 이미지 URL 생성 (Phase A)

`app_id`로 Steam CDN URL을 생성하여 DB에 일괄 저장. 실제 접근 가능 여부는 검증 안 함.

**주요 함수**

| 함수 | 역할 |
|------|------|
| `fetch_targets(db, force)` | DB에서 처리 대상 게임 조회 (force=False면 기존 URL 있는 게임 제외) |
| `bulk_update_headers(db, updates)` | 배치 단위 UPDATE, 실패 시 배치 롤백 |

```bash
python scripts/fill_header_images.py
python scripts/fill_header_images.py --force   # 기존 URL 덮어쓰기
```

---

### `verify_header_images.py` — 이미지 URL 검증 (Phase B)

모든 게임의 `header_image`에 비동기 HEAD 요청으로 404를 탐지.
실패 시 대체 URL 순서대로 재시도. `asyncio.Semaphore`로 동시 요청 수 제한.

**URL 시도 순서**
1. `/header.jpg`
2. `/capsule_616x353.jpg`
3. `/capsule_467x181.jpg`
4. `/capsule_231x87.jpg`
5. `/library_600x900.jpg`

**주요 함수**

| 함수 | 역할 |
|------|------|
| `check_url(session, url, timeout)` | HTTP HEAD 요청 — GET 대신 HEAD로 본문 다운로드 없이 200 확인 |
| `find_valid_url(session, app_id)` | URL_CANDIDATES 순서대로 시도, 첫 성공 URL 반환 |
| `process_game(sem, http, db_factory, app_id, game_id)` | Semaphore로 동시 요청 제한 + 성공 즉시 개별 DB UPDATE |
| `main()` | 전체 게임 비동기 병렬 처리, 실패분 일괄 `header_image=""` 마킹 |

```bash
python scripts/verify_header_images.py
python scripts/verify_header_images.py --concurrency 20  # 기본 15
python scripts/verify_header_images.py --limit 100       # 테스트용
python scripts/verify_header_images.py --timeout 8.0     # 타임아웃 초
```

---

### `fix_failed_headers.py` — Steam API 복구 (Phase C)

`header_image`가 비어있는 게임을 Steam Store API로 직접 조회하여 복구.

**주요 함수**

| 함수 | 역할 |
|------|------|
| `fetch_steam_header(session, app_id, sem)` | Steam `/api/appdetails` 호출, `success=false`(삭제/비공개)면 None 반환 |
| `main()` | 빈 URL 게임 조회 → API 호출 → 성공분 DB UPDATE, 실패분은 `""` 유지 |

```bash
python scripts/fix_failed_headers.py
python scripts/fix_failed_headers.py --dry-run          # DB 변경 없이 미리보기
python scripts/fix_failed_headers.py --concurrency 10   # 기본 5
```

---

### `extract_sample.py` — 샘플 추출 유틸리티

`gem_potential` 기준 상위 10개 게임을 CSV로 추출. 데이터 검수 및 품질 확인용.

**주요 처리**
- 정렬: `gem_potential` 내림차순 → `indie_spirit` 내림차순
- 출력: BOM 포함 UTF-8 (`utf-8-sig`) — Excel 한글 깨짐 방지

```bash
python scripts/extract_sample.py
python scripts/extract_sample.py -o output/top_gems.csv  # 출력 경로 지정
```

---

## 기술 스택

| 라이브러리 | 용도 |
|------------|------|
| openai | GPT-5.4 Batch API, text-embedding-3-small |
| sqlalchemy (async) | FastAPI DB에 직접 접근 (임베딩 적재) |
| asyncpg | PostgreSQL 비동기 드라이버 |
| pgvector | `Vector(1536)` 타입 — SQLAlchemy 연동 |
| aiohttp | 비동기 HTTP (헤더 이미지 검증) |
| tqdm | 진행률 표시 |
| pandas | CSV 처리 (`fix_data.py`, `extract_sample.py`) |
| python-dotenv | `.env` 환경변수 로드 |

---

## DB 접속

```bash
docker exec -it hidden_gem_db psql -U juntae -d hidden_gem_db
```

```sql
-- 현황 요약
SELECT
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE is_analyzed) AS analyzed,
  COUNT(*) FILTER (WHERE header_image != '' AND header_image IS NOT NULL) AS has_image,
  COUNT(*) FILTER (WHERE header_image = '' OR header_image IS NULL) AS no_image
FROM games;

-- 임베딩 현황 (game_metrics 테이블)
SELECT
  COUNT(*) AS total_metrics,
  COUNT(*) FILTER (WHERE embedding IS NOT NULL) AS has_embedding,
  COUNT(*) FILTER (WHERE embedding IS NULL) AS no_embedding
FROM game_metrics;

-- gem_potential 분포
SELECT
  FLOOR(gem_potential) AS score,
  COUNT(*) AS count
FROM game_metrics
GROUP BY 1
ORDER BY 1 DESC;
```

---

## 환경변수 (.env)

```env
# OpenAI — Batch API + 임베딩 생성
OPENAI_API_KEY=sk-...

# DB — load_embeddings.py 직접 접속용
DATABASE_URL=postgresql+asyncpg://juntae:0312@localhost:5432/hidden_gem_db
```

Django DB 설정은 `django_core/config/settings.py` 참조.

---

## 다음 할 일

- [ ] `verify_header_images.py` 전체 4,190개 실행
- [ ] `fix_failed_headers.py` 실패분 복구
- [ ] 프론트엔드 (Next.js) 시작
- [ ] 유저 시스템 구현 (로그인, 좋아요, taste_dna)
