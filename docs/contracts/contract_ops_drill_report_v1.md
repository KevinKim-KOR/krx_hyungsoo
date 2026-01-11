# Contract: Ops Drill Report V1

**Version**: 1.0
**Date**: 2026-01-11
**Status**: LOCKED

---

## 1. 개요

전체 운영 파이프라인(Health → Cycle → Summary → Send)의 End-to-End 건전성을 증명하는 드릴 리포트 스키마입니다.

> 🔒 **No External Send**: 드릴 실행 시 외부 발송 절대 금지
> 
> 🔒 **Force Console**: 내부 함수 호출로 콘솔 모드 강제
> 
> 🔒 **RAW_PATH_ONLY**: 모든 evidence ref는 접두어 없는 raw path

---

## 2. Schema: OPS_DRILL_REPORT_V1

```json
{
  "schema": "OPS_DRILL_REPORT_V1",
  "asof": "2026-01-11T17:00:00",
  "run_id": "uuid",
  "inputs_observed": {
    "gate_mode": "DRY_RUN",
    "emergency_stop_enabled": false,
    "sender_enabled": false,
    "self_test_passed": true
  },
  "steps": [
    {
      "name": "evidence_health",
      "result": "PASS",
      "decision_observed": "WARN",
      "elapsed_ms": 150
    },
    {
      "name": "ops_cycle",
      "result": "PASS",
      "overall_status": "DONE",
      "elapsed_ms": 500
    },
    {
      "name": "ops_summary",
      "result": "PASS",
      "snapshot_ref": "reports/ops/summary/snapshots/ops_summary_20260111_170000.json"
    },
    {
      "name": "outbox_preview",
      "result": "PASS",
      "message_count": 3
    },
    {
      "name": "send_console",
      "result": "PASS",
      "delivery_actual": "CONSOLE",
      "console_output_lines": 3
    },
    {
      "name": "resolver_proof",
      "result": "PASS",
      "tested_ref": "reports/ops/summary/ops_summary_latest.json",
      "http_status": 200
    }
  ],
  "overall_result": "PASS",
  "top_fail_reasons": [],
  "evidence_refs": [
    "reports/ops/drill/snapshots/drill_20260111_170000.json",
    "reports/ops/summary/ops_summary_latest.json"
  ]
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema` | string | OPS_DRILL_REPORT_V1 |
| `asof` | ISO8601 | 드릴 실행 시각 |
| `run_id` | UUID | 드릴 실행 고유 ID |
| `inputs_observed` | object | 드릴 시점의 시스템 상태 |
| `steps[]` | array | 각 단계 결과 |
| `steps[].name` | string | 단계 이름 |
| `steps[].result` | string | PASS/WARN/FAIL/SKIPPED |
| `overall_result` | string | PASS/WARN/FAIL |
| `top_fail_reasons` | array | 실패 사유 (max 5) |
| `evidence_refs` | array | RAW_PATH_ONLY 증거 참조 |

---

## 4. Overall Result 결정 규칙

| 조건 | 결과 |
|------|------|
| 모든 steps가 PASS | PASS |
| 1개 이상 WARN (FAIL 없음) | WARN |
| 1개 이상 FAIL | FAIL |
| 예외 발생 시 | FAIL (Fail-Closed) |

---

## 5. 저장소 경로

| 경로 | 용도 | 방식 |
|------|------|------|
| `reports/ops/drill/latest/drill_latest.json` | 최신 드릴 리포트 | Atomic Write |
| `reports/ops/drill/snapshots/*.json` | 스냅샷 | Append-only |

---

## 6. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-11 | 초기 버전 (Phase C-P.37) |
