# Contract: Ops Run Receipt V1

**Version**: 1.0
**Date**: 2026-01-10
**Status**: LOCKED

---

## 1. 개요

하루 운영 사이클의 통합 영수증 스키마를 정의합니다.

> 🔒 **이 영수증 하나로 오늘 시스템이 뭘 했는지 확인 가능**

---

## 2. 스키마 정의

### OPS_RUN_RECEIPT_V1

```json
{
  "schema": "OPS_RUN_RECEIPT_V1",
  "run_id": "uuid",
  "asof": "2026-01-10T09:05:00",
  "invocation": {
    "type": "API",
    "path": "/api/ops/cycle/run",
    "caller": "scheduler"
  },
  "observed_modes": {
    "gate_mode": "DRY_RUN",
    "delivery_mode": "CONSOLE_ONLY",
    "sender_enable": false,
    "window_active": false,
    "emergency_stop": false
  },
  "ticket_step": {
    "decision": "DONE",
    "reason": "1 ticket processed",
    "receipt_ref": "reports/ops/tickets/snapshots/..."
  },
  "push_delivery_step": {
    "decision": "DONE",
    "outbox_ref": "reports/ops/push/outbox/outbox_latest.json"
  },
  "live_fire_step": {
    "decision": "SKIPPED",
    "reason": "NOT_REAL_GATE",
    "live_fire_receipt_ref": null
  },
  "external_send_count": 0,
  "refs": {
    "ops_run_snapshot": "reports/ops/scheduler/snapshots/ops_run_20260110_090500.json"
  }
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema` | string | OPS_RUN_RECEIPT_V1 |
| `run_id` | UUID | 실행 고유 ID |
| `asof` | ISO8601 | 실행 시각 |
| `invocation` | object | 호출 정보 |
| `invocation.type` | string | API / Script |
| `invocation.path` | string | API 경로 |
| `invocation.caller` | string | 호출자 |
| `observed_modes` | object | 관측된 모드 |
| `observed_modes.gate_mode` | string | Gate 모드 |
| `observed_modes.delivery_mode` | string | Delivery 정책 |
| `observed_modes.sender_enable` | bool | Sender 활성화 |
| `observed_modes.window_active` | bool | 윈도우 활성 |
| `observed_modes.emergency_stop` | bool | Emergency Stop |
| `ticket_step` | object | 티켓 처리 결과 |
| `ticket_step.decision` | string | DONE/SKIPPED |
| `ticket_step.reason` | string | 사유 |
| `ticket_step.receipt_ref` | string? | 영수증 참조 |
| `push_delivery_step` | object | Push Delivery 결과 |
| `push_delivery_step.decision` | string | DONE/SKIPPED |
| `push_delivery_step.outbox_ref` | string? | Outbox 참조 |
| `live_fire_step` | object | Live Fire 결과 |
| `live_fire_step.decision` | string | DONE/SKIPPED/BLOCKED |
| `live_fire_step.reason` | string | 사유 |
| `live_fire_step.live_fire_receipt_ref` | string? | Live Fire 영수증 참조 |
| `external_send_count` | int | 외부 발송 횟수 (0 = 안전) |
| `refs` | object | 스냅샷 참조 |

---

## Schema Fields

> 🔒 **Dotted Path 표기 규칙**: nested는 `a.b.c`

- schema
- run_id
- asof
- invocation
- invocation.type
- invocation.path
- invocation.caller
- observed_modes
- observed_modes.gate_mode
- observed_modes.delivery_mode
- observed_modes.sender_enable
- observed_modes.window_active
- observed_modes.emergency_stop
- ticket_step
- ticket_step.decision
- ticket_step.reason
- ticket_step.receipt_ref
- push_delivery_step
- push_delivery_step.decision
- push_delivery_step.outbox_ref
- live_fire_step
- live_fire_step.decision
- live_fire_step.reason
- live_fire_step.live_fire_receipt_ref
- external_send_count
- refs
- refs.ops_run_snapshot

---

## 4. Decision 값

| 값 | 설명 |
|----|------|
| `DONE` | 정상 완료 |
| `SKIPPED` | 조건 미충족으로 스킵 |
| `BLOCKED` | 정책 위반으로 차단 |
| `STOPPED` | Emergency Stop으로 중단 |

---

## 5. Live Fire Step Reason

| 값 | 설명 |
|----|------|
| `NOT_REAL_GATE` | Gate가 REAL_ENABLED 아님 |
| `NOT_SCHEDULED` | 일정 외 시간 |
| `NO_MESSAGES` | Outbox 비어있음 |
| `SENDER_DISABLED` | Sender 비활성 |
| `WINDOW_INACTIVE` | 윈도우 미활성/소진 |
| `SELF_TEST_FAIL` | Self-Test 실패 |
| `EMERGENCY_STOP` | 비상 정지 |

---

## 6. 저장소 경로

| 경로 | 용도 | 방식 |
|------|------|------|
| `reports/ops/scheduler/latest/ops_run_latest.json` | 최신 영수증 | Atomic Write |
| `reports/ops/scheduler/snapshots/*.json` | 스냅샷 | Append-only |

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-10 | 초기 버전 (Phase C-P.27) |
