# Contract: Ticket Request V1

**Version**: 1.0
**Date**: 2026-01-03
**Status**: LOCKED

---

## 1. 개요

티켓 시스템은 **운영자 요청을 기록**하는 시스템입니다.

> 🚫 **No Execution 원칙**: 티켓 생성은 **실행을 트리거하지 않습니다**. 오직 파일에 기록만 합니다.
> - subprocess 호출 금지
> - reconcile/report 로직 실행 금지
> - 파일 읽기/생성/Append만 허용

---

## 2. 스키마 정의

### 2-A. TICKET_SUBMIT_V1 (입력용 - UI → Backend)

UI가 Backend로 전송하는 페이로드입니다.

```json
{
  "schema": "TICKET_SUBMIT_V1",
  "request_type": "REQUEST_RECONCILE | REQUEST_REPORTS | ACKNOWLEDGE",
  "payload": { ... },
  "trace_id": "optional-trace-id"
}
```

| Key | Type | 필수 | 설명 |
|-----|------|------|------|
| `request_type` | enum | ✅ | 요청 타입 |
| `payload` | object | ✅ | 타입별 페이로드 |
| `trace_id` | string | ⚠️ | 추적용 ID (Optional) |

---

### 2-B. TICKET_REQUEST_V1 (저장용 - Backend → Storage)

Backend가 서버 정보를 주입하여 저장하는 스키마입니다.

```json
{
  "schema": "TICKET_REQUEST_V1",
  "request_id": "uuid-server-generated",
  "requested_at": "2026-01-03T14:20:00+09:00",
  "request_type": "REQUEST_RECONCILE",
  "payload": { ... },
  "status": "OPEN",
  "trace_id": "optional-trace-id"
}
```

| Key | Type | 필수 | 생성 주체 | 설명 |
|-----|------|------|-----------|------|
| `request_id` | UUID | ✅ | **Server** | 고유 식별자 |
| `requested_at` | ISO8601 | ✅ | **Server** | 요청 시각 |
| `request_type` | enum | ✅ | Client | 요청 타입 |
| `payload` | object | ✅ | Client | 타입별 페이로드 |
| `status` | enum | ✅ | **Server** | 상태 (최초 `OPEN` 고정) |
| `trace_id` | string | ⚠️ | Client | 추적용 ID |

### Status Enum

| Status | 설명 |
|--------|------|
| `OPEN` | 대기 중 (최초 고정) |
| `IN_PROGRESS` | 처리 중 |
| `DONE` | 완료 |
| `FAILED` | 실패 |

---

## 3. Payload Constraints (타입별)

### REQUEST_RECONCILE

```json
{
  "mode": "FULL | INCREMENTAL",
  "reason": "사유 설명"
}
```

| Key | Type | 필수 | 값 |
|-----|------|------|-----|
| `mode` | enum | ✅ | `FULL` 또는 `INCREMENTAL` |
| `reason` | string | ✅ | 사유 (최대 200자) |

### REQUEST_REPORTS

```json
{
  "mode": "RE-EVALUATE | REGEN",
  "scope": "PHASE_C_LATEST",
  "reason": "사유 설명"
}
```

| Key | Type | 필수 | 값 |
|-----|------|------|-----|
| `mode` | enum | ✅ | `RE-EVALUATE` 또는 `REGEN` |
| `scope` | string | ✅ | 고정: `PHASE_C_LATEST` |
| `reason` | string | ✅ | 사유 (최대 200자) |

### ACKNOWLEDGE

```json
{
  "message_id": "push_20260103_143000_001"
}
```

| Key | Type | 필수 | 설명 |
|-----|------|------|------|
| `message_id` | string | ✅ | 확인할 Push Message ID |

---

## 4. 저장소 경로

| 경로 | 용도 | 정책 |
|------|------|------|
| `state/tickets/ticket_requests.jsonl` | 티켓 저장 | **Append-only** |

> 🚫 **Append-only**: 수정/삭제 금지. 새 티켓은 항상 파일 끝에 추가됩니다.

---

## 5. Backend 동작 흐름

```
1. UI: TICKET_SUBMIT_V1 전송
2. Backend: 유효성 검증
3. Backend: 서버 정보 강제 주입
   - request_id: UUID 생성
   - requested_at: 서버 시간
   - status: "OPEN" 고정
4. Backend: TICKET_REQUEST_V1로 변환
5. Backend: state/tickets/ticket_requests.jsonl에 Append
6. Backend: { "result": "OK", "request_id": "..." } 응답
```

---

## 6. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-P.1) |
