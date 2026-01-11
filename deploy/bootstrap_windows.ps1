# =============================================================================
# KRX Alertor Modular - Bootstrap Script (Windows)
# Phase C-P.39: Deployment Profile Lock
# =============================================================================
# 용도: venv 생성, 의존성 설치, 헬스체크, DRY_RUN ops 1회 실행
# 실패 시 exit code != 0
# =============================================================================

param(
    [switch]$SkipOps  # Ops Cycle DRY_RUN 스킵 옵션
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " KRX Alertor Modular - Bootstrap" -ForegroundColor Cyan
Write-Host " v1.0-golden" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. Working directory 확인
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
Write-Host "[1/5] Project root: $ProjectRoot" -ForegroundColor Green

# 2. Python 버전 확인
Write-Host "[2/5] Checking Python version..." -ForegroundColor Yellow
try {
    $pythonVersion = py -3 --version 2>&1
    Write-Host "  Python: $pythonVersion" -ForegroundColor Green
}
catch {
    Write-Host "  ERROR: Python 3 not found. Install Python 3.10+" -ForegroundColor Red
    exit 1
}

# 3. venv 생성/활성화
Write-Host "[3/5] Setting up virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path ".venv")) {
    Write-Host "  Creating .venv..." -ForegroundColor Yellow
    py -3 -m venv .venv
}
Write-Host "  Activating .venv..." -ForegroundColor Green
& ".\.venv\Scripts\Activate.ps1"

# 4. 의존성 설치
Write-Host "[4/5] Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: pip install failed" -ForegroundColor Red
    exit 1
}
Write-Host "  Dependencies installed." -ForegroundColor Green

# 5. Backend 시작 (백그라운드) + Health Check
Write-Host "[5/5] Starting backend for health check..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    param($root)
    Set-Location $root
    & ".\.venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
} -ArgumentList $ProjectRoot

Start-Sleep -Seconds 5

# Health Check
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/ops/health" -Method GET -TimeoutSec 10
    Write-Host "  Health Check: OK" -ForegroundColor Green
}
catch {
    Write-Host "  Health Check: FAILED (backend may not be running)" -ForegroundColor Red
    Stop-Job $backendJob -ErrorAction SilentlyContinue
    exit 1
}

# 6. DRY_RUN Ops Cycle (선택)
if (-not $SkipOps) {
    Write-Host "[Bonus] Running DRY_RUN Ops Cycle..." -ForegroundColor Yellow
    try {
        $opsResult = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/ops/cycle/run" -Method POST -TimeoutSec 30
        Write-Host "  Ops Cycle: $($opsResult.overall_status)" -ForegroundColor Green
    }
    catch {
        Write-Host "  Ops Cycle: FAILED" -ForegroundColor Red
    }
}

# Cleanup
Stop-Job $backendJob -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Bootstrap Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Start backend: uvicorn backend.main:app --host 0.0.0.0 --port 8000"
Write-Host "  2. Open dashboard: http://localhost:8000/dashboard/"
Write-Host "  3. Register scheduler: See docs/ops/runbook_deploy_v1.md"
Write-Host ""

exit 0
