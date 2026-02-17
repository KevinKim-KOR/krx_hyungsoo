# KRX Alertor Modular — STATE_LATEST (Handoff)

> **Meta-SSoT**: [MASTER_PLAN_STATUS.md](MASTER_PLAN_STATUS.md) (Architecture/Drift Definition)
> **Protocol**: [COLLAB_PROTOCOL.md](COLLAB_PROTOCOL.md) (User-Agent Rules)

---

## 0) 오늘 결론 (2026-02-17)
- ✅ **현재 운영 상태**: [OK] (P146.9 Sync Deadlock Fixed)
- 🧩 **핵심 변경**:
    - **Sync Architecture**: `sync.py` now writes files directly to avoid Proxy Loopback Deadlock.
    - **Connectivity**: `connect_oci.bat` added for SSH Tunnel Automation.
    - **UI**: Cockpit(Streamlit) is the Primary Control Plane.

---

## 1) 아키텍처 요약 (Hybrid Split)
- **PC (Control Plane)**:
    - **Role**: Data Review, Strategy Config, Portfolio Edit.
    - **Sync**: **PULL** (State/Ops Summary) -> Edit -> **PUSH** (Override/Portfolio).
    - **UI**: Streamlit Cockpit (`localhost:8501`).
- **OCI (Execution Plane)**:
    - **Role**: Data Aggregation, Signal Generation, Real Execution.
    - **Sync**: Passive (API Endpoint for PC PULL/PUSH).
    - **Backend**: Systemd Service (`krx-backend`).

---

## 2) Git / 브랜치
- **Repo**: `krx_hyungsoo`
- **Branch**: `archive-rebuild`
- **PC State**: Synced with OCI (via API). Git Push is secondary backup.
- **OCI State**: Running `P146.9-FIX` code.

---

## 3) OCI 서비스 상태 (Target)
- **Service**: `krx-backend` (Port 8000)
- **Access**: Via SSH Tunnel (`localhost:8001` -> `reserved:8000`).
- **Health Check**:
  ```powershell
  curl http://localhost:8001/api/ops/health
  ```

---

## 4) 운영 루프 (The Loop)
1.  **09:05 KST**: OCI `daily_ops.sh` runs (Cron). Generates `ops_summary`.
2.  **09:10 KST**: Operator opens PC `start.bat`.
    - **PULL**: Syncs `ops_summary` to PC.
3.  **Review**: Operator checks Dashboard.
    - If `RISK: OK`, **Draft Ticket**.
    - If `RISK: WARN`, Edit Portfolio/Settings -> **PUSH** -> **Draft Ticket**.
4.  **Execution**: Submit Ticket -> OCI Executes.

---

## 5) 주요 이슈 및 해결 (Log)
- **2026-02-17 (P146.9)**:
    - **Symptom**: `PULL` Timeout (30s) despite 120s setting.
    - **Root Cause**: `sync.py` called `requests.post(localhost)` which blocked the async event loop (Deadlock).
    - **Fix**: Refactored `sync.py` to use direct file I/O.
    - **Artifacts**: `deploy/pc/connect_oci.bat`, `docs/contracts/contract_sync_v1.md`.

---

## 6) 다음 단계 (Next Steps)
- **P147 (Stability)**: `stop.bat` reliability, Tunnel auto-reconnect.
- **P148 (Governance)**: UI-based Parameter Audit.
- **P149 (Cleanup)**: Remove legacy React code.

---

## 7) 1-Line Verification
- **System Health**:
  ```powershell
  curl -s http://localhost:8001/api/ops/health | python -m json.tool
  ```
- **Sync Check**:
  ```powershell
  curl -s http://localhost:8001/api/ops/summary/latest | findstr "updated_at"
  ```
