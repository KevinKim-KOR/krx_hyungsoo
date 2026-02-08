# P119: PC -> OCI Flight Status One-Command (Hardened)
# Usage: .\deploy\pc\flight_status.ps1

$KeyPath = "e:\AI Study\orcle cloud\oracle_cloud_key"
$RemoteHost = "ubuntu@168.107.51.68"
$RemoteCmd = "cd krx_hyungsoo && bash deploy/oci/flight_status.sh"

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "   ✈️  CHECKING OCI FLIGHT STATUS (REMOTE)" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

# Execute SSH and capture output while streaming
$Output = ssh -i $KeyPath $RemoteHost $RemoteCmd
$SSHExitCode = $LASTEXITCODE

# Print Output to Console (if captured, otherwise it streams but we want to capture for parsing exit condition effectively or just trust the script)
# Actually, if we use invoke-expression or just run it, it streams.
# But we want to check if DONE_TODAY is present.

$Output | ForEach-Object { Write-Host $_ }

if ($SSHExitCode -ne 0) {
    Write-Host "`n❌ OCI Connection Failed or Script Error (Exit Code: $SSHExitCode)" -ForegroundColor Red
    exit $SSHExitCode
}

# Analyze for DONE_TODAY visual confirmation
$IsDone = $Output -match "STAGE\s+:\s+DONE_TODAY"

if ($IsDone) {
    Write-Host "`n✅ STATUS: DONE_TODAY (Routine Complete)" -ForegroundColor Green
    exit 0
}
else {
    Write-Host "`n⚠️  STATUS: ACTIVE / INCOMPLETE" -ForegroundColor Yellow
    
    # P128 Suggestion
    Write-Host "💡 TIP: Download Artifacts -> .\deploy\pc\pull_operator_pack.ps1" -ForegroundColor Gray
    
    exit 2
}
