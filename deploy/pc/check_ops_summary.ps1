# check_ops_summary.ps1 - PC Ops Summary Check Script (D-P.53)
# Usage: .\deploy\pc\check_ops_summary.ps1
# Exit codes: 0=OK (even if WARN), 3=API/JSON/resolve error

param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function Write-Step($step, $total, $msg) {
    Write-Host "[$step/$total] $msg" -ForegroundColor Cyan
}

# Step 1: Regenerate
Write-Step 1 3 "Regenerating Ops Summary..."
try {
    $regen = Invoke-RestMethod -Uri "$BaseUrl/api/ops/summary/regenerate?confirm=true" -Method POST
}
catch {
    Write-Host "❌ Regenerate API failed: $_" -ForegroundColor Red
    exit 3
}

# Step 2: Get latest
Write-Step 2 3 "Fetching latest summary..."
try {
    $latest = Invoke-RestMethod -Uri "$BaseUrl/api/ops/summary/latest" -Method GET
}
catch {
    Write-Host "❌ Latest API failed: $_" -ForegroundColor Red
    exit 3
}

# Step 3: Parse
Write-Step 3 3 "Validating summary..."
$row = if ($latest.rows) { $latest.rows[0] } else { $latest }
if (-not $row) {
    Write-Host "❌ No summary found" -ForegroundColor Red
    exit 3
}

$overall = $row.overall_status
$guard = $row.guard
$eh = if ($guard) { $guard.evidence_health } else { @{} }
$ehDecision = if ($eh) { $eh.decision } else { "UNKNOWN" }
$ehSnapshotRef = if ($eh) { $eh.snapshot_ref } else { $null }

$tr = $row.tickets_recent
$trFailed = if ($tr) { $tr.failed } else { 0 }
$trExcluded = if ($tr) { $tr.excluded_cleanup_failed } else { 0 }

$risks = $row.top_risks
$riskCodes = if ($risks) { $risks | ForEach-Object { $_.code } } else { @() }

# Step 4: Verify snapshot_ref
if ($ehSnapshotRef) {
    Write-Step 4 4 "Verifying evidence_health.snapshot_ref..."
    try {
        $evidence = Invoke-WebRequest -Uri "$BaseUrl/api/evidence/resolve?ref=$ehSnapshotRef" -Method GET -UseBasicParsing
        if ($evidence.StatusCode -ne 200) {
            Write-Host "❌ Evidence resolve failed: HTTP $($evidence.StatusCode)" -ForegroundColor Red
            exit 3
        }
        $ehResolve = "OK"
    }
    catch {
        Write-Host "❌ Evidence resolve failed: $_" -ForegroundColor Red
        exit 3
    }
}
else {
    $ehResolve = "N/A"
}

# Summary
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Yellow
Write-Host "OPS: $overall | health=$ehDecision | snapshot=$ehResolve" -ForegroundColor Green
Write-Host "tickets_recent: failed=$trFailed excluded=$trExcluded" -ForegroundColor Green
Write-Host "top_risks: $($riskCodes -join ', ')" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Yellow

Write-Host "✅ PASS: All checks passed" -ForegroundColor Green
exit 0
