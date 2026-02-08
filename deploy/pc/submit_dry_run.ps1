<#
.SYNOPSIS
    P131: Trigger Dry Run Submission
    Invokes OCI script to submit a Dry Run record.
.DESCRIPTION
    NO TOKEN HANDLING on PC.
    SSH into OCI and runs manual_loop_submit_dry_run.sh.
#>
param (
    [string]$HostName = "168.107.51.68",
    [string]$UserName = "ubuntu",
    [string]$KeyPath = "e:\AI Study\orcle cloud\oracle_cloud_key"
)

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "   🛡️  TRIGGERING DRY RUN (SSH -> OCI)" -ForegroundColor Cyan
Write-Host "==================================================="

$RemoteScript = "bash krx_hyungsoo/deploy/oci/manual_loop_submit_dry_run.sh"

ssh -t -i $KeyPath -o StrictHostKeyChecking=no "$UserName@$HostName" "$RemoteScript"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Dry Run Trigger Failed (Exit Code: $LASTEXITCODE)"
    exit 1
}

Write-Host "---------------------------------------------------"
Write-Host "✅ Dry Run Triggered." -ForegroundColor Green
