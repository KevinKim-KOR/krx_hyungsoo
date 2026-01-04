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

| Priority | Source | 설명 |
|----------|--------|------|
| 1 | `ENV_ONLY` | OS 환경변수 (`os.environ`) - **기본** |
| 2 | `.env` (Optional) | `python-dotenv` 설치 시 지원 가능 |

### .env 지원 조건

```python
# .env 지원은 선택적
try:
    from dotenv import load_dotenv
    if Path(".env").exists():
        load_dotenv()
except ImportError:
    pass  # ENV_ONLY로 동작
```

---

## 4. Non-Leak 규칙

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

## 5. 운영 책임

| 책임 주체 | 역할 |
|-----------|------|
| **운영자** | 시크릿 세팅, 회전, 폐기 |
| **시스템** | 상태 체크 (present/absent), 보고 |

---

## 6. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-04 | 초기 버전 (Phase C-P.20) |
