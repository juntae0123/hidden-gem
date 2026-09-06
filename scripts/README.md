# scripts/ — 운영 스크립트 (스케줄러·백업·이미지)

데이터 파이프라인 본체는 `embeddings/` 로 옮겨갔다(2026-08~). 여기는 **호스트(Windows)에서 도는 것**과 일회성 운영 도구만 남긴다.
실행 위치는 프로젝트 루트.

```
scripts/
├── pipeline/
│   └── setup_weekly_task.ps1   Windows Task Scheduler 등록 — 매주 월 03:30
│                               `docker compose exec -T batch python -m embeddings.weekly_pipeline` (기본 대상: 운영 DB)
│                               등록: PowerShell -ExecutionPolicy Bypass -File scripts\pipeline\setup_weekly_task.ps1
├── backup/
│   ├── backup_db.sh            pg_dump → gzip, 7일 로테이션 (backups/ 는 gitignore)
│   ├── setup_task_scheduler.ps1  Windows 스케줄 등록 (권장)
│   └── setup_cron.sh           WSL/Linux cron
└── images/                     Steam 헤더 이미지 일회성 보정
    ├── fill_header_images.py   CDN URL 일괄 생성
    ├── verify_header_images.py HEAD 요청으로 404 탐지
    └── fix_failed_headers.py   Steam API 로 URL 복구
```

옛 1세대 배치 파이프라인(make_diet_batch → split → submit → check → download → combine → merge → validate → fix → load_embeddings)은
`legacy/scripts_pipeline_v1/` 로 이동했다. 현재 흐름은 `embeddings/README.md`.
