<#
.SYNOPSIS
    PC Auto Renew Bundle (D-P.60)
    
.DESCRIPTION
    Runs daily to:
    1. Generate new strategy bundle (fresh timestamp)
    2. Commit and Push to OCI registry (GitHub/GitLab)
    
    This ensures OCI always has a fresh bundle (<24h) for daily operations.

.EXAMPLE
    .\auto_renew_bundle.ps1
#>

$ErrorActionPreference = "Stop"

# Configuration
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$REPO_ROOT = "$SCRIPT_DIR\..\.."
$LOG_FILE = "$REPO_ROOT\logs\pc_auto_renew.log"
$DATE_STR = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

# Ensure log dir
if (-not (Test-Path "$REPO_ROOT\logs")) {
    New-Item -ItemType Directory -Path "$REPO_ROOT\logs" | Out-Null
}

function Write-Log {
    param([string]$Message)
    $LogMsg = "[$DATE_STR] $Message"
    Write-Host $LogMsg
    Add-Content -Path $LOG_FILE -Value $LogMsg
}

try {
    Write-Log "--------------------------------------------------------"
    Write-Log "Starting PC Bundle Auto-Renewal..."
    
    Set-Location $REPO_ROOT

    # 1. Update from remote (just in case)
    Write-Log "Pulling latest changes..."
    git pull origin archive-rebuild
    
    # 2. Run Generator Script
    Write-Log "Running generate_strategy_bundle.py..."
    $Result = python deploy/pc/generate_strategy_bundle.py 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        throw "Generator script failed with exit code $LASTEXITCODE `nOutput: $Result"
    }
    
    # 3. Git Operations
    Write-Log "Committing bundle changes..."
    git add state/strategy_bundle/
    
    # Check if there are changes
    $Status = git status --porcelain
    if ($Status) {
        git commit -m "Auto: Renew strategy bundle ($DATE_STR)"
        
        Write-Log "Pushing to remote..."
        git push origin archive-rebuild
        
        Write-Log "SUCCESS: Bundle renewed and pushed."
    }
    else {
        Write-Log "SKIPPED: No changes detected (Bundle might be already fresh?)"
    }
    
    Write-Log "Auto-Renewal Complete."
    
}
catch {
    Write-Log "ERROR: $_"
    exit 1
}
exit 0
