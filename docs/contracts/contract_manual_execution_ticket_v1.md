# MANUAL_EXECUTION_TICKET_V1 Contract

## Overview
This contract defines the schema for the **Manual Execution Ticket**.
It translates the `EXECUTION_PREP_V1` snapshot into a human-readable format (JSON + CSV + MD) for manual execution.
It serves as the "Job Order" for the human operator.

## Schema: MANUAL_EXECUTION_TICKET_V1

| Field | Type | Description |
|---|---|---|
| schema | String | Fixed "MANUAL_EXECUTION_TICKET_V1" |
| asof | ISO8601 | UTC Timestamp of generation |
| source | Object | Links to source prep |
| source.prep_ref | String | Path to Execution Prep |
| source.prep_asof | ISO8601 | Timestamp of Prep |
| source.confirm_token | String | Token required for execution (inherited) |
| source.plan_id | String | Plan ID |
| decision | String | GENERATED \| BLOCKED \| NO_PREP \| PREP_NOT_READY |
| reason | String | Reason code |
| reason_detail | String | Detailed explanation |
| summary | Object | High-level summary of the ticket |
| summary.total_orders | Integer | Total count of orders |
| summary.total_notional | Number | Estimated total value (KRW) |
| summary.cash_before | Number | Cash before execution (from Portfolio) |
| summary.cash_after_est | Number | Estimated cash after execution |
| guardrails | Object | Inherited Guardrail results |
| guardrails.decision | String | READY \| WARN \| BLOCKED |
| guardrails.violated | Array | List of violated rule codes |
| orders | Array | List of orders tailored for checking |
| orders[].ticker | String | Ticker symbol |
| orders[].side | String | BUY / SELL |
| orders[].qty | Integer | Quantity |
| orders[].limit_price | Number | Limit Price (Nullable) |
| orders[].notional_est | Number | Estimated Value |
| orders[].display | String | Human readable string |
| orders[].checks | Object | Per-order validation (qty_ok, etc.) |
| copy_paste | String | **Optimized string for HTS/MTS input** |
| output_files | Object | paths to generated friendly formats |
| output_files.csv_path | String | Path to CSV version |
| output_files.md_path | String | Path to Markdown version |
| evidence_refs | Array | Paths to supporting documents |

## Logic
- **Input**: `EXECUTION_PREP_V1` (Latest)
- **Validation**:
    - Check if Prep exists and is `READY`.
    - If Prep is BLOCKED/NOT_READY -> Ticket is BLOCKED.
- **Output**:
    - JSON (Machine readable SSOT)
    - CSV (Spreadsheet friendly)
    - MD (Review friendly)

## File Paths
- **Latest**: `reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest.json`
- **Snapshots**: `reports/live/manual_execution_ticket/snapshots/manual_execution_ticket_YYYYMMDD_HHMMSS.json`
