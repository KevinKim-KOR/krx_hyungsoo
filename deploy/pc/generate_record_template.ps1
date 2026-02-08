<#
.SYNOPSIS
    Generates a Manual Execution Record Draft JSON from OCI Data.
.DESCRIPTION
    Fetches Ops Summary, Prep, Ticket, and Export from OCI API.
    Validates Stage and Linkage.
    Creates a pre-filled JSON draft for the operator to complete.
.PARAMETER BaseUrl
    Base URL of the OCI API (e.g., http://192.168.1.100:8000)
#>
param (
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl
)

# Configuration
$DraftDir = "local/manual_execution_record_drafts"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$DraftFile = "$DraftDir/manual_execution_record_draft_$Timestamp.json"

# Ensure Directory
if (-not (Test-Path $DraftDir)) {
    New-Item -ItemType Directory -Path $DraftDir | Out-Null
}

function Get-Json ($Endpoint) {
    try {
        $Response = Invoke-RestMethod -Uri "$BaseUrl$Endpoint" -Method Get -ErrorAction Stop
        return $Response
    }
    catch {
        Write-Error "Failed to fetch from $Endpoint : $($_.Exception.Message)"
        exit 1
    }
}

Write-Host "--- PC Record Template Generator V1 ---"
Write-Host "Connecting to $BaseUrl..."

# 1. Fetch Ops Summary & Check Stage
$OpsSummary = Get-Json "/api/ops/summary/latest"
$Stage = $OpsSummary.manual_loop.stage

Write-Host "Current Stage: $Stage"

$AllowedStages = @("AWAITING_HUMAN_EXECUTION", "AWAITING_RECORD_SUBMIT", "DONE_TODAY", "DONE_TODAY_PARTIAL", "AWAITING_RETRY_EXECUTION")
if ($AllowedStages -notcontains $Stage) {
    Write-Error "BLOCKED: Stage '$Stage' is not ready for record generation."
    exit 1
}

# 2. Fetch Artifacts
$Prep = Get-Json "/api/execution_prep/latest"
$Ticket = Get-Json "/api/manual_execution_ticket/latest"
$Export = Get-Json "/api/order_plan_export/latest"

# 3. Validate Linkage
$PrepPlanId = $Prep.source.plan_id
$TicketPlanId = $Ticket.source.plan_id
$ExportPlanId = $Export.plan_id

Write-Host "Linkage Check:"
Write-Host "  Prep Plan ID: $PrepPlanId"
Write-Host "  Ticket Plan ID: $TicketPlanId"
Write-Host "  Export Plan ID: $ExportPlanId"

if (($PrepPlanId -ne $TicketPlanId) -or ($PrepPlanId -ne $ExportPlanId)) {
    Write-Error "BLOCKED: Plan ID Mismatch."
    exit 1
}

# 4. Construct Draft
$Items = @()
foreach ($Order in $Export.orders) {
    $Items += @{
        ticker       = $Order.ticker
        side         = $Order.side
        status       = "EXECUTED" # Default to EXECUTED for convenience
        qty_planned  = $Order.qty
        executed_qty = $Order.qty # Default to Full Fill
        avg_price    = $null # To be filled
        note         = ""
    }
}

$Draft = @{
    schema      = "MANUAL_EXECUTION_RECORD_V1"
    asof        = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
    source_refs = @{
        prep_ref = $Prep.source.order_plan_ref # Approximate
    }
    linkage     = @{
        prep_plan_id   = $PrepPlanId
        ticket_plan_id = $TicketPlanId
        export_plan_id = $ExportPlanId
        ticket_id      = $Ticket.ticket_id # Assuming exists
    }
    filled_at   = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
    items       = $Items
    dedupe      = @{
        idempotency_key = "" # To be filled or auto-generated
    }
}

# 5. Save Draft
$JsonContent = $Draft | ConvertTo-Json -Depth 5
$JsonContent | Set-Content -Path $DraftFile -Encoding UTF8

Write-Host "SUCCESS: Draft Generated"
Write-Host "  Draft Path: $DraftFile"
Write-Host "  Orders Count: $($Items.Count)"
Write-Host "  Plan ID: $PrepPlanId"
exit 0
