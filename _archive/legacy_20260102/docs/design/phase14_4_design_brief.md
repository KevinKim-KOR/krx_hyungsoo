# Phase 14.4 Design Brief: The Observer's Cockpit

**Date**: 2025-12-29
**Role**: UI/UX Designer & Frontend Developer
**Objective**: "Clean, Honest, and Professional Observation"

엔진은 동결되었습니다. 이제 우리는 엔진이 만들어낸 결과물을 가장 정직하고 아름답게 보여주는 **관측소(Cockpit)**를 구축합니다.

## 1. Design Concept: "Cyber-Physical Ops"
*   **Keywords**: Trustworthy, Dark Mode, High Contrast, Data-Dense.
*   **Palette**:
    *   **Background**: Deep Slate (`#0f172a`) - 눈의 피로 최소화.
    *   **Accent**: Cyan (`#22d3ee`) - 정보의 명확한 전달.
    *   **Alert**:
        *   🟢 **Green**: Perfect Operation.
        *   🟡 **Yellow**: Partial / Warning (Admin Attention Required).
        *   🔴 **Red**: System Failure.
*   **Typography**: `Inter` (Google Fonts) - 숫자 가독성 최적화.

## 2. Information Architecture (IA) Re-design

### A. Global Header (Sticky)
*   **System Title**: "KRX Alertor"
*   **Status Badge**: [OK/WARN/FAIL] (Real-time Heartbeat)
*   **Last Update**: YYYY-MM-DD HH:MM:SS

### B. Main Dashboard (Grid Layout)
1.  **System Health Card**:
    *   로그 분석 결과 (키워드 카운트).
    *   Read Quality Indicator (Partial/Perfect).
2.  **Asset Summary Card**:
    *   Total Equity (Big Number).
    *   Cash Ratio (Progress Bar).
3.  **Market Sentiment (Regime)**:
    *   Bull/Bear Indicator (Daily Signal 기반 유추).

### C. Details Tabs
1.  **Portfolio (Inventory)**:
    *   보유 종목 리스트, 수량, 평가액.
2.  **Signals (Decision)**:
    *   금일 매매 의사결정 내역.
3.  **Logs (Evidence)**:
    *   Raw Log Viewer (Terminal-like Style).

## 3. Implementation Plan
*   **Tech Stack**: React 18 (Single HTML), Tailwind CSS (CDN).
*   **File**: `dashboard/index.html` (Single Source).
*   **Constraints**:
    *   **No Build Step**: `babel-standalone` 사용.
    *   **Responsive**: 모바일에서도 상태 확인 가능하도록 Flex/Grid 반응형 설계.

## 4. Key UX Improvements
1.  **Start-up Animation**: 로딩 시 시스템 부팅 시퀀스 효과.
2.  **Visual Hierarchy**: 중요한 숫자(평가금액)는 크게, 보조 정보(날짜)는 작게.
3.  **Error Visibility**: 로그가 깨졌거나 파일이 없으면 숨기지 않고 "명확하게" 빈 상태(Empty State)를 보여줌.

---
**"엔진은 보이지 않는 곳에서 일하지만, UI는 그 노고를 증명해야 합니다."**
이 설계안을 바탕으로 프론트엔드 구현을 시작합니다.
