# Contract: Daily Ops Report V1

**Version**: 1.0
**Date**: 2026-01-04
**Status**: LOCKED

---

## 1. 개요

일일 운영 리포트 스키마를 정의합니다. 티켓 처리 현황을 집계하여 운영 KPI로 제공합니다.

---

## 2. 스키마 정의

### DAILY_OPS_REPORT_V1

```json
{
  "schema": "DAILY_OPS_REPORT_V1",
  "asof": "2026-01-04T12:00:00",
  "period": "2026-01-04",
  "summary": {
    "tickets_total": 10,
    "done": 5,
    "failed": 2,
    "blocked": 3
  },
  "blocked_reasons_top": [
    {"reason": "Window not ACTIVE", "count": 2},
    {"reason": "Approval not APPROVED", "count": 1}
  ],
  "last_real_execution": {
    "request_id": "uuid",
    "request_type": "REQUEST_REPORTS",
    "exit_code": 0,
    "acceptance_pass": true
  },
  "artifacts_written": [
    "reports/phase_c/latest/report_human.json",
    "reports/phase_c/latest/report_ai.json"
  ]
}
```

---

## 3. 저장 경로

| 파일 | 설명 |
|------|------|
| `reports/ops/daily/ops_report_latest.json` | 최신 일일 리포트 (overwrite) |
| `reports/ops/daily/snapshots/ops_report_YYYYMMDD.json` | 날짜별 스냅샷 (append 성격) |

---

## 4. 갱신 규칙

- Worker가 티켓 처리 완료 후 자동 갱신
- 근거 데이터:
  - `state/tickets/ticket_requests.jsonl`
  - `state/tickets/ticket_results.jsonl`
  - `state/tickets/ticket_receipts.jsonl`

---

## 5. blocked_reasons_top 집계 규칙

- 오늘 날짜의 Receipt V3 중 `decision == BLOCKED`인 항목에서 `acceptance.reason` 또는 `block_reasons` 집계
- 상위 3개만 표시

---

## 6. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-04 | 초기 버전 (Phase C-P.13) |
