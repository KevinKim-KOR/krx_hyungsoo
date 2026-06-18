# run_three_push_sync_task.ps1
# 용도: Windows Task Scheduler에서 호출하는 PC → OCI 3-PUSH package sync wrapper.
# 사용처: docs/handoff/PC_THREE_PUSH_SYNC_TASKSCHEDULER.md 참조.
# 동작:
#   1. 프로젝트 루트로 이동
#   2. .venv Python으로 scripts/sync_three_push_packages.py 실행
#   3. stdout/stderr를 logs/three_push_sync_task.log에 append
#   4. 실패 시 non-zero exit code 반환 (Task Scheduler에서 실패 인지 가능)

# 주의: sync 스크립트가 INFO 로그를 stderr로 출력한다.
# PS 5.1에서는 pipeline 내 `2>&1`이 native stderr 줄을 ErrorRecord로 wrapping하여
# $ErrorActionPreference="Stop" 와 결합하면 정상 INFO 로그가 종료 예외를 유발한다.
# 따라서 ErrorActionPreference는 기본값(Continue)을 유지하고,
# 출력은 `*>` (모든 stream을 파일로 redirect) 로 캡처해 ErrorRecord wrapping을 우회한다.
# `*>` 는 stdout과 stderr를 모두 동일 파일로 보낸다 — 두 stream 모두 보존 목적.

# 프로젝트 루트 = 이 스크립트 위치의 상위 디렉토리
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$SyncScript = Join-Path $ProjectRoot "scripts\sync_three_push_packages.py"
$LogDir = Join-Path $ProjectRoot "logs"
$LogFile = Join-Path $LogDir "three_push_sync_task.log"

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

$Timestamp = Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz"
Add-Content -Path $LogFile -Value "===== [$Timestamp] sync task 시작 ====="

if (-not (Test-Path $VenvPython)) {
    $msg = "[$Timestamp] ERROR: venv python not found at $VenvPython"
    Add-Content -Path $LogFile -Value $msg
    exit 2
}

if (-not (Test-Path $SyncScript)) {
    $msg = "[$Timestamp] ERROR: sync script not found at $SyncScript"
    Add-Content -Path $LogFile -Value $msg
    exit 3
}

# `*>` 는 stdout/stderr/모든 stream을 동일 파일로 redirect한다.
# (PS 5.1 NativeCommandError 회피를 위해 `2>&1` 대신 사용 — 위 주석 참조.)
$RunLog = $LogFile.Replace(".log", "_run.log")
& $VenvPython $SyncScript *> $RunLog
$ExitCode = $LASTEXITCODE
Get-Content $RunLog -ErrorAction SilentlyContinue | Add-Content -Path $LogFile

$Timestamp = Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz"
Add-Content -Path $LogFile -Value "===== [$Timestamp] sync task 종료 exit_code=$ExitCode ====="
exit $ExitCode
