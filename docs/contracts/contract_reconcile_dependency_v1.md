# Contract: Reconcile Dependency V1

**Version**: 1.0
**Date**: 2026-01-03
**Status**: LOCKED

---

## 1. 개요

Reconcile REAL 실행에 필요한 최소 의존성을 정의합니다.

> ⚠️ **Fail-Closed**: 의존성 미충족 시 REAL 실행 금지 + FAILED receipt 기록

---

## 2. 스키마 정의

### RECONCILE_DEPENDENCY_V1

```json
{
  "schema": "RECONCILE_DEPENDENCY_V1",
  "python_min_version": "3.10",
  "pip_dependencies_min": {
    "pandas": "required for data manipulation",
    "pyarrow": "required for parquet file reading"
  },
  "why_needed": {
    "pandas": "DataFrame 기반 데이터 조인/필터/집계 처리",
    "pyarrow": "parquet 형식 evidence/ledger 파일 읽기"
  },
  "failure_policy": "REAL_BLOCKED_DEPENDENCY_MISSING"
}
```

---

## 3. 필수 패키지

| Package | Why Needed | Check Method |
|---------|------------|--------------|
| `pandas` | DataFrame 기반 reconcile 로직 | `import pandas` |
| `pyarrow` | parquet 파일 읽기 | `import pyarrow` |

---

## 4. 실패 정책

| 조건 | 결과 |
|------|------|
| pandas import 실패 | PREFLIGHT_FAIL |
| pyarrow import 실패 | PREFLIGHT_FAIL |
| Python < 3.10 | PREFLIGHT_FAIL |

---

## 5. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-P.10) |
