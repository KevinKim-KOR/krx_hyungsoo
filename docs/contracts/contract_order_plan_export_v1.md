# Contract: Order Plan Export V1

**Version**: 1.1 (Strict Token Rules)
**Date**: 2026-02-18
**Status**: ACTIVE

---

## 1. 개요

`Order Plan Export`는 자동 생성된 계획을 사람이 검토하고 승인하기 위한 **"Execution Source"**입니다.
Ticket이 생성되기 전, 이 아티팩트가 먼저 생성되어야 하며 **보안 토큰**을 포함합니다.

---

## 2. Schema: ORDER_PLAN_EXPORT_V1

```json
{
  "schema": "ORDER_PLAN_EXPORT_V1",
  "source": { 
     "plan_id": "plan-20240101-100000-xxxx",
     "decision": "GENERATED" 
  },
  "summary": { 
     "orders_count": 5, 
     "buy_value": 1000000 
  },
  "human_confirm": {
     "required": true,
     "confirm_token": "46a7226830efd31b" 
  },
  "decision": "GENERATED"
}
```

---

## 3. Token Policy (Critical)

### 3.1 Source of Truth
`human_confirm.confirm_token` 필드는 전체 매매 사이클에서 유일한 **"승인 키(Approval Key)"**입니다.

### 3.2 Live Mode Restriction
- **LIVE Mode**: `required: true`이며, Ticket 생성 및 Execution Submit 시 이 토큰이 **반드시 일치**해야 합니다.
- **DRY_RUN Mode**: 토큰 검증이 완화되지만, 아티팩트 자체에는 토큰이 포함됩니다.

### 3.3 Linkage
- **Ticket**: `Export.confirm_token` 값을 복사(상속)해야 합니다.
- **Submit**: Operator가 입력한 토큰이 `Export.confirm_token`과 대조됩니다.

---

## 4. 저장소 경로

- **Latest**: `reports/live/order_plan_export/latest/order_plan_export_latest.json`
