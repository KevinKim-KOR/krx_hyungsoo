# Contract: Push Delivery V1

**Version**: 1.0
**Date**: 2026-01-04
**Status**: LOCKED

---

## 1. 개요

푸시 메시지 발송 라우터의 결정 영수증 스키마를 정의합니다.

> 🔒 **Console-First**: 기본 목적지는 CONSOLE. 외부 발송 조건 미충족 시 무조건 CONSOLE로 회귀.

---

## 2. 스키마 정의

### PUSH_DELIVERY_RECEIPT_V1

```json
{
  "schema": "PUSH_DELIVERY_RECEIPT_V1",
  "delivery_run_id": "uuid",
  "asof": "2026-01-04T17:00:00",
  "gate_mode": "MOCK_ONLY",
  "emergency_stop_enabled": false,
  "secrets_available": false,
  "summary": {
    "total_messages": 5,
    "console": 5,
    "external": 0,
    "skipped": 0
  },
  "decisions": [
    {
      "message_id": "msg-uuid",
      "channel_decision": "CONSOLE",
      "channel_target": "console",
      "reason_code": "GATE_MOCK_ONLY_CONSOLE"
    }
  ]
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `delivery_run_id` | UUID | 실행 ID |
| `asof` | ISO8601 | 실행 시각 |
| `gate_mode` | string | 현재 Gate 모드 |
| `emergency_stop_enabled` | boolean | 비상 정지 상태 |
| `secrets_available` | boolean | 외부 발송 시크릿 존재 여부 |
| `summary` | object | 결정 요약 |
| `decisions` | array | 개별 메시지 결정 목록 |

---

## 4. Reason Codes

| 코드 | 설명 |
|------|------|
| `GATE_MOCK_ONLY_CONSOLE` | Gate가 MOCK_ONLY → CONSOLE |
| `GATE_DRY_RUN_CONSOLE_ONLY` | Gate가 DRY_RUN → CONSOLE |
| `NO_SECRET_FALLBACK_CONSOLE` | REAL이지만 Secrets 미설정 → CONSOLE |
| `EMERGENCY_STOP_FORCED_CONSOLE` | 비상 정지 활성 → CONSOLE 강제 |
| `EXTERNAL_ALLOWED` | REAL + Secrets OK → 외부 발송 가능 (시뮬레이션) |

---

## 5. 저장소 경로

| 경로 | 용도 |
|------|------|
| `state/push/push_delivery_receipts.jsonl` | Append-only 결정 로그 |
| `reports/ops/push/push_delivery_latest.json` | 최신 결정 스냅샷 |
| `reports/ops/push/console_out_latest.json` | 콘솔 출력 내용 |

---

## 6. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-04 | 초기 버전 (Phase C-P.18) |
