# Runbook: Live Micro-Pilot V1 (1-Trade Test)

## Goal
Verify the end-to-end Manual Execution Pipeline with **Real Brokerage Interaction** by executing **exactly one trade** (buying 1 unit of a low-cost ETF) while keeping the rest of the portfolio unchanged.

## Prerequisites
-   [x] P138 (Param Review) & P139 (Dashboard) Deployed.
-   [x] OCI Stage is `NEED_HUMAN_CONFIRM` (Morning State).
-   [x] KIS Token is ready.
-   [x] Mobile Dashboard is accessible.

## Procedure

### 1. Preparation (PC)
Run the Gate:
```powershell
.\deploy\pc\go_live_gate.ps1
```
> Expect: `GO_LIVE=READY`

Run the Orchestrator:
```powershell
.\deploy\pc\daily_operator.ps1
```
> Follow the instruction: "Run Prep"

### 2. Preparation (OCI)
Copy the command from Dashboard/Terminal and run on OCI:
```bash
# Example
deploy/oci/manual_loop_prepare.sh
```
-   Enter Token.
-   Wait for "Ticket Generated".

### 3. Execution (Human)
**CRITICAL:** This is the Micro-Pilot Step.
1.  Open the Ticket (`manual_execution_ticket_latest.md` or Dashboard Link).
2.  Select **ONE** buy order from the list (e.g., KODEX 200, 1 share).
3.  **Execute** this single trade in your Broker App (MTS/HTS).
4.  **Ignore** all other orders for today.

### 4. Record Submission (PC)
Generate the Record Draft:
```powershell
.\deploy\pc\daily_manual_loop.ps1 -DoDraft
```
> Edit the generated JSON file (`local/manual_execution_record_drafts/...`).

**EDITING RULES:**
-   Set `execution_result` to `"PARTIAL"`.
-   For the **Executed Item**: Set `action_status="FILLED"`, `filled_qty=1`, `filled_price=...`.
-   For **All Other Items**: Set `action_status="SKIPPED"`, `note="Micro-Pilot constraint"`.

Push the Draft:
```powershell
.\deploy\pc\daily_manual_loop.ps1 -DoPushDraft
```

### 5. Finalize (OCI)
Submit the Record:
```bash
deploy/oci/manual_loop_submit_record.sh incoming/...
```
-   Enter Token.
-   Verify Stage becomes `DONE_TODAY_PARTIAL`.

## Verification
1.  Check Dashboard: Stage should be `DONE_TODAY_PARTIAL`.
2.  Check Dashboard: Mode should be `LIVE` (not DRY_RUN).
3.  Check Dashboard: Portfolio should update tomorrow (after P91 restore).

## Rollback (If needed)
If the trade fails or record is wrong:
-   Do NOT submit the record.
-   Call `deploy/oci/manual_loop_submit_dry_run.sh` to close the day safely without recording bad data.
