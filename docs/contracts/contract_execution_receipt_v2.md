# Contract: Execution Receipt V2

**Version**: 2.0
**Date**: 2026-01-03
**Status**: LOCKED

---

## 1. 개요

Execution Receipt V2는 **REAL 실행 증거를 완전히 기록**합니다.

> 📜 **Audit Trail**: command, exit_code, artifacts, 파일 변경 추적

---

## 2. 스키마 정의

### EXECUTION_RECEIPT_V2

```json
{
  "schema": "EXECUTION_RECEIPT_V2",
  "receipt_id": "uuid",
  "request_id": "uuid",
  "mode": "MOCK_ONLY | DRY_RUN | REAL",
  "decision": "EXECUTED | BLOCKED | FAILED",
  "block_reasons": [],
  "started_at": "ISO datetime",
  "finished_at": "ISO datetime",
  "command": ["python", "-m", "app.generate_reports"],
  "exit_code": 0,
  "artifacts_written": ["reports/phase_c/latest/report_human.json"],
  "latest_files_changed": {
    "reports/phase_c/latest/report_human.json": {
      "mtime_before": "2026-01-03T10:00:00",
      "mtime_after": "2026-01-03T19:00:00"
    }
  },
  "safety_checks": {
    "emergency_stop": false,
    "approval_status": "APPROVED",
    "allowlist_pass": true,
    "window_active": true,
    "window_id": "uuid"
  }
}
```

---

## 3. 필드 설명

| Key | Type | 필수 | 설명 |
|-----|------|------|------|
| `decision` | enum | ✅ | EXECUTED/BLOCKED/FAILED |
| `block_reasons` | array | BLOCKED 시 | 차단 사유 목록 |
| `started_at` | ISO8601 | ✅ | 실행 시작 시각 |
| `finished_at` | ISO8601 | ✅ | 실행 종료 시각 |
| `command` | array | REAL 시 | 실행된 명령어 |
| `exit_code` | int/null | REAL 시 | 프로세스 종료 코드 |
| `artifacts_written` | array | ✅ | 생성된 파일 목록 |
| `latest_files_changed` | object | REAL 시 | 변경된 파일 추적 |
| `safety_checks` | object | ✅ | 안전장치 검사 결과 |

---

## 4. 저장소 경로

| 경로 | 정책 |
|------|------|
| `state/tickets/ticket_receipts.jsonl` | Append-only |

---

## 5. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 |
| 2.0 | 2026-01-03 | REAL 증거 강화 (Phase C-P.9) |
