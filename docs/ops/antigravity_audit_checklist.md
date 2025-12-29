# Antigravity Rules Audit Checklist (Phase 13.5)

**Date**: 2025-12-29
**Auditor**: Antigravity Agent
**Status**: REVIEW REQUIRED

본 리포트는 `docs/ops/active_surface.md`에 명시된 유효 범위 내 코드가 Antigravity Rules를 준수하고 있는지 점검한 결과입니다.

## 1. Summary of Violations

| Rule ID | Category | Severity | Description | Count |
| :--- | :--- | :--- | :--- | :--- |
| **1-1** | Language | **Medium** | 주요 파일 내 주석 및 로그 메시지가 영어로 작성됨. | 2 Files |
| **3-4** | Hardcoding | Low | 일부 설정값이 코드 내에 포함되어 있음. | 1 File |
| **4-4** | Error Log | Low | `try-except` 블록에서 알림 없이 단순 예외 처리. | 1 File |

## 2. Detailed Findings

### A. Rule 1-1 (한국어 미준수)
**정책**: 모든 주석, 로그, 사용자 메시지는 **한국어(Korean)**여야 한다.

*   **[VIOLATION] `backend/main.py`**
    *   **Context**: 신규 작성된 FastAPI 코드 전반.
    *   **Evidence**:
        *   `app = FastAPI(title="KRX Alertor Modular API"...)`
        *   `description="Read-Only Observer Backend"`
        *   `def get_status(): """Reads logs/daily_{TODAY}.log..."""`
    *   **Action Required**: Docstring 및 Description을 한국어로 번역 수정 필요.

*   **[VIOLATION] `tools/paper_trade_phase9.py`** (Partial)
    *   **Context**: 일부 변수명이나 기술적 로그는 영어 관행을 따랐으나, 사용자용 Output은 한국어가 혼용됨. (Passable but note worthy)

### B. Rule 3-4 (Hardcoding)
**정책**: 변경 가능한 설정값은 `config/`로 분리해야 한다.

*   **[NOTICE] `app/cli/alerts.py`**
    *   `sp_scan.add_argument("--date", type=str, default="auto", help="날짜 (auto=오늘)")`
    *   기본값들이 코드 내에 존재하나, CLI 인자 특성상 허용 가능 범위.
    *   단, `choices=['legacy', 'phase9']` 등 전략 목록이 하드코딩되어 있어 전략 추가 시 코드 수정 필요.

### C. Rule 4-4 (Error Logging)
**정책**: 예외 발생 시 단순 `print`나 `pass`가 아닌, 적절한 로깅/알림 처리가 되어야 한다.

*   **[RISK] `backend/main.py`**
    *   `except Exception as e: raise HTTPException(...)`
    *   웹 서버 표준 패턴이므로 허용되나, **운영 로그 파일**에는 기록되지 않고 HTTP 500 응답만 나감.
    *   **Recommendation**: `logger.error(...)`를 추가하여 `logs/backend.log` 등에 남기는 것을 권장.

---
**Conclusion**: `backend/main.py`의 주석 언어 위반(1-1)이 가장 현저하며, 이는 추후 Phase 14 UI 구현 시 수정 권장됩니다.
