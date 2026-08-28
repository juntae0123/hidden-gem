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
