# Hidden Gem

> Steam 인디 게임 AI 추천 서비스 — 4,190개 게임 × 60개 지표 분석

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Django](https://img.shields.io/badge/Django-5.0+-092E20?style=flat-square&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![pgvector](https://img.shields.io/badge/pgvector-HNSW-orange?style=flat-square)](https://github.com/pgvector/pgvector)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--5.4%20%7C%20Embeddings-412991?style=flat-square&logo=openai&logoColor=white)](https://openai.com/)
[![Docker](https://img.shields.io/badge/Docker-PostgreSQL-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)

---

## 개요

Hidden Gem은 Steam 인디 게임을 **60개 AI 분석 지표**로 평가하고, **49차원 지표 벡터 + 1536차원 임베딩**을 결합한 하이브리드 알고리즘으로 숨은 명작을 추천하는 서비스입니다.

- **데이터**: GPT-5.4 Batch API로 4,190개 게임 × 60개 지표 추출
- **추천**: 코사인 유사도 + 유클리디안 거리 + 벡터 임베딩 하이브리드
- **관리**: Django Admin으로 게임 데이터 관리, FastAPI로 추천 API 서빙

---

## 아키텍처

```
┌───────────────────────────────────────────────────────────────┐
│                      클라이언트 (Frontend)                     │
│                   Next.js / React (예정)                      │
└──────────────────────────┬────────────────────────────────────┘
                           │ HTTP
         ┌─────────────────┼─────────────────┐
         ▼                                   ▼
┌─────────────────┐               ┌──────────────────────┐
│  FastAPI :8000  │               │   Django :8001        │
│  (추천 API)     │               │   (Admin 전용)        │
│                 │               │                       │
│  /api/v1/games/ │               │  /admin/              │
│    search       │               │  /admin/games/        │
│    recommend    │               │  /admin/users/        │
│    by-game      │               │                       │
│    by-preference│               │  Few-Shot 분석        │
│    /{app_id}    │               │  (새 게임 추가 시)    │
└───────┬─────────┘               └──────────┬────────────┘
        │ SQLAlchemy (async)       Django ORM │
        │ read-only                read/write │
        └────────────┬────────────────────────┘
                     ▼
       ┌─────────────────────────┐
       │  PostgreSQL + pgvector  │
       │  Docker :5432           │
       │                         │
       │  games (4,190행)        │
       │  game_metrics (60개)    │
       │  embedding vector(1536) │
       │  HNSW index             │
       └─────────────────────────┘
                     ▲
       ┌─────────────┴─────────────┐
       │      Redis Pub/Sub        │
       │  hidden_gem:game_updates  │
       └───────────────────────────┘
            ▲                   ▲
   Django Signal          FastAPI Subscriber
 (게임 추가/수정 시)      (캐시 무효화 등)
```

---

## 데이터 파이프라인

```
Steam CSV 원본 데이터
        │
        ▼
[1] make_diet_batch.py   ─── JSONL → GPT Batch 요청 파일 (토큰 최적화)
        │
        ▼
[2] split_batch.py       ─── 1,000개 단위 분할 (OpenAI 파일 크기 제한)
        │
        ▼
[3] submit_batches.py    ─── OpenAI Batch API 제출 (비동기, ~50% 비용 절감)
        │
        ▼
[4] check_batches.py     ─── 완료 상태 폴링 + output_file_id 수집
        │
        ▼
[5] download_outputs.py  ─── 완료된 Batch 결과 파일 다운로드
        │
        ▼
[6] combine_outputs.py   ─── 분할된 결과 단일 JSONL로 통합
        │
        ▼
[7] merge_metrics.py     ─── 기존 42개 + 신규 18개 = 60개 지표 병합
        │
        ▼
[8] validate_merge.py    ─── 결측치 리포트, 데이터 품질 검증
        │
        ▼
[9] fix_data.py          ─── CSV + JSONL 병합, gem_potential 주입
        │
        ▼
[Django] load_games.py   ─── PostgreSQL 적재 (bulk_create, upsert)
        │
        ▼
[scripts] load_embeddings.py ─── text-embedding-3-small → pgvector(1536)
        │
        ▼
     완성 DB ✅

헤더 이미지 파이프라인 (별도):
fill_header_images → verify_header_images → fix_failed_headers
```

---

## 추천 알고리즘

### by-game (특정 게임 기반)

임베딩이 있을 때:
```
score = cosine_similarity(49D) × 0.35
      + euclidean_similarity(49D) × 0.35
      + cosine_similarity(1536D embedding) × 0.30
      + gem_bonus
```

임베딩 없을 때 (fallback):
```
score = cosine_similarity(49D) × 0.50
      + euclidean_similarity(49D) × 0.50
      + gem_bonus
```

### by-preference (선호도 기반)

```
score = euclidean_similarity(user_pref → game_metrics) × 0.60
      + cosine_similarity(user_pref → game_metrics) × 0.40
      + gem_bonus

※ 사용자가 명시한 지표에 2.5× 가중치 적용
```

### 유클리디안 유사도 정규화

```
euclidean_similarity = max(0, 1 - distance / max_distance)
# max_distance = 30.0  (49D 벡터 실험적 최대값)
```

### Hidden Gem 보너스

```
gem_bonus = (gem_potential/100 × 0.10 + review_bonus) × confidence_score

review_bonus:
  리뷰 < 500    → +0.05  (숨은 명작 보너스)
  리뷰 < 2,000  → +0.02
  리뷰 >= 2,000 → 0
```

### 60개 지표 구성

| 카테고리 | 개수 | 예시 |
|----------|------|------|
| VIBE | 7 | cozy_factor, horror_factor, gore_level |
| DEMANDS | 5 | reflex_demand, strategic_depth, learning_curve |
| MECHANICS | 11 | freedom_level, action_pacing, rng_dependency |
| SOCIAL | 5 | coop_synergy, competitive_stress, npc_interaction |
| PRESENTATION | 5 | lore_richness, choice_consequence, visual_spectacle |
| SYSTEM/UX | 7 | build_variety, save_flexibility, ui_ux_polish |
| ART/AUDIO | 3 | art_style_uniqueness, audio_design, animation_quality |
| OTHER | 2 | world_reactivity, community_dependency |
| NEW | 4 | narrative_depth, replay_value, monetization_fairness |
| TAGS (bool) | 9 | is_turn_based, has_crafting, has_permadeath |
| EVAL | 2 | gem_potential (0~100), confidence_score (0~1) |

---

## API 엔드포인트

Base URL: `http://localhost:8000/api/v1`

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/games/search` | 이름/장르/개발사 텍스트 검색 |
| `GET` | `/games/stats/overview` | DB 통계 (게임 수, 평균 gem_potential) |
| `GET` | `/games/metrics/list` | 사용 가능한 지표 목록 (49개 수치 + 9개 태그) |
| `GET` | `/games/{app_id}` | 게임 상세 + 60개 지표 전체 |
| `POST` | `/games/recommend/by-game` | 특정 게임 기반 유사 게임 추천 |
| `POST` | `/games/recommend/by-preference` | 유저 선호도 기반 맞춤 추천 |

### 요청 예시

**by-game 추천**
```json
POST /api/v1/games/recommend/by-game
{
  "app_id": 1086940,
  "count": 5,
  "exclude_same_developer": false
}
```

**by-preference 추천**
```json
POST /api/v1/games/recommend/by-preference
{
  "preferences": {
    "cozy_factor": 8,
    "strategic_depth": 7,
    "horror_factor": 1
  },
  "required_tags": ["has_crafting"],
  "excluded_tags": ["has_permadeath"],
  "count": 5,
  "min_gem_potential": 60
}
```

**검색**
```
GET /api/v1/games/search?q=hollow&min_gem=70&limit=10
```

Swagger UI: `http://localhost:8000/docs`

---

## 설치 및 실행

### 사전 요구사항

- Python 3.11+
- Docker Desktop
- OpenAI API Key (데이터 파이프라인 재실행 시)

### 1. 환경 설정

```bash
git clone https://github.com/your-username/hidden-gem-project.git
cd Hidden-Gem-project

# 가상환경 생성 및 활성화
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac/Linux

# 의존성 설치
pip install -r fastapi_app/requirements.txt
pip install -r django_core/requirements.txt
```

### 2. 환경변수 (.env)

```env
# DB
DB_NAME=hidden_gem_db
DB_USER=juntae
DB_PASSWORD=0312
DB_HOST=localhost
DB_PORT=5432

# FastAPI
DATABASE_URL=postgresql+asyncpg://juntae:0312@localhost:5432/hidden_gem_db
SECRET_KEY=your-secret-key

# Django
DJANGO_SECRET_KEY=your-django-secret-key
DJANGO_DEBUG=True

# OpenAI (데이터 파이프라인용)
OPENAI_API_KEY=sk-...

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 3. PostgreSQL + pgvector (Docker)

```bash
# PostgreSQL + pgvector 컨테이너 시작
docker run -d \
  --name hidden_gem_db \
  -e POSTGRES_DB=hidden_gem_db \
  -e POSTGRES_USER=juntae \
  -e POSTGRES_PASSWORD=0312 \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# pgvector 확장 활성화
docker exec -it hidden_gem_db psql -U juntae -d hidden_gem_db \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 4. Django 마이그레이션

```bash
cd django_core
python manage.py migrate
python manage.py createsuperuser
```

### 5. 데이터 적재

```bash
# 게임 데이터 + 지표 적재 (Django)
cd django_core
python manage.py load_games --input ../data/final/final_master_games_fixed.jsonl

# 임베딩 생성 + 적재 (scripts)
cd ..
python scripts/load_embeddings.py
```

### 6. 서버 실행

**FastAPI** (추천 API, 포트 8000)
```bash
cd fastapi_app
uvicorn main:app --reload --port 8000
```

**Django** (Admin, 포트 8001)
```bash
cd django_core
python manage.py runserver 8001
```

**Redis** (Django↔FastAPI 동기화)
```bash
docker run -d --name redis -p 6379:6379 redis:alpine
```

---

## 폴더 구조

```
Hidden-Gem-project/
├── fastapi_app/                 # FastAPI 추천 API 서버 (포트 8000)
│   ├── main.py                  # 앱 엔트리포인트, CORS, lifespan
│   ├── config.py                # 환경변수 설정 (pydantic-settings)
│   ├── database.py              # 비동기 DB 연결 (SQLAlchemy async)
│   ├── models/
│   │   └── game.py              # SQLAlchemy ORM (Game, GameMetric)
│   ├── schemas/
│   │   └── game.py              # Pydantic 요청/응답 스키마
│   ├── routers/
│   │   └── games.py             # API 엔드포인트 6개
│   └── services/
│       └── recommender.py       # 하이브리드 추천 엔진 (핵심 로직)
│
├── django_core/                 # Django 관리 서버 (포트 8001)
│   ├── config/
│   │   ├── settings.py          # Django 설정
│   │   └── urls.py              # URL 라우팅 (admin only)
│   └── apps/
│       ├── games/
│       │   ├── models.py        # Game, GameMetric ORM
│       │   ├── admin.py         # 게임 관리 Admin UI
│       │   ├── signals.py       # Redis Pub/Sub 동기화 시그널
│       │   └── management/commands/
│       │       ├── load_games.py         # JSONL → DB 적재
│       │       └── analyze_new_games.py  # Few-Shot 신규 게임 분석
│       └── users/
│           ├── models.py        # CustomUser (Steam OAuth 예정)
│           └── admin.py         # 유저 관리 Admin
│
├── scripts/                     # 데이터 파이프라인 스크립트 (14개)
│   ├── make_diet_batch.py       # [1] GPT Batch 요청 파일 생성
│   ├── split_batch.py           # [2] 1,000개 단위 분할
│   ├── submit_batches.py        # [3] OpenAI Batch API 제출
│   ├── check_batches.py         # [4] 완료 상태 확인
│   ├── download_outputs.py      # [5] 결과 다운로드
│   ├── combine_outputs.py       # [6] 결과 통합
│   ├── merge_metrics.py         # [7] 60개 지표 병합
│   ├── validate_merge.py        # [8] 데이터 검증
│   ├── fix_data.py              # [9] CSV+JSONL 병합 및 보정
│   ├── load_embeddings.py       # 임베딩 생성 및 pgvector 적재
│   ├── fill_header_images.py    # 헤더 이미지 CDN URL 생성
│   ├── verify_header_images.py  # 이미지 URL 유효성 검증 (HEAD)
│   ├── fix_failed_headers.py    # Steam API로 이미지 URL 복구
│   ├── extract_sample.py        # gem_potential 상위 샘플 추출
│   └── README.md                # 스크립트 상세 가이드
│
├── data/                        # 데이터 파일 (gitignore)
│   └── final/
│       └── final_master_games_fixed.jsonl
│
├── .env                         # 환경변수 (gitignore)
└── README.md                    # 이 파일
```

---

## 기술 스택

| 레이어 | 기술 | 용도 |
|--------|------|------|
| API | FastAPI 0.115 | 추천 API, 비동기 처리 |
| Admin | Django 5.0 | 게임 데이터 관리 UI |
| DB | PostgreSQL 16 + pgvector | 게임 데이터 + 벡터 저장 |
| Vector Index | HNSW (m=16, ef=64) | 근사 최근접 이웃 검색 |
| ORM | SQLAlchemy 2.0 async / Django ORM | FastAPI / Django 각각 |
| AI 분석 | OpenAI GPT-5.4 Batch | 4,190개 60지표 추출 |
| AI 신규 | GPT-4o-mini Few-Shot | 신규 게임 분석 (~1/60 비용) |
| Embedding | text-embedding-3-small | 1536차원 게임 임베딩 |
| Cache/MQ | Redis Pub/Sub | Django→FastAPI 실시간 동기화 |
| Validation | Pydantic v2 | 요청/응답 스키마 검증 |

---

## 데이터 현황

- **총 게임**: 4,190개 (Steam 인디 게임)
- **60개 지표**: 49개 수치(0~10) + 9개 불리언 태그 + gem_potential + confidence_score
- **임베딩**: 1,536차원 OpenAI 벡터 (pgvector HNSW 인덱스)
- **분석 방법**: GPT-5.4 Batch (원본 4,190개) → Few-Shot gpt-4o-mini (신규 추가)
