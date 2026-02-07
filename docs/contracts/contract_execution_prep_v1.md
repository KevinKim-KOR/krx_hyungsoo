# EXECUTION_PREP_V1 Contract

## Overview
This contract defines the schema for the **Execution Preparation** phase. 
It serves as an immutable snapshot of orders *after* human confirmation but *before* actual execution/broadcast.
It acts as a safety gate, locking the orders with a confirmation token.

## Schema: EXECUTION_PREP_V1

| Field | Type | Description |
|---|---|---|
| schema | String | Fixed "EXECUTION_PREP_V1" |
| asof | ISO8601 | UTC Timestamp of preparation |
| source | Object | Links to source documents |
| source.export_ref | String | Path to Order Plan Export |
| source.export_asof | ISO8601 | Timestamp of Export |
| source.order_plan_ref | String | Path to Original Order Plan |
| source.plan_id | String | Plan ID |
| source.confirm_token | String | Token provided by human to unlock execution |
| decision | String | READY \| BLOCKED \| NO_EXPORT \| NO_PLAN \| TOKEN_MISMATCH |
| reason | String | Reason code |
| reason_detail | String | Detailed explanation |
| orders | Array | Immutable list of orders to be executed |
| safety | Object | Safety checks summary |
| safety.orders_count | Integer | Total order count |
| safety.max_orders_allowed | Integer | Configured limit (Default: 20) |
| safety.max_single_order_ratio | Float | Configured ratio limit (Default: 0.35) |
| verdict | String | PASS \| WARN \| BLOCKED (Safety Verdict) |
| manual_next_step | String | Instructions for next step (execution) |
| evidence_refs | Array | Paths to supporting documents |

## Logic
- **Input**: `ORDER_PLAN_EXPORT_V1`, User Input (`confirm_token`).
- **Validation**:
    - Check if Export exists and is GENERATED.
    - Validate `confirm_token` matches `export.human_confirm.confirm_token`.
    - Fail-Closed: If Export/Plan is BLOCKED, Prep is BLOCKED.
- **Output**: Immutable JSON snapshot.

## File Paths
- **Latest**: `reports/live/execution_prep/latest/execution_prep_latest.json`
- **Snapshots**: `reports/live/execution_prep/snapshots/execution_prep_YYYYMMDD_HHMMSS.json`
