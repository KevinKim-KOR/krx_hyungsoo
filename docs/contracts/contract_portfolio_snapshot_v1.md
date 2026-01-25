# Contract: Portfolio Snapshot V1

**Version**: 1.0  
**Date**: 2026-01-25  
**Status**: ACTIVE

---

## 1. 개요

PC UI에서 입력한 보유자산(현금/보유종목)을 저장하고, Order Plan 생성의 기반이 됩니다.

> 🔒 **Fail-Closed**: Portfolio 없으면 Order Plan은 BLOCKED
>
> 🔒 **Integrity**: payload_sha256으로 무결성 검증

---

## 2. Schema: PORTFOLIO_SNAPSHOT_V1

```json
{
  "schema": "PORTFOLIO_SNAPSHOT_V1",
  "asof": "2026-01-25T10:00:00",
  "portfolio_id": "uuid-v4",
  "cash": 10000000,
  "holdings": [
    {
      "ticker": "069500",
      "name": "KODEX 200",
      "quantity": 100,
      "avg_price": 35000,
      "current_price": 36000,
      "market_value": 3600000
    },
    {
      "ticker": "229200",
      "name": "KODEX 코스닥150",
      "quantity": 50,
      "avg_price": 12000,
      "current_price": 12500,
      "market_value": 625000
    }
  ],
  "total_value": 14225000,
  "cash_ratio_pct": 70.3,
  "updated_at": "2026-01-25T10:00:00",
  "updated_by": "ui",
  "snapshot_ref": "state/portfolio/snapshots/portfolio_20260125_100000.json",
  "evidence_refs": ["state/portfolio/latest/portfolio_latest.json"],
  "integrity": {
    "payload_sha256": "sha256-of-holdings-section"
  }
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema` | string | PORTFOLIO_SNAPSHOT_V1 |
| `asof` | ISO8601 | 스냅샷 시각 |
| `portfolio_id` | UUID | 포트폴리오 ID |
| `cash` | number | 현금 (원) |
| `holdings` | array | 보유 종목 목록 |
| `total_value` | number | 총 평가액 (현금 + 보유종목) |
| `cash_ratio_pct` | number | 현금 비율 (%) |
| `updated_at` | ISO8601 | 최종 수정 시각 |
| `updated_by` | string | ui / api / sync |
| `snapshot_ref` | string | 스냅샷 경로 |
| `evidence_refs` | array | resolver 접근 가능 경로 (최소 1개) |
| `integrity` | object | payload_sha256 |

### holdings[] 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `ticker` | string | 종목 코드 |
| `name` | string | 종목명 |
| `quantity` | number | 보유 수량 |
| `avg_price` | number | 평균 매수가 |
| `current_price` | number | 현재가 (선택) |
| `market_value` | number | 평가금액 |

---

## 4. API

### GET /api/portfolio/latest

최신 포트폴리오 조회

### POST /api/portfolio/upsert?confirm=true

포트폴리오 저장/업데이트

**Request Body:**
```json
{
  "cash": 10000000,
  "holdings": [
    {"ticker": "069500", "name": "KODEX 200", "quantity": 100, "avg_price": 35000}
  ]
}
```

---

## 5. 저장소 경로

| 경로 | 용도 |
|------|------|
| `state/portfolio/latest/portfolio_latest.json` | 최신 |
| `state/portfolio/snapshots/portfolio_YYYYMMDD_HHMMSS.json` | 스냅샷 |

---

## 6. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-25 | 초기 버전 (D-P.58) |
