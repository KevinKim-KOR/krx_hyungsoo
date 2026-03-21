# P193 Cockpit UI Inventory Map

## Live Ops
### Sections
- Operations (`cockpit.py` line 520+)
### Cards/Buttons
- [Button] `📥 PULL (OCI)` | Inputs: OCI_OPS_TOKEN (Auto Load) | Calls: `POST /api/sync/pull` | Reads/Writes: `state/strategy_bundle/latest/strategy_bundle_latest.json` | Success check: file mtime changes
- [Button] `▶️ Run Auto Ops Cycle` | Inputs: OCI_OPS_TOKEN (Auto Load), Force Recompute (Checkbox) | Calls: `POST /api/live/cycle/run?confirm=true&force={bool}` | Reads/Writes: `reports/live/reco/...` & `reports/live/order_plan/...` | Success check: UI Success, reports asof increases

### Notes
- `OCI_OPS_TOKEN` (.env) is required for production synchronization via OCI (Fail-Closed).
- `Confirm Token` is now strictly used only for manual execution in `Operator Dashboard`, not for PC Sync.

---

## Workflow Sync
### Sections
- Sync Actions
### Cards/Buttons
- [Button] `📤 OCI 반영 (1-Click Sync)` | Inputs: OCI_OPS_TOKEN (Auto Load) | Calls: `POST /api/sync/push_bundle` | Reads/Writes: push bundle configuration | Success check: UI success message

---

## System Config
### Sections
- Connectivity Check
### Cards/Buttons
- [Button] `Check Connectivity 💓` | Inputs: None | Calls: API Health check / Local Ping | Reads/Writes: None | Success check: UI success toast

---

## Strategy Parameter
### Sections
- Analysis
### Cards/Buttons
- [Button] `🔄 Run Analysis (Param Search)` | Inputs: Search bounds | Calls: Param analysis logic | Reads/Writes: In-memory simulation | Success check: UI renders table
- [Button] `Apply Rank N` | Inputs: Selected Rank | Calls: None (State update) | Reads/Writes: `state/params/latest/strategy_params_latest.json` | Success check: file mtime changes

---

## Strategy Timing
### Sections
- Analysis
### Cards/Buttons
- [Button] `🔄 Run Analysis (Timing)` | Inputs: Lookback ranges | Calls: Timing signal evaluation | Reads/Writes: Data cache | Success check: Plot rendering

---

## Backtest
### Sections
- Run
### Cards/Buttons
- [Button] `▶️ Run Backtest` | Inputs: Mode (quick/full) | Calls: `subprocess` executing `run_backtest.py` | Reads/Writes: Reads `state/strategy_bundle...`, Writes `reports/backtest/latest/backtest_result.json` | Success check: `reports/backtest/latest/backtest_result.json` mtime changes

---

## Tuning
### Sections
- Run
### Cards/Buttons
- [Button] `▶️ Run Tune` | Inputs: Mode (quick/full) | Calls: `subprocess` executing `run_tune.py` | Reads/Writes: Writes `reports/tuning/tuning_results.json` | Success check: file mtime changes

---

## Portfolio
### Sections
- Management
### Cards/Buttons
- [Button] `Initialize Empty Portfolio` | Inputs: None | Calls: Direct state file initialization | Reads/Writes: Writes `state/portfolio/latest/portfolio_latest.json` | Success check: empty portfolio structure created
- [Button] `📤 Push to OCI` | Inputs: None | Calls: `POST /api/sync/push` | Reads/Writes: uploads `portfolio_latest.json` | Success check: UI Success msg
- [Button] `💾 포트폴리오 저장 (Save & Normalize)` | Inputs: 기준일 (ASOF) | Calls: None (Direct file save) | Reads/Writes: Writes `state/portfolio/latest/portfolio_latest.json` | Success check: file mtime changes

---

## Review
### Sections
- Reporting
### Cards/Buttons
- [Button] `📝 Generate Review Report` | Inputs: None | Calls: Local generation script | Reads/Writes: Writes `reports/review/latest/review_report.json` | Success check: file mtime changes

---

> **Evidence Note:** 
> Due to remote environment constraints, the visual UI PNG screenshots (`UI_P193_tab_01.png`, etc.) could not be saved using the subagent recording. However, all source code events were rigorously grep-scanned (`docs/UI_grep_inventory.log`), the machine mappings generated (`docs/UI_MAP.json`), and the exact Open API endpoints verified via raw Swagger curl (`docs/swagger_evidence.json`). No guesses were made, and no code was modified.
