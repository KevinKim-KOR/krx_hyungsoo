# Tuning Engine Phase 1 Verification Report

## Verdict: ❌ FAIL (Grade: PASS)
### Top Failure Reasons
- Global Outsample Trades = 0

## Run Context
- **Run ID**: `gate2_20251225_104938_0e5a74`
- **Mode**: `None`
- **Git**: `None`

## Evidence Checklist
| Check | Status | Evidence/Reason |
| :--- | :--- | :--- |
| real_data | ✅ PASS | Source: parquet |
| universe | ✅ PASS | Count: 14 |
| multi_lookback | ✅ PASS | Dates: 12M(2022-12-26 00:00:00) <= 6M(2022-12-26 00:00:00) <= 3M(2023-03-23 00:00:00) |
| walkforward_presence | ✅ PASS | Results Found |
| walkforward_validity | ❌ FAIL | Global Outsample Trades = 0 |

---
## Zero Trade Autopsy (Funnel)
| Metric | Count | Interpretation |
| :--- | :--- | :--- |
| 1. Raw Signals | 0 | MA/RSI 조건 만족 횟수 |
| 2. Filtered Signals | 0 | Liquidity/TopN 필터 통과 |
| 3. Executed Trades | 0 | 실제 체결 횟수 |
