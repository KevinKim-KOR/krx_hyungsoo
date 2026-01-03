# Phase C-P.2: Ticket Status Board

**Date**: 2026-01-03
**Status**: ✅ 완료

---

## 📋 목표

C-P.1에서 발행된 티켓이 실제로 "처리 상태"를 갖도록 백엔드(소비 및 조회 로직)와 UI(상태 보드)를 구현.

---

## 📁 생성된 문서/파일

| 타입 | 경로 | 설명 |
|------|------|------|
| Contract | `docs/contracts/contract_ticket_result_v1.md` | TICKET_RESULT_V1, TICKETS_BOARD_V1 스키마 |
| Data | `state/tickets/ticket_results.jsonl` | 처리 결과 로그 (Append-only) |

---

## 🔌 새 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/tickets/consume` | OPEN → IN_PROGRESS |
| POST | `/api/tickets/complete` | IN_PROGRESS → DONE/FAILED |
| GET | `/api/tickets/latest` | 티켓 상태 보드 (TICKETS_BOARD_V1) |

---

## 🔄 State Machine

```
OPEN → IN_PROGRESS → DONE
             │
             └→ FAILED
```

| 전이 | 조건 |
|------|------|
| OPEN → IN_PROGRESS | consume 호출 |
| IN_PROGRESS → DONE | complete(DONE) |
| IN_PROGRESS → FAILED | complete(FAILED) |
| DONE/FAILED → * | ❌ 불가 |

---

## 🖥️ Dashboard 변경

- **[Tickets]** 탭 추가
- Table View (Requested At / Type / Trace ID / Status Badge / Message)
- Status Badges: OPEN(Gray), IN_PROGRESS(Blue), DONE(Green), FAILED(Red)

---

## ✅ 검증 결과

| 항목 | 결과 |
|------|------|
| OPEN → IN_PROGRESS | ✅ HTTP 200 |
| 중복 consume | ✅ HTTP 409 (Idempotency) |
| IN_PROGRESS → DONE | ✅ HTTP 200 |
| 상태 보드 조회 | ✅ Envelope 포맷 |
| Lint | ✅ PASS |

---

## 🚀 다음 단계

**C-P.3**: Push Notifier 연동
