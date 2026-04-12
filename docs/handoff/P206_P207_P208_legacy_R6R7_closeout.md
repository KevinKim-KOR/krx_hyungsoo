# P206/P207/P208 Legacy R6/R7 Closeout
> asof: 2026-04-12
> 상태: **완료** — 대상 8건 정리, 기능 변경 없음
> 직전 문서: [P209_STEP9C_close_and_TrackB_handoff.md](P209_STEP9C_close_and_TrackB_handoff.md)

---

## 0. 이 문서의 목적

P209 는 이미 별도 평가를 마쳤다. 이 문서는 P206~P208 에서 carry 된
legacy fallback/default 잔존 8건을 Rule 6/7 관점에서 정리한 closeout 기록이다.

기능/정책/실험 결과는 변경하지 않았고, 대표 성능(`CAGR 12.387 / MDD 12.7446 /
Sharpe 1.1019 / Verdict REJECT`)에 영향 없음.

---

## 1. 대상 8건 정리 내역

### P208 계열 (1건)

| # | 파일 | 이전 패턴 | 분류 | 수정 |
|---|---|---|---|---|
| 1 | `run_backtest.py` L760 | `params.get(k) or _resolve(...)` | OPTIONAL | `if is not None else _resolve(...)` 명시 분기 |

### P207 계열 (1건)

| # | 파일 | 이전 패턴 | 분류 | 수정 |
|---|---|---|---|---|
| 2 | `backtest_runner.py` L943 | `_alloc_params.get("volatility_lookback", 20)` | REQUIRED | `if key not in: raise KeyError` + 직접 subscript |

### P206 계열 (6건)

| # | 파일 | 이전 패턴 | 분류 | 수정 |
|---|---|---|---|---|
| 3 | `backtest_runner.py` L532 | `exo_regime_schedule.get("schedule", {})` | REQUIRED (exo 존재 시) | `if key not in: raise KeyError` + subscript |
| 4 | `backtest_runner.py` L1025 | `_exo_sched.get(str(d), "risk_on")` | OPTIONAL | `if _d_str in _exo_sched else "risk_on"` + 주석 |
| 5 | `backtest_runner.py` L1030 | `_esc.get("safe_asset_ticker", "")` | OPTIONAL→REQUIRED 분기 | exo 존재 시 subscript, 미존재 시 sentinel `""` |
| 6 | `backtest_runner.py` L1031 | `_esc.get("neutral_risky_pct", 0.50)` | 동일 | exo 존재 시 subscript, 미존재 시 WHITELIST(math) `1.0` |
| 7 | `backtest_runner.py` L1032 | `_esc.get("neutral_dollar_pct", 0.20)` | 동일 | sentinel `0.0` |
| 8 | `backtest_runner.py` L1033 | `_esc.get("riskoff_dollar_pct", 0.50)` | 동일 | sentinel `0.0` |

---

## 2. grep 검증 증거

대상 패턴 잔존 검색 결과 (수정 후):

```
=== or {} / or [] ===
(없음)
=== volatility_lookback default ===
(없음)
=== exo .get("schedule" ===
(없음)
=== .get(str(d), "risk_on") ===
(없음)
=== safe_asset_ticker / neutral_risky_pct / neutral_dollar_pct / riskoff_dollar_pct ===
(없음)
```

대상 8건 기준 잔존 0건.

---

## 3. 범위 밖 잔존 (미접촉, 보고만)

- `backtest_runner.py:1469`: `_exo_sched.get(str(d), "N/A") if _exo_sched else "N/A"`
  — rebalance trace 의 WHITELIST(display) 표시용. 지시문 고정 8건 범위 밖.
- `evidence_writer.py` / `contextual_guard_panel.py` / `contextual_guard_compare.py`
  내 display `.get()` — 이미 WHITELIST 분류 주석 기재. 지시문 수정 금지 파일.

---

## 4. 정적 게이트

| 검사 | 결과 |
|---|---|
| `black --check` | 2 files unchanged |
| `flake8` | clean |
| `py_compile` | OK |

---

## 5. 수정 파일 범위

- `app/backtest/runners/backtest_runner.py` (P206 6건 + P207 1건)
- `app/run_backtest.py` (P208 1건)
- 범위 외 파일 오염: 없음
