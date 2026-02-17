# Collaboration Protocol (User-Agent)
> **Objective**: Streamline collaboration between Human Operator and AI Agent for KRX Alertor Modular.

## 1. Response Modes
### (Mode 1) Verification / Diagnosis (Source Unchanged)
**Trigger**: "Check status", "Investigate logs", "Why X failed?"
**Format**:
1. **Diagnosis**: Root cause analysis based on logs/evidence.
2. **Checklist**: Step-by-step verification points.
3. **Expected Result**: What "Normal" looks like.

### (Mode 2) Action / Implementation (Source Changed)
**Trigger**: "Fix bug", "Implement feature", "Update config"
**Format**:
1. **Plan**: Concise list of changes.
2. **Execution**: `replace_file_content` / `write_to_file`.
3. **Verification Command**: CLI command to verify the fix immediately.
4. **Final Report (JSON)**:
   ```json
   {
       "status": "FIXED",
       "affected_files": ["..."],
       "verification_cmd": "curl ...",
       "rollback_cmd": "git checkout ..."
   }
   ```

## 2. Change Management Rules
1.  **Deployment Impact**: If code changes affect OCI behavior:
    - Provide: `git add . && git commit -m "..." && git push`
    - Provide: `ssh ... "cd ... && git pull && systemctl restart krx-backend"`
2.  **Safety First**:
    - **Fail-Closed**: If unsure, block execution.
    - **Token Security**: Never log tokens. Use env vars or secret files.
    - **No External Send**: Unless explicitly requested, do NOT trigger external APIs (Telegram/Broker) during dev.

## 3. Verification Rules
- **Beyond PASS/FAIL**:
    - Do NOT just say "It works".
    - SHOW the evidence.
    - Example: `curl ... | grep "status": "OK"` output.
- **UI Observation Points**:
    - "Check Cockpit Sidebar -> PULL Button -> Green Toast".
    - "Check Backend Console -> [DEBUG] ...".

## 4. Session Handoff Template
At the end of a session, append this block to `docs/handoff/STATE_LATEST.md` or provide it in chat:

```markdown
## Session Summary (YYYY-MM-DD)
- **Status**: [STABLE / UNSTABLE / WIP]
- **Main Change**: (e.g., Refactored sync.py deadlock)
- **Root Cause**: (e.g., synchronous requests call to self)
- **Decision**: (e.g., Switch to direct file IO)
- **Next Action**: (e.g., Verify PULL in Cockpit)
- **Caution**: (e.g., Ensure Backend is restarted)
```
