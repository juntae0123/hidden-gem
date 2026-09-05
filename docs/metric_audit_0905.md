# 지표 감사 — 49+9 는 충분한가, 무엇을 더하고 고치고 뺄까 (2026-09-05)

> **§7 이 최종이다.** §1~§6 의 '합병' 제안은 개발자 반론으로 철회됐다(디테일 손실·미래 게임의 판단 공백). 데이터 분석(§2)은 그대로 유효하고,
> 조치는 '합치기'에서 '앵커를 갈라 구분을 가르치기'로 바뀌었다. 지표는 줄이지 않고 늘린다(52 + 17 + 9).

개발자 질문: "지표 63개 충분한가? 더 있으면 좋을 것, 있는 것 중 개선·제외할 것."
근거: 교사 4,190건(GPT-5.4) + 학생 8,760건(gpt-5.4-mini) 원본 JSONL 에서 직접 계산한 분포·상관·유효 차원,
홀드아웃 150쌍의 지표별 r, 배치 프롬프트의 정의(`batch_generator.py:214-258`), 사용자 입력 동선(프리셋·Vibe·검색어 사전).

---

## 1. 결론 먼저

**개수는 충분하다. 문제는 개수가 아니라 세 종류의 지표가 한 그릇에 섞여 있다는 것이다.**

| 종류 | 무엇 | 설명문으로 잴 수 있나 | 판정 |
|---|---|---|---|
| A. 취향·설계 축 | 분위기, 요구 능력, 메커닉, 서사, 사회성 (약 30개) | **있다** — 개발자가 설명문에 쓰는 것 | 살린다. 중복 6쌍만 합친다 |
| B. 실행 품질 | ui_ux_polish, tutorial_quality, save_flexibility, progression_clarity, animation_quality, audio_design, monetization_fairness, modding_support, community_dependency | **없다** — 해봐야 안다 | 교사도 σ 0.5~1.0 으로 뭉개짐(기본값 찍기). 슬라이더에서 빼고 **리뷰 근거**로 대체 |
| C. 사실 속성 | 멀티 규모, 협동, 스텔스 유무, 창작 도구 | 설명문보다 **Steam 메타데이터가 정확** | LLM 추정 대신 appdetails categories/tags 로 |

여기에 **사용자가 말하고 싶은데 축이 없는 것** 3~4개가 있고, **LLM 이 아니라 크롤러로 채워야 할 실측** 5개가 있다.
"60개 지표" 라는 숫자는 유지 가능하지만 구성이 바뀐다: 취향 축 ~35 + 속성 태그 ~17 + 실측 ~8.

---

## 2. 데이터가 말하는 것

### 2-1. 유효 차원 — 49개가 실제로는 약 20개다
합산 12,949건 표준화 후 PCA: 누적 설명분산 50% = **4개 성분**, 80% = 13, 90% = 21, 95% = 29.
"다른 48개로 이 지표를 얼마나 예측할 수 있나"(R²): action_pacing .95, reflex_demand .94, narrative_depth .93, lore_richness .90,
growth_reward .88, strategic_depth .88, endgame_content .87, learning_curve .87 … — 상위 20개가 R² .82 이상.
반대로 독립적인 것: stealth_importance .22, monetization_fairness .23, user_creation .31, save_flexibility .44, platforming .53, humor .53, rng .56.
(독립 ≠좋음 — monetization_fairness 는 독립적인데 **홀드아웃 r 0.36**. 독립적이고 신뢰 불가 = 노이즈.)

### 2-2. 강한 중복 쌍 (|r| ≥ 0.83, 교사·학생 모두)
| 쌍 | r 합산 | 교사 | 학생 | 판정 |
|---|---|---|---|---|
| reflex_demand ~ action_pacing | **.94** | .94 | .95 | 설명문으로는 구분 불가. **합친다** → `action_intensity` |
| lore_richness ~ narrative_depth | .89 | .85 | .90 | 합친다 → `narrative_depth` (세계관은 설명문에서 서사와 분리 안 됨) |
| grind_factor ~ growth_reward | .86 | .85 | .88 | **정의 붕괴**. grind 는 "반복 노동 강요"(부정)인데 성장 보상과 같이 움직인다 → 앵커 교정 (§4-3) |
| soundtrack_impact ~ audio_design | .85 | .71 | .91 | 합친다 → `audio` |
| build_variety ~ endgame_content | .84 | .74 | .86 | replay_value(.78/.73)와 함께 → `replay_depth` 하나 |
| visual_spectacle ~ animation_quality | .83 | .76 | .81 | 합친다 → `visual_polish` |
| learning_curve ~ difficulty_accessibility | **−.76** | −.49 | −.84 | 같은 축의 양끝. → `difficulty` 하나 (0 쉬움·옵션 많음 ~ 10 가혹) |

'프레젠테이션 품질' 요인(visual/audio/animation/art_style 서로 .6~.8)은 **한 덩어리**다 — LLM 이 "잘 만든 게임" 후광을 네 칸에 나눠 적는다.

### 2-3. 설명문으로 잴 수 없는 것 — 교사 σ 가 말해준다
| 지표 | 교사 σ | 교사 0% | 홀드아웃 r | 뜻 |
|---|---|---|---|---|
| tutorial_quality | **0.53** | 0 | .48 | 거의 전부 5. 설명문에 튜토리얼 얘기가 없다 |
| save_flexibility | **0.73** | 0 | .51 | 동일 |
| ui_ux_polish | 0.78 | 0 | .55 | 동일 |
| progression_clarity | 0.94 | 0 | .59 | 동일 |
| monetization_fairness | 1.54 | 0 | **.36** | 인디 유료 게임은 대부분 "해당 없음" — 모델마다 다른 기본값 (교사 6.35 / 학생 6.94) |
| modding_support | 2.21 | 17 | .43 | 학생은 94% 가 0. 설명문에 모딩 언급이 드물다 |
| community_dependency | 1.59 | 0 | .61 | 학생 36% 가 0, 교사 0% — 정의를 두 모델이 다르게 읽음 |

이 7개는 **정보가 아니라 기본값**이다. v7 이 마스크라 사용자가 안 고르면 안 들어가지만, 슬라이더에 있는 한 누군가 고른다.
그리고 X-Factor 시절엔 이것들이 8+ 로 가점을 만들었다. → 슬라이더·identity 에서 **숨긴다** (컬럼은 보존).
실제로 알고 싶은 것(UI 완성도, 튜토리얼, 과금)은 **Steam 리뷰 텍스트**에 있다 — 다음 단계의 데이터 소스.

### 2-4. 0 에 몰린 지표 — 척도가 아니라 유무다
| 지표 | 교사 0% | 학생 0% | 판정 |
|---|---|---|---|
| stealth_importance | **98** | 91 | 불리언 `has_stealth` 로. 0~10 은 낭비 |
| user_creation | 86 | 95 | 불리언 `has_user_creation` 로 |
| coop_synergy / multiplayer_scale / competitive_stress | 79~82 | 70~87 | **Steam categories** 가 정답: Online Co-op / Local Co-op / Shared-Split Screen / PvP. LLM 추정 → 메타데이터 |
| platforming_precision | 46 | 80 | 플랫포머 안에서는 의미 있음(Celeste 10 vs 캐주얼 3). 유지 |
| dark_fantasy_vibe / horror / cozy / gore | 21~54 | 36~54 | 0 이 정보다("공포 없음"). 유지 — v7 이 0 을 목표로 쓸 수 있게 됐다 |

### 2-5. 불리언 태그 9개
`is_real_time` 80% true → 정보량 낮음(`is_turn_based` 의 여집합에 가깝다). `has_permadeath` 교사 0.5% vs 학생 5.6% — 교사 라벨이 의심스럽다
(로그라이크가 4,190개 중 21개일 리 없다). 나머지는 유지. 교사 데이터에만 있는 `has_automation`(100% true)·`has_enemy_pressure`(0%)는 죽은 태그, DB 에 없음 — 무시.

---

## 3. 사용자가 말하고 싶은데 축이 없는 것

검색어 사전(MOOD/FEATURE_KEYWORDS)·프리셋·Vibe 와 한국 인디 이용자의 실제 질의를 대조:

| 질의 | 지금 | 판정 |
|---|---|---|
| "한국어 되는", "한글 지원" | **없음** | 가장 큰 공백. 취향 축이 아니라 **필터** — appdetails `supported_languages` 로 (LLM 아님, 비용 0) |
| "짧게 끝나는 / 볼륨 큰" | session_length(회당) 만 | **총 플레이타임**이 없다. Steam appreviews 의 `author.playtime_forever` 샘플 중앙값으로 실측 가능 — 리뷰 갱신 때 같이 |
| "연애 / 로맨스" | 없음 | 취향 축 추가 `romance_focus` (설명문에서 잘 드러남) |
| "추리 / 미스터리 / 수사" | puzzle_complexity 로 우회 | 추가 `mystery_factor` |
| "SF / 판타지 / 현대 / 역사" 배경 | dark_fantasy 만 | **배경 설정** 축 부재. 불리언 4개 `setting_scifi/fantasy/modern/historical` (문장 검색은 임베딩이 잡지만 슬라이더·Vibe 는 못 잡음) |
| "글 많이 읽는 / 비주얼노벨" | narrative_linearity 로 우회 | 추가 `reading_load` (텍스트 비중) |
| "덱빌딩" | build_variety + turn_based 우회 | 불리언 `has_deckbuilding` — 인디에서 너무 큰 하위 장르 |
| "농사 / 생활 시뮬" | cozy + management 우회 | 불리언 `has_life_sim` |
| "로컬 코옵 / 친구랑 한 화면" | coop_synergy(LLM) | Steam categories 로 (위 2-4) |
| "컨트롤러 / 스팀덱" | 없음 | categories 메타데이터 필터 |
| "성인 / 선정성 없는" | gore 만 | Steam content descriptors 로 `mature_content` |
| "병맛 / 기묘함" | humor 우회 | 보류 — humor_rating 재정의로 흡수 가능한지 먼저 |

---

## 4. 제안 — 무엇을 어떻게

### 4-1. 즉시 (비용 0, 오늘)
- 실행 품질 7개를 `/metrics/list`·슬라이더·identity 에서 **숨김** (`HIDDEN_METRIC_FIELDS`). 컬럼·값 보존. Vibe/프리셋에서도 안 쓰는지 확인 (지금 안 씀).
- `is_real_time` 은 태그 필터 UI 에서 내림 (정보량 낮음).

### 4-2. 크롤러 확장 (LLM 비용 0, Steam 호출은 이미 하는 appdetails 안에 있음)
`supported_languages`(한국어 여부), `categories`(Online/Local Co-op, Split Screen, PvP, Full Controller Support, Steam Deck 은 별도),
`content_descriptors`, `platforms`. 컬럼 5~8개 추가. **한국어 지원 필터**가 이 프로젝트에서 가장 큰 사용자 가치 하나다.
리뷰 갱신(`refresh_reviews`)에 `num_per_page=100` 한 페이지를 받아 `playtime_forever` 중앙값 → `median_playtime_hours`. 호출 수 동일.

### 4-3. 정의 교정 (다음 백필/재분석 프롬프트 v2)
- `grind_factor`: "10=진행하려면 같은 행동을 수십 시간 반복해야 함(MapleStory), 5=선택적 파밍, 0=반복 없음" — **성장 보상과 독립**임을 명시. 예: "Hades 는 growth_reward 9 / grind 3".
- `humor_rating`: 병맛·기묘함을 포함하는지 앵커에 명시 (Goat Simulator 10, 유머 없음 0).
- 합병 지표 6개는 **재분석 없이 뷰로**: `action_intensity = mean(reflex, pacing)`, `narrative_depth' = mean(narrative, lore)`, `audio = mean(soundtrack, audio_design)`,
  `visual_polish = mean(visual, animation)`, `replay_depth = mean(replay, build_variety, endgame)`, `difficulty = mean(learning_curve, 10−difficulty_accessibility)`.
  원본 컬럼 보존. 프롬프트 v2 부터는 합친 이름으로만 뽑는다 → **출력 토큰 감소 = 비용 감소**(출력이 비용의 71%).

### 4-4. 신규 지표 (프롬프트 v2, 전 게임 재부여 — 학생 모델 하나로 통일)
수치 3: `romance_focus`, `mystery_factor`, `reading_load`. 불리언 6: `setting_scifi/fantasy/modern/historical`, `has_deckbuilding`, `has_life_sim`, + 기존 전환 2: `has_stealth`, `has_user_creation`.
**전 게임에 같은 모델(gpt-5.4-mini)로** 부여한다 — 새 축엔 교사 기준이 없으므로 코호트 편향이 애초에 없다. 신규 지표만 뽑는 짧은 프롬프트면
12,949건 × 약 $0.002 ≈ **$25~30**. 백필 재개($27)와 같은 창에서.

### 4-5. 결과 구성 (제안)
| | 지금 | 제안 |
|---|---|---|
| LLM 수치 축 | 49 | **35** (49 − 합병 6 − 실행품질 7 − 불리언 전환 2 − 메타데이터 전환 2 + 신규 3) |
| LLM 불리언 | 9 | **15** (9 − is_real_time 1 + 전환 2 + 배경 4 + 하위장르 2 − 1?) → 정확 수는 구현 때 |
| Steam 실측 | 3 (리뷰 수·긍정률·가격) | **~9** (+한국어, 코옵 3종, 컨트롤러, 성인, 플레이타임 중앙값) |
| 발굴 | gem_potential(사용 불가) | gem_evidence(리뷰 기반) |

"60개의 세분화된 지표" 문구는 "취향 축 35 + 속성 17 + 실측 9" 로 정직하게 다시 쓸 수 있다. 숫자는 비슷하고 **각 칸이 실제로 다른 것을 잰다**.

---

## 5. 하지 말 것
- 지표를 더 **잘게** 쪼개는 것. 유효 차원 20 에 49개 — 이미 LLM 이 구분 못 하는 칸이 많다. 쪼갤수록 후광이 여러 칸에 복사된다.
- 실행 품질을 LLM 에 다시 묻는 것. 설명문엔 그 정보가 없다. 리뷰 텍스트가 있어야 한다.
- 합병을 재분석으로 하는 것. 뷰(평균)로 충분하고 비용 0. 재분석은 프롬프트 v2 신규 지표 때 한 번만.
- 교사 4,190건을 GPT-5.4 로 다시 뽑는 것. 새 축은 학생 모델로 전 게임 통일이 맞다 (편향 없음, 저비용).

## 6. 이 변경이 v7 에 주는 것
가중 RMSE 는 축이 서로 독립일수록 정직하다. 지금은 사용자가 "액션 9" 를 고르면 reflex/pacing/time_pressure 세 칸이 같은 걸 세 번 세고,
"스토리 9" 는 narrative/lore/environmental 이 세 번 센다. 합치면 **사용자가 고른 축 하나가 한 번만** 들어간다.
실행 품질 7개가 빠지면 "잘 만든 게임 후광"이 취향 거리에 섞이지 않는다.

---

## 7. 개발자 반론 → 판정 수정 (2026-09-05 밤)

> "느낌이 비슷한 지표 2개가 있을 수 있지만 합치면 디테일이 떨어진다. 앞으로 수집할 게임에서 지표의 부재는 판단 공백이다 —
> A 축으로 매력적인 게임이 A 가 없어서 저평가되거나, A+B+C 시너지에서 B 가 없어 반대로 고평가될 수 있다."

**받아들인다. 합병 제안(§2-2, §4-3 의 뷰 합병)은 철회.** 이유를 정확히 적는다.

- 내가 본 r=0.94 는 **지금까지 수집된 게임 모집단의 사실**이지 두 축의 **의미가 같다는 증명이 아니다.** 리듬 게임(reflex 9, pacing 5),
  턴제인데 QTE 가 있는 게임(reflex 6, pacing 2), 느린 호러(time_pressure 8, action_pacing 2) — 두 축이 갈리는 게임은 존재하고,
  그런 게임이야말로 "지표가 세분화된 사이트"가 잡아야 하는 게임이다. 합치면 그 게임이 정확히 사라진다.
- **v7 마스크 아래에서는 중복이 점수를 해치지 않는다.** 사용자가 고른 축만 거리에 들어가므로, reflex 와 pacing 이 둘 다 들어가는 건
  사용자가 둘 다 골랐을 때뿐이고 그건 사용자의 뜻이다. 중복이 문제였던 건 49개를 전부 넣던 v6/4단계 시절이다.
  → §6 의 "세 번 센다" 주장은 v6 에 대한 것이었다. v7 에선 성립하지 않는다. **정정.**
- 컬럼 유지 비용은 0 이고, 출력 토큰 절감은 지표 6개 = 전체의 약 12% 라 크지 않다.

**대신 이렇게 한다 — 디테일을 살리는 방향:**
1. **앵커를 갈라놓는다.** 프롬프트 v2 에 두 축이 *다르게* 나오는 예시를 명시한다. reflex_demand vs action_pacing: "리듬 게임 = reflex 9 / pacing 6,
   느린 스텔스 호러 = reflex 3 / pacing 2 / time_pressure 8". lore_richness vs narrative_depth: "Elden Ring = lore 10 / narrative 4, To the Moon = lore 3 / narrative 9".
   grind_factor vs growth_reward: "Hades = growth 9 / grind 3, MapleStory = growth 7 / grind 10". learning_curve vs difficulty_accessibility 는
   방향이 다른 별개 축("배우기 어렵다" vs "쉬운 옵션이 있다")임을 명시 — Celeste 는 learning 7 / accessibility 9.
   → 상관이 떨어지면 LLM 이 구분을 시작한 것이고, 그대로면 설명문에 그 정보가 없다는 뜻. **다음 홀드아웃에서 쌍별 r 을 다시 잰다.**
2. **실행 품질 7개도 버리지 않는다.** 계속 수집·저장한다. 다만 신뢰가 낮으므로 **슬라이더에서 "추정치" 표시**(숨김 대신)와 identity 제외.
   리뷰 텍스트 소스가 붙으면 그 값으로 교체한다 — 컬럼이 살아 있어야 교체가 된다.
3. **0 에 몰린 지표도 수치로 유지**, 불리언은 **추가**한다(전환 아님). stealth_importance 0~10 은 스텔스 게임 안에서의 비중을 잡는다.
4. 신규 축(§3·§4-4)과 메타데이터(§4-2)는 그대로 — 여기가 "부재 = 공백"을 실제로 줄이는 부분이다. 특히 배경 설정·연애·추리·읽기 비중은
   지금 있는 어떤 조합으로도 표현되지 않는다.

**수정된 구성:** 수치 49 → **52** (+romance_focus, mystery_factor, reading_load), 불리언 9 → **17**, Steam 실측 3 → **9**.
"60개 지표" → "취향 축 52 + 속성 17 + 실측 9". 개수는 늘고, 각 칸의 정의는 더 날카로워진다.

**하나만 남기는 경고:** 축이 많을수록 사용자가 슬라이더 49개(→52개) 앞에서 멈추는 콜드스타트가 커진다. 그건 지표를 줄여서 풀 문제가 아니라
프리셋·Vibe·스와이프·문장 검색(이미 있다)으로 푸는 UI 문제다. 지표 개수와 입력 UI 를 분리해서 생각한다.
