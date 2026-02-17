# Contract: Ops Summary V1

**Version**: 1.0
**Date**: 2026-01-11
**Status**: LOCKED

---

## 1. 개요

운영자가 단일 API/UI로 시스템 전체 상태를 파악할 수 있도록 통합 요약을 정의합니다.

> 🔒 **Single Pane of Glass**: 1개 API + 1개 UI 카드로 오늘 상태 판단
> 
> 🔒 **RAW_PATH_ONLY**: 모든 evidence ref는 접두어 없이 raw path

---

## 2. Schema: OPS_SUMMARY_V1

```json
{
  "schema": "OPS_SUMMARY_V1",
  "asof": "2026-01-11T09:00:00",
  "overall_status": "OK",
  "guard": {
    "evidence_health": {
      "decision": "PASS",
      "fail_closed_triggered": false,
      "snapshot_ref": "reports/ops/evidence/health/snapshots/health_20260111.json"
    },
    "emergency_stop": { "enabled": false },
    "execution_gate": { "mode": "DRY_RUN" }
  },
  "last_run_triplet": {
    "last_done": "2026-01-11T08:30:00",
    "last_failed": null,
    "last_blocked": null
  },
  "tickets": {
    "open": 2,
    "in_progress": 0,
    "done": 15,
    "failed": 1,
    "blocked": 0
  },
  "tickets_recent": {
    "window_days": 3,
    "max_events": 200,
    "start_at": "2026-01-08T09:00:00",
    "end_at": "2026-01-11T09:00:00",
    "failed": 0,
    "excluded_cleanup_failed": 1,
    "blocked": 0,
    "done": 5,
    "in_progress": 0,
    "failed_line_refs": []
  },
  "push": {
    "outbox_row_count": 3,
    "last_send_decision": "READY",
    "sender_enabled": false
  },
  "evidence": {
    "index_row_count": 25,
    "health_decision": "PASS"
  },
  "strategy_bundle": {
    "present": true,
    "decision": "PASS",
    "latest_ref": "state/strategy_bundle/latest/strategy_bundle_latest.json",
    "bundle_id": "uuid",
    "created_at": "2026-01-24T10:00:00",
    "strategy_name": "KRX_MOMENTUM_V1",
    "strategy_version": "1.0.0",
    "stale": false
  },
  "reco": {
    "present": true,
    "decision": "GENERATED | EMPTY_RECO | BLOCKED | NO_RECO_YET",
    "reason": "SUCCESS | NO_BUNDLE | BUNDLE_FAIL | BUNDLE_STALE | SYSTEM_ERROR",
    "latest_ref": "reports/live/reco/latest/reco_latest.json",
    "snapshot_ref": "reports/live/reco/snapshots/reco_20260124_110000.json",
    "report_id": "uuid",
    "created_at": "2026-01-24T11:00:00",
    "source_bundle": { "bundle_id": "...", "strategy_name": "...", "strategy_version": "..." },
    "summary": {
      "total_positions": 3,
      "buy_count": 2,
      "sell_count": 1,
      "hold_count": 0,
      "cash_pct": 0.25
    },
    "evidence_refs": ["reports/live/reco/latest/reco_latest.json"]
  },
  "top_risks": [
    {
      "code": "EVIDENCE_HEALTH_WARN",
      "severity": "WARN",
      "message": "1 check has warning",
      "evidence_refs": ["reports/ops/evidence/health/latest/health_latest.json"]
    }
  ]
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema` | string | OPS_SUMMARY_V1 |
| `asof` | ISO8601 | 생성 시각 |
| `overall_status` | enum | OK/WARN/BLOCKED/STOPPED/NO_RUN_HISTORY |
| `guard` | object | Guard 상태 |
| `guard.evidence_health` | object | Evidence Health 상태 |
| `guard.emergency_stop` | object | Emergency Stop 상태 |
| `guard.execution_gate` | object | Execution Gate 상태 |
| `last_run_triplet` | object | 마지막 실행 정보 |
| `tickets` | object | 티켓 요약 카운터 (누적) |
| `tickets_recent` | object | Risk Window 내 티켓 요약 (D-P.52) |
| `tickets_recent.window_days` | int | 적용된 윈도우 일수 (기본: 3) |
| `tickets_recent.failed` | int | 위험 창 내 FAILED (cleanup 제외) |
| `tickets_recent.excluded_cleanup_failed` | int | 제외된 cleanup FAILED |
| `tickets_recent.failed_line_refs` | array | 최근 실패 라인 참조 (최대 5개) |
| `push` | object | Push 요약 |
| `evidence` | object | Evidence 요약 |
| `top_risks` | array | 상위 위험 (max 5) |

---

## 4. Overall Status 결정 규칙

| 우선순위 | 조건 | 결과 |
|----------|------|------|
| 1 | `emergency_stop.enabled == true` | STOPPED |
| 2 | `evidence_health.decision == FAIL` | BLOCKED |
| 3 | `evidence_health.decision == WARN` | WARN |
| 4 | `ops_run_latest` 없음 | NO_RUN_HISTORY |
| 5 | 그 외 | OK |

---

## 5. 저장소 경로

| 경로 | 용도 | 방식 |
|------|------|------|
| `reports/ops/summary/latest/ops_summary_latest.json` | 최신 요약 | Atomic Write |
| `reports/ops/summary/snapshots/*.json` | 스냅샷 | Append-only |

---

## 6. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-11 | 초기 버전 (Phase C-P.35) |
| 1.1 | 2026-01-24 | Risk Window 추가 (D-P.52): `tickets_recent` 섹션, cleanup 제외 |
