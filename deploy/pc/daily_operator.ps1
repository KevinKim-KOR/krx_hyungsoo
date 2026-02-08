<#
.SYNOPSIS
    P129: PC Daily Operator Orchestrator V1
    One-Command Interface for Daily Operations.
.DESCRIPTION
    1. Checks Backend Status (Fail-Closed).
    2. Optional: Publishes Bundle.
    3. Pulls Operator Pack (SSOT Sync).
    4. Displays ONE clear Next Action.
    NO TOKEN HANDLING.
.PARAMETER PullPack
    Download artifacts (Default: $true)
.PARAMETER PublishBundle
    Run publish_bundle.ps1 (Default: $false)
.PARAMETER BaseUrl
    OCI Backend URL (Default: Env:KRX_OCI_BASE_URL or http://168.107.51.68:8000)
#>
param (
    [bool]$PullPack = $true,
    [switch]$PublishBundle,
    [string]$BaseUrl = "$env:KRX_OCI_BASE_URL"
)

if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
    $BaseUrl = "http://168.107.51.68:8000"
}

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "   🚀 DAILY OPERATOR ORCHESTRATOR" -ForegroundColor Cyan
Write-Host "   Backend: $BaseUrl" -ForegroundColor Gray
Write-Host "==================================================="

# 1. Check Backend (Fail-Closed)
Write-Host "Checking Backend Status..." -NoNewline
try {
    $Dashboard = Invoke-RestMethod -Uri "$BaseUrl/api/operator/dashboard" -Method Get -TimeoutSec 5
    Write-Host " ONLINE" -ForegroundColor Green
}
catch {
    Write-Host " OFFLINE / TIMEOUT" -ForegroundColor Red
    Write-Error "CHECK_BACKEND: Unable to reach OCI Dashboard. Aborting."
    exit 1
}

$Stage = $Dashboard.stage
$AsOf = $Dashboard.asof
Write-Host "STAGE : [$Stage]" -ForegroundColor Yellow
Write-Host "AS OF : $AsOf" -ForegroundColor DarkGray
Write-Host "---------------------------------------------------"

# 2. Publish Bundle (Optional)
if ($PublishBundle) {
    Write-Host ">> Executing Bundle Publish..." -ForegroundColor Cyan
    .\deploy\pc\publish_bundle.ps1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Bundle Publish Failed. Aborting."
        exit 1
    }
    Write-Host "Bundle Publish Complete." -ForegroundColor Green
    Write-Host "---------------------------------------------------"
}

# 3. Pull Operator Pack
if ($PullPack) {
    Write-Host ">> Syncing Operator Pack..." -ForegroundColor Cyan
    .\deploy\pc\pull_operator_pack.ps1 -BaseUrl $BaseUrl
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Pack Pull Failed. Aborting."
        exit 1
    }
    Write-Host "---------------------------------------------------"
}

# 4. Next Action Guidance
Write-Host "🎯 NEXT ACTION REQUIRED:" -ForegroundColor Cyan

switch ($Stage) {
    "NEED_HUMAN_CONFIRM" {
        Write-Host "   1. SSH into OCI" -ForegroundColor White
        Write-Host "   2. Run Prep Script (Requires Token)" -ForegroundColor White
        Write-Host "   Command: bash deploy/oci/manual_loop_prepare.sh" -ForegroundColor Green
    }
    "PREP_READY" {
        Write-Host "   1. SSH into OCI" -ForegroundColor White
        Write-Host "   2. Generate Ticket (or re-run prep)" -ForegroundColor White
        Write-Host "   Command: bash deploy/oci/manual_loop_prepare.sh" -ForegroundColor Green
    }
    "AWAITING_HUMAN_EXECUTION" {
        Write-Host "   1. Open Ticket (in local/operator_pack/...)" -ForegroundColor White
        Write-Host "   2. Execute Trades Manually in HTS/MTS" -ForegroundColor White
        Write-Host "   3. When Done -> Generate Record Draft" -ForegroundColor White
    }
    "AWAITING_RECORD_SUBMIT" {
        Write-Host "   1. Generate Record Draft (if not done)" -ForegroundColor White
        Write-Host "      Command: .\deploy\pc\generate_record_template.ps1" -ForegroundColor Green
        Write-Host "   2. Push & Submit" -ForegroundColor White
        Write-Host "      Command: .\deploy\pc\daily_manual_loop.ps1 -DoPushDraft -DoSubmit" -ForegroundColor Green
    }
    "DONE_TODAY" {
        Write-Host "   ✅ Daily Cycle Complete." -ForegroundColor Green
        Write-Host "   No further action required." -ForegroundColor White
    }
    "DONE_TODAY_PARTIAL" {
        Write-Host "   ⚠️  Partial Execution." -ForegroundColor Yellow
        Write-Host "   Review Ops Summary." -ForegroundColor White
    }
    Default {
        Write-Host "   UNKNOWN STAGE. Please check Ops Summary manually." -ForegroundColor Red
        Write-Host "   Command: .\deploy\pc\daily_manual_loop.ps1" -ForegroundColor Gray
    }
}

Write-Host "==================================================="
exit 0
