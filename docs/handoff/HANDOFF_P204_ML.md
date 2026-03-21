# ML Handoff Package (P204)

## A. 프로젝트 한 줄 요약 및 현재 목표
**KRX Alertor Modular V10.0**은 PC(조종석)에서 파라미터를 통제하고 OCI(운영석)에서 자동/수동 매매 산출물을 무결성 있게 발행하는 퀀트 트레이딩 플랫폼입니다.
**현재 목표**: 기초 UI/UX 및 보안(토큰/승인/해시) 파이프라인 정비가 모두 끝났으므로, 본격적인 **"ML 튜닝 (백테스트 최적화)"** 세션을 시작합니다.

## B. 현재 운영 구조 (Architecture)
1. **PC 조종석 (`http://localhost:8501`)**: `cockpit.py` 스트림릿 기반. 전략 파라미터를 설정하고 OCI 서버로 1-Click Sync 하거나, OCI 서버의 산출물을 PULL 하여 확인하는 **Master Control** 역할.
2. **OCI 운영석 (`http://<OCI_IP>:8000`)**: FastAPI / 백엔드 데몬 기반. PC로부터 전달받은 파라미터를 토대로 무거운 연산을 돌리고, 매일 아침 `reco` ➜ `order_plan` ➜ `export` ➜ `prep` ➜ `ticket` ➜ `record` 증명서(Evidence)들을 발행하는 **Execution Engine** 역할.

## C. 최종 확정된 3대 핵심 정책 (절대 규칙)
1. **Token 정책 (Auto-Load & Fail-Closed)**
   - OCI와 통신하는 모든 쓰기/실행 권한(1-Click Sync, Run Auto Ops 등)은 **오직 `OCI_OPS_TOKEN` 1개** 키본만 사용합니다.
   - PC `.env` 파일에 기록해두면 `AUTO(.env)`로 자동 로드되며, UI상에서 `OVERRIDE`도 가능합니다. **토큰이 비어있으면 로컬/분산 동작 일체가 차단(Fail-Closed)** 됩니다.
2. **Approval Gate (결재 장벽)**
   - `state/strategy_bundle/latest/live_approval.json` 파일 내 `"status": "APPROVED"`가 없으면, 모든 1-Click Sync 및 Auto Ops 실행이 **즉시 차단**됩니다.
3. **Hash 안정성 정책 (원천 차단)**
   - `live_approval.json` 자체는 번들(Bundle) 페이로드 해시 검증 대상에서 완전히 **제외(Exclude)**됩니다.
   - 이를 통해 승인 버튼을 누름으로써 파일이 변경되더라도 순환 참조(Hash Mismatch) 오류가 발생하지 않습니다.

## D. 운영 UI 동선 (사람이 누르는 순서)
- **워크플로우 (P170) 탭**: 
  1. [Approve LIVE] 클릭 (승인 결재)
  2. [1-Click Sync] 클릭 (OCI로 최신 파라미터 푸시)
- **데일리운영 (P144) 탭**: 
  1. [PULL (OCI)] 클릭 (전일/최신 데이터 읽어오기)
  2. [Run Auto Ops Cycle] 클릭 (오늘 치 매매 파이프라인 가동)
  3. Flow Guide로 `✅ 정렬됨` 상태 확인.
- **정비창 (P190) 탭**: (필요시만 사용)
  1. Portfolio 구조 임의 교정 기능
  2. Holdings Timing 템플릿 팩토리 가동 등

## E. OCI Operator 대시보드 (`/operator`) 카드 구조
- 접속 경로: OCI 백엔드의 `http://<IP>:8000/operator` 화면
- **Section 1: OPS (추천/주문안)** `[HEALTH ➜ RECO ➜ ORDER PLAN ➜ SUMMARY]`
  - 시스템이 매일 자동으로 뽑아내는 필수 운영 산출물 4대장.
- **Section 2: EXECUTION (실행)** `[EXPORT ➜ PREP ➜ TICKET ➜ TICKET MD]`
  - 사람이 HTS/MTS 등에 직접 수동 주문을 집어넣기 위해 발행받는 서류 묶음. (기준 `plan_id` 불일치 시 `⚠️ OUTDATED` 표출됨)
- **Section 3: RECORD (기록)** `[RECORD]`
  - 체결이 끝난 후 시스템에 성과를 남기는 수동/선택 사항.

## F. 최종 합격 기준 4가지 (통과 완료)
1. **Token Autoload / Fail-Closed**: .env 토큰 자동 로드 및 토큰 누락 시 완벽한 차단 완료 (P203).
2. **Approval + Sync + Ops 관통**: 워크플로우 탭에서 결재 버튼 클릭 후 Sync 및 Auto Ops 버튼까지 한 방에 물 흐르듯 통과 완료 (P200).
3. **Hash Mismatch 원천 차단**: 서버/로컬 해시 데드락 버그 완전 제거 완료 (P200, P201).
4. **Operator UI 정합성 경고**: 예전 문서 열람 방지를 위한 OUTDATED 시각화(삭제 로직 아님) 경고등 점등 완성 (P202).

## G. 다음 세션(ML/Tuning) 지침 (실행 플랜)
다음 세션은 오직 **백테스트(Backtest) 지표 향상과 ML/통계 기반 최적화**에만 집중합니다. 코드 구조나 배선 개조는 엄격히 금지됩니다. (P204-HANDOFF 의거)
- **튜닝 목표**: (예) 일간 변동성(Vol) 및 벡테스트 기간 내 MDD 축소
- **평가 지표**: MDD < 10%, CAGR > 15%, Sharpe Ratio 등
- **실험 범위**: `app/optuna_tuner.py` 혹은 파라미터 구조의 `momentum_window`, `vol_window`, `weights` 교정 및 강화.
- **실패 기준**: 모델 과적합(Overfitting) 현상 발생, 혹은 연산 소요시간이 1주일을 초과할 경우 전략 기각.
- **결과 저장 위치**: `reports/tuning/` 내부 산출물로 기록.

---
### 📚 참고 문서 이력서 (참조 경로)
- UI 배치: `docs/UI_MAP.md`, `docs/UI_MAP.json`, `docs/UI_CATALOG_V1.md`, `docs/UI_WIRING_DECISION_V1.json`
- 현장 백서: `docs/OCI_EVIDENCE_RESOLVER_GUIDE_V1.md`
- 시스템 동향/디버깅 히스토리 (JSON Reports): 
  - `docs/task_reports/P198_Approval_Gate_Report.json`
  - `docs/task_reports/P200_FIX_V2_Report.json`
  - `docs/task_reports/P201_Critical_Report.json`
  - `docs/task_reports/P202_0_Report.json`
  - `docs/task_reports/P203_0_Report.json`
