# Hidden Gem — 작업 규칙 (실수 대장)

**이 파일은 이 프로젝트에서 실제로 낸 실수를 규칙으로 바꾼 기록이다.** 각 항목에는 그 규칙을 만들게 한
사건과 날짜가 붙어 있다 — 볼륨을 꽉 채워 Postgres 를 크래시 루프에 빠뜨린 날, 플래그가 서빙에 닿지 않았던 날,
"설정은 있는데 적용은 안 된" 방어를 발견한 날.

읽는 순서는 정해져 있다. **작업 전에 여기부터**, 그다음 `docs/system_invariants.md`(불변식 C-1~C-16 + 변경 전 체크리스트),
`docs/decisions_0905.md`(설계 결정 R-1~R-24: 상황 → 검토 → 판단 → 근거).

왜 코드 밖에 규칙을 적는가 — 1인 개발에서는 같은 실수를 두 번 하지 않게 막아줄 사람이 없다. 그래서 규칙을
파일로 만들고, **AI 협업 세션이 매번 이 파일을 먼저 읽게** 한다(파일명이 `CLAUDE.md` 인 이유. 도구가 바뀌면
파일명만 바뀐다). 사람이 읽어도 그대로 유효한 운영 규칙이고, 실제로 새 환경 세팅·인수인계 때 이 순서로 쓴다.

> 규칙이 늘어나는 방식: 사고 → 원인 확정(실측) → 규칙 한 줄 + 실수 기록. 규칙 없이 "조심하자"로 끝낸 항목은 없다.

## 0. 원칙 — 건네기 전에 내가 먼저 돌린다
- 사용자에게 명령을 주기 전에 **내가 먼저 실행해서 결과를 본다.** 내 환경에서 못 돌리는 것(DB·컨테이너 필요)은
  `[미검증]` 표시를 붙여서 준다. 표시 없이 준 명령은 검증된 것이다 — 그 약속을 지킨다.
- "컴파일 됐다"는 "돌아간다"가 아니다. `py_compile` 통과 뒤 실행 시 `UnboundLocalError` 로 죽은 적 있다 (ablation `out["flags"]`, 2026-09-05).
- 사용자가 실행 출력을 붙여줄 때마다 **첫 줄부터 끝까지** 읽는다. 크래시 위 헤더에 이미 답이 있었던 적이 있다.

## 1. 실행 위치 — 스크립트마다 컨테이너가 다르다 (docstring "실행" 절에서 복사한다, 기억으로 쓰지 않는다)
| 무엇 | 어디서 | 명령 |
|---|---|---|
| `rec_snapshot`, `gem_evidence`, `migrate`, `refresh_reviews`, `recalc_percentile`, `batch_processor` | **batch** (embeddings/ 마운트, PYTHONPATH=/app) | `docker compose exec batch python -m embeddings.<모듈> ...` |
| `scripts.ablation` | **fastapi** (cwd=/app=fastapi_app, DB 의존성) | `docker compose exec fastapi python -m scripts.ablation --pool default` |
| pytest | **호스트 venv** (컨테이너에 pytest 없음) | `.venv/Scripts/pytest fastapi_app/tests/... -q` |
| 테스트가 import 할 수 있는 것 | 라우터·서비스 모듈만. **`main` 은 import 하지 않는다** — 호스트 venv 에 `sentry_sdk` 가 없다 (2026-09-07 `ModuleNotFoundError`). 앱 수준 검사는 라우터 모듈(`routers.games.router`, `routers.ops.router`)을 직접 본다 | |
| 마이그레이션 SQL | `embeddings/migrations/` 에 둔다 | `deploy/` 는 batch 에 마운트되지 않는다 (FileNotFoundError, 2026-09-05) |

- 실수 기록: fastapi 컨테이너에 `embeddings.rec_snapshot`·`fastapi_app.scripts.ablation`·`pytest` 를 주었다가 4개 전부 실패 (2026-09-05).
  명령 블록을 만들 때 `grep -n "docker compose exec" <스크립트>` 로 docstring 을 확인하고 그대로 복사한다.
- 사용자 셸은 **Windows git bash**: 경로는 슬래시(`.venv/Scripts/pytest`). `\` 는 먹히지 않는다.

## 2. 플래그·설정 — `.env` 를 고쳤다고 끝난 게 아니다 (C-11)
- fastapi 컨테이너는 루트 `.env` 를 읽지 않는다. 결과를 바꾸는 플래그는 `docker-compose.yml` fastapi `environment:` 에
  `${X:-기본값}` 으로 있어야 하고, 바꾼 뒤엔 **`docker compose up -d fastapi`** (`restart` 는 env 를 다시 읽지 않는다).
- 호스트에서 프로젝트 루트에 서서 pytest 를 돌리면 pydantic Settings 가 루트 `.env` 를 읽는다 → 테스트가 환경값에
  의존하면 실패한다. `tests/conftest.py` 의 `_pin_scoring_flags` 가 플래그를 코드 기본값으로 고정한다.
  실수 기록: `.env` 에 `GEM_SOURCE=evidence` 를 넣자 루트에서 돌린 pytest 3건 실패 (2026-09-05).
- **새 플래그 하나 = 다섯 곳**: ① `config.py` 기본값 ② compose `environment:` ③ `conftest._FLAG_DEFAULTS`
  ④ `cache._key_version()` (결과를 바꾸면) ⑤ Railway 대시보드 변수 (배포 시). 하나라도 빼면 조용히 무시된다.
- 플래그를 적용한 뒤에는 **적용됐다는 증거**를 본다: `python -c "from config import settings; print(settings.X)"`
  (컨테이너 안), 응답 `score_breakdown.gem_source`, ablation 헤더 `플래그:` 줄.

- `docker compose up -d <svc>` 는 컨테이너를 **재생성**한다 — 그 안에서 `exec -d` 로 돌던 장기 작업(백필·prod_sync)은 죽는다. 순서는 항상 **환경/비밀 변경 → `up -d` → 장기 작업 시작**. 여러 할 일을 목록으로 건넬 때도 이 순서로 배열한다. 실수 기록: 2026-09-06 백필 시작 직후 비밀번호 교체 절차의 `up -d batch` 가 백필을 죽임.
- 컨테이너 안에서만 쓰는 로그는 재생성 시 사라진다 — 남겨야 할 로그 디렉터리는 compose volumes 에 마운트한다 (`./logs:/app/logs`).

## 1''. Git Bash(MINGW) 는 `/`로 시작하는 인자를 윈도우 경로로 바꾼다
- 사용자는 Git Bash 를 쓴다. `docker compose exec ... --csv /app/data/new_games.csv` 를 주면
  MSYS 경로 변환이 일어나 컨테이너에 `C:/Program Files/Git/app/data/new_games.csv` 가 전달된다.
  실수 기록: 2026-09-06 백필 batch#4 진단 명령이 이것 때문에 '파일 없음'으로 죽어 한 번 헛돌았다.
- 규칙: 컨테이너 내부 경로는 **앞 슬래시 없이** 쓴다 (`--csv data/new_games.csv`) — batch/fastapi 의 working_dir 가 `/app` 이라 그대로 맞는다.
  꼭 절대경로가 필요하면 `MSYS_NO_PATHCONV=1` 을 명령 앞에 붙이거나 `//app/...` 로 쓴다.
- DB URL(`postgresql://...`)·`-c "SELECT ..."` 는 변환 대상이 아니다. 변환되는 건 `/`로 시작하는 경로형 인자다.

- **프런트 도메인 하나 = 네 곳**: ① Railway **fastapi** `FRONTEND_URL`(CORS) ② Railway **django** `FRONTEND_URL`(CORS+CSRF) ③ Vercel `NEXT_PUBLIC_SITE_URL`
  ④ Google OAuth 승인된 원본. 실수 기록: 2026-09-07 도메인 전환에서 ①을 빼먹어 새 도메인에서 API 전부 CORS 거부 → "연결에 문제가 있어요".
  같은 이름의 변수가 서비스마다 따로 있다 — 하나 고쳤다고 끝난 게 아니다(플래그 5곳 규칙과 같은 구조).

## 1'. 명령 블록에 자리표시자를 넣지 않는다
- `<운영 DB URL>` 같은 꺾쇠 자리표시자는 **금지**. 사용자는 블록을 통째로 붙인다 — bash 가 `<`·`>` 를 리다이렉트로 읽어 그 줄이 조용히 죽고
  다음 줄(`git push`)은 그대로 실행된다. 실수 기록: 운영 마이그레이션 3줄이 안 돈 채 push 만 나감 (2026-09-05 심야).
- 값이 필요한 명령은 **두 단계**로: 첫 블록은 `export X='여기에_붙이기'` 한 줄만, 둘째 블록은 `"$X"` 를 쓰는 명령.
- 돌면 안 되는 순서가 있는 명령(마이그레이션 → push)은 **한 블록에 넣지 않는다**. 앞 단계의 확인 출력("완료")을 받은 뒤 다음 블록을 준다.

## 2'. 배포 — push 는 곧 운영 배포다 (Vercel/Railway 자동)
- 모델(`models/game.py`)에 컬럼을 추가했으면 **push 전에** 운영 DB 마이그레이션 → 채움 → Railway 변수 → push (C-12). 순서를 바꾸면 500.
- push 를 권하기 전에 `git log origin/master..master --oneline` 으로 미푸시 커밋을 세고, 그 안에 스키마·플래그 변경이 있는지 본다.
- 사용자가 자는 시간엔 배포하지 않는다. push 는 사용자가 한다.

## 2''''. 저장소는 공개, 레시피는 비공개
- 공개 저장소에 두지 않는 것: **PRD·사업 계획**, **분석 시스템 프롬프트**(`data/prompts/`), **few-shot**(`data/fewshot/`), 데이터셋, `.env`.
  보관 위치는 `Desktop/Hidden-Gem-비공개/` (prd/, prompts/). 프롬프트를 바꾸면 그 폴더에도 복사한다 — 저장소 백업에 안 들어간다.
- `batch_generator` 는 프롬프트를 `data/prompts/analysis_system_prompt_v6.txt` 에서 **지연 로드**한다. 파일이 없으면 명확히 죽는다.
  새 환경에서 배치가 "프롬프트 파일이 없다"로 죽으면 비공개 폴더에서 복원하는 게 맞다 — 저장소에서 찾지 않는다.
- 지표 이름·스키마·채점 공식은 공개다(이미 README·포트폴리오에 적혀 있다). 비밀은 '무엇을 재는가'가 아니라 '어떻게 재게 하는가'(프롬프트 문장·예시)다.

## 2'''. 방어는 '설정'이 아니라 '적용'을 검사한다
- `settings.RATE_LIMIT_*` 는 정의돼 있고 테스트도 통과했지만 **어떤 엔드포인트에도 붙어 있지 않았다**(taste.py 만 예외).
  설정의 존재·값만 검사하는 테스트는 통과하면서 무방비를 통과시킨다. 실수 기록: 2026-09-07 공개 전 점검에서 발견.
- 규칙: 보호 장치를 만들면 **그 장치가 대상 경로에 붙었는지**를 테스트한다(라우트의 dependencies 검사). 값 검증은 그다음이다.
  같은 함정을 이미 두 번 겪었다 — 정적 `/health`(무엇을 확인하는지 모르는 헬스체크), 무인증 `/ops/*`(경로만 숨김).
- 새 엔드포인트를 추가하면 확인할 것 셋: ① 레이트 리밋 의존성 ② 인증(운영용이면 토큰) ③ 입력 길이·형식 제한.

## 2''. 운영 DB 에 쓰기 전
- 운영에 1천 행 이상 쓰기 전 `embeddings.db_space` 로 크기·한도를 본다 (C-13). 실수 기록: 볼륨 0.5GB 에 12,843행을 밀어 Postgres 크래시 루프 (2026-09-05 심야).
- 로컬→운영 데이터 이동은 `embeddings.prod_sync` 만 쓴다 (upsert, 삭제 없음, dry-run 먼저). 운영의 사용자 테이블은 절대 건드리지 않는다.
- 운영 스키마 제약(NOT NULL 등)은 로컬과 다를 수 있다 — dry-run 은 이걸 못 잡는다. 실패하면 제약을 풀지 말고 데이터를 맞춘다.
- 운영 비밀(DB 비밀번호·URL·API 키)은 채팅에 요구하지 않는다 — 사용자에게 `.env` 에 넣게 하고 나는 변수명만 쓴다(`$PROD_DB`, `PROD_DATABASE_URL`). 채팅에 노출되면 그날 안에 교체한다(순서: ALTER USER → Railway 변수 → 로컬 .env → `up -d batch` → 접속 확인). 실수 기록: 2026-09-05 운영 URL 을 붙여 받아 비밀번호 노출.

## 3. 점수 로직 수정 — 세 경로 + 절제 도구 + 캐시 키
- 경로 A(`score_v6`/`score_v7`, 취향·Vibe) / B(`recommend_by_game`) / C(`semantic_search`) **전부** 같은 규칙을 따르는지 grep 으로 확인.
  실수 기록: `GEM_SOURCE=evidence` 를 v7 과 B/C 에만 넣어 `SCORE_VERSION=v6` 상태에선 A 만 legacy 로 남을 판이었다 (2026-09-05).
- `scripts/ablation.py` 는 서빙과 **같은 분기**를 써야 한다 (풀 admit, gem_factor, gem 소스, 예산). 다르면 절제 결론이 서빙과 무관해진다.
- 결과를 바꾸는 조건은 전부 캐시 키에 (C-9). `_key_version()` 에 플래그, payload 에 조건.
- 함수 기본값 인자(`.get(k, 5.0)`, `or x`, `gem_factor=1.0`)는 **호출자가 실제로 채우는지** 확인한다 (C-10, D-26).

## 4. 코드를 고친 뒤 — 순서 고정
1. 고친 파일 전부 `python -m py_compile`.
2. **실행**: 테스트 있으면 `pytest` — `fastapi_app/` 안에서 한 번, 루트에서 한 번(.env 읽히는 조건). 스크립트면 최소 `--help`/dry-run.
3. 새 코드에 테스트 한 개 이상 (경계: NULL, 0, 계수 0, 플래그 양쪽).
4. 관련 문서 갱신 — `decisions_0905.md`(결정·실행 기록), `system_invariants.md`(새 부류의 실수면 C-n 추가), 이 파일(규칙).
5. 커밋: 한국어·상세·"왜"까지. 사용자가 `git push` 한다(자동 배포). `.env` 커밋 금지. 데이터 삭제 금지(`is_active` 만).

## 5. 측정·비교 — 예측을 먼저 적는다
- 스냅샷/절제를 돌리기 전에 **기대값을 문장으로** 적고(교사 비율 방향, top-5 유지 개수, spearman 범위), 결과가 다르면 멈춘다.
- "변화 없음"은 캐시가 비워졌고(`total_keys==0`) 플래그가 닿았다는 증거가 있을 때만 결론이다 (C-9·C-11).
- 어떤 출력이 **합격 판정**에 쓰이는지 명령과 함께 말한다 (예: R-3 전환의 판정은 `--diff s4 s5`, ablation 은 보조).
- 검토자 동의는 증거가 아니다. 숫자는 대시보드·실측만. 비용 추정치는 "추정"이라고 쓴다.

## 6. 보고 방식
- 실수는 **원인 한 줄 + 수정 커밋 해시 + 재실행 명령**. 변명·장문 사과 없음.
- 사용자 취지 원문은 그대로 인용해 기록한다("신작으로 신생게임을 보호해서 그들만의 리그를 만들고 보여주자").
- 새로 뭘 시작하기 전에 지금 단계의 합격 판정이 끝났는지 먼저 본다.
