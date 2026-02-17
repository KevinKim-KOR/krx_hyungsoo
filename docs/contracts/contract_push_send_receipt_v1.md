# Contract: Push Send Receipt V1

**Version**: 1.0
**Date**: 2026-01-07
**Status**: LOCKED

---

## 1. 개요

실제 발송 결과 영수증 스키마를 정의합니다.

> 🔒 **Formatter 강제**: 발송 본문은 `app/utils/push_formatter.py`만 사용
> 
> 🚫 **Secret Leak Zero**: 에러 메시지 sanitize 필수

---

## 2. 스키마 정의

### PUSH_SEND_RECEIPT_V1

```json
{
  "schema": "PUSH_SEND_RECEIPT_V1",
  "send_id": "uuid",
  "asof": "2026-01-07T23:00:00",
  "channel": "TELEGRAM",
  "message_id": "msg-uuid",
  "request_type": "ALERT",
  "decision": "SENT",
  "blocked_reason": null,
  "formatter_ref": "app/utils/push_formatter.py",
  "preview_ref": "api:/api/push/preview/latest",
  "secrets_status_observed": {
    "TELEGRAM_BOT_TOKEN": true,
    "TELEGRAM_CHAT_ID": true
  },
  "http_status": 200,
  "error_class": null,
  "error_message_sanitized": null,
  "evidence_refs": [
    "reports/ops/evidence/index/latest/evidence_index_latest.json",
    "reports/ops/push/send/latest/send_latest.json",
    "reports/ops/push/outbox/latest/outbox_latest.json"
  ]
}
```

> 🔒 **evidence_refs 규칙**
> - Raw Path Only (접두어 금지: `json:`, `file://` 등)
> - 권장 포함 (존재 시): send_latest, outbox_latest, preview_latest, self_test_latest, evidence_index_latest

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema` | string | 스키마명 (PUSH_SEND_RECEIPT_V1) |
| `send_id` | UUID | 발송 고유 ID (서버 생성) |
| `asof` | ISO8601 | 발송 시각 |
| `channel` | enum | `TELEGRAM` |
| `message_id` | string | Outbox 메시지 ID |
| `request_type` | string | 푸시 타입 (ALERT 등) |
| `decision` | enum | 발송 결정 |
| `blocked_reason` | enum? | 차단 사유 |
| `formatter_ref` | string | 포맷터 경로 |
| `preview_ref` | string | 프리뷰 API 참조 |
| `secrets_status_observed` | object | 시크릿 존재 여부 (값 아님) |
| `secrets_status_observed.TELEGRAM_BOT_TOKEN` | bool | 토큰 존재 여부 |
| `secrets_status_observed.TELEGRAM_CHAT_ID` | bool | 채팅 ID 존재 여부 |
| `http_status` | integer? | HTTP 응답 코드 |
| `error_class` | string? | 에러 클래스명 |
| `error_message_sanitized` | string? | Sanitized 에러 메시지 |

---

## Schema Fields

> 🔒 **Dotted Path 표기 규칙**: nested는 `a.b.c`, 배열은 `items[].field`

- schema
- send_id
- asof
- channel
- message_id
- request_type
- decision
- blocked_reason
- formatter_ref
- preview_ref
- secrets_status_observed
- secrets_status_observed.TELEGRAM_BOT_TOKEN
- secrets_status_observed.TELEGRAM_CHAT_ID
- http_status
- error_class
- error_message_sanitized

---

## 4. Decision 값

| 값 | 설명 |
|----|------|
| `SENT` | 발송 성공 |
| `SKIPPED` | 조건 미충족으로 스킵 |
| `BLOCKED` | 정책 위반으로 차단 |
| `FAILED` | 발송 시도했으나 실패 |

---

## 5. blocked_reason 값

| 값 | 설명 |
|----|------|
| `EMERGENCY_STOP` | 비상 정지 활성 |
| `NOT_REAL_GATE` | Gate가 REAL_ENABLED 아님 |
| `SENDER_DISABLED` | Real Sender 비활성 |
| `SELF_TEST_FAIL` | Self-Test 실패 |
| `NO_MESSAGES` | Outbox 메시지 없음 |
| `ALLOWLIST_VIOLATION` | Allowlist 위반 |
| `WINDOW_CONSUMED` | One-Shot 윈도우 소진 |
| `SECRET_INJECTION_SUSPECTED` | 시크릿 인젝션 감지 |

---

## 6. Error Sanitization 규칙

> 🚫 **시크릿 문자열 마스킹 필수**
> 
> 에러 메시지에서 토큰/API 키 등 시크릿 값이 노출되지 않도록 sanitize

```python
# Sanitize 예시
if "bot" in error_msg.lower() and len(error_msg) > 50:
    error_msg = "[SANITIZED: API error]"
```

---

## 7. 저장소 경로

| 경로 | 용도 | 방식 |
|------|------|------|
| `state/push/send_receipts.jsonl` | 발송 로그 | Append-only |
| `reports/ops/push/send/latest/send_latest.json` | 최신 발송 | Atomic Write |
| `reports/ops/push/send/snapshots/*.json` | 스냅샷 | Append-only |

---

## 8. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-10 | 초기 버전 (Phase C-P.25) |
| 1.1 | 2026-01-10 | Schema Fields 섹션 추가 (Phase C-P.25.1) |
