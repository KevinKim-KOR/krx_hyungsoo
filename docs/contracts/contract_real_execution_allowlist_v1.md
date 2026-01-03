# Contract: Real Execution Allowlist V1

**Version**: 1.0
**Date**: 2026-01-03
**Status**: LOCKED (Immutable)

---

## 1. 개요

Real Execution Allowlist는 **실행 가능한 명령/모듈/출력을 화이트리스트로 잠금**합니다.

> 🔒 **Immutable Contract**: 이 파일은 `docs/contracts/`에 고정되며, state/ 저장 금지.

---

## 2. 핵심 정책

### 2.1 Immutable Path
- **위치**: `docs/contracts/execution_allowlist_v1.json`
- **불변성**: 런타임에 수정 불가, 배포 시에만 변경
- **이유**: 공격자가 state 파일을 조작해도 허용 범위가 확장되지 않음

### 2.2 Exact Match Only
- 명령어 배열: **완전 일치** 필요 (부분 매칭 금지)
- 출력 경로: **정확한 경로** 일치 필요 (접두어 매칭 금지)
- 예: `["python", "-m", "app.reconcile"]` ≠ `["python", "-m", "app.reconcile", "--force"]`

### 2.3 위반 시 처리
- **Decision**: `SHADOW_BLOCKED`
- **BlockedBy**: `EXECUTION_ALLOWLIST_V1`
- **Violations**: 위반 항목 목록 기록

---

## 3. 스키마 정의

### REAL_EXECUTION_ALLOWLIST_V1

```json
{
  "schema": "REAL_EXECUTION_ALLOWLIST_V1",
  "version": "1.0",
  "asof": "2026-01-03",
  "allowed_request_types": ["REQUEST_RECONCILE", "REQUEST_REPORTS"],
  "rules": {
    "REQUEST_RECONCILE": {
      "real_command_allowlist": [["python", "-m", "app.reconcile"]],
      "expected_outputs_allowlist": [
        "reports/phase_c/latest/recon_summary.json",
        "reports/phase_c/latest/recon_daily.jsonl"
      ],
      "required_inputs": ["config/production_config_v2.py"]
    }
  }
}
```

---

## 4. 검증 흐름

```
1. Load allowlist (docs/contracts/)
2. Check request_type in allowed_request_types
3. Check command in real_command_allowlist (exact match)
4. Check outputs in expected_outputs_allowlist (exact match)
5. Pass → SHADOW_OK / Fail → SHADOW_BLOCKED
```

---

## 5. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-P.8) |
