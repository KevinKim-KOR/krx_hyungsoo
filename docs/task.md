- [x] **P146.8 Dashboard & Sync (Token/Ticket MD/PC Sync)**
    - [x] A: Dashboard API Update (Token Hint/Required Flag) `backend/operator_dashboard.py`
    - [x] B: Submit Draft Logic Update (DRY_RUN vs LIVE) `backend/main.py`
    - [x] C: Sync Cycle Ticket MD Regeneration `backend/main.py`
    - [x] D: PC Apply to OCI Sync (PUSH + Read-Back) `pc_cockpit/cockpit.py`
    - [x] UI: Operator Token Hint & Validation `templates/operator.html`
    - [x] Fix: Dashboard 500 Error (logger) & OCI Data Restore

- [x] **P146.9 System Resilience (Timeout & Health)**
    - [x] Cockpit: Increase request timeouts (Configurable for Pull)
    - [x] Cockpit: Add Latency Health Check UI (Local & OCI)
    - [x] Backend: Audit OCI call timeouts (Dynamic)
    - [x] Fix: PULL Logic (Sync Ops Summary from OCI) `app/routers/ssot.py`, `sync.py`
    - [x] Fix: Path Mismatch (latest dir) `OPS_SUMMARY_PATH`
    - [x] Fix: Ref Validator (Allow Ops Summary) `app/utils/ref_validator.py`
    - [x] Documentation: Contracts (Sync/Dashboard) & Runbook (P146.8/9)
    - [x] Cockpit UI Optimization (V1.7): No Sidebar, Main Block Connectivity, Clean SSOT
    - [x] Fix: Start Script (Duplicate Window) `start.bat`
    - [x] Fix: Loopback Issue (Set OCI_BACKEND_URL) `start.bat`
    - [x] Fix: Sync Validation (V1 Schema Support) `app/routers/sync.py`
    - [x] Process: Created Deployment Workflow `.agent/workflows/deploy_sync.md` (Commit->Push->Pull + Docs)
    - [x] Documentation: Design Reality Sync (Contracts updated to matches `latest/` implementation)

- [x] **Documentation Patch (P0: Critical Alignment)**
    - [x] **Phase 1: High-Level Guides**
        - [x] `README.md`: UI-First (PC Cockpit / OCI Operator), Remove Dashboard, Add Warnings
        - [x] `STATE_LATEST.md`: Fix Parallel Universe, 3 Daily Ops Elements, Token Truth
    - [x] **Phase 2: Core Contracts (P0)**
        - [x] `contract_dashboard_api_v1.md` -> `contract_operator_api_v1.md` (Rename/Refactor)
        - [x] `contract_sync_v1.md`: Split 3 Types (SSOT, Status, Artifact)
        - [x] `contract_evidence_ref_v1.md`: Allow `latest/` & Viewer Rules (Raw/Fail-Soft)
        - [x] `contract_manual_execution_ticket_v1.md`: Source=Export, Token=Export
        - [x] `contract_manual_execution_record_v1.md`: Add Draft Concept
    - [x] **Phase 3: New Artifacts**
        - [x] `runbook_ui_daily_ops_v1.md` (NEW): Step-by-step UI Guide
        - [x] `contract_manual_execution_record_draft_v1.md` (NEW): Draft Schema
    - [x] **Phase 4: Operational Docs**
        - [x] `active_surface.json`: Update Paths, Remove Dashboard
        - [x] `runbook_deploy_v1.md`: Systemd Only, Warn Manual Uvicorn
        - [x] `smoke_test.md`: UI-Based Scenarios
    - [x] **Phase 5: Cleanup & Consistency (P1/P2)**
        - [x] P1 Contracts: Settings, Order Plan Export, Execution Gate
        - [x] Index: `contracts_index.md` Update
        - [x] Deprecation: Mark legacy runbooks as DEPRECATED

## Future Roadmap (Master Plan)

- [ ] **P147: Operational Stability**
    - [ ] `stop.bat` clean shutdown verification.
    - [ ] `connect_oci.bat` auto-reconnect logic.
    - [ ] Goal: 5 consecutive days without CLI intervention.

- [ ] **P148: Governance & Parameters**
    - [ ] UI-based Parameter Governance (LLM Tuning Loop).
    - [ ] Audit trail for parameter changes.

- [ ] **P149: UI Refinement**
    - [ ] Archive legacy `dashboard/` (React).
    - [ ] Full transition to Streamlit Cockpit.
