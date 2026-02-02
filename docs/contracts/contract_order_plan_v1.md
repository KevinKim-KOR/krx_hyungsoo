# Contract: Order Plan V1

**Version**: 1.1 (P102 Update)  
**Date**: 2026-02-02  
**Status**: ACTIVE

---

## 1. 개요

Reco + Portfolio를 기반으로 **주문 의도(Intent)**를 생성합니다.
**수량/가격 계산은 포함하지 않으며**, 어떤 종목을 매수/매도할지 방향성만 결정합니다. (P103에서 수량 계산)

> 🔒 **Fail-Closed**: Portfolio 또는 Reco 없으면 BLOCKED
>
> 🔒 **No External Send**: 정보만 생성, 외부 전송 없음
>
> 🔒 **No Broker Call**: 브로커 연동 없음

---

## 2. Schema: ORDER_PLAN_V1

```json
{
  "schema": "ORDER_PLAN_V1",
  "asof": "2026-02-02T10:00:00",
  "plan_id": "uuid-v4",
  "decision": "COMPLETED",
  "reason": "SUCCESS",
  "reason_detail": "Generated 2 orders",
  "source": {
    "reco_ref": "reports/live/reco/latest/reco_latest.json",
    "reco_asof": "2026-02-02T09:55:00",
    "reco_decision": "GENERATED",
    "bundle_id": "uuid-bundle",
    "bundle_created_at": "2026-02-02T09:00:00",
    "payload_sha256": "sha256-hash",
    "portfolio_ref": "state/portfolio/latest/portfolio_latest.json",
    "portfolio_updated_at": "2026-02-02T09:50:00"
  },
  "orders": [
    {
      "ticker": "069500",
      "side": "BUY",
      "intent": "ADD",
      "confidence": "HIGH",
      "reason": "TOP_PICK",
      "reason_detail": "Score 1.5"
    },
    {
      "ticker": "229200",
      "side": "SELL",
      "intent": "EXIT",
      "confidence": "MEDIUM",
      "reason": "HOLDING_ACTION_SELL",
      "reason_detail": "Stop loss triggered"
    }
  ],
  "evidence_refs": ["reports/live/reco/latest/reco_latest.json"],
  "error_summary": null
}
```

---

## 3. 필드 정의

### Top Level
| 필드 | 타입 | 설명 |
|------|------|------|
| `schema` | string | `ORDER_PLAN_V1` 고정 |
| `asof` | ISO8601 | 생성 시각 |
| `decision` | enum | `COMPLETED` / `EMPTY` / `WARN` / `BLOCKED` |
| `reason` | enum | `SUCCESS` / `NO_RECO` / `PORTFOLIO_INCONSISTENT` 등 |
| `reason_detail` | string | 상세 사유 (Sanitized, <=240자) |
| `source` | object | 입력 소스 메타데이터 (추적성) |
| `orders` | array | 주문 의도 목록 |

### source 객체
| 필드 | 설명 |
|------|------|
| `reco_ref` | Reco 리포트 경로 |
| `reco_decision` | Reco 리포트의 decision |
| `bundle_id` | 사용된 전략 번들 ID |
| `portfolio_ref` | Portfolio 파일 경로 |

### orders[] 객체 (Intent-Only)
| 필드 | 타입 | 설명 |
|------|------|------|
| `ticker` | string | 종목 코드 |
| `side` | enum | `BUY` / `SELL` |
| `intent` | enum | `ADD` (추가매수), `REDUCE` (부분매도), `NEW_ENTRY` (신규진입), `EXIT` (전량매도) |
| `confidence` | enum | `LOW` / `MEDIUM` / `HIGH` |
| `reason` | string | 주문 사유 |
| `reason_detail` | string | 상세 사유 |

---

## 4. Decision 규칙 (Fail-Closed)

| 상황 | Decision | Reason |
|------|----------|--------|
| Reco 파일 없음 | `BLOCKED` | `NO_RECO` |
| Reco Decision이 정상이 아님 (BLOCKED/EMPTY 등) | `EMPTY` | `NO_ORDERS_FROM_RECO` |
| Portfolio 데이터 오염 (보유>0인데 가치<=0 등) | `BLOCKED` | `PORTFOLIO_INCONSISTENT` |
| 정상 생성 (주문 있음) | `COMPLETED` | `SUCCESS` |
| 정상 생성 (주문 없음) | `EMPTY` | `NO_ORDERS` |

---

## 5. 저장 경로
- `reports/live/order_plan/latest/order_plan_latest.json`
- `reports/live/order_plan/snapshots/order_plan_YYYYMMDD_HHMMSS.json`
