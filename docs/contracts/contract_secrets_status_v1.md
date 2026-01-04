# Contract: Secrets Status V1

**Version**: 1.0
**Date**: 2026-01-04
**Status**: LOCKED

---

## 1. 개요

시크릿 존재 여부 상태를 정의합니다.

> 🚫 **값 노출 금지**: 오직 존재 여부(`present: bool`)만 반환합니다.

---

## 2. 스키마 정의

### SECRETS_STATUS_V1

```json
{
  "schema": "SECRETS_STATUS_V1",
  "asof": "2026-01-04T17:00:00",
  "provider": "ENV_ONLY",
  "secrets": {
    "TELEGRAM_BOT_TOKEN": { "present": true },
    "TELEGRAM_CHAT_ID": { "present": true },
    "SLACK_WEBHOOK_URL": { "present": false },
    "SMTP_HOST": { "present": false },
    "SMTP_USER": { "present": false },
    "SMTP_PASS": { "present": false },
    "EMAIL_TO": { "present": false }
  }
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `provider` | string | 시크릿 소스 (`ENV_ONLY`) |
| `secrets` | object | 시크릿별 존재 여부 맵 |
| `secrets[key].present` | boolean | 해당 시크릿 존재 여부 |

---

## 4. Provider 정책

| Provider | 설명 |
|----------|------|
| `ENV_ONLY` | `os.environ`에서만 조회 (기본) |

### .env 지원 (선택 사항)

- `python-dotenv`가 설치되어 있고 `.env` 파일이 존재할 때만 `load_dotenv()`를 **시도**
- 실패/미설치/미존재 시 조용히 `ENV_ONLY`로 진행 (에러로 막지 않음)
- 어떤 경우에도 **값은 반환/로그 금지**

---

## 5. 값 노출 금지 규칙

> 🔒 **Hard Rule**: 다음 정보는 절대 노출 금지
> - 시크릿 값
> - 시크릿 길이
> - 시크릿 프리픽스/서픽스
> - 값 유추 가능한 모든 정보

---

## 6. API Endpoint

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/secrets/status` | 시크릿 존재 여부 조회 |

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-04 | 초기 버전 (Phase C-P.19) |
