# 백필 후속 런북 (2026-09-04) — 쓸 수 있는 데이터를 가장 싸게

원칙 세 가지. 첫째, **재분석은 마지막 수단**이다. 이미 $50 넘게 들어간 8,650건은
보정으로 살리는 걸 먼저 시도한다(비용 0). 둘째, 돈이 나가는 단계는 아래 표에 전부
적어두고, 그 외 단계는 전부 무료(Steam API·DB 연산)다. 셋째, 모든 DB 변경은
`--dry-run` 먼저, 그리고 원본 보존(백업 테이블) 없이 덮어쓰는 단계는 없다.

| 단계 | 비용 | 걸리는 시간 |
|---|---|---|
| 1 후처리(라벨 복구·임베딩·리뷰 게이트·샘플) | 0 (임베딩 999건 ≈ $0.02) | 리뷰 조회 2.5~3h (백그라운드) |
| 1 홀드아웃 150건 (동기+캐시) | ≈ $1 (실측으로 확정) | 15~25분 |
| 2 판정·보정·백분위 재계산 | 0 | 5분 |
| 3 서비스 확인 | 0 | 10분 |
| 4 재개 (남은 3/16~6월초 ≈ 5,500건) | 방식에 따라 $20~80 — **결정 후에만** | 회차당 30~60분 |

현재 상태: 백필 16회차, 신작 8,650건 분석·적재(9/4 → 6월 초 출시작). 1회차 999건은
교사 라벨이 붙어 임베딩 미완. 2~9회차 4,112건은 리뷰 게이트 이전에 활성화된 상태.
gem_percentile은 12,837건 통합으로 재계산됨(교사 데이터가 상위 1/3 독식 — 2단계에서 정리).
루프는 `data/STOP_BACKFILL`로 정상 종료됨.

---

## 0. 실행 위치 (중요)

모든 `embeddings.*` 스크립트는 **batch 컨테이너 안에서** 돌린다. `.env`의 활성
`DATABASE_URL`이 `db:5432`(도커 네트워크 호스트명)라 Windows 호스트에서 그냥
`python -m embeddings.X`로 실행하면 DB에 붙지 못하고, `requests`/`sqlalchemy` 같은
의존성도 호스트 venv엔 없다. 항상 앞에 `docker compose exec batch` 를 붙인다.
(호스트에서 직접 돌리려면 `.env`의 로컬용 `DATABASE_URL=...@localhost:5432` 주석을
해제해야 하는데, 그러면 컨테이너 쪽이 깨지므로 권장하지 않는다.)

## 1. 후처리 한 번에 (데스크탑, 도커)

```
docker compose exec -d batch sh -c "python -m embeddings.post_backfill --wait > /app/data/post_backfill.log 2>&1"
docker compose exec batch tail -n 40 /app/data/post_backfill.log
```

순서: 1회차 라벨 복구 → 임베딩 → 홀드아웃(교사 게임 150개를 학생에 **동기 호출**로) →
교사 vs 학생 비교 → Steam 리뷰 수 조회 + 노출 게이트 → 눈검수 샘플.
전 출력은 `data/audit/post_backfill_report.txt`.

홀드아웃을 동기로 돌리는 이유: 같은 12-shot 프롬프트라 결과 품질은 배치와 동일하고,
동기에서만 붙는 프롬프트 캐시 할인(입력 95%가 few-shot 반복)을 **대시보드로 실측**할 수 있다.
실행 전 OpenAI Usage의 오늘 금액을 적어두고, 끝난 뒤 증가분 ÷ 150 = 동기 요청당 단가.
배치 실측 $0.0071/요청과 비교해서 4단계 재개 방식을 정한다.

리뷰 조회(2.5~3h)는 Steam 무료 API. 끝나면 리뷰 수 구간별 분포표가 찍힌다.
게이트 기본 10(Steam이 리뷰 점수를 표시하는 최소치). 분포 보고 바꾸려면 `.env`
`MIN_REVIEWS_FOR_EXPOSURE` 수정 후 `python -m embeddings.refresh_reviews --gate-only`.

---

## 2. 홀드아웃 판정 → 보정 (비용 0)

`post_backfill_report.txt`의 `holdout-compare` 구간에서 세 숫자를 본다:
gem **스피어만 ρ**, gem **편향(학생-교사)**, 수치 49개 중 **MAE>2.5 지표 수**.

**A. ρ ≥ 0.7 이고 |편향| ≤ 8** — 학생은 교사 잣대 유지. 보정 불필요.
  → `recalc_percentile --yes`만 다시 (1회차 999건 편입 반영). 끝.

**B. ρ ≥ 0.7 인데 편향이 크다(예: 학생이 20~30 낮음)** — 순서는 맞고 수준만 다름 = 보정으로 살린다.
  오프라인 비교(offline_compare.txt)가 이 케이스를 예고한다: 상관 구조 r=0.87, 장르 핵심 지표 일치,
  재현성 77% 완전 일치인데 gem 43 vs 76, 연출 계열 1~2점 하향.
  ```
  docker compose exec batch python -m embeddings.calibrate_student --fit
  docker compose exec batch python -m embeddings.calibrate_student --apply --dry-run
  docker compose exec batch python -m embeddings.calibrate_student --apply --yes
  docker compose exec batch python -m embeddings.recalc_percentile --yes
  ```
  `--fit`은 지표별로 학생→교사 선형 매핑을 적합하고, r<0.45(순서 불일치)나 편향 작은 지표는
  자동으로 건너뛴다. `--apply`는 원본을 `student_raw_metrics`에 먼저 보존(멱등, 재적용 시 이중
  보정 없음), `--revert`로 언제든 복원. 파라미터는 `data/audit/calibration_params.json`(커밋).
  보정 후 percentile 재계산이 **필수** — gem 스케일이 바뀌니까.

**C. ρ < 0.5** — 학생이 교사와 다른 걸 보고 있다. 보정 불가.
  8,650건은 서비스 노출을 게이트로 막아둔 채 보존(지우지 않음)하고, 재개는 교사 모델로만.
  기존 8,650건 교사 재분석은 약 $130 — 바로 결정하지 말고 C가 진짜인지 홀드아웃 300건으로
  한 번 더 확인($2)한 뒤.

**어느 경우든 제외할 지표 2개**: `modding_support`(학생 94%가 0), `community_dependency`
(36% 0, 상관 구조 최다 이탈). 보정으로도 못 살린다. 추천 엔진 의도 가중치에서 이 둘이
Primary/Secondary로 쓰이는 곳(recommender.py 149행 근처 `community_dependency`)은 신작
가중치를 0으로 두거나, 학생 라벨 게임에서 이 두 지표를 NULL 폴백 처리하는 게 안전하다.
(코드 수정은 판정 뒤에.)

---

## 3. 서비스 확인 (0원)

- 랭킹/메인 '오늘의 추천'에 신작이 섞여 나오는지, gem 뱃지 받는 신작이 있는지
  (percentile 재계산 뒤 `SELECT COUNT(*) FROM games g JOIN game_metrics m ON m.game_id=g.id
  WHERE g.analysis_method='fewshot_5.4based' AND g.is_active AND m.gem_percentile>=80;` 가 0이면
  2단계가 덜 된 것)
- `data/audit/new_games_sample.csv` 상위/하위 15건 이름·설명·점수 눈검수 (내가 읽고 판단해줄 수 있음)
- 검색 3개: "힐링 농장", "짧은 로그라이크", "위쳐 같은 게임" — 신작 노출 여부

---

## 4. 재개 결정 (여기서만 돈이 나간다)

남은 구간 3/16 ~ 6월 초, 약 5,500건. 단가는 1단계 실측으로 채운다.

| 방식 | 요청당 (실측) | 5,500건 | 품질 |
|---|---|---|---|
| 학생 배치 (지금까지 방식) | $0.0071 | ≈ $39 | 홀드아웃 결과에 따름 |
| 학생 동기+캐시 | 1단계에서 확정 (예상 $0.003~0.005) | ≈ $17~28 | 배치와 **동일** (같은 프롬프트) |
| 교사 배치 (few-shot 없음) | 코드 등록가 기준 ≈ $0.015 — 가격표 재확인 필요 | ≈ $80 | 기준 그 자체 |

재개 명령 (동기 모드 예):
```
docker compose exec batch rm /app/data/STOP_BACKFILL
docker compose exec -d batch sh -c "python -m embeddings.weekly_pipeline --from 2026-03-16 --to 2026-06-10 --limit 500 --loop --sync > /app/data/backfill2.log 2>&1"
```
멈추기는 언제든 `data/STOP_BACKFILL` 파일 생성(컨테이너 밖에서 파일만 만들어도 됨).
동기 모드는 요청이 순차라 500건에 40~60분. 1회차 끝나고 대시보드 증가분이 예상과 맞는지 확인한 뒤 계속.

재개 전 확인: `.env`에 `OPENAI_PRICE_INPUT_PER_M` / `OUTPUT_PER_M`을 가격표에서 확인해 넣어두면
batch_generator 예상 비용이 실제 단가로 찍힌다(지금은 미등록 → 달러 표시 안 함).

---

## 5. 마무리

- `git push` (프로젝트 레포: 커밋 9건, div-log 레포: 1건). embeddings/·docs/만 바뀌어 배포 영향 없음.
- 주간 스케줄 등록은 재개 방식이 정해진 뒤: `scripts/pipeline/setup_weekly_task.ps1`
  (주간은 신작 ~500건, 게이트·리뷰·재평가 단계 포함).
- Railway 배포 실패 알림 켜기, Umami 운영 연결 확인 (이전부터 미완).

---

## 포트폴리오 ⑪에 채울 숫자 (docs/portfolio_raw.md)

이 사건 자체가 스토리다. "싸게 뽑았다"가 아니라 **"싸게 뽑은 데이터가 쓸 수 있는지 어떻게 증명하고, 안 되면 재분석 대신 뭘 했나"**.
- 비용 추정 오류: 추정 $0.85/500 vs 실측 $3.6/500 (단가표 폴백 + 한글 토큰 과소 추정) → 추정기 수정, 실사용량 리포트
- 배치 vs 캐시: 입력 26.5k 중 95%가 반복 few-shot → 배치 50% 할인이 캐시 90% 할인보다 불리한 구조 발견 → 동기 단가 실측값 [채우기]
- 무료 검증으로 먼저 판단: 상관 구조 r=0.869, 장르 핵심 지표 Δ≤0.7, 재현성 77% 완전 일치·gem ±4, 죽은 지표 2개 식별
- 홀드아웃 150쌍 ($1): ρ [채우기], 편향 [채우기], MAE>2.5 지표 [채우기]개 → 판정 [A/B/C]
- 보정(B였다면): 매핑 파라미터, 보정 전/후 신작 gem 상위 20% 진입 수 [채우기], 재분석 대비 절감액 [채우기]
- 원격 킬 스위치: 컨테이너 접근 없이 파일 하나로 detached 루프 정상 종료 (05:50 생성 → 05:52 종료)
