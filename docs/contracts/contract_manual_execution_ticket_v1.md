# Contract: Manual Execution Ticket V1

**Version**: 1.1 (Source = Export)
**Date**: 2026-02-18
**Status**: ACTIVE

---

## 1. 개요

`Manual Execution Ticket`은 "사람이 읽고 승인하기 위한" 매매 주문서(Job Order)입니다.
단, 실제 실행의 **Source of Truth**는 Ticket이 아니라 **Export 아티팩트**입니다.

| 항목 | 역할 | 비고 |
|---|---|---|
| **Export** | **Execution Source** | 시스템이 생성한 기계어 주문서 (불변) |
| **Ticket** | **Human View** | Export를 사람이 읽기 쉽게 변환한 문서 (Markdown/JSON) |

---

## 2. Token Policy

티켓에는 실행을 위한 `confirm_token`이 포함되어야 하지만, 이 값은 **Export에서 상속**받아야 합니다.

- **Source**: `reports/live/order_plan_export/latest/order_plan_export_latest.json` -> `confirm_token`
- **Validation**:
  - `Ticket.token` != `Export.token` → **Invalid Ticket** (생성 차단 or 경고)
  - Operator는 Ticket에 적힌 토큰을 보고 입력하는 것이 아니라, **Export가 승인한 토큰**을 사용해야 함.

---

## 3. Schema: MANUAL_EXECUTION_TICKET_V1

```json
{
  "schema": "MANUAL_EXECUTION_TICKET_V1",
  "asof": "2026-02-18T09:05:00",
  "source_ref": "reports/live/order_plan_export/latest/order_plan_export_latest.json",
  "plan_id": "PLAN-20260218-XYZ",
  "confirm_token": "safe-token-123",
  "summary": {
    "total_orders": 5,
    "total_buy_krw": 1000000,
    "total_sell_krw": 0
  },
  "orders": [
    {
      "ticker": "005930",
      "action": "BUY",
      "qty": 10,
      "price": 0,
      "msg": "시장가 매수"
    }
  ],
  "view_paths": {
    "markdown": "reports/live/ticket/latest/ticket_latest.md"
  }
}
```

---

## 4. Regeneration Rule

Ticket MD 파일은 언제든지 **latest Export**를 기반으로 재생성될 수 있습니다.

- **Trigger**: `POST /api/operator/ticket/regenerate/{date}`
- **Logic**:
    1. `order_plan_export_latest.json` 로드.
    2. `confirm_token` 및 `plan_id` 추출.
    3. Markdown 템플릿 렌더링.
    4. `ticket_latest.md` 덮어쓰기.
