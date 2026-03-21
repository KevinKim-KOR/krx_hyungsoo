# ML Session Handoff Checklist (P204)

다음 세션(ML 튜닝 및 최적화) 작업을 시작할 때, 기존 시스템이 즉시 정상 작동하는지 여부를 검증하기 위한 1분 체크리스트입니다.

## 🖥️ PC 환경 확인 (Cockpit - localhost:8501)
- [ ] **토큰 설정 확인**: `워크플로우` 탭의 `OCI Access Token` 옆에 `TOKEN: AUTO(.env)` 뱃지가 활성화되어 있는지 확인. (없다면 `.env` 파일에 `OCI_OPS_TOKEN`이 기입되어 있는지 점검)
- [ ] **결재 승인 통과**: `워크플로우` 탭에서 **[Approve LIVE]** 토글을 켜고, 5-Step Flow Guide의 [Step 0] 이 `✅ APPROVED`로 뜨는지 확인.
- [ ] **1-Click Sync**: `워크플로우` 탭의 **[📤 OCI 반영 (1-Click Sync)]** 클릭 후 에러 없이 쾌적하게 성공 Toast 창이 등반하는지 확인.

## ☁️ OCI 서버 확인 (Backend)
- [ ] **Approval 파일 존재**: OCI 서버 백엔드 내 `state/strategy_bundle/latest/live_approval.json` 파일이 생성되었는지 확인.
- [ ] **Auto Ops 갱신**: 조종석에서 **[▶️ Run Auto Ops Cycle]** 버튼 클릭 시, OCI에서 `reco_latest.json` 및 `order_plan_latest.json` 파일의 `asof` Timestamp 값이 방금 시간으로 갱신되었는지 확인.
- [ ] **오퍼레이터 대시보드 구조 확인**: OCI의 `http://<IP>:8000/operator` 화면이 오류 없이 3단(OPS/EXECUTION/RECORD) 분류로 분리되어 출력되는지 브라우저에서 직접 확인.

## 🆘 실패 시 1차 진단 경로 (Troubleshooting)
1. **Sync / Auto Ops 버튼이 먹통이고 경고만 뜰 때**
   - ➜ `.env`의 `OCI_OPS_TOKEN` 을 먼저 확인하세요. (P203 정책 강화로 토큰 누락 시 1차 차단당합니다.)
2. **"LIVE 승인 없음(또는 REVOKED)" 경고가 뜰 때**
   - ➜ `live_approval.json` 파일이 지워졌거나 "status":"REVOKED" 처리되었는지 확인. 조종석 `워크플로우` 상에서 [Approve LIVE] 를 눌러 재승인하세요.
3. **오퍼레이터 화면에서 Execution 카드들에 뻘건 ⚠️ OUTDATED 뱃지가 번쩍일 때**
   - ➜ 이는 현상적인 경고등일 뿐 삭제 오류가 아닙니다! 과거에 생성된 주문서의 `plan_id`가 현재 OPS 섹션의 `ORDER PLAN` `plan_id`와 달라서 생기는 시각적 효과이므로 당황하지 말고 "아, 옛날 껍데기구나" 넘기시면 됩니다.
