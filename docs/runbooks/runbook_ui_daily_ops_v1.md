# Runbook: UI Daily Ops V1.7 (최신판)

**Target**: All Operators
**Prerequisite**: PC Cockpit (:8501) 구동 
**Goal**: Daily Trading Cycle Execution (09:00 ~ 15:30)

---

## 0. Prerequisite (준비 및 토큰 자동 로드)

1. **PC**: `start.bat` 실행 → **Cockpit** 열림 (`http://localhost:8501`).
2. **토큰 설정**: `.env` 파일 내에 `OCI_OPS_TOKEN=...` 이 기입되어 있어야 합니다. (P203)
   - 이제 토큰을 매번 복붙할 필요 없이 `AUTO(.env)` 모드로 자동 인식됩니다.
   - 토큰이 누락될 경우 모든 OCI 반영/가동 로직은 **Fail-Closed(강제 중단)** 처리됩니다.

---

## 1. 운영 흐름 가이드 (5-Step Flow Guide)

오퍼레이터는 `데일리운영 (P144)` 탭의 **🗺️ 운영 흐름 가이드**를 위에서부터 아래로 순차적으로 따라갑니다. (P202)

### [Step 0] 승인 (Approval)
- **목적**: 시스템 가동(LIVE)에 부여된 승인 상태를 확인합니다.
- **수행**: `워크플로우 (P170)` 탭에서 [Approve LIVE] 클릭. (이미 승인되어 있으면 생략)

### [Step 1] 동기화 (1-Click Sync)
- **목적**: PC의 최신 파라미터(설정)를 OCI로 푸시합니다.
- **수행**: `데일리운영 (P144)` 탭에서 📥 **PULL (OCI)** 를 눌러 최신 상태를 읽고, `워크플로우` 탭이나 `데일리운영` 탭에 있는 📤 **OCI 반영 (1-Click Sync)** 버튼을 누릅니다.

### [Step 2] 운영 실행 (Auto Ops)
- **목적**: OCI 백엔드에서 RECO(추천) 및 ORDER PLAN(주문안)을 자동 생성시킵니다.
- **수행**: `데일리운영` 탭 - 🤖 Auto Operations 영역에서 ▶️ **Run Auto Ops Cycle** 버튼 클릭.

### [Step 3] 실행 티켓 정렬 확인 (Execution)
- **목적**: 주문안(ORDER_PLAN) 대비 Export / Prep / Ticket 해시 정렬이 올바른지 확인.
- **확인**: Flow Guide의 State가 `✅ 정렬됨` 으로 표시되는지 체크.

### [Step 4] 수동 체결 영수증 제출 (Record)
- **목적**: 필요 시 실제 결과(`manual_execution_record`)를 남길 때 사용.

---

## 2. OCI Evidence Resolver 데일리 체크 (P202-1)

실행 단계 진입 전, 시스템 산출물(증거)들을 실시간 시각화로 확인해야 합니다.
- **접속**: `http://<OCI_IP>:8000/operator` (또는 터널 8001/operator)

### ⚙️ Section 1: OPS (필수 점검)
매일 시스템이 생성하는 자동 산출물입니다. 모두 초록색 Status이거나 에러가 없어야 합니다.
1. `HEALTH`: 시스템 가드레일/이상여부.
2. `RECO`: 최상위 추천 종목 명단.
3. `ORDER PLAN`: 현재 자금을 베이스로 계산된 실제 수량/금액 주문안 (**plan_id** 기준 발급).
4. `SUMMARY`: 운영 해시라인 및 스테이지 요약.

### 🛠️ Section 2: EXECUTION (실행용)
사람이 실제 체결을 하기 위해 HTS/MTS를 켤 때만 엽니다.
- 주문서 기반 보안토큰(`EXPORT`), 안전성검사(`PREP`), HTS 복붙용 문서(`TICKET`, `TICKET MD`)가 있습니다.
- ⚠️ **주의**: 이 파일들의 `plan_id` 뱃지가 위쪽 Section 1의 `ORDER PLAN`과 다르면 빨간색 **[⚠️ OUTDATED]** 경고 뱃지가 점등됩니다.

### 📝 Section 3: RECORD (선택)
수동 제출용 영수증 보관함 (`RECORD`)

---

## 💡 Troubleshooting

- **"OCI_OPS_TOKEN 없음(.env 설정 필요)" 경고**: PC 루트 폴더의 `.env` 파일 내에 `OCI_OPS_TOKEN` 발급 여부를 체크하고 다시 실행하세요.
- **"LIVE 승인 없음" 차단**: [Step 0] 워크플로우 탭에서 Approve LIVE 과정이 누락되었거나 철회(Revoked)되었습니다.
- **10초 주기 깜박임 (UI 깜박거림)**: 현재 해결되었습니다(P202). 갱신이 필요하면 우측 상단 Refresh 버튼을 누르십시오.
