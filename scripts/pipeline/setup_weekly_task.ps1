# ============================================================
# Hidden Gem 주간 신작 파이프라인 - Windows Task Scheduler 등록
# 위치: C:\Hidden-Gem-project\scripts\pipeline\setup_weekly_task.ps1
#
# 매주 월요일 03:30에 embeddings.weekly_pipeline 실행.
# OpenAI Batch 대기 시간(최대 24h)을 감안해 실행 제한을 26시간으로 둔다.
# 관리자 권한 PowerShell에서 실행.
#
# 실행:
#   PowerShell -ExecutionPolicy Bypass -File scripts\pipeline\setup_weekly_task.ps1
# ============================================================

$TaskName   = "HiddenGem_Weekly_Ingest"
$ProjectDir = "C:\Hidden-Gem-project"
$LogPath    = "$ProjectDir\logs\weekly_task.log"

# 파이프라인은 batch 컨테이너에서 실행 (의존성이 그 이미지에 있음)
# 전제: 실행 시각에 Docker Desktop이 켜져 있어야 함 (설정 > 로그인 시 시작 권장)

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "기존 태스크 제거됨"
}

New-Item -ItemType Directory -Force -Path "$ProjectDir\logs" | Out-Null

$Action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"docker compose exec -T batch python -m embeddings.weekly_pipeline >> `"$LogPath`" 2>&1`"" `
    -WorkingDirectory $ProjectDir

$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "03:30AM"

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 26) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 30) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Hidden Gem 주간 신작 수집/분석/적재 파이프라인"

Write-Host ""
Write-Host "등록 완료: $TaskName (매주 월요일 03:30)"
Write-Host "수동 테스트: Start-ScheduledTask -TaskName $TaskName"
Write-Host "로그: $LogPath"
