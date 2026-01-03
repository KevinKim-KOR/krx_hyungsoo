# Contract: Execution Plan V1

**Version**: 1.0
**Date**: 2026-01-03
**Status**: LOCKED

---

## 1. 개요

Execution Plan은 **티켓 타입별 실행 명령을 정의**하는 Machine-Readable 문서입니다.

> 📂 **SoT Location**: `docs/contracts/execution_plan_v1.json`

---

## 2. 파일 구조

```json
{
  "version": "1.0",
  "description": "Machine-Readable Execution Plan",
  "plans": {
    "<REQUEST_TYPE>": {
      "cmd": [...],
      "module": "...",
      "description": "..."
    }
  }
}
```

---

## 3. 필드 정의

### 3.1 Root Fields

| Key | Type | 필수 | 설명 |
|-----|------|------|------|
| `version` | string | ✅ | Plan 버전 |
| `description` | string | ⚠️ | 문서 설명 |
| `plans` | object | ✅ | 티켓 타입별 실행 계획 |

### 3.2 Plan Entry Fields

| Key | Type | 필수 | 설명 |
|-----|------|------|------|
| `cmd` | array | ✅ | 실행 명령어 배열 (예: `["python", "-m", "app.reconcile"]`) |
| `module` | string | ✅ | 타겟 모듈 경로 (예: `app/reconcile.py`) |
| `description` | string | ⚠️ | 명령 설명 |

---

## 4. 현재 정의된 Plans

| Request Type | Command | Module |
|--------------|---------|--------|
| `REQUEST_RECONCILE` | `python -m app.reconcile` | `app/reconcile.py` |
| `REQUEST_REPORTS` | `python -m app.generate_reports` | `app/generate_reports.py` |

---

## 5. Dry-Run Validation Checks

Worker가 DRY_RUN 모드에서 수행하는 검증 항목:

| Check Key | 설명 |
|-----------|------|
| `plan_exists` | `execution_plan_v1.json`에 해당 request_type이 존재함 |
| `module_exists` | module 경로의 파일이 파일시스템에 존재함 |
| `python_available` | Python 인터프리터 사용 가능 |

---

## 6. Usage in Worker

```python
# 1. Load Plan
plans = load_execution_plan()

# 2. Get Plan for Request Type
plan = plans.get(request_type)
cmd = plan.get("cmd", [])

# 3. Dry Validation (NOT Execution)
checks = validate_plan(plan)
```

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-P.5) |
