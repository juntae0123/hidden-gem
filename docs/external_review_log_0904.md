# 외부 검토 기록 — 점수 메커니즘 (2026-09-04)

이 문서는 `docs/scoring_mechanism_asis.md` 를 외부 모델에 넘겨 받은 검토 3건을
**출처 / 지적 / 내 검증 판정 / 근거(file:line)** 형태로 남긴 것이다.
다음 세션(모델 교체 후)에서 이 문서만 읽고 이어서 판단할 수 있게 쓴다.

## 0. 출처와 독립성 (중요)

| 회차 | 출처 (사용자 진술) | 성격 |
|---|---|---|
| R1 | TypingMind, **Fable 5** | as-is 문서 기반 1차 검토 |
| R2 | TypingMind, **GPT-5.6 Sol** | as-is 문서 기반 1차 검토 |
| R3 | TypingMind, 위 두 모델 (정정 커밋 재검증) | 내 정정 커밋(`fdac6dc`)에 대한 재검토 |

사용자 진술 원문: "타이핑마인드에서 fable 5랑 gpt5.6 sol 로 뽑은거야".

**내가 한 실수 하나를 먼저 기록한다.** R1/R2 를 서로 다른 검토자로 취급해
"두 모델이 동일하게 지적했다 = 교차검증됐다"고 쓴 적이 있다. 이건 틀렸다.
- 두 검토 모두 **같은 입력 문서**(내가 쓴 as-is 문서)만 봤다. 코드를 직접 읽지 않았다.
- 따라서 두 검토가 일치하는 지점은 "독립적 확인"이 아니라 **같은 문서를 같은 방식으로
  읽었다는 사실**에 가깝다. 내 문서가 틀렸으면 둘 다 같이 틀린다.
- 실제로 R3 가 이 점을 지적했고, 나는 그 지적을 수용한다.

**결론: 외부 검토의 일치는 근거가 아니다. 근거는 코드와 DB 뿐이다.**
아래 판정에서 "확인"은 내가 코드/DB 를 직접 읽어 대조한 것만 뜻한다.

---

## 1. R1 (Fable 5) — as-is 문서 검토

### 1-1. 내 문서의 오류 지적 (수용, 정정 완료)

| 항목 | 지적 | 판정 | 조치 |
|---|---|---|---|
| D-4 | 설명이 실제 코드 동작과 다르다 | **수용** | as-is 문서 정정 (커밋 `07f0bbc`) |
| D-12 | 동일 | **수용** | 동일 |

### 1-2. 신규 결함 제기 N-1 ~ N-5

| 번호 | 지적 | 판정 | 근거 / 비고 |
|---|---|---|---|
| N-1 | 4-tier 가중치(W_PRIMARY/SECONDARY/NEUTRAL/IRRELEVANT)가 49개 지표 전체에 연결되지 않았다 | **확인** | `recommender.py:376-380` `get_weight_map` 은 preferences 에 있는 키만 W_PRIMARY 로 올린다. 나머지는 전부 W_NEUTRAL. |
| N-2 | 지표 결측 처리에서 0 과 NULL 이 구분되지 않는다 | **확인** | `recommender.py:884` `float(getattr(...,f,5.0) or 5.0)` → 실제 0.0 이 5.0 으로 바뀐다 |
| N-3 | gem 계열 컬럼이 하나에 여러 의미를 담고 있다 | **확인** | `gem_potential`(LLM 추정) 과 증거 기반 지수가 같은 컬럼 계보를 공유 → 코호트 간 비교 불가 |
| N-4 | obscurity floor 가 낮아 리뷰 극소수 게임이 과대평가된다 | **확인 + 이미 조치** | `gem_evidence.py` floor=50, z=1.96 적용 (리뷰 2건 게임 51.8 → 억제) |
| N-5 | confidence_score 를 곱하는 설계가 의미를 흐린다 | **확인, 제거 예정** | `recommender.py:566-569` `min((gem/100*0.7 + review_bonus) * confidence, 1.0)` |

### 1-3. 작업 우선순위 제안 (Day 1~3) — 수용, 단 순서 1건 변경

R1 제안: Day1 = 점수 공식 정정 / Day2 = gem 전환 / Day3 = 검증 도구.
**변경**: R3 의 지적을 받아 **캐시 오염 차단을 Day1 앞에 둔다**. 이유는 §3-1 참조.

### 1-4. 검증 방법론 제안

- 불변식 테스트 (invariant tests) → `docs/system_invariants.md` I-1~I-4 / C-1~C-8 로 반영, 테스트 코드는 미작성
- RBO (rank-biased overlap) 로 순위 변화 측정 → **수용, 미구현**. 현재 `rec_snapshot --diff` 는
  단순 교집합/순서변동만 센다. RBO 는 전체 풀 재정렬이 필요해 채점 쪽 도구가 따로 있어야 한다.
- LLM pairwise judge 로 추천 품질 평가 → **보류**. 비용이 붙고, 지금은 기계적 결함이 더 많다.

---

## 2. R2 (GPT-5.6 Sol) — as-is 문서 검토

| 번호 | 지적 | 판정 | 근거 |
|---|---|---|---|
| 2-1 | 점수 경로가 3개라는 서술이 맞다 | **확인** | A `score_v6.calculate_score_v6` / B `recommend_by_game` / C `semantic_search` |
| 2-2 | 4-tier 를 배선하는 대신 **질의 마스크**로 접근하라 | **수용(설계 방향)** | 명시되지 않은 46개 지표에 임의 목표값을 주는 문제를 피할 수 있다. §4 참조 |
| 2-3 | 가중치가 거리 계산에서 **제곱으로 들어간다** | **확인 — 실제 버그** | `recommender.py:439` `vec[i] = val * weight_map.get(field, W_NEUTRAL)` 후 유클리드 거리 → w² 효과 |
| 2-4 | `hint_score` 분모가 잘못됐다 | **확인** | `recommender.py:1120` `hint_score = match / len(metric_hints)` — 건너뛴 힌트가 분모에 남는다 |
| 2-5 | 후보 풀을 `limit*2` 로 잡는 것은 부족하다 | **확인, 우선순위 낮음** | 필터가 뒤에 걸리면 결과 수가 줄어든다 |
| 2-6 | gem 컬럼 분리 + NULL 을 0 과 구분 | **수용** | `gem_evidence_score` + `gem_evidence_status` 로 분리 예정 |
| 2-7 | confidence 곱셈 제거 | **수용** | N-5 와 동일 |
| 2-8 | 구성요소 σ 를 실제로 측정하라 | **수용, 측정했고 해석을 정정했다** | §3-2 참조 |

---

## 3. R3 — 내 정정 커밋(`fdac6dc`) 재검증

### 3-1. 1순위 위험: 스냅샷 캐시 오염 (수용, **이번에 조치 완료**)

원문 요지: "가장 먼저 할 것은 점수 공식 변경이 아니라 스냅샷의 캐시 오염을 차단하는
일입니다. 이 작업 없이 얻은 s1 은 증거력이 부족합니다."

**확인된 사실**
- 캐시 키에 점수 로직 버전이 없다 — `cache.py:89/97/104`
  - `semantic:{query_hash}:{limit}`
  - `rec:game:{app_id}:{count}`
  - `rec:pref:{pref_hash}:{count}`
- 따라서 s0 을 찍고 코드를 고쳐 s1 을 찍으면 **s1 이 s0 의 캐시를 그대로 돌려받는다.**
  "변화 없음" 이 코드가 안전하다는 증거가 아니라 캐시가 살아있다는 증거가 된다.
- `invalidate_all` 은 '키 0개'와 'Redis 예외'를 **모두 0 으로** 반환 — `cache.py:170-195`.
  반환값만으로 성공 판정 불가.

**조치 (`embeddings/rec_snapshot.py`)**
1. `--save` 는 매 회차 `POST /ops/cache/invalidate` 호출
2. 성공 판정을 반환값이 아니라 `GET /ops/cache` 의 `total_keys == 0` 으로 한다
   (`get_stats` 는 실패 시 `{"error": ...}` 를 주므로 'Redis 죽음'과 '키 0개'가 구분된다 — `cache.py:238-240`)
3. 확인 실패 시 **스냅샷을 쓰지 않고 종료 코드 2**
4. 무효화 기록(`meta.cache_clear`)을 스냅샷에 박고, `--diff`/`--variance` 는
   기록이 없거나 실패한 스냅샷에 대해 경고를 먼저 출력한다
5. 탈출구는 `--no-cache-clear` 하나뿐이며 스냅샷에 '증거 불가' 표시가 남는다

### 3-2. σ 해석 오류 (수용, 이미 정정 + 이번에 도구까지 정정)

- 내가 "σ 비중 = 랭킹 지배력 = 실제 영향력" 이라고 썼다. **틀렸다.**
- 실측: ΣCov ≈ **−0.553** → 상위 N 표본에서 구성요소 간 음의 공분산이 크다.
  이것은 게임의 성질이 아니라 **합계 상위 N 으로 잘라낸 선택 절단(collider) 인공물**이다.
- 게다가 도구 자체가 "σ 비중이 실제 영향력이다" 를 헤더에 출력하면서
  바로 아래 [측정 한계] 에서 그걸 부정하고 있었다 → **이번에 헤더·독스트링 정정**.
- 순위 영향력을 재려면 구성요소를 끄고 **전체 풀을 재정렬**해 Kendall τ / RBO 를 봐야 한다.
  스냅샷은 상위 N 만 담으므로 원리적으로 불가능하다.

### 3-3. rec_snapshot 결함 3건 (수용, 이번에 조치 완료)

| 지적 | 판정 | 조치 |
|---|---|---|
| 경로 B/C 의 gem 기여분을 못 읽는다 (`sb.get("gem_score")` 만 본다. B/C 키는 `gem_bonus`) | **확인** | `_gem_contrib()` 로 키 존재 여부 분기. `or` 를 쓰지 않아 **실제 값 0.0 이 보존된다** |
| 같은 라벨을 덮어써 증거가 사라진다 | **확인** | 기존 파일 있으면 거부(exit 2), `--overwrite` 필요 |
| 16개 중 1개만 성공해도 종료 코드 0 | **확인** | `ok != total` 이면 exit 1 |
| 포화도 기준이 명목 예산(75/18/6)이라 무의미 | **확인** | Core 는 시그모이드 상한(거리 0 에서 0.8176) 때문에 75 에 **도달 불가** → 명목 기준으로는 영원히 0%. **관측 최대값의 97% 기준**으로 교체 |
| pooled σ 가 시나리오 평균 차이를 섞는다 | **확인, 편향 방향 불명** | 합산 σ 와 '시나리오 내 평균 σ' 를 **둘 다** 출력하고 어느 쪽으로도 단정하지 않는다 |
| 같은 게임이 시나리오 간 중복 등장 → 표본 비독립 | **확인** | 고유 게임 수 / 중복 등장 건수를 출력하고 "유의성 검정에 쓸 수 없다"고 명시 |

### 3-4. X-Factor 해석 (수용 — '확정'에서 '가설'로 강등)

- 내 1차 진단: "X-Factor 는 전원 포화된 무해한 상수 가산" → **틀렸다.**
- 2차 진단: "X-Factor 는 선택 게이트다. Core 승자 폭이 5.7 밖에 안 되므로
  X-Factor < 15.6 인 후보는 상위 10 진입 자체가 막힌다."
- R3 판정: 이건 **강한 가설이지 확정이 아니다.** 상위 N 표본만으로는 증명되지 않는다.
  → 문서 표기를 '확정'에서 '강한 가설'로 내린다.
- 파생 주장 **"X-Factor ↔ 인기도 상관"** 은 **측정 전까지 보류(withheld)**. 근거 없다.
- **실무적 함의**: X-Factor 를 제거하는 커밋에는 "상위 10 중 절반 유지" 같은
  안정성 합격 기준을 적용하면 안 된다. 그 변경은 순위가 크게 바뀌는 것이 정상 예측이다.
  → `--diff` 출력에 이 경고를 넣었다.

### 3-5. `must_not` 은 안전망이 아니다 (수용)

- boolean 태그의 `must_not` 이 임계값 처리 없이 무시되는 경로가 있다.
- "사용자가 싫다고 한 것은 안 나온다"를 `must_not` 에 의존해 설명하면 안 된다.

### 3-6. `query_hint` 는 스키마에 없다 (**내가 직접 확인**)

- `schemas/game.py` 의 `RecommendByGameRequest` 필드는 **`app_id`, `count`,
  `exclude_same_developer` 셋뿐**이다. `query_hint` 는 없다.
- 따라서 `routers/games.py:264` 의 `query_hint=getattr(request, "query_hint", None)` 은
  **항상 None** 이다.
- 결론: 경로 B 의 4-tier 가중치는 **외부 API 로 도달 불가**하고,
  semantic → 참조 게임 → by-game 내부 재라우팅 경로에서만 값이 들어간다.

### 3-7. 캐시 키에 조건이 빠져 있다 (**내가 직접 확인**)

| 캐시 키 | 빠진 조건 | 결과 |
|---|---|---|
| `by_game_key(app_id, count)` | `exclude_same_developer` | 조건이 달라도 같은 캐시를 돌려준다 |
| `by_preference_key(...)` | `required_tags`, `excluded_tags`, `min_gem_potential` | 동일 |
| `semantic_key(query, limit)` | `min_gem_potential` | 동일 |
| 전부 | `CACHE_VERSION` prefix 없음 | 점수 로직을 고쳐도 옛 결과가 살아있다 |

부가 확인: `MD5[:8]` 은 해시 충돌 여유가 얇다 / `invalidate_game` 은 이름과 달리
`rec:game:*` 만 지운다(pref·semantic 에 남은 그 게임은 안 지워짐) / `keys()` 대신
`scan_iter()` 를 써야 한다(운영 Redis 블로킹).

### 3-8. `use_masking` 은 죽은 코드인데 API 문서는 효과를 약속한다 (수용)

- API 설명에 "변별력 5배 향상" 이 적혀 있지만 `use_masking` 경로는 실행되지 않는다.
- **거짓 계약**이므로 문서에서 내리거나 코드를 살려야 한다. 포트폴리오 리스크.

### 3-9. 응답 스키마가 실제와 다르다 (**내가 직접 확인**)

- `GameMetricResponse` 는 평가 필드 **3개**(`gem_potential`, `gem_percentile`,
  `confidence_score`)를 노출한다. 문서는 2개라고 적혀 있었다.
  → 실제 필드 수는 **49 + 9 + 3 = 61개** (문서의 60 이 아니다).
- 응답 스키마 설명이 **경로 A 만** 기술하고 있어 B/C 응답 형태와 어긋난다
  (`similarity_score` / `score_breakdown` 키 구성이 경로마다 다르다).
- `query_type` 에 `semantic_by_reference` 가 빠져 있다.

### 3-10. 기타 (수용, 우선순위 낮음)

- 스키마에 mutable default 사용
- `preferences={}` 빈 요청이 통과된다
- 태그 충돌(`required_tags` ∩ `excluded_tags`)을 막지 않는다
- `to_display_score` 하한이 없다 → 시맨틱 코사인이 음수면 표시 점수가 음수가 될 수 있다
- `/stats/overview` 가 코호트가 다른 gem 값(LLM 추정 vs 증거 기반)을 평균낸다 — 비교 불가한 값의 평균

---

## 4. 확정된 설계 의도 (검토와 무관하게 바꾸지 않는다)

사용자 진술: **"점수가 사용자의 취향 혹은 검색문장(문장이던 한단어던 문단이던)에
따라 달라지는건 내 의도가 맞아."**

→ 따라서 "같은 게임인데 질의마다 점수가 다르다"는 것은 **버그가 아니다.**
검토에서 이 방향의 지적이 나오면 기각한다. 4-tier 를 '배선'하는 작업도 이 의도 위에서
해야 하며, 명시되지 않은 46개 지표에 임의 목표값을 주는 방식은 이 의도를 왜곡한다
(R2 의 질의 마스크 제안이 이 의도와 더 맞다).

또한 데이터는 절대 삭제하지 않는다 — 노출은 `is_active` 게이트로만 조절한다.

---

## 5. 이번 커밋에서 실제로 한 것 / 아직 안 한 것

**한 것**
- `rec_snapshot.py`: 캐시 무효화 강제 + 검증, 라벨 덮어쓰기 거부, 경로 B/C gem 키 흡수,
  16/16 성공 강제, σ 헤더·독스트링 정정, 포화도 기준을 관측 최대로 교체,
  pooled σ 한계 명시 + 고유/중복 게임 수 보고, X-Factor 변경 시 합격기준 경고
- 이 기록 문서

**아직 안 한 것 (다음 세션 작업 순서)**
1. `--save s1_after_gate` 실행 → `--variance s1_after_gate` → `--diff s0 s1`
   (σ_final vs σ_core 로 절단 여부 재판정)
2. Day 1 수정 커밋 + 불변식 테스트 4건:
   - D-10 `or 5.0` → `resolve_null`
   - D-2 `or 50` → `is None` 분기 (4곳)
   - D-24 `positive_ratio or 0.5`
   - D-16 `NUMERIC_METRIC_FIELDS[:20]` → 49개 전체
   - D-18 quality 상한 클램프
   - D-22 hint_score 분모
   - `nullslast` 적용
   - 시맨틱 표시 점수 하한 0
   - 캐시 키에 조건 추가 + `CACHE_VERSION` prefix
3. 교사 코호트 리뷰 백필 (`refresh_reviews --cohort teacher --new`, 무료, 약 1.2h)
   — gem 전환의 **선행 조건**
4. `--threshold-report` 로 노출 임계값 확정 (권고안: 노출 `리뷰 ≥ 3 AND Wilson ≥ 0.35`,
   배지 `리뷰 ≥ 30`)
5. gem 컬럼 분리 (`gem_evidence_score` + `gem_evidence_status`, NULL ≠ 0),
   gem_potential fallback / review_bonus / discovery+quality / `× confidence` 제거
6. 질의 마스크 + 가중 RMSE `sqrt(Σw·diff²/Σw)` + X-Factor 제거를
   **한 변경 창에서** 절제 실험(ablation)과 함께
7. 백필 재개 (`--limit 500 --loop --audit-n 30`, 약 $27), 주간 스케줄러 등록
8. `git push` (미푸시 약 30커밋)
