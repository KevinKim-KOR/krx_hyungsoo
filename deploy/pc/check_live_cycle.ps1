# check_live_cycle.ps1 - PC용 Live Cycle Check Script (D-P.51)
# Usage: .\deploy\pc\check_live_cycle.ps1
# Exit codes: 0=PASS, 2=snapshot_ref mismatch, 3=API/JSON error

param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function Write-Step($step, $msg) {
    Write-Host "[$step/4] $msg" -ForegroundColor Cyan
}

# Step 1: Run Live Cycle
Write-Step 1 "Running Live Cycle..."
try {
    $runResp = Invoke-RestMethod -Uri "$BaseUrl/api/live/cycle/run?confirm=true" -Method POST
}
catch {
    Write-Host "❌ API call failed: $_" -ForegroundColor Red
    exit 3
}

# Step 2: Get latest receipt
Write-Step 2 "Fetching latest receipt..."
try {
    $latest = Invoke-RestMethod -Uri "$BaseUrl/api/live/cycle/latest" -Method GET
}
catch {
    Write-Host "❌ Latest API call failed: $_" -ForegroundColor Red
    exit 3
}

# Step 3: Parse and validate
Write-Step 3 "Validating receipt..."
$row = $latest.rows[0]
if (-not $row) {
    Write-Host "❌ No receipt found" -ForegroundColor Red
    exit 3
}

$result = $row.result
$decision = $row.decision
$bundle = $row.bundle
$reco = $row.reco
$push = $row.push
$snapshotRef = $row.snapshot_ref

$bundleDecision = if ($bundle) { $bundle.decision } else { "UNKNOWN" }
$bundleStale = if ($bundle) { $bundle.stale.ToString().ToLower() } else { "true" }
$recoDecision = if ($reco) { $reco.decision } else { "UNKNOWN" }
$delivery = if ($push) { $push.delivery_actual } else { "UNKNOWN" }

# Step 4: Verify snapshot_ref
Write-Step 4 "Verifying snapshot_ref..."
if (-not $snapshotRef) {
    Write-Host "❌ snapshot_ref is null/empty" -ForegroundColor Red
    exit 2
}

try {
    $evidence = Invoke-WebRequest -Uri "$BaseUrl/api/evidence/resolve?ref=$snapshotRef" -Method GET -UseBasicParsing
    if ($evidence.StatusCode -ne 200) {
        Write-Host "❌ Evidence resolve failed: HTTP $($evidence.StatusCode)" -ForegroundColor Red
        exit 2
    }
}
catch {
    Write-Host "❌ Evidence resolve failed: $_" -ForegroundColor Red
    exit 2
}

# Summary
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Yellow
Write-Host "LIVE: $result $decision | bundle=$bundleDecision stale=$bundleStale | reco=$recoDecision | delivery=$delivery | snapshot_ref=OK" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Yellow

if ($delivery -eq "CONSOLE_SIMULATED") {
    Write-Host "✅ PASS: All checks passed" -ForegroundColor Green
    exit 0
}
else {
    Write-Host "⚠️ WARNING: delivery_actual=$delivery (expected CONSOLE_SIMULATED)" -ForegroundColor Yellow
    exit 0
}
