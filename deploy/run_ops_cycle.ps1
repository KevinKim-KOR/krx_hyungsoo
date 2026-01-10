# deploy/run_ops_cycle.ps1
# Ops Cycle 실행 스크립트 (Windows PowerShell)
# Phase C-P.27

param(
    [string]$ApiBase = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

Write-Host "[OPS_CYCLE] Starting Ops Cycle Run..." -ForegroundColor Cyan
Write-Host "[OPS_CYCLE] API Base: $ApiBase" -ForegroundColor Gray

try {
    $response = Invoke-RestMethod -Uri "$ApiBase/api/ops/cycle/run" -Method POST -ContentType "application/json"
    
    Write-Host "[OPS_CYCLE] Response:" -ForegroundColor Green
    $response | ConvertTo-Json -Depth 10 | Write-Host
    
    $overallStatus = $response.overall_status
    
    if ($overallStatus -in @("DONE", "STOPPED", "SKIPPED")) {
        Write-Host "[OPS_CYCLE] Completed with status: $overallStatus" -ForegroundColor Green
        exit 0
    }
    else {
        Write-Host "[OPS_CYCLE] Completed with status: $overallStatus" -ForegroundColor Yellow
        exit 1
    }
}
catch {
    Write-Host "[OPS_CYCLE] Error: $_" -ForegroundColor Red
    exit 1
}
