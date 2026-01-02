# deploy/run_daily.ps1
# KRX Alertor Modular - Daily Automation Script (Windows/PowerShell)

# [운영 규칙 / Operational Rules]
# 1. 실행 시간: KST 15:40 ~ 16:30 (종가 확정 후 실행 필수)
# 2. No-Op 원칙: 신호가 0건이어도 중단하지 않음.
# 3. 장애 복구: 재실행 시 python -m tools.paper_trade_phase9 --force 사용.

$ErrorActionPreference = "Stop"

$TODAY = Get-Date -Format "yyyyMMdd"
$LOG_DIR = "logs"
$LOG_FILE = "$LOG_DIR/daily_$TODAY.log"

if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Force -Path $LOG_DIR | Out-Null
}

function Log-Output {
    param([string]$Message)
    $TimeStamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $Line = "[$TimeStamp] $Message"
    Write-Output $Line
    Add-Content -Path $LOG_FILE -Value $Line -Encoding UTF8
}

Log-Output "========================================================"
Log-Output "Phase 9 Daily Run START"

# Rule Check
$CurrentHour = (Get-Date).Hour
Log-Output "[RULE Check] Ensure current time is between 15:40 ~ 16:30 KST (Current Hour: $CurrentHour)"

# Step 1: Signal Generation
Log-Output ">>> [Step 1] Generating Signals..."
try {
    # Using python directly. Ensure python is in path.
    # Capturing output is tricky without losing color, but tee-object works for streams.
    # Here we just run it. If it fails, catch block catches it due to ErrorActionPreference? 
    # Actually external commands don't trigger try/catch automatically unless check $LASTEXITCODE.
    
    python -m app.cli.alerts scan --strategy phase9 --config config/production_config.yaml | Tee-Object -FilePath $LOG_FILE -Append
    if ($LASTEXITCODE -ne 0) { throw "Step 1 Failed with exit code $LASTEXITCODE" }
    Log-Output "[Step 1] Success."
}
catch {
    Log-Output "[Step 1] FAILED. $_"
    exit 1
}

# Step 2: Execution
Log-Output ">>> [Step 2] Executing Paper Trade..."
try {
    python -m tools.paper_trade_phase9 | Tee-Object -FilePath $LOG_FILE -Append
    if ($LASTEXITCODE -ne 0) { throw "Step 2 Failed with exit code $LASTEXITCODE" }
    Log-Output "[Step 2] Success."
}
catch {
    Log-Output "[Step 2] FAILED. $_"
    exit 1
}

Log-Output "Daily Run COMPLETED Successfully."
Log-Output "========================================================"
