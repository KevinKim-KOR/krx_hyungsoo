# Contract: Weekly Live Fire Ops V1

**Version**: 1.0
**Date**: 2026-01-10
**Status**: LOCKED

---

## 1. 개요

주간 Live Fire 운영 정책 및 윈도우 기반 발송 규칙을 정의합니다.

> 🔒 **No Surprise Sender**: sender_enable=true라도 유효한 윈도우 없으면 발송 금지
> 
> 🔒 **One-Shot**: 성공/실패와 무관하게 1회 시도 = 윈도우 소진
> 
> 🔒 **Post-Fire Lockdown**: 발송 후 sender_enable → false 자동 복귀

---

## 2. 스키마 정의

### WEEKLY_LIVE_FIRE_OPS_V1

```json
{
  "schema": "WEEKLY_LIVE_FIRE_OPS_V1",
  "version": "1.0",
  "window_policy": {
    "enabled_days": ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"],
    "time_window_kst": "09:00-18:00",
    "duration_minutes": 540,
    "max_attempts_per_window": 1
  },
  "preconditions": {
    "gate_mode": "REAL_ENABLED",
    "self_test": "SELF_TEST_PASS",
    "emergency_stop": false,
    "outbox_row_count_min": 1,
    "sender_enable": true,
    "window_active": true
  },
  "postconditions": {
    "window_consumed": true,
    "sender_enable_after": false
  },
  "evidence_refs": {
    "send_latest": "reports/ops/push/send/latest/send_latest.json",
    "send_receipts": "state/push/send_receipts.jsonl",
    "postmortem_latest": "reports/ops/push/postmortem/latest/postmortem_latest.json"
  }
}
```

---

## 3. Window Policy

| 항목 | 값 | 설명 |
|------|------|------|
| `enabled_days` | 월-금 | 주말 발송 금지 |
| `time_window_kst` | 09:00-18:00 | 업무 시간 내 |
| `duration_minutes` | 540 | 9시간 |
| `max_attempts_per_window` | 1 | One-Shot |

---

## 4. Preconditions (발송 전 필수 조건)

| 조건 | 필수 값 | 미충족 시 |
|------|---------|----------|
| Gate Mode | `REAL_ENABLED` | SKIPPED (NOT_REAL_GATE) |
| Self-Test | `SELF_TEST_PASS` | BLOCKED (SELF_TEST_FAIL) |
| Emergency Stop | `false` | BLOCKED (EMERGENCY_STOP) |
| Outbox Messages | `>= 1` | SKIPPED (NO_MESSAGES) |
| Sender Enable | `true` | SKIPPED (SENDER_DISABLED) |
| Window Active | `true` | BLOCKED (WINDOW_INACTIVE) |

---

## 5. Postconditions (발송 후 강제 사항)

| 항목 | 값 | 설명 |
|------|------|------|
| `window_consumed` | `true` | 윈도우 소진 (성공/실패 무관) |
| `sender_enable_after` | `false` | 자동 Lockdown |

---

## 6. 운영 흐름

```
1. Outbox 확인 → row_count < 1 → SKIP (NO_MESSAGES)
2. Preconditions 체크 → 실패 → SKIP/BLOCKED
3. POST /api/push/send/run 호출
4. (성공/실패 무관) Window 소진 처리
5. Sender Enable → false 복귀
6. LIVE_FIRE_OPS_RECEIPT_V1 저장
```

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-10 | 초기 버전 (Phase C-P.26) |
