# fastapi_app/

Hidden Gem 추천 API 서버. Django가 관리하는 PostgreSQL 데이터를 읽어
하이브리드 유사도 알고리즘으로 게임을 추천한다.

포트: **8000** | 역할: **읽기 전용 추천 API** | DB 접근: **SQLAlchemy async (read-only)**

---

## 폴더 구조

```
fastapi_app/
├── main.py              # 앱 진입점 — FastAPI 인스턴스, CORS, lifespan, 헬스체크
├── config.py            # 환경변수 설정 — pydantic-settings, DB URL 조합
├── database.py          # DB 연결 — 비동기 엔진, 세션 팩토리, get_db()
├── models/
│   └── game.py          # SQLAlchemy ORM — Game, GameMetric 테이블 매핑
├── schemas/
│   └── game.py          # Pydantic 스키마 — 요청/응답 모델 정의
├── routers/
│   └── games.py         # API 엔드포인트 6개 — 검색, 상세, 추천
└── services/
    └── recommender.py   # 추천 엔진 — 하이브리드 유사도 계산 핵심 로직
```

---

## 실행 방법

```bash
# 프로젝트 루트에서
cd fastapi_app
uvicorn main:app --reload --port 8000

# 또는 직접 실행
python main.py
```

서버 기동 후:
- API 문서 (Swagger UI): http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- 헬스체크: http://localhost:8000/health

---

## 파일별 설명

### `main.py` — 앱 진입점

FastAPI 인스턴스 생성, CORS 미들웨어, lifespan 이벤트, 기본 엔드포인트 등록.

| 항목 | 값 |
|------|----|
| 앱 버전 | 2.0.0 |
| API 접두사 | `/api/v1` |
| CORS | 전체 허용 (개발용 — 운영 시 도메인 제한 필요) |

주요 엔드포인트:

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/` | 서비스 기본 정보 |
| `GET` | `/health` | 헬스체크 (Docker/k8s 용) |

---

### `config.py` — 환경변수 설정

```python
from config import settings

settings.DATABASE_URL   # postgresql+asyncpg://...
settings.DEBUG          # SQL 쿼리 로그 출력 여부
settings.API_V1_PREFIX  # "/api/v1"
```

**`Settings` 클래스** (pydantic-settings `BaseSettings` 상속)

| 속성 | 기본값 | 설명 |
|------|--------|------|
| `DB_HOST` | `localhost` | PostgreSQL 호스트 |
| `DB_PORT` | `5432` | PostgreSQL 포트 |
| `DB_USER` | `juntae` | DB 사용자 |
| `DB_NAME` | `hidden_gem_db` | DB 이름 |
| `DEBUG` | `False` | SQLAlchemy SQL 로그 출력 |
| `DEFAULT_RECOMMEND_COUNT` | `5` | 기본 추천 개수 |
| `MAX_RECOMMEND_COUNT` | `20` | 최대 추천 개수 |
| `GEM_POTENTIAL_SCALE` | `100.0` | gem_potential 정규화 기준 |

**`DATABASE_URL` property**: asyncpg 드라이버용 연결 URL 자동 조합.

**`get_settings()`**: `@lru_cache` 싱글톤 — `.env` 파일을 한 번만 읽음.

---

### `database.py` — 비동기 DB 연결

SQLAlchemy 2.0 async 엔진과 세션 팩토리. Django가 생성한 테이블을 읽기 전용으로 접근.

**엔진 파라미터**

| 파라미터 | 값 | 이유 |
|----------|----|------|
| `pool_size` | 10 | 동시 요청 기본 연결 풀 |
| `max_overflow` | 20 | 피크 트래픽 임시 연결 |
| `pool_pre_ping` | True | 끊어진 연결 자동 재시도 |
| `pool_recycle` | 3600 | PostgreSQL 유휴 타임아웃 방지 |
| `expire_on_commit` | False | commit 후 객체 재사용 가능 |
| `autoflush` | False | 의도치 않은 INSERT/UPDATE 방지 |

**`get_db()`**: FastAPI `Depends(get_db)`용 세션 의존성 주입 함수.

```python
@router.get("/games/{app_id}")
async def get_game(app_id: int, db: AsyncSession = Depends(get_db)):
    ...
```

---

### `models/game.py` — SQLAlchemy ORM

Django `games`, `game_metrics` 테이블과 1:1로 매핑. 컬럼명이 Django와 완전히 일치해야 한다.

**`Game`** — `games` 테이블

| 컬럼 그룹 | 주요 필드 |
|-----------|-----------|
| 기본 정보 | `app_id`, `name`, `genres`, `developer`, `publisher` |
| Steam 데이터 | `steam_positive_ratio`, `review_count`, `is_free`, `is_indie` |
| AI 생성 콘텐츠 | `one_line_summary`, `marketing_hook`, `target_personas` |
| 분석 상태 | `is_analyzed`, `analysis_method` (`gpt5.4_batch` / `fewshot` / `manual` / `pending`) |
| 관계 | `metrics` → `GameMetric` (1:1, lazy select) |

**`GameMetric`** — `game_metrics` 테이블

| 컬럼 그룹 | 개수 | 타입 |
|-----------|------|------|
| VIBE | 7 | Float (0~10) |
| DEMANDS | 5 | Float (0~10) |
| MECHANICS | 11 | Float (0~10) |
| SOCIAL | 5 | Float (0~10) |
| PRESENTATION | 5 | Float (0~10) |
| SYSTEM/UX | 7 | Float (0~10) |
| ART/AUDIO | 3 | Float (0~10) |
| OTHER | 2 | Float (0~10) |
| NEW | 4 | Float (0~10) |
| TAGS | 9 | Boolean |
| EVAL | 2 | Float (gem_potential 0~100, confidence 0~1) |
| EMBEDDING | 1 | `Vector(1536)` (pgvector) |

**모듈 레벨 상수**

| 이름 | 내용 |
|------|------|
| `NUMERIC_METRIC_FIELDS` | 추천 벡터화에 사용하는 49개 수치 지표명 리스트 |
| `BOOLEAN_TAG_FIELDS` | 9개 불리언 태그명 리스트 |
| `METRIC_CATEGORIES` | 카테고리별 지표 분류 dict (프론트 UI 구성용) |

---

### `schemas/game.py` — Pydantic 스키마

API 요청 검증 및 응답 직렬화에 사용하는 Pydantic v2 모델.

**응답 스키마**

| 클래스 | 설명 |
|--------|------|
| `GameMetricResponse` | 60개 지표 전체 응답 |
| `GameResponse` | 게임 기본 정보 응답 |
| `GameWithMetrics` | `GameResponse` + `GameMetricResponse` 통합 |
| `GameSearchResult` | 검색 결과 간략 응답 (8개 필드) |

**요청 스키마**

| 클래스 | 주요 필드 |
|--------|-----------|
| `RecommendByGameRequest` | `app_id`, `count` (1~20), `exclude_same_developer` |
| `RecommendByPreferenceRequest` | `preferences` (Dict), `required_tags`, `excluded_tags`, `count`, `min_gem_potential` |

**추천 응답 스키마**

| 클래스 | 주요 필드 |
|--------|-----------|
| `RecommendedGame` | `app_id`, `similarity_score` (0~1), `match_reasons`, `key_metrics` |
| `RecommendationResponse` | `query_type`, `reference_game`, `total_candidates`, `recommendations` |

---

### `routers/games.py` — API 엔드포인트

prefix: `/api/v1/games`

| Method | Path | 함수 | 설명 |
|--------|------|------|------|
| `GET` | `/search` | `search_games()` | 이름/장르/개발사 ilike 검색, min_gem 필터 |
| `GET` | `/stats/overview` | `get_stats()` | DB 통계 (게임 수, 평균 gem_potential) |
| `GET` | `/metrics/list` | `list_metrics()` | 사용 가능한 지표 목록 |
| `GET` | `/{app_id}` | `get_game_detail()` | 게임 상세 + 60개 지표 전체 |
| `POST` | `/recommend/by-game` | `recommend_by_game()` | 특정 게임 기반 추천 |
| `POST` | `/recommend/by-preference` | `recommend_by_preference()` | 선호도 기반 추천 |

**`search_games()` 주요 동작**
- `ilike` 검색: 이름/장르/개발사 OR 조건 (대소문자 무시)
- `min_gem` 필터: JOIN 복잡성 회피를 위해 Python 레벨에서 처리
- 정렬: `review_count DESC` (검증된 인기 게임 우선)

**`recommend_by_preference()` 주요 동작**
- 지표명/태그명 사전 검증 → 잘못된 키는 400 에러
- `NUMERIC_METRIC_FIELDS` / `BOOLEAN_TAG_FIELDS` 기준으로 검증

---

### `services/recommender.py` — 추천 엔진

**`GameRecommender` 클래스** (모듈 레벨 싱글톤 `recommender` 로 export)

**초기화 상수**

| 속성 | 값 | 설명 |
|------|----|------|
| `dimension` | 49 | 수치 지표 벡터 차원 |
| `neutral_value` | 5.0 | null 지표 대체값 |
| `max_distance` | 30.0 | 유클리드 거리 정규화 기준 |

**내부 메서드 (private)**

| 메서드 | 역할 |
|--------|------|
| `_metric_to_vector(metric, weights)` | `GameMetric` → 49D numpy 배열 변환, null→5.0 폴백 |
| `_parse_embedding(metric)` | `Vector(1536)` 또는 JSON 문자열 → numpy 배열 파싱 |
| `_cosine_similarity(a, b)` | 코사인 유사도 계산, 영벡터 안전 처리 |
| `_euclidean_similarity(a, b)` | `max(0, 1 - dist/30.0)` 정규화 유사도 |
| `_hybrid_score(m, t, t_emb, m_emb)` | 코사인(35%)+유클리드(35%)+임베딩(30%) 합산 |
| `_check_tags(metric, required, excluded)` | Boolean 태그 필터링 |
| `_calculate_gem_bonus(metric, review_count)` | `(gem/100×0.10 + review_bonus) × confidence` |
| `_generate_match_reasons_from_target(...)` | 기준 게임과 공통 특징 텍스트 생성 (±1.5 허용) |
| `_generate_match_reasons_from_preferences(...)` | 선호도와 매칭 이유 생성 (±2.0 허용) |
| `_get_key_metrics(metric, preferences)` | 특징 지표 top-5 선택 |

**공개 메서드 (public)**

| 메서드 | 반환 | 설명 |
|--------|------|------|
| `recommend_by_game(db, app_id, count, exclude_same_developer)` | `(Game, List[Tuple])` | 기준 게임 기반 하이브리드 추천 |
| `recommend_by_preference(db, preferences, required_tags, excluded_tags, count, min_gem_potential)` | `List[Tuple]` | 선호도 기반 추천 |
| `format_recommendations_by_game(results)` | `List[RecommendedGame]` | by-game 결과 포맷 |
| `format_recommendations_by_preference(results, preferences)` | `List[RecommendedGame]` | by-preference 결과 포맷 |

**추천 알고리즘 요약**

```
# by-game (임베딩 있을 때)
score = cosine(49D) × 0.35 + euclidean(49D) × 0.35 + cosine(1536D) × 0.30 + gem_bonus

# by-game (임베딩 없을 때)
score = cosine(49D) × 0.50 + euclidean(49D) × 0.50 + gem_bonus

# by-preference
score = euclidean × 0.60 + cosine × 0.40 + gem_bonus
※ 사용자 명시 지표에 2.5× 가중치
```

---

## 기술 스택

| 라이브러리 | 버전 | 용도 |
|------------|------|------|
| FastAPI | 0.115+ | 비동기 REST API 프레임워크 |
| uvicorn | 최신 | ASGI 서버 |
| SQLAlchemy | 2.0+ | 비동기 ORM (asyncpg 드라이버) |
| asyncpg | 최신 | PostgreSQL 비동기 드라이버 |
| pgvector | 최신 | `Vector(1536)` 타입 지원 |
| pydantic | v2 | 요청/응답 스키마 검증 |
| pydantic-settings | 최신 | `.env` 기반 설정 관리 |
| numpy | 최신 | 벡터 연산 (유사도 계산) |

---

## 환경변수 (.env)

```env
DB_HOST=localhost
DB_PORT=5432
DB_USER=juntae
DB_PASSWORD=0312
DB_NAME=hidden_gem_db
DEBUG=False
```

`.env`는 프로젝트 루트에 위치. `fastapi_app/config.py`의 `Settings.Config.env_file = ".env"` 로 자동 참조.

---

## 주의사항

- **읽기 전용**: FastAPI는 DB 쓰기를 하지 않는다. 게임 추가/수정은 Django Admin 또는 `manage.py` 커맨드 사용.
- **ORM 컬럼 동기화**: `models/game.py`의 컬럼명은 Django 마이그레이션 파일과 반드시 일치해야 한다. Django 모델 변경 시 여기도 함께 수정.
- **CORS**: 현재 전체 허용(`allow_origins=["*"]`) — 운영 배포 시 구체적인 도메인으로 변경 필요.
