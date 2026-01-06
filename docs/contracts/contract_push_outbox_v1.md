# Contract: Push Outbox V1

**Version**: 1.0
**Date**: 2026-01-07
**Status**: LOCKED

---

## 1. 개요

Push 발송 예정본(Outbox)의 스키마를 정의합니다.

> 🔒 **delivery_policy = CONSOLE_ONLY** (고정)
> 
> 🚫 **시크릿 값 포함 절대 금지**

---

## 2. 스키마 정의

### PUSH_OUTBOX_V1

```json
{
  "schema": "PUSH_OUTBOX_V1",
  "outbox_id": "uuid",
  "asof": "2026-01-07T12:00:00",
  "delivery_run_id": "uuid",
  "gate_mode_observed": "MOCK_ONLY",
  "delivery_policy": "CONSOLE_ONLY",
  "self_test_decision_observed": "SELF_TEST_FAIL",
  "messages": [
    {
      "message_id": "msg-uuid",
      "push_type": "ALERT",
      "title": "Alert Title",
      "content": "Message content",
      "target_channels": ["CONSOLE"],
      "blocked_reason": "NO_SECRETS_FOR_ANY_CHANNEL"
    }
  ],
  "summary": {
    "total_messages": 1,
    "console_bound": 1,
    "external_candidate": 0
  }
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema` | string | `PUSH_OUTBOX_V1` |
| `outbox_id` | UUID | Outbox 고유 ID |
| `asof` | ISO8601 | 생성 시각 |
| `delivery_run_id` | UUID | 연관된 Delivery Run ID |
| `gate_mode_observed` | string | 관측된 Gate 모드 |
| `delivery_policy` | string | **항상 CONSOLE_ONLY** |
| `self_test_decision_observed` | string? | Self-Test 결과 |
| `messages` | array | 발송 예정 메시지 목록 |
| `summary` | object | 요약 통계 |

---

## 4. 핵심 규칙

> 🛑 **External Send = FORBIDDEN**
> 
> Outbox는 "발송 예정"만 기록합니다. 실제 외부 발송은 절대 금지입니다.

> 🚫 **시크릿 값 포함 금지**
> 
> 어떤 필드에도 시크릿 값, 토큰, API 키 등을 포함하지 않습니다.

---

## 5. 저장소 경로

| 경로 | 용도 | 방식 |
|------|------|------|
| `reports/ops/push/outbox/outbox_latest.json` | 최신 Outbox | Atomic Overwrite |
| `reports/ops/push/outbox/snapshots/outbox_*.json` | 스냅샷 | Append-only |

### Atomic Write 절차

```python
tmp_path = "outbox_latest.json.tmp"
# 1. tmp에 완전한 JSON 기록
tmp_path.write_text(json.dumps(data))
# 2. os.replace로 원자적 교체
os.replace(tmp_path, latest_path)
```

---

## 6. Snapshot Naming 규칙

- **포맷**: `outbox_YYYYMMDD_HHMMSS.json`
- **예**: `outbox_20260107_132501.json`
- **금지**: 콜론(`:`) 사용 금지

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-07 | 초기 버전 (Phase C-P.21) |
