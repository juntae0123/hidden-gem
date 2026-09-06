# frontend/ — Next.js 16 (App Router), Vercel 배포

API 는 `NEXT_PUBLIC_API_URL`(FastAPI `/api/v1`) 과 Django(인증). 상태는 zustand, 데이터 패칭은 React Query. 스타일 Tailwind.

```
src/
├── app/
│   ├── page.tsx                 메인 — 히어로(취향분석 CTA), Vibe 칩, 섹션
│   ├── search/page.tsx          취향 분석: 49 지표 슬라이더(카테고리·툴팁) → by-preference. 중립(5.0) 지표는 보내지 않음(R-8).
│   │                            결과 아래 **신작 리그**(신작끼리 매칭) + '조용한 신작(리뷰<100) 포함' 토글(R-16), 취향 DNA 카드
│   ├── ranking/page.tsx         랭킹 3탭: 스테디 히든젬 / 요즘 뜨는 / 신작 리그(지금 달리는·아직 조용한), 장르 칩 (R-11·R-17)
│   ├── game/[appId]/            게임 상세 — 지표 레이더, 뱃지, 유사 게임(by-game)
│   ├── onboarding/, onboarding/swipe/   카드 스와이프 12개 → 초기 취향
│   ├── login/, auth/callback/   Google OAuth2 · Steam OpenID (JWT 는 URL fragment 로 전달)
│   ├── mypage/ (edit, taste)    프로필·취향·Steam 라이브러리 분석·탈퇴(익명화)
│   ├── privacy/, terms/         약관
│   ├── layout.tsx, providers.tsx, globals.css
├── components/
│   ├── game/   GameGrid · GameDetail · RecommendList · RankingTable(랭킹 3종 표) · RankingList
│   ├── ui/     GameCard · GemBadge(증거 지수 60/45 티어, NULL 은 뱃지 없음) · LifecycleBadge(신작 D+n / 출시 예정) · MatchBar
│   │           RadarChart · VibeChips · DnaCard · SearchBar · SurveyModal/SurveyGate · LoginPromptModal · CookieConsent · ErrorState · Loading*
│   └── layout/ Navbar · Footer
├── hooks/      useRecommend(by-preference/vibe mutation, useNewLeague(prefs, count, includeQuiet), useRanking) · useSearch · useGames
├── lib/        api.ts(fetch 래퍼, recommendByPreference(prefs,count,{maxReviewCount,includeNew,newOnly}), fetchRanking) · score.ts(GEM_EVIDENCE_TIERS)
│               constants.ts · umami.ts(이벤트) · utils.ts
├── store/      useUserStore(세션/JWT/로그인) · useGameStore
└── types/      game.ts (Lifecycle, RankingItem/Response/Type, RecommendedGame)
```

점수 표시 규칙: 서버가 준 `similarity_score`(v7: Core 87 + gem 12 → 상위 90대) 를 그대로 보여준다. 발굴 뱃지는 `gem_evidence` 기준(정착 게임만), 신작은 "발굴 점수는 아직 매기지 않아요".

```
npm install && npm run dev        # http://localhost:3000  (.env.local: NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1)
npx tsc --noEmit -p . && npx eslint src
```
