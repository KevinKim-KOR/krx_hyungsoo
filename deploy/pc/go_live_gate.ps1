<#
.SYNOPSIS
    P130: Go-Live Readiness Gate V1
    Determines if the system is ready for the daily manual loop.
.DESCRIPTION
    Read-only check.
    SSOT: ops_summary.manual_loop.stage & top_risks
    Timeout: 5 seconds (Fail-Closed)
    No Token Handling.
.PARAMETER BaseUrl
    OCI Backend URL (Default: Env:KRX_OCI_BASE_URL or http://168.107.51.68:8000)
#>
param (
    [string]$BaseUrl = "$env:KRX_OCI_BASE_URL"
)

if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
    $BaseUrl = "http://168.107.51.68:8000"
}

# Blocked Risk Codes
$BlockingRisks = @(
    "BUNDLE_STALE_WARN",
    "NO_PORTFOLIO",
    "INPUT_BLOCKED",
    "RECORD_LINKAGE_MISMATCH",
    "DUPLICATE_RECORD_BLOCKED",
    "MISSING_DETAIL",
    "MISSING_" # Wildcard-ish check
)

# Ready Stages
$ReadyStages = @(
    "NEED_HUMAN_CONFIRM",
    "PREP_READY",
    "AWAITING_HUMAN_EXECUTION",
    "AWAITING_RECORD_SUBMIT",
    "DONE_TODAY",
    "DONE_TODAY_PARTIAL"
)

Write-Host "Checking Go-Live Readiness..." -NoNewline

# 1. Fetch Summary (Fail-Closed)
try {
    $Summary = Invoke-RestMethod -Uri "$BaseUrl/api/ops/summary/latest" -Method Get -TimeoutSec 5
    Write-Host " OK" -ForegroundColor Green
    
    # Handle Envelope (if rows present)
    if ($Summary.rows) {
        $Root = $Summary.rows[0]
    }
    else {
        $Root = $Summary
    }
}
catch {
    Write-Host " FAIL" -ForegroundColor Red
    Write-Host "GO_LIVE=CHECK_BACKEND NEXT=Check OCI Backend Service" -ForegroundColor Red
    exit 1
}

$Stage = $Root.manual_loop.stage
$Risks = $Root.top_risks
if (-not $Audio) { $Risks = @() } # top_risks might be null or missing

# 2. Risk Analysis
$ComponentsBlocked = @()
foreach ($Risk in $Risks) {
    $Code = $Risk.code
    foreach ($Blocker in $BlockingRisks) {
        if ($Code -eq $Blocker -or ($Blocker -eq "MISSING_" -and $Code.StartsWith("MISSING_"))) {
            $ComponentsBlocked += $Code
        }
    }
}

if ($ComponentsBlocked.Count -gt 0) {
    Write-Host "GO_LIVE=BLOCKED" -ForegroundColor Red
    Write-Host "RISK=$($ComponentsBlocked -join ',')" -ForegroundColor Yellow
    Write-Host "NEXT=Resolve Risks (Run deployment/recovery scripts)" -ForegroundColor White
    exit 0
}

# 3. Stage Analysis
if ($Stage -in $ReadyStages) {
    Write-Host "GO_LIVE=READY" -ForegroundColor Green
    Write-Host "STAGE=$Stage" -ForegroundColor Cyan
    
    # Simple Next Guideline
    $NextCmd = ".\deploy\pc\daily_operator.ps1"
    if ($Stage -eq "NEED_HUMAN_CONFIRM") { $Next = "Run Prep" }
    elseif ($Stage -eq "PREP_READY") { $Next = "Generate Ticket" }
    elseif ($Stage -eq "AWAITING_HUMAN_EXECUTION") { $Next = "Manual Execution" }
    elseif ($Stage -eq "AWAITING_RECORD_SUBMIT") { $Next = "Push Draft" }
    elseif ($Stage -like "DONE_*") { $Next = "None (Done)" }
    else { $Next = "Check Dashboard" }
    
    Write-Host "NEXT=$Next ($NextCmd)" -ForegroundColor White
}
else {
    Write-Host "GO_LIVE=HELD" -ForegroundColor Yellow
    Write-Host "STAGE=$Stage (Not in Ready List)" -ForegroundColor Yellow
    Write-Host "NEXT=Check Ops Summary for details" -ForegroundColor White
}

exit 0
