# docs/ — 설계·결정·실측 기록

**읽는 순서(새 세션)**: 루트 `CLAUDE.md` → `decisions_0905.md` → `ablation_result_0905.md` → `system_invariants.md`.

| 문서 | 내용 |
|---|---|
| `decisions_0905.md` | 결정 R-1~R-26 (v7 공식, gem 증거 전환, 생애주기·신작 리그, 랭킹 정렬, 토글, 운영 정합). 왜 그렇게 했는지의 원본 |
| `ablation_result_0905.md` | 절제 실측 1~4회차·스냅샷 diff(s4→s7). **예측을 먼저 적고 틀린 것을 기록** |
| `system_invariants.md` | 깨면 안 되는 것·서로 충돌하는 것 C-1~C-17, 실수 분류 A~G, 변경 전 체크리스트 |
| `final_verdict_0905.md` | D-26(장르 핵심 목표값 5.0 상수) 발견과 최종 판단 |
| `scoring_mechanism_asis.md` | 점수 메커니즘 as-is (D-1~D-26, 세 경로 mermaid) — 외부 검토 입력용 보조 문서 |
| `self_feedback_0905.md` | PRD 대비 셀프 피드백 (경로 B 가 PRD 공식, v6 는 PRD 에 없음 등) |
| `lifecycle_split_spec_0905.md` | 신작/정착/유명 분리 명세 — 랭킹 3종·신작 리그·프런트 |
| `metric_audit_0905.md` | 지표 63개 감사(PCA·상관·측정 가능성) + 개발자 판단(합치지 않음, 앵커 분리·축 추가) |
| `external_review_log_0904.md` / `external_review_prompt*.md` | 외부 AI 검토 원문·판정(1차 3건, 2차 21건) / 검토 요청 프롬프트(소스 원문 우선) |
| `code_review_0904.md`, `security_review.md` | 코드·보안 점검 |
| `backfill_runbook_0904.md`, `gem_transition_plan.md`, `apply_guide.md` | 백필 실행서, gem 전환 계획, 배포 적용 가이드 |
| `design_improvements.md` | 프런트 개선 노트 |
| `images/` | README 화면 캡처 |

숫자는 실측만 적는다(대시보드·스냅샷·절제 출력). 추정은 "추정"이라고 쓴다.

개인 작업 문서는 이 저장소에 두지 않는다 — 저장소는 코드와 설계·실측 기록만 공개한다.
