# Contract: Ticket Result V1

**Version**: 1.0
**Date**: 2026-01-03
**Status**: LOCKED

---

## 1. 개요

티켓 결과 시스템은 **티켓 처리 상태를 기록**하는 시스템입니다.

> 🚫 **No Execution 원칙**: 상태 변경은 **기록만** 수행합니다. 실제 엔진 실행은 별도로 처리됩니다.

---

## 2. 스키마 정의

### 2-A. TICKET_RESULT_V1 (저장용)

처리 결과를 기록하는 스키마입니다.

```json
{
  "schema": "TICKET_RESULT_V1",
  "result_id": "uuid-server-generated",
  "request_id": "uuid-ref-to-request",
  "processed_at": "2026-01-03T14:50:00+09:00",
  "status": "IN_PROGRESS | DONE | FAILED",
  "processor_id": "manual | worker_id",
  "message": "처리 메시지",
  "artifacts": []
}
```

| Key | Type | 필수 | 생성 주체 | 설명 |
|-----|------|------|-----------|------|
| `result_id` | UUID | ✅ | **Server** | 결과 고유 ID |
| `request_id` | UUID | ✅ | Client | 원본 티켓 ID |
| `processed_at` | ISO8601 | ✅ | **Server** | 처리 시각 |
| `status` | enum | ✅ | Client | 처리 상태 |
| `processor_id` | string | ✅ | Client | 처리자 ID |
| `message` | string | ✅ | Client | 처리 메시지 |
| `artifacts` | array | ⚠️ | Client | 생성된 산출물 경로 |

---

### 2-B. TICKETS_BOARD_V1 (조회용 View)

상태 보드에 표시할 종합 뷰입니다.

```json
{
  "request_id": "uuid",
  "requested_at": "2026-01-03T14:20:00+09:00",
  "request_type": "REQUEST_RECONCILE",
  "payload": {...},
  "trace_id": "optional",
  "current_status": "OPEN | IN_PROGRESS | DONE | FAILED",
  "last_message": "최신 메시지",
  "last_processed_at": "2026-01-03T14:50:00+09:00"
}
```

---

## 3. State Machine

### 상태 전이 규칙

```
OPEN ─────→ IN_PROGRESS ─────→ DONE
                 │
                 └─────────────→ FAILED
```

| From | To | 조건 |
|------|----|------|
| `OPEN` | `IN_PROGRESS` | consume 호출 |
| `IN_PROGRESS` | `DONE` | complete(status=DONE) |
| `IN_PROGRESS` | `FAILED` | complete(status=FAILED) |
| `DONE` | * | ❌ 불가 |
| `FAILED` | * | ❌ 불가 |

---

## 4. 저장소 경로

| 경로 | 용도 | 정책 |
|------|------|------|
| `state/tickets/ticket_requests.jsonl` | 티켓 요청 | Append-only |
| `state/tickets/ticket_results.jsonl` | 처리 결과 | Append-only |

> 🚫 **Append-only**: 수정/삭제 금지.

---

## 5. API Endpoints

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/tickets/consume` | OPEN → IN_PROGRESS |
| POST | `/api/tickets/complete` | IN_PROGRESS → DONE/FAILED |
| GET | `/api/tickets/latest` | 상태 보드 조회 |

---

## 6. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-P.2) |
