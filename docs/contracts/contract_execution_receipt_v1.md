# Contract: Execution Receipt V1

**Version**: 1.0
**Date**: 2026-01-03
**Status**: LOCKED

---

## 1. 개요

Execution Receipt는 **티켓 실행 시도에 대한 영수증**입니다.

> 📝 **Append-Only**: 모든 실행 시도는 수정/삭제 없이 기록됩니다.

---

## 2. 스키마 정의

### EXECUTION_RECEIPT_V1

```json
{
  "schema": "EXECUTION_RECEIPT_V1",
  "receipt_id": "uuid",
  "request_id": "uuid",
  "issued_at": "2026-01-03T17:00:00+09:00",
  "mode": "MOCK_ONLY | DRY_RUN | REAL_ENABLED",
  "result": "SKIPPED | BLOCKED | DONE | FAILED",
  "message": "실행 결과 메시지",
  "artifacts": []
}
```

| Key | Type | 필수 | 생성 주체 | 설명 |
|-----|------|------|-----------|------|
| `receipt_id` | UUID | ✅ | **Server** | 영수증 고유 ID |
| `request_id` | UUID | ✅ | From Ticket | 원본 티켓 ID |
| `issued_at` | ISO8601 | ✅ | **Server** | 발급 시각 |
| `mode` | enum | ✅ | Gate 상태 | 실행 모드 |
| `result` | enum | ✅ | Worker | 실행 결과 |
| `message` | string | ✅ | Worker | 결과 메시지 |
| `artifacts` | array | ⚠️ | Worker | 생성된 산출물 목록 |

---

## 3. Result 정의

| Result | 설명 |
|--------|------|
| `SKIPPED` | 실행 건너뜀 (Emergency Stop 등) |
| `BLOCKED` | 정책에 의해 차단됨 |
| `DONE` | 정상 완료 |
| `FAILED` | 실행 실패 |

---

## 4. 저장소 경로

| 경로 | 정책 |
|------|------|
| `state/tickets/ticket_receipts.jsonl` | Append-only |

---

## 5. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-P.6) |
