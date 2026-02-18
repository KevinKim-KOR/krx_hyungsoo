# Contract: Manual Execution Draft V1

**Version**: 1.0
**Date**: 2026-02-18
**Status**: ACTIVE

---

## 1. 개요

`Manual Execution Draft`는 Operator가 매매를 최종 승인하기 전에 서버로부터 받는 **"실행 미리보기(Preview)"** 객체입니다.
이 객체는 저장되지 않으며(Transient), 오직 Operator Dashboard의 UI 렌더링과 Submit 검증용으로 사용됩니다.

---

## 2. Schema: MANUAL_EXECUTION_DRAFT_V1

```json
{
  "schema": "MANUAL_EXECUTION_DRAFT_V1",
  "asof": "2026-02-18T09:10:00",
  "plan_id": "PLAN-20260218-XYZ",
  "ticket_ref": "reports/live/ticket/latest/ticket_latest.md",
  "action": "EXECUTE",
  "mode": "LIVE",
  "token_required": true,
  "summary": {
    "total_orders": 5,
    "total_value_krw": 1000000
  },
  "validation": {
    "is_valid": true,
    "messages": []
  }
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|---|---|---|
| `plan_id` | String | 대상 Order Plan ID (필수 일치) |
| `ticket_ref` | String | 승인 대상 티켓 경로 |
| `action` | Enum | `EXECUTE` (실행) / `CANCEL` (취소) |
| `mode` | Enum | `LIVE` / `DRY_RUN` |
| `token_required` | Boolean | `true`이면 Submit 시 토큰 필수 |
| `validation.is_valid` | Boolean | 실행 가능 여부 (false면 버튼 비활성화) |

---

## 4. UI 동작 (Operator Dashboard)

1. **Review**: `ticket_ref`의 내용을 Operator에게 보여줍니다.
2. **Input**: `token_required=true`이면 토큰 입력창을 노출합니다.
3. **Action**: `action=EXECUTE`이면 "승인(Submit)" 버튼을, `CANCEL`이면 "취소" 버튼을 활성화합니다.
