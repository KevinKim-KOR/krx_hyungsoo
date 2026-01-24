# Contract: Reco Report V1

**Version**: 1.0
**Date**: 2026-01-24
**Status**: LOCKED

---

## 1. 개요

OCI에서 `STRATEGY_BUNDLE_V1`을 기반으로 생성되는 추천(Recommendation) 리포트 스키마를 정의합니다.

> 🔒 **Fail-Closed**: 번들 무결성 실패 시 EMPTY_RECO 생성
> 
> 🔒 **Read-Only**: 추천은 읽기 전용, 실제 주문 연동 금지
> 
> 🔒 **RAW_PATH_ONLY**: evidence_refs는 raw 경로만 허용

---

## 2. Schema: RECO_REPORT_V1

```json
{
  "schema": "RECO_REPORT_V1",
  "report_id": "uuid-v4",
  "created_at": "2026-01-24T10:00:00+09:00",
  "source_bundle": {
    "bundle_id": "uuid-v4",
    "strategy_name": "KRX_MOMENTUM_V1",
    "strategy_version": "1.0.0",
    "bundle_decision": "PASS"
  },
  "decision": "GENERATED | EMPTY_RECO | BLOCKED",
  "reason": "SUCCESS | NO_BUNDLE | BUNDLE_FAIL | BUNDLE_STALE | SYSTEM_ERROR",
  "recommendations": [
    {
      "ticker": "069500",
      "name": "KODEX 200",
      "action": "BUY | SELL | HOLD",
      "weight_pct": 0.25,
      "signal_score": 0.85,
      "rationale": "20일 모멘텀 상위, ADX > 25"
    }
  ],
  "summary": {
    "total_positions": 3,
    "buy_count": 2,
    "sell_count": 1,
    "hold_count": 0,
    "cash_pct": 0.10
  },
  "constraints_applied": {
    "max_position_pct": 0.25,
    "max_positions": 4,
    "min_cash_pct": 0.10
  },
  "evidence_refs": [
    "state/strategy_bundle/latest/strategy_bundle_latest.json",
    "reports/live/reco/latest/reco_latest.json"
  ],
  "integrity": {
    "payload_sha256": "sha256-of-recommendations-section"
  }
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `schema` | string | ✓ | "RECO_REPORT_V1" |
| `report_id` | UUID | ✓ | 고유 식별자 |
| `created_at` | ISO8601 | ✓ | 생성 시각 (KST) |
| `source_bundle` | object | ✓ | 소스 번들 정보 |
| `source_bundle.bundle_id` | UUID | ✓ | 번들 ID |
| `source_bundle.strategy_name` | string | ✓ | 전략 이름 |
| `source_bundle.strategy_version` | string | ✓ | 전략 버전 |
| `source_bundle.bundle_decision` | string | ✓ | 번들 검증 결과 |
| `decision` | string | ✓ | GENERATED, EMPTY_RECO, BLOCKED |
| `reason` | string | ✓ | 상태 사유 |
| `recommendations` | array | ✓ | 추천 목록 (EMPTY_RECO 시 빈 배열) |
| `summary` | object | ✓ | 추천 요약 |
| `constraints_applied` | object | ✓ | 적용된 제약조건 |
| `evidence_refs` | array | ✓ | 증거 참조 경로 (RAW_PATH_ONLY) |
| `integrity` | object | ✓ | 무결성 정보 |

---

## 4. Decision 결정 규칙

| 조건 | decision | reason |
|------|----------|--------|
| 번들 없음 | EMPTY_RECO | NO_BUNDLE |
| 번들 FAIL | BLOCKED | BUNDLE_FAIL |
| 번들 STALE (24h+) | EMPTY_RECO | BUNDLE_STALE |
| 번들 PASS/WARN + 추천 생성 성공 | GENERATED | SUCCESS |
| 시스템 오류 | BLOCKED | SYSTEM_ERROR |

---

## 5. 저장소 경로

| 경로 | 용도 | 방식 |
|------|------|------|
| `reports/live/reco/latest/reco_latest.json` | 최신 추천 리포트 | Atomic Write |
| `reports/live/reco/snapshots/*.json` | 스냅샷 | Append-only |

---

## 6. Recommendations 항목 스키마

```json
{
  "ticker": "string (종목코드)",
  "name": "string (종목명)",
  "action": "BUY | SELL | HOLD",
  "weight_pct": "number (0.0 ~ 1.0)",
  "signal_score": "number (-1.0 ~ 1.0)",
  "rationale": "string (추천 사유)"
}
```

---

## 7. EMPTY_RECO 상태 예시

번들 없음 또는 STALE 시:

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
  "evidence_refs": [],
  "integrity": {
    "payload_sha256": "e3b0c44..."
  }
}
```

---

## 8. 금지사항

> ⚠️ **추천 리포트 절대 금지**

- 실제 주문 연동
- 외부 전송 (텔레그램, 슬랙, 이메일)
- 실시간 가격 데이터 (추천은 전략 파라미터 기반)

---

## 9. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-24 | 초기 버전 (Phase D-P.48) |
