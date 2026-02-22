# Runbook: UI Daily Ops V1

**Target**: All Operators
**Prerequisite**: PC Cockpit (:8501) via `start.bat`
**Goal**: Daily Trading Cycle Execution (09:00 ~ 15:30)

---

## 0. Prerequisite (준비)

1. **PC**: `start.bat` 실행 → **Cockpit** 열림 (`http://localhost:8501`).
2. **OCI**: SSH Tunnel 연결 확인 (Target: `http://localhost:8001`).
   - Cockpit 하단 "System Connectivity" 버튼 클릭 → **Status: OK** 초록불 확인.

---

## 1. Phase 1: Config & Push (08:50)

PC의 최신 전략 설정을 OCI에 동기화합니다.

1. **Cockpit > Settings 탭** 이동.
2. `Strategy Params` 및 `Universe` 티커 목록 확인.
3. **`📤 PUSH (OCI)` 버튼 클릭**.
4. **Toast 메시지 확인**: "Push Success (Updated: ...)"

> ✅ **Check Point**: 변경된 설정이 다음 사이클부터 반영됩니다.

---

## 2. Phase 2: Execution Trigger (09:00 ~ )

매매 사이클을 실행합니다. (PC는 명령만 내리고, 실행은 OCI가 담당합니다.)

1. **Cockpit > Ops 탭** 이동.
2. (선택사항) 필요 시 **`☑ Force Recompute (Overwrite)`** 체크.
   - *주의*: 당일 이미 생성된 플랜이 있더라도 무조건 새로 생성합니다 (`LIVE` 모드에선 보호됨).
3. **`▶️ Run Auto Ops Cycle` 버튼 클릭**.
4. **Toast 메시지 확인**: "Auto Ops Cycle Completed" 및 Info 박스 요약 확인 (예: `RECO: REGEN | ORDER_PLAN: SKIP`).
5. **대기**: 약 1~5분 소요 (OCI 내부 연산).

---

## 3. Phase 3: Observation & Sync (09:05 ~ )

OCI의 실행 결과를 PC로 가져와 확인합니다.

1. **`⬇ PULL (OCI)` 버튼 클릭**.
2. **Status Bar 확인**:
   - `NO_ACTION_TODAY`: 오늘 매매 없음 (종료).
   - `EXECUTION_PREP`: 매매 기회 포착 (승인 필요).
   - `UNKNOWN`: 동기화 실패 (재시도 필요).
3. **Ops Summary 블록 확인**:
   - `Risk Status`, `Market Condition`, `Signal` 등 세부 정보 확인.

---

## 4. Phase 4: Manual Approval (If Needed)

`EXECUTION_PREP` 상태라면, OCI Operator Dashboard에서 승인해야 합니다.

1. **브라우저 접속**: `http://<OCI_IP>:8000/operator` (또는 로컬 터널 `http://localhost:8001/operator`)
2. **Draft Manager** 섹션 확인.
3. **Generate Draft** 버튼 클릭 → `Preview` 확인 (매수 종목/수량).
4. **Submit Ticket**:
   - **Token 입력**: `EXPORT_CONFIRM_TOKEN` (보안상 별도 채널로 공유된 값).
   - **Confirm** 클릭.
5. **결과 확인**: "Execution Record Created" 메시지.

---

## 5. Phase 5: Final Verification

승인 후, PC 상태를 최종 동기화합니다.

1. **Cockpit > Ops 탭** 이동.
2. **`⬇ PULL (OCI)` 버튼 클릭**.
3. **Status Bar 확인**: `EXECUTION_COMPLETED` (또는 `PARTIAL_FILLED`).
4. **Evidence Arrived**: `Trade Log` 및 `Postmortem` 리포트가 화면에 표시되는지 확인.

---

## 💡 Troubleshooting

- **PC `Unknown` / Timeout**:
  - `start.bat` 창에서 SSH Tunnel 끊김 여부 확인.
  - `stop.bat` 후 `start.bat` 재시작.
- **OCI 500 Error**:
  - 설정(Push) 문제일 가능성 높음. `Settings` 확인 후 다시 Push.
