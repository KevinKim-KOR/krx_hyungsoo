# Tools Module Analysis

**분석 일자**: 2025-12-29
**분석 대상**: `tools/` 디렉토리 내 16개 파일 (전수 조사)

## 1. 개요 (Overview)
`tools/` 디렉토리는 시스템 유지보수, 백테스트 실행(Phase별), 데이터 검증, 디버깅을 위한 독립적인 스크립트 모음입니다.
대부분의 스크립트는 `__main__` 블록을 가지고 직접 실행되도록 설계되었습니다.

## 2. 파일별 상세 분석 (Detailed Analysis)

### 2.1 Backtest Runners (Phase Execution)
각 개발 Phase별 백테스트 실행기들입니다. Phase가 지남에 따라 레거시화되는 경향이 있습니다.

#### `run_phase30_final.py`
*   **목적**: **Phase 3 Gate 3 (Final Test Unsealing)** 실행기.
*   **함수 목록 및 기능**:
    *   `run_gate3()`: Test 셋을 봉인 해제하고 최종 성과(Train/Val/Test)를 측정 및 과적합(Degradation) 검사를 수행. **(유지)**
*   **판단**: **[유지]** (현재 시스템의 최종 품질 관문 역할을 하는 핵심 스크립트)

#### `run_phase20_real_gate2.py`
*   **목적**: **Phase 2.0 (Real Data + Gate 2)** 실행기. 리얼 데이터 엔진의 워크포워드(WF) 검증 루프.
*   **판단**: **[유지]** (실운용 전 리얼 데이터 검증용으로 중요)

#### `run_phase15_realdata.py`
*   **목적**: **Phase 1.5 (Real Data Evidence)** 실행기.
*   **기능**: `run_strict_phase15`, `MiniWalkForward`, `MockTelemetry` 등을 포함하여 강력한 재현성 검증 로직 탑재.
*   **판단**: **[유지]** (시스템의 가장 강력한 튜닝/검증 엔진 구현체. 다른 Phase 스크립트들이 이를 import하여 사용함)

#### `run_phase15_clean.py`
*   **목적**: Phase 15의 경량화/단순화 버전.
*   **판단**: **[삭제 고려 / 아카이브]** (기능적으로 `run_phase15_realdata.py`가 상위 호환이므로, 이건 레거시 실험 코드임)

#### `run_phase9_diag.py`
*   **목적**: Phase 9 (Crisis Alpha Strategy) 진단 스크립트.
*   **판단**: **[유지]** (현재 주력 전략인 Phase 9의 로직 검증용)

#### `run_phase8_diag.py`, `run_phase7_2_diag.py`
*   **목적**: 구형 Phase (Phase 8, Phase 7.2) 진단 스크립트.
*   **판단**: **[아카이브 / 삭제 대상]** (이미 지나간 Phase의 스냅샷. 현재는 불필요하나 히스토리 보존 차원에서 `archive/`로 이동 권장)

---

### 2.2 Verification & Diagnostics
데이터 무결성 및 로직 검증용 유틸리티입니다.

#### `verify_paper_logic.py`
*   **목적**: Phase 10 (Paper Trading) 대비 로직 검증.
*   **기능**: `MarketRegimeDetector`를 직접 호출하여 Regime 감지(Bull/Bear/Chop)가 의도대로 동작하는지 시뮬레이션.
*   **판단**: **[유지]** (라이브 로직 검증에 필수)

#### `verify_mock_multilookback.py`
*   **목적**: Mock 데이터 환경에서 Lookback 기간별 동작 차이 검증.
*   **판단**: **[유지/아카이브]** (엔진 무결성 테스트용. CI 용도로 유용하나 자주 쓰이진 않음. 유지 권장)

#### `diagnose_market.py`
*   **목적**: 마켓 데이터(KODEX 200) 로딩 및 컬럼 정규화 테스트.
*   **판단**: **[유지]** (데이터 피드 연동 문제 발생 시 가장 먼저 돌려보는 진단 도구)

#### `debug_alpha_autopsy.py`
*   **목적**: 특정 종목/기간의 알파 팩터(지표) 상세 부검(Autopsy).
*   **기능**: 지표 값, 매매 신호 발생 여부를 Row 단위로 추적하여 JSON/CSV 리포트 생성.
*   **판단**: **[유지]** (전략 디버깅 시 매우 유용한 도구)

#### `debug_core_logic.py`
*   **목적**: 코어 로직(백테스트 엔진) 디버깅. `verify_mock_multilookback.py`와 유사.
*   **판단**: **[삭제 대상]** (`verify_mock_multilookback.py`와 역할 중복. 삭제 권장)

---

### 2.3 Utilities
기타 편의 기능 스크립트입니다.

#### `replay_manifest.py`
*   **목적**: 저장된 백테스트 결과(Manifest)를 다시 실행하여 재현성(Reproducibility) 검증.
*   **판단**: **[유지]** (시스템 신뢰성 보장의 핵심 도구. 절대 삭제 불가)

#### `export_trials.py`
*   **목적**: Optuna 튜닝 결과 DB(`optuna.db`)를 CSV로 내보내고 Top 3 요약 생성.
*   **판단**: **[유지]** (튜닝 결과 분석용 필수 유틸)

#### `convert_docs_encoding.py`
*   **목적**: 문서 파일 인코딩 일괄 변환 (UTF-8).
*   **판단**: **[유지/아카이브]** (일회성 도구이나, 윈도우 환경 협업 시 유용하므로 `scripts/`로 이동하거나 유지)

#### `cat_log.py`
*   **목적**: 윈도우 환경에서 `cat` 명령 대용으로 로그 파일 출력.
*   **판단**: **[삭제 대상]** (단순 쉘 대용 스크립트로 불필요. PowerShell `type` 명령어 등으로 대체 가능)

## 3. 종합 의견 (Summary)
`tools/` 폴더는 실험적 성격의 파일이 많아 정리가 필요합니다.

### 삭제/아카이브 권장 목록
1.  **[삭제]** `debug_core_logic.py`: `verify_mock_multilookback.py` 등과 중복.
2.  **[삭제]** `cat_log.py`: OS 기본 명령어로 대체 가능.
3.  **[아카이브]** `run_phase15_clean.py`: `run_phase15_realdata.py`로 대체됨.
4.  **[아카이브]** `run_phase8_diag.py`, `run_phase7_2_diag.py`: Legacy Phase 코드.

나머지 파일들은 현재 운영 및 검증 프로세스(Phase 2.0, 3.0, 9, 10)에 필수적이므로 **[유지]**해야 합니다.
특히 `run_phase15_realdata.py`, `replay_manifest.py`, `run_phase30_final.py`는 시스템의 근간을 이루는 핵심 실행기입니다.
