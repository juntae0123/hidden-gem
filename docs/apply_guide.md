# 2026-08-28 변경분 적용 가이드 (Vercel + Railway 자동 배포 전제)

"커밋하면 알아서 최신화"는 곧 "깨진 커밋도 알아서 배포된다"는 뜻.
아래 순서대로 확인 후 커밋한다.

## 오늘 바뀐 것

1. **이모지 정리 (43개 파일)** — 주석/로그/CLI 프롬프트/admin 라벨에서 제거.
   유지한 곳: vibe_config emoji 데이터 필드, 프론트 UI 문자열,
   batch_generator SYSTEM_PROMPT(모델 지시 일부), cost_guard Discord 알람 이모지.
2. **batch_generator `--yes` 플래그** — 무인 실행용 (업로드 확인 프롬프트 생략).
3. **embeddings/weekly_pipeline.py (신규)** — 신작 발견→배치→적재→임베딩→백분위
   5단계 오케스트레이터. + scripts/pipeline/setup_weekly_task.ps1 (매주 월 03:30).
4. **메인 히어로 + 네비 리디자인** — page.tsx, Navbar.tsx (docs/design_improvements.md).
5. **docs/** — portfolio_raw.md, design_improvements.md, 이 문서.

이미 검증됨: 전체 py_compile 통과, `tsc --noEmit` 통과.
아직 안 됨(Windows에서 할 것): `npm run build`, `pytest`.

## 커밋 전 체크 (로컬)

```bash
cd C:\Hidden-Gem-project\frontend
npm run build            # Vercel 빌드와 같은 관문

cd C:\Hidden-Gem-project
.venv\Scripts\activate
pytest fastapi_app/tests # 24개 통과 확인
git diff --stat          # 의도한 파일만 바뀌었는지
```

## 커밋 순서 (문제 시 롤백 단위가 되게 분리)

```bash
git add -p  # 또는 파일 단위로
git commit -m "refactor: strip emoji from comments/logs (keep UI strings and prompts)"
git commit -m "feat: weekly new-game ingestion pipeline + task scheduler setup"
git commit -m "design: taste-analysis hero + larger navbar, umami CTA events"
git push origin main     # → Vercel/Railway 자동 배포
```

배포 직후:
```bash
curl https://<railway-도메인>/health
```
프론트는 Vercel 프로덕션 URL에서 메인/검색/게임상세 육안 확인 (모바일 폭 포함).

롤백: Vercel → Deployments → 직전 배포 Promote / Railway → Deployments → Redeploy.

## 주간 파이프라인 가동 순서

1. few-shot 예시 확인: `data/fewshot/fewshot_examples.jsonl`
   (없으면 `python -m embeddings.fewshot_sampler --input data/merged/... --n 24` 먼저)
2. 리허설 (batch 컨테이너에서 실행 — 의존성이 이 이미지에 있음):
   `docker compose exec batch python -m embeddings.weekly_pipeline --crawl-only`
   → `docker compose exec batch python -m embeddings.weekly_pipeline --limit 3` (비용 ~수십 원)
3. 스케줄 등록 (관리자 PowerShell):
   `PowerShell -ExecutionPolicy Bypass -File scripts\pipeline\setup_weekly_task.ps1`
4. 4월 이후 백필: `--days 150 --limit 100`으로 몇 주에 나눠 소화.

참고: DB가 Railway면 .env DATABASE_URL이 Railway를 가리키는지 확인.
파이프라인은 로컬 PC에서 돌고 프로드 DB에 직접 적재한다.

## 커밋 위생

- 목적이 다른 변경을 한 커밋에 섞지 말 것 (롤백 단위).
- 푸시 전 `git diff --staged`로 .env/키 유출 확인.

---

# 2차 변경분 (같은 날 저녁)

## 바뀐 것

1. **히어로 카피 교체** — "60개의 세분화된 지표로, 숨은 명작을 찾아냅니다" (부제 삭제).
2. **Steam 로그인 (allauth OpenID)**
   - settings: `providers.steam` 추가 / requirements: `python3-openid` 추가
   - adapter: Steam은 이메일이 없어 `steam_<id>@users.hiddengem.local` 합성 이메일로
     자동 가입 통과, 닉네임은 personaname
   - setup_oauth.py가 STEAM_API_KEY로 Steam SocialApp 자동 등록
   - 로그인 페이지에 "Steam으로 계속하기" 버튼
3. **취향 DNA 카드** (`components/ui/DnaCard.tsx`) — /search 결과 상단 버튼.
   canvas로 1080x1080 이미지 렌더 → 저장/Web Share. umami 이벤트:
   dna_card_create/save/share. 외부 이미지는 CORS taint 때문에 미포함(텍스트/바 차트만).

## Steam 로그인 가동 순서

1. https://steamcommunity.com/dev/apikey 에서 API Key 발급 (도메인: localhost)
2. `.env`에 `STEAM_API_KEY=...` 추가
3. 컨테이너 재빌드 (requirements 변경): `docker compose up -d --build django`
4. SocialApp 등록: `docker exec hidden_gem_django python scripts/setup_oauth.py`
5. 테스트: http://localhost:3000/login → Steam 버튼 → Steam 로그인 →
   /auth/callback 리다이렉트 → 닉네임 = Steam 프로필명 확인
6. 운영(Railway)에도 STEAM_API_KEY 환경변수 추가 + setup_oauth 1회 실행
   (운영 Site 도메인은 Railway 도메인으로 — setup_site()가 localhost로 덮으니
   운영에서는 admin에서 Site만 수동 확인)

## 배포 전 최종 체크 (통합)

```bash
cd frontend && npm run build
cd .. && .venv\Scripts\activate && pytest fastapi_app/tests
docker compose up -d --build django   # requirements 변경 반영
docker exec hidden_gem_django python scripts/setup_oauth.py
```
