# P204-A: 튜닝 엔진(run_tune.py) 구조 정찰 및 다중 구간 평가 도입 타당성 검토

## 1. 정찰 목표
본 백서는 본격적인 Optuna 머신러닝 튜닝 개조(P204 이후 세션)에 앞서, 기존 백테스트 코어 로직의 결합도를 파악하고 **"핵심 백테스트 엔진 수정 없이 다중 구간 평가(Multi-Period) 도입이 가능한지"** 여부를 판독한 정찰 보고서입니다.

---

## 2. 조사 및 분석 결과

### A. 일간 수익률(Daily Returns) 시계열 데이터 반환 여부
- **확인 파일**: `app/tuning/runner.py` 내 `run_single_trial()` 함수
- **분석 결과**: **Yes.** 현재 백테스트 엔진(`BacktestRunner.run()`)은 단순 스칼라 값만 뱉는 것이 아니라, **`nav_history`라는 `(날짜, 누적순자산)` 형태의 원시 시계열 데이터 파이프라인을 튜닝 루프 쪽으로 온전히 반환**하고 있습니다. 
- **현재 처리 방식**: `runner.py` 코드 내부 79번째 줄을 보면, 전달받은 `nav_history` 튜플을 Pandas Series로 변환한 뒤 `.pct_change()`를 먹여 직접 `rets`(일간 수익률 배열)를 추출해 내고 있습니다. 

### B. 다중 구간(Multi-Period) 평가 도입/호출 구조 타당성
- **엔진 비침습성 보장 (Yes)**: 코어 매매 엔진 내부는 전혀 건드릴 필요가 없습니다. 
- **다중 구간 도입 방식 2가지 모두 호환 가능**:
  1. **사후 쪼개기 (Post-processing)**: 한 번의 긴 기간(예: 3년)에 대해 엔진을 호출한 뒤, 반환받은 `nav_history` 시계열 데이터를 튜닝 스크립트(`runner.py`) 단에서 연도별/반기별로 슬라이싱(Slicing)하여 각각의 MDD/Sharpe 판독.
  2. **다중 호출 (Multi-call)**: `app/tuning/runner.py` 안에서 1개의 Trial 당 `BacktestRunner.run(...)`을 Start/End Date를 바꿔가며 여러 번(For loop) 호출.
- **결론**: 두 방법 모두 백테스트 엔진 코어를 단 1줄도 수정하지 않고 `app/tuning/runner.py` (또는 `objective.py`) 레벨의 랩퍼(Wrapper) 조율만으로 즉시 구현이 가능합니다.

### C. Optuna 스토리지 방식 및 로컬 SQLite 전환 타당성
- **현재 스토리지 방식**: `app/run_tune.py` (174번째 줄) 기준, `storage` 파라미터가 명시되지 않은 완벽한 **InMemory(메모리 증발형)** 방식으로 동작하고 있습니다.
- **SQLite 전환 타당성 (Yes/Safe)**: 
  - Optuna 특성상 아키텍처 변경 없이 `optuna.create_study(..., storage="sqlite:///reports/tuning/optuna.db", load_if_exists=True)` 파라미터 단 한 줄만 추가하면 즉각적인 RDB 영속성이 확보됩니다.
  - 현재 시스템 구조상 `reports/tuning/` 경로는 이미 거버넌스 쓰기/읽기가 허용된 합법적 샌드박스이므로 파일 권한 충돌의 위험이 없습니다.

---

## 3. 최종 결론 및 권고 (Executive Summary)

> **"핵심 백테스트 엔진 로직 수정 없이 다중 구간 평가(Multi-Period) 최적화 및 SQLite 영구 저장소 도입은 100% 가능합니다 (YES)."**

**이유:**
엔진(코어)과 튜닝(랩퍼) 간의 **관심사 분리(Separation of Concerns)**가 완벽히 되어 있습니다. 코어 엔진은 무조건 자신의 할 일(특정 기간에 대한 매매 시뮬레이션 후 `nav_history` 시계열 추출)만 묵묵히 수행하여 반환하며, 튜닝 평가자(`runner.py`)가 그 시계열을 마음대로 다룰 수 있는 원시적 접근권을 가지고 있기 때문입니다. 

따라서 다음 ML/Tuning 세션에서는 오직 `app/tuning/` 폴더 내의 로직(`runner.py`, `objective.py`)만 개조하여 다중 구간 페널티 함수를 제작하면 됩니다. 코어 파괴 위험도는 0%입니다.
