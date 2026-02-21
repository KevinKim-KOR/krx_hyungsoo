# STATE_LATEST (Snapshot)

**As Of**: 2026-02-18 (Phase 5 Complete)
**Status**: ACTIVE (UI-First Operations)

---

## 0) One-line Goal
- **Master Plan 완주를 위한 운영/백테스트/튜닝 파이프라인을 UI-First로 안정화**

---

## 1) Environment (Facts)
- **PC Cockpit**: `http://localhost:8501`
- **PC Backend**: `http://localhost:8000`
- **OCI Operator**: `http://168.107.51.68:8000/operator` (Direct) / `http://localhost:8001/operator` (Tunnel)
- **OCI Backend**: `http://168.107.51.68:8000` (Service: `krx-backend.service`)
- **Restart Canon**: `deploy/oci/restart_backend.sh` (The **ONLY** allowed restart method)
- **Forbidden**: `uvicorn` manual dispatch (Causes port 8000 zombie)

---

## 2) Current Mode / Date
- **Mode**: **LIVE** (Pilot V3 Context)
- **System Phase**: Daily Ops (09:00 ~ 15:30)
- **Today(KST)**: 2026-02-18 (Phase 5)
- **Simulation**: `asof_override: OFF`

---

## 3) Latest Stage & Transition
- **Current Stage**: `DONE_TODAY` (Expected when finished)
- **Stage Transition Table** (Based on `generate_ops_summary.py`):
  1. `NO_ACTION_TODAY` (Start/No Trades)
  2. `NEED_HUMAN_CONFIRM` (Prep Output, Waiting for Export Token)
  3. `AWAITING_HUMAN_EXECUTION` / `AWAITING_RECORD_SUBMIT` (Ticket Issued, Waiting for Submit)
  4. `DONE_TODAY` (Record Submitted & Validated)
  5. `BLOCKED` / `ERROR` (Exception/Validation Fail)

---

## 4) Latest Artifacts (Canonical "latest" pointers)
- `ops_summary_latest`: `reports/ops/summary/latest/ops_summary_latest.json`
- `export_latest`: `reports/live/order_plan_export/latest/order_plan_export_latest.json`
- `ticket_latest`: `reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest.md` (and `.json`, `.csv`)
- `record_latest`: `reports/live/manual_execution_record/latest/manual_execution_record_latest.json`
- `portfolio_latest`: `state/portfolio/latest/portfolio_latest.json`

---

## 5) Token SSOT & Actions
- **Source**: `EXPORT_CONFIRM_TOKEN` (in `export_latest.json`)
- **Actions Requiring Token**:
  1. **PC**: `PUSH (Settings)` (Block if no token)
  2. **OCI**: `SUBMIT (Draft)` (Block if mismatch)
  - *Note*: `PULL` and `RUN AUTO OPS` do not require token.
- **Display**: Masked only (`****`).

---

## 6) PC -> OCI Sync Payload (Push)
- **Files Transferred** (via `api/sync/push` in P146):
  1. `state/portfolio/latest/portfolio_latest.json` (Normalized)
  2. `state/runtime/asof_override_latest.json` (Mode/Date)
  - *Note*: Strategy Bundle (which includes params) is generated separately and must be present on OCI, but the `Push` button primarily overwrites the two files above.

---

## 7) What’s Next (Top 3)
1.  **Pilot V3 Verification**: Execute 5-day UI-only trading (1 trade/day limit).
2.  **LLM Tuning Loop**: Parameter optimization based on `daily_flight` results.
3.  **Backtest Engine**: Re-enable backtest with new `contract_execution_gate` rules.

---

## 8) Open Issues (Blockers)
- None (Documentation Overhaul Complete).
