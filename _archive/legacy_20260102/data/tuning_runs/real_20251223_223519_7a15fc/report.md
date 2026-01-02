# Tuning Engine Phase 1 Verification Report

## Verdict: ❌ FAIL (Grade: PASS)
### Top Failure Reasons
- Missing lookbacks: [3, 6, 12]

## Run Context
- **Run ID**: `gate2_20251223_223549_18a8f1`
- **Mode**: `None`
- **Git**: `None`

## Evidence Checklist
| Check | Status | Evidence/Reason |
| :--- | :--- | :--- |
| real_data | ✅ PASS | Source: parquet |
| universe | ✅ PASS | Count: 14 |
| multi_lookback | ❌ FAIL | Missing lookbacks: [3, 6, 12] |
| walkforward | ❌ FAIL | Skipped due to earlier failure |
