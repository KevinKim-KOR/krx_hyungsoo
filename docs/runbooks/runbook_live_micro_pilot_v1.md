# Runbook: Live Micro-Pilot V1 (P132)

## Overview
Safe, minimal validation of the "Live" execution path.
**Goal**: Manually execute **1 trade only** via HTS/MTS, record it, and verify the system reflects the result.

## Prerequisites
- OCI Stage: `NEED_HUMAN_CONFIRM` (Daily Ops triggered).
- Token: Valid OCI Token ready.
- HTS/MTS: Ready for trading.

## Steps

### 1. Preparation (OCI)
Run the daily prepare script to generate the ticket.
```bash
# On PC, run Orchestrator (simplest)
./deploy/pc/daily_operator.ps1
# Follow "PREPARE" guidance.
```
**Verify**: Stage is `AWAITING_HUMAN_EXECUTION`.

### 2. Manual Execution (Human)
1.  Open the Ticket (link provided by dashboard or file).
2.  **Select ONE trade** (smallest notional/size) from the "Top Picks" or "Buy" list.
3.  **Execute that ONE trade** in HTS/MTS.
    -   *Constraint*: Do NOT execute the others.
4.  Note the `executed_quantity` and `price`.

### 3. Record & Submit (PC -> OCI)
1.  **Generate Template**:
    ```powershell
    ./deploy/pc/generate_record_template.ps1
    ```
2.  **Edit Draft** (`local/manual_execution_record_drafts/draft_....json`):
    -   Find the item you executed.
    -   Set `decision`: "EXECUTED".
    -   Fill `executed_quantity` and `average_price`.
    -   For **all other items**, leave as is (or set `decision`: "SKIPPED" if you want to be explicit, but strictly "PARTIAL" usually implies some attempted, some not).
    -   **Important**: Set top-level `execution_result` to `"PARTIAL"` (if you intend to finish here) or `"EXECUTED"` (if you consider this 1 trade as the "full" pilot). *Recommendation: Use "PARTIAL" to test P123 logic.*
3.  **Push Draft**:
    ```powershell
    ./deploy/pc/push_record_draft.ps1
    ```
4.  **Submit (OCI)**:
    ```bash
    # On OCI (or triggered via Orchestrator/SSH)
    ./deploy/oci/manual_loop_submit_record.sh <record_filename>
    ```

### 4. Verification
-   **Dashboard**: `GET /operator` or `./deploy/pc/flight_status.ps1`.
-   **Expect**:
    -   Stage: `DONE_TODAY_PARTIAL` (if result="PARTIAL") or `DONE_TODAY` (if result="EXECUTED").
    -   Mode: `LIVE` (System default).
    -   No "Dry Run" indicators.

## Emergency / Rollback
-   If incorrect record submitted: Use same flow to submit a correction (idempotency key bump might be needed if blocked).
-   If Stage BLOCKED: Check `top_risks` in Dashboard.
