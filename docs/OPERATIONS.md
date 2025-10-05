# OPERATIONS (Consolidated)

> **Version:** 2025-10-05 (Asia/Seoul)  
> This document consolidates and replaces both **OPERATIONS.md** and **OPERATIONS_updated.md**.  
> Scope: Day-to-day ops for the **krx_alertor_modular** project (PC→NAS flow, batch framework, data policy, and runbooks).

---

## 1) Purpose & Principles

- **Single source of truth**: Develop on **PC**, deploy/run on **NAS**. NAS code is pull-only; never edit live on NAS.
- **Resilience first**: During market hours, try online; on **external errors** (rate-limit, transient HTTP, schema drift) **skip gracefully** and exit **RC=0**.
- **Hard‑coding minimized**: Paths are repo-relative; behavior via env/config (e.g., `config/env.nas.sh`, `config/data_sources.yaml`).

---

## 2) Architecture Overview

**PC (dev) → Git → NAS (ops)**

1. Develop & commit on **PC**.
2. NAS pulls via `scripts/linux/batch/update_from_git.sh` (installs deps if needed).
3. Batch entrypoints in `scripts/linux/batch/*` call **jobs** through a **generic runner** with lock/guards/retry.
4. Jobs call Python entrypoints (`app.py`, `report_*_cli.py`, `scripts/bt/run_bt.py`, …).  
5. Outputs: `backtests/`, `logs/`, `reports/` (web can read).

---

## 3) Environments

### 3.1 NAS
`config/env.nas.sh` (example):
```bash
export ENV=nas
export PYTHONBIN="/volume2/homes/Hyungsoo/krx/krx_alertor_modular/venv/bin/python"
export ALLOW_NET_FETCH=1   # online by default; batch can override per job if needed
```

> If `PYTHONBIN` is unset, runners default to `python3`.

### 3.2 PC (Windows)
- Use Conda env (e.g., `ai-study`).  
- When running commands that include `&` in arguments (benchmarks), **quote** the string (PowerShell parses `&`).  
  Example: `--benchmarks "KOSPI,S&P500"`.

---

## 4) Batch Framework (standardized)

All scheduled tasks follow this chain:

```
batch entry  →  run_with_lock.sh  →  jobs/_run_generic.sh  →  jobs/run_py_guarded.sh  →  python script
           (exclusive lock)         (guard/retry/log)         (map external errors to skip/RC=0)
```

### 4.1 Lock
`scripts/linux/jobs/run_with_lock.sh`
- Takes `<script_to_run> [args…]` and passes through arguments.
- Creates `.locks/<script>.lock` and uses `flock -n`.

### 4.2 Generic Runner
`scripts/linux/jobs/_run_generic.sh`
- Options:
  - `--log <name>`: log file at `logs/<name>_YYYY-MM-DD.log`
  - `--guard <mode>`: `none | td | th`  
    - `td` = trading day guard only  
    - `th` = trading day **and** trading-hours guard
  - `--retry-rc <N> --retry-max <K> --retry-sleep <S>`: retry when child returns RC `N`.
- Remaining args after `--` are the exact command to run (e.g., `"$PYTHONBIN" app.py scanner`).

### 4.3 External-Error Guard
`scripts/linux/jobs/run_py_guarded.sh`
- Runs the python command, captures stderr/stdout.
- If it matches external-error patterns (rate-limit, timeouts, 5xx, etc.), **prints** `[SKIP] external-data-unavailable (guarded)` and **exits 0**.

### 4.4 Guards (Python-side)
- Guard logic imports from `utils/trading_day.py`:
  - `is_trading_day()`
  - `in_trading_hours()`
- `_run_generic.sh --guard td | th` triggers a small Python pre-check; skip with RC `200/201` (which the runner converts to normal skip).

---

## 5) Deployed Jobs & Entry Points

### 5.1 Scanner (intraday)
- **Batch**: `scripts/linux/batch/run_scanner.sh`
- **Generic config**: `--guard th` (trading day + trading hours)  
- **Command**: `"$PYTHONBIN" app.py scanner`  
  > If scanner is a separate module, replace with `"$PYTHONBIN" scripts/scanner.py ..."`.

### 5.2 End-of-Day Report
- **Batch**: `scripts/linux/batch/run_report_eod.sh`
- **Generic config**: `--guard td --retry-rc 2 --retry-max 2 --retry-sleep 300`
- **Command**: `"$PYTHONBIN" report_eod_cli.py --date auto`  
  - RC=2 is reserved for “temporary data staleness” and will be retried.

### 5.3 Watchlist Report
- **Batch**: `scripts/linux/batch/run_report_watchlist.sh`
- **Generic config**: default (no guard).  
  - Optionally `--guard td` to skip on non-trading days.
- **Command**: `"$PYTHONBIN" report_watchlist_cli.py --date auto`.

### 5.4 Backtest & Regression
- **Job**: `scripts/linux/jobs/run_bt.sh` → `python -m scripts.bt.run_bt ...`
- **Postprocess**: `scripts/linux/jobs/bt_postprocess.sh`  
  - Snapshot list of `backtests/*_<strategy>` (mtime order)  
  - Generate `manifest.json` if missing  
  - Compare **A=prev** (baseline) vs **B=latest** (candidate) with `scripts/bt/compare_runs.py`  
  - Report: `logs/compare_<strategy>_YYYY-MM-DD.log`

Outputs in `backtests/<timestamp>_<strategy>/`:
- `daily_returns.csv`, `equity_curve.csv`, `equity_curve.png`, `metrics.json`, `report.txt`, `manifest.json`

> **Note:** DRIFT can be expected when environment/inputs change. After stabilization, consecutive runs in the same day should be comparable.

---

## 6) Data Loading & External Source Policy

### 6.1 Provider Policy
- Implemented in `scripts/bt/data_loader.py` with `ExternalDataUnavailable` exception.  
- **Order of providers** (per benchmark):  
  `local_cache` → `parquet` → `pykrx_index` → `yf_index` → `yf_etf`  
- Policy can be overridden via `config/data_sources.yaml`:
```yaml
benchmarks:
  KOSPI:
    providers: [local_cache, parquet, pykrx_index, yf_index, yf_etf]
    symbols:
      pykrx_index: "1001"
      yf_index: "^KS11"
      yf_etf: "069500.KS"
      local_keys: ["069500.KS", "069500", "KOSPI", "KOSPI_ETF"]
  S&P500:
    providers: [local_cache, parquet, yf_index, yf_etf]
    symbols:
      yf_index: "^GSPC"
      yf_etf: "SPY"
      local_keys: ["SPY", "^GSPC"]
```

### 6.2 yfinance Caching & Retry
- `data/webcache/yf/` caches downloads by ticker/date.
- Exponential backoff retries inside loader; still failing → raise `ExternalDataUnavailable` (caller skips).

### 6.3 Skip-on-External-Errors
- Backtest runner: if **KOSPI** (required) unavailable → overall skip (RC=0).  
- Other benchmarks fail independently and are logged as `[WARN] benchmark unavailable: … (skipped)`.

---

## 7) Updates & Health

### 7.1 Update from Git (NAS)
```
bash scripts/linux/batch/update_from_git.sh
```
- Fetch/FF-only pull, venv activation if present, install `requirements-nas.txt` when available.  
- Appends to `logs/update_YYYY-MM-DD.log`.

### 7.2 Healthcheck (optional)
```
bash scripts/linux/batch/run_healthcheck.sh
```
- Git branch/head, free disk, today logs existence, recent errors, active locks.

---

## 8) Scheduler (Cron) – Guidance

> Already registered by ops; below is a **reference** pattern.

```
# Example (Asia/Seoul timezone on NAS)
# Intraday scanner every 5 minutes during trading hours:
*/5  * * * 1-5  /path/to/repo/scripts/linux/batch/run_scanner.sh

# EOD report at 18:10 on trading days:
10 18 * * 1-5  /path/to/repo/scripts/linux/batch/run_report_eod.sh

# Watchlist at 09:00 every day:
0 9  * * *     /path/to/repo/scripts/linux/batch/run_report_watchlist.sh
```

> Guards will skip safely on non-trading days/hours (RC=0).

---

## 9) Folder Roles (Project Layout)

| Folder | Role | Ops Use |
|---|---|---|
| `scripts/linux/batch/` | **Scheduler entrypoints** (locked, generic runner invocation). | **Required** |
| `scripts/linux/jobs/`  | **Generic runner**, guarded Python wrapper, BT jobs, postprocess. | **Required** |
| `scripts/linux/utils/` | Utility scripts (e.g., update from git). | Recommended |
| `scripts/bt/`          | Backtest runner + manifest + compare (regression). | Required for BT |
| `utils/`               | Common helpers (trading day/hour, config loader). | Required |
| `signals/`             | Alert/notification service code. | As used |
| `web/`                 | API/UI to expose reports/backtests. | Optional |
| `data/`                | Caches and webcache (`data/webcache/yf`). | **Required** |
| `backtests/`           | Backtest outputs per run. | **Required** |
| `reports/`             | Aggregated artifacts (consumed by web). | Recommended |
| `config/`              | Env and data source policy (`env.nas.sh`, `data_sources.yaml`). | **Required** |
| `secret/`              | Sensitive configs (e.g., `secret/watchlist.yaml`). | Recommended |
| `docs/`                | Operational docs (this file). | Recommended |
| `tests/`               | Developer tests; not called by scheduler. | Optional |
| `scripts/legacy/…`     | Archived legacy shell scripts for audit. | Optional |

> Exclude from repo: `venv/`, `.venv/`, `__pycache__/` (env- or interpreter‑generated).

---

## 10) Runbooks

### 10.1 Manual Checks
```bash
# Scanner (guarded)
bash scripts/linux/batch/run_scanner.sh ; echo $?

# EOD report (guarded + retry on rc=2)
bash scripts/linux/batch/run_report_eod.sh ; echo $?

# Watchlist (simple)
bash scripts/linux/batch/run_report_watchlist.sh ; echo $?

# Logs
tail -n 80 logs/scanner_$(date +%F).log
tail -n 80 logs/report_$(date +%F).log
tail -n 80 logs/watchlist_$(date +%F).log
```

### 10.2 Backtest (manual)
```bash
# NAS: local output to backtests/
bash scripts/linux/jobs/run_bt.sh

# Compare previous vs latest:
bash scripts/linux/jobs/bt_postprocess.sh
tail -n 80 logs/compare_krx_ma200_$(date +%F).log
```

### 10.3 Troubleshooting Quick Hints
- **Usage shown by _run_generic.sh** → usually means `run_with_lock.sh` didn’t pass arguments. Ensure pass-through in `run_with_lock.sh` and batch scripts.  
- **PowerShell ampersand error** → quote benchmark list (`"KOSPI,S&P500"`).  
- **External data failing** → should print `[SKIP] external-data-unavailable (guarded)` and exit 0 (no alerts).  
- **Unexpected DRIFT** → stabilize inputs (same day rerun), ensure same `out_root`, then treat the newest run as candidate against the immediate previous run.

---

## 11) Security & Secrets

- Keep tokens/keys and private configs under `secret/` (not committed).  
- `utils/config.py` loads from `secret/watchlist.yaml` first, then falls back to repo default if missing.  
- Do not commit `venv/`, `.venv/`, `__pycache__/`.  
- NAS git working copy is necessary for `update_from_git.sh` (keep `.git/` on NAS clone).

---

## 12) Housekeeping & Legacy

- Historical root-level shell scripts are archived under `scripts/legacy/<YYYY-MM-DD>/`.  
- Prefer **generic runner path** over bespoke shell wrappers. Migrate legacy scripts when used again.

---

## 13) Roadmap / Improvements

- **Data source policy** (`config/data_sources.yaml`) as the single place to switch provider priority/order per benchmark.  
- **Pre-cache job** (optional): `scripts/linux/batch/precache_benchmarks.sh` to warm yfinance/pykrx data before market open.  
- **Optional offline mode** for critical intraday paths (PC can pre‑ingest and sync), but current strategy is **online with graceful skip**.

---

_End of document._
