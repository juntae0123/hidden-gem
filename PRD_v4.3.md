# Hidden Gem - 제품 요구사항 문서 (PRD) v4.3

**최종 갱신: 2026-09-06 | v4.2.3(2026-05-25) → v4.3: 데이터 3배·추천 엔진 v7·발굴 지수 실측화·생애주기 분리·운영 자동화 반영**
**이전 버전: `docs/prd_history/PRD_v4.2.3.md` (2026-05-25, 11차 교차검증본 — 비전·수익·로드맵 원문 보존)**

> v4.2.3 은 "무엇을 만들 것인가"의 문서였다. v4.3 은 그중 **실제로 만들어져 측정된 것**과
> **측정 결과로 설계가 바뀐 것**을 반영한다. 바뀐 절: §2 현재 완성도, §4 추천 엔진(v5→v7),
> §5 데이터 스키마(실제 운영 스키마 추가), §6 로드맵. 비전·수익·모트(§1, §7~§13)는 유지.
> 근거 문서: `docs/decisions_0905.md`(R-1~R-19), `docs/system_invariants.md`(C-1~C-14), `docs/ablation_result_0905.md`(절제 실측).

---

## 0. 변경 이력

| 버전 | 핵심 변화 |
|------|----------|
| v3.0 | 추천 엔진 v3 구현 |
| v3.1 | Sentry + Discord 알람 |
| v3.2 | 추천 엔진 v5 + 24개 테스트 + 점수 시스템 재설계 |
| v4.0 | B2B 데이터 비즈니스 + Vibe Cluster 75개 추가 |
| v4.1 | 자기비판 (수익 보수화, Vibe 단계화) |
| v4.2 | 시니어 피드백 통합, 1인+AI 현실, 한국 메인+영미권 시드 |
| **v4.2.1** | **DRP + 분석 인프라 + 무가입 전략 + 번아웃 + 법무 + PMF 신호 보정** |
| v4.2.2~4.2.3 | 측정/절감/법적보호 미세 디테일 (2026-05-25) |
| **v4.3** | **교사-학생 증류로 12,843개 / 추천 엔진 v7(Core+발굴 분리) / gem 을 LLM 추정 → 리뷰 실측(Wilson×무명도)으로 교체 / 생애주기 분리·신작 리그 / 운영 DB 정합·주간 자동화 (2026-09-06)** |

---

## 1. 제품 비전

### Mission Statement
> "한국 인디 게임의 큐레이터로 시작해서,
> 글로벌 게임 의도 데이터 플랫폼이 된다."

### 진짜 정체성 선언
```
❌ "60개 지표로 게임 분류하는 사이트" (X)
❌ "B2B SaaS 게임 분석 도구"        (X)
❌ "글로벌 동시 진출 플랫폼"          (X, Year 1엔 환상)

✅ "한국 인디 게임 큐레이터" (Year 1)
✅ "Korea-discovered Hidden Gems" (Year 2+)
✅ "글로벌 게임 의도 데이터 플랫폼" (Year 3+)
```

### Business Model (3-Stage)
```
Year 1: B2C 검증 모드
  - 한국 MAU 5K~10K 목표
  - 어필리에이트 + 프리미엄 (소규모)
  - 행동 데이터 누적 (Vibe 검증)
  - PMF 검증 (재방문율 > 30%)
  - 수익 < $3K/월 (OK)

Year 2: B2B 베타 시작
  - 한국 MAU 30K + 영미권 시드 2K
  - 첫 B2B 베타 5곳 → 유료 전환 1-3곳
  - MRR $5K~$10K
  - Vibe Cluster 30개로 확장

Year 3+: 글로벌 본격
  - 한국 + 영미권 동시 운영
  - B2B 정식 출시 ($199~$999/월)
  - MRR $20K~$50K
  - Vibe Cluster 50-75개 자연 진화
```

### 타겟 유저
```
B2C Primary (Year 1):
  하드코어 한국 게이머 (취향 뚜렷, 새 게임 탐색)
  "이런 거 또 없나?" 캐주얼 게이머
  한국 인디 게임 팬

B2C Secondary (Year 2+):
  영미권 인디 게이머 (Korea-discovered 컨셉)
  한국 게임 관심 있는 글로벌 유저

B2B (Year 2+):
  Tier 1: 한국 인디 게임사 ($49~$199/월)
  Tier 2: 한국 진출 노리는 글로벌 (일본/중국) ($500~$1,500/월)
  Tier 3: 한국 시장 분석 컨설팅 ($999+/월)
  API: 디스코드 봇, 게임 미디어 ($49~$199/월)
```

---

## 2. 현재 완성도 (2026-09-06 기준)

서비스: https://hidden-gem-gold.vercel.app · API: Railway(FastAPI + Django + Postgres/pgvector + Redis)

### ✅ 데이터 — 4,190 → 12,843 (교사-학생 증류)
```
✅ 교사 4,190개  : GPT-5.4 Batch, 블라인드 입력(개발사·평점 숨김)
✅ 학생 8,653개  : gpt-5.4-mini + 12-shot 증류
   실측 단가      : $0.0049/요청 (Batch 50% × 프롬프트 캐시 90% 중복 적용, 대시보드 확인)
   품질 검증      : 홀드아웃 150쌍 지표 MAE 0.77 (49지표 교사급)
   폐기           : LLM 추정 gem_potential — 교사 대비 r ≈ -0.02, 사용 불가 판정
✅ 리뷰 실측      : 교사 코호트 전량 + 학생 코호트 수집, review_history/review_refresh_log 이력화
✅ 임베딩         : 1536차원 pgvector HNSW (ef_search 상향 + 폴백으로 후필터 굶주림 대응)
🔄 백필 진행 중   : 2026-03-16~06-05 출시 신작 (~7,500개 예상, 회차 500개 $2.45)
```

### ✅ 추천 엔진 — v5 → v7 (§4 참조)
```
✅ 경로 A (취향 문장/슬라이더): 질의 마스크 + 가중 RMSE → 가우시안 매치 87 + 발굴 12
✅ 경로 B (게임 기준 유사)     : 지표 60% + 임베딩 40% → 94 + 발굴 5
✅ 경로 C (시맨틱 검색)        : 임베딩 85% + LLM 힌트 15% → 94 + 발굴 5
✅ 발굴 지수 = Wilson 하한(z=1.96) × 무명도(log, 상한 2만, 지수 0.5) — 근거 없으면 NULL(폴백 없음)
✅ 생애주기 분리: 신작(≤180일) / 정착 / 유명(리뷰 2만+) / 출시예정 — 발굴은 정착작만
✅ 랭킹 3보드: steady / new(신작 리그) / rising + 조용한 신작 토글
✅ X-Factor 는 게이트로 격하 (절제 실측: 전체의 88.7%가 미달, 단독 정렬 시 리뷰 중앙 19,700)
```

### ✅ 측정·품질 인프라 (v4.2.3 에 없던 축)
```
✅ 절제(ablation) 도구: 항 하나씩 끄고 전체 풀 재정렬 → spearman·RBO·교사비율·리뷰중앙
✅ 스냅샷 회귀: 19 시나리오(취향 5 + 시맨틱 3 + 게임기준 + 랭킹 3보드 + 카나리아) s1~s7 diff
✅ 예측 먼저 기록 → 실측 → 틀린 예측 3건 보존(스케일 보정 / gem 전환 / 랭킹 속도 편향)
✅ pytest 36 통과 (점수 불변식·생애주기·랭킹 정렬·플래그 고정)
✅ 캐시 키에 로직 버전 포함: {CACHE_VERSION}-{SCORE_VERSION}-{GEM_SOURCE}
```

### ✅ 운영 (1인 운영 가능하게)
```
✅ 주간 파이프라인 자동화: 크롤 → 배치 → 적재 → 임베딩 → 리뷰 → 발굴지수 (월 03:30, Task Scheduler)
✅ 대상 DB 를 운영으로 고정(--target prod) + 시작 전 용량 게이트(70%) + Discord 알림
✅ 킬 스위치 2단: STOP_PIPELINE(전부) / STOP_BACKFILL(백필만)
✅ 운영 DB 정합 도구 prod_sync (app_id upsert 전용, 삭제 없음, 61분 → 85초)
✅ 비용 가드 $50/일·$5/시 + 대시보드 실측 보고 원칙
✅ 운영 사고 대응 기록: 볼륨 크래시(WAL)·마이그레이션 순서·참조 변수 재배포 → C-11~C-14 규칙화
```

### 🟡 진행 중
```
🟡 Google OAuth2 + JWT (Django·프론트 코드 완료, SocialApp 등록·테스트 남음)
🟡 Vibe Cluster (§3) — 보조축으로만 계획, 주축 승격은 실측 후
🟡 홈 3섹션 / 상세 페이지 발굴 배지
```

### 🔴 미구현
```
🔴 개인정보처리방침(한국어) + GDPR 삭제 API + 쿠키 동의
🔴 분석 인프라(PostHog/Plausible) — 현재 자체 UserAction 로그만
🔴 프롬프트 v2(앵커 분리 + 축 추가) — 전체 게임 균일 통과가 전제라 백필 완료 후 판단
🔴 R-4 노출 게이트 재검토 (리뷰 부족 신작의 노출 정책)
```

---

## 3. Vibe Cluster (Phase 2 핵심)

### 3-1. 단계적 진화 전략
```
Phase 2-A (Week 2-3): Macro Vibes 12개만
  자동 매핑 + 수동 검수 Top 200
  → UI/UX 검증 우선

Phase 3 (Month 2-3): 데이터 기반 Sub-Vibes 30개
  검색 패턴 분석 → 도출

Phase 4 (Month 6+): 50개로 확장
  트래픽 5K+ 확보 후

Year 2+: 75개 자연 도달
  유저 검증 + 커뮤니티 태깅
```

### 3-2. Macro Vibes 12개
```python
MACRO_VIBES = {
    # 감정 기반 (5)
    'cozy_escape':         '🌿 아늑한 도피',
    'emotional_journey':   '💧 감정적 여정',
    'cerebral_high':       '🧠 지적 쾌감',
    'visceral_thrill':     '⚡ 본능적 짜릿함',
    'meditative_flow':     '🌊 명상적 몰입',

    # 도전 기반 (3)
    'mastery_pursuit':     '⚔️ 숙련의 추구',
    'puzzle_obsession':    '🧩 퍼즐 집착',
    'survival_tension':    '🔥 생존 긴장',

    # 사회 기반 (2)
    'social_bonding':      '👥 사회적 유대',
    'competitive_edge':    '🏆 경쟁의 칼날',

    # 창작/탐험 (2)
    'creative_expression': '🎨 창작의 표현',
    'exploration_wonder':  '🌌 탐험의 경이',
}
```

### 3-3. 비용 계산
```
초기 구축:
  - Macro 12개 정의: 1-2시간 (Claude 협업)
  - 4,190개 자동 매핑: $0.50 (1회)
  - 수동 검수 Top 200: 100분
  - 분포 검증 + 재조정: 2시간
  → 총 6-8시간 (1.5일)

운영:
  - 신작 매핑: $0.0001/game
  - 검색 자동 분류: $10/월 (캐싱 시)
```

### 3-4. 검증 기준
```
분포 균형:
  - 각 vibe당 게임 50개+ 보장
  - 최대/최소 비율 < 10:1
  - 불균형 시 vibe 통합 또는 재정의

정확도 (Top 200 수동 검수):
  - Primary vibe > 80%
  - Secondary vibe > 60%
  - 미달 시 프롬프트 재조정 후 재실행
```

---

## 4. 추천 엔진 v7 (구현 완료, 2026-09-06)

v5(지표 60% + 임베딩 40% → 시그모이드)는 **경로 B/C 에 남아 있고**, 취향 입력 경로는 v7 로 교체했다.
교체 이유는 절제 실측이다: v5 의 X-Factor 항이 질의와 무관하게 유명작을 끌어올리고 있었다(단독 정렬 시 상위 20 의 교사 비율 0.90, 리뷰 중앙 19,700).

### 4-1. 세 경로 (하나만 고치면 안 된다 — C-8)
```
경로 A  취향 문장 / 49지표 슬라이더 / 스와이프   → score_v7
경로 B  이 게임과 비슷한 게임 (recommend_by_game) → 지표 60% + 임베딩 40% → 0~94 + 발굴 5
경로 C  시맨틱 검색 (semantic_search)            → 임베딩 85% + LLM 힌트 15% → 0~94 + 발굴 5
```

### 4-2. score_v7 — 취향 매칭과 발굴을 분리한다
```
질의 마스크: 사용자가 말하지 않은 축은 채점에서 제외한다 (말한 축만 본다)
거리        : 마스크된 축의 가중 RMSE
매치        : exp(-(d / 3.5)^2)              -> Core 87점
발굴        : gem_evidence 기반              -> 최대 12점
합계        : 0 ~ 99 (앵커 100은 기준 게임 전용)

설계 의도: "점수는 사용자의 취향/검색 문장에 따라 달라진다."
         고정된 '좋은 게임 순위'가 아니라, 말한 취향에 대한 거리다.
```

### 4-3. 발굴 지수 (gem_evidence) — LLM 추정에서 리뷰 실측으로
```
gem_evidence = Wilson 하한(긍정률, z=1.96) x 무명도(log 스케일, 상한 리뷰 2만, 지수 0.5)

- 근거 없음 = NULL. 중앙값·평균 폴백을 두지 않는다 (R-3). 0 과 NULL 을 구분한다.
- 대상은 정착작만. 신작은 리뷰가 쌓이기 전이라 발굴 점수를 주지 않는다(신작 리그로 분리).
- 유명작(리뷰 2만+)은 발굴 대상에서 제외 — 발굴의 정의상 무명도가 0이다.
- 전환 스위치 GEM_SOURCE=legacy|evidence (v6/v7/B/C/절제 도구가 모두 존중, 캐시 키에 포함)

폐기된 것: LLM 이 추정하던 gem_potential (교사 대비 r ≈ -0.02). 모델은 "숨은 명작"을 못 본다.
```

### 4-4. 생애주기 분리 (R-11 / R-16 / R-17)
```
upcoming  출시 예정
new       출시 180일 이내      -> 신작 리그에서 신작끼리 경쟁
established 그 외              -> 발굴 대상
famous    리뷰 20,000+         -> 발굴 제외

신작 리그 정렬(R-17): 누적 리뷰 수 desc, Wilson >= 0.70
  속도(velocity) 정렬은 D+3~16 에 편향돼 카나리아(메챠 카멜레온)를 1위에서 떨어뜨렸다 -> 폐기
조용한 신작(리뷰 <100): 별도 토글, Wilson 우선(>= 0.35)
```

### 4-5. 4단계 가중치 (경로 B 유지)
```python
W_PRIMARY    = 5.0  # 관련 (3~5개)
W_SECONDARY  = 2.0  # 연관 (5~8개)
W_NEUTRAL    = 0.5  # 공통
W_IRRELEVANT = 0.1  # 나머지
# 변별력: 25 vs 3.5 -> 7배
```

### 4-6. score_breakdown 응답 (v7)
```json
{
  "core_score": 81.4,
  "gem_score": 7.4,
  "gem_source": "evidence",
  "gem_evidence": 61.7,
  "xfactor": 0,
  "lifecycle": "established",
  "final_score": 88.8
}
```
경로 B/C 는 키 이름이 다르다(`metric_score`/`embedding_score`/`gem_bonus`) — 프런트·측정 도구가 세 경로를 각각 읽는다 (C-8).

---

## 5. 데이터 스키마

### 5-0. 실제 운영 스키마 (2026-09 현재, 위 계획 테이블과 구분)
```sql
-- games: 기본 정보 + 상태
--   is_analyzed / analysis_method('teacher'|'fewshot_5.4based'|'pending') / is_active
--   is_active=FALSE 는 '삭제'가 아니라 노출 게이트 미달. 데이터는 절대 지우지 않는다 (C-1)

-- game_metrics: 60개 지표 + 발굴 지수
ALTER TABLE game_metrics ADD COLUMN
  gem_evidence            FLOAT,        -- Wilson 하한 x 무명도. 근거 없으면 NULL
  gem_evidence_updated_at TIMESTAMP,
  gem_evidence_reason     VARCHAR(50);  -- ok / too_new / insufficient / no_reviews / famous

-- 리뷰 이력 (주간 갱신)
CREATE TABLE review_history     (game_id, review_count, positive_ratio, checked_at);
CREATE TABLE review_refresh_log (game_id, refreshed_at, status);
```
분포(12,843건 기준): ok 3,219(전부 교사) / famous 970 / too_new 5,246(학생) / insufficient 1,701 / no_reviews 1,707.


### 5-1. UserAction (Phase 3 확장)
```sql
ALTER TABLE user_actions ADD COLUMN
  referrer VARCHAR(200),
  user_agent_hash VARCHAR(64),
  country_code VARCHAR(2),
  hour_of_day INTEGER,
  day_of_week INTEGER,
  session_position INTEGER,
  time_since_prev_action INTEGER;
```

### 5-2. GameVibeFingerprint (Phase 2-A)
```sql
CREATE TABLE game_vibe_fingerprints (
  game_id INTEGER PRIMARY KEY REFERENCES games(id),
  primary_vibe VARCHAR(50),
  primary_score FLOAT,
  secondary_vibe VARCHAR(50),
  secondary_score FLOAT,
  vibe_distribution JSONB,
  confidence FLOAT,
  manual_verified BOOLEAN DEFAULT FALSE,
  updated_at TIMESTAMP
);
```

### 5-3. UserVibeProfile (Phase 3)
```sql
CREATE TABLE user_vibe_profiles (
  user_id INTEGER PRIMARY KEY REFERENCES users(id),
  vibe_vector JSONB,
  primary_persona VARCHAR(50),
  secondary_persona VARCHAR(50),
  activity_pattern JSONB,
  confidence FLOAT,
  updated_at TIMESTAMP
);
```

### 5-4. DailyMetric (B2B 집계)
```sql
CREATE TABLE daily_metrics (
  date DATE,
  game_id INTEGER REFERENCES games(id),
  search_count INTEGER,
  detail_view_count INTEGER,
  steam_click_count INTEGER,
  like_count INTEGER,
  ctr_detail_to_steam FLOAT,
  unique_sessions INTEGER,
  PRIMARY KEY (date, game_id)
);
```

---

## 6. 로드맵

### Phase 1 ✅ 완료
### Phase 1.7 ✅ 완료 (2026-06~09, v4.2.3 이후 실제로 한 것)
```
✅ 교사-학생 증류로 데이터 3배 (4,190 -> 12,843)
✅ 추천 엔진 v7 + 발굴 지수 실측화 + 생애주기 분리 + 신작 리그
✅ 절제·스냅샷 측정 체계 + pytest 36 + 불변식 문서 C-1~C-14
✅ 운영 DB 정합(prod_sync) + 주간 파이프라인 자동화 + 용량 게이트 + 킬 스위치
```

### Phase 1.6 🔴 남음 (보안 + 법무 + 분석 인프라)
```
- Google OAuth 동작 확인 / Axios 토큰 자동 갱신 / 로그아웃 블랙리스트
- CORS 도메인 제한
- 개인정보처리방침(한국어) + GDPR 데이터 삭제 API + 쿠키 동의
- PostHog 또는 Plausible 도입
※ 트래픽을 받기 전에 끝내야 하는 유일한 블로커. 데이터·엔진보다 우선순위가 높다.
```

### Phase 2-A 🟡 Week 2-3 (Vibe Cluster)
```
Week 2: Macro Vibe 12개 정의 + 4,190 자동 매핑
Week 3: 수동 검수 + Vibe 추천 API + 사용자 테스트
```

### Phase 2-B 🟡 Week 4-5 (Steam + 온보딩)
```
Week 4: Steam OpenID + 라이브러리 분석
Week 5: 스와이프 온보딩 (10개 게임)
```

### Phase 2-C 🔥 Week 6-7 (DNA + 첫 마케팅)
```
Week 6: 취향 DNA 카드 + SNS 공유
Week 7: 한국 마케팅 시드 + 영미권 시드 (AI 협업)
```

### Phase 3 📈 Week 8-12 (트래픽 확보)
```
한국 70% / 영미권 20% / 분석 10%
목표: Month 3 한국 MAU 500-1000
```

### Phase 4 💰 Month 4-6 (B2B 베타)
```
한국 인디 5곳 무료 베타 → 1-3곳 유료 전환
```

### Phase 5 🌍 Year 2 (글로벌)
```
조건: Year 1 MAU 10K+ + MRR $3K+ 달성
영미권 본격 진출
```

---

## 7. 시간 배분 + 마케팅 SLA

### 매일 (평일)
```
오전 4시간: 코딩 + AI 협업
저녁 1.5시간: 한국 마케팅
밤 1시간: 영미권 시드 (AI 활용)
밤 0.5시간: 데이터 분석
```

### 주말
```
풀 마케팅 모드 + 콘텐츠 일괄 생산
일요일: 무조건 휴식
```

### 마케팅 운영 SLA (지속 가능 수준)
```
한국 채널 (활동량):
  - 디시 게임갤: 일 1-2건, 주 5-10건
  - 루리웹: 주 3-5건
  - 한국어 블로그: 주 2-3편
  - 일요일: 무조건 휴식

측정 방법 (NEW):
  - Notion 데이터베이스 (날짜/플랫폼/링크/반응/클릭수)
  - 매주 금요일 마케팅 회고에 자동 집계
  - 클릭 추적: bit.ly 단축 URL (무료, 통계 무제한)
  - PostHog UTM 파라미터 추적
    예: ?utm_source=dcinside&utm_campaign=game_recommend
  - 채널별 ROI 계산 (시간 투입 vs MAU 증가)

영미권 (AI 협업):
  - r/PatientGamers: 주 1회
  - r/IndieGaming: 주 1회
  - Indie Hackers: 월 2회

품질 기준:
  - 답글: 게임 추천 질문 글에만 (스팸 X)
  - 사이트 링크: 본문 X, 답글에서만 자연스럽게
  - 같은 사이트 링크: 일 1회 제한
  - "자연스러움 체크": AI에 검수 의뢰

백업 계정 전략:
  - 디시: 3개 계정 (활동 분산, 정지 위험)
  - 루리웹: 2개 계정
  - Reddit: 1개 (활동 기록 누적, 다중 X)

정지 대응:
  - 계정 정지 시 즉시 백업 계정 전환
  - 사이트 노출 안 함, "추천 글만"
  - 1주일 활동 후 자연스럽게 사이트 언급
```

---

## 8. KPI

### B2C 추천 품질
```
- 시맨틱 검색 CTR > 40%
- Steam 클릭률 > 20%
- 검색 실패율 < 10%
- p95 응답시간 < 500ms
- 재방문율 > 30% (PMF 핵심)
```

### 마일스톤
```
Week 1:  Vibe Macro 12개 + 매핑 정확도 검증 (Top 100)
Week 2:  Vibe 칩 UI 클릭률 측정 시작
Month 1: 디시/루리웹 첫 게시물 → 트래픽 추적
Month 2: 재방문율 > 20% 달성
Month 3: 한국 MAU 500 + 행동 로그 5만 건
Month 6: 한국 MAU 5,000 + 첫 B2B 베타 1곳
Month 9: 한국 MAU 10,000 + 영미권 500
Month 12: MAU 20,000 + MRR $1K-$3K
```

### Vibe Cluster 품질
```
- 분포 균형 (최대/최소 < 10:1)
- 각 Vibe당 50개+ 게임
- 수동 검수 정확도 > 80%
- Vibe 칩 클릭률 > 15%
```

### 비용 효율
```
- OpenAI 일일 < $50
- 캐시 적중률 > 70%
- 검색당 평균 < $0.002
- 인프라 비용 < $50/월 (Year 1)
```

### B2B (Phase 4+)
```
- 첫 베타 5곳 (Month 4)
- 첫 유료 1곳 (Month 6)
- MRR $1K (Month 9)
- MRR $5K (Month 12)
- 유지율 > 80% (3개월)
```

---

## 9. 수익 시나리오

### 보수
```
Year 1: $500~$1K/월
Year 2: $3K~$5K/월
Year 3: $10K/월
Year 4: $25K/월
Year 5: $50K+/월
```

### 현실 (기준점)
```
Year 1: $1K~$3K/월
Year 2: $10K~$15K/월
Year 3: $25K~$40K/월
Year 4: $60K/월
Year 5: $100K+/월
```

### 낙관
```
Year 1: $3K~$7K/월
Year 2: $20K~$30K/월
Year 3: $50K+/월
Year 4: $100K+/월
Year 5: $200K+/월
```

---

## 10. PMF 검증 신호 (수정됨)

### Month 3 PMF 검증 신호

#### 🟢 좋음 (계속 진행)
```
- 한국 MAU 500+
- 재방문율 25%+
- 검색 → Steam 클릭률 15%+
- 디시/루리웹 자발적 언급 1건+
```

#### 🟡 중간 (마케팅 강화)
```
- MAU 200~500
- 재방문율 15~25%
- → Pivot X, 마케팅 채널 추가
- 유튜버 협업 시도
- 한국 게임 미디어 시도
```

#### 🔴 안 좋음 (Pivot 검토)
```
- MAU < 100 (한 달 마케팅 후에도)
- 재방문율 < 10%
- Steam 클릭률 < 5%
- → 그제야 Pivot 옵션 검토
```

### Pivot 옵션
```
Option A: "한국 인디 전용"으로 좁힘
  - 4,190개 → 500개 한국 인디만
  - "Hidden Gem 한국 인디관" 정체성
  - 한국 인디 개발자 직접 영업

Option B: B2B 우선 진출
  - B2C 트래픽 안 모이면 B2B 직접 영업
  - 한국 게임사 5곳 직접 만남
  - 첫 유료 1곳 빠르게 확보

Option C: 데이터 자체 판매
  - 4,190개 60개 지표 데이터셋
  - SteamSpy 한국판 포지션
  - 한국 데이터 라이선스 ($99~$499)

Option D: 마케팅 채널 변경
  - 디시/루리웹 → 유튜브 협업 집중
  - 한국 게임 미디어 (인벤, 게임메카)
```

---

## 11. 진짜 모트

### 1. "한국 인디 큐레이터" 정체성 (Year 1)
```
- 1인 운영자의 진정성
- 한국 게이머와 직접 소통
- 한국 인디 개발자 우대 알고리즘
- 한국 시장 1년 누적 신뢰
→ 카피 6개월+ 필요
```

### 2. Hidden Gem Discovery Algorithm
```
- 인지도 역수 + 품질 + 개성
- 1년 누적 정확도
- 한국어 리뷰 가중치
→ 알고리즘 공개돼도 데이터 카피 불가
```

### 3. Community Validation (Network Effect)
```
- 유저가 "Vibe 맞아요" 직접 투표
- AI 매핑 정확도 ↑
- Crowd-sourced ground truth
→ 카피 회사가 유저 가져가야 함
```

### 4. AI 협업 효율 (1인의 5배)
```
- 코드 5배 빠름
- 영어 콘텐츠 5배 빠름
- 결정 검증 5배 빠름
→ 다른 회사보다 Phase 1-4 빠르게 도달
```

---

## 12. 법적/사업적 리스크

| 리스크 | 심각도 | 대응 | 시점 |
|--------|--------|------|------|
| Steam CDN 핫링킹 | 🟡 | Cloudflare Images | Phase 4 |
| 게임 설명 저작권 | 🟡 | AI 생성 요약만 | 완료 ✅ |
| Steam API ToS | 🔴 | 법무 검토 | Phase 1.6 |
| 개인정보 (PIPA/GDPR) | 🔴 | 처리방침 + 삭제 API | Phase 1.6 |
| OpenAI 비용 폭탄 | ✅ | cost_guard.py | 완료 ✅ |
| GPT 할루시네이션 | 🟡 | 리뷰 병합 + confidence | Phase 2-A |
| Reddit AI 의심 | 🟡 | AI 초안 + 너 개성 30% | Phase 3 |
| B2B 데이터 유출 | 🔴 | 익명화 + 표본 500+ | Phase 4 |
| B2B 부정확 인사이트 | 🔴 | 통계 유의성 (p<0.05) | Phase 4 |
| 1인 번아웃 | 🟡 | 주 1일 휴식 + 신호 모니터링 | 상시 |

---

## 13. 기술 스택

| 구분 | 현재 | Phase 2-A | Phase 3-4 | Year 2+ |
|------|------|-----------|-----------|---------|
| 백엔드 | FastAPI + Django ✅ | + Celery | + Airflow | - |
| DB | PostgreSQL + pgvector ✅ | + Redis ✅ | + Materialized Views | + ClickHouse |
| AI | GPT-5.4, embed-3 ✅ | + GPT-4.1-mini | + Vibe Classifier | + 자체 검토 |
| 프론트 | Next.js 16.2.6 ✅ | + PWA | + 모바일 앱 | - |
| 인증 | Google OAuth + JWT 🟡 | + Steam OpenID | + Apple Sign In | - |
| 모니터링 | Sentry ✅ | + PostHog | + Grafana | - |
| 분석 | - | PostHog Free | + Metabase | + 자체 |
| 배포 | 로컬 Docker | Vercel + Railway | + AWS (B2B) | - |

---

## 14. 1인 + AI 협업 원칙

### 코딩
```
- Claude로 풀코드 작성 → 통합/검수
- Gemini로 코드 리뷰
- Opus로 아키텍처 검증
- 효율: 일반 1인의 5배
```

### 마케팅
```
한국어: 너가 100% 작성 (진정성 핵심)
영어: AI 초안 + 너의 개성 30%
"Korea-discovered" 컨셉 강조
```

### 데이터 분석
```
- AI로 SQL/차트 생성
- 너는 인사이트 판단
- PostHog 자체 대시보드 활용
```

### 법무/회계
```
- 표준 약관 + 1회 변호사 검토 ($300)
- 회계 외주 ($50/월)
- 사이버 보안 보험 (Phase 4)
```

---

## 15. 배포 체크리스트 (Phase 1.6)

### 보안
```
☑ OpenAI 비용 가드 ✅
☑ Rate Limiting ✅
☑ Sentry ✅
☑ Discord 알람 ✅
☐ Google OAuth 동작 확인
☐ Axios 토큰 자동 갱신
☐ 로그아웃 토큰 블랙리스트
☐ CORS 도메인 제한
☐ httpOnly 쿠키 (선택)
```

### 안정성
```
☑ DB 백업 cron ✅
☑ 핵심 테스트 24개 ✅
☐ Disaster Recovery 절차 (Section 18)
☐ 복구 훈련 (분기 1회)
☐ 환경변수 전체 확인 (.env.production)
```

### 법적
```
☐ 개인정보처리방침 (한국어)
☐ 이용약관
☐ 쿠키 동의 배너
☐ 데이터 삭제 API (GDPR Article 17)
☐ Steam API ToS 검토
☐ 변호사 1회 상담 ($150)
```

### 분석 인프라
```
☐ PostHog 또는 Plausible 도입
☐ 펀널 분석 설정
☐ 리텐션 추적
☐ Vibe 칩 커스텀 이벤트
```

### 마케팅 준비
```
☐ 디시인사이드 계정 3개
☐ 루리웹 계정 2개
☐ Indie Hackers 프로필
☐ Reddit 계정 (활동 기록 누적)
☐ Hidden Gem 트위터/스레드
☐ 한국어 블로그 시작
```

---

## 16. Disaster Recovery Plan (DRP) ⭐ NEW

### 백업 다층화
```
매일 03:00 - 로컬 백업 (PostgreSQL)
매주 일요일 04:00 - S3 업로드 (예정)
매월 1일 - 별도 디스크 복사 (외장 SSD)

보관 정책:
  일별: 30일
  주별: 12주
  월별: 6개월
```

### 재난 시나리오별 복구
```
시나리오 1: Docker 컨테이너 손실
  복구: docker-compose up -d
  데이터: postgres_data 볼륨 유지됨
  소요: 5분

시나리오 2: 디스크 손실
  복구: 최근 백업 → 새 디스크 복원
  pg_restore < backup_YYYYMMDD.sql.gz
  소요: 30분

시나리오 3: 실수로 DELETE
  복구: 어제 백업으로 부분 복원
  특정 테이블만 복원 가능
  소요: 15분

시나리오 4: Cloud 계정 정지
  복구: 다른 클라우드로 이전
  Docker 이미지 + S3 백업 활용
  소요: 2-4시간
```

### 복구 절차 (테스트 완료 기준)
```bash
# 1. PostgreSQL 복구
docker exec -i hidden_gem_db psql -U juntae -d hidden_gem_db < backup.sql

# 2. Redis 복구 (캐시만이라 재구축)
docker restart hidden_gem_redis

# 3. Sentry 복구
# 새 프로젝트 생성 → DSN 교체 → .env 업데이트

# 4. 동작 확인
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/games/stats/overview
```

### 분기 1회 복구 훈련
```
실제 모의 재해 실행:
1. 테스트 DB 만들어서 백업 → 복원
2. 백업 → 동작 확인까지 1시간 안 가능 검증
3. 절차 문서 업데이트
4. 부족한 부분 자동화 추가
```

### 백업 무결성 자동 검증 (매주 일요일) ⭐ NEW
```bash
# scripts/backup/verify_backup.sh
# 매주 일요일 04:30 자동 실행

LATEST_BACKUP=$(ls -t /backup/*.sql.gz | head -1)

# 1. 압축 무결성 검사
gzip -t "$LATEST_BACKUP" || {
  curl -X POST $DISCORD_WEBHOOK -d "🚨 백업 파일 손상: $LATEST_BACKUP"
  exit 1
}

# 2. pg_restore --list로 구조 검증
gunzip -c "$LATEST_BACKUP" | pg_restore --list > /tmp/backup_toc.txt || {
  curl -X POST $DISCORD_WEBHOOK -d "🚨 백업 복원 불가: $LATEST_BACKUP"
  exit 1
}

# 3. 테이블 수 검증 (정상: 20개+)
TABLE_COUNT=$(grep -c "TABLE DATA" /tmp/backup_toc.txt)
if [ $TABLE_COUNT -lt 20 ]; then
  curl -X POST $DISCORD_WEBHOOK -d "⚠️ 백업 테이블 수 비정상: $TABLE_COUNT"
fi

# 4. 성공 알람
curl -X POST $DISCORD_WEBHOOK -d "✅ 백업 무결성 검증 완료: $LATEST_BACKUP ($TABLE_COUNT 테이블)"
```

---

## 17. 분석 인프라 ⭐ NEW

### Tier 1: 무료 도구 (Phase 1-3)

#### PostHog Cloud Free (1순위 권장)
```
- 1M 이벤트/월 무료 (Year 1에 충분)
- 펀널 분석, 리텐션
- 세션 리플레이
- A/B 테스트 (Phase 2+)
- 자체 호스팅 가능 (Year 2+ 데이터 양 시)
```

#### Plausible Analytics ($9/월)
```
- 프라이버시 친화적 (쿠키 X)
- GA보다 가벼움
- GDPR 자동 준수
- 대시보드 간결
```

#### 자체 행동 로그 (이미 있음)
```
- UserAction 테이블 ✅
- daily_metrics 집계 (Phase 3)
- Vibe 분포 SQL 쿼리
```

### Tier 2: Phase 4+ (B2B 출시 후)

#### Metabase (자체 호스팅, 무료)
```
- 대시보드 + SQL 쿼리
- B2B 고객용 리포트
- 자동 스케줄링
```

#### Mixpanel ($25/월)
```
- 코호트 분석
- A/B 테스트 본격
- 푸시 통합
```

### 측정 우선순위
```
1. MAU/DAU: PostHog 자동
2. 재방문율: 자체 로그 (session_id)
3. CTR: UserAction (rec_click / search_click)
4. Steam 클릭률: UserAction (steam_click)
5. Vibe 칩 클릭: PostHog 커스텀 이벤트
6. 펀널: 메인 → 게임 상세 → Steam 클릭
7. 리텐션: 1일/7일/30일
```

### 이벤트 정의 (PostHog)
```javascript
// 페이지 진입
posthog.capture('$pageview')

// 검색
posthog.capture('search', { query: '...', count: 12 })

// Vibe 칩 클릭
posthog.capture('vibe_chip_click', { vibe: 'cozy_escape' })

// 게임 상세
posthog.capture('game_view', { app_id: 1086940 })

// Steam 클릭
posthog.capture('steam_click', { app_id: 1086940, score: 87 })
```

### 지역별 자동 처리 (GDPR/PIPA/CCPA) ⭐ NEW
```typescript
// src/lib/analytics.ts

async function initAnalytics() {
  // 1. IP 기반 지역 감지 (Cloudflare 헤더 또는 API)
  const country = await detectCountry();  // 'KR', 'US', 'DE' 등

  // 2. 지역별 처리 분기
  if (EU_COUNTRIES.includes(country)) {
    // EU: GDPR — 명시적 옵트인 필수
    if (!hasConsent('eu_analytics')) {
      showConsentBanner('eu');  // 강제 배너
      return;  // 동의 전엔 추적 X
    }
    posthog.init({ ..., opt_out_capturing_by_default: false });
  }
  else if (country === 'KR') {
    // 한국: PIPA — 약관 동의로 충분 (가입 시 처리)
    posthog.init({ ... });
  }
  else if (country === 'US') {
    // 미국: CCPA — 옵트아웃 링크 제공
    posthog.init({ ... });
    showCCPAOptOutLink();  // 하단 푸터에 "Do Not Sell" 링크
  }
  else {
    // 기타: 기본 옵트인
    posthog.init({ ... });
  }
}

const EU_COUNTRIES = ['DE', 'FR', 'IT', 'ES', 'NL', 'BE', 'AT', 'PL', /* ... */];
```

---

## 18. 무가입 유저 전략 ⭐ NEW

### 비로그인 유저도 100% 핵심 기능 사용
```
✅ 검색 (이미 됨)
✅ 추천 (이미 됨)
✅ 게임 상세 (이미 됨)
✅ 행동 로그 수집 (session_id로)
```

### 가입 유도 시점 (Soft Push)
```
5번째 게임 상세 진입 시:
  배너: "가입하면 이 게임들 저장됩니다"
  강제 X, 닫기 가능

10번째 검색 시:
  모달: "내 취향 분석 → 맞춤 추천 받기"
  스킵 가능

DNA 카드 만들 때:
  자연스러운 가입 요구
  "공유하려면 가입 필요"

찜하기 시도:
  로그인 모달 (자연스러움)
```

### 가입 안 하는 이유 측정
```
- 가입 페이지 진입 → 이탈 추적 (PostHog)
- 가입 페이지 이탈률 > 70%면 UI 재검토
- 가입 버튼 클릭 → 가입 완료 펀널
```

### 데이터 수집은 가입 무관
```
- session_id 영구 추적 (localStorage)
- 비로그인도 vibe 학습 가능 (Phase 3)
- 가입 시 session_id → user_id 머지
- "비로그인 행동 + 가입 시 통합" 자연스러움
```

### 1인 SaaS 평균 전환율 (참고)
```
100명 방문 → 70명 둘러봄 → 5명 가입 → 2명 온보딩
PMF 검증된 SaaS: 5% (가입) → 50% (온보딩 완료)
PMF 안 된 SaaS: 1-2% (가입) → 20% (이탈)

목표: Month 6까지 가입 전환율 3%+ 달성
```

---

## 19. 번아웃 방지 프로토콜 ⭐ NEW

### 신호 모니터링 (주 1회 자가 체크)
```
☐ 코딩 6시간 이상 = 정상
☐ 마케팅 1.5시간 = 정상
☐ 잠 7시간 이상
☐ 운동 주 2회
☐ 가족/친구 만남 주 1회

3개 이상 X → 다음 주 워크로드 50% 감소
5개 이상 X → 1주일 강제 휴가
```

### 강제 휴식 규칙
```
일요일: 코딩 절대 금지 (마케팅도 X)
18:00 이후: 큰 결정 안 함 (코드 변경 X)
분기 1주일: 완전 휴가 (PRD 결정도 미룸)
연 2주: 장기 휴가 (여행)
```

### 정기 회고
```
매주 금요일 30분:
  - 이번 주 성공 / 실패
  - 다음 주 우선순위 1개만 (3개 X)
  - AI 협업 효율 점수 (1-10)

매월 마지막 일요일 1시간:
  - 1개월 KPI 리뷰
  - PRD 수정 필요 여부
  - 번아웃 신호 체크
  - 다음 달 1순위 결정
```

### Day 1 회고 템플릿 (Notion/Obsidian)
```
매일 22:00 5분 회고:
- 오늘 한 것: (구체적)
- 오늘 막힌 것: (해결책 + AI 도움)
- 내일 1순위: (1개만)
- AI 협업 효율: (1-10점)
- 컨디션: (😊/😐/😫)

→ 1주일 후 패턴 분석
```

### 위험 신호 (즉시 대응)
```
🚨 다음 중 1개라도:
  - 잠 5시간 이하 3일 연속
  - 코딩 10시간+ 매일
  - 마케팅 글 의무감으로만
  - "그만하고 싶다" 생각 주 3회+
  - 식사/운동 무시

→ 즉시 3일 휴식 + 우선순위 재설정
```

### AI 의존 번아웃 (1인+AI 특유의 위험) ⭐ NEW
```
신호:
  - 코드 작성 전 무조건 AI에 물어봄
  - AI 응답 없으면 진행 못 함
  - 자신감 하락 ("내가 한 게 맞나?")
  - 직접 디버깅 능력 약화
  - 작은 함수도 직접 못 짬
  - AI 답변을 무비판적으로 수용

체크 질문 (주 1회 자가 진단):
  - 오늘 AI 없이 코딩한 시간이 있나?
  - AI 답변에 "이상한데?"라고 의심한 적 있나?
  - 작은 버그 직접 디버깅했나?

대응 프로토콜:
  - 주 1회 "AI 없이 코딩 데이" (수요일 권장)
    → 작은 기능 1개를 직접 짜기
    → 디버깅도 직접
    → 답답해도 30분은 혼자
  
  - AI 응답 비판적 검증 습관:
    → 풀코드 받으면 5분간 직접 읽기
    → "이거 왜 이렇게 짰지?" 1개 질문 만들기
    → 실행 전 의도 다시 확인
  
  - 작은 작업은 직접:
    → 100줄 미만 = 직접 시도 (막히면 AI)
    → 100줄 이상 = AI 협업 OK

근본 원칙:
  AI는 동료지 부모가 아니다.
  내가 결정하고 AI가 도와주는 거지,
  AI가 결정하고 내가 따라가는 게 아니다.
```

---

## 20. 법무 체크포인트 ⭐ NEW

### Phase 1.6 (이번 주)
```
한국 변호사 30분 상담 ($150):
☐ 개인정보처리방침 검토
☐ Steam API 사용 ToS 위반 여부
☐ 디시/루리웹 마케팅 위법 여부
☐ AI 생성 콘텐츠 저작권
☐ 어필리에이트 표시 의무

→ 변호사 추천: 스타트업 전문 변호사 (로톡, 헬프미)
```

### Phase 4 (B2B 출시 전)
```
한국 변호사 본격 검토 ($500):
☐ B2B 계약서 템플릿
☐ 데이터 제공 약관
☐ 라이센스 명시
☐ 환불 정책
☐ 분쟁 해결 조항

세무 처리 (별도 ⭐ NEW):
☐ 부가가치세(VAT) 처리:
  - 한국 B2B는 자동 면세 X (10% VAT 부과)
  - 매출 8천만원/년 초과 시 일반과세자 전환
  - 그 전엔 간이과세자 (4% VAT)
☐ 세금계산서 발행 시스템
  - 홈택스 전자세금계산서 ($0)
  - 또는 Stripe Tax 한국 ($50/월)
☐ 외화 매출 처리 (영미권 B2B)
  - Stripe Atlas + 국내 사업자 병행
  - 원천징수 + 부가세 처리
☐ 회계사 (월 결산 외주):
  - 비용 $50~$100/월
  - 매출 1천만원 이상 시 필수
```

### Phase 5 (영미권 진출)
```
미국 변호사 1회 상담 ($300):
☐ GDPR 준수 검토
☐ CCPA (캘리포니아)
☐ 미국 세금 (W-9, 1099)
☐ 미국 사업자 등록 필요 여부
☐ 결제 처리 (Stripe Atlas)
```

### 분기 1회 점검 (자체)
```
☐ 개인정보처리방침 최신화
☐ 이용약관 변경 사항
☐ Steam API ToS 업데이트 확인
☐ 새로운 법규 (PIPA 개정 등)
```

---

## 21. 마케팅 채널 확장 옵션 (Phase 3+)

### 한국 게임 미디어 (시도)
```
인벤 게임뉴스:
  - 콜드메일 ($0)
  - "한국 인디 게임 큐레이션 사이트" 보도자료
  - 성공률 10-20%

게임메카:
  - 인터뷰 요청
  - "1인 + AI로 만든 게임 추천" 스토리
  - 성공 시 트래픽 +500-1,000

디스이즈게임:
  - 인디 게임 기획 기사
  - "Hidden Gem이 발굴한 한국 인디 10선"
  - 게임사 협업 가능
```

### 유튜브 협업 (효과 큼)
```
타겟 채널 (구독자 5K~50K):
  - 한국 인디게임 리뷰
  - 게임 추천 채널
  - 게임 큐레이터

협업 방식:
  - "Hidden Gem이 추천한 게임" 영상
  - 무료 제공 + 영상 노출
  - 1편 = 트래픽 1,000-5,000
```

### 한국 컨퍼런스 (Year 2)
```
NDC (Nexon Developers Conference): 매년 4월
BIC (Busan Indie Connect): 매년 9월
KGC (Korea Game Conference): 매년 11월

발표 신청:
  - "1인 + AI로 만든 게임 추천 플랫폼"
  - "한국 인디 게임 발굴 알고리즘"
  - 인지도 + 인디 개발자 네트워크
```

### Steam 큐레이터
```
- "Hidden Gem 큐레이터" 운영
- 매주 게임 5개 추천
- 위시리스트 추가 → Steam 매출 영향
- 무료 트래픽 도구
```

### ❌ 피해야 할 채널 (자원 낭비) ⭐ NEW
```
페이스북 광고:
  - 게임 추천 CPC 매우 비쌈 ($2~$5/클릭)
  - 전환율 1% 미만
  - 한국 게이머 페이스북 활동 적음
  → Year 2까지 시도 X

인스타그램:
  - 게임 콘텐츠 도달률 낮음 (3%)
  - 비주얼 우선 플랫폼 (텍스트 추천 부적합)
  - 해시태그 효과 미미
  → 부수적 채널로만 (메인 X)

네이버 카페 (게임 카페):
  - 가입 어려움 (등업 시스템)
  - 광고 신고 시 영구 차단
  - 1인이 운영하기 부담
  → 시도하지 말 것

유튜브 댓글 스팸:
  - 즉시 신고당함
  - 채널 신뢰 하락
  → 절대 금지

카카오톡 오픈채팅:
  - 효과 미미
  - 스팸 인식
  - 시간 대비 ROI 낮음
  → 시도 X

TikTok:
  - 게임 추천에 너무 짧음 (15초)
  - 한국 게이머 활동 적음
  - 영상 제작 시간 부담
  → Year 2+ 검토

LinkedIn:
  - B2C 게임과 무관
  - B2B는 가능하나 비효율
  → Phase 4 B2B에만

클럽하우스:
  - 서비스 자체가 죽어감
  → 절대 시도 X
```

---

## 22. AI Cost 모니터링 강화 (Phase 2-A)

### Vibe 매핑 후 비용 보정
```
일일 한도: $50 → $30 (보수적)
시간당 한도: $5 → $3

비용 구성 (예상):
  - 시맨틱 검색 GPT: $0.001~$0.005/검색
  - 임베딩: $0.0001/검색
  - Vibe 매핑 (1회): $0.50
  - 신작 매핑: $0.01/일
```

### 비상 트리거
```
일일 비용 $20 초과 → Discord 알람 (경고)
일일 비용 $25 초과 → 신규 API 호출 차단
시간당 $3 초과 → Discord 알람
시간당 $5 초과 → 30분 차단

복구 조건:
  - 비용 정상화 + 자동 차단 해제
  - Discord에 정상화 알람
```

### 비용 절감 전략
```
1. 캐시 적극 활용 (이미 됨)
2. 시맨틱 검색 GPT → 키워드 추출만
3. 임베딩은 1회 생성 후 저장
4. 신작 매핑은 일괄 배치 (주 1회)
```

---

## 23. 성공 후의 위험 ⭐ NEW (PRD 마지막 인사이트)

### "실패보다 성공이 무서울 수 있다"

유저 10,000+ 모이면 새로운 문제 시작.
이걸 미리 인지하고 있어야 함.

### 위험 시나리오별 대비

#### 시나리오 1: 인프라 비용 폭증
```
유저 1,000명 → 인프라 $50/월
유저 10,000명 → $500/월 (10배)
유저 50,000명 → $2,000/월 (40배)

원인:
  - PostgreSQL 디스크 + IOPS
  - Redis 메모리
  - OpenAI API 호출
  - Cloudflare/S3 트래픽

대비 (Month 6에 자동 알람):
  - 인프라 비용 $100+/월 → Discord 알람
  - $300+/월 → 긴급 비용 절감 검토
  - $500+/월 → 유료 전환 가속 또는 인프라 최적화

비용 절감 Action Plan (우선순위 NEW):
  1순위: Redis 캐시 TTL 늘리기 (1h → 6h)
         - 적중률 70% → 85% 예상
         - OpenAI 비용 50% 감소
         - 1시간 작업, 즉시 효과
  
  2순위: OpenAI 임베딩 DB 캐시
         - 같은 쿼리 임베딩 재사용
         - text_embedding_cache 테이블
         - 4시간 작업, 임베딩 비용 70% 감소
  
  3순위: pgvector → Qdrant 마이그레이션 (10만+ 유저 시)
         - 쿼리 속도 5배
         - 메모리 사용 50% 감소
         - 2일 작업, Phase 4+ 검토
  
  4순위: Cloudflare Images 도입
         - Steam CDN 핫링킹 제거
         - 트래픽 비용 절감
         - 1일 작업, $5/월 (이미지 캐싱)
  
  5순위: 무료 티어 기능 축소 (마지막 수단)
         - 일일 검색 횟수 제한
         - 추천 결과 5개 → 3개
         - UX 하락 위험, 신중히 결정
```

#### 시나리오 2: 고객 문의 폭증
```
유저 1,000명 → 일 0-2건 문의
유저 10,000명 → 일 10-30건
유저 50,000명 → 일 50-100건 (1인 불가능)

대비:
  - Discord 커뮤니티로 셀프 서포트
  - FAQ 페이지 적극 운영
  - 자동 응답 봇 (GPT 기반)
  - Year 2 파트타임 CS 고용 검토 ($500/월)
```

#### 시나리오 3: 어뷰징 증가
```
유저 늘면 어뷰저도 늘어남:
  - 가짜 행동 로그 (B2B 데이터 오염)
  - 추천 결과 조작 (특정 게임 띄우기)
  - 가입 폭탄 (봇 가입)
  - DDoS 시도

대비:
  - Trust Score 시스템 (Phase 3 미리 준비)
  - Rate Limit 동적 조정
  - 이상 행동 자동 감지
  - Cloudflare WAF (Phase 4)
  - reCAPTCHA v3 (가입 시)
```

#### 시나리오 4: 카피캣 등장
```
한국 인디 추천 사이트 5개+ 우후죽순:
  - 너 사이트 UI 그대로 카피
  - Vibe Cluster 컨셉 도용
  - 가격 후려치기 ($199 → $49)

대비:
  - "Korea-discovered" 정체성 미리 굳히기
  - 한국 인디 개발자 네트워크 (모트)
  - 1년 누적 데이터 (카피 6개월+ 필요)
  - 커뮤니티 충성도 (Trust > 가격)
  - 빠른 기능 추가 (AI 협업 5배 활용)

법적 보호 (NEW):
  - 상표 등록:
    "Hidden Gem" 한글 + 영문 동시 출원
    한국: 특허청 (약 $150, 6개월 소요)
    미국: USPTO (약 $250, 1년 소요, Phase 5)
    → Year 1 안에 한국 등록 완료 권장
  
  - 알고리즘 영업비밀 보호:
    - GitHub Private 저장소
    - .env 파일 절대 커밋 X (이미 처리)
    - 직원/외주 NDA 템플릿 준비 (Phase 4)
    - 핵심 알고리즘 비공개 (오픈소스 X)
  
  - UI 디자인 저작권:
    - 자동 보호 (별도 등록 불필요)
    - 명백한 카피 시 증거 수집 (스크린샷 + 타임스탬프)
    - Wayback Machine으로 우리 사이트 기록 보존
  
  - 명백한 카피캣 대응:
    1단계: 경고장 발송 ($50, 변호사 명의)
    2단계: 호스팅 업체에 신고 (DMCA)
    3단계: 한국 저작권위원회 분쟁 조정
    4단계: 민사 소송 (최후 수단)
    
  - 예방 차원:
    - 우리 사이트 캡처 + 코드 git history 보존
    - 1년 단위로 변호사 1회 검토 ($100)
```

#### 시나리오 5: 기능 요청 폭증
```
유저 늘수록:
  - "이 기능 추가해주세요" 메일 폭증
  - 모든 요청 들어주면 PRD 망가짐
  - 거절하면 유저 이탈

대비:
  - 공개 로드맵 (Notion/GitHub)
  - 투표 시스템 (유저가 우선순위)
  - 분기별 1개만 추가 원칙
  - "지금은 아닙니다" 정중한 거절 템플릿
```

### 성공 후 정신 건강
```
1인 SaaS 성공 시 흔한 문제:
  - 외로움 (혼자 모든 결정)
  - 압박감 (실패 책임 100% 본인)
  - 무한 책임감 (24/7 가동)
  - 정체감 (운영자 vs 개발자 vs 마케터)

대비:
  - 1인 SaaS 커뮤니티 가입 (Indie Hackers, Microconf)
  - 멘토 1명 찾기 (월 1회 통화)
  - 분기 1회 휴가 (강제 디지털 디톡스)
  - 가족/친구와 일 분리 (저녁 18시 이후 X)
```

### 한 줄 결론
```
"실패는 회복 가능하다. 
 번아웃은 회복 어렵다.
 인프라/CS/카피캣/어뷰징 미리 준비하자.
 그리고 가끔은 진짜로 쉬자."
```

---

## 한 줄 결론

```
"AI 협업으로 효율 5배,
 한국에서 정체성 확립 1년,
 영미권은 Year 2부터 본격,
 PMF 검증 후 B2B 시작 - 이게 진짜 1인+AI의 길."
```

---

*PRD v4.2.3 FINAL | Last Updated: 2026-05-25*
*v3.2 (기술) + v4.0 (비전) + v4.1 (자기비판) + v4.2 (시니어 통합) + v4.2.1 (보완 5개) + v4.2.2 (미세 5개 + 성공 후 위험) + v4.2.3 (마지막 디테일 3개)*
*점수: 100/100 PERFECT (이 이상은 의미 없음)*
*이제 코드 짜러 가자.*
*다음 리뷰: Phase 1.6 완료 후 (Week 1 끝)*
