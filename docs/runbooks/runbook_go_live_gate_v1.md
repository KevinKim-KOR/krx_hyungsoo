# Runbook: Go-Live Readiness Gate V1
**Version**: 1.0
**Last Updated**: 2026-02-08

## Overview
Checks if the OCI environment is healthy and ready for the daily manual execution loop.

## Usage
**Run ON PC** (PowerShell):
```powershell
.\deploy\pc\go_live_gate.ps1
```

## Outputs

### 1. `GO_LIVE=READY`
- **Meaning**: No blocking risks found. Stage is valid.
- **Action**: Proceed to Operator Orchestrator.
  ```powershell
  .\deploy\pc\daily_operator.ps1
  ```

### 2. `GO_LIVE=BLOCKED`
- **Meaning**: Critical risks detected (e.g., Stale Bundle, Missing Portfolio, Blocked Input).
- **Action**: **DO NOT PROCEED**. Resolve the specific RISK listed in the output.
    - `BUNDLE_STALE_WARN` -> Publish new bundle (`daily_operator.ps1 -PublishBundle`).
    - `NO_PORTFOLIO` -> Run Portfolio Bootstrap.
    - `CHECK_BACKEND` -> Restart OCI Backend.

### 3. `GO_LIVE=HELD`
- **Meaning**: System is running but in an unusual stage (e.g., Initialization not complete).
- **Action**: Check `.\deploy\pc\daily_operator.ps1` or OCI logs manually.

## Constraints
- **Token Lock**: This gate never requires a token. If asked, something is wrong.
- **Fail-Closed**: Network timeouts defaults to blocked.
