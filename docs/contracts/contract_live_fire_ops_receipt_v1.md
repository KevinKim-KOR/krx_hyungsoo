# Contract: Live Fire Ops Receipt V1

**Version**: 1.0
**Date**: 2026-01-10
**Status**: LOCKED

---

## 1. 개요

1회 Live Fire 실행에 대한 운영 요약 증거 스키마를 정의합니다.

> 🔒 **운영 1줄 요약**: 언제, 어떤 outbox 1건이, 어떤 채널로, 성공/실패로 끝났는지

---

## 2. 스키마 정의

### LIVE_FIRE_OPS_RECEIPT_V1

```json
{
  "schema": "LIVE_FIRE_OPS_RECEIPT_V1",
  "run_id": "uuid",
  "asof": "2026-01-10T15:30:00",
  "precheck_summary": {
    "gate_mode": "REAL_ENABLED",
    "self_test": "SELF_TEST_PASS",
    "emergency_stop": false,
    "sender_enabled": true,
    "window_active": true,
    "outbox_row_count": 1
  },
  "attempted": true,
  "blocked_reason": null,
  "send_http_status": 200,
  "channel": "TELEGRAM",
  "message_id": "uuid",
  "window_consumed": true,
  "sender_disabled_after": true,
  "refs": {
    "outbox_snapshot_path": "reports/ops/push/outbox/snapshots/...",
    "send_latest_path": "reports/ops/push/send/send_latest.json",
    "postmortem_latest_path": "reports/ops/push/postmortem/postmortem_latest.json"
  }
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema` | string | LIVE_FIRE_OPS_RECEIPT_V1 |
| `run_id` | UUID | 실행 고유 ID |
| `asof` | ISO8601 | 실행 시각 |
| `precheck_summary` | object | 사전 점검 결과 |
| `precheck_summary.gate_mode` | string | Gate 모드 |
| `precheck_summary.self_test` | string | Self-Test 결과 |
| `precheck_summary.emergency_stop` | bool | Emergency Stop 상태 |
| `precheck_summary.sender_enabled` | bool | Sender Enable 상태 |
| `precheck_summary.window_active` | bool | 윈도우 활성 여부 |
| `precheck_summary.outbox_row_count` | int | Outbox 메시지 수 |
| `attempted` | bool | 발송 시도 여부 |
| `blocked_reason` | string? | 차단 사유 |
| `send_http_status` | int? | HTTP 응답 코드 |
| `channel` | string | 발송 채널 (TELEGRAM) |
| `message_id` | string? | 메시지 ID |
| `window_consumed` | bool | 윈도우 소진 여부 |
| `sender_disabled_after` | bool | Sender Lockdown 확인 |
| `refs` | object | 증거 파일 참조 |

---

## Schema Fields

> 🔒 **Dotted Path 표기 규칙**: nested는 `a.b.c`, 배열은 `items[].field`

- schema
- run_id
- asof
- precheck_summary
- precheck_summary.gate_mode
- precheck_summary.self_test
- precheck_summary.emergency_stop
- precheck_summary.sender_enabled
- precheck_summary.window_active
- precheck_summary.outbox_row_count
- attempted
- blocked_reason
- send_http_status
- channel
- message_id
- window_consumed
- sender_disabled_after
- refs
- refs.outbox_snapshot_path
- refs.send_latest_path
- refs.postmortem_latest_path

---

## 4. 저장소 경로

| 경로 | 용도 | 방식 |
|------|------|------|
| `reports/ops/push/live_fire/live_fire_latest.json` | 최신 Receipt | Atomic Write |
| `reports/ops/push/live_fire/snapshots/*.json` | 스냅샷 | Append-only |

---

## 5. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-10 | 초기 버전 (Phase C-P.26) |
