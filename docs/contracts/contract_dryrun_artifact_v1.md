# Contract: Dry-Run Artifact V1

**Version**: 1.0
**Date**: 2026-01-03
**Status**: LOCKED

---

## 1. 개요

Dry-Run Artifact는 **실행 전 검증 결과를 기록**하는 표준화된 리포트입니다.

> 🚫 **No Real Execution**: 실제 엔진 실행 없이 검증만 수행합니다.

---

## 2. 스키마 정의

### DRYRUN_ARTIFACT_V1

```json
{
  "schema": "DRYRUN_ARTIFACT_V1",
  "asof": "2026-01-03T16:30:00+09:00",
  "request_id": "uuid",
  "request_type": "REQUEST_RECONCILE",
  "valid": true,
  "plan_ref": ["python", "-m", "app.reconcile"],
  "checks": {
    "plan_exists": true,
    "module_exists": true,
    "python_available": true
  },
  "errors": []
}
```

| Key | Type | 필수 | 설명 |
|-----|------|------|------|
| `schema` | string | ✅ | 고정: "DRYRUN_ARTIFACT_V1" |
| `asof` | ISO8601 | ✅ | 검증 시각 |
| `request_id` | UUID | ✅ | 원본 티켓 ID |
| `request_type` | string | ✅ | 티켓 타입 |
| `valid` | boolean | ✅ | 모든 검증 통과 여부 |
| `plan_ref` | array | ✅ | 실행 계획 Command 배열 |
| `checks` | object | ✅ | 개별 검증 항목 결과 |
| `errors` | array | ✅ | 실패 시 오류 메시지 목록 |

---

## 3. Checks 필드

| Check Key | 설명 |
|-----------|------|
| `plan_exists` | execution_plan_v1.json에 해당 request_type이 존재함 |
| `module_exists` | target module 파일이 파일시스템에 존재함 |
| `python_available` | Python 인터프리터 사용 가능 |

---

## 4. 저장 경로

| 경로 | 파일명 패턴 |
|------|-------------|
| `reports/tickets/dryrun/` | `{request_id}.json` |

---

## 5. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-P.5) |
