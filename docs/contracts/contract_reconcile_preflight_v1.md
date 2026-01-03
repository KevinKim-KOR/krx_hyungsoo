# Contract: Reconcile Preflight V1

**Version**: 1.0
**Date**: 2026-01-03
**Status**: LOCKED

---

## 1. 개요

REAL 실행 직전의 Deep Preflight 체크리스트를 정의합니다.

> 🔒 **Fail-Closed**: 하나라도 실패 시 REAL 실행 금지

---

## 2. 스키마 정의

### RECONCILE_PREFLIGHT_V1

```json
{
  "schema": "RECONCILE_PREFLIGHT_V1",
  "asof": "ISO datetime",
  "request_id": "uuid",
  "checks": {
    "import_check": {"status": "PASS|FAIL", "detail": "..."},
    "input_ready_check": {"status": "PASS|FAIL", "detail": "..."},
    "output_writable_check": {"status": "PASS|FAIL", "detail": "..."},
    "allowlist_check": {"status": "PASS|FAIL", "detail": "..."},
    "gate_check": {"status": "PASS|FAIL", "detail": "..."}
  },
  "effective_plan": ["python", "-m", "app.reconcile"],
  "decision": "PREFLIGHT_PASS | PREFLIGHT_FAIL",
  "fail_reasons": []
}
```

---

## 3. 체크 항목

| Check | 설명 | FAIL 조건 |
|-------|------|-----------|
| `import_check` | pandas/pyarrow import 가능 | ImportError |
| `input_ready_check` | reconcile 입력 파일 존재 | 파일 없음 |
| `output_writable_check` | latest/ 디렉토리 쓰기 가능 | 권한 없음 |
| `allowlist_check` | execution_allowlist exact match | 불일치 |
| `gate_check` | gate + estop + window 상태 | 조건 불충족 |

---

## 4. Artifact 저장

| 경로 | 파일명 |
|------|--------|
| `reports/tickets/preflight/` | `{request_id}.json` |

---

## 5. 실패 정책

```
IF any check.status == FAIL:
    decision = PREFLIGHT_FAIL
    REAL execution = BLOCKED
    receipt.status = FAILED
```

---

## 6. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-P.10) |
