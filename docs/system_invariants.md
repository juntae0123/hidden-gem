# 시스템 불변식 — 깨지면 안 되는 것, 무엇이 무엇과 충돌하는가

이 문서를 만든 이유: 2026-09-03~04 이틀간 발생한 버그를 분류해보니 **대부분이 "옆 컴포넌트가
실제로 어떻게 동작하는지 확인하지 않고 이름으로 추측"해서 생겼다.** 개별 코드가 틀린 게 아니라
연결 지점을 몰랐다. 그 지식이 어디에도 적혀 있지 않아 매번 다시 틀렸다.

**작업 전에 이 문서를 먼저 읽는다. 새 불변식을 발견하면 여기에 추가한다.**

---

## 1. 절대 깨면 안 되는 것 (복구 불가)

| # | 불변식 | 왜 | 깨졌을 때 |
|---|---|---|---|
| I-1 | `analysis_method='gpt5.4_batch'` 4,190건의 `game_metrics` 는 **백업이 없는 원본**이다 | 교사 GPT-5.4 로 $수백 들여 만든 기준 데이터. `embedding_backup_20260703` 은 embedding만 백업한다 | 재생성 불가. 학생 값으로 덮이면 모든 품질 비교의 기준이 사라진다 |
| I-2 | `game_metrics.gem_potential` 은 **코호트별로 스케일이 다르다** (교사 40~95 μ75.5 / 학생 1~92 μ42.8) | 교사는 인기작만 채점, 학생은 전수. 홀드아웃 실측 MAE 19.5 ρ0.49 | 두 코호트를 한 줄로 정렬하면 교사가 상위를 독식한다 |
| I-3 | 사용자 행동 로그(`user_actions`)는 재현 불가능한 유일 데이터다 | 트래픽이 다시 오지 않는다 | 삭제 시 영구 손실 |
| I-4 | **데이터는 지우지 않는다.** 품질이 의심되는 게임도 분석 결과는 보존하고 `is_active` 로만 제어 | 서비스 취지 = "게임의 가능성 보존" (개발자 명시) | 취지 위반 + 재분석 비용 |

**따라서**: `game_metrics` 를 UPDATE 하는 코드는 (a) 대상 코호트를 `analysis_method` 로 명시적으로
좁히고 (b) 원본을 별도 테이블에 보존한 뒤 (c) 되돌리는 명령을 함께 만든다. 셋 중 하나라도
없으면 그 코드는 미완성이다.

---

## 2. 데이터가 화면에 나오기까지 — 끊기는 지점이 어디인가

```
크롤 → games(pending, is_active=FALSE)
     → 배치 분석 → game_metrics UPSERT + analysis_method 갱신
     → 임베딩 생성
     → 리뷰 조회 → 노출 게이트 → is_active=TRUE
     → gem_percentile 재계산
     → 추천 API → 프런트
```

이 체인에서 **하나라도 안 되면 게임은 존재하지만 보이지 않는다.** 실제로 이 이유로 두 번 막혔다.

| 조건 | 없으면 | 확인 방법 |
|---|---|---|
| `game_metrics` 행 존재 | 추천 후보에서 JOIN 탈락 | `is_analyzed`, method 확인 |
| `analysis_method='fewshot_5.4based'` | 임베딩 단계가 대상으로 잡지 않음 | **라벨 하나로 전체가 멈춘다 (실제 발생)** |
| `embedding IS NOT NULL` | 벡터 검색에서 누락 + 활성화 조건 미달 | |
| `review_count >= 게이트` | 비노출 | 게이트는 학생 라벨만 대상 |
| `is_active=TRUE` | 모든 추천 쿼리에서 제외 | **활성화 단계가 아예 없었다 (실제 발생)** |
| `gem_percentile IS NOT NULL` | gem 보너스가 폴백값으로 계산됨 | 루프 끝에 1회만 재계산됨 |

---

## 3. 서로 충돌하는 것들 (하나를 건드리면 다른 쪽이 깨진다)

### C-1. `gem_percentile` 은 4곳에서 읽히고 **폴백 방식이 곳마다 다르다**
```
score_v6.py:294          gem_pct = gem_percentile or 50            → 0 이 50 으로 바뀐다
recommender.py:898       float(game.metrics.gem_percentile or 50)  → 0 이 50 으로 바뀐다
recommender.py:1171+     metric.gem_percentile or metric.gem_potential → 0 이 다른 컬럼으로 넘어간다
recommender.py:560-563   is not None 분기 → 0 을 그대로 보존한다 (여기만 올바르다)
```
**정정(2026-09-04)**: 초판은 "전부 `or` 폴백"이라고 적었다. 틀렸다.
`_calculate_gem_bonus`(`:560-563`)는 `is not None` 으로 분기해 **실제 값 0 을 보존**하고
NULL 일 때만 폴백한다. 즉 세 곳은 0 을 잃고 한 곳은 보존한다 — **같은 컬럼을 읽는
네 곳이 서로 다르게 해석한다는 것이 진짜 문제**다.
→ 이 컬럼에 **0을 쓰면 세 곳에서 50(또는 다른 컬럼)으로 읽힌다.** 값의 의미를 바꾸려면
읽는 쪽 4곳을 같은 커밋에서 고쳐야 하고, 고치는 방향은 `:560-563` 쪽이다.
→ `gem_potential` 폴백이 있으므로 두 스케일(I-2)이 자동으로 섞인다.

### C-2. 리뷰 수는 **세 곳에서 독립적으로** 점수에 들어간다
1. `score_v6.compute_gem_bonus` 의 `discovery` (리뷰 수 계단)
2. `recommender._calculate_gem_bonus` 의 `review_bonus` (리뷰 1,000 미만 선형)
3. 근거 기반 gem 지수의 `무명도` (전환 시)
→ gem을 리뷰 기반으로 바꾸면 **같은 정보가 2~3번 계상된다.** 하나를 도입하면 나머지를 빼야 한다.

### C-3. 노출 게이트와 `batch_processor.activate_games` 가 서로 다른 조건을 쓴다
게이트는 리뷰 수를 보고, `activate_games` 는 metrics+embedding만 본다.
→ 배치 재적재를 하면 게이트로 내린 게임이 **다시 켜진다.** 재적재는 정상적인 복구 절차이므로
   이건 언젠가 반드시 발생한다.

### C-4. `max_review_count` 필터는 `review_count` 가 채워져 있다는 전제에 서 있다
교사 4,190건이 NULL이어서 **한 번도 작동하지 않았다.** 필터 조건이 NULL을 명시적으로 통과시킨다.
→ 유명작 제외를 논하려면 먼저 리뷰 데이터를 채워야 한다. 코드만 있어도 동작하지 않는다.

### C-5. `0.0` 과 `NULL` 과 `없음` 이 코드마다 다르게 해석된다
```
recommender.py:884   getattr(m, f, 5.0) or 5.0    → 진짜 0.0 이 5.0 이 된다
NULL_FALLBACK_POLICY → 공포·고어·모딩은 0, 나머지는 중앙값
must_not 필터        → NULL 은 통과시킨다
```
→ 지표 값 0은 흔하다(공포 0이 48%, 아늑함 0이 35%). 폴백 정책을 고칠 때 세 곳을 함께 봐야 한다.

### C-6. 배치 산출물 파일명이 프로덕션과 감사에서 공유된다
`data/batch_output_*.jsonl` 을 루프도, 홀드아웃 감사도 만든다. mtime 최신을 고르면
**교사 게임 결과를 프로덕션에 적재한다.** → 새로 생긴 파일만 인정하는 차집합 방식으로만 안전하다.

### C-9. 캐시 키에 점수 로직 버전이 없다 (측정 자체를 무효화한다)
```
semantic:{query_hash}:{limit}   rec:game:{app_id}:{count}   rec:pref:{pref_hash}:{count}
```
키에 코드 버전이 없고, 조건 일부도 빠져 있다(`exclude_same_developer`, `required_tags`,
`excluded_tags`, `min_gem_potential`). 그래서 **점수 공식을 고친 뒤 같은 질의를 던지면
변경 전 결과가 그대로 돌아온다.** 회귀 비교의 결론이 조용히 뒤집힌다.
또 `invalidate_all` 은 '키 0개'와 'Redis 예외'를 모두 0 으로 돌려주므로(`cache.py:170-195`)
반환값만으로 성공을 판정할 수 없다 — `GET /ops/cache` 의 `total_keys` 로 확인해야 한다.
→ 조치: `rec_snapshot --save` 가 매 회차 무효화 + 확인을 강제하고, 실패 시 스냅샷을
  쓰지 않고 죽는다. 근본 해결은 캐시 키에 `CACHE_VERSION` prefix + 누락 조건 추가.
→ 2026-09-05 현재: 세 키 모두 `_key_version()` = `{CACHE_VERSION}-{SCORE_VERSION}-{GEM_SOURCE}` 접두 + 누락 조건 포함.
  플래그만 바꿔도 옛 결과가 살아남지 않는다. 단, 스냅샷 비교는 여전히 무효화+확인을 강제한다(이중 안전).

### C-10. `score_v6.calculate_score_v6` 는 `target_metrics` 가 **꽉 찬 dict** 라고 가정한다
`compute_core_score` 는 `target_metrics.get(f, 5.0)` 으로 장르 핵심 지표의 목표값을 읽는다.
`recommend_by_preference` 는 `target_metrics=preferences` — 사용자가 입력한 3~5개 키만 있는 sparse dict —
를 넘긴다. 어긋난 계약을 `.get(f, 5.0)` 이 조용히 메워서 **Core 의 65% 가 "장르 핵심에서 평범한가"**
를 재게 됐다(D-26, `final_verdict_0905.md` §2). 세 외부 검토가 전부 놓쳤다 — 문서에 target 출처가 없었다.
→ 함수의 기본값 인자(`.get(k, default)`, `or x`)는 **호출자가 그 키를 실제로 채우는지** 확인해야 한다.
  기본값이 "안전한 중립"으로 보여도 호출 맥락에서는 채점 규칙이 된다.

### C-11. 운영 플래그는 `.env` 를 고쳐도 fastapi 컨테이너에 **닿지 않는다** (2026-09-05 R-3 전환에서 발견)
`config.Settings.Config.env_file = ".env"` 는 컨테이너 작업 디렉터리 `/app`(= `fastapi_app/`) 기준이고,
`docker-compose.yml` 의 fastapi 서비스는 `env_file` 없이 `environment:` 로 변수를 하나씩 넘긴다.
따라서 루트 `.env` 에 `GEM_SOURCE=evidence` 를 적고 `restart` 해도 서빙은 계속 `legacy` — **아무 오류 없이**.
반면 batch 컨테이너는 `env_file: .env` 라서 같은 값을 읽는다 → 배치와 서빙이 다른 플래그로 돌 수 있다.
→ 조치: 결과를 바꾸는 플래그(`SCORE_VERSION`, `GEM_SOURCE`, `VIBE_SECONDARY_ENABLED`, `PREF_EMBED_TIEBREAK`)를
  compose `environment:` 에 `${X:-기본값}` 으로 명시. 값을 바꾼 뒤엔 `docker compose up -d fastapi`
  (`restart` 는 env 를 다시 읽지 않는다). 전환 뒤엔 반드시 응답의 `score_breakdown.gem_source` /
  `ablation` 헤더의 `플래그:` 줄로 실제 적용값을 확인한다. 같은 이유로 캐시 키에도 두 플래그가 들어간다(C-9 후속).
  Railway 는 대시보드 변수로 넘기므로 별도 확인.

### C-12. 모델에 컬럼을 추가하면 **push 가 곧 운영 장애**다 (자동 배포 + 마이그레이션 수동)
`models/game.py` 의 `GameMetric` 에 `gem_evidence_*` 컬럼이 있으므로 SQLAlchemy 는 모든 `GameMetric` SELECT 에 그 컬럼을 넣는다.
운영 DB 에 컬럼이 없으면 추천·검색·상세 전부 `UndefinedColumn` 500. Railway 는 push 즉시 배포되므로 **마이그레이션은 push 전에** 운영 DB 에 먼저.
순서: ① 운영 DB 에 `embeddings/migrations/*.sql` 적용 (`docker compose exec -e DATABASE_URL=<운영> batch python -m embeddings.migrate --file …`)
② 운영 DB 에 `gem_evidence --fill --yes` (읽는 건 review_count·positive_ratio 만 — 운영 DB 의 리뷰 백필 상태를 먼저 본다: `--fill --dry-run` 의 no_reviews 비율)
③ Railway 변수 `SCORE_VERSION=v7`, `GEM_SOURCE=evidence` ④ push. ①~③ 없이 push 하면 롤백은 Railway Redeploy(직전) 뿐이다.
`ADD COLUMN IF NOT EXISTS` 라 ① 은 재실행 안전. 컬럼 추가 없이 코드만 배포하는 경우에도 GEM_SOURCE 기본값(legacy)이면 새 컬럼을 읽기만 하므로 ① 만 있으면 된다.

### C-13. 대량 쓰기 전에 타깃의 남은 공간을 본다 — WAL 이 데이터보다 먼저 볼륨을 채운다
운영 Postgres 볼륨이 0.5GB 일 때 12,843행 upsert 를 밀어넣자 데이터(≈200MB)가 아니라 **WAL(기본 max_wal_size 1GB)** 이 먼저 디스크를 채웠다.
`No space left on device` → autovacuum PANIC → 재시작 루프(복구 redo 는 끝나는데 WAL 한 파일 쓸 공간이 없어 다시 죽음). 볼륨 증설 외엔 못 살린다.
→ 규칙: 운영에 1천 행 이상 쓰기 전 `db_space` 로 DB 크기와 볼륨 한도를 본다. 필요 공간 = 데이터 증분 + WAL 1GB + 여유. 묶음 실행으로 시간을 줄이면 WAL 도 덜 쌓인다.
  볼륨 사용량 감시(70% 알림)를 주간 파이프라인에 넣는다. 한도가 있는 저장소는 "언젠가 터진다" — 감시가 답이다.

### C-7. Steam API 를 두 스크립트가 동시에 두드릴 수 있다
크롤러(store 검색 1.6s + appdetails 1.5s)와 `refresh_reviews`(appreviews 1.0s)는 같은 IP를 쓴다.
합치면 Steam 비공식 한도(약 200req/5min)를 넘어 **둘 다 429** 를 맞는다. → 동시 실행 금지.

### C-8. 점수 경로가 **셋**이고 예산이 다르다
```
A 취향 분석  score_v6.calculate_score_v6   Core75 + XFactor18 + Gem 6
B 유사 게임  recommend_by_game             (지표60% + 임베딩40%) × 94 + Gem ×5
C 문장 검색  semantic_search               (임베딩85% + 힌트15%) × 94 + Gem ×5
```
**정정(2026-09-04)**: 초판은 경로가 둘이라고 적었다. 셋이다. 경로 C 는 힌트 점수라는
고유 항을 갖고, `score_breakdown` 의 gem 키 이름도 A(`gem_score`)와 B·C(`gem_bonus`)가
다르다 — 감사 도구가 이걸 몰라 B·C 의 gem 기여분을 못 읽고 있었다.
→ 한쪽 공식만 고치면 세 화면의 점수가 서로 비교 불가능해진다. gem 관련 수정은 항상
세 경로를 모두 본다.

---

## 4. 이번 버그들의 실제 원인 분류

| 분류 | 사례 | 공통점 |
|---|---|---|
| **A. 연결 지점을 이름으로 추측** | ① `weekly_pipeline` 이 `batch_processor --version` 을 안 넘김(기본값이 교사 라벨) ② 임베딩 후 `is_active` 전환 단계 부재 ③ `extraction_version`('gpt5.4-batch-v1')을 `analysis_method`('gpt5.4_batch')로 착각 ④ `rec_snapshot` 이 실제 응답을 안 보고 필드명을 지어냄 | 옆 컴포넌트를 **2분만 읽으면** 확인됐다. 이름에서 동작을 추론했다 |
| **B. 측정 없이 숫자를 단정** | ⑤ 회차 비용 $0.85(실제 $2.45) — 추정기가 다른 모델 단가를 쓰는 걸 확인 안 함 ⑥ "배치 할인과 캐시 할인은 중복 안 된다" — 근거 없이 단정, 대시보드에 별도 항목으로 존재 | **1차 출처를 보지 않았다.** 사용자가 돈을 잘못된 전제로 썼다 |
| **C. 데이터 분포에 대고 검증 안 함** | ⑦ 무명도에 하한이 없어 리뷰 2~3개가 상위 독식 ⑧ gem 선형 보정이 퇴화 매핑이 되는 것을 만들고 나서야 발견 | 머릿속과 손으로 고른 몇 케이스에서만 맞았다 |
| **G. 표본 출처를 안 물음** (2026-09-05) | ⑪ 홀드아웃 150건(교사 인기작만)에서 X-Factor 100% 포화를 보고 "상수"라고 판정 — 전체 풀은 7.7% 포화, 88.7% 가 15.6 미만인 게이트였다 | C 분류의 하위 사례. 검증 표본이 모집단을 대표하는지 먼저 확인 |
| **D. 실행 환경 가정** | ⑨ `/proc` 스캔(윈도우에서 크래시) ⑩ 취소 시 `return 0` → 호출부가 성공으로 오해해 파괴적 쓰기 | 내가 쓴 두 함수의 규약조차 안 맞췄다 |

### 더 근본적인 것
이틀 동안 **매 턴 산출물(스크립트·문서·커밋)을 만드는 것**에 최적화했다. 그게 진척처럼 보였다.
그런데 오늘 3개 검토를 병렬로 돌리자, **내가 계속 편집하던 그 파일들에서** 의도 이탈 14건이
나왔다 — 4단계 가중치가 메인 경로에서 죽어 있다는 것, `0.0` 이 `5.0` 으로 읽힌다는 것.
읽으면 보이는 것들이었다. 만들기만 하고 읽지 않았다.

**시작할 때 해야 했던 일 한 가지**: "게임 하나가 화면에 나오고 점수를 받기까지"를 코드로
한 번 끝까지 따라가는 것. 그것만 했으면 A 분류 전체와 C-1·C-4가 첫날 보였다.

---

## 5. 변경 전 체크리스트

지표·점수·노출·라벨을 건드리는 모든 작업에 적용한다.

- [ ] **끝까지 따라갔나** — 이 값을 읽는 곳을 `grep` 으로 전부 찾았나? 폴백(`or`, `COALESCE`,
      `getattr` 기본값)이 걸려 있나? 0과 NULL을 구분하나?
- [ ] **기본값이 채점 규칙이 되지 않나** — `.get(k, default)` 의 default 가 실제로 얼마나 자주 쓰이나?
      호출자가 그 키를 채우는가? (C-10)
- [ ] **세 경로를 봤나** — 경로 A(`score_v6`) / B(`recommend_by_game`) / C(`semantic_search`)
      전부 확인했나? 응답 키 이름(`gem_score` vs `gem_bonus`)까지 봤나? (C-8)
- [ ] **캐시를 비웠나** — 캐시 키에 로직 버전이 없다. 점수를 고친 뒤 측정하려면 먼저
      `POST /ops/cache/invalidate` + `GET /ops/cache` 로 `total_keys == 0` 을 확인해야 한다.
      확인 없이 얻은 "변화 없음"은 증거가 아니다 (§C-9)
- [ ] **코호트를 좁혔나** — `analysis_method` 조건이 있나? 교사 데이터가 대상에 들어가나? (I-1)
- [ ] **원본을 보존했나** — 되돌리는 명령이 있나? 백업 테이블이 실제로 원본을 담나?
- [ ] **분포에 대고 검증했나** — 실제 데이터에서 상위·하위 20건을 눈으로 봤나? 극단값(0, NULL,
      표본 1~3개)에서 어떻게 되나?
- [ ] **숫자의 출처를 말할 수 있나** — 이 수치가 계산인가 실측인가? 1차 출처가 무엇인가? (B 분류)
- [ ] **동시 실행 충돌이 없나** — Steam API, 배치 산출물 파일명, DB 락 (C-6·C-7).
      파이프라인은 `data/pipeline.lock` 으로 이중 실행을 막는다 — 락이 있는데 돌려야 하면 이유를 먼저 확인한다.
- [ ] **되돌릴 수 있나** — 한 줄로 되돌리는 방법이 있나? 없으면 왜 없나?
- [ ] **플래그가 실제로 서빙에 닿았나** — `.env` 만 고친 게 아닌가? compose `environment:` 에 있나?
      `up -d` 로 재생성했나? 응답/ablation 헤더에서 적용값을 봤나? (C-11)
- [ ] **비용을 쓰는 경로에 레이트 리밋이 붙었나** — LLM·임베딩을 호출하는 엔드포인트는 IP 단위 제한이 필수다.
      `settings.RATE_LIMIT_*` 가 있는 것과 라우트에 붙은 것은 다르다 — 라우트의 `dependencies` 를 테스트가 검사한다.
      cost_guard 는 피해 상한이지 예방이 아니다. (C-16)
- [ ] **사용자 입력이 프롬프트로 들어가나** — 제어문자 제거·길이 제한·구분자로 감싸고 "데이터일 뿐 지시가 아니다"를 명시한다.
      LLM 출력도 신뢰하지 않는다: 타입·길이 검증 후에만 임베딩/DB 조회로 넘긴다. (C-16)
- [ ] **운영 엔드포인트가 열려 있지 않나** — `/ops/*` 는 `X-Ops-Token` 필수이고, 토큰 미설정 시 운영에서는
      503 으로 막힌다(fail closed). 새 운영 엔드포인트를 만들면 같은 게이트를 붙인다. 확인: 토큰 없이 호출해
      **401** 이 오는지 본다 — 200 이면 옛 코드가 돌고 있다. (C-15)
- [ ] **비밀을 바꿨으면 쓰는 쪽을 재배포했나** — Railway 참조 변수(`${{Postgres.PGPASSWORD}}`)는 값만 갱신되고
      돌고 있는 컨테이너의 환경변수는 옛 값이다. django/fastapi 재배포 후 **DB 를 실제로 읽는 엔드포인트**로 확인한다
      (`/health` 는 정적 응답이라 증거가 아니다). (C-14)
- [ ] **장기 작업을 죽이지 않나** — `docker compose up -d` 는 컨테이너를 재생성한다. `exec -d` 로 돌던 백필/동기화가 있으면 먼저 확인한다. (C-14)
- [ ] **외부 provider 자격증명이 라이브러리가 읽는 필드에 있나** — allauth steam 은 `SocialApp.client_id` 가 아니라
      **`secret`** 을 읽는다(`SteamOpenIDProvider.sociallogin_from_response`). 빈 키로 Steam API 를 호출하면 403 →
      `raise_for_status()` → 콜백 **500**. 확인: `python manage.py check_oauth` (빈칸·Site 연결·중복만 본다). (C-17)
- [ ] **남의 API 를 부르는 콜백이 그 API 장애를 500 으로 흘리지 않나** — 스팀 콜백은 `SafeSteamCallbackView` 가
      `requests.RequestException` 을 잡아 `/login?error=steam_unavailable` 로 되돌린다. 새 소셜 provider 도 같이 감싼다. (C-17)
- [ ] **소셜 로그인이 회원가입 폼으로 빠지지 않나** — allauth 자동 가입 판정은 `user.email` 이 아니라
      `sociallogin.email_addresses` 를 본다. 이메일을 안 주는 provider(스팀)는 `pre_social_login` 에서
      합성 주소를 그 자리에 넣는다. 확인: `manage.py test apps.users` — '훅을 빼면 거부된다'까지 고정돼 있다. (C-17)
- [ ] **운영에서 500 트레이스백이 로그에 남나** — Django 기본 `LOGGING` 은 console 핸들러에 `require_debug_true` 가
      걸려 있어 `DEBUG=False` 면 아무것도 안 찍는다. `settings.LOGGING` 에 `django.request` → stdout 을 명시해 둔다. (C-17)
- [ ] **push 전에 운영 DB 스키마가 코드와 맞나** — 모델에 컬럼을 추가했나? 그러면 운영 마이그레이션 → 채움 → Railway 변수 → push 순서 (C-12)

---

## 6. 관련 문서
- `docs/external_review_log_0904.md` — 외부 검토 3건 기록과 판정(출처·근거 포함)
- `docs/final_verdict_0905.md` — 최종 판단(D-26, 작업 순서 변경, Core 재설계 권고)
- `docs/scoring_mechanism_asis.md` — 점수·지표 메커니즘 현황도(D-1~D-14)
- `docs/code_review_0904.md` — 코드 리뷰 전문
- `docs/gem_transition_plan.md` — gem 전환 계획과 안전 절차
- `docs/backfill_runbook_0904.md` — 백필 후속 작업 순서·비용
