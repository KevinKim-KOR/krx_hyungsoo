# Contract: Push Render Preview V1

**Version**: 1.0
**Date**: 2026-01-07
**Status**: LOCKED

---

## 1. 개요

Push 메시지 렌더링 프리뷰 스키마를 정의합니다.

> 🔒 **No Send**: 프리뷰만 생성, 실제 발송 절대 금지
> 
> 🚫 **Secret Injection Zero**: 시크릿 값/템플릿 흔적 차단

---

## 2. 스키마 정의

### PUSH_RENDER_PREVIEW_V1

```json
{
  "schema": "PUSH_RENDER_PREVIEW_V1",
  "preview_id": "uuid",
  "asof": "2026-01-07T01:00:00",
  "source_outbox_ref": "reports/ops/push/outbox/outbox_latest.json",
  "formatter_ref": "app/utils/push_formatter.py",
  "channels_evaluated": ["CONSOLE", "TELEGRAM", "SLACK", "EMAIL"],
  "observed_gate_mode": "MOCK_ONLY",
  "rendered": [
    {
      "channel": "TELEGRAM",
      "message_id": "msg-uuid",
      "text_preview": "*[ALERT]* Title\n\nContent",
      "actions_preview": [],
      "blocked": false,
      "blocked_reason": null,
      "secret_injection_check": "PASS"
    }
  ],
  "summary": {
    "total_render": 4,
    "pass": 4,
    "blocked": 0
  }
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema` | string | `PUSH_RENDER_PREVIEW_V1` |
| `preview_id` | UUID | Preview 고유 ID |
| `asof` | ISO8601 | 생성 시각 |
| `source_outbox_ref` | string | 원본 Outbox 경로 |
| `formatter_ref` | string | 포맷터 경로 (단일 소스 보장) |
| `channels_evaluated` | array | 평가된 채널 목록 |
| `observed_gate_mode` | string | 관측된 Gate 모드 |
| `rendered` | array | 채널별 렌더링 결과 |
| `summary` | object | 요약 통계 |

---

## 4. Rendered 항목 구조

| 필드 | 타입 | 설명 |
|------|------|------|
| `channel` | string | 채널명 |
| `message_id` | string | 메시지 식별자 |
| `text_preview` | string | 전송 텍스트 동일본 |
| `actions_preview` | array | 버튼 라벨/타입 |
| `blocked` | boolean | 차단 여부 |
| `blocked_reason` | enum? | 차단 사유 |
| `secret_injection_check` | enum | `PASS` / `BLOCKED` |

---

## 5. blocked_reason 값

| 값 | 설명 |
|----|------|
| `SECRET_INJECTION_SUSPECTED` | 템플릿 패턴 감지 (`{{`, `}}`, `${`) |
| `SECRET_KEY_NAME_IN_TEXT` | 시크릿 키 이름 발견 |
| `null` | 정상 |

---

## 6. Secret Injection 검증 규칙

> 🚫 **차단 패턴**
> - `{{` 또는 `}}` (Jinja/Mustache 템플릿)
> - `${` (Shell/JS 인터폴레이션)
> - `$(` (Shell 명령 치환)

> 🚫 **차단 키 이름**
> - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_TOKEN`
> - `SLACK_WEBHOOK_URL`, `SLACK_TOKEN`
> - `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `SMTP_PASSWORD`
> - `EMAIL_TO`, `EMAIL_PASSWORD`
> - `API_KEY`, `API_SECRET`

---

## 7. 저장소 경로

| 경로 | 용도 | 방식 |
|------|------|------|
| `reports/ops/push/preview/preview_latest.json` | 최신 프리뷰 | Atomic Overwrite |
| `reports/ops/push/preview/snapshots/preview_*.json` | 스냅샷 | Append-only |

---

## 8. API Endpoints

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/push/preview/latest` | 최신 프리뷰 조회 |

---

## 9. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-07 | 초기 버전 (Phase C-P.22) |
