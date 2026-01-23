# Contract: Ticket Reaper V1

**Version**: 1.0
**Date**: 2026-01-23
**Status**: ACTIVE

---

## 1. 개요

오래된 `IN_PROGRESS` 상태의 티켓(stale)을 자동으로 정리하여 Ops 카운터 왜곡과 처리 흐름 방해를 방지합니다.

> ⚠️ **청소 대상**: `IN_PROGRESS` 상태이면서 `last_processed_at`이 임계치(기본 24시간)를 초과한 티켓만
>
> ⚠️ **종료 상태**: `DONE`이 아닌 `FAILED`로 종료 (감사/안전상 유리)

---

## 2. Schema: TICKET_REAPER_REPORT_V1

```json
{
  "schema": "TICKET_REAPER_REPORT_V1",
  "asof": "2026-01-23T21:00:00+09:00",
  "decision": "NONE | CLEANED",
  "threshold_seconds": 86400,
  "stale_count": 1,
  "cleaned_count": 1,
  "cleaned_items": [
    {
      "request_id": "fd4888b3-...",
      "request_type": "EXECUTION_ENABLE",
      "last_processed_at": "2026-01-22T10:00:00+09:00",
      "reason": "AUTO_CLEANUP_STALE_IN_PROGRESS"
    }
  ],
  "evidence_refs": [
    "reports/ops/tickets/reaper/snapshots/reaper_20260123_210000.json"
  ]
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema` | string | `TICKET_REAPER_REPORT_V1` 고정 |
| `asof` | ISO datetime | 실행 시점 |
| `decision` | enum | `NONE` (정리할 것 없음) / `CLEANED` (정리 수행) |
| `threshold_seconds` | int | stale 판정 임계치 (기본 86400 = 24시간) |
| `stale_count` | int | stale 후보 개수 |
| `cleaned_count` | int | 실제 정리된 개수 |
| `cleaned_items` | array | 정리된 티켓 목록 |
| `evidence_refs` | array | RAW_PATH_ONLY 형식 증거 경로 |

### cleaned_items 항목

| 필드 | 타입 | 설명 |
|------|------|------|
| `request_id` | string | 티켓 ID |
| `request_type` | string | 티켓 유형 |
| `last_processed_at` | ISO datetime | 마지막 처리 시점 |
| `reason` | string | `AUTO_CLEANUP_STALE_IN_PROGRESS` |

---

## 4. 정리 규칙

### 4-A. Stale 판정 조건

티켓이 stale로 판정되려면 **모든 조건 충족**:

1. `current_status == IN_PROGRESS`
2. `last_processed_at`이 `now() - threshold_seconds`보다 이전
3. (선택) `request_type`이 특정 유형 제외

### 4-B. 정리 시 생성되는 TicketResult

```json
{
  "request_id": "...",
  "processor_id": "TICKET_REAPER",
  "status": "FAILED",
  "processed_at": "2026-01-23T21:00:00+09:00",
  "message": "AUTO_CLEANUP_STALE_IN_PROGRESS: exceeded 86400s threshold"
}
```

---

## 5. API

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/tickets/reaper/latest` | 최신 리포트 조회 |
| POST | `/api/tickets/reaper/run` | 수동 실행 |

### POST 요청 body (optional)

```json
{
  "threshold_seconds": 86400,
  "max_clean": 50
}
```

---

## 6. 아티팩트 경로

| 경로 | 설명 |
|------|------|
| `reports/ops/tickets/reaper/latest/reaper_latest.json` | 최신 리포트 |
| `reports/ops/tickets/reaper/snapshots/reaper_YYYYMMDD_HHMMSS.json` | 스냅샷 |

---

## 7. Ops Cycle 연동

Ops Cycle에서 **Step 0.25**로 실행:

1. Emergency Stop 확인 직후
2. 티켓 선택 전에 reaper 실행
3. 결과를 `ops_run_receipt.ticket_reaper`에 기록

---

## 8. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-23 | 초기 버전 (Phase C-P.43) |
