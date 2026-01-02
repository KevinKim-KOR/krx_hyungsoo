# Active Surface Declaration (System Scope)

**Last Updated**: 2025-12-29
**Status**: ACTIVE

이 문서는 "KRX Alertor Modular" 시스템의 유효한 운영 범위(Active Surface)를 정의합니다. 이 범위 밖의 코드는 'Legacy'로 간주되며, 유지보수 대상에서 제외됩니다.

## 1. Operational Standards (운영 기준)
본 시스템은 다음 3가지 핵심 원칙에 따라 운영됩니다.
1.  **Close-on-Close**: 장중 실시간 데이터가 아닌, **일별 종가 확정 데이터**를 기준으로 의사결정을 수행합니다.
2.  **Read-only Observer**: UI 및 외부 시스템은 엔진의 상태를 변경할 수 없으며, 오직 **산출물(파일)을 읽기**만 합니다.
3.  **Idempotency (멱등성)**: 모든 배치 스크립트는 여러 번 실행되어도 부작용이 없어야 하며, 중복 실행 시 **Skip** 합니다.

## 2. Valid Entry Points (진입점)
시스템을 구동하거나 상태를 조회하기 위한 유일한 승인된 진입점입니다.
*   **Automation**: `deploy/run_daily.sh` (or `.ps1`) - 일일 배치 오케스트레이터.
*   **Core Logic**: `app.cli.alerts` - 시그널 생성 및 스캔 엔진.
*   **Trading**: `tools.paper_trade_phase9` - 가상 매매 및 장부 관리.
*   **Interface**: `backend.main` - FastAPI Read-Only Backend & UI.

## 3. Source of Truth (데이터 원천)
시스템의 상태를 대변하는 단일 진실 공급원(Single Source of Truth)입니다.
*   **Portfolio State**: `state/paper_portfolio.json` (잔고, 현금, 평가금액)
*   **Execution Logs**: `logs/daily_YYYYMMDD.log` (실행 이력, 성공/실패 여부)
*   **Decision Records**: `reports/signals_YYYYMMDD.yaml` (매매 의사결정 기록)

## 4. Configuration Policy (설정 정책)
*   `config/production_config.py` (및 `.yaml`)은 **Immutable(불변)** 취급됩니다.
*   실행 중인 프로세스나 UI에서 설정을 변경하는 것은 금지되며, 변경이 필요한 경우 배포 프로세스를 통해야 합니다.

---
**Note**: `_archive/` 폴더 내의 코드는 참조용일 뿐, 운영 환경에서 로드되거나 실행되어서는 안 됩니다.
