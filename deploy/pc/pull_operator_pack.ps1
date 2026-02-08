<#
.SYNOPSIS
    P128: PC Pull Operator Pack V1
    Downloads valid artifacts (Ticket, Plan, Export, Reco, etc.) from OCI.
.DESCRIPTION
    Read-only sync. Uses OCI Dashboard API (P127) as SSOT.
    Creates local/operator_pack/YYYYMMDD_HHMMSS/ folder.
    NO TOKEN HANDLING.
#>
param (
    [string]$BaseUrl = "http://168.107.51.68:8000"
)

# 1. Configuration
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutputDir = "local\operator_pack\$Timestamp"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "   📦 PULLING OPERATOR PACK (READ-ONLY)" -ForegroundColor Cyan
Write-Host "   Target: $OutputDir" -ForegroundColor Gray
Write-Host "==================================================="

# 2. Fetch Dashboard (SSOT)
try {
    Write-Host "Fetching Dashboard SSOT..." -NoNewline
    $Dashboard = Invoke-RestMethod -Uri "$BaseUrl/api/operator/dashboard" -Method Get -TimeoutSec 5
    Write-Host " OK" -ForegroundColor Green
}
catch {
    Write-Host " FAIL" -ForegroundColor Red
    Write-Error "CHECK_BACKEND: Failed to reach OCI Dashboard ($BaseUrl). Is Backend running?"
    exit 1
}

$Stage = $Dashboard.stage
Write-Host "Current Stage: $Stage" -ForegroundColor Yellow
$Artifacts = $Dashboard.artifacts

if (-not $Artifacts) {
    Write-Host "No artifacts found in dashboard." -ForegroundColor Yellow
    exit 0
}

# 3. Download Artifacts
$Count = 0
foreach ($Key in $Artifacts.PSObject.Properties.Name) {
    $RefPath = $Artifacts.$Key
    
    # Simple filename from key + extension
    # Determine extension from RefPath
    $Ext = [IO.Path]::GetExtension($RefPath)
    if (-not $Ext) { $Ext = ".json" }
    
    $FileName = "$Key$Ext"
    $OutFile = Join-Path $OutputDir $FileName
    
    Write-Host "Downloading [$Key]... " -NoNewline
    
    try {
        # Using Evidence Resolver
        # URL Encode RefPath
        $EncodedRef = [uri]::EscapeDataString($RefPath)
        $DownloadUrl = "$BaseUrl/api/evidence/resolve?ref=$EncodedRef"
        
        Invoke-WebRequest -Uri $DownloadUrl -OutFile $OutFile -TimeoutSec 10
        Write-Host "OK ($FileName)" -ForegroundColor Green
        $Count++
    }
    catch {
        Write-Host "SKIP/FAIL (Not found or Error)" -ForegroundColor DarkGray
        # Not fatal, just skip
    }
}

Write-Host "---------------------------------------------------"
Write-Host "✅ Download Complete. ($Count files)" -ForegroundColor Green
Write-Host "   Folder: $OutputDir"
Write-Host "---------------------------------------------------"

# 4. Next Action Reminder
if ($Dashboard.next_action -and $Dashboard.next_action.command) {
    Write-Host "NEXT ACTION (From OCI):" -ForegroundColor Cyan
    Write-Host "   $($Dashboard.next_action.command)" -ForegroundColor White
}
