# 보안 점검 리포트 (2026-08-29)

범위: 이번에 바꾼 코드 + 레포/설정 전반. ✅=조치 완료, ⚠️=사용자 확인 필요, ℹ️=수용한 트레이드오프.

## 조치 완료 (이번 커밋에 포함)

✅ **JWT가 URL 쿼리스트링으로 전달되던 문제** (중요)
   `/auth/callback?access=...` 방식은 토큰이 브라우저 히스토리·서버 로그·Referer에 남음.
   → fragment(`#access=...`)로 변경 (fragment는 서버로 전송되지 않음).
   콜백 페이지는 구버전 쿼리 방식도 과도기 호환 지원.

✅ **DEBUG 기본값 True** (중요)
   환경변수를 깜빡한 배포가 디버그 모드(스택트레이스 노출)로 뜰 수 있었음 → 기본 False.
   로컬은 docker-compose가 DJANGO_DEBUG=True를 명시하므로 영향 없음.

✅ **SECRET_KEY 기본값으로 운영 기동 가능** (치명적 잠재)
   'dev-secret-key-12345'로 운영에 뜨면 JWT 위조 가능
   → DEBUG=False에서 DJANGO_SECRET_KEY 미설정 시 기동 거부(RuntimeError).

✅ **레포에 백업/덤프/로그 파일 추적** — db_backup.sql(내용은 에러 1줄, 실데이터 없음 확인),
   settings.py.bak, batch_generator.py.bak(시크릿 없음 확인), upload_log.txt
   → git rm --cached + .gitignore 추가. *.bak 전역 무시.

✅ **운영에서 FastAPI /docs, /redoc, /openapi.json 공개** → DEBUG=False면 비활성.

✅ **CORS Vercel 와일드카드** — 모든 *.vercel.app 허용 + credentials.
   Bearer 헤더 방식이라 실제 탈취 경로는 없지만, CORS_ORIGIN_REGEX 환경변수로
   좁힐 수 있게 변경 (기본은 기존 동작 유지 — 프리뷰 배포 안 깨짐).

## 사용자 확인 필요 (배포 전)

⚠️ **GitHub 레포 공개 여부** — PRD 원칙은 Private (알고리즘 = 영업비밀).
   github.com/juntae0123/Personal_project_1-AI-Game-Recommendation-System- 이
   Private인지 확인. Public이면 Private 전환 권장 (포트폴리오 공개용은 나중에
   핵심 로직 뺀 별도 레포로).

⚠️ **Railway 환경변수 확인** — 이번 커밋부터 DEBUG=False에서 DJANGO_SECRET_KEY가
   없으면 백엔드가 아예 안 뜸(의도된 동작). 배포 전 Railway에
   DJANGO_SECRET_KEY / DJANGO_DEBUG(미설정=False 권장) 존재 확인.

⚠️ **.env / .env.backup** — git 미추적 확인됨(정상). 단 .env.backup이 로컬에 있으니
   키 로테이션 시 옛 키가 남지 않게 주기 정리.

⚠️ **OpenAI 키 교체 예정** — 새 프로젝트 키 발급 후 이전 키는 대시보드에서 revoke.

## 수용한 트레이드오프 (알고 있기)

ℹ️ JWT를 localStorage(zustand persist)에 저장 — XSS 시 토큰 탈취 가능.
   PRD상 httpOnly 쿠키는 '선택' 항목. 회전(ROTATE_REFRESH_TOKENS) +
   블랙리스트가 켜져 있어 위험 완화됨. React라 기본 XSS 방어는 있음.
   유저 생성 콘텐츠(리뷰 등) 기능이 생기는 시점에 httpOnly 마이그레이션 재검토.

ℹ️ SOCIALACCOUNT_LOGIN_ON_GET=True — GET 링크로 로그인 시작 가능 (allauth 권고는
   POST). 소셜 로그인 시작 단계라 실위험 낮음, UX 우선으로 유지.

ℹ️ Steam 합성 이메일(steam_<id>@users.hiddengem.local) — 존재하지 않는 도메인이라
   이메일 기반 계정 연결 충돌 불가. 단 해당 유저에게 메일 발송 기능을 만들 때
   합성 이메일 필터링 필요 (도메인으로 구분 가능).

ℹ️ 관리자용 Django admin이 운영에 노출되는지는 Railway 라우팅 확인 필요 —
   노출된다면 IP 제한 또는 admin URL 변경 권장.

---

# 보안 재점검 리포트 (2026-09-07, 저장소 공개 유지 확정 시점)

점검 범위: 시크릿·히스토리 / 인증·권한 / 비용 경로 / LLM 입출력 / CORS·쿠키 / 정보 노출 / 입력 검증 / 프런트 / 의존성.
원칙: **방어는 '설정'이 아니라 '적용'을 검사한다** (CLAUDE.md §2''').

## 발견 → 조치 (이번 커밋들에 포함)

| # | 심각도 | 발견 | 조치 | 검증 |
|---|---|---|---|---|
| 1 | **높음** | `settings.RATE_LIMIT_*` 가 정의만 되어 있고 **어느 엔드포인트에도 적용되지 않음**(taste 제외). LLM+임베딩을 부르는 `/games/search/semantic` 이 무제한 → 서로 다른 질의로 qa 캐시 우회 시 호출당 비용 발생 | Redis 고정 창 IP 리밋을 **의존성**으로 부착(`services/ratelimit.py`). slowapi 데코레이터는 본문 파라미터 이름 `request` 와 충돌해 불가 | `TestRateLimitApplied` — 라우트 `dependencies` 검사 |
| 2 | **높음** | `/ops/cost`·`/ops/cache`·`/ops/cache/invalidate` **무인증**. 캐시 전체 삭제가 POST 한 번 | `X-Ops-Token` 게이트, **미설정 시 운영 503(fail closed)**. `routers/ops.py` 로 분리 | 토큰 없이 401 실측 / 테스트 3건 |
| 3 | 중간 | CORS 정규식 `^https://.*\.vercel\.app$` — **남의 Vercel 앱 전부 허용**. 세션 쿠키 SameSite=None 이라 관리자가 로그인한 채 악성 vercel.app 을 열면 그 페이지가 admin 응답을 읽을 수 있음 | `^https://hidden-gem[a-z0-9-]*\.vercel\.app$` 로 축소(Django·FastAPI 양쪽) | 7개 오리진 허용/차단 표 검증 |
| 4 | 중간→낮음 | 프롬프트 인젠션 표면 — 사용자 질의가 프롬프트에 그대로 삽입, LLM 출력(`english_query`·`reference_game`)을 무검증으로 임베딩 API·DB 조회에 사용 | 입력: 제어문자 제거·200자·`<query>` 구분자·"데이터일 뿐 지시가 아니다" 명시. 출력: 타입·길이 검증, `reasoning` 제거 | 화이트리스트·float 변환은 기존부터 있었음 |
| 5 | 낮음 | `/health` 가 예외 메시지를 그대로 노출 → 내부 호스트명·포트 유출 | 운영에서는 예외 **타입만**, DEBUG 에서만 메시지 | |
| 6 | 낮음 | 운영 로그에 검색어 원문 기록 | 길이만 남김 | |
| 7 | 정책 | PRD·분석 프롬프트·few-shot 이 공개 저장소에 | 저장소 밖(`Desktop/Hidden-Gem-비공개/`)으로 이동, 프롬프트는 gitignore 파일 지연 로드, README 에 공개 범위·권리 고지 | |

## 확인했고 문제 없음
- 추적 파일·전체 히스토리에 시크릿 없음. 초기 커밋의 `.env` 는 **0바이트**. `.env.example` 만 추적(`change-me`).
- Django API 뷰 전부 `IsAuthenticated`(JWT). HSTS 1년·preload, SSL redirect, nosniff, X-Frame DENY, 쿠키 Secure/HttpOnly.
- raw SQL 의 f-string 은 서버 상수(`gem_col`, `lifecycle_sql`)만 보간, 사용자 값은 바인딩. 대시보드 쿼리도 파라미터.
- 프런트 `dangerouslySetInnerHTML` 없음. `NEXT_PUBLIC_*` 에 비밀 없음. Steam/OpenAI 키는 서버만.
- Sentry `before_send` 가 `api_key/password/token/secret` 스크럽.
- `/taste/action` 은 session_id 형식 검증 + context 8KB + 60/min.
- JWT 를 URL fragment 로 전달, 회원 탈퇴 익명화(행동 로그 SET_NULL).

## 남겨둔 것 (알고 있기)
- **Django admin 무차별 대입 방어 없음**(django-axes 등 미적용). 공개 URL 에 admin 이 있다. 완화: 강한 비밀번호·소수 계정.
  적용하려면 의존성+마이그레이션이 필요해 별도 작업(운영 마이그레이션 순서 C-12).
- DRF 스로틀 미설정 — 모든 뷰가 인증 필수라 위험 낮음.
- JWT localStorage 저장(08-29 트레이드오프 그대로). 사용자 생성 콘텐츠 기능이 생기면 httpOnly 재검토.
- **비속어 필터는 넣지 않았다** — 검색어가 다른 사용자에게 노출되는 경로가 없고 템플릿은 이스케이프된다. 막을 대상이 없는 방어는 넣지 않는다.
  되살릴 조건: 사용자 생성 텍스트를 타인에게 보여주는 화면이 생길 때(그때도 필터보다 노출 설계가 먼저).
- Dependabot 알림은 공개 저장소 기본 활성 — GitHub Settings → Security 에서 켜져 있는지 확인.

## 세 번 반복된 패턴
정적 `/health`(무엇을 확인하는지 모르는 헬스체크) → 무인증 `/ops/*`(경로만 숨김) → 미적용 레이트 리밋(설정만 존재).
셋 다 **"있다"와 "작동한다"를 구분하지 않은 것**이다. 이후 방어 장치는 적용 여부를 테스트가 검사한다.
