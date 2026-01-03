# Contract: Ticket Idempotency V1

**Version**: 1.0
**Date**: 2026-01-03
**Status**: LOCKED

---

## 1. 개요

Ticket Idempotency는 **중복 티켓 처리를 방지**하는 규칙입니다.

> 🔒 **Enforcement Point**: Backend API의 `consume` 단계에서 강제됨

---

## 2. 핵심 규칙

| 규칙 | 설명 |
|------|------|
| **Terminal State 단일성** | Request ID당 1개의 Terminal State(`DONE`/`FAILED`)만 허용 |
| **Enforcement** | `POST /api/tickets/consume`에서 409 Conflict로 강제 |

---

## 3. 상태 전이 다이어그램

```
           ┌──────────[중복 consume]──────────┐
           │                                  │
           ▼                                  │
        ┌──────┐    consume     ┌─────────────┴─┐    complete    ┌──────┐
[NEW]──►│ OPEN │──────────────►│ IN_PROGRESS   │──────────────►│ DONE │
        └──────┘                └───────────────┘                └──────┘
           │                          │                            │
           │                          │                            │
           X (불가)                   X (불가)                     X (불가)
```

---

## 4. 409 Conflict 발생 조건

| Endpoint | 조건 | 응답 |
|----------|------|------|
| `POST /api/tickets/consume` | `current_status != OPEN` | 409 Conflict |
| `POST /api/tickets/complete` | `current_status != IN_PROGRESS` | 409 Conflict |

---

## 5. Idempotency Authority

| 권한 | 위치 |
|------|------|
| **최종 권한** | Backend API (`consume` 409 응답) |
| 보조 체크 | Worker 로컬 파일 확인 (힌트용) |

> ⚠️ **중요**: 파일 확인은 힌트일 뿐, 최종 권한은 Backend API에 있습니다.

---

## 6. Worker 동작

| API 응답 | Worker 동작 |
|----------|-------------|
| 200 OK | 처리 진행 |
| 409 Conflict | `SKIP_AND_CONTINUE` (로그 남기고 다음 티켓) |

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-P.4) |
