# Deprecated Inventory Log (Legacy Quarantine)

**Date**: 2025-12-29
**Action**: Moved to `_archive/` directory.

The following components have been removed from the active surface and quarantined. They should not be imported or executed in the production pipeline.

## 1. Web Interface (Old)
*   **Source**: `web/`
*   **Description**: Legacy FastAPI/Jinja2 implementation. Replaced by `backend/` (Phase 14).
*   **Key Files**: `main.py`, `routers/`, `templates/`

## 2. PC Client (Old)
*   **Source**: `pc/`
*   **Description**: Legacy Fat Client or script runner. Replaced by centralized `deploy/` scripts.

## 3. Daily Scripts (Old)
*   **Source**: `scripts/daily/`
*   **Description**: Fragmented daily runners. Replaced by `deploy/run_daily.sh` & `.ps1`.

## 4. Tools (Old Runners)
*   **Files**:
    *   `tools/run_phase15_clean.py`
    *   `tools/run_phase8_diag.py`
    *   `tools/run_phase7_2_diag.py`
*   **Reason**: Replaced by unified `app.cli.alerts` and `tools.paper_trade_phase9`.

---
**Restoration Policy**: If any logic from these files is needed, copy the snippet into a new `core` module strictly following current architecture rules. Do not move files back.
