# legacy/ — 더 이상 실행하지 않는 코드·산출물 (참고용 보존)

지우지 않고 옮겨둔다(데이터·이력은 삭제하지 않는다는 프로젝트 원칙). 실행되지 않고 어디서도 import 되지 않는다.

| 폴더 | 무엇 | 대체 |
|---|---|---|
| `_legacy_backend/` | 3~5월 초기 백엔드 | `fastapi_app/` + `django_core/` |
| `legacy_fastapi_app/` | 이중 구조 이전 FastAPI | `fastapi_app/` |
| `frontend/` | 초기 프런트 (node_modules 는 gitignore) | `frontend/` (Next.js 16) |
| `scripts_pipeline_v1/` | 1세대 배치 파이프라인(2-패스 60컬럼 구축용 10개 스크립트) + 옛 README | `embeddings/weekly_pipeline.py` 계열 |
| `embeddings_v1/` | 8월 말 배치 도구 초판(auto_batch_sender·batch_merger·split_batch·db_updator·smoke test·.bak) + `history/`(3월 수집기) | `embeddings/batch_generator.py`·`batch_processor.py` |
| `fastapi_scripts_v6/` | score_v6 변별력 검증·Vibe 분포 점검 스크립트(8~9월 초) | `fastapi_app/scripts/ablation.py`, `embeddings/rec_snapshot.py` |
| `div_log_early/` | 3월 개발 노트 3개 | 별도 저장소 `div-log_hidden-gem` |
| `root_artifacts/` | 초기 명세 노트북, 설치 노트북, 스크린샷, 업로드 로그, 3월 db dump(131B), project_way.md | `PRD_v4.2.3.md`, `docs/` |

2026-09-06 정리 (R-18 이후). 새로 은퇴시키는 코드는 여기 폴더를 만들고 이 표에 한 줄 추가한다.
