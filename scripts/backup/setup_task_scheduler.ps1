# ============================================================
# Hidden Gem Windows Task Scheduler 등록 스크립트
# 위치: C:\Hidden-Gem-project\scripts\setup_task_scheduler.ps1
#
# WSL cron보다 Windows에서 더 안정적.
# 관리자 권한으로 실행 필요.
#
# 실행:
#   PowerShell -ExecutionPolicy Bypass -File scripts\setup_task_scheduler.ps1
# ============================================================

$TaskName = "HiddenGem_DB_Backup"
$ProjectDir = "C:\Hidden-Gem-project"
$ScriptPath = "$ProjectDir\scripts\backup_db.sh"
$LogPath = "$ProjectDir\backups\cron.log"

# 기존 태스크 제거 (중복 방지)
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "기존 태스크 제거됨"
}

# Git Bash 경로 확인
$GitBash = "C:\Program Files\Git\bin\bash.exe"
if (-not (Test-Path $GitBash)) {
    $GitBash = "C:\Program Files (x86)\Git\bin\bash.exe"
}
if (-not (Test-Path $GitBash)) {
    Write-Error "Git Bash를 찾을 수 없음. Git for Windows 설치 필요."
    exit 1
}

# 백업 디렉토리 생성
New-Item -ItemType Directory -Force -Path "$ProjectDir\backups" | Out-Null

# 태스크 액션 정의 (Git Bash로 쉘 스크립트 실행)
$Action = New-ScheduledTaskAction `
    -Execute $GitBash `
    -Argument "-c `"bash '$ScriptPath' >> '$LogPath' 2>&1`"" `
    -WorkingDirectory $ProjectDir

# 매일 새벽 3시 실행
$Trigger = New-ScheduledTaskTrigger -Daily -At "03:00AM"

# 설정 (컴퓨터 켜져 있을 때만, 배터리 모드도 실행)
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 10) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false

# 태스크 등록
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -RunLevel Highest `
    -Description "Hidden Gem PostgreSQL 일일 백업" | Out-Null

Write-Host ""
Write-Host "============================="
Write-Host " 태스크 등록 완료!"
Write-Host "============================="
Write-Host "이름: $TaskName"
Write-Host "실행: 매일 새벽 3:00 AM"
Write-Host "로그: $LogPath"
Write-Host ""
Write-Host "즉시 테스트:"
Write-Host "  & '$GitBash' -c `"bash '$ScriptPath'`""
Write-Host ""
Write-Host "태스크 확인:"
Write-Host "  Get-ScheduledTask -TaskName '$TaskName'"