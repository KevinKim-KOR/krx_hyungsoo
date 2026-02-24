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

## P150: Global KST Synchronization (Feb 20, 2026)

### Functional Changes
- **Date Formatting**: Ensured all generated JSON and MD artifacts (`ops_summary_latest.json`, `manual_execution_ticket_latest.json`, etc.) consistently output timestamps in Korean Standard 시(+09:00).
- **Timezone Safety**: Replaced naive and explicit `timezone.utc` objects with robust KST generation logic, standardizing dashboard logic to avoid naive vs timezone-aware Python collisions.

## P152: Auto Ops Force Recompute & Idempotency (Feb 22, 2026)

### Functional Changes
- **Backend Generator Scripts**: Idempotency checks were added. The generator scripts now check if an artifact was already created today to avoid accidental overwrites. They output `[RESULT: SKIP_OR_REGEN]` natively to `stdout` which is parsed by the orchestrator.
- **Backend Orchestration**: `backend/main.py` replaced standard imports with `subprocess.run` to orchestrate generator scripts independently and parse their `[RESULT:]` codes cleanly.
- **PC Cockpit**: Added a `☑ Force Recompute (Overwrite)` checkbox for operators. Output toasts were improved to display status such as `RECO: REGEN | ORDER_PLAN: SKIP`.

## P153: RECO Math Bug Fix & Force Cascade Architecture

### Functional Changes
- **RECO Math Bug Fix**: Corrected a bug in `app/generate_reco_report.py` where `buy_count` ignored `ADD` actions and only accounted for `BUY`.
- **Key-Based Idempotency**: `app/generate_order_plan.py` and `app/generate_order_plan_export.py` now utilize unique keys (`reco_key` and `order_plan_key`) instead of relying solely on the date to decide whether to SKIP or REGEN.
- **Force Cascade**: If an upstream script (like RECO) is regenerated, the backend orchestrator now automatically propagates a `--force` flag (Force Cascade) down to sub-components (PLAN and EXPORT) to guarantee full propagation of the new state.
- **Cash Allocation Logic**: If the RECO report intends to `ADD` or `NEW_ENTRY` tickers, the generator now pulls their prices from `strategy_bundle_latest.json`'s auxiliary timing metadata to compute accurate quantities and allocate the available `cash` evenly among them.
- **Improved UI Tracing**: The orchestrator parses the `SKIP reason=same_reco_key` values and feeds them back into the Cockpit frontend to provide greater visibility into exactly why a phase was skipped.

## P154: Force Cascade Architecture & UI Result Persistence (Feb 22, 2026)

### Functional Changes
- **Strict Fail-Closed Cascade**: The Force Cascade logic (`--force` propagation to downstream stages) was restricted to only activate when the execution mode (`_exec_mode`) is `DRY_RUN` or `REPLAY`. This prevents dangerous cascading overwrites in `LIVE` production mode while allowing flexible recalculation during testing.
- **Robust Key Detection**:
  - `generate_order_plan.py` now explicitly records `reco_report_id`, `reco_created_at`, `bundle_id`, and `reco_key` within the `source` block to provide absolute traceability of the upstream RECO report it is based on.
  - `generate_order_plan_export.py` now generates its `order_plan_key` by directly hashing the stringified, sorted `orders` array. This ensures that any change in the actual order contents will trigger an export regeneration, rendering it immune to metadata drifts.
- **UI Result Persistence**: The PC Cockpit (`pc_cockpit/cockpit.py`) now stores the Auto Ops execution result (e.g. `✅ RECO: REGEN | ORDER_PLAN: SKIP`) into `st.session_state["last_cycle_result"]`. This prevents the status message from instantly disappearing when the page invokes `st.rerun()`.

## P155: ORDER_PLAN Always-Write & Fail-Fast Orchestrator (Feb 22, 2026)

### Functional Changes
- **Fail-Fast Orchestrator**: The backend `live/cycle/run` API now aggressively halts execution (`fail-fast`) if any subprocess script returns a non-zero exit code. Instead of silently ignoring it, the API records the stdout and stderr tails alongside the return code into `reports/ops/run/latest/ops_run_latest.json`.
- **Always-Write Latest Order Plan**: The `generate_order_plan.py` generator was wrapped in an overarching try-except block to ensure that even if data processing (like price fetching or cash allocation) structurally fails, the `order_plan_latest.json` file is explicitly written out with a status of `ERROR` and `PRICE_MISSING_OR_ALLOC_FAIL`.
  - This solves the issue where previously failed operations would retain 'stale' Order Plans with old `bundle_id` versions, creating synchronization mismatch downstream.
- **UI Error Presentation**: The Cockpit UI (`pc_cockpit/cockpit.py`) gracefully catches HTTP 500 responses containing partial `ops_run` dumps within the detail payload. This ensures that when the backend fails fast, operators immediately see exactly which generator crashed and the accompanying reason on screen (e.g., `❌ RECO: REGEN | ORDER_PLAN: FAIL (SCRIPT_ERROR)`).

## P163: Legacy Backtest Engine Audit & Handoff (Feb 23, 2026)

### Findings
- Conducted a full codebase audit for the backtest engine.
- Revealed that the active `app/` architecture contains **0** actual backtest engine files and relies entirely on a 36-line mock JSON file (`reports/backtest/latest/backtest_result.json`).
- Discovered the complete, production-grade backtest engine still preserved intact within `_archive/legacy_20260102/`.

### Actions Taken
- **Deep Analysis**: Analyzed all 33 legacy files (~5,600 lines) across 5 subsystem layers (Core Engine, Strategy, Execution Runner, Tuning & Promotion, Data Infra, and Config).
- **Handoff Document Generation**: Created `docs/archive/legacy_backtest_engine_analysis.md` encompassing architectural breakdowns, mermaid diagrams, API signatures, metric formulas, pipeline routing, and a migration gap analysis.
- **Active Surface Registry**: Protected the newly generated analysis document by explicitly registering it within `docs/ops/active_surface.json` to prevent accidental deletion during automated cleanups.

## P164: Backtest Engine Active Migration — Phase 1 (Feb 23, 2026)

### What Changed
- **New Package**: Created `app/backtest/` with 5 subpackages (`engine/`, `strategy/`, `infra/`, `runners/`, `utils/`), 10 migrated source files, 6 `__init__.py` files.
- **Import Remapping**: All `from core.*` imports replaced with `from app.backtest.*`. Removed `FORCE_ENTRY_ONCE` debug artifact from runner.
- **Simplified `calendar_kr.py`**: Removed `core.utils.datasources` dependency, uses yfinance directly.
- **yfinance 0.2.x Fix**: Added MultiIndex column flattening to `data_loader._normalize_df()`.
- **CLI Entry Point**: `app/run_backtest.py` — reads strategy bundle, downloads OHLCV, runs engine, writes atomic result + snapshot.
- **Dependencies**: Added `yfinance>=0.2.0` and `joblib>=1.0.0` to `requirements.txt`.

### Verification Results

| Check | Result |
|---|---|
| (A) `_archive` references in `app/backtest/` | **0** ✅ |
| (B) `python -m app.run_backtest --mode quick` | **OK** — 4 tickers, 468 rows, 127 trades ✅ |
| (C) `backtest_result.json` real metrics | **CAGR=48.81, total_return=21.25** ✅ |

### Known Limitations (P165 scope)
- `mdd=0.0` and `sharpe=0.0` — engine metric calculation may need review for the 6-month quick period.
- Ticker-level metrics duplicate portfolio-level values (runner returns portfolio-level only).
- UI buttons not connected (deferred to P165).

## P165: Backtest 결과 품질 보정 + PC Cockpit 탭 (Feb 24, 2026)

### What Changed
- **MDD/Sharpe 재계산**: `format_result()`에서 `nav_history`로부터 equity_curve/daily_returns를 추출하여 MDD=7.58%, Sharpe=2.22 산출 (기존 0.0 → 실값)
- **Ticker별 Buy&Hold 독립 계산**: 포트폴리오 복붙 제거, 각 종목의 OHLCV 종가로 CAGR/MDD/Win Rate 독립 산출 (4종목 모두 다른 값)
- **PC Cockpit 🧪 백테스트 탭**: 고정 탭 신설, Mode 선택(Quick/Full), ▶️ CLI 실행 버튼, summary/tickers/top_performers 표시, LLM 복붙용 JSON 블록

### Verification Results

| Check | Result |
|---|---|
| `summary.mdd != 0` | **7.5813** ✅ |
| `summary.sharpe != 0` | **2.2239** ✅ |
| Ticker CAGRs not all equal | **4 unique values** ✅ |
| `meta.equity_curve` exists | **117 pts** ✅ |
| `meta.daily_returns` exists | **116 pts** ✅ |
