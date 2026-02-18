# STATE_LATEST (Snapshot)

**As Of**: 2026-02-18 (Phase 5 Complete)
**Status**: ACTIVE (UI-First Operations)

---

## 0) One-line Goal
- **Master Plan 완주를 위한 운영/백테스트/튜닝 파이프라인을 UI-First로 안정화**

---

## 1) Environment
- **PC Cockpit**: `http://localhost:8501`
- **PC Backend**: `http://localhost:8000`
- **OCI Operator**: `http://168.107.51.68:8000/operator` (SSH Tunnel: `http://localhost:8001/operator`)
- **OCI Service**: `krx-backend.service` (Systemd)
- **Restart Canon**: `deploy/oci/restart_backend.sh` (Includes port 8000 killer)
- **Forbidden**: `uvicorn backend.main:app` (Manual execution causes port conflict)

---

## 2) Current Mode / Date
- **Mode**: **LIVE** (Pilot V3 Context)
- **System Phase**: Daily Ops (09:00 ~ 15:30)
- **Today(KST)**: 2026-02-18
- **Simulation**: `asof_override: OFF`

---

## 3) Latest Stage (PC vs OCI)
- **PC Stage**: `EXECUTION_COMPLETED` (Expected)
- **OCI Stage**: `EXECUTION_COMPLETED` (Expected)
- **Sync Policy**: **PULL** is for Status/Summary sync. Full report artifacts are fetched on-demand.

---

## 4) Latest Artifacts (Canonical "latest" pointers)
- `ops_summary_latest`: `reports/ops/summary/latest/ops_summary_latest.json`
- `export_latest`: `reports/live/order_plan_export/latest/order_plan_export_latest.json`
- `ticket_latest`: `reports/live/ticket/latest/ticket_latest.md` (Human Readable)
- `record_latest`: `reports/live/manual_execution_record/latest/manual_execution_record_latest.json`
- `portfolio_latest`: `state/portfolio/latest/portfolio_latest.json`
- `draft_latest`: (Transient Object in API, not stored as file)

---

## 5) Token SSOT
- **Authentication**: **EXPORT_CONFIRM_TOKEN** is the Single Source of Truth.
- **Path**: `export_latest.json` -> `human_confirm.confirm_token`
- **Rule**:
  - `Draft` submitted with Token -> Validated against `Export.token`.
  - **Mismatch**: 403 Forbidden (Strict Fail-Closed).
  - **Display**: UI must mask token (e.g. `****`).

---

## 6) What’s Next (Top 3)
1.  **Pilot V3 Verification**: Execute 5-day UI-only trading (1 trade/day limit).
2.  **LLM Tuning Loop**: Parameter optimization based on `daily_flight` results.
3.  **Backtest Engine**: Re-enable backtest with new `contract_execution_gate` rules.

---

## 7) Open Issues (Blockers)
- None (Documentation Overhaul Complete).
