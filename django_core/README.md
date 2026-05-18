# django_core/

Hidden Gem 관리 서버. 게임 데이터 적재/수정/분석을 담당하는 Django 백엔드.
FastAPI가 읽는 PostgreSQL 테이블의 원본 데이터를 여기서 관리한다.

포트: **8001** | 역할: **Admin UI + 데이터 관리** | DB 접근: **Django ORM (read/write)**

---

## 폴더 구조

```
django_core/
├── manage.py                        # Django 관리 CLI 진입점
├── config/
│   ├── settings.py                  # Django 전역 설정 (DB, 앱 목록, Redis 등)
│   ├── urls.py                      # URL 라우팅 — /admin/ 전용
│   ├── asgi.py                      # ASGI 설정 (비동기 서버용)
│   └── wsgi.py                      # WSGI 설정 (전통 서버용)
└── apps/
    ├── games/                       # 핵심 앱 — 게임 데이터 관리
    │   ├── models.py                # Game, GameMetric ORM 모델
    │   ├── admin.py                 # Admin UI 커스터마이징
    │   ├── signals.py               # Redis Pub/Sub 동기화 시그널
    │   ├── apps.py                  # 앱 설정 (signals 자동 등록)
    │   └── management/commands/
    │       ├── load_games.py        # JSONL → DB 적재 커맨드
    │       └── analyze_new_games.py # Few-Shot 신규 게임 분석 커맨드
    └── users/
        ├── models.py                # CustomUser 모델 (Steam OAuth 예정)
        └── admin.py                 # 유저 관리 Admin
```

---

## 실행 방법

```bash
cd django_core

# 마이그레이션
python manage.py migrate

# 관리자 계정 생성
python manage.py createsuperuser

# 서버 실행 (포트 8001 — FastAPI와 분리)
python manage.py runserver 8001
```

Admin UI: http://localhost:8001/admin/

---

## 파일별 설명

### `config/settings.py` — 전역 설정

| 설정 | 값 | 비고 |
|------|----|------|
| `DATABASES` | PostgreSQL (Docker :5432) | FastAPI와 동일 DB |
| `AUTH_USER_MODEL` | `users.CustomUser` | AbstractUser 확장 |
| `REDIS_HOST/PORT` | localhost:6379 | 시그널 Pub/Sub 용 |
| `CORS_ALLOW_ALL_ORIGINS` | True | 개발용 — 운영 시 변경 |
| `REST_FRAMEWORK.PAGE_SIZE` | 20 | DRF 페이지네이션 |
| `GPT_MODELS.original` | `gpt-5.4` | 원본 4,190개 분석 모델 |
| `GPT_MODELS.fewshot_mini` | `gpt-4o-mini` | 신규 게임 Few-Shot 모델 |
| `GPT_MODELS.embedding` | `text-embedding-3-small` | 임베딩 생성 모델 |

---

### `config/urls.py` — URL 라우팅

Django는 Admin UI 전용. API는 FastAPI(포트 8000)에서 담당.

```python
urlpatterns = [
    path('admin/', admin.site.urls),
]
```

---

### `apps/games/models.py` — 게임 모델

**`Game`** — `games` 테이블

| 필드 그룹 | 주요 필드 | 비고 |
|-----------|-----------|------|
| 기본 정보 | `app_id` (unique), `name`, `genres`, `developer` | Steam 원본 |
| Steam 데이터 | `steam_positive_ratio`, `review_count`, `is_free` | 0.0~1.0, 정수 |
| AI 생성 | `one_line_summary`, `marketing_hook`, `target_personas` | GPT-5.4 생성 |
| 분석 상태 | `is_analyzed`, `analysis_method` | choices 참조 |

`analysis_method` choices:

| 값 | 의미 |
|----|------|
| `gpt5.4_batch` | 원본 4,190개 — GPT-5.4 Batch API |
| `fewshot_5.4based` | Few-Shot — gpt-4o-mini (5.4 예시 기반) |
| `manual` | 수동 입력 |
| `pending` | 분석 대기 중 |

**`GameMetric`** — `game_metrics` 테이블

`game` 필드가 PK이자 FK인 OneToOne 구조.
60개 지표 전체 + AI 분석 근거(`analysis_summary`, `metric_justifications`) + 원본 JSON 보관.

| 필드 그룹 | 개수 | 스케일 |
|-----------|------|--------|
| VIBE | 7 | 0~10 Float |
| DEMANDS | 5 | 0~10 Float |
| MECHANICS | 11 | 0~10 Float |
| SOCIAL | 5 | 0~10 Float |
| PRESENTATION | 5 | 0~10 Float |
| SYSTEM/UX | 7 | 0~10 Float |
| ART/AUDIO | 3 | 0~10 Float |
| OTHER | 2 | 0~10 Float |
| NEW | 4 | 0~10 Float |
| TAGS | 9 | Boolean |
| gem_potential | 1 | 0~10 Float |
| confidence_score | 1 | 0~1 Float |

---

### `apps/games/admin.py` — Admin 커스터마이징

**`GameMetricInline`** — Game 상세 페이지 내 지표 인라인 편집

- 60개 지표를 카테고리별 collapse 섹션으로 표시
- `can_delete=False` — 인라인에서 지표 실수 삭제 방지

**`GameAdmin`** — 게임 목록/검색/필터 (URL: `/admin/games/game/`)

| 기능 | 설정 |
|------|------|
| 검색 | `app_id`, `name`, `developer`, `publisher`, `genres` |
| 필터 | `is_analyzed`, `analysis_method`, `is_active`, `is_indie` |
| 목록 표시 | `method_badge`, `gem_potential`, `confidence_score`, `review_count` |
| 인라인 | `GameMetricInline` (지표 섹션별 접기) |
| Import/Export | JSONL/CSV 가져오기/내보내기 (django-import-export) |

`method_badge()` 색상 코드:

| 색상 | analysis_method |
|------|----------------|
| 초록 | `gpt5.4_batch` |
| 파랑 | `fewshot_5.4based` |
| 회색 | `manual` |
| 빨강 | `pending` |

**`GameMetricAdmin`** — 지표 단독 조회 (URL: `/admin/games/gamemetric/`)

지표 품질 점검용. `gem_potential`, `confidence_score` 기준 필터 제공.

---

### `apps/games/signals.py` — Redis Pub/Sub 동기화

Django Admin에서 게임 데이터 변경 시 FastAPI에 이벤트를 발행하는 Django 시그널.

**채널**: `hidden_gem:game_updates`

| 시그널 함수 | 트리거 | 이벤트 타입 |
|-------------|--------|-------------|
| `notify_game_update()` | `Game` post_save | `game_created` / `game_updated` |
| `notify_metric_update()` | `GameMetric` post_save | `metric_created` / `metric_updated` (+ `requires_embedding_refresh: true`) |
| `notify_game_delete()` | `Game` post_delete | `game_deleted` |

**`get_redis_client()`**: 매 시그널마다 lazy하게 클라이언트 생성. `settings.REDIS_HOST/PORT` 참조.

> Redis 연결 실패 시 예외를 삼켜 Django 작업을 중단하지 않음 (silent fail).

---

### `apps/games/management/commands/load_games.py` — 데이터 적재 커맨드

JSONL 파일을 읽어 `games` + `game_metrics` 테이블에 적재.

```bash
python manage.py load_games --input data/final/final_master_games_fixed.jsonl

# 옵션
python manage.py load_games --input <파일> --batch-size 100  # 배치 크기 (기본 100)
python manage.py load_games --input <파일> --update          # 기존 게임 업데이트
python manage.py load_games --input <파일> --dry-run         # DB 변경 없이 미리보기
```

**주요 내부 메서드**

| 메서드 | 역할 |
|--------|------|
| `handle()` | CLI 진입점 — `_save_batch()` 호출로 100개 단위 bulk_create |
| `_create_game(data)` | dict → `Game` 인스턴스 변환, `marketing_hook` dict/str 정규화 |
| `_parse_date(value)` | `"Nov 2022"`, `"2022-11-01"` 등 다양한 날짜 형식 파싱 |
| `_save_batch(games, metrics)` | 원자적 트랜잭션 + `bulk_create(update_conflicts=True)` |
| `_get_metric(data)` | 다중 소스(raw_content, content, 루트 필드) 우선순위 폴백 |
| `_create_metric(game, data)` | dict → `GameMetric` 인스턴스 변환 |
| `_update_game(game, data)` | 기존 게임 필드 업데이트 + `GameMetric` 완전 교체 |
| `_validate_data(data)` | 필수 필드 15개 이상 존재 검증 (임계값 15/18) |

---

### `apps/games/management/commands/analyze_new_games.py` — Few-Shot 분석 커맨드

`is_analyzed=False` 게임을 gpt-4o-mini + Few-Shot으로 분석. 원본 4,190개의 1/60 비용.

```bash
python manage.py analyze_new_games

# 옵션
python manage.py analyze_new_games --limit 10         # 처리할 최대 게임 수
python manage.py analyze_new_games --dry-run          # GPT 호출 없이 미리보기
python manage.py analyze_new_games --app-id 1234567   # 특정 게임만 분석
```

**주요 내부 메서드**

| 메서드 | 역할 |
|--------|------|
| `handle()` | 3단계 파이프라인: 미분석 게임 조회 → Few-Shot 분석 → DB 저장 |
| `_find_similar_games(game)` | 기존 분석 게임 중 유사한 5개 선택 (향후 pgvector 업그레이드 예정) |
| `_analyze_with_fewshot(game, examples)` | gpt-4o-mini에 5개 예시 + 대상 게임 전달, JSON 응답 파싱 |
| `_build_examples(games)` | Few-Shot 프롬프트용 예시 텍스트 구성 |

---

### `apps/users/models.py` — 커스텀 유저 모델

```python
class CustomUser(AbstractUser):
    steam_id = models.CharField(max_length=50, blank=True)  # Steam OAuth 예정
    bio = models.TextField(blank=True)
    avatar_url = models.URLField(blank=True)
```

`AUTH_USER_MODEL = 'users.CustomUser'`로 Django 기본 User 대체.

---

## 기술 스택

| 라이브러리 | 용도 |
|------------|------|
| Django 5.0 | Admin UI, ORM, 마이그레이션 |
| djangorestframework | DRF (REST API 예비용) |
| django-cors-headers | CORS 미들웨어 |
| django-import-export | Admin CSV/JSONL 가져오기/내보내기 |
| django-filter | Admin/API 필터링 |
| psycopg2-binary | PostgreSQL 동기 드라이버 (Django ORM용) |
| redis | Redis Pub/Sub 시그널 클라이언트 |
| openai | GPT-5.4 / gpt-4o-mini API 호출 |
| python-dotenv | `.env` 파일 로드 |

---

## 환경변수 (.env)

```env
# DB
DB_NAME=hidden_gem_db
DB_USER=juntae
DB_PASSWORD=0312
DB_HOST=localhost
DB_PORT=5432

# Django
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# OpenAI (analyze_new_games 커맨드용)
OPENAI_API_KEY=sk-...
```

---

## 자주 쓰는 커맨드

```bash
# DB 현황 확인
python manage.py shell -c "
from apps.games.models import Game, GameMetric
print('Total:', Game.objects.count())
print('Analyzed:', Game.objects.filter(is_analyzed=True).count())
print('Pending:', Game.objects.filter(is_analyzed=False).count())
print('Has metrics:', GameMetric.objects.count())
"

# 마이그레이션 생성 (모델 변경 후)
python manage.py makemigrations
python manage.py migrate

# 특정 앱만 마이그레이션
python manage.py migrate games
```

---

## 주의사항

- **ORM 동기화**: `models.py` 변경 시 `fastapi_app/models/game.py`도 함께 수정해야 한다.
- **쓰기 권한**: DB 쓰기는 Django만 담당. FastAPI는 절대 직접 INSERT/UPDATE 하지 않는다.
- **시그널 순서**: `GameMetric` 저장 시그널이 `requires_embedding_refresh=True`를 발행하므로, 신규 게임 적재 후 `scripts/load_embeddings.py`를 실행해야 추천 임베딩이 갱신된다.
- **SECRET_KEY**: 운영 환경에서는 `.env`에 강력한 키를 반드시 설정.
