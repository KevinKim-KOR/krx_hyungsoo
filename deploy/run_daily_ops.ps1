# Daily Ops Cycle Runner (Windows)
# Phase C-P.17

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

Set-Location $ProjectDir

Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Starting Daily Ops Cycle..."

try {
    & ".\.venv\Scripts\python.exe" -m app.run_ops_cycle
    $ExitCode = $LASTEXITCODE
} catch {
    Write-Host "Error: $_"
    $ExitCode = 1
}

Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Ops Cycle finished with exit code: $ExitCode"
exit $ExitCode
