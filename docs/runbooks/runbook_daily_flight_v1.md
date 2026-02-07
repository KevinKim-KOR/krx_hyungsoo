# Daily Flight Checklist V1 (P116)

**목표**: 10~15분 내 "정석 루틴" 완료 (PC → OCI → Manual Loop → Done)
**원칙**: Token Lock 준수 (파일 저장 금지), Fail-Closed (에러 시 중단)

## 1. PC 단계 (Bundle Publish)
**목표**: 최신 전략 번들 생성 및 OCI 배포
1. **PowerShell** 실행 (관리자 권한 아님)
   ```powershell
   cd "e:\AI Study\krx_alertor_modular"
   .\deploy\publish_bundle.ps1
   # 기대결과: "✅ Bundle Published to OCI: ..."
   ```

## 2. OCI 단계 (Auto Ops)
**목표**: Order Plan Export 생성 (자동화 범위 끝)
1. **SSH 접속**
   ```bash
   ssh -i "e:\AI Study\orcle cloud\oracle_cloud_key" ubuntu@168.107.51.68
   cd krx_hyungsoo
   ```
2. **Daily Ops 실행**
   ```bash
   bash deploy/oci/daily_ops.sh
   # 기대결과: "STAGE: NEED_HUMAN_CONFIRM" 또는 "PREP_READY"
   ```

## 3. OCI 단계 (Manual Loop)
**목표**: Prep → Ticket → Execution → Record → DONE_TODAY
1. **상태 확인 (수시 실행)**
   ```bash
   bash deploy/oci/flight_status.sh
   # 출력된 "NEXT ACTION"을 따를 것
   ```

2. **준비 (Prepare & Ticket)**
   * **조건**: `NEXT: RUN: deploy/oci/manual_loop_prepare.sh`
   ```bash
   bash deploy/oci/manual_loop_prepare.sh
   # 토큰 입력 (보이지 않음)
   # 기대결과: "✅ PREPARE COMPLETED", "Ticket: ...md"
   ```

3. **실행 (Human Execution)**
   * **티켓 확인**: `cat reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest.md`
   * **MTS/HTS 거래 수행**

4. **기록 (Submit Record)**
   * **조건**: `NEXT: EXECUTE TRADES -> RUN: deploy/oci/manual_loop_submit_record.sh`
   * **Record 파일 생성** (예: `record.json`)
     ```json
     {"items":[{"ticker":"005930","side":"BUY","status":"EXECUTED","executed_qty":10,"price":60000,"note":"Example"}]}
     ```
   * **제출**
     ```bash
     bash deploy/oci/manual_loop_submit_record.sh record.json
     # 토큰 입력
     # 기대결과: "✅ SUBMIT COMPLETED", "New Stage: DONE_TODAY"
     ```

## 4. 완료 확인 (Daily Done)
1. **최종 상태 확인**
   ```bash
   bash deploy/oci/flight_status.sh
   # 기대결과: "STAGE: DONE_TODAY", "NEXT: NONE (Done)"
   ```

---

## 🛑 트러블슈팅 (자주 발생하는 3가지)
1. **Bundle Stale**: PC에서 `publish_bundle.ps1` 다시 실행 후 `daily_ops.sh` 재실행.
2. **Missing Portfolio**: `deploy/oci/portfolio_bootstrap.sh` (P107) 확인 필요 (현재 수동).
3. **Contract 5 Blocked**: `flight_status.sh` 확인. 의존성(Reco/OrderPlan) 문제 해결 후 `daily_ops.sh` 재실행.
