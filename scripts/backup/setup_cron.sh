#!/bin/bash
# ============================================================
# Hidden Gem cron 등록 스크립트
# 위치: /c/Hidden-Gem-project/scripts/setup_cron.sh
#
# Windows에서는 Git Bash 또는 WSL에서 실행.
# WSL cron 사용 (Windows Task Scheduler 대안).
#
# 실행:
#   bash scripts/setup_cron.sh
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRIPT="${SCRIPT_DIR}/backup_db.sh"

# 스크립트 실행 권한 부여
chmod +x "${BACKUP_SCRIPT}"

echo "========================================="
echo " Hidden Gem Cron 등록"
echo "========================================="

# ==================== WSL 환경 체크 ====================
if grep -qi microsoft /proc/version 2>/dev/null; then
    echo "환경: WSL 감지됨"
    CRON_ENV="WSL"
elif [ "$(uname -s)" = "Linux" ]; then
    echo "환경: Linux"
    CRON_ENV="Linux"
else
    echo "환경: Git Bash / Windows"
    CRON_ENV="Windows"
fi

# ==================== Crontab 등록 ====================

# 기존 Hidden Gem cron 제거 후 재등록 (중복 방지)
CRON_MARKER="# Hidden Gem"

# 기존 항목 제거
EXISTING=$(crontab -l 2>/dev/null || echo "")
CLEANED=$(echo "${EXISTING}" | grep -v "${CRON_MARKER}" | grep -v "backup_db.sh")

# 새 항목 추가
NEW_CRON="${CLEANED}
${CRON_MARKER} — DB 백업 (매일 새벽 3시)
0 3 * * * bash ${BACKUP_SCRIPT} >> /c/Hidden-Gem-project/backups/cron.log 2>&1
"

echo "${NEW_CRON}" | crontab -

echo ""
echo "✅ Cron 등록 완료:"
crontab -l | grep -A1 "${CRON_MARKER}"
echo ""
echo "확인 명령어:"
echo "  crontab -l                    # 등록된 cron 목록"
echo "  bash ${BACKUP_SCRIPT}         # 수동 즉시 실행 테스트"
echo "  tail -f /c/Hidden-Gem-project/backups/backup.log  # 로그 확인"