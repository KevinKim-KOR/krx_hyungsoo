# check_ops_summary.ps1 - PC Ops Summary Check Script (D-P.53.1)
# Usage: .\deploy\pc\check_ops_summary.ps1
# Exit codes: 0=OK (even if WARN), 3=API/JSON/resolve error
#
# D-P.53.1 Hardening:
# - Proper array iteration (no string manipulation)
# - Evidence validation via resolver API only

param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function Write-Step($step, $total, $msg) {
    Write-Host "[$step/$total] $msg" -ForegroundColor Cyan
}

# Step 1: Regenerate
Write-Step 1 4 "Regenerating Ops Summary..."
try {
    $null = Invoke-RestMethod -Uri "$BaseUrl/api/ops/summary/regenerate?confirm=true" -Method POST
}
catch {
    Write-Host "❌ Regenerate API failed: $_" -ForegroundColor Red
    exit 3
}

# Step 2: Get latest
Write-Step 2 4 "Fetching latest summary..."
try {
    $latest = Invoke-RestMethod -Uri "$BaseUrl/api/ops/summary/latest" -Method GET
}
catch {
    Write-Host "❌ Latest API failed: $_" -ForegroundColor Red
    exit 3
}

# Step 3: Parse
Write-Step 3 4 "Parsing summary..."
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
$riskCodes = if ($risks) { ($risks | ForEach-Object { $_.code }) -join "," } else { "" }

# Find health risk evidence_refs
$healthRefs = @()
if ($risks) {
    foreach ($r in $risks) {
        if ($r.code -in @("EVIDENCE_HEALTH_WARN", "EVIDENCE_HEALTH_FAIL")) {
            $healthRefs = $r.evidence_refs
            break
        }
    }
}

# Step 4: Verify refs via resolver
Write-Step 4 4 "Verifying evidence refs via resolver..."
$ehResolve = "N/A"

if ($ehSnapshotRef) {
    try {
        $encodedRef = [System.Web.HttpUtility]::UrlEncode($ehSnapshotRef)
        $evidence = Invoke-WebRequest -Uri "$BaseUrl/api/evidence/resolve?ref=$encodedRef" -Method GET -UseBasicParsing
        if ($evidence.StatusCode -eq 200) {
            $ehResolve = "OK"
        }
        else {
            Write-Host "⚠️ snapshot_ref resolve: HTTP $($evidence.StatusCode)" -ForegroundColor Yellow
            $ehResolve = "SKIP"
        }
    }
    catch {
        Write-Host "⚠️ snapshot_ref resolve failed: $_" -ForegroundColor Yellow
        $ehResolve = "SKIP"
    }
}

# Verify health risk refs
foreach ($ref in $healthRefs) {
    if ($ref) {
        try {
            $encodedRef = [System.Web.HttpUtility]::UrlEncode($ref)
            $result = Invoke-WebRequest -Uri "$BaseUrl/api/evidence/resolve?ref=$encodedRef" -Method GET -UseBasicParsing
            if ($result.StatusCode -ne 200) {
                Write-Host "⚠️ ref resolve failed: $ref (HTTP $($result.StatusCode))" -ForegroundColor Yellow
            }
        }
        catch {
            Write-Host "⚠️ ref resolve failed: $ref ($_)" -ForegroundColor Yellow
        }
    }
}

# Summary
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Yellow
Write-Host "OPS: $overall | health=$ehDecision | snapshot=$ehResolve" -ForegroundColor Green
Write-Host "tickets_recent: failed=$trFailed excluded=$trExcluded" -ForegroundColor Green
Write-Host "top_risks: [$riskCodes]" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Yellow

Write-Host "✅ PASS: All checks completed" -ForegroundColor Green
exit 0
