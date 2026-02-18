# Runbook: Live Micro Pilot V2 (DEPRECATED)

> ⚠️ **DEPRECATED**: superseded by [runbook_ui_daily_ops_v1.md](runbook_ui_daily_ops_v1.md) (2026-02-09 ~ 02-13)

## Goal
**5-Day Live Execution** with strict constraints.
- **Rule 1**: Max **1 Trade** (or 1 Set) per day.
- **Rule 2**: Token input ONLY on OCI.
- **Rule 3**: Fail-Closed on any violation.

## Daily Routine (Mon-Fri)

### 1. Check Status (PC)
```powershell
.\deploy\pc\flight_status.ps1
```
- **Check**: Stage / Next Action.
- **Fail-Closed**: If timeout/error, STOP.

### 2. Auto Ops (OCI)
```bash
bash deploy/oci/daily_ops.sh >> logs/daily_ops.log 2>&1
```
- **Expect**: `NEED_HUMAN_CONFIRM`.

### 3. Prep & Ticket (OCI)
```bash
bash deploy/oci/manual_loop_prepare.sh
# Enter Token
```
- **Expect**: `AWAITING_HUMAN_EXECUTION`.

### 4. Human Execution (HTS/MTS)
- **Action**: Ticket에 있는 주문 중 **1개 주문만** 실행(체결).
- **Constraint**: Do not touch other items.

### 5. Draft Record (PC)
```powershell
.\deploy\pc\generate_record_template.ps1
# Edit draft: Ticket/Export의 주문 목록/plan_id/linkage는 절대 수정하지 말 것.
# 실행한 1개 주문만 EXECUTED로 표기(스키마가 요구하는 최소 필드만 수정).
# 나머지 주문은 드래프트 기본값(또는 스키마 enum 허용값) 그대로 유지.
```

### 6. Push Draft (PC -> OCI)
```powershell
.\deploy\pc\push_record_draft.ps1
```

### 7. Submit Record (OCI)
```bash
bash deploy/oci/submit_record_from_incoming.sh
# Enter Token
```
- **Expect**: `PARTIAL` (or `DONE_TODAY`).

### 8. Final Gate Check (OCI)
```bash
bash deploy/oci/steady_gate_check.sh
```
- **Pass Condition**: `PASS` (or `WARN` if meant to be).

---

## Daily Evidence Log (Copy & Paste)

### Day 1 (2026-02-09)
- [ ] `flight_status`: ________________
- [ ] `prepare` Stage: ________________
- [ ] `submit` Stage:  ________________
- [ ] `steady_gate`:   ________________

### Day 2 (2026-02-10)
- [ ] `flight_status`: ________________
- [ ] `prepare` Stage: ________________
- [ ] `submit` Stage:  ________________
- [ ] `steady_gate`:   ________________

### Day 3 (2026-02-11)
- [ ] `flight_status`: ________________
- [ ] `prepare` Stage: ________________
- [ ] `submit` Stage:  ________________
- [ ] `steady_gate`:   ________________

### Day 4 (2026-02-12)
- [ ] `flight_status`: ________________
- [ ] `prepare` Stage: ________________
- [ ] `submit` Stage:  ________________
- [ ] `steady_gate`:   ________________

### Day 5 (2026-02-13)
- [ ] `flight_status`: ________________
- [ ] `prepare` Stage: ________________
- [ ] `submit` Stage:  ________________
- [ ] `steady_gate`:   ________________

---

## Final Report Template (JSON)
Fill this out after Day 5 and submit.
```json
{
  "phase": "P133",
  "result": "OK",
  "window": {
    "start_kst": "2026-02-09",
    "end_kst": "2026-02-13",
    "live_days": 5
  },
  "stats": {
    "executed_orders_total": 5,
    "days_done_today": 0,
    "days_partial": 5,
    "blocked_days": 0
  },
  "verification": {
    "token_not_logged": true,
    "guardrails_enforced": true,
    "linkage_dedupe_enforced": true,
    "steady_gate_check_all_days": "PASS"
  },
  "constraints": {
    "no_broker_call": true,
    "token_lock_not_bypassed": true,
    "no_external_send": true,
    "no_outbox_mutation": true
  }
}
```
