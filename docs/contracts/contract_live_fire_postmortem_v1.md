# Contract: Live Fire Postmortem V1

**Version**: 1.0
**Date**: 2026-01-10
**Status**: LOCKED

---

## 1. 개요

Live Fire 실행 결과 분석 및 Kill-Switch 상태 검증을 위한 Postmortem 스키마를 정의합니다.

> 🔒 **No External Send**: 이 단계는 분석/기록 전용
> 
> 🔒 **Kill-Switch Check**: Sender 비활성 상태 검증 필수

---

## 2. 스키마 정의

### LIVE_FIRE_POSTMORTEM_V1

```json
{
  "schema": "LIVE_FIRE_POSTMORTEM_V1",
  "event_id": "uuid",
  "asof": "2026-01-10T14:00:00",
  "overall_safety_status": "SAFE",
  "context_observed": {
    "gate_mode": "MOCK_ONLY",
    "sender_enabled": false,
    "emergency_stop_enabled": false,
    "self_test_decision": "SELF_TEST_PASS"
  },
  "send_attempt_observed": {
    "attempted": true,
    "decision": "SENT",
    "http_status": 200,
    "ref": "reports/ops/push/send/send_latest.json"
  },
  "safety_invariants": {
    "sender_is_currently_disabled": true,
    "window_was_consumed": true,
    "emergency_stop_is_off": true
  },
  "evidence_refs": {
    "outbox_path": "reports/ops/push/outbox/outbox_latest.json",
    "receipt_path": "state/push/send_receipts.jsonl",
    "send_latest_path": "reports/ops/push/send/send_latest.json"
  }
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema` | string | `LIVE_FIRE_POSTMORTEM_V1` |
| `event_id` | UUID | Postmortem 이벤트 고유 ID |
| `asof` | ISO8601 | 생성 시각 |
| `overall_safety_status` | enum | `SAFE` / `UNSAFE` / `UNKNOWN` |
| `context_observed` | object | 관측된 시스템 상태 |
| `context_observed.gate_mode` | string | Gate 모드 |
| `context_observed.sender_enabled` | bool | Sender 활성화 여부 |
| `context_observed.emergency_stop_enabled` | bool | Emergency Stop 활성화 |
| `context_observed.self_test_decision` | string | Self-Test 결과 |
| `send_attempt_observed` | object | 발송 시도 관측 결과 |
| `send_attempt_observed.attempted` | bool | 발송 시도 여부 |
| `send_attempt_observed.decision` | string | 발송 결정 |
| `send_attempt_observed.http_status` | int? | HTTP 상태 코드 |
| `send_attempt_observed.ref` | string? | 참조 경로 |
| `safety_invariants` | object | 안전 불변식 검증 결과 |
| `safety_invariants.sender_is_currently_disabled` | bool | Sender 비활성 상태 |
| `safety_invariants.window_was_consumed` | bool | 윈도우 소진 여부 |
| `safety_invariants.emergency_stop_is_off` | bool | Emergency Stop OFF 상태 |
| `evidence_refs` | object | 증거 파일 경로 |
| `evidence_refs.outbox_path` | string? | Outbox 경로 |
| `evidence_refs.receipt_path` | string? | Receipt 경로 |
| `evidence_refs.send_latest_path` | string? | Send Latest 경로 |

---

## Schema Fields

> 🔒 **Dotted Path 표기 규칙**: nested는 `a.b.c`, 배열은 `items[].field`

- schema
- event_id
- asof
- overall_safety_status
- context_observed
- context_observed.gate_mode
- context_observed.sender_enabled
- context_observed.emergency_stop_enabled
- context_observed.self_test_decision
- send_attempt_observed
- send_attempt_observed.attempted
- send_attempt_observed.decision
- send_attempt_observed.http_status
- send_attempt_observed.ref
- safety_invariants
- safety_invariants.sender_is_currently_disabled
- safety_invariants.window_was_consumed
- safety_invariants.emergency_stop_is_off
- evidence_refs
- evidence_refs.outbox_path
- evidence_refs.receipt_path
- evidence_refs.send_latest_path

---

## 4. overall_safety_status 계산 규칙

| 상태 | 조건 |
|------|------|
| `SAFE` | sender_enabled=false AND emergency_stop=false |
| `UNSAFE` | sender_enabled=true (Kill-Switch ON 상태) |
| `UNKNOWN` | 상태 파일 없음 또는 파싱 실패 |

---

## 5. 저장소 경로

| 경로 | 용도 | 방식 |
|------|------|------|
| `reports/ops/push/postmortem/postmortem_latest.json` | 최신 Postmortem | Atomic Write |
| `reports/ops/push/postmortem/snapshots/*.json` | 스냅샷 | Append-only |

---

## 6. API Endpoints

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/ops/push/postmortem/latest` | 최신 Postmortem 조회 |
| POST | `/api/ops/push/postmortem/regenerate` | Postmortem 재생성 |

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-10 | 초기 버전 (Phase C-P.25) |
