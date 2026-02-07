<#
.SYNOPSIS
    Pushes a Manual Execution Record Draft to OCI via SCP.
.DESCRIPTION
    Selects the latest draft (or specified one).
    Calcualtes Local SHA256.
    Transfers to OCI incoming directory.
    Verifies Remote SHA256.
.PARAMETER Host
    OCI Host IP
.PARAMETER User
    OCI User (default: ubuntu)
.PARAMETER KeyPath
    Path to SSH Private Key
.PARAMETER DraftPath
    Optional path to specific draft. Defaults to latest in local/manual_execution_record_drafts/
#>
param (
    [Parameter(Mandatory = $true)]
    [string]$HostName, # 'Host' is reserved? using HostName
    
    [string]$UserName = "ubuntu",
    
    [Parameter(Mandatory = $true)]
    [string]$KeyPath,
    
    [string]$DraftPath
)

$LocalDir = "local/manual_execution_record_drafts"
$RemoteDir = "krx_hyungsoo/incoming/manual_execution_record_drafts"

# 1. Select Draft
if (-not $DraftPath) {
    if (-not (Test-Path $LocalDir)) {
        Write-Error "Local draft directory not found: $LocalDir"
        exit 1
    }
    $Latest = Get-ChildItem $LocalDir -Filter "*.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $Latest) {
        Write-Error "No draft files found in $LocalDir"
        exit 1
    }
    $DraftPath = $Latest.FullName
}
elseif (-not (Test-Path $DraftPath)) {
    Write-Error "Specified draft not found: $DraftPath"
    exit 1
}

Write-Host "Selected Draft: $DraftPath"

# 2. Calculate Local SHA256
$LocalHash = (Get-FileHash $DraftPath -Algorithm SHA256).Hash.ToLower()
Write-Host "Local SHA256:  $LocalHash"

# 3. Ensure Remote Directory
Write-Host "Ensuring remote directory..."
$EnsureCmd = "mkdir -p $RemoteDir"
ssh -i $KeyPath -o StrictHostKeyChecking=no "$UserName@$HostName" $EnsureCmd
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to create remote directory."
    exit 1
}

# 4. SCP Transfer
Write-Host "Transferring file..."
$FileName = Split-Path $DraftPath -Leaf
$RemotePath = "$RemoteDir/$FileName"
# Windows SCP syntax helper
scp -i $KeyPath -o StrictHostKeyChecking=no $DraftPath "$UserName@$HostName`:$RemotePath"
if ($LASTEXITCODE -ne 0) {
    Write-Error "SCP Transfer Failed."
    exit 1
}

# 5. Verify Remote SHA256
Write-Host "Verifying remote integrity..."
$VerifyCmd = "sha256sum $RemotePath | cut -d ' ' -f 1"
$RemoteHash = (ssh -i $KeyPath -o StrictHostKeyChecking=no "$UserName@$HostName" $VerifyCmd)

# Clean whitespace
$RemoteHash = $RemoteHash.Trim().ToLower()
Write-Host "Remote SHA256: $RemoteHash"

if ($LocalHash -eq $RemoteHash) {
    Write-Host "SUCCESS: Integrity Verified."
    Write-Host "Remote Path: $RemotePath"
    Write-Host "Next Step (OCI): bash deploy/oci/submit_record_from_incoming.sh $RemotePath"
    exit 0
}
else {
    Write-Error "Integrity Check FAILED! Hashes do not match."
    exit 1
}
