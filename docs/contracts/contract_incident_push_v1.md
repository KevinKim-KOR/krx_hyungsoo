# Contract: Incident Push V1

**Version**: 1.0  
**Date**: 2026-01-25  
**Status**: ACTIVE

---

## 1. 개요

운영 장애/차단 발생 시 **즉시** 텔레그램으로 알림을 발송합니다.

> 🔒 **Idempotency**: `incident_<KIND>_YYYYMMDD` (동일 타입은 하루 1회)
> 
> 🔒 **Fail-Closed**: 백엔드 다운 시 스크립트에서 telegram.env 직발송 fallback
>
> ⚠️ **스팸 방지**: 동일 종류의 장애는 1일 1회만 발송

---

## 2. Incident 종류

| Kind | 설명 | 발생 조건 |
|------|------|----------|
| `BACKEND_DOWN` | 백엔드 불가 | daily_ops Step2 health 실패 |
| `OPS_BLOCKED` | Ops Summary BLOCKED | overall_status=BLOCKED |
| `OPS_FAILED` | Ops Summary 생성 실패 | API 에러 |
| `LIVE_BLOCKED` | Live Cycle BLOCKED | decision=BLOCKED |
| `LIVE_FAILED` | Live Cycle 실행 실패 | API 에러 |
| `PUSH_FAILED` | 발송 실패 | Telegram 발송 에러 |

---

## 3. Schema: INCIDENT_PUSH_V1

```json
{
  "schema": "INCIDENT_PUSH_V1",
  "asof": "2026-01-25T09:05:30",
  "idempotency_key": "incident_BACKEND_DOWN_20260125",
  "kind": "BACKEND_DOWN",
  "severity": "CRITICAL",
  "step": "Step2",
  "message": "🚨 INCIDENT: BACKEND_DOWN\n\n서버가 응답하지 않습니다.\nStep: Step2 (Health Check)\n\n조치: OCI 접속하여 systemctl restart krx-backend.service",
  "reason": "HTTP 000 - Connection refused",
  "delivery_actual": "TELEGRAM",
  "send_receipt": {
    "provider": "TELEGRAM",
    "message_id": 12346,
    "sent_at": "2026-01-25T09:05:31"
  },
  "snapshot_ref": "reports/ops/push/incident/snapshots/incident_BACKEND_DOWN_20260125_090530.json",
  "evidence_refs": ["reports/ops/push/incident/latest/incident_latest.json"]
}
```

---

## 4. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema` | string | INCIDENT_PUSH_V1 |
| `asof` | ISO8601 | 발생 시각 |
| `idempotency_key` | string | `incident_<KIND>_YYYYMMDD` |
| `kind` | enum | BACKEND_DOWN / OPS_BLOCKED / OPS_FAILED / LIVE_BLOCKED / LIVE_FAILED / PUSH_FAILED |
| `severity` | enum | CRITICAL / HIGH / MEDIUM |
| `step` | string | 발생한 단계 (Step1~6) |
| `message` | string | 발송 메시지 |
| `reason` | string | 상세 사유 |
| `delivery_actual` | enum | CONSOLE_SIMULATED / TELEGRAM / FALLBACK_CURL |
| `send_receipt` | object? | 발송 결과 |
| `snapshot_ref` | string | 스냅샷 경로 |
| `evidence_refs` | array | resolver 접근 가능 경로 |

---

## 5. API

### POST /api/push/incident/send

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `confirm` | query | true 필수 |
| `mode` | query | normal / test |
| `kind` | query | incident 종류 (필수) |
| `reason` | query | 상세 사유 |
| `step` | query | 발생 단계 |

**응답:**
```json
{
  "result": "OK",
  "skipped": false,
  "kind": "BACKEND_DOWN",
  "idempotency_key": "incident_BACKEND_DOWN_20260125",
  "delivery_actual": "TELEGRAM"
}
```

### GET /api/push/incident/latest

최신 incident 조회

---

## 6. 저장소 경로

| 경로 | 용도 |
|------|------|
| `reports/ops/push/incident/latest/incident_latest.json` | 최신 |
| `reports/ops/push/incident/snapshots/incident_<KIND>_YYYYMMDD_HHMMSS.json` | 스냅샷 |

---

## 7. Fallback (백엔드 다운)

백엔드가 죽은 경우, `daily_ops.sh`에서 직접 curl로 Telegram 발송:

```bash
# telegram.env에서 토큰/chat_id 로드 후
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" \
  -d "text=🚨 INCIDENT: BACKEND_DOWN"
```

이 경우 `delivery_actual: "FALLBACK_CURL"`

---

## 8. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-25 | 초기 버전 (D-P.57) |
