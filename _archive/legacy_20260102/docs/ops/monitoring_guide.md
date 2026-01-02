# Operational Monitoring Guide v1.0

**Target Audience**: System Operator / Admin
**Purpose**: 일일 관제 및 트러블슈팅 가이드

## 1. Dashboard Overview

"KRX Alertor Cockpit"은 3차원 상태 분석 로직을 통해 가장 정직한 시스템 상태를 보여줍니다.

### Status Badge (Color Code)
상태 배지는 단순 성공/실패가 아닌, **로그의 신뢰도(Quality)**를 포함하여 판단합니다.

| 배지 (Badge) | 색상 (Color) | 의미 (Meaning) | 행동 가이드 (Action) |
|---|---|---|---|
| **SYSTEM FAIL** | 🔴 **RED** | **치명적 오류**. 실행이 중단되었거나 실패함. | 즉시 [LOGS] 탭에서 원인을 파악하고 재실행 필요. |
| **OK (ERRORS)** | 🟠 **ORANGE** | **실행 완료**되었으나, 로그 내 **에러**가 발견됨. | [LOGS] 탭에서 `[ERROR]` 키워드 검색 후 영향도 평가. |
| **OK (LOG DAMAGED)** | 🟡 **YELLOW** | **실행 완료**. 단, 로그 인코딩 문제로 일부 내용이 깨짐. | 운영상 문제는 없으나, 추후 로그 인코딩(`utf-8`) 확인 권장. |
| **OPERATIONAL** | 🟢 **GREEN** | **완벽한 상태**. (깨짐 없음, 에러 없음) | 조치 불필요. 퇴근하십시오. |

## 2. Daily Monitoring Routine

1.  **Dashboard Access**:
    *   URL: `http://localhost:8000/`
    *   시간: 장 마감(15:30) 이후 자동화 실행(~16:00) 종료 시점.

2.  **Check Points**:
    *   **헤더 배지**: 🟢 또는 🟡인지 확인. (🔴/🟠는 조치 필요)
    *   **Total Equity**: 어제 대비 자산이 갱신되었는지 확인 (Context 차트 활용).
    *   **Portfolio**: 현재 `Cash 100%`인지, `Holdings`가 있는지 확인.
    *   **Signals**: "오늘 거래 없음 (No Action)"인지, 구체적인 매매 신호가 있는지 확인.

## 3. Trouble Shooting

### Case A: "Backend Disconnected" (화면이 안 뜸)
*   **원인**: 백엔드 서버(`uvicorn`)가 꺼져 있음.
*   **조치**:
    ```bash
    cd /path/to/project
    uvicorn backend.main:app --host 0.0.0.0 --port 8000
    ```

### Case B: "Schema Mismatch" 또는 이상한 UI 동작
*   **원인**: UI(`index.html`)와 백엔드 API 버전(`backend/main.py`)이 UI-1.0 규칙을 어김.
*   **조치**: `docs/design/ui_contract_v1.0.md`를 참조하여 버전 일치 여부 확인.

---
**"Trust-First Monitoring"**
우리는 보이지 않는 것을 믿지 않습니다. 오직 증거(`[OK]`, `files`)만이 진실입니다.
