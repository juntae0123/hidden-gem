#!/bin/bash
# ============================================================
# Hidden Gem DB 백업 스크립트
# 위치: /c/Hidden-Gem-project/scripts/backup_db.sh
#
# 기능:
#   1. pg_dump → gzip 압축 → /backup/ 저장
#   2. 7일 이상 된 로컬 백업 자동 삭제
#   3. 성공/실패 로그 기록
#   4. (선택) Discord 웹훅 알람
#
# 실행:
#   bash scripts/backup_db.sh
#   bash scripts/backup_db.sh --notify  # Discord 알람 포함
# ============================================================

set -euo pipefail

# ==================== 설정 / Config ====================

DB_CONTAINER="hidden_gem_db"
DB_USER="juntae"
DB_NAME="hidden_gem_db"

BACKUP_DIR="/c/Hidden-Gem-project/backups"
LOG_FILE="${BACKUP_DIR}/backup.log"
RETENTION_DAYS=7                         # 로컬 보관 기간 (일)

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/db_${DATE}.sql.gz"

# Discord 웹훅 (선택, .env에서 주입 가능)
DISCORD_WEBHOOK="${DISCORD_WEBHOOK_URL:-}"

# ==================== 유틸 / Utils ====================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

notify_discord() {
    local message="$1"
    local emoji="$2"
    if [ -n "${DISCORD_WEBHOOK}" ]; then
        curl -s -X POST "${DISCORD_WEBHOOK}" \
            -H "Content-Type: application/json" \
            -d "{\"content\": \"${emoji} **[Hidden Gem 백업]** ${message}\"}" \
            > /dev/null 2>&1 || true
    fi
}

# ==================== 메인 / Main ====================

# 백업 디렉토리 생성
mkdir -p "${BACKUP_DIR}"

log "===== 백업 시작 ====="
log "대상: ${DB_CONTAINER} / ${DB_NAME}"
log "저장: ${BACKUP_FILE}"

# Docker 컨테이너 실행 중인지 확인
if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
    log "❌ 오류: Docker 컨테이너 '${DB_CONTAINER}'가 실행 중이지 않음"
    notify_discord "백업 실패: DB 컨테이너 미실행" "🚨"
    exit 1
fi

# pg_dump 실행
if docker exec "${DB_CONTAINER}" \
    pg_dump -U "${DB_USER}" "${DB_NAME}" \
    | gzip > "${BACKUP_FILE}"; then

    # 파일 크기 확인
    FILE_SIZE=$(du -sh "${BACKUP_FILE}" | cut -f1)
    log "✅ 백업 성공: ${BACKUP_FILE} (${FILE_SIZE})"
    notify_discord "백업 성공 — ${FILE_SIZE} (${DATE})" "✅"
else
    log "❌ 백업 실패"
    notify_discord "백업 실패! 즉시 확인 필요" "🚨"
    rm -f "${BACKUP_FILE}"  # 불완전한 파일 제거
    exit 1
fi

# 오래된 백업 삭제 (RETENTION_DAYS일 이상)
DELETED=$(find "${BACKUP_DIR}" -name "db_*.sql.gz" \
    -mtime +${RETENTION_DAYS} -print -delete | wc -l)

if [ "${DELETED}" -gt 0 ]; then
    log "🗑️  오래된 백업 ${DELETED}개 삭제 (${RETENTION_DAYS}일 초과)"
fi

log "===== 백업 완료 ====="