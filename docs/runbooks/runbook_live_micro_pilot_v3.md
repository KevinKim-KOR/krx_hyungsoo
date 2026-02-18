# Runbook: Live Micro Pilot V3 (UI-First)

**Period**: 2026-02-17 ~ 02-21
**Goal**: Validate "UI-First Operations" with Real Money (Small Scale).
**Base Procedure**: [runbook_ui_daily_ops_v1.md](runbook_ui_daily_ops_v1.md)

---

## 1. Pilot Constraints (Safety)

이 파일럿 기간 동안은 아래 제약조건을 **절대 준수**해야 합니다.

1.  **Ticket Limit**: 하루 최대 **1건**의 매수/매도.
2.  **Budget Limit**: 1회 주문 금액 **100,000 KRW** 미만.
3.  **Approve**: 반드시 `EXPORT_CONFIRM_TOKEN`을 교차 검증할 것.

---

## 2. UI-Only Procedure

모든 조작은 **PC Cockpit**과 **OCI Operator Dashboard**로만 수행합니다. (CLI 금지)

### Step 1: Config Push (PC)
- **Settings**: `Momentum Period` 등을 미세 조정하여 Signal 생성을 유도.
- **Push**: `📤 PUSH (OCI)` 클릭.

### Step 2: Auto Ops Trigger (PC)
- **Run**: `▶️ Run Auto Ops Cycle` 클릭.
- **Wait**: 3분 대기.

### Step 3: Verify Draft (OCI Operator)
- **Access**: `http://localhost:8001/operator` 접속.
- **Draft Manager**:
    - [ ] `Plan ID`가 `NO_ACTION`이 아닌지 확인.
    - [ ] **Ticker**: 의도한 종목인가? (예: TIGER 미국채10년선물)
    - [ ] **Quantity**: 예산(10만원) 이내인가?
    - [ ] **Price**: 시장가(0) 또는 지정가 확인.

### Step 4: Submit (OCI Operator)
- **Token**: `EXPORT_CONFIRM_TOKEN` 입력.
- **Submit**: 승인 버튼 클릭.

### Step 5: Verification (PC)
- **Pull**: `⬇ PULL (OCI)` 클릭.
- **Status**: `EXECUTION_COMPLETED` 확인.
- **Evidence**: `Trade Log`에 체결 내역 표시 확인.

---

## 3. Emergency Stop

만약 UI가 먹통이거나 이상 주문 발생 시:
1. **OCI SSH 접속**.
2. `killall uvicorn` 또는 `sudo systemctl stop krx-backend`.
3. 증권사 MTS로 즉시 접속하여 미체결 주문 취소.
