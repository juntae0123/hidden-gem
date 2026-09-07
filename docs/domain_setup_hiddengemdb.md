# 도메인 전환 체크리스트 — hiddengemdb.com (2026-09-06)

Vercel Registrar 등록. 갱신 $10.46/yr, 자동 갱신 켜짐, 만료 2027-09-06.

## 코드에서 끝난 것 (커밋됨)
- `frontend/src/lib/constants.ts` — `SITE_URL`(기본 `https://hiddengemdb.com`, `NEXT_PUBLIC_SITE_URL` 로 덮어쓰기), `CONTACT_EMAIL`
- `layout.tsx` — `metadataBase`, canonical, OG `url`/`siteName`/`locale`, 트위터 카드, 타이틀 템플릿
- `sitemap.ts` / `robots.ts` 신설 — `/mypage`·`/auth/` 만 색인 제외, 사이트맵 링크
- `privacy/page.tsx` — 소유하지 않은 `privacy@hiddengem.io` 제거 → `CONTACT_EMAIL`
- `DnaCard` 공유 카드 하단 호스트 표기 폴백
- Django `settings.py` — CORS/CSRF 기본값 `hiddengem.io` → `hiddengemdb.com`, `FRONTEND_URL` 중복 정의 제거

## 대시보드에서 직접 (순서대로)
1. **Vercel → 프로젝트 → Settings → Domains** 에 `hiddengemdb.com` + `www.hiddengemdb.com` 추가.
   같은 계정에서 산 도메인이라 DNS 는 자동. www 는 apex 로 리다이렉트 설정.
2. **Vercel → Settings → Environment Variables**
   - `NEXT_PUBLIC_SITE_URL = https://hiddengemdb.com`
   - (Umami 를 쓰면) `NEXT_PUBLIC_UMAMI_URL`, `NEXT_PUBLIC_UMAMI_WEBSITE_ID` 확인
   저장 후 재배포해야 반영된다.
3. **Railway → fastapi 서비스 → Variables** ← ⚠️ 이걸 빼먹어서 프런트가 "연결에 문제가 있어요"로 죽었다 (09-07)
   - `FRONTEND_URL = https://hiddengemdb.com,https://www.hiddengemdb.com,https://hidden-gem-gold.vercel.app`
     (FastAPI CORS 허용 목록. django 의 같은 이름 변수와 **별개**다)
3-2. **Railway → django 서비스 → Variables**
   - `FRONTEND_URL = https://hiddengemdb.com,https://www.hiddengemdb.com`
     (이 값이 그대로 CORS + CSRF 화이트리스트가 된다)
   - `ALLOWED_HOSTS` 에 django 도메인 유지 + 나중에 커스텀 서브도메인 붙이면 추가
4. **Google Cloud Console → OAuth 클라이언트**
   - 콜백은 Django 도메인이라 리디렉션 URI 는 그대로 둬도 로그인은 된다.
   - 승인된 JavaScript 원본에 `https://hiddengemdb.com` 을 추가해두면 안전.
5. **Umami** — 웹사이트 설정의 도메인을 새 주소로 변경(또는 두 도메인 모두 등록).
6. **Google Search Console** — 새 도메인 등록 + `https://hiddengemdb.com/sitemap.xml` 제출.

## 확인
```
curl -sI https://hiddengemdb.com | head -3
curl -s https://hiddengemdb.com/robots.txt
curl -s https://hiddengemdb.com/sitemap.xml | head -5
```
로그인 1회(구글) → 찜 1회 → `/admin/dashboard/` 에서 행동 로그가 늘어나는지.

## 남은 판단
- 이메일: `privacy@hiddengemdb.com` 을 쓰려면 메일 포워딩이 필요하다(Vercel 은 제공 안 함).
  Cloudflare 로 DNS 를 옮기면 Email Routing 이 무료. 그 전까지는 개인 메일로 둔다.
- API 서브도메인(`api.hiddengemdb.com` → Railway)은 선택. 붙이면 OAuth·CORS 설정을 한 번 더 손봐야 한다.
