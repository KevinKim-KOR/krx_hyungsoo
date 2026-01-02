# UI/UX Redesign Context Brief

> **For AI Assistant (Gemini)**: This document defines the requirements and context for designing a new Web UI for the `KRX Alertor Modular` system.

---

## 1. Project Goal
The objective is to build a **Modern Web Dashboard** that interfaces with the newly completed Python `Core` logic.
The UI serves three main purposes:
1.  **Configuration Management**: View and edit strategy parameters (`config/`).
2.  **Tuning & Optimization**: Run Optuna tuning sessions and visualize results.
3.  **Reporting & Monitoring**: View daily trading signals and backtest reports.

## 2. Architecture Constraints

### ✅ Target Architecture (Use These)
*   **Backend**: Python **FastAPI** (Located in `backend/`).
    *   *Note*: The backend currently exists but needs to be expanded to wrap the new `core` features.
*   **Core Logic**: All business logic is in `core/`.
    *   **Engine**: `core/engine` (Backtest/Live execution).
    *   **Tuning**: `extensions/tuning` (Optuna integration).
    *   **Config**: `core/utils/config.py` & `config/production_config.py`.
*   **Database**: SQLite (`data/krx_alertor.db`).

### ❌ Ignore (Legacy/Deprecated)
*   **`web/`**: Old Jinja2/Monolithic FastAPI app. **Do not use codes from here.**
*   **`pc/`**: Thick client CLI.
*   **`nas/`**: Legacy deployment scripts.

---

## 3. Key Functional Requirements

### A. Parameter Management (Config)
*   **Goal**: Replace manual editing of `config_prod.yaml` with a UI form.
*   **Backend Logic**: Read/Write `config/production_config.py` or YAML files.
*   **UI Features**:
    - Form-based editor for Strategy Parameters (Weights, MA periods).
    - Validation using Pydantic models (from `core`).

### B. Tuning Dashboard (Optuna)
*   **Goal**: Run hyperparameter optimization and pick the best parameters.
*   **Backend Logic**: Trigger `tools/run_phase15_realdata.py` or `extensions/tuning/runner.py`.
*   **UI Features**:
    - "Start Tuning" button (with progress bar).
    - Pareto Frontier Visualization (Return vs MDD).
    - Table of Top N Trials.
    - "Apply Parameter" button (Updates Config).

### C. System Reports
*   **Goal**: Visualize Backtest and Live Trading results.
*   **Data Source**: `reports/` (HTML/JSON) or DB query.
*   **UI Features**:
    - Interactive Equity Curve charts.
    - Monthly/Yearly Profit Heatmap.
    - Trade Log table.

---

## 4. Reference Files for Design
To understand the data structures, please inspect:
1.  **`docs/design/components/01_core.md`**: Understands the Engine & Signals.
2.  **`docs/tuning/00_overview.md`**: Understands the Tuning System.
3.  **`config/production_config.py`**: The schema for parameters.

## 5. User Persona
*   **Quant Trader**: Needs dense information, quick actions, and reliability.
*   **Style**: Dark mode, High contrast, Data-heavy (Tables/Charts).
