# Contract: Order Plan V1

**Version**: 1.0  
**Date**: 2026-01-25  
**Status**: ACTIVE

---

## 1. 개요

Reco + Portfolio를 기반으로 실제 주문안(매수/매도 수량)을 생성합니다.

> 🔒 **Fail-Closed**: Portfolio 또는 Reco 없으면 BLOCKED
>
> 🔒 **No External Send**: 주문안은 정보만 생성, 실제 주문 실행 없음

---

## 2. Schema: ORDER_PLAN_V1

```json
{
  "schema": "ORDER_PLAN_V1",
  "asof": "2026-01-25T10:00:00",
  "plan_id": "uuid-v4",
  "decision": "GENERATED",
  "reason": "SUCCESS",
  "source_refs": {
    "reco_ref": "reports/live/reco/latest/reco_latest.json",
    "portfolio_ref": "state/portfolio/latest/portfolio_latest.json"
  },
  "orders": [
    {
      "action": "BUY",
      "ticker": "069500",
      "name": "KODEX 200",
      "target_weight_pct": 25,
      "current_weight_pct": 10,
      "delta_weight_pct": 15,
      "order_amount": 1500000,
      "estimated_quantity": 42,
      "signal_score": 0.03
    },
    {
      "action": "SELL",
      "ticker": "229200",
      "name": "KODEX 코스닥150",
      "target_weight_pct": 0,
      "current_weight_pct": 5,
      "delta_weight_pct": -5,
      "order_amount": -625000,
      "estimated_quantity": -50,
      "signal_score": -0.02
    }
  ],
  "summary": {
    "total_buy_amount": 1500000,
    "total_sell_amount": 625000,
    "net_cash_change": -875000,
    "estimated_cash_after": 9125000,
    "estimated_cash_ratio_pct": 64.2,
    "buy_count": 1,
    "sell_count": 1
  },
  "constraints_applied": {
    "max_single_weight_pct": 30,
    "min_order_amount": 100000
  },
  "snapshot_ref": "reports/live/order_plan/snapshots/order_plan_20260125_100000.json",
  "evidence_refs": ["reports/live/order_plan/latest/order_plan_latest.json"],
  "integrity": {
    "payload_sha256": "sha256-of-orders-section"
  }
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema` | string | ORDER_PLAN_V1 |
| `asof` | ISO8601 | 생성 시각 |
| `plan_id` | UUID | 주문안 ID |
| `decision` | enum | GENERATED / BLOCKED / EMPTY |
| `reason` | string | SUCCESS / NO_PORTFOLIO / NO_RECO / EMPTY_RECO |
| `source_refs` | object | reco_ref + portfolio_ref |
| `orders` | array | 주문 목록 |
| `summary` | object | 요약 통계 |
| `constraints_applied` | object | 적용된 제약 조건 |
| `snapshot_ref` | string | 스냅샷 경로 |
| `evidence_refs` | array | resolver 접근 가능 경로 |
| `integrity` | object | payload_sha256 |

### orders[] 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `action` | enum | BUY / SELL |
| `ticker` | string | 종목 코드 |
| `name` | string | 종목명 |
| `target_weight_pct` | number | 목표 비중 (%) |
| `current_weight_pct` | number | 현재 비중 (%) |
| `delta_weight_pct` | number | 변화 비중 (%) |
| `order_amount` | number | 주문 금액 (원) |
| `estimated_quantity` | number | 예상 수량 |
| `signal_score` | number | 시그널 점수 |

---

## 4. API

### GET /api/order_plan/latest

최신 주문안 조회

### POST /api/order_plan/regenerate?confirm=true

주문안 재생성

---

## 5. 저장소 경로

| 경로 | 용도 |
|------|------|
| `reports/live/order_plan/latest/order_plan_latest.json` | 최신 |
| `reports/live/order_plan/snapshots/order_plan_YYYYMMDD_HHMMSS.json` | 스냅샷 |

---

## 6. Decision 규칙

| 상황 | decision | reason |
|------|----------|--------|
| Portfolio 없음 | BLOCKED | NO_PORTFOLIO |
| Reco 없음 | BLOCKED | NO_RECO |
| Reco가 EMPTY/BLOCKED | BLOCKED | EMPTY_RECO |
| 주문 생성 성공 | GENERATED | SUCCESS |
| 주문이 비어있음 | EMPTY | NO_ORDERS |

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-25 | 초기 버전 (D-P.58) |
