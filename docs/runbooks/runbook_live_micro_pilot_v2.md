# Runbook: Live Micro-Pilot V2 (Weekly Routine)

## Goal
Establish a repeatable, safe daily operation routine for 5 consecutive days.
**Rule**: Maximum **1 Trade** (or 1 Buy/Sell pair) per day.

## Schedule (Example)
- **Day 1 (Mon)**: Buy 1 share of Top Pick A.
- **Day 2 (Tue)**: Buy 1 share of Top Pick B (or Sell A if exit signal).
- **Day 3 (Wed)**: ...
- **Day 4 (Thu)**: ...
- **Day 5 (Fri)**: ...

## Daily Checklist

### 1. 09:00 - System Check (PC)
```powershell
.\deploy\pc\daily_operator.ps1
```
- **Expect**: `NEED_HUMAN_CONFIRM` (if new day) or `DONE_TODAY` (if already done).
- **Verify**: Backend is ONLINE.

### 2. 09:10 - Preparation (OCI via SSH)
```bash
# SSH into OCI
bash deploy/oci/manual_loop_prepare.sh
# Input Execution Token
```
- **Expect**: Stage transitions to `AWAITING_HUMAN_EXECUTION`.
- **Artifact**: `manual_execution_ticket_latest.json` generated.

### 3. 09:30 - Execution (Human)
- **Open Ticket**: Review "Top Picks".
- **Action**: Execute **ONE** trade in HTS/MTS.
    - *Constraint*: Do not exceed 1 trade/set.
    - *Constraint*: Do not touch other items.
- **Record**: Note quantity and price.

### 4. 09:40 - Reporting (PC -> OCI)
1.  **Draft**:
    ```powershell
    .\deploy\pc\generate_record_template.ps1
    ```
2.  **Edit**:
    - Open `local/manual_execution_record_drafts/...`
    - Set `execution_result`: `"PARTIAL"` (Recommended) or `"EXECUTED"`.
    - Mark the **1 trade** as `EXECUTED` with details.
    - Mark others as `SKIPPED` (or leave as `PENDING`/`UNKNOWN` if using Partial).
3.  **Push**:
    ```powershell
    .\deploy\pc\push_record_draft.ps1
    ```
4.  **Submit** (OCI):
    ```bash
    bash deploy/oci/manual_loop_submit_record.sh <record_file_name>
    ```

### 5. 10:00 - Verification
- **Dashboard**:
    ```powershell
    .\deploy\pc\flight_status.ps1
    ```
- **Expect**:
    - Stage: `DONE_TODAY_PARTIAL` (or `DONE_TODAY`).
    - Mode: `LIVE`.
    - Risks: None (or `WARN` if partial).

## Emergency Procedures
- **Stage BLOCKED**: Check `top_risks` in Dashboard.
- **Mistake in Record**: Re-submit with corrected JSON (idempotency key update may be needed).
- **System Failure**: Stop operation. Do not force trades.

## Success Criteria (Weekly)
1.  5 Days of operation.
2.  No Token logged in any file.
3.  `steady_gate_check.sh` PASS every day.
