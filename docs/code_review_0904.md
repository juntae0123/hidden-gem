# 코드·데이터 리뷰 (2026-09-04) — 잘못 잡고 방향 정리

3개 영역을 병렬로 정독 검토했다: ① 수집 파이프라인 ② 신규 품질/gem 도구 ③ 서빙 계층(추천 점수).
아래는 **소스에서 확인한 것만** 적었다. 검토 중 제기됐지만 내가 직접 확인해 **기각한 것**도 끝에 남긴다.

---

## 0. 지금 진행 중인 작업 (2026-09-04 12:10 UTC 기준)

| 상태 | 내용 |
|---|---|
| **실행 중** | `post_backfill` 의 `reviews` 단계 = `refresh_reviews --new`. 신작 8,653건의 Steam 리뷰 수 조회. 진행 3,700/8,653, 완료 예상 13:40 UTC. 끝나면 노출 게이트(리뷰 10개 미만 → `is_active=FALSE`)가 자동 적용되고, 이어서 `--new-sample` 이 돌고 종료. **OpenAI 비용 0** (Steam 무료 API). |
| **정지** | 백필 루프. 16회차 8,653건 적재 후 `data/STOP_BACKFILL` 로 정상 종료(05:52). 3/16~6월초 약 5,500건 미수집. |
| **완료** | 1회차 라벨 복구(999건), 임베딩 995건 생성, 홀드아웃 150쌍 감사($1). |
| **미적용** | gem 근거 지수 전환. `gem_evidence` 는 미리보기만 돌렸고 DB는 무변경. |
| **미푸시** | 커밋 22건 (프로젝트 21 + div-log 1). |

---

## 1. 지금 당장 위험 — 실행 금지 / 수정 완료분

### 1-1. `gem_evidence --apply` 에서 "n" 을 눌러도 DB에 0을 쓴다 [치명 · 수정 완료]
`apply()` 가 취소 시에도 `return 0` 이었고, 호출부가 `rc == 0` 을 성공으로 보고 이어서
무근거 게임 `gem_percentile = 0` 쓰기를 실행했다. **분포만 보고 취소하려던 조작이 부분 실행된다.**
→ 취소 시 `return 1`. (`4f5dbff` 이후 수정)

### 1-2. `gem_percentile = 0` 이 프로덕션에서 **50으로 읽힌다** [치명 · 코드 수정 필요, 미수정]
```python
recommender.py:898   gem_percentile=float(game.metrics.gem_percentile or 50)
score_v6.py:294      gem_pct = gem_percentile or 50
recommender.py:1171,1202,1234   metric.gem_percentile or metric.gem_potential
```
`0.0 or 50` → **50**. 근거 지수는 유명작을 0으로 만드는 것이 핵심인데, 그 0이 중간값 50으로
해석된다. 즉 **전환의 의미가 정반대로 뒤집힌다.** 응답 필드에서는 0이 LLM gem(예: 88)으로 부활한다.
→ `is None` 검사로 바꿔야 한다. 이 수정 없이는 gem 전환을 적용해선 안 된다.

### 1-3. 교사 코호트에 리뷰 근거가 없다 → 한 컬럼에 세 스케일 [치명 · 하드 거부로 수정 완료]
교사 4,190건은 `review_count`/`steam_positive_ratio` 가 비어 있다. 이 상태로 적용하면
교사=LLM 백분위 0~100, 학생=근거 지수 0~72, 무근거=0 이 한 컬럼에 섞이고 뱃지 70+ 는
거의 교사 게임만 뽑는다 — 의도와 정반대.
→ `gem_evidence --apply` 가 교사 무근거 100건 초과면 **거부**(exit 2)하고 `--cohort teacher` 선행을 요구.

### 1-4. `latest_batch_output()` 이 홀드아웃 결과를 집어 교사 데이터를 덮어쓸 수 있다 [치명 · 수정 완료]
`data/batch_output_*.jsonl` 중 mtime 최신을 고르는 방식이었다. 홀드아웃(`--sync`)도 같은 경로·같은
패턴으로 파일을 만든다. 루프와 감사가 겹치면 **교사 150건의 metrics 가 학생 값으로 덮이고
`analysis_method` 까지 학생 라벨로 바뀐다.** 백업이 없어 복구 불가.
→ 회차 시작 시점 스냅샷과의 **차집합**만 인정하도록 수정.

### 1-5. 크롤러가 DB 접속 실패를 삼키고 빈 중복 집합을 반환 [치명 · 수정 완료]
`load_existing_app_ids` 가 예외를 잡아 `set()` 을 돌려줬다. 일시적 DB 오류 하나로 이미 분석된
게임(교사 포함)을 재수집·재분석하고 그 metrics 를 학생 값으로 덮어쓴다.
→ 즉시 중단(exit 4)으로 변경.

---

## 2. gem 전환 전 반드시 고칠 것 (서빙 계층 · 승인 필요)

이 묶음은 추천 점수 체계를 건드리므로 승인 후 한 커밋으로 진행한다.

1. **`or 50` → `is None`** (`recommender.py:898`, `score_v6.py:294`, `:1171/1202/1234`) — 1-2 참조.
2. **`gem_potential` 폴백 제거** (`recommender.py:560-563`) — 근거가 없는 게임이 LLM 스케일 값을
   물려받아, 리뷰 데이터 없는 교사 게임이 **실제 무명 명작보다 2배 높은 gem 보너스**를 받는다.
   실측: 교사(리뷰 NULL, gem 85, conf 0.9) 4.03점 vs 진짜 히든젬(리뷰 800, 지수 70, conf 0.7) 1.92점.
3. **이중 계상 제거** — 근거 지수에 이미 리뷰 수·긍정률이 들어있다.
   - `recommender.py:567` `review_bonus` 항 제거
   - `score_v6.py:312` `discovery`(리뷰 수 계단) + `quality`(긍정률) 항 제거, `gem_signal` 만 남김
4. **스케일 재조정** — 근거 지수 최대가 약 72라 `/100` 으로 나누면 상단이 도달 불가.
   `recommender.py:568`, `score_v6.py:310` 의 분모를 실측 최대로. 뱃지 임계값 70/80/90 도 재설정 필요
   (프론트 `lib/score.ts`).
5. **`SCORE_GEM_MAX = 6.0` vs 다른 경로 `×5.0`** — 두 엔드포인트의 gem 예산이 다르다. 하나로 통일.

---

## 3. 추천 품질 결함 (gem 과 무관하게 이미 점수를 망치고 있다)

### 3-1. 진짜 `0.0` 이 `5.0` 으로 읽힌다 [치명 · 이번 리뷰의 최대 발견]
```python
recommender.py:884   f: float(getattr(game.metrics, f, 5.0) or 5.0)
```
`0.0 or 5.0 == 5.0`. 지표 값 0은 흔하다 — 실측으로 `horror_factor` 0이 학생 48%/교사 40%,
`cozy_factor` 0이 35%/21%, `stealth_importance` 0이 90%+. **이 값들이 전부 중립 5.0으로 바뀌어
by-preference(취향 분석 = 메인 동선)에 들어간다.**
- "공포 원함(9)" → 공포 0인 게임이 5로 읽혀 중간 점수를 받는다
- "힐링 원함(공포 0)" → 공포 0인 완벽한 후보가 5로 읽혀 오히려 불리해진다
양방향으로 깨진다. `NULL_FALLBACK_POLICY`(`recommender.py:250-261`)가 이미 지표별 폴백을
정의해 두었는데 이 경로만 무시하고 있다. → `resolve_null(f, raw)` 로 교체.

### 3-2. 4단계 동적 가중치가 by-preference 에서 **작동하지 않는다** [높음]
`recommend_by_preference` 는 `weight_map` 을 만들고 `target_vec`(848), `cand_vec`(879)까지
계산하지만 **점수에 쓰지 않는다.** 실제 점수는 `calculate_score_v6` 이 전담하고, 그 함수는
weight_map 을 인자로 받지 않으며 내부에 `2.0/1.0` 하드코딩 가중치를 쓴다. weight_map 은
응답에 echo 되고 match_reason 정렬에만 쓰인다.
→ PRD·포트폴리오의 핵심 주장("검색 의도에 따라 지표 가중치를 5.0/2.0/0.5/0.1로 분류")이
메인 엔드포인트에서 사실이 아니다. 지표 강등도 `get_weight_map` 만 고쳐선 효과가 없다.

### 3-3. 신뢰 못 할 3개 지표가 X-Factor 에서 무가중치로 보너스를 받는다 [높음]
`score_v6.py:235` X-Factor 는 49개 지표를 **전부** 순회하며 값 ≥8이면 가점한다(가중치 없음).
`modding_support` 하나가 9면 **+3.90점**, 3개가 9면 **+11.70점**(18점 예산 중) — gem 예산 전체보다 크다.
학생 모델에서 이 3개는 r=0.36~0.61로 신뢰 불가. 추가로:
- `recommender.py:372` 중립 하한 목록에 `monetization_fairness` 가 들어가 0.1 → 0.5로 승격
- `recommender.py:149` `community_dependency` 가 `feature_coop` 의 secondary(2.0×)
- `score_v6.py:116` `modding_support` 가 사용자 노출 identity 문구 후보

### 3-4. `max_review_count` 유명작 필터가 무력 + 적용 경로 누락 [높음]
```python
recommender.py:858-862
(Game.review_count <= max_review_count) | (Game.review_count.is_(None))
```
NULL 을 명시적으로 통과시키고 0도 통과한다. 교사 게임이 전부 NULL/0이라 **필터가 한 번도
걸러낸 적이 없다** (스냅샷에서 5개 프리셋 전체/히든젬 결과 동일, 공포 1위 FNAF3).
더 나아가 필터가 **by-preference 에만** 있다. by-vibe(칩 UI)는 인자를 아예 넘기지 않고,
by-game·semantic·`/games/search` 에는 조건이 없다.
→ 교사 리뷰 백필 후 조건을 `COALESCE(review_count,0) <= max` 로 바꾸고, 누락 경로에 전파.

### 3-5. `/games/search` 가 NULL 을 먼저 정렬한다 [중간]
`routers/games.py:96` `Game.review_count.desc()` — Postgres 는 DESC 에서 NULL 을 **먼저** 놓는다.
리뷰 데이터 없는 코호트가 검색 1페이지를 점유한다. 같은 파일의 `recommender.py:948` 은
`.desc().nullslast()` 로 올바르게 쓰고 있어 일관성도 깨졌다.

### 3-6. 그 외 확인된 것
- 부정 선호가 Core 에서 무시된다: `score_v6.py:172-175` 가 `v >= 7` 만 채택 → "공포 빼고(0)"는 가중치 0
- Core 와 X-Factor 가 사용자 요청 지표를 이중 계상 (`score_v6.py:232` 가 intent 필드를 제외하지 않음)
- `must_not` 은 NULL 을 통과시키지만 점수는 NULL/0을 5.0으로 본다 (3-1과 충돌)
- by-game 캐시 키에 `exclude_same_developer` 누락 (`routers/games.py:253`) → 다른 조건 결과가 서로 서빙됨
- `/games/search` 는 `LIMIT` 후 파이썬에서 `min_gem` 필터 → 페이지가 짧아지고 비결정적
- `use_masking`, `query_hint` 는 스키마·문서에만 있고 동작하지 않는다
- 장르 Core 매칭은 `genres.split(',')[0]` 로 **첫 장르만** 본다. Steam 은 액션/캐주얼/인디를 앞에
  두는 경우가 많아 '전략'·'공포' 게임이 `DEFAULT_CORE_METRICS` 로 떨어진다 (키 언어는 정상 — 아래 기각 항목 참조)

---

## 4. 파이프라인 견고성 (재개 전 처리)

| 항목 | 위험 | 조치 |
|---|---|---|
| `batch_processor` 가 1,000행 UPSERT를 **한 트랜잭션**에서 처리하고 행별 `except` 로 계속 | 한 행 실패 → 트랜잭션 abort → 전량 미커밋 + 다음 회차 재과금. 로그는 "성공 312개"로 보인다 | 행별 `begin_nested()` 또는 개별 트랜잭션 |
| `generate_embeddings` 가 100개 묶음을 재시도 없이 호출, 청크 전체 성공 후에만 기록 | 설명 20k자 게임 하나로 400 → 그 청크 100개 전량 폐기 + 파이프라인 중단. 이미 지불한 임베딩 유실 | 텍스트 절단 + 청크별 커밋 + 개별 폴백 |
| `relabel_version` 이 **실패 응답의 app_id 까지** 재라벨 | metrics 없이 학생 라벨 → pending도 아니고 분석도 아닌 영구 미아. 1회차 실패 1건이 이미 이 상태일 수 있다 | `status_code == 200` 만 수집 |
| `activate_games`(batch_processor)가 리뷰 게이트를 우회 | 재적재 시 게이트로 내린 게임이 다시 켜진다 (멱등하지 않음) | `exposure_policy.activate_eligible` 호출로 통일 |
| `recalc_percentile` 이 루프 끝에 1회만 | 회차 중 활성화된 게임이 `gem_percentile` NULL 상태로 서빙됨. 루프가 중간에 죽으면 영구 NULL | 활성화 조건에 `gem_percentile IS NOT NULL` 추가 또는 회차마다 재계산 |
| pending 재시도에 시도 횟수가 없다 | 계속 실패하는 게임이 최대 60회 재과금, 오래된 실패는 `created_at DESC` 정렬에 밀려 영구 미시도 | 시도 횟수 컬럼 + 오래된 것 우선 |
| `refresh_reviews` 가 `total_reviews: 0` 응답을 그대로 기록 | 리뷰 4,200개 게임이 일시적 응답 이상으로 0/NULL 로 덮이고 복구 불가(로그에 비율 미기록) | 비영(非零) → 0 덮어쓰기 거부 옵션 |
| `rec_snapshot --save` 가 기존 라벨을 덮어쓴다 | before 기준선 유실 → diff 가 "변화 없음"으로 오판 | 존재 시 거부 |

---

## 5. 감사 도구 자체의 결함

- `audit_student` 드리프트 게이트가 **NaN 상관을 통과로 처리**한다(`:193`). 학생이 어떤 지표를
  전부 같은 값으로 뱉으면(가장 위험한 붕괴) r=NaN → 무플래그 + 낮은 MAE 로 "가장 건전한 지표"로 보인다.
- 드리프트 게이트가 `numeric_mae_mean` 만 본다. 이미 깨진 것으로 판명된 `gem_mae`/`gem_spearman` 은
  기록만 하고 비교하지 않는다.
- 기준선이 **자기 자신을 기록**한다(첫 실행이 곧 기준). 조작자 확인 없이 그날 품질이 정상으로 굳는다.
- 드리프트 감지 시 `SystemExit(3)` 이 **오적재 방지 파일 이동보다 먼저** 실행된다 → 홀드아웃 결과가
  `data/` 에 남아 다음 `batch_processor` 가 교사 데이터를 덮어쓸 수 있다. (1-4와 같은 사고 경로)
- `gem_evidence` 의 영향 리포트가 **다른 엔드포인트 공식**을 재현하고 있다. by-preference(프리셋 10/13)는
  `score_v6.compute_gem_bonus`(gem 가중치 0.3, 예산 6.0)를 쓰는데 리포트는
  `recommender._calculate_gem_bonus`(0.7, 5.0)를 계산한다 → 표시된 영향 수치가 실제와 다르다.
- `gem_evidence` 의 백분위가 `PERCENT_RANK` 와 다르다(동점 처리·모집단). `--write percentile` 값은
  기존 컬럼 값과 비교 가능하지 않다.
- `calibrate_student` 의 `MAX_MAE_RATIO` 가 교사 분산이 좁은 지표의 정상 보정을 거부한다.
  드라이런 미리보기가 현재 컬럼에서 계산하고 실제 쓰기는 백업 원본에서 계산해 재적용 시 값이 다르다.
- `usage_report` 가 서로 다른 모델의 토큰을 한 단가로 합산한다 (교사·학생 배치가 섞이면 과소 추정).

---

## 6. 데이터 상태 점검 결과

- 교사 코호트 **손상 없음**: `gem_potential` 보유 12,837건, 전환 전 `gem_percentile` 보유 4,193건
  = 교사 4,190 + α. 대량 재라벨 흔적 없음.
- 학생 8,653건: 49지표 완전체 100%, 평균 MAE 0.77(교사급), 재현성 77% 완전 일치.
- `gem_potential`(학생)은 사용 불가 판정. 근거 지수와의 상관 **r = −0.022** — LLM 은 "인지도 대비 품질"을
  애초에 측정하고 있지 않았다.
- 신뢰 못 할 3개 지표가 49차원 제곱오차의 **25.4%**. 제외 시 교사-학생 벡터 거리 오차 −14%.
- 리뷰 조회 중간 집계(게이트 통과 1,243건 시점): 근거 보유 2,542건 중 지수 μ49.1 σ19.4.
- 무근거 10,295건 중 활성 6,425건 = 교사 4,190(게이트 대상 밖) + 게이트 적용 전 활성화된 학생분.
  리뷰 조회 완료 시 학생분은 정리된다.

---

## 7. 제기됐으나 확인 후 **기각**한 지적

- **"장르 Core 매칭이 죽었다(키가 한글인데 DB는 영문)"** → 기각. `games.genres` 는 한글이다
  (교사 데이터 `"액션, 무료 플레이"`, 크롤러 로그 `"어드벤처, 인디"` — Steam 한국어 로케일로 수집).
  다만 **첫 장르만** 보는 문제는 실재한다(3-6).
- **"`IN (:ver, :ver2)` 바인딩 오류"** → 기각. 스칼라 바인드 2개로 올바르다.
- **Wilson 하한 / 무명도 / 스피어만 동점 처리 / 금지 컬럼 가드 / `recalc_percentile` 공식**
  → 모두 코드가 문서와 일치하며 정상.

---

## 8. 다음 작업 순서 (권장)

**A. 지금 (리뷰 조회 완료 대기 중, 비용 0)**
1. `post_backfill` 완료 확인 → 게이트 적용 결과와 리뷰 분포 확인
2. 교사 리뷰 백필: `refresh_reviews --cohort teacher --new` (무료, 1.2h) — 이게 없으면 gem 전환도,
   유명작 필터도 불가능

**B. 서빙 계층 수정 (승인 후 한 커밋)** — 2장 5개 + 3-1(`or 5.0`) + 3-3(X-Factor 제외) + 3-5(nullslast)
   `or 5.0` 수정만으로도 취향 분석 정확도가 눈에 띄게 달라질 것이다(지표 값 0이 20~90% 비중)

**C. gem 전환** — `rec_snapshot --save s1` → `gem_evidence` 미리보기 → `--apply` → `--save s2` → `--diff`

**D. 파이프라인 견고성** — 4장 표의 상위 4개 (트랜잭션, 임베딩 청크, relabel 필터, activate 통일)

**E. 재개** — `--limit 500 --loop --audit-n 30`, 회차당 $2.45, 남은 5,500건 ≈ $27

**F. 정리** — 3-2(4단계 가중치가 실제로 동작하게 할지, 아니면 문서·포트폴리오 주장을 정정할지 결정)
