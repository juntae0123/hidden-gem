# ============================================================
# Hidden Gem 주간 파이프라인 실행기 (Task Scheduler 가 호출)
# 9/13·9/20 실행이 'service "batch" is not running' 으로 조용히 실패했다 (R-27).
#   원인: 'docker compose exec' 는 batch 컨테이너가 떠 있어야만 동작.
#   대책: Docker 엔진이 뜰 때까지 기다린 뒤 'docker compose run --rm' 으로 일회성 컨테이너에서 실행.
# 실패하면 exit 1 -> 스케줄러 RestartCount 가 30분 뒤 재시도한다.
# ============================================================
$ErrorActionPreference = "Continue"
$ProjectDir = "C:\Hidden-Gem-project"
$LogPath    = "$ProjectDir\logs\weekly_task.log"
Set-Location $ProjectDir
New-Item -ItemType Directory -Force -Path "$ProjectDir\logs" | Out-Null

function Log($msg) { "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg | Out-File -Append -Encoding utf8 $LogPath }

Log "=== weekly run start ==="

# 1) Docker 엔진 확인 — 꺼져 있으면 Docker Desktop 을 띄우고 최대 10분 대기
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $dd = "$Env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dd) { Log "Docker 꺼져 있음 -> Docker Desktop 시작"; Start-Process $dd }
    $ok = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 10
        docker info *> $null
        if ($LASTEXITCODE -eq 0) { $ok = $true; break }
    }
    if (-not $ok) { Log "FAIL: Docker 엔진이 10분 안에 뜨지 않음"; exit 1 }
}
Log "docker ok"

# 2) 일회성 batch 컨테이너에서 파이프라인 실행 (컨테이너가 떠 있을 필요 없음)
# PowerShell 5.1 의 *>> 는 UTF-16 으로 써서 로그가 깨진다 -> cmd 리다이렉트
cmd.exe /c "docker compose run --rm -T batch python -m embeddings.weekly_pipeline >> `"$LogPath`" 2>&1"
$code = $LASTEXITCODE
Log "=== weekly run end (exit $code) ==="
exit $code
