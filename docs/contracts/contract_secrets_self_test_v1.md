# Contract: Secrets Self-Test V1

**Version**: 1.0
**Date**: 2026-01-04
**Status**: LOCKED

---

## 1. 개요

시크릿 Self-Test 결과 스키마를 정의합니다.

> 🔒 **Fail Closed**: 애매하면 PASS가 아니라 FAIL

---

## 2. 스키마 정의

### SECRETS_SELF_TEST_V1

```json
{
  "schema": "SECRETS_SELF_TEST_V1",
  "asof": "2026-01-04T18:00:00",
  "provider": "ENV_ONLY",
  "secrets_checked_count": 7,
  "present_count": 2,
  "missing_required_by_channel": {
    "TELEGRAM": [],
    "SLACK": ["SLACK_WEBHOOK_URL"],
    "EMAIL": ["SMTP_HOST", "SMTP_USER", "SMTP_PASS", "EMAIL_TO"]
  },
  "decision": "SELF_TEST_PASS",
  "reason": "TELEGRAM channel ready (2/2 secrets present)"
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema` | string | `SECRETS_SELF_TEST_V1` |
| `asof` | ISO8601 | 테스트 시각 |
| `provider` | string | 시크릿 소스 (`ENV_ONLY`) |
| `secrets_checked_count` | integer | 체크한 시크릿 총 수 |
| `present_count` | integer | 존재하는 시크릿 수 |
| `missing_required_by_channel` | object | 채널별 누락된 시크릿 목록 |
| `decision` | enum | `SELF_TEST_PASS` 또는 `SELF_TEST_FAIL` |
| `reason` | string | 결정 사유 (값 노출 없음) |

---

## 4. Decision 규칙

| 결정 | 조건 |
|------|------|
| `SELF_TEST_PASS` | 최소 1개 외부 채널이 완전 준비됨 |
| `SELF_TEST_FAIL` | 모든 외부 채널이 불완전 |

### 채널별 완전 준비 기준

| 채널 | 조건 |
|------|------|
| TELEGRAM | `TELEGRAM_BOT_TOKEN` AND `TELEGRAM_CHAT_ID` |
| SLACK | `SLACK_WEBHOOK_URL` |
| EMAIL | `SMTP_HOST` AND `SMTP_USER` AND `SMTP_PASS` AND `EMAIL_TO` |

---

## 5. Reason 예시 (값 노출 없음)

| 상황 | Reason |
|------|--------|
| Telegram 준비 | `TELEGRAM channel ready (2/2 secrets present)` |
| 전체 미준비 | `No external channel ready` |
| Slack만 준비 | `SLACK channel ready (1/1 secrets present)` |

---

## 6. 저장소 경로

| 경로 | 용도 |
|------|------|
| `reports/ops/secrets/latest/self_test_latest.json` | 최신 결과 (overwrite) |
| `reports/ops/secrets/snapshots/self_test_*.json` | 스냅샷 (append-only) |

---

## 7. API Endpoints

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/secrets/self_test` | 최근 결과 조회 |
| POST | `/api/secrets/self_test/run` | Self-Test 실행 |

---

## 8. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-04 | 초기 버전 (Phase C-P.20) |
