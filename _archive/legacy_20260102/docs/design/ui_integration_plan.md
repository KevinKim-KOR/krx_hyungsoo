# UI Integration Plan (Read-Only Observer Pattern)

**Target**: Build a Web Dashboard that visualizes the trading engine's outputs without coupling to the engine code.
**Philosophy**: "File-Based Coupling" - The UI reads what the Engine writes.

---

## 1. Data Source Map

UI가 읽어야 할 파일과 그 용도입니다.

| Category | File Path Pattern | Content & Usage |
| :--- | :--- | :--- |
| **Status** | `logs/daily_{TODAY}.log` | **System Health**: <br>- `[OK]`: 실행 완료<br>- `[SKIP]`: 이미 실행됨<br>- `FAILED`: 에러 발생<br>- Time Warning 확인 |
| **Portfolio** | `state/paper_portfolio.json` | **Current Asset State**: <br>- `total_equity`: 총 자산<br>- `cash`: 현금 잔고<br>- `positions`: 보유 종목 리스트 |
| **Signals** | `reports/signals_{TODAY}.yaml` | **Daily Decision**: <br>- `signal_type`: BUY/SELL/EXIT<br>- `score`: 점수<br>- `reason`: 선정 사유 (ADX, Regime 등) |
| **History** | `reports/paper/paper_*.json` | **Performance Tracking**: <br>- 과거 날짜들의 equity 및 pnl 데이터를 취합하여 차트 생성 |

---

## 2. UI Component Requirements

각 화면 컴포넌트가 바인딩해야 할 데이터 소스입니다.

### A. Dashboard Card (Main View)
*   **Data**: `state/paper_portfolio.json`, `logs/daily_{TODAY}.log`
*   **Display**:
    *   **Status Badge**: 🟢 OK / 🟡 SKIP / 🔴 FAIL (로그 파일 파싱)
    *   **Total Equity**: `total_equity` (KRW 포맷)
    *   **Daily PnL**: 오늘 `equity` - 어제 `equity` (History 비교)
    *   **Exposure**: `(total_equity - cash) / total_equity` (%)

### B. Market Status (Side Panel)
*   **Data**: `reports/signals_{TODAY}.yaml` (또는 별도 Market Meta 파일 필요시 논의)
*   **Display**:
    *   **Regime**: Bull / Bear / Chop (Signal 파일 내 메타데이터 혹은 Reason 필드 추론)
    *   **Market Action**: "Risk-On (Buy allowed)" vs "Risk-Off (Cash only)"

### C. Portfolio Table
*   **Data**: `state/paper_portfolio.json` -> `positions`
*   **Columns**:
    *   종목코드 (`code`)
    *   보유수량 (`qty`)
    *   평단가 (`avg_price`)
    *   *현재가*: (`total_equity` 역산 혹은 별도 API 호출 필요. *UI에서 실시간 시세 조회 허용 여부 결정 필요*)
    *   평가금액 (`qty * current_price`)

### D. Equity Chart
*   **Data**: `reports/paper/paper_*.json` (Glob pattern scan)
*   **Visual**: Line Chart
    *   **X-Axis**: Date (`execution_date`)
    *   **Y-Axis**: Total Equity
    *   **Tooltip**: 일별 수익률, 매매 횟수

### E. Raw Report Viewer
*   **Data**: 선택된 날짜의 `yaml`, `json`, `log`
*   **Feature**: 텍스트 그대로 보여주는 `<pre>` 블록 또는 JSON Tree Viewer. 디버깅용.

---

## 3. Implementation Steps (Draft)

1.  **Backend API (FastAPI Wrapper)**:
    *   엔진 코드를 import하지 않고, 단순히 **파일을 읽어 JSON으로 리턴하는 API**만 구현.
    *   `GET /api/status/today`: 로그 파싱 결과 리턴.
    *   `GET /api/portfolio`: 포트폴리오 JSON 리턴.
    *   `GET /api/history`: 과거 리포트 취합 리턴.

2.  **Frontend (React/Dashboard)**:
    *   위 API를 호출하여 렌더링.
    *   **Action**: "Refresh" 버튼 (단순 API 재호출). "Execute" 버튼 (존재하지 않음 or Disable 처리).
