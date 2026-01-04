# Contract: Push Channels V1

**Version**: 1.0
**Date**: 2026-01-04
**Status**: LOCKED

---

## 1. 개요

푸시 발송 채널 정의 및 채널별 시크릿 요구사항을 명세합니다.

> 🔒 **Default Rule**: 조건 미충족 시 무조건 CONSOLE

---

## 2. 스키마 정의

### PUSH_CHANNELS_V1

```json
{
  "schema": "PUSH_CHANNELS_V1",
  "channels": ["CONSOLE", "TELEGRAM", "SLACK", "EMAIL"],
  "channel_config": {
    "CONSOLE": {
      "required_secrets": [],
      "allowed_push_types": ["*"]
    },
    "TELEGRAM": {
      "required_secrets": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
      "allowed_push_types": ["ALERT", "DAILY_REPORT", "SIGNAL"]
    },
    "SLACK": {
      "required_secrets": ["SLACK_WEBHOOK_URL"],
      "allowed_push_types": ["ALERT", "DAILY_REPORT"]
    },
    "EMAIL": {
      "required_secrets": ["SMTP_HOST", "SMTP_USER", "SMTP_PASS", "EMAIL_TO"],
      "allowed_push_types": ["DAILY_REPORT"]
    }
  }
}
```

---

## 3. Channels Enum

| 채널 | 설명 |
|------|------|
| `CONSOLE` | 콘솔 출력 (기본) |
| `TELEGRAM` | Telegram Bot API |
| `SLACK` | Slack Webhook |
| `EMAIL` | SMTP Email |

---

## 4. 채널별 Required Secrets

| 채널 | Required Secrets |
|------|------------------|
| CONSOLE | (없음) |
| TELEGRAM | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| SLACK | `SLACK_WEBHOOK_URL` |
| EMAIL | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_TO` |

---

## 5. 채널별 Allowed Push Types

| 채널 | Allowed Types |
|------|---------------|
| CONSOLE | `*` (모든 타입) |
| TELEGRAM | ALERT, DAILY_REPORT, SIGNAL |
| SLACK | ALERT, DAILY_REPORT |
| EMAIL | DAILY_REPORT |

---

## 6. No Values Guarantee

> 🚫 **값 노출 금지**: 이 Contract는 시크릿의 **존재 여부**만 정의합니다.
> 시크릿 값, 길이, 프리픽스 등 유추 가능한 정보는 절대 노출하지 않습니다.

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-04 | 초기 버전 (Phase C-P.19) |
