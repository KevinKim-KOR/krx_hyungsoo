# Contract: Evidence Health Report V1

**Version**: 1.0
**Date**: 2026-01-11
**Status**: LOCKED

---

## 1. 개요

Evidence Health Check 결과 리포트 스키마를 정의합니다.

> 🔒 **Validator Single Source**: ref 검증은 공용 모듈(`ref_validator.py`)만 사용

---

## 2. Schema: EVIDENCE_HEALTH_REPORT_V1

```json
{
  "schema": "EVIDENCE_HEALTH_REPORT_V1",
  "asof": "2026-01-11T00:00:00",
  "period": {
    "from": "2026-01-04T00:00:00",
    "to": "2026-01-11T00:00:00"
  },
  "summary": {
    "total": 10,
    "pass": 8,
    "warn": 1,
    "fail": 1,
    "decision": "WARN"
  },
  "checks": [
    {
      "name": "ticket_receipts_resolvable",
      "decision": "PASS",
      "reason": "98.5% resolvable (49/50)",
      "stats": { "total": 50, "ok": 49, "fail": 1 }
    }
  ],
  "top_fail_reasons": [
    { "reason": "NOT_FOUND", "count": 3 },
    { "reason": "INVALID_REF", "count": 1 }
  ]
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema` | string | `EVIDENCE_HEALTH_REPORT_V1` |
| `asof` | ISO8601 | 리포트 생성 시각 |
| `period` | object | 검사 기간 |
| `period.from` | ISO8601 | 시작 시각 |
| `period.to` | ISO8601 | 종료 시각 |
| `summary` | object | 요약 통계 |
| `summary.total` | int | 총 체크 수 |
| `summary.pass` | int | PASS 수 |
| `summary.warn` | int | WARN 수 |
| `summary.fail` | int | FAIL 수 |
| `summary.decision` | enum | 최종 결정 (PASS/WARN/FAIL) |
| `checks` | array | 개별 체크 항목 |
| `checks[].name` | string | 체크 이름 |
| `checks[].decision` | enum | PASS/WARN/FAIL |
| `checks[].reason` | string | 사유 |
| `checks[].stats` | object | 통계 |
| `top_fail_reasons` | array | 상위 실패 사유 |

---

## 4. 저장소 경로

| 경로 | 용도 | 방식 |
|------|------|------|
| `reports/ops/evidence/health/health_latest.json` | 최신 리포트 | Atomic Write |
| `reports/ops/evidence/health/snapshots/*.json` | 스냅샷 | Append-only |

---

## 5. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-11 | 초기 버전 (Phase C-P.33) |
