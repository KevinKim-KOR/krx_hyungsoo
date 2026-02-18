# Contract: Manual Execution Record V1

**Version**: 1.1 (Added Draft Concept)
**Date**: 2026-02-18
**Status**: ACTIVE

---

## 1. 개요

사람(Operator)의 매매 실행 결과를 기록하는 최종 영수증입니다.
P146부터 **Draft(초안) -> Submit(제출) -> Record(기록)**의 3단계 워크플로우를 따릅니다.

---

## 2. Workflow & Schema

### Phase 1: Draft (Preview)
UI에서 "매매 승인" 버튼을 누르기 전, 서버가 생성하는 미리보기 객체입니다.

- **Schema**: `MANUAL_EXECUTION_DRAFT_V1`
- **Fields**:
  - `plan_id`: 대상 Order Plan ID
  - `ticket_ref`: 참조 Ticket 경로
  - `action`: `EXECUTE` / `CANCEL`
  - `reason`: `MANUAL_CONFIRM` (기본값)
  - `token_required`: `true` (LIVE) / `false` (DRY_RUN)

### Phase 2: Submit (Action)
Operator가 Draft를 확인하고 토큰과 함께 제출합니다.

- **Payload**:
  ```json
  {
      "draft": { ...Draft Object... },
      "token": "safe-token-123"
  }
  ```

### Phase 3: Record (Immutable Result)
서버가 검증 후 생성하는 영구 불변 기록입니다.

- **Schema**: `MANUAL_EXECUTION_RECORD_V1`
- **Path**: `reports/live/manual_execution_record/latest/manual_execution_record_latest.json`

---

## 3. Schema: MANUAL_EXECUTION_RECORD_V1

```json
{
  "schema": "MANUAL_EXECUTION_RECORD_V1",
  "asof": "2026-02-18T09:10:00",
  "record_id": "REC-20260218-001",
  "linkage": {
    "plan_id": "PLAN-20260218-XYZ",
    "ticket_ref": "reports/live/ticket/latest/ticket_latest.md",
    "export_ref": "reports/live/order_plan_export/latest/order_plan_export_latest.json"
  },
  "execution_result": "EXECUTED",
  "operator_proof": {
    "token_hash": "sha256:...",
    "mode": "LIVE"
  },
  "summary": {
    "total_orders": 5,
    "executed": 5,
    "skipped": 0
  }
}
```

---

## 4. Token & Blocking Rules

1. **Ticket == Export**: `Draft.plan_id`와 `Export.plan_id`가 일치해야 합니다.
2. **Token Match**:
   - **LIVE**: 제출된 `token`이 `Export.confirm_token`과 일치해야 합니다. (불일치 시 403)
   - **DRY_RUN**: 토큰이 없으면 서버가 `MOCK_TOKEN`을 자동 주입합니다.
