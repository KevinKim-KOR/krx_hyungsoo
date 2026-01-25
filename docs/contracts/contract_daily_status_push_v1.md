# Contract: Daily Status Push V1

**Version**: 1.1  
**Date**: 2026-01-25  
**Status**: ACTIVE

---

## 1. 개요

OCI 크론(09:05 KST)이 실행 후, 당일 운영 상태와 **추천 상세**를 PUSH 발송합니다.

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
  "mode": "normal",
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
    "decision": "GENERATED",
    "reason": null,
    "items_count": 3
  },
  "reco_items": [
    {"action": "BUY", "ticker": "069500", "name": "KODEX 200", "weight_pct": 25, "signal_score": 0.03},
    {"action": "SELL", "ticker": "229200", "name": "KODEX 코스닥150", "weight_pct": 15, "signal_score": -0.02}
  ],
  "top_risks": ["EVIDENCE_HEALTH_WARN"],
  "message": "📊 KRX OPS: WARN\n🔄 LIVE: OK COMPLETED\n...\n\n📈 추천:\n• BUY 069500 KODEX 200 25% (0.03)\n• SELL 229200 KODEX 코스닥150 15% (-0.02)",
  "delivery_actual": "TELEGRAM",
  "send_receipt": {
    "provider": "TELEGRAM",
    "message_id": 12345,
    "sent_at": "2026-01-25T09:05:01"
  },
  "snapshot_ref": "reports/ops/push/daily_status/snapshots/daily_status_20260125_090501.json",
  "evidence_refs": ["reports/ops/push/daily_status/latest/daily_status_latest.json"]
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema` | string | DAILY_STATUS_PUSH_V1 |
| `asof` | ISO8601 | 생성 시각 |
| `idempotency_key` | string | `daily_status_YYYYMMDD` (mode=test면 `test_daily_status_YYYYMMDD_HHMMSS`) |
| `mode` | enum | normal / test |
| `ops_status` | enum | OK / WARN / BLOCKED / STOPPED |
| `live_status` | object | result + decision |
| `bundle` | object | decision + stale |
| `reco` | object | decision + reason + items_count |
| `reco_items` | array | **v1.1** 추천 상세 (최대 5개) |
| `top_risks` | array | risk code 목록 |
| `message` | string | 발송용 메시지 (추천 상세 포함) |
| `delivery_actual` | enum | CONSOLE_SIMULATED / TELEGRAM / SLACK 등 |
| `send_receipt` | object? | 실발송 시 provider/message_id/sent_at |
| `snapshot_ref` | string | 스냅샷 경로 |
| `evidence_refs` | array | resolver 접근 가능 경로 |

### reco_items 필드 (v1.1)

| 필드 | 타입 | 설명 |
|------|------|------|
| `action` | enum | BUY / SELL / HOLD |
| `ticker` | string | 종목 코드 |
| `name` | string | 종목명 |
| `weight_pct` | number | 비중(%) |
| `signal_score` | number | 시그널 점수 |

**규칙:**
- 최대 5개까지만 포함 (메시지 길이 제한)
- 추천이 비어있으면 `reco.decision=EMPTY`, `reco.reason`에 사유 표시

---

## 4. API

### POST /api/push/daily_status/send

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `confirm` | query | true 필수 |
| `mode` | query | normal(1일1회) / test(우회) |

**응답 (성공):**
```json
{
  "result": "OK",
  "skipped": false,
  "mode": "test",
  "idempotency_key": "test_daily_status_20260125_091234",
  "delivery_actual": "TELEGRAM",
  "message": "...",
  "provider_message_id": 12345
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
| 1.1 | 2026-01-25 | D-P.57: reco_items 상세 추가, mode 필드 추가 |
