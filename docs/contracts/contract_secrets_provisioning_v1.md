# Contract: Secrets Provisioning V1

**Version**: 1.0
**Date**: 2026-01-04
**Status**: LOCKED

---

## 1. 개요

시크릿 프로비저닝 규칙을 정의합니다.

> 🔒 **운영 책임**: 시크릿 세팅/회전은 운영자가 수행, 시스템은 상태만 체크

---

## 2. Canonical Secret Names

| 채널 | Secret Name | 설명 |
|------|-------------|------|
| TELEGRAM | `TELEGRAM_BOT_TOKEN` | Telegram Bot API Token |
| TELEGRAM | `TELEGRAM_CHAT_ID` | Telegram Chat ID |
| SLACK | `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL |
| EMAIL | `SMTP_HOST` | SMTP 서버 호스트 |
| EMAIL | `SMTP_USER` | SMTP 사용자명 |
| EMAIL | `SMTP_PASS` | SMTP 비밀번호 |
| EMAIL | `EMAIL_TO` | 수신자 이메일 주소 |

---

## 3. Source Priority

> 🔒 **SYSTEM_ENV > DOTENV**: 시스템 환경변수가 .env보다 우선

| Priority | Source | 설명 |
|----------|--------|------|
| 1 | `SYSTEM_ENV` | OS 시스템 환경변수 - **최우선** |
| 2 | `DOTENV` | `.env` 파일 (override=false) |

### .env 로딩 정책 (C-P.24)

```python
# override=false: 시스템 환경변수가 우선
try:
    from dotenv import load_dotenv
    if Path(".env").exists():
        load_dotenv(override=False)  # SYSTEM_ENV > DOTENV
except ImportError:
    pass  # ENV_ONLY로 동작
```

> ⚠️ **로딩 시점**: Backend 프로세스 시작 시 1회만 로드 (요청마다 로드 금지)

---

## 4. Present 판정 규칙 (C-P.24)

> 🔒 **present 판정**: `os.getenv(KEY)`가 None 또는 빈 문자열 ""이면 `false`, 그 외 `true`

```python
def is_present(key: str) -> bool:
    value = os.getenv(key)
    return value is not None and value != ""
```

### Self-Test 한계

| 항목 | 설명 |
|------|------|
| 체크 대상 | present (존재 여부) |
| 미체크 대상 | valid (유효성, 네트워크 호출 금지) |
| 보증 범위 | **형상 완결성(Configuration completeness)** |

---

## 5. Non-Leak 규칙

> 🚫 **값 노출 절대 금지**

| 금지 항목 | 설명 |
|-----------|------|
| 값 반환 | API 응답에 값 포함 금지 |
| 값 로깅 | 로그에 값 출력 금지 |
| 값 마스킹 | `***` 형태도 길이 유추 가능하므로 금지 |
| 부분 문자열 | 앞/뒤 일부 노출 금지 |

### 허용되는 응답

```json
{
  "TELEGRAM_BOT_TOKEN": { "present": true },
  "TELEGRAM_CHAT_ID": { "present": false }
}
```

---

## 6. 운영 책임

| 책임 주체 | 역할 |
|-----------|------|
| **운영자** | 시크릿 세팅, 회전, 폐기 |
| **시스템** | 상태 체크 (present/absent), 보고 |

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-04 | 초기 버전 (Phase C-P.20) |
| 1.1 | 2026-01-07 | SYSTEM_ENV > DOTENV 우선순위, present 판정 규칙 (Phase C-P.24) |
