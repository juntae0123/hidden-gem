# 📂 Hidden Gem - scripts/ 가이드

> 실행 위치: 항상 프로젝트 루트 (`C:\Hidden-Gem-project\`)  
> 가상환경: `source .venv/Scripts/activate`

---

## 🗺️ 전체 흐름

```
[1단계] GPT Batch로 60개 지표 추출
make_diet_batch → split_batch → submit_batches
→ check_batches → download_outputs → combine_outputs
→ merge_metrics → validate_merge → fix_data
                                        ↓
                                   DB 적재 (load_games)

[2단계] 헤더 이미지 채우기
fill_header_images → verify_header_images → fix_failed_headers
```

---

## 📦 스크립트 목록

### 1️⃣ 데이터 파이프라인 (이미 완료 ✅)

| 순서 | 파일 | 역할 | 상태 |
|------|------|------|------|
| 1 | `make_diet_batch.py` | JSONL → GPT Batch 요청 파일 생성 | ✅ 완료 |
| 2 | `split_batch.py` | 요청 파일 1000개씩 분할 | ✅ 완료 |
| 3 | `submit_batches.py` | OpenAI Batch API 제출 | ✅ 완료 |
| 4 | `check_batches.py` | Batch 진행 상태 확인 | ✅ 완료 |
| 5 | `download_outputs.py` | Batch 결과 다운로드 | ✅ 완료 |
| 6 | `combine_outputs.py` | 분할된 결과 하나로 합치기 | ✅ 완료 |
| 7 | `merge_metrics.py` | 기존 42개 + 신규 18개 = 60개 병합 | ✅ 완료 |
| 8 | `validate_merge.py` | 병합 결과 검증 (결측치 리포트) | ✅ 완료 |
| 9 | `fix_data.py` | CSV + JSONL 병합 (이름/gem_potential 주입) | ✅ 완료 |

```bash
# 재실행 필요 시 (신규 게임 추가 등)
python scripts/make_diet_batch.py -i data/final/final_master_games.jsonl -o diet_batch_requests.jsonl
python scripts/split_batch.py -i diet_batch_requests.jsonl -o batch_requests/
python scripts/submit_batches.py -i batch_requests/
python scripts/check_batches.py
python scripts/download_outputs.py -o batch_outputs/
python scripts/combine_outputs.py -i batch_outputs/ -o batch_output_combined.jsonl
python scripts/merge_metrics.py -o data/final/final_master_games.jsonl -b batch_output_combined.jsonl -out data/final/final_master_games_merged.jsonl
python scripts/validate_merge.py -i data/final/final_master_games_merged.jsonl
python scripts/fix_data.py
```

---

### 2️⃣ 헤더 이미지 파이프라인 (진행중 🔄)

| 순서 | 파일 | 역할 | 상태 |
|------|------|------|------|
| 1 | `fill_header_images.py` | app_id → CDN URL 일괄 생성 | ✅ 완료 (4190개) |
| 2 | `verify_header_images.py` | HEAD 요청으로 404 탐지 | 🔄 전체 실행 필요 |
| 3 | `fix_failed_headers.py` | Steam API로 신규 URL 패턴 복구 | 🔄 verify 후 실행 |

```bash
# Phase A - 최초 1회 (완료)
python scripts/fill_header_images.py

# Phase B - 검증 (전체 4190개)
python scripts/verify_header_images.py

# Phase C - 실패분 복구
python scripts/fix_failed_headers.py

# 결과 확인
docker exec -it hidden_gem_db psql -U juntae -d hidden_gem_db -c \
  "SELECT COUNT(*) as filled, COUNT(*) FILTER (WHERE header_image='') as empty FROM games;"
```

> ⚠️ **주의**: 최근 Steam 게임(app_id 3,000,000+)은 CDN URL 패턴이 달라서  
> `verify` → `fix_failed_headers` 순서로 반드시 실행할 것.

---

### 3️⃣ 유틸리티

| 파일 | 역할 | 사용법 |
|------|------|--------|
| `extract_sample.py` | gem_potential 상위 10개 샘플 추출 | `python scripts/extract_sample.py` |

---

## 🗄️ DB 접속

```bash
docker exec -it hidden_gem_db psql -U juntae -d hidden_gem_db
```

```sql
-- 현황 확인
SELECT
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE is_analyzed) AS analyzed,
  COUNT(*) FILTER (WHERE header_image != '' AND header_image IS NOT NULL) AS has_image,
  COUNT(*) FILTER (WHERE header_image = '' OR header_image IS NULL) AS no_image
FROM games;
```

---

## 📝 환경 변수 (.env)

```
OPENAI_API_KEY=sk-...   # GPT Batch용 (데이터 파이프라인)
```

DB 접속 정보는 `fastapi_app/config.py` 참조.

---

## 🚨 다음 할 일

- [ ] `verify_header_images.py` 전체 4190개 실행
- [ ] `fix_failed_headers.py` 실패분 복구
- [ ] 프론트엔드 (Next.js) 시작
- [ ] 유저 시스템 구현 (로그인, 좋아요, taste_dna)
- [ ] 벡터 DB 마이그레이션 검토 (pgvector)
