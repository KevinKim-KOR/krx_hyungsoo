# Contract: Evidence SLO V1

**Version**: 1.0
**Date**: 2026-01-11
**Status**: LOCKED

---

## 1. 개요

Evidence 시스템의 Service Level Objectives를 정의합니다.

> 🔒 **No Execution**: 검사 + 리포트 생성만 허용
> 
> 🔒 **RAW_PATH_ONLY**: 접두어 금지 (`json:`, `file://` 등)

---

## 2. Schema: EVIDENCE_SLO_V1

```json
{
  "schema": "EVIDENCE_SLO_V1",
  "window_days": 7,
  "min_resolvable_rate": 0.98,
  "min_required_refs_per_receipt": 1,
  "targets": [
    "ticket_receipts",
    "send_latest",
    "postmortem_latest",
    "evidence_index_latest"
  ]
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema` | string | `EVIDENCE_SLO_V1` |
| `window_days` | int | 검사 윈도우 (일) |
| `min_resolvable_rate` | float | 최소 해석 가능 비율 (0.0~1.0) |
| `min_required_refs_per_receipt` | int | 영수증당 최소 refs 개수 |
| `targets` | string[] | 검사 대상 목록 |

---

## 4. SLO 임계값

| 지표 | 기본값 | PASS | WARN | FAIL |
|------|--------|------|------|------|
| `resolvable_rate` | 0.98 | ≥ 0.98 | 0.90~0.98 | < 0.90 |
| `refs_per_receipt` | 1 | ≥ 1 | 0 | N/A |
| `target_exists` | - | true | - | false |

---

## 5. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-11 | 초기 버전 (Phase C-P.33) |
