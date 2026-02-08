# Contract: Dry Run Record V1

## Overview
Represents a simulated execution of the Daily Manual Loop. No actual orders are placed.

## Schema
```json
{
  "spec_version": "1.0",
  "id": "dry_run_20260208_...",
  "type": "DRY_RUN",
  "timestamp": "2026-02-08T12:00:00.000000",
  "linkage": {
    "plan_id": "plan_...",
    "ticket_id": "ticket_..."
  },
  "execution_result": "DRY_RUN",
  "decision": "COMPLETED",
  "items": [], 
  "operator_confirm": true,
  "meta": {
    "generator": "app/generate_dry_run_record.py",
    "host": "oci-instance-..."
  }
}
```

## Constraints
1.  **No Execution**: No external calls to broker.
2.  **Linkage**: Must match latest Ticket and Plan.
3.  **Dedupe**: Idempotency key checked (optional for dry run, but good practice).
