# Contract: Ops Cycle V2

**Version**: 2.0
**Date**: 2026-01-04
**Status**: LOCKED

---

## 1. 개요

Ops Cycle 1회에 운영 리포트 생성 + 티켓 0~1건 처리를 묶어 실행합니다.

> 🔒 **Bounded Processing**: Cycle 1회당 티켓 처리 최대 1건

---

## 2. 스키마 정의

### OPS_CYCLE_RUN_V2

```json
{
  "schema": "OPS_CYCLE_RUN_V2",
  "run_id": "uuid",
  "asof": "2026-01-04T12:00:00",
  "overall_status": "DONE",
  "ops_report_ref": "reports/ops/daily/ops_report_latest.json",
  "ticket_step": {
    "attempted": true,
    "selected_request_id": "uuid or null",
    "selected_request_type": "REQUEST_REPORTS or null",
    "decision": "PROCESSED",
    "reason": "TICKET_PROCESSED_OK",
    "receipt_ref": "state/tickets/ticket_receipts.jsonl:line20"
  },
  "safety_snapshot": {
    "emergency_stop_enabled": false,
    "execution_gate_mode": "DRY_RUN",
    "window_active": false,
    "allowlist_version": "v1"
  },
  "counters": {
    "tickets_open": 2,
    "tickets_in_progress": 0,
    "tickets_done": 5,
    "tickets_failed": 1,
    "tickets_blocked": 2,
    "skips_this_run": 0
  }
}
```

---

## 3. Enum 정의

### overall_status

| 값 | 설명 |
|----|------|
| `DONE` | 정상 완료 |
| `DONE_WITH_SKIPS` | 완료 (일부 스킵) |
| `FAILED` | 실패 |
| `STOPPED` | Emergency Stop으로 중단 |

### ticket_step.decision

| 값 | 설명 |
|----|------|
| `PROCESSED` | 티켓 처리 성공 |
| `SKIPPED` | 안전장치로 스킵 |
| `NONE` | 처리할 티켓 없음 |

### ticket_step.reason

| 값 | 설명 |
|----|------|
| `NO_OPEN_TICKETS` | OPEN 티켓 없음 |
| `EMERGENCY_STOP_ACTIVE` | 비상 정지 상태 |
| `LOCK_CONFLICT_409` | Lock 충돌 |
| `GATE_BLOCKED` | Gate가 MOCK_ONLY |
| `ALLOWLIST_VIOLATION` | Allowlist 불일치 |
| `PREFLIGHT_FAIL` | Preflight 실패 |
| `WINDOW_NOT_ACTIVE` | REAL Window 비활성 |
| `TICKET_PROCESSED_OK` | 정상 처리 |
| `TICKET_PROCESS_FAILED` | 처리 실패 |

---

## 4. 실행 흐름

```
1. Emergency Stop 확인
   └─ enabled → STOPPED + 티켓 처리 안함
   
2. Lock 확보
   └─ 충돌 → SKIPPED + reason=LOCK_CONFLICT_409
   
3. Ops Report 생성 (regenerate)

4. 티켓 1건 선택 (OPEN 중 가장 오래된 것)
   └─ 없음 → decision=NONE
   
5. 티켓 처리 시도 (Worker 1-step)
   └─ 성공 → decision=PROCESSED
   └─ 실패 → decision=SKIPPED + reason 기록
   
6. OPS_CYCLE_RUN_V2 스냅샷 저장

7. Lock 해제
```

---

## 5. 저장소 경로

| 경로 | 용도 |
|------|------|
| `reports/ops/daily/snapshots/ops_run_YYYYMMDD_HHMMSS.json` | V2 스냅샷 |
| `state/tickets/ticket_receipts.jsonl` | Receipt 로그 |

---

## 6. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 2.0 | 2026-01-04 | 초기 버전 (Phase C-P.16) |
