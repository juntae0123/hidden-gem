# 생애주기 분리 — 랭킹·추천·프런트 개편 명세 (2026-09-05)

개발자 결정: "신작과 스테디/유명작을 같은 선상에 놓지 않는다. 랭킹은 스테디 / 요즘 뜨는 / 신작으로 나눈다.
추천에서 신작은 '데이터가 부족해 정확하진 않지만 받을래?' 로 물어서 넣거나 따로 뺀다."
→ decisions R-11 확정, R-12(프런트) 신설. 이 문서가 구현 명세다.

원칙 하나: **취향 일치(Core)는 모든 게임에 같은 척도. 발굴·랭킹은 생애주기별로 다른 질문.**

---

## 1. 생애주기 정의 (백엔드, 요청 시 계산 — 컬럼 추가 없음)

```
lifecycle(game):
    if review_count >= 20000                         → "famous"       이미 발견됨
    elif release_date and (today − release_date) <= 180일 → "new"       판단 보류 구간
    else                                             → "established"  발굴 질문이 성립하는 구간
    (release_date NULL 이면 established 로 취급 — 크롤러가 못 읽은 구간, 신작일 가능성은 낮다)
```
경계 180일·20,000 은 `.env` 로 조정 가능(`LIFECYCLE_NEW_DAYS`, `LIFECYCLE_FAMOUS_REVIEWS`).
응답 스키마 `RecommendedGame` / `GameWithMetrics` 에 `lifecycle` 필드 추가.

## 2. 지표 — 생애주기마다 다른 것을 잰다

| 층 | 잰다 | 계산 | 필요한 것 |
|---|---|---|---|
| new | **초기 속도** | `velocity = review_count / max(days_since_release, 7)` (리뷰/일). 같은 90일 출시 코호트 안에서 백분위 | `release_date` (있음) |
| new | 초기 평판 | Wilson 하한 (n ≥ 3) | 있음 |
| established | **발굴 지수** | R-3 그대로: Wilson × 로그 무명도 | 교사 리뷰 백필 완료(됨) |
| 전체 | **최근 상승** | `Δreviews(30일) / max(이전 총량, 50)` — 상대 증가율 | **리뷰 이력**: `review_refresh_log` 를 PK(app_id) 덮어쓰기에서 **append-only** 로 바꿔야 한다 (아래 §5) |

gem 보너스(점수에 더해지는 6점): `established` 만 받는다. `new` 와 `famous` 는 0.
`gem_evidence_status`: `ok` / `too_new` / `famous` / `no_reviews` / `insufficient`.

## 3. API

### 랭킹 (신규) `GET /games/ranking?type=steady|rising|new&genre=&limit=30`
지금 `/ranking` 페이지는 랭킹이 아니라 **장르 프리셋 by-preference 결과**다(`ranking/page.tsx:23-37`). 이걸 진짜 랭킹으로 바꾼다.

| type | 대상 | 정렬 | 최소 조건 |
|---|---|---|---|
| `steady` (스테디 히든젬) | established | `gem_evidence_score` desc | 리뷰 ≥ 30, Wilson ≥ 0.5 |
| `rising` (요즘 뜨는) | established + new | 30일 상대 증가율 desc | Δ ≥ 20건, Wilson ≥ 0.5 |
| `new` (신작) | new | velocity 백분위 desc, 동률 Wilson | 리뷰 ≥ 3, Wilson ≥ 0.35 |

`genre` 는 `games.genres ilike` 필터. 취향 프리셋은 쓰지 않는다 — 랭킹은 사용자 무관 지표다.
캐시 키 `rank:{VER}:{type}:{genre}:{limit}`, TTL 6h (리뷰 갱신 주기에 맞춤).

### 추천 3경로 공통 `include_new: bool = false`
- `false`(기본): `lifecycle == "new"` 후보 제외. 지금 상위권에 들어오는 신작이 빠지므로 **s-스냅샷으로 전후 확인**.
- `true`: 포함. 응답의 각 게임에 `lifecycle: "new"` 가 붙어 프런트가 뱃지를 그린다. 점수는 Core 만(gem 0).
- 캐시 키에 `include_new` 포함 (`by_preference_key` / `semantic_key` / `by_game_key`).
- `famous` 는 추천에서 제외하지 않는다 — 취향에 맞으면 나온다. 히든젬 화면만 `max_review_count` 로 뺀다(기존 동작).

### 노출 게이트와의 관계
`include_new` 기본 false 이면 메인 추천은 신작을 안 보여주므로, **신작의 `is_active` 게이트를 R-4(리뷰 ≥ 3 AND Wilson ≥ 0.35)로
내려도 메인 목록의 품질은 안 떨어진다.** 신작은 신작 랭킹·신작 포함 토글에서만 보인다. 이것으로 R-4 임계값 논쟁이 정리된다 —
"가능성 보존"(노출)과 "메인 품질"(기본 제외)이 동시에 성립한다.

## 4. 프런트

| 화면 | 지금 | 바꿀 것 |
|---|---|---|
| `/ranking` | 탭 전체/장르/내취향 — 실제로는 프리셋 추천 | 탭 **스테디 히든젬 / 요즘 뜨는 / 신작**. 각 탭 안에 장르 칩. 카드에 근거 숫자 표시(스테디: 발굴지수·리뷰수·긍정률 / 뜨는: 30일 +N건 / 신작: 출시 D+n, 리뷰 n, 속도 상위 x%) |
| `/search` 취향 분석, Vibe 칩 | 결과 12개, 신작 섞임 | 결과 위에 토글 **"신작 포함"** (기본 꺼짐). 라벨: "출시 6개월 미만은 리뷰가 적어 정확도가 낮아요". 켜면 신작 카드에 `신작 · D+n` 뱃지 |
| `/game/[appId]` | GemBadge 70/80/90 | 생애주기 뱃지 + 근거 문장: 신작 "출시 D+40, 리뷰 18건 — 판단 보류 중" / 정착 "리뷰 420건 중 94% 긍정, 발굴지수 63" / 유명 "리뷰 4.2만 — 이미 검증된 게임" |
| 홈 | — | 섹션 3개를 랭킹 탭과 1:1 로: "묻힌 명작" / "요즘 뜨는" / "이번 분기 신작". 각 6개 |
| 뱃지 | GemBadge(70/80/90) | `히든젬`(established, 지수 ≥ 60, 리뷰 ≥ 30) / `주목`(45~60) / `떠오르는`(rising 상위 10%) / `신작`(new). 70/80/90 폐기 (D-13) |

문구 원칙: 신작에는 점수처럼 보이는 숫자를 붙이지 않는다. "판단 보류"를 그대로 보여준다. 그게 정직하고, 사용자가 신작을 클릭해
리뷰를 남기는 것이 이 사이트가 신작에 해주는 일이다.

## 5. 백엔드 선행 작업 (순서)
1. `review_refresh_log` → append-only 이력 테이블 `review_history(app_id, refreshed_at, total_reviews, positive)`.
   기존 행은 첫 스냅샷으로 이관. `refresh_reviews` 가 매 실행 INSERT. 주간 실행이면 4주 뒤부터 "요즘 뜨는"이 살아난다.
   (그 전까지 `rising` 탭은 "데이터 쌓는 중 — n주 후" 표시)
2. `lifecycle()` 헬퍼 + 응답 필드 + `include_new` 파라미터 + 캐시 키 (Day 1 스타일의 작은 커밋)
3. `GET /games/ranking` (3 type)
4. gem 전환(R-3) 시 `too_new`/`famous` 상태를 함께 넣는다
5. 프런트: 랭킹 탭 → 검색 토글 → 상세 뱃지 → 홈 섹션 순

## 6. 개발자가 정할 것
- 180일 / 20,000 경계 (내 기본값. 6개월은 스팀 "신작" 감각, 2만은 기존 무명도 cap 과 일치)
- 신작 토글 기본값: 꺼짐(내 판단 — 메인 품질 우선, 신작은 자기 탭이 있다)
- "떠오르는" 기준: 상대 증가율 상위 10% (절대 건수면 유명작이 독식)
- 홈 섹션 순서
