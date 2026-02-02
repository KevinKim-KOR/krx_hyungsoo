<#
.SYNOPSIS
    P100-4: Bundle Publish 원커맨드 통합 스크립트
.DESCRIPTION
    PC에서 명령 1번으로:
    1. git pull origin main
    2. Bundle 생성 (regime + scorer + holding_action)
    3. 로컬 검증 (스키마/필드/ENUM-only/sanitize)
    4. git add / commit / push
    5. 요약 10줄 출력
.NOTES
    실패하면 즉시 종료 (exit code != 0)
    로그: logs/pc_publish_bundle.log
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ============================================================================
# Step 0: 상수 정의
# ============================================================================
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$REPO_ROOT = (Get-Item "$SCRIPT_DIR\..\..").FullName
$VENV_PYTHON = Join-Path $REPO_ROOT ".venv\Scripts\python.exe"
$BUNDLE_SCRIPT = Join-Path $REPO_ROOT "deploy\pc\generate_strategy_bundle.py"
$BUNDLE_LATEST = Join-Path $REPO_ROOT "state\strategy_bundle\latest\strategy_bundle_latest.json"
$LOG_DIR = Join-Path $REPO_ROOT "logs"
$LOG_FILE = Join-Path $LOG_DIR "pc_publish_bundle.log"

$VALID_REGIME_CODES = @("RISK_ON", "RISK_OFF", "NEUTRAL", "VOLATILE")
$VALID_STATUSES = @("OK", "SKIPPED", "NO_ACTION")
$ENUM_PATTERN = "^[A-Z0-9_]+$"

# P100-4-FIX1: Allowlist paths for commit hygiene (glob patterns)
$ALLOWLIST_PATTERNS = @(
    "deploy/pc/publish_bundle.ps1",
    "deploy/pc/generate_strategy_bundle.py",
    "app/scoring/*",
    "state/strategy_bundle/*"
)

# ============================================================================
# Helper Functions
# ============================================================================
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$Level] $Message"
    Write-Host $line
    Add-Content -Path $LOG_FILE -Value $line -Encoding UTF8
}

function Exit-WithError {
    param([string]$Message)
    Write-Log $Message "ERROR"
    Write-Host ""
    Write-Host "=== PUBLISH FAILED ===" -ForegroundColor Red
    Write-Host $Message -ForegroundColor Red
    exit 1
}

function Test-EnumOnly {
    param([string]$Value)
    return $Value -match $ENUM_PATTERN
}

function Test-SanitizedDetail {
    param([string]$Value)
    if (-not $Value) { return $true }
    if ($Value.Contains("`n") -or $Value.Contains("`r")) { return $false }
    if ($Value.Length -gt 240) { return $false }
    return $true
}

# P100-4-FIX1: Check if path matches any allowlist pattern
function Test-PathInAllowlist {
    param([string]$FilePath)
    foreach ($pattern in $ALLOWLIST_PATTERNS) {
        # Convert glob to regex-like match
        $regexPattern = "^" + ($pattern -replace "\*", ".*") + "$"
        if ($FilePath -match $regexPattern) {
            return $true
        }
        # Also check if path starts with pattern (for directory patterns)
        $dirPattern = $pattern -replace "\*$", ""
        if ($FilePath.StartsWith($dirPattern)) {
            return $true
        }
    }
    return $false
}

# ============================================================================
# Step 1: Preflight
# ============================================================================
Write-Host ""
Write-Host "=== P100-4: Bundle Publish ===" -ForegroundColor Cyan
Write-Host ""

# Repo root 이동
Set-Location $REPO_ROOT
Write-Log "Repo root: $REPO_ROOT"

# Git 확인
try {
    $gitVersion = git --version
    Write-Log "Git: $gitVersion"
}
catch {
    Exit-WithError "Git not available: $_"
}

# Python venv 확인
if (-not (Test-Path $VENV_PYTHON)) {
    Exit-WithError "Python venv not found at: $VENV_PYTHON"
}
Write-Log "Python venv: $VENV_PYTHON"

# logs 디렉토리 생성
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
}
Write-Log "Log file: $LOG_FILE"

$startTime = Get-Date

# ============================================================================
# Step 1.5: Preflight Dirty Check (P100-4-FIX1)
# ============================================================================
Write-Log "Step 1.5: Checking worktree for unauthorized changes..."
$ErrorActionPreference = "Continue"
$dirtyFiles = git status --porcelain 2>&1
$ErrorActionPreference = "Stop"

if ($dirtyFiles) {
    $blockedPaths = @()
    $allowedPaths = @()
    
    foreach ($line in $dirtyFiles -split "`n") {
        if ($line.Trim()) {
            # Extract file path (skip first 3 chars which are status flags)
            $filePath = $line.Substring(3).Trim()
            # Handle renamed files (old -> new)
            if ($filePath -match " -> ") {
                $filePath = ($filePath -split " -> ")[1]
            }
            $filePath = $filePath -replace "\\", "/"
            
            if (Test-PathInAllowlist $filePath) {
                $allowedPaths += $filePath
            }
            else {
                $blockedPaths += $filePath
            }
        }
    }
    
    if ($blockedPaths.Count -gt 0) {
        Write-Log "Blocked paths outside allowlist: $($blockedPaths -join ', ')" "ERROR"
        Exit-WithError "Dirty files outside allowlist detected. Commit or stash them first: $($blockedPaths -join ', ')"
    }
    
    Write-Log "Allowed dirty files: $($allowedPaths.Count) (will be committed)"
}
else {
    Write-Log "Worktree clean, no uncommitted changes"
}

# ============================================================================
# Step 2: Git 최신화
# ============================================================================
Write-Log "Step 2: Git pull..."
$ErrorActionPreference = "Continue"
$pullResult = git pull origin main 2>&1
$pullExitCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($pullExitCode -ne 0) {
    Exit-WithError "Git pull failed with exit code: $pullExitCode - $pullResult"
}
Write-Log "Git pull: OK"

# ============================================================================
# Step 3: Bundle 생성
# ============================================================================
Write-Log "Step 3: Generating bundle..."
try {
    $bundleOutput = & $VENV_PYTHON $BUNDLE_SCRIPT 2>&1
    $bundleExitCode = $LASTEXITCODE
    Write-Log "Bundle generation output: $($bundleOutput -join ' ')"
    if ($bundleExitCode -ne 0) {
        Exit-WithError "Bundle generation failed with exit code: $bundleExitCode"
    }
}
catch {
    Exit-WithError "Bundle generation exception: $_"
}

# ============================================================================
# Step 4: 로컬 검증
# ============================================================================
Write-Log "Step 4: Validating bundle..."

if (-not (Test-Path $BUNDLE_LATEST)) {
    Exit-WithError "Bundle file not found: $BUNDLE_LATEST"
}

try {
    $bundleContent = Get-Content $BUNDLE_LATEST -Raw -Encoding UTF8
    $bundle = $bundleContent | ConvertFrom-Json
}
catch {
    Exit-WithError "Failed to parse bundle JSON: $_"
}

# 4-1. schema 검증
if ($bundle.schema -ne "STRATEGY_BUNDLE_V1") {
    Exit-WithError "Invalid schema: $($bundle.schema)"
}
Write-Log "Validation: schema OK"

# 4-2. created_at 검증 (10분 이내)
try {
    $createdAt = [DateTime]::Parse($bundle.created_at)
    $age = (Get-Date) - $createdAt
    if ($age.TotalMinutes -gt 10) {
        Exit-WithError "Bundle too old: created_at=$($bundle.created_at), age=$($age.TotalMinutes) minutes"
    }
}
catch {
    Exit-WithError "Invalid created_at: $($bundle.created_at)"
}
Write-Log "Validation: created_at OK (age: $([int]$age.TotalSeconds)s)"

# 4-3. regime 검증
$regime = $bundle.strategy.regime
if (-not $regime.code -or $regime.code -notin $VALID_REGIME_CODES) {
    Exit-WithError "Invalid regime.code: $($regime.code)"
}
if (-not (Test-EnumOnly $regime.reason)) {
    Exit-WithError "regime.reason not ENUM-only: $($regime.reason)"
}
if (-not (Test-SanitizedDetail $regime.reason_detail)) {
    Exit-WithError "regime.reason_detail not sanitized"
}
Write-Log "Validation: regime OK"

# 4-4. scorer 검증
$scorer = $bundle.strategy.scorer
if (-not $scorer.status -or $scorer.status -notin $VALID_STATUSES) {
    Exit-WithError "Invalid scorer.status: $($scorer.status)"
}
if ($scorer.status -eq "OK" -and $null -eq $scorer.top_picks) {
    Exit-WithError "scorer.status=OK but top_picks missing"
}
Write-Log "Validation: scorer OK"

# 4-5. holding_action 검증
$holdingAction = $bundle.strategy.holding_action
if (-not $holdingAction.status -or $holdingAction.status -notin $VALID_STATUSES) {
    Exit-WithError "Invalid holding_action.status: $($holdingAction.status)"
}
if (-not (Test-EnumOnly $holdingAction.reason)) {
    Exit-WithError "holding_action.reason not ENUM-only: $($holdingAction.reason)"
}
if (-not (Test-SanitizedDetail $holdingAction.reason_detail)) {
    Exit-WithError "holding_action.reason_detail not sanitized"
}
Write-Log "Validation: holding_action OK"

# 4-6. integrity 검증
if (-not $bundle.integrity.payload_sha256) {
    Exit-WithError "integrity.payload_sha256 missing"
}
Write-Log "Validation: integrity OK"

Write-Log "All validations passed!"

# ============================================================================
# Step 5: Commit & Push
# ============================================================================
Write-Log "Step 5: Git commit & push..."

# Staging - P100-4-FIX1: Stage all allowlist paths
$ErrorActionPreference = "Continue"
foreach ($pattern in $ALLOWLIST_PATTERNS) {
    # Convert pattern to path
    $pathToAdd = $pattern -replace "\*$", ""
    if (Test-Path $pathToAdd) {
        git add $pathToAdd 2>&1 | Out-Null
    }
}
# Also explicitly add the specific files
git add deploy/pc/publish_bundle.ps1 2>&1 | Out-Null
git add deploy/pc/generate_strategy_bundle.py 2>&1 | Out-Null
git add app/scoring/ 2>&1 | Out-Null
git add state/strategy_bundle/ 2>&1 | Out-Null
$addExitCode = $LASTEXITCODE
if ($addExitCode -ne 0) {
    $ErrorActionPreference = "Stop"
    Exit-WithError "Git add failed with exit code: $addExitCode"
}
Write-Log "Git add: OK (all allowlist paths)"

# Check if there are changes to commit (all staged files, not just bundle)
$status = git status --porcelain 2>&1
$stagedStatus = git diff --cached --name-only 2>&1
if (-not $stagedStatus) {
    Write-Log "No staged changes to commit"
    $commitHash = (git rev-parse --short HEAD 2>&1).ToString().Trim()
    $commitCreated = $false
}
else {
    # Commit all staged changes
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $commitMsg = "bundle(pc): publish $timestamp"
    git commit -m $commitMsg 2>&1 | Out-Null
    $commitExitCode = $LASTEXITCODE
    if ($commitExitCode -ne 0) {
        $ErrorActionPreference = "Stop"
        Exit-WithError "Git commit failed with exit code: $commitExitCode"
    }
    $commitHash = (git rev-parse --short HEAD 2>&1).ToString().Trim()
    $commitCreated = $true
    Write-Log "Committed: $commitHash"
}

# Push
$pushResult = git push origin main 2>&1
$pushExitCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($pushExitCode -ne 0) {
    Exit-WithError "Git push failed with exit code: $pushExitCode"
}
Write-Log "Git push: OK"

# ============================================================================
# Step 6: 성공 요약 10줄 출력
# ============================================================================
$endTime = Get-Date
$duration = $endTime - $startTime

$topPicksCount = if ($scorer.top_picks) { $scorer.top_picks.Count } else { 0 }
$topPicksSummary = ""
if ($topPicksCount -gt 0) {
    $top3 = $scorer.top_picks | Select-Object -First 3
    $topPicksSummary = ($top3 | ForEach-Object { "$($_.ticker):$($_.score)" }) -join ", "
}

$itemsCount = if ($holdingAction.items) { $holdingAction.items.Count } else { 0 }
$actionCounts = @{}
if ($holdingAction.items) {
    foreach ($item in $holdingAction.items) {
        $act = $item.action
        if (-not $actionCounts.ContainsKey($act)) { $actionCounts[$act] = 0 }
        $actionCounts[$act]++
    }
}
$actionSummary = ($actionCounts.Keys | ForEach-Object { "$_`:$($actionCounts[$_])" }) -join ", "

Write-Host ""
Write-Host "=== PUBLISH SUCCESS ===" -ForegroundColor Green
Write-Host "1. created_at     : $($bundle.created_at)"
Write-Host "2. bundle_id      : $($bundle.bundle_id)"
Write-Host "3. regime         : $($regime.code) / $($regime.reason)"
Write-Host "4. scorer         : $($scorer.status) (picks=$topPicksCount) [$topPicksSummary]"
Write-Host "5. holding_action : $($holdingAction.status) (items=$itemsCount) [$actionSummary]"
Write-Host "6. sha256_prefix  : $($bundle.integrity.payload_sha256.Substring(0, 16))"
Write-Host "7. commit         : $commitHash $(if($commitCreated){'(new)'}else{'(unchanged)'})"
Write-Host "8. push           : OK"
Write-Host "9. duration       : $([int]$duration.TotalSeconds)s"
Write-Host "10. log           : $LOG_FILE"
Write-Host ""

Write-Log "Publish completed in $([int]$duration.TotalSeconds)s"

# ============================================================================
# Step 7: Worktree Clean Gate (P100-4-FIX1)
# ============================================================================
$ErrorActionPreference = "Continue"
$finalStatus = git status --porcelain 2>&1
$ErrorActionPreference = "Stop"

if ($finalStatus) {
    Write-Host ""
    Write-Host "=== WORKTREE NOT CLEAN ===" -ForegroundColor Yellow
    Write-Host "Remaining uncommitted files:" -ForegroundColor Yellow
    Write-Host $finalStatus
    Exit-WithError "Worktree not clean after publish. This should not happen - please investigate."
}

Write-Host "11. worktree      : CLEAN" -ForegroundColor Green
Write-Log "Worktree clean gate: PASS"

exit 0
