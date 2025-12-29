# UI Constitution (Contract) v1.0

**Date**: 2025-12-29
**Version**: 1.0
**Scope**: Dashboard UI & Backend API Agreement

이 문서는 UI와 Backend 간의 **"불변의 약속"**을 정의합니다. 모든 UI 구현과 API 응답은 이 규칙을 위반할 수 없습니다.

## 1. Color Rules (상태 표시 헌법)

시스템의 상태(Status Badge)는 단일 필드가 아닌, `badge`, `read_quality`, `evidence` 3차원 데이터를 종합하여 판단해야 합니다.

| 상태 (Priority 순) | 조건 (Logic) | 색상 (Color) | 의미 (Meaning) |
|---|---|---|---|
| **FAIL** | `badge == "FAIL"` | 🔴 **RED** | **시스템 실행 실패**. 즉각 조치 필요. |
| **WARN** | `badge == "OK"` AND `evidence.error_count > 0` | 🟠 **ORANGE** | **실행은 완료**되었으나, 로그 내 **에러 키워드**가 발견짐. |
| **CAUTION** | `badge == "OK"` AND `read_quality != "perfect"` | 🟡 **YELLOW** | 실행 성공 여부와 무관하게, **로그 파일이 손상**되어(인코딩 등) 신뢰할 수 없음. |
| **NORMAL** | 그 외조 모든 경우 (`badge == "OK"`) | 🟢 **GREEN** | **완벽한 성공**. (로그 깨짐 없고, 에러 키워드 없음) |

## 2. Wording Rules (오해 방지)

사용자(운영자)가 시스템이 멈춘 것으로 오해하지 않도록 명확한 단어를 사용합니다.

| 상황 | 금지어 (Do Not Use) | 권장어 (Recommended) |
|---|---|---|
| 시그널 0건 (정상) | "데이터 없음", "에러" | **"오늘 거래 없음 (No Action)"** |
| 시그널 0건 (FAIL) | "데이터 없음" | **"거래 없음 (실행 실패 가능성 확인 필요)"** |
| Backend 연결 실패 | "로딩중..." | **"Backend 연결 불가 (구동 확인)"** |

## 3. Data Source Priority (Source of Truth)

UI는 데이터를 가공하거나 추정하지 않으며, 아래 지정된 소스만을 1:1로 투영(Projection)합니다.

1.  **Status (헤더)**: `/api/status` $\rightarrow$ `logs/daily_{TODAY}.log`
2.  **Portfolio (자산)**: `/api/portfolio` $\rightarrow$ `state/paper_portfolio.json`
3.  **History (차트)**: `/api/history` $\rightarrow$ `reports/paper/*.json`
4.  **Signals (목록)**: `/api/signals` $\rightarrow$ `reports/signals_{TODAY}.yaml`

## 4. API Versioning

*   **API Schema Version**: `UI-1.0`
*   **Rule**: Backend는 `/api/status` 응답에 반드시 `"schema_version": "UI-1.0"`을 포함해야 하며, UI는 이를 검증해야 합니다.
