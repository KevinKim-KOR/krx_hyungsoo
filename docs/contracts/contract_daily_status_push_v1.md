# Contract: Daily Status Push V1

**Version**: 1.0  
**Date**: 2026-01-25  
**Status**: ACTIVE

---

## 1. 개요

OCI 크론(09:05 KST)이 실행 후, 당일 운영 상태를 1줄 요약으로 PUSH 발송합니다.

> 🔒 **Idempotency**: 1일 1회만 발송 (idempotency_key: `daily_status_YYYYMMDD`)
> 
> 🔒 **No Secret Leak**: 비밀/경로/토큰/원문 JSON 금지, 요약만 발송
>
> 🔒 **Fail-Closed**: sender_enabled=true인데 발송 실패 → 운영 장애(exit 3)

---

## 2. Schema: DAILY_STATUS_PUSH_V1

```json
{
  "schema": "DAILY_STATUS_PUSH_V1",
  "asof": "2026-01-25T09:05:00",
  "idempotency_key": "daily_status_20260125",
  "ops_status": "WARN",
  "live_status": {
    "result": "PASS",
    "decision": "COMPLETED"
  },
  "bundle": {
    "decision": "PASS",
    "stale": false
  },
  "reco": {
    "decision": "GENERATED"
  },
  "top_risks": ["EVIDENCE_HEALTH_WARN"],
  "message": "KRX OPS: WARN | LIVE: PASS COMPLETED | bundle=PASS stale=false | reco=GENERATED | risks=[EVIDENCE_HEALTH_WARN]",
  "delivery_actual": "CONSOLE_SIMULATED",
  "send_receipt_ref": null,
  "evidence_refs": ["reports/ops/push/daily_status/latest/daily_status_latest.json"]
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema` | string | DAILY_STATUS_PUSH_V1 |
| `asof` | ISO8601 | 생성 시각 |
| `idempotency_key` | string | `daily_status_YYYYMMDD` 형식 |
| `ops_status` | enum | OK/WARN/BLOCKED/STOPPED |
| `live_status` | object | result + decision |
| `bundle` | object | decision + stale |
| `reco` | object | decision |
| `top_risks` | array | risk code 목록 |
| `message` | string | 1줄 요약 메시지 (발송용) |
| `delivery_actual` | enum | CONSOLE_SIMULATED / TELEGRAM / SLACK 등 |
| `send_receipt_ref` | string? | 실발송 시 receipt 경로 |
| `evidence_refs` | array | resolver 접근 가능 경로 |

---

## 4. API

### POST /api/push/daily_status/send

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `confirm` | query | true 필수 (확인 없이 발송 방지) |

**응답 (성공):**
```json
{
  "result": "OK",
  "delivery_actual": "CONSOLE_SIMULATED",
  "idempotency_key": "daily_status_20260125",
  "skipped": false,
  "message": "KRX OPS: WARN | ..."
}
```

**응답 (이미 발송됨):**
```json
{
  "result": "OK",
  "skipped": true,
  "idempotency_key": "daily_status_20260125",
  "message": "Already sent today"
}
```

---

## 5. 저장소 경로

| 경로 | 용도 |
|------|------|
| `reports/ops/push/daily_status/latest/daily_status_latest.json` | 최신 |
| `reports/ops/push/daily_status/snapshots/daily_status_YYYYMMDD_HHMMSS.json` | 스냅샷 |

---

## 6. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-25 | 초기 버전 (D-P.55) |
