# P146.2/3: UI-Only Draft Manager & Fail-Soft Viewer

## P146.2 Features
- **Backend**: Draft Record Generation API (`POST /draft`).
- **Fail-Soft**: Evidence Resolver returns `raw_preview` on JSON parse error.
- **Consistency**: Forced `DRY_RUN` execution mode in Replay.

## P146.3-HOTFIX: Draft Manager & UX Refinement
### Changes
- **Backend**: 
    - **Robust Generation**: Removed strict `OPS_SUMMARY` dependency. Now relies on `TICKET` & `EXPORT` artifacts.
    - **Guidance**: Added error guidance text to Evidence Resolver response for corrupted files.
- **Frontend (Operator Dashboard)**:
    - **Draft Manager**: Added Preview (Pretty JSON), Token Input with Toggle, and clear instructions.
    - **Legacy Upload**: Moved to `<details>` accordion to reduce clutter.
    - **Record Tile**: Renamed to "RECORD (VIEW ONLY)" to prevent confusion.

### Validation
1. **Generate Draft**: Click "Generate Draft (Server)". Verify Preview appears with JSON content.
2. **Submit Draft**: Enter Token (use Eye toggle to check) and click Submit. Verify success.
3. **Corruption Test**: View a corrupted file. Verify "FILE CORRUPTED" guidance appears.

## P146.8: Token & Sync (Feb 17, 2026)

### Functional Changes
- **Token Handling (SSOT)**: 
  - **LIVE Mode**: Enforces strict match against `EXPORT` artifact's `confirm_token`. UI shows masked hint.
  - **DRY_RUN Mode**: Token input hidden and optional (auto-filled by server).
- **Ticket MD Sync**: Regenerating a ticket (or Sync Cycle) now also regenerates the `.md` file with the correct Plan ID and Token.
- **PC-OCI Sync**: "Apply to OCI" button in PC Cockpit now strictly Pushes settings to OCI and Reads them back for verification.

### Troubleshooting (Post-Deployment)
1. **Dashboard 500 Error**: Caused by missing `logger` import. Fixed.
2. **Missing Draft / No Action Today**:
   - Cause: OCI Server `ops_summary.json` was reset to current day (empty) during restart/deployment, losing Replay Context (Feb 13 data).
   - Fix: Manually restored `ops_summary` and `order_plan_export` from `snapshots/` archive for Feb 13.
   - Note: Ticket/Draft snapshots were missing; user advised to regenerate them via Dashboard.

## P146.9: System Resilience (Timeout & Health)

### Functional Changes
- **PC Cockpit**: 
    - **Health Check**: Added "System Health" sidebar with Latency Metric to Local Backend.
    - **Configurable Timeout**: Added "Timeout (sec)" input for "Pull from OCI" to handle slow connections (default 120s).
- **Backend (OCI Proxy)**:
    - **Robust Sync**: `api/sync` endpoints now accept `timeout_seconds` parameter to dynamically adjust OCI timeouts.

### Validation
1. **Health Check**: Click "Check Connectivity" in Sidebar. Verify latency is shown (e.g., "Local API: 15ms").

### Troubleshooting (Failed Sync)
1. **Loopback Error**:
   - Cause: `OCI_BACKEND_URL` was not set in `start.bat`, causing PC Backend to default to `localhost:8000` (itself) instead of Tunnel (`localhost:8001`).
   - Fix: Added `set "OCI_BACKEND_URL=http://localhost:8001"` in `start.bat`.
2. **Schema Validation Error**:
   - Cause: `app/routers/sync.py` rigidly checked for `rows` key. New Ops Summary V1 schema is flat (no `rows`).
   - Fix: Relaxed validation to accept either `rows` or `schema` keys.
3. **Design Drift (Contract Mismatch)**:
   - Issue: Docs stated `reports/ops/summary/ops_summary_latest.json`, but implementation used `reports/ops/summary/latest/ops_summary_latest.json`.
   - Fix: Updated 9 contract files (`docs/contracts/*.md`) to match `latest/` implementation.

## Documentation Overhaul (P0/P1/P2) — P146 UI-First Standard

A major documentation refactoring was performed to align with the "PC Control / OCI Execution" architecture.

### 1. High-Level Guides
- **README.md**: Rewritten for UI-First. Removed CLI/Dashboard legacy. Added "Systemd Only" warning.
- **STATE_LATEST.md**: Fixed "Parallel Universe". Defined 3 Daily Ops Elements (Push/Run/Pull) and Token Truth.

### 2. Core Contracts
- **Operator API**: Created `contract_operator_api_v1.md` (Replaced Dashboard API). Defined Draft/Submit endpoints.
- **Sync Protocol**: Rewrote `contract_sync_v1.md` to define 3 types (SSOT, Status, Artifact) and Timeout rules.
- **Evidence Ref**: Updated `contract_evidence_ref_v1.md` to allow `latest/` and added Viewer Rules (Fail-Soft).
- **Ticket & Record**: Clarified `Export` as Source of Truth. Added `Draft` concept and schema.

### 3. Runbooks
- **New Standard**: Created `docs/runbooks/runbook_ui_daily_ops_v1.md` (Checklist for Daily UI Ops).
- **Pilot V3**: Updated `runbook_live_micro_pilot_v3.md` to use the new UI-First procedure with Pilot constraints.
- **Deployment**: Updated `runbook_deploy_v1.md` to enforce `systemd` and forbid manual `uvicorn`.

### 4. Operational Docs
- **Active Surface**: Updated `active_surface.json` with new paths and endpoints.
- **Smoke Test**: Rewrote `smoke_test.md` with 6 UI-First scenarios.

## SSOT Consolidation (Final Cleanup)

- **Structure**: Removed `docs/handoff/` directory. All definitive documentation is now under `docs/SSOT/`.
- **New Protocol**: strict "Documentation Update Protocol" added to `PROJECT_CONSTITUTION.md`.
    - Every session must update `SSOT`, `walkthrough.md`, and `task.md`.
- **References**: Updated `contracts_index.md` to point to `docs/SSOT/STATE_LATEST.md`.
