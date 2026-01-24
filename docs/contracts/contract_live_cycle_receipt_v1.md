# Contract: Live Cycle Receipt V1

**Version**: 1.0
**Date**: 2026-01-24
**Status**: LOCKED

---

## 1. 개요

OCI에서 단일 실행으로 Bundle→Reco→Summary→(Console)Send를 처리하고 결과를 영수증으로 남깁니다.

> 🔒 **Fail-Closed**: 중간 실패 시에도 영수증 저장 + result=FAILED
> 
> 🔒 **Console Only**: 외부 발송 금지 (delivery_actual=CONSOLE_SIMULATED)
> 
> 🔒 **RAW_PATH_ONLY**: evidence_refs는 raw 경로만 허용

---

## 2. Schema: LIVE_CYCLE_RECEIPT_V1

```json
{
  "schema": "LIVE_CYCLE_RECEIPT_V1",
  "cycle_id": "uuid-v4",
  "asof": "2026-01-24T19:00:00+09:00",
  "result": "OK | FAILED",
  "decision": "COMPLETED | PARTIAL | BLOCKED",
  "reason": "SUCCESS | BUNDLE_FAIL | RECO_FAIL | SUMMARY_FAIL | PUSH_FAIL",
  "bundle": {
    "latest_ref": "state/strategy_bundle/latest/strategy_bundle_latest.json",
    "decision": "PASS | WARN | FAIL | NO_BUNDLE",
    "stale": false,
    "valid": true,
    "evidence_refs": ["state/strategy_bundle/latest/strategy_bundle_latest.json"]
  },
  "reco": {
    "latest_ref": "reports/live/reco/latest/reco_latest.json",
    "snapshot_ref": "reports/live/reco/snapshots/reco_YYYYMMDD_HHMMSS.json",
    "decision": "GENERATED | EMPTY_RECO | BLOCKED",
    "reason": "SUCCESS | NO_BUNDLE | BUNDLE_FAIL | BUNDLE_STALE",
    "evidence_refs": ["reports/live/reco/latest/reco_latest.json"]
  },
  "ops_summary": {
    "latest_ref": "reports/ops/summary/ops_summary_latest.json",
    "snapshot_ref": "reports/ops/summary/snapshots/ops_summary_YYYYMMDD_HHMMSS.json"
  },
  "push": {
    "preview_ref": "reports/ops/push/preview/preview_latest.json",
    "send_receipt_ref": null,
    "delivery_actual": "CONSOLE_SIMULATED"
  },
  "snapshot_ref": "reports/live/cycle/snapshots/live_cycle_YYYYMMDD_HHMMSS.json",
  "evidence_refs": [
    "reports/live/cycle/latest/live_cycle_latest.json"
  ],
  "integrity": {
    "payload_sha256": "sha256-of-results-section"
  }
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `schema` | string | ✓ | "LIVE_CYCLE_RECEIPT_V1" |
| `cycle_id` | UUID | ✓ | 고유 실행 식별자 |
| `asof` | ISO8601 | ✓ | 실행 시각 |
| `result` | enum | ✓ | OK, FAILED |
| `decision` | enum | ✓ | COMPLETED, PARTIAL, BLOCKED |
| `reason` | enum | ✓ | SUCCESS, BUNDLE_FAIL, RECO_FAIL, SUMMARY_FAIL, PUSH_FAIL |
| `bundle` | object | ✓ | 번들 로드/검증 결과 |
| `reco` | object | ✓ | 추천 생성 결과 |
| `ops_summary` | object | ✓ | Ops Summary 재생성 결과 |
| `push` | object | ✓ | Push 결과 (Console Only) |
| `snapshot_ref` | string | ✓ | 본 영수증의 스냅샷 경로 |
| `evidence_refs` | array | ✓ | 증거 참조 (최소 1개) |
| `integrity` | object | ✓ | 무결성 정보 |

---

## 4. Result/Decision 결정 규칙

| 상황 | result | decision | reason |
|------|--------|----------|--------|
| 전체 성공 | OK | COMPLETED | SUCCESS |
| Bundle FAIL 시 | FAILED | BLOCKED | BUNDLE_FAIL |
| Bundle STALE 시 | OK | PARTIAL | BUNDLE_STALE |
| Reco BLOCKED 시 | OK | PARTIAL | RECO_BLOCKED |
| Summary/Push 실패 | FAILED | PARTIAL | SUMMARY_FAIL/PUSH_FAIL |
| 시스템 예외 | FAILED | BLOCKED | SYSTEM_ERROR |

---

## 5. 저장소 경로

| 경로 | 용도 | 방식 |
|------|------|------|
| `reports/live/cycle/latest/live_cycle_latest.json` | 최신 영수증 | Atomic Write |
| `reports/live/cycle/snapshots/live_cycle_*.json` | 스냅샷 | 매 실행시 생성 |

---

## 6. 금지사항

> ⚠️ **Live Cycle 절대 금지**

- 외부 발송 (Telegram, Slack, Email)
- 실제 주문 실행
- `delivery_actual`에 `CONSOLE_SIMULATED` 외의 값

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-24 | 초기 버전 (Phase D-P.50) |
