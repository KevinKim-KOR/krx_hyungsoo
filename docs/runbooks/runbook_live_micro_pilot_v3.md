# Runbook: Live Micro-Pilot V3 (Post-Hotfix Re-entry)

## Goal
**5-Day Live Execution** (Next 5 Trading Days) ensuring P140/P141 Hotfixes are stable.
- **Rule 1**: Max **1 Trade** (or 1 Set) per day.
- **Rule 2**: Token input ONLY on OCI.
- **Rule 3**: Fail-Closed on any violation.
- **Rule 4**: **EMPTY Day = NO ACTION**. Do not enter token.

## Daily Routine (Mon-Fri)

### 1. Check Status (PC)
#### 1-A. System Health (Cockpit)
- Open Cockpit (`http://localhost:8501`).
- Check Sidebar **"System Health"**:
  - Latency: Green (<100ms).
  - Sync Timeout: Check constraint (default 120s).

#### 1-B. Flight Status (CLI)
```powershell
.\deploy\pc\flight_status.ps1
```
- **Check**: Stage / Next Action.
- **Fail-Closed**: If timeout/error, STOP.

### 2. Auto Ops (OCI)
```bash
bash deploy/oci/daily_ops.sh >> logs/daily_ops.log 2>&1
```

### 3. Check Stage (Critical Decision)
Check `ops_summary.manual_loop.stage`:

#### Case A: `NO_ACTION_TODAY` (or `BLOCKED` with Empty info)
- **Condition**: Market Holiday, No Orders, or Empty Plan.
- **Action**: **STOP**. Do NOT proceed to Prep. Do NOT enter token.
- **Log**: Mark as "EMPTY / No Action" in Daily Log.

#### Case B: `NEED_HUMAN_CONFIRM` (Trade Day)
- **Condition**: Valid Order Plan exists.
- **Action**: Proceed to Prep.

### 4. Prep & Ticket (OCI) - *Only if Trade Day*
```bash
bash deploy/oci/manual_loop_prepare.sh
# Enter Token
```
- **Expect**: `AWAITING_HUMAN_EXECUTION`.

### 5. Human Execution (HTS/MTS) - *Only if Trade Day*
- **Action**: Ticket에 있는 주문 중 **1개 주문만** 실행(체결).
- **Constraint**: Do not touch other items.

### 6. Draft Record (PC) - *Only if Trade Day*

**Option A: Dashboard (Recommended)**
1. Open `http://localhost:8000/dashboard`.
2. Click **"Generate Draft (Server)"**.
3. Review Preview.
4. **Submit via Dashboard**:
   - Enter `Token`.
   - Click "Submit Draft".

**Option B: CLI (Legacy)**
```powershell
.\deploy\pc\generate_record_template.ps1
# Edit draft: Ticket/Export의 주문 목록/plan_id/linkage는 절대 수정하지 말 것.
# 실행한 1개 주문만 EXECUTED로 표기.
```

### 7. Push Draft (PC -> OCI) - *Only if Option B used*
```powershell
.\deploy\pc\push_record_draft.ps1
```

### 8. Submit Record (OCI) - *Only if Option B used*
```bash
bash deploy/oci/submit_record_from_incoming.sh
# Enter Token
```
- **Expect**: `PARTIAL` (or `DONE_TODAY`).

### 9. Final Gate Check (OCI)
```bash
bash deploy/oci/steady_gate_check.sh
```
- **Pass Condition**: `PASS` (or `WARN` if meant to be).

---

## Daily Evidence Log (Copy & Paste)

### Day 1
- [ ] `flight_status`: ________________ (Time: ________)
- [ ] `stage`: ________________ (EMPTY / TRADE)
- [ ] `steady_gate`:   ________________

### Day 2
- [ ] `flight_status`: ________________
- [ ] `stage`: ________________
- [ ] `steady_gate`:   ________________

### Day 3
- [ ] `flight_status`: ________________
- [ ] `stage`: ________________
- [ ] `steady_gate`:   ________________

### Day 4
- [ ] `flight_status`: ________________
- [ ] `stage`: ________________
- [ ] `steady_gate`:   ________________

### Day 5
- [ ] `flight_status`: ________________
- [ ] `stage`: ________________
- [ ] `steady_gate`:   ________________

---

## Final Report Template (JSON)
Fill this out after Day 5 and submit.
```json
{
  "phase": "P142",
  "result": "OK",
  "window": {
    "rule": "NEXT_5_TRADING_DAYS",
    "note": "Post-Hotfix Re-entry"
  },
  "verification": {
    "token_not_logged": true,
    "guardrails_enforced": true,
    "linkage_dedupe_enforced": true,
    "steady_gate_check_all_days": "PASS",
    "empty_days_handled_correctly": "PASS"
  },
  "constraints": {
    "no_broker_call": true,
    "token_lock_not_bypassed": true,
    "no_external_send": true,
    "no_outbox_mutation": true
  }
}
```
