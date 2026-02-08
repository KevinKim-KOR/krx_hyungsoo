<#
.SYNOPSIS
    Daily Manual Loop Orchestrator (PC)
    P126: One-Command Runner
.DESCRIPTION
    Checks OCI Stage and executes allowed actions.
    Enforces Fail-Closed sequence.
    NEVER handles tokens (delegates to OCI).
.PARAMETER DoPrep
    Execute Prep on OCI (Token required on OCI)
.PARAMETER DoTicket
    Execute Ticket Gen on OCI
.PARAMETER DoDraft
    Generate Record Draft on PC (P124)
.PARAMETER DoPushDraft
    Push Draft to OCI (P125)
.PARAMETER DoSubmit
    Submit Record on OCI (Token required on OCI) (P125)
.PARAMETER PlanOnly
    Show status and next action (Default)
#>
param (
    [switch]$DoPrep,
    [switch]$DoTicket,
    [switch]$DoDraft,
    [switch]$DoPushDraft,
    [switch]$DoSubmit,
    [switch]$PlanOnly,

    [string]$HostName = "168.107.51.68",
    [string]$UserName = "ubuntu",
    [string]$KeyPath = "e:\AI Study\orcle cloud\oracle_cloud_key",
    [string]$BaseUrl = "http://localhost:8000"
)

# Configuration
$RemoteDir = "krx_hyungsoo"

# Helper: Run SSH Command
function Invoke-SSHCmd {
    param ([string]$Command)
    ssh -i $KeyPath -o StrictHostKeyChecking=no "$UserName@$HostName" "cd $RemoteDir && $Command"
    return $LASTEXITCODE
}

# Helper: Get OCI Stage
function Get-OCIStage {
    Write-Host "Fetching OCI Stage..." -ForegroundColor Gray
    
    $Cmd = "python3 deploy/oci/get_stage.py"
    $Output = ssh -i $KeyPath -o StrictHostKeyChecking=no "$UserName@$HostName" "cd $RemoteDir && $Cmd"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error fetching stage: $Output" -ForegroundColor Red
        return "UNKNOWN"
    }
    
    # Parse STAGE_VALUE:VALUE
    $OutputString = $Output -join "`n"
    if ($OutputString -match "STAGE_VALUE:(.*)") {
        return $matches[1].Trim()
    }
    
    Write-Host "Debug Output: $OutputString" -ForegroundColor Gray
    return "UNKNOWN"
}

# 1. Get Status
$CurrentStage = Get-OCIStage
Write-Host "Current Stage: [$CurrentStage]" -ForegroundColor Cyan

# 2. Determine Next Action
$NextAction = "NONE"
$AllowedActions = @()

switch ($CurrentStage) {
    "NEED_HUMAN_CONFIRM" {
        $NextAction = "Run Prep (DoPrep)"
        $AllowedActions += "DoPrep"
    }
    "PREP_READY" {
        $NextAction = "Generate Ticket (DoTicket)"
        $AllowedActions += "DoTicket"
    }
    # Note: manual_loop_prepare.sh often does Ticket automatically.
    
    "AWAITING_HUMAN_EXECUTION" {
        $NextAction = "Generate Draft (DoDraft) OR Push/Submit (DoPushDraft, DoSubmit)"
        $AllowedActions += "DoDraft"
        $AllowedActions += "DoPushDraft"
        $AllowedActions += "DoSubmit"
    }
    "AWAITING_RECORD_SUBMIT" {
        $NextAction = "Push & Submit (DoPushDraft, DoSubmit)"
        $AllowedActions += "DoPushDraft"
        $AllowedActions += "DoSubmit"
    }
    "DONE_TODAY" {
        $NextAction = "No Action Required"
    }
    "DONE_TODAY_PARTIAL" {
        $NextAction = "Review Partial / Retry if needed"
    }
    Default {
        $NextAction = "Wait / Contact Admin"
    }
}

Write-Host "Next Action  : $NextAction" -ForegroundColor Green

# 3. Execution Logic
if ($PlanOnly -or (-not ($DoPrep -or $DoTicket -or $DoDraft -or $DoPushDraft -or $DoSubmit))) {
    exit 0
}

# 4. Fail-Closed Checks and Execution
if ($DoPrep) {
    if ("DoPrep" -notin $AllowedActions) {
        Write-Error "Action 'DoPrep' BLOCKED in stage '$CurrentStage'."
        exit 1
    }
    Write-Host ">> Executing Prep on OCI..."
    # Invoke interactive SSH for token input
    ssh -t -i $KeyPath -o StrictHostKeyChecking=no "$UserName@$HostName" "cd $RemoteDir && bash deploy/oci/manual_loop_prepare.sh"
}

if ($DoTicket) {
    if ("DoTicket" -notin $AllowedActions) {
        Write-Error "Action 'DoTicket' BLOCKED in stage '$CurrentStage'."
        exit 1
    }
    Write-Host ">> Executing Ticket Gen..."
    ssh -t -i $KeyPath -o StrictHostKeyChecking=no "$UserName@$HostName" "cd $RemoteDir && curl -X POST $BaseUrl/api/manual_execution_ticket/regenerate?confirm=true"
}

if ($DoDraft) {
    if ("DoDraft" -notin $AllowedActions) {
        Write-Error "Action 'DoDraft' BLOCKED in stage '$CurrentStage'."
        exit 1
    }
    Write-Host ">> Generating Record Draft (PC)..."
    .\deploy\pc\generate_record_template.ps1 -BaseUrl "http://$HostName`:8000"
}

if ($DoPushDraft) {
    if ("DoPushDraft" -notin $AllowedActions) {
        Write-Error "Action 'DoPushDraft' BLOCKED in stage '$CurrentStage'."
        exit 1
    }
    Write-Host ">> Pushing Draft to OCI..."
    .\deploy\pc\push_record_draft.ps1 -HostName $HostName -KeyPath $KeyPath
}

if ($DoSubmit) {
    if ("DoSubmit" -notin $AllowedActions) {
        Write-Error "Action 'DoSubmit' BLOCKED in stage '$CurrentStage'."
        exit 1
    }
    Write-Host ">> Submitting Record on OCI..."
    # Need to know the filename? push_record_draft verifies it.
    # But submit script takes filename as arg.
    # We should probably list the incoming file and pick latest or ask user?
    # For "One-Command", we can assume push just happened.
    # Let's verify what file is in incoming.
    
    # Strategy: List files in incoming, pick latest.
    $FindCmd = "ls -t incoming/manual_execution_record_drafts/*.json | head -n 1"
    $RemoteFile = ssh -i $KeyPath -o StrictHostKeyChecking=no "$UserName@$HostName" "cd $RemoteDir && $FindCmd"
    $RemoteFile = $RemoteFile.Trim()
    
    if (-not $RemoteFile) {
        Write-Error "No draft file found in incoming/ on OCI."
        exit 1
    }
    
    Write-Host "Target File: $RemoteFile"
    
    # Interactive SSH for token
    ssh -t -i $KeyPath -o StrictHostKeyChecking=no "$UserName@$HostName" "cd $RemoteDir && bash deploy/oci/submit_record_from_incoming.sh $RemoteFile"
}

Write-Host "Done."
