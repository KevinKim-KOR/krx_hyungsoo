# Contract: Reco Report V1

**Version**: 1.1
**Date**: 2026-01-24
**Status**: LOCKED

---

## 1. 개요

OCI에서 `STRATEGY_BUNDLE_V1`을 기반으로 생성되는 추천(Recommendation) 리포트 스키마를 정의합니다.

> 🔒 **Fail-Closed**: 번들 무결성 실패 시 BLOCKED 생성
> 
> 🔒 **Read-Only**: 추천은 읽기 전용, 실제 주문 연동 금지
> 
> 🔒 **RAW_PATH_ONLY**: evidence_refs는 raw 경로만 허용 (접두어 금지)
> 
> 🔒 **Snapshot 필수**: 매 생성마다 스냅샷 자동 생성

---

## 2. Schema: RECO_REPORT_V1 (Report 본문)

```json
{
  "schema": "RECO_REPORT_V1",
  "report_id": "uuid-v4",
  "created_at": "2026-01-24T10:00:00+09:00",
  "source_bundle": {
    "bundle_id": "uuid-v4",
    "strategy_name": "KRX_MOMENTUM_V1",
    "strategy_version": "1.0.0",
    "latest_ref": "state/strategy_bundle/latest/strategy_bundle_latest.json",
    "created_at": "2026-01-24T09:50:00+09:00",
    "bundle_decision": "PASS",
    "integrity": {
      "payload_sha256": "..."
    }
  },
  "decision": "GENERATED | EMPTY_RECO | BLOCKED",
  "reason": "SUCCESS | NO_BUNDLE | BUNDLE_FAIL | BUNDLE_STALE | SYSTEM_ERROR",
  "top_picks": [...],
  "holding_actions": [...],
  "summary": {...},
  "constraints_applied": {...},
  "evidence_refs": ["reports/live/reco/latest/reco_latest.json"],
  "integrity": {
    "payload_sha256": "sha256-of-recommendations-section"
  }
}
```

> **Note**: `source_bundle`은 `NO_BUNDLE` 상태일 때 `null` 가능

---

## 3. API Envelope: GET /api/reco/latest

```json
{
  "schema": "RECO_REPORT_V1",
  "asof": "2026-01-24T10:00:00+09:00",
  "status": "ready | no_reco_yet | error",
  "report": { ...RECO_REPORT_V1... },
  "summary": {
    "present": true,
    "decision": "GENERATED",
    "reason": "SUCCESS",
    "latest_ref": "reports/live/reco/latest/reco_latest.json",
    "report_id": "uuid",
    "created_at": "2026-01-24T10:00:00",
    "source_bundle": {...},
    "summary": {...}
  },
  "snapshots": [
    {"filename": "reco_20260124_100000.json", "mtime": "...", "ref": "reports/live/reco/snapshots/reco_20260124_100000.json"}
  ],
  "error": null
}
```

---

## 4. 필드 정의

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `schema` | string | ✓ | "RECO_REPORT_V1" |
| `report_id` | UUID | ✓ | 고유 식별자 |
| `created_at` | ISO8601 | ✓ | 생성 시각 (KST) |
| `source_bundle` | object/null | ✓ | 소스 번들 정보 (NO_BUNDLE 시 null) |
| `decision` | enum | ✓ | GENERATED, EMPTY_RECO, BLOCKED |
| `reason` | enum | ✓ | SUCCESS, NO_BUNDLE, BUNDLE_FAIL, BUNDLE_STALE, SYSTEM_ERROR |
| `top_picks` | array | ✓ | 추천 종목 (bundle.scorer.top_picks) |
| `holding_actions` | array | ✓ | 보유 종목 액션 (bundle.holding_action.items) |
| `summary` | object | ✓ | 추천 요약 |
| `constraints_applied` | object/null | ✓ | 적용된 제약조건 |
| `evidence_refs` | array | ✓ | 증거 참조 경로 (RAW_PATH_ONLY, **최소 1개 필수**) |
| `integrity` | object | ✓ | 무결성 정보 |

---

## 5. Decision 결정 규칙

| 조건 | decision | reason |
|------|----------|--------|
| 번들 없음 | EMPTY_RECO | NO_BUNDLE |
| 번들 FAIL | BLOCKED | BUNDLE_FAIL |
| 번들 STALE (24h+) | EMPTY_RECO | BUNDLE_STALE |
| 번들 PASS/WARN + 추천 생성 성공 | GENERATED | SUCCESS |
| 시스템 오류 | BLOCKED | SYSTEM_ERROR |

---

## 6. 저장소 경로

| 경로 | 용도 | 방식 |
|------|------|------|
| `reports/live/reco/latest/reco_latest.json` | 최신 추천 리포트 | Atomic Write |
| `reports/live/reco/snapshots/reco_*.json` | 스냅샷 | 매 생성 시 자동 생성 |

---

## 7. evidence_refs 규칙

> ⚠️ **모든 상태에서 최소 1개의 evidence_ref 필수**

| decision | evidence_refs |
|----------|---------------|
| GENERATED | `["reports/live/reco/latest/reco_latest.json", "state/strategy_bundle/latest/strategy_bundle_latest.json"]` |
| EMPTY_RECO | `["reports/live/reco/latest/reco_latest.json"]` |
| BLOCKED | `["reports/live/reco/latest/reco_latest.json"]` |

---

## 8. EMPTY_RECO 상태 예시

```json
{
  "schema": "RECO_REPORT_V1",
  "report_id": "uuid",
  "created_at": "2026-01-24T10:00:00+09:00",
  "source_bundle": null,
  "decision": "EMPTY_RECO",
  "reason": "NO_BUNDLE",
  "recommendations": [],
  "summary": {
    "total_positions": 0,
    "buy_count": 0,
    "sell_count": 0,
    "hold_count": 0,
    "cash_pct": 1.0
  },
  "constraints_applied": null,
  "evidence_refs": ["reports/live/reco/latest/reco_latest.json"],
  "integrity": {
    "payload_sha256": "e3b0c44..."
  }
}
```

---

## 9. 금지사항

> ⚠️ **추천 리포트 절대 금지**

- 실제 주문 연동
- 외부 전송 (텔레그램, 슬랙, 이메일)
- 실시간 가격 데이터 (추천은 전략 파라미터 기반)
- `file://`, `http://`, `json:` 등 접두어 사용

---

## 10. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-24 | 초기 버전 (Phase D-P.48) |
| 1.1 | 2026-01-24 | API Envelope 추가, evidence_refs 필수화 (Phase D-P.48.1-REV) |

