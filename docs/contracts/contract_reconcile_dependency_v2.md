# Contract: Reconcile Dependency V2

**Version**: 2.0
**Date**: 2026-01-03
**Status**: LOCKED

---

## 1. 개요

REQUEST_RECONCILE REAL 실행에 필요한 의존성을 **정공법**으로 확정합니다.

> 🔒 **Fail-Closed**: 필수 import 실패 시 PREFLIGHT_FAIL + REAL 시도 금지

---

## 2. 필수 의존성 (Required Imports)

| Package | Why Needed | Check Method |
|---------|------------|--------------|
| `pandas` | DataFrame 기반 reconcile 로직 | `import pandas` |
| `pyarrow` | parquet 파일 읽기 | `import pyarrow` |

---

## 3. 결정 규칙

```
IF pandas import 실패 OR pyarrow import 실패:
    decision = PREFLIGHT_FAIL
    REAL 시도 = 금지
    receipt = BLOCKED
```

---

## 4. 증거(Artifact) 요구

### 4-A. Deps Snapshot

- **경로**: `state/deps/installed_deps_snapshot.json`
- **필수 필드**:
  - `asof`: ISO datetime
  - `python_version`: 문자열
  - `packages`: `{"pandas": "x.y.z", "pyarrow": "x.y.z"}`
  - `source`: "pip freeze" | "importlib metadata"

### 4-B. Preflight Artifact

- **경로**: `reports/tickets/preflight/{request_id}.json`
- **필수 필드**:
  - `imports`: pandas/pyarrow 결과 PASS/FAIL
  - `decision`: PREFLIGHT_PASS | PREFLIGHT_FAIL

---

## 5. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (C-P.10) |
| 2.0 | 2026-01-03 | 정공법 확정 (C-P.11) |
