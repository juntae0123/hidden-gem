# scripts/

Hidden Gem 데이터 파이프라인 + 운영 스크립트 모음.

실행 위치: 항상 **프로젝트 루트** (`C:\Hidden-Gem-project\`)
가상환경: `source .venv/Scripts/activate`

---

## 폴더 구조

```
scripts/
├── backup/                     # DB 백업 + 스케줄러 등록
│   ├── backup_db.sh            # pg_dump → gzip 백업 실행
│   ├── setup_cron.sh           # WSL/Linux cron 등록
│   └── setup_task_scheduler.ps1 # Windows Task Scheduler 등록 (권장)
│
├── pipeline/                   # GPT Batch API → DB 적재 전체 파이프라인
│   ├── make_diet_batch.py      # [1] GPT Batch 요청 파일 생성
│   ├── split_batch.py          # [2] 1,000개 단위 분할
│   ├── submit_batches.py       # [3] OpenAI Batch API 제출
│   ├── check_batches.py        # [4] 완료 상태 확인
│   ├── download_outputs.py     # [5] 결과 파일 다운로드
│   ├── combine_outputs.py      # [6] 분할 결과 통합
│   ├── merge_metrics.py        # [7] 60개 지표 병합
│   ├── validate_merge.py       # [8] 데이터 품질 검증
│   ├── fix_data.py             # [9] CSV 메타데이터 보완
│   └── load_embeddings.py      # pgvector 임베딩 적재
│
├── images/                     # Steam 헤더 이미지 파이프라인
│   ├── fill_header_images.py   # [A] CDN URL 일괄 생성
│   ├── verify_header_images.py # [B] HEAD 요청으로 404 탐지
│   └── fix_failed_headers.py   # [C] Steam API로 URL 복구
│
├── utils/                      # 유틸리티
│   └── extract_sample.py       # gem_potential 상위 샘플 추출
│
└── README.md
```

---

## 1. DB 백업 (`backup/`)

### 수동 실행

```bash
bash scripts/backup/backup_db.sh
```

- 백업 저장: `C:\Hidden-Gem-project\backups\db_YYYYMMDD_HHMMSS.sql.gz`
- 로그: `backups/backup.log`
- 7일 초과 파일 자동 삭제

### 자동화 등록 (Windows — 권장)

```powershell
# PowerShell 관리자 권한으로 실행
PowerShell -ExecutionPolicy Bypass -File scripts\backup\setup_task_scheduler.ps1
```

→ 매일 새벽 3:00 AM 자동 실행 등록

### 자동화 등록 (WSL/Linux)

```bash
bash scripts/backup/setup_cron.sh
```

---

## 2. 데이터 파이프라인 (`pipeline/`)

신규 게임 추가 또는 지표 재분석 시 사용.

```
Steam CSV 원본
    ↓
[1] make_diet_batch    GPT Batch 요청 파일 생성
[2] split_batch        1,000개 단위 분할
[3] submit_batches     OpenAI Batch API 제출 (동기 대비 ~50% 비용 절감)
[4] check_batches      완료 상태 확인 (수 시간~24시간 소요)
[5] download_outputs   완료 파일 다운로드
[6] combine_outputs    분할 결과 단일 JSONL 통합
[7] merge_metrics      기존 42개 + 신규 18개 = 60개 지표 병합
[8] validate_merge     결측치/범위 검증
[9] fix_data           이름/gem_potential 주입, 최종 정규화
    ↓
Django manage.py load_games   PostgreSQL 적재
    ↓
load_embeddings               pgvector 임베딩 적재
```

### 전체 실행 순서

```bash
# [1] Batch 요청 파일 생성
python scripts/pipeline/make_diet_batch.py \
  -i data/final/final_master_games.jsonl \
  -o diet_batch_requests.jsonl

# [2] 1,000개 단위 분할
python scripts/pipeline/split_batch.py \
  -i diet_batch_requests.jsonl \
  -o batch_requests/

# [3] Batch API 제출
python scripts/pipeline/submit_batches.py -i batch_requests/

# [4] 완료 상태 확인 (완료될 때까지 반복)
python scripts/pipeline/check_batches.py

# [5] 결과 다운로드
python scripts/pipeline/download_outputs.py -o batch_outputs/

# [6] 결과 통합
python scripts/pipeline/combine_outputs.py \
  -i batch_outputs/ \
  -o batch_output_combined.jsonl

# [7] 60개 지표 병합
python scripts/pipeline/merge_metrics.py \
  -o data/final/final_master_games.jsonl \
  -b batch_output_combined.jsonl \
  -out data/final/final_master_games_merged.jsonl

# [8] 품질 검증
python scripts/pipeline/validate_merge.py \
  -i data/final/final_master_games_merged.jsonl

# [9] 최종 데이터 보정
python scripts/pipeline/fix_data.py

# Django 적재
cd django_core
python manage.py load_games \
  --input ../data/final/final_master_games_fixed.jsonl
cd ..

# 임베딩 적재
python scripts/pipeline/load_embeddings.py
```

---

## 3. 헤더 이미지 파이프라인 (`images/`)

```bash
# [A] CDN URL 일괄 생성 (네트워크 없이 빠름)
python scripts/images/fill_header_images.py

# [B] HEAD 요청으로 404 탐지 + 대체 URL 시도
python scripts/images/verify_header_images.py

# [C] 여전히 빈 게임을 Steam API로 복구
python scripts/images/fix_failed_headers.py
```

---

## 4. 유틸리티 (`utils/`)

```bash
# gem_potential 상위 10개 샘플 추출 (데이터 검수용)
python scripts/utils/extract_sample.py
```

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
  COUNT(*) FILTER (WHERE header_image != '') AS has_image
FROM games;

-- gem_potential 분포
SELECT FLOOR(gem_potential) AS score, COUNT(*) AS count
FROM game_metrics
GROUP BY 1 ORDER BY 1 DESC;

-- 임베딩 현황
SELECT
  COUNT(*) FILTER (WHERE embedding IS NOT NULL) AS has_embedding,
  COUNT(*) FILTER (WHERE embedding IS NULL) AS no_embedding
FROM game_metrics;
```

---

## 환경변수 (`.env`)

```env
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql+asyncpg://juntae:0312@localhost:5432/hidden_gem_db
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...  # 선택
```
