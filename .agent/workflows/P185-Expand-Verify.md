---
description: P185-Expand-Verify - Validating Bucket Expansion
---

# P185-Expand-Verify Verification Workflow Constraint

**Purpose**: This workflow forces any agent analyzing bucket expansions to mathematically verify SSOT adherence and check the engine's real operation bounds against meta evidence.

## Verification Steps
When verifying bucket expansions, the agent MUST explicitly extract and validate the following metrics from `backtest_result.json`:

1. **SSOT Adherence**: Provide evidence that `meta.param_source.sha256` exactly matches the local SHA256 output of `strategy_params_latest.json`.
2. **Rebalance Trigger Bounding**: Verify `meta.rebalance_trigger_source` strictly reads as `"params.rebalance"` (Ensures legacy `rebalance_rule` is dead/overridden).
3. **Month-Start Clustering**: Verify `meta.rebalance_cluster_check.cluster_ok` is `true`, asserting trades cluster overwhelmingly on days 1~3 in `rebalance_only` mode.
4. **Fallback Constraint**: Assure `fallback_count = 0` ensuring strict data determinism.

## Required Outputs
Generate a structured JSON response (e.g. `docs/P185-Expand-Verify_report.json`) explicitly addressing:
- `param_source_sha_matches_ssot: bool`
- `rebalance_trigger_source_is_params_rebalance: bool`
- `cluster_ok_true: bool`

*Do NOT attempt to alter Python backtest decision structures to spoof these assertions.*
