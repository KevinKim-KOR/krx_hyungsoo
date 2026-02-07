# MANUAL_EXECUTION_RECORD_V1 Contract

## Overview
This contract defines the schema for the **Manual Execution Record**.
It documents the *result* of the manual execution performed by the human operator.
It is the "Receipt" or "Flight Log" of the manual operation.

## Schema: MANUAL_EXECUTION_RECORD_V1

| Field | Type | Description |
|---|---|---|
| schema | String | Fixed "MANUAL_EXECUTION_RECORD_V1" |
| asof | ISO8601 | UTC Timestamp of recording |
| source_refs | Object | Reference paths |
| source_refs.execution_prep_ref | String | Path to Prep |
| source_refs.ticket_ref | String | Path to Ticket |
| source_refs.order_plan_export_ref | String | Path to Export |
| linkage | Object | ID Linkage for Integrity |
| linkage.bundle_id | String | Strategy Bundle ID |
| linkage.plan_id | String | Order Plan ID |
| linkage.export_id | String | Export ID (if available, or uses Plan ID) |
| linkage.ticket_id | String | Ticket Source ID |
| operator_proof | Object | Proof of manual work |
| operator_proof.filled_at | ISO8601 | Time of execution completion |
| operator_proof.method | String | HTS \| MTS \| OTHER |
| operator_proof.evidence_note | String | Short note |
| dedupe | Object | Anti-duplication |
| dedupe.idempotency_key | String | Unique Key (ticket_id + filled_at + plan_id) |
| decision | String | EXECUTED \| PARTIAL \| SKIPPED \| BLOCKED |
| summary | Object | Execution stats |
| summary.orders_total | Integer | Total orders in ticket |
| summary.executed_count | Integer | Number of orders executed |
| summary.skipped_count | Integer | Number of orders skipped |
| items | Array | Execution details per order |
| items[].ticker | String | Ticker symbol |
| items[].side | String | BUY/SELL |
| items[].requested_qty | Number | Original Qty |
| items[].status | String | EXECUTED \| SKIPPED |
| items[].executed_qty | Number | Actual executed Qty |
| items[].note | String | Human note (optional) |
| reason | String | Overall reason |
| reason_detail | String | Detail |
| evidence_refs | Array | Supporting docs |

## Logic
- **Input**: User Submission (JSON Body), `MANUAL_EXECUTION_TICKET_V1` (Latest), `EXECUTION_PREP_V1` (Latest).
- **Validation**:
    - Verify Token matches Prep/Ticket.
    - Check Ticket consistency.
- **Output**: Immutable JSON Record.

## File Paths
- **Latest**: `reports/live/manual_execution_record/latest/manual_execution_record_latest.json`
- **Snapshots**: `reports/live/manual_execution_record/snapshots/manual_execution_record_YYYYMMDD_HHMMSS.json`
