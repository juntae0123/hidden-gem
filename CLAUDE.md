# Hidden Gem — Claude 작업 규칙 (매 세션 먼저 읽는다)

이 파일은 사용자(준태)가 "실수할 만한 것은 지침으로 박아놔"라고 해서 만든 것이다.
규칙마다 그 규칙을 만들게 한 **실제 실수**를 옆에 적는다. 새 실수가 나오면 같은 형식으로 여기에 추가한다.
문서 더 볼 것: `docs/system_invariants.md`(C-1~C-11, §5 체크리스트), `docs/decisions_0905.md`(R-1~R-15).

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

## 1'. 명령 블록에 자리표시자를 넣지 않는다
- `<운영 DB URL>` 같은 꺾쇠 자리표시자는 **금지**. 사용자는 블록을 통째로 붙인다 — bash 가 `<`·`>` 를 리다이렉트로 읽어 그 줄이 조용히 죽고
  다음 줄(`git push`)은 그대로 실행된다. 실수 기록: 운영 마이그레이션 3줄이 안 돈 채 push 만 나감 (2026-09-05 심야).
- 값이 필요한 명령은 **두 단계**로: 첫 블록은 `export X='여기에_붙이기'` 한 줄만, 둘째 블록은 `"$X"` 를 쓰는 명령.
- 돌면 안 되는 순서가 있는 명령(마이그레이션 → push)은 **한 블록에 넣지 않는다**. 앞 단계의 확인 출력("완료")을 받은 뒤 다음 블록을 준다.

## 2'. 배포 — push 는 곧 운영 배포다 (Vercel/Railway 자동)
- 모델(`models/game.py`)에 컬럼을 추가했으면 **push 전에** 운영 DB 마이그레이션 → 채움 → Railway 변수 → push (C-12). 순서를 바꾸면 500.
- push 를 권하기 전에 `git log origin/master..master --oneline` 으로 미푸시 커밋을 세고, 그 안에 스키마·플래그 변경이 있는지 본다.
- 사용자가 자는 시간엔 배포하지 않는다. push 는 사용자가 한다.

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
