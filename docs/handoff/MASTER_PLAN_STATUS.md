# KRX Alertor Modular — Master Plan Status
> **Version**: 1.0 (2026-02-17)
> **Definition**: A Hybrid Investment Ops System where OCI handles scheduled execution/data and PC handled analysis/control via a secure SSH Bridge.

## 1. System Definition
- **Objective**: Automate Crisis Alpha Strategy (Bear Detection, Chop Filter) with 99.9% availability.
- **Scope**:
  - **OCI (Cloud)**: Data Aggregation, Signal Generation, Order Plan, Live Execution (Cron/Systemd).
  - **PC (Local)**: Backtesting, Portfolio Management, Operations Cockpit (Streamlit), Manual Override.

## 2. Hybrid Architecture (Split Responsibility)
| Component | PC (Control Plane) | OCI (Execution Plane) | Connectivity |
|-----------|--------------------|-----------------------|--------------|
| **UI** | **Cockpit (Streamlit :8501)** | None (Headless) | N/A |
| **Backend** | **Proxy Backend (:8000)** | **Ops Backend (:8000)** | **SSH Tunnel (:8001 -> :8000)** |
| **Data** | Backtest Data (Local) | Live Data / SSOT (Remote) | `API SYNC` (Pull/Push) |
| **Execution** | Simulation / Dry-run | **Real Execution** | `TICKET` Submissions |

**Key Mechanism**:
- **Look-aside Sync**: PC does not touch OCI DB directly. It `PULLs` Snapshot, edits locally, and `PUSHes` changes (Token protected).
- **Deadlock Prevention**: PC Backend writes files directly instead of calling itself via HTTP.

## 3. Master Plan Status (Phase C-S.0 + P146.x)

### Completed Scope
- **Phase C**: Core Strategy Logic, Reconcile, artifact generation.
- **P146.8 (Dashboard)**: Streamlit V1.7, Draft Management, Regenerate API.
- **P146.9 (Resilience)**: `sync.py` Timeout/Deadlock Fix, SSH Tunnel Automation (`connect_oci.bat`).

### Documentation Drift & SSoT Declaration
| Domain | Old Document (Outdated) | **New SSoT (Authoritative)** |
|--------|--------------------------|------------------------------|
| **UI** | `dashboard/index.html` (React) | **`pc_cockpit/cockpit.py` (Streamlit)** |
| **Ops** | `runbook_daily_ops.md` (CLI-only) | **`runbook_pc_oci_split_v1.md`** (Updated for UI) |
| **Sync** | Git Pull only | **API Sync (`contract_sync_v1.md`)** |
| **Backend** | `nohup` / `python` direct | **`systemd` (OCI)** / **`start.bat` (PC)** |

## 4. End-to-End Execution Loop
1.  **Signal Generation (OCI)**:
    - Cron triggers `daily_ops.sh` (09:05 KST).
    - Generates `ops_summary.json` (Signal + Risks).
    - *Evidence*: `reports/ops/summary/ops_summary_latest.json`.
2.  **Review (PC)**:
    - Operator launches `start.bat`.
    - Cockpit -> **PULL** (Syncs OCI -> PC).
    - UI confirms `Order Plan` and `Risks`.
3.  **Override/Plan (PC)**:
    - Operator edits Portfolio or Settings in UI.
    - **PUSH** (Syncs PC -> OCI).
4.  **Draft & Submit (PC/OCI)**:
    - UI generates `Manual Execution Ticket`.
    - **Submit** (API call to OCI).
5.  **Execution (OCI)**:
    - `ticketer.py` or Live Cycle processes the ticket.
    - *Evidence*: `reports/tickets/results/*.json`.

## 5. Current Snapshot (2026-02-17)
- **Active Contract**: `contract_sync_v1.md`, `contract_dashboard_api_v1.md`.
- **Active Runbook**: `runbook_pc_oci_split_v1.md` (needs update to reflect `connect_oci.bat`).
- **Critical Fix**: `sync.py` refactored to use direct file/IO (no loopback).

## 6. Next Priorities (DoD)
1.  **Operational Stability (P147)**:
    - [ ] `stop.bat` clean shutdown verified on all OS.
    - [ ] `connect_oci.bat` auto-reconnect logic improvement.
    - DoD: 5 consecutive days of Ops without manual CLI intervention.
2.  **Governance Tuning (P148)**:
    - [ ] Parameter governance workflow (UI based).
    - DoD: Parameter audit trail fully visible in Cockpit.
3.  **UI Refinement (P149)**:
    - [ ] Remove legacy React artifacts.
    - DoD: `dashboard/` folder archived.
