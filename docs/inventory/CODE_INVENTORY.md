# 코드 인벤토리 (2026-04-20)

읽기 전용 발견 보고서. 수정/제안/평가 없음.

## 1. 살아있는 것 (현재 동작 중)
- [start.bat](../../start.bat): uvicorn backend.main:app(8000) + streamlit pc_cockpit/cockpit.py(8501) + connect_oci.bat 기동
- [backend/main.py](../../backend/main.py): FastAPI 엔트리, 16개 라우터 수동 include (core/portfolio/reporting/push/tickets/ops/evidence/live_cycle 등)
- [pc_cockpit/cockpit.py](../../pc_cockpit/cockpit.py): Streamlit 부트스트랩
- [deploy/oci/](../../deploy/oci/): 15+ .sh (daily cron, portfolio update, ops_summary, holding_watch)
- 근거: start.bat에 직접 기동, 최근 커밋(ac29b4b0/f5607323 P210-STEP10C)이 app/backend 전반 수정

## 2. 만들다 중단된 것 (코드는 있으나 미완성)
- [app/backtest/runners/backtest_runner.py](../../app/backtest/runners/backtest_runner.py): NotImplementedError
- [app/run_tune.py](../../app/run_tune.py): NotImplementedError (Optuna 튜닝 콘솔)
- [app/generate_manual_execution_record.py](../../app/generate_manual_execution_record.py): TODO "Implement if needed to compare with Prep"

## 3. 중복/구버전 의심
- [docs/SSOT/CONSTITUTION.md](../SSOT/CONSTITUTION.md) vs [docs/SSOT/PROJECT_CONSTITUTION.md](../SSOT/PROJECT_CONSTITUTION.md): 헌법 2종 병존 (후자는 git D 상태)
- [docs/SSOT/PROJECT_ORIGIN_INTENT.md](../SSOT/PROJECT_ORIGIN_INTENT.md) vs [docs/SSOT/AI_ROLE_OPERATING_RULES.md](../SSOT/AI_ROLE_OPERATING_RULES.md) vs [docs/SSOT/PROJECT_ASSUMPTIONS.md](../SSOT/PROJECT_ASSUMPTIONS.md) vs [docs/SSOT/PROJECT_KILL_SWITCHES.md](../SSOT/PROJECT_KILL_SWITCHES.md): 최상위 원칙 문서 4개 동시 존재
- [pc_cockpit/cockpit.py](../../pc_cockpit/cockpit.py) vs pc_cockpit/cockpit.py.bak: 백업 파일(라인 수 대폭 차이)
- [_archive/cleanup_20260215/](../../_archive/cleanup_20260215/) / [_archive/deprecated_code/](../../_archive/deprecated_code/) / [_archive/deprecated_docs/](../../_archive/deprecated_docs/) / [_archive/legacy_20260102/](../../_archive/legacy_20260102/): 4종 아카이브 레이어

## 4. 고아 파일 (어디서도 호출 안 됨)
- [app/reconcile.py](../../app/reconcile.py): 상위 import 없음 (독립 유틸 추정)
- [app/verify_ops_summary_links.py](../../app/verify_ops_summary_links.py): 라우터/backend import 없음
- [app/lint_active_surface.py](../../app/lint_active_surface.py): run_lint() 호출 지점 미확인
- [error.log](../../error.log): 2026-03-22 17KB 런타임 로그, git 추적됨

## 5. 과잉 복잡도 의심 (단일 사용자 프로젝트 기준)
- [app/backtest/reporting/](../../app/backtest/reporting/): allocation_constraints/, drawdown/, holding_structure/ 3중 하위, 각각 sweep/diagnostic/report_writer/verdict
- [app/backtest/ml/predictive_risk_classifier](../../app/backtest/ml/): 혼자 쓰는 환경에서 ML 분류기 레이어
- [app/pc/](../../app/pc/) + [pc_cockpit/services/](../../pc_cockpit/services/) + [pc_cockpit/views/](../../pc_cockpit/views/): PC 전용 3층 분리
- 판단 기준: "혼자 쓰는 프로그램에 필요한가" — 총 Python 모듈 589개

## 6. 토큰/인증 시스템
- TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID: .env → [app/providers/telegram_sender.py](../../app/providers/telegram_sender.py)
- OCI_BACKEND_URL / OCI_OPS_TOKEN: .env → [app/routers/sync.py](../../app/routers/sync.py) (pull_from_oci)
- KIS / KRX 별도 토큰 파일 미발견 (pykrx>=1.0.51 의존, 무인증)
- .env: 루트에 347B 커밋 상태

## 7. 외부 연동 지점
- OCI: [app/routers/sync.py](../../app/routers/sync.py) pull_from_oci() + [start.bat](../../start.bat) connect_oci.bat SSH 터널 + [app/routers/ssot.py](../../app/routers/ssot.py) platform.node() "oracle" 감지
- Telegram: [app/providers/telegram_sender.py](../../app/providers/telegram_sender.py) send_telegram_message() → [app/generate_daily_status_push.py](../../app/generate_daily_status_push.py), [app/generate_incident_push.py](../../app/generate_incident_push.py)
- 시세: [app/backtest/infra/providers/naver_fdr.py](../../app/backtest/infra/providers/naver_fdr.py) (FDR), [app/backtest/infra/providers/yfinance_provider.py](../../app/backtest/infra/providers/yfinance_provider.py), [app/providers/market_data.py](../../app/providers/market_data.py) (pykrx)

## 8. 발견했으나 용도를 모르겠는 것
- [freiends_project/](../../freiends_project/): 1.8MB zip + MOMENTUM_ETF_ANALYSIS.md(57KB) + P211_PHASE2_HANDOFF_MASTERPLAN.md(10KB), 폴더명 오타, git 추적, 현재 단계(P210-STEP10C)와 불일치
- [config/production_config.py](../../config/production_config.py): v1/v2 이중화 여부 미확정
- [app/backtest/runners/backtest_runner.py](../../app/backtest/runners/backtest_runner.py) NotImplementedError인데 [app/backtest/reporting/](../../app/backtest/reporting/) 트리는 확장 상태
