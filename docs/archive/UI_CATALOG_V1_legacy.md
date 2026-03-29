> **DEPRECATED** (2026-03-28): 이 문서는 S2(cockpit.py 분해) 이전 기준입니다.
> 기능 매핑은 대체로 유효하나, cockpit.py 라인 참조가 현재 views/ 구조와 일치하지 않습니다.

# P194 UI Catalog V1

This catalog strictly maps all discovered Cockpit UI footprints into 3 operational surfaces (데일리운영 (P144), 워크플로우 (P170), 정비창 (Advanced)) without modifying any application code.

## 데일리운영 (P144) Daily Ops
Daily execution and lifecycle operations strictly related to LIVE cycle driving.

| 기능ID (TAB::SECTION::LABEL) | Surface | Label(화면 표시명) | Inputs | Call | Read files | Write files | Success signal | Risk |
|---|---|---|---|---|---|---|---|---|
| LiveOps::Operations::Pull | 데일리운영 (P144) | 📥 PULL (OCI) | Confirm Token (Password) | POST `/api/sync/pull` | - | `state/strategy_bundle/latest/strategy_bundle_latest.json` | file mtime changes | LOW (Read OCI, but Token unnecessarily asked) |
| LiveOps::Operations::Push | 데일리운영 (P144) | 📤 PUSH (OCI) | Confirm Token (Password) | POST `/api/sync/push` | `state/strategy_bundle/etc` | - | Backend sync logs | HIGH (OCI write + token) |
| LiveOps::Operations::AutoOps | 데일리운영 (P144) | ▶️ Run Auto Ops Cycle | Force Recompute (Checkbox) | POST `/api/live/cycle/run?confirm=true&force={bool}` | - | `reco_latest.json`, `order_plan_latest.json` | reports asof increases | MID (Generates Live Plans locally) |

---

## 워크플로우 (P170) Workflow Hub
Orchestration, Configuration, Portfolio state management, and Workflow syncs.

| 기능ID (TAB::SECTION::LABEL) | Surface | Label(화면 표시명) | Inputs | Call | Read files | Write files | Success signal | Risk |
|---|---|---|---|---|---|---|---|---|
| Workflow::Sync::PushBundle | 워크플로우 (P170) | 📤 OCI 반영 (1-Click Sync) | OCI Access Token (Password) | POST `/api/sync/push_bundle` | - | - | UI success msg | HIGH (OCI write + token) |
| Config::Connectivity::Check | 워크플로우 (P170) | Check Connectivity 💓 | None | Local Ping | - | - | UI success toast | LOW (Stateless ping) |
| Portfolio::Mgmt::InitEmpty | 워크플로우 (P170) | Initialize Empty Portfolio | None | Direct State | - | `state/portfolio/latest/portfolio_latest.json` | empty struct created | MID (Overwrites local state) |
| Portfolio::Mgmt::PushOCI | 워크플로우 (P170) | 📤 Push to OCI | None | POST `/api/sync/push` | `portfolio_latest.json` | - | UI success msg | HIGH (OCI write, missing token input!) |
| Portfolio::Mgmt::SavePort | 워크플로우 (P170) | 💾 포트폴리오 저장 (Save & Normalize) | 기준일 (ASOF) | Direct State | - | `portfolio_latest.json` | file mtime changes | MID (Local state mutating) |
| Review::Reporting::GenReport | 워크플로우 (P170) | 📝 Generate Review Report | None | Local Script | - | `reports/review/latest/review_report.json` | file mtime changes | LOW (Local read/write only) |

---

## 정비창 (Advanced) Advanced Lab
Research, timing analysis, parameter tuning, and backtesting (Heavy computation).

| 기능ID (TAB::SECTION::LABEL) | Surface | Label(화면 표시명) | Inputs | Call | Read files | Write files | Success signal | Risk |
|---|---|---|---|---|---|---|---|---|
| Params::Analysis::ParamSearch | 정비창 (Advanced) | 🔄 Run Analysis (Param Search) | None | Local Logic | - | - | UI renders table | LOW (Read-only simulation) |
| Params::Analysis::ApplyRank | 정비창 (Advanced) | Apply Rank N | None | Direct State | - | `state/params/latest/strategy_params_latest.json` | file mtime changes | MID (Mutates parameter state) |
| Timing::Analysis::TimingRun | 정비창 (Advanced) | 🔄 Run Analysis (Timing) | None | Local Logic | - | - | Plot rendering | LOW (Read-only visual) |
| Backtest::Run::RunBacktest | 정비창 (Advanced) | ▶️ Run Backtest | Mode (Radio) | SUBPROCESS `run_backtest.py` | `strategy_bundle...` | `reports/backtest/latest/backtest_result.json` | mtime changes | LOW (Local intense compute) |
| Tuning::Run::RunTune | 정비창 (Advanced) | ▶️ Run Tune | Mode (Radio) | SUBPROCESS `run_tune.py` | - | `reports/tuning/tuning_results.json` | file mtime changes | LOW (Local intense compute) |
