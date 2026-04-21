# ML 자산 화이트리스트 (2026-04-21)

목적: krx_alertor_modular 에서 "ML 관련 자산"만 추출한 복사 대상 목록.
정의: Track B predictive_risk_classifier 관련 학습·feature·예측·compare 파이프라인.
제외: Main Run 엔진, UI/Streamlit, SSOT 저장 로직, OCI crontab, Telegram.

---

## 복사 대상 파일 (Whitelist)

### 1) ML 코어 (train/predict/feature/label)
- [app/backtest/ml/__init__.py](../../app/backtest/ml/__init__.py): Track B ML 패키지 엔트리, `build_predictions_for_sweep` / `format_training_report` 재노출
- [app/backtest/ml/predictive_risk_classifier.py](../../app/backtest/ml/predictive_risk_classifier.py): dataset build + label(L0/L1/L2 profile) + feature(v1 14개) + leakage check + walk-forward train/predict + training report (LR/RF)

### 2) ML Sweep 하니스 (compare run 전용)
- [app/backtest/reporting/predictive_risk_compare.py](../../app/backtest/reporting/predictive_risk_compare.py): 실험군(A0~A3, B0~B3) sweep, ML 학습 + backtest 호출 + compare.json/csv/md + training_report 산출

### 3) SSOT 스키마 검증 (ML 설정 블록 한정)
- [app/utils/param_loader.py](../../app/utils/param_loader.py): `_validate_trackb_predictive_risk_classifier` + `_validate_trackb_predictive_risk_experiments` + `_ALLOWED_TRACKB_*` enum들 (264~430 라인 근방. ML 스키마 검증만 발췌 필요)

### 4) SSOT 파라미터 블록 (참조용 견본)
- [state/params/latest/strategy_params_latest.json](../../state/params/latest/strategy_params_latest.json): `trackb_predictive_risk_classifier` + `trackb_predictive_risk_classifier_experiments` 8실험 정의 (295~380 라인)

### 5) 설계 문서
- [docs/analysis/P210-STEP10A-TRACKB-PREDICTIVE-RISK-CLASSIFIER-PLAN-V1.md](../analysis/P210-STEP10A-TRACKB-PREDICTIVE-RISK-CLASSIFIER-PLAN-V1.md): Track B 설계 원본
- [docs/handoff/P209_STEP9C_close_and_TrackB_handoff.md](P209_STEP9C_close_and_TrackB_handoff.md): Track A → Track B 전환 핸드오프
- [docs/handoff/P210_STEP10A_close_and_STEP10B_handoff.md](P210_STEP10A_close_and_STEP10B_handoff.md), [docs/handoff/P210_STEP10A2_close_and_STEP10B_handoff.md](P210_STEP10A2_close_and_STEP10B_handoff.md), [docs/handoff/P210_STEP10C_close_and_phase2_handoff.md](P210_STEP10C_close_and_phase2_handoff.md): Step10 진행 handoff

### 6) 산출물 샘플 (참조용)
- [reports/tuning/predictive_risk_compare.json](../../reports/tuning/predictive_risk_compare.json), .csv, .md
- [reports/tuning/predictive_risk_training_report.json](../../reports/tuning/predictive_risk_training_report.json), .md

---

## 의존성 (프로젝트 내)

- [app/backtest/ml/__init__.py](../../app/backtest/ml/__init__.py)
  → `app.backtest.ml.predictive_risk_classifier` (`build_predictions_for_sweep`, `format_training_report`)

- [app/backtest/ml/predictive_risk_classifier.py](../../app/backtest/ml/predictive_risk_classifier.py)
  → 외부만: numpy, pandas, sklearn.linear_model.LogisticRegression, sklearn.ensemble.RandomForestClassifier. **프로젝트 내부 import 0건** (완전 독립)

- [app/backtest/reporting/predictive_risk_compare.py](../../app/backtest/reporting/predictive_risk_compare.py)
  → `app.backtest.ml.build_predictions_for_sweep`, `app.backtest.ml.format_training_report`
  → `run_backtest_fn`, `format_result_fn` (Callable 주입, 직접 import 없음)
  → 외부: csv, json, datetime, pathlib

- [app/utils/param_loader.py](../../app/utils/param_loader.py) (ML 관련 함수만)
  → 외부만. 프로젝트 내부 import 없음 (ML 검증 섹션 한정)

## Main Run 엔진 측 훅 포인트 (복사 대상 아님, 新 프로젝트에서 재설계)

`BacktestRunner.run` 이 ML 예측을 받는 인터페이스 (제외 대상이지만 계약 확인용):
- [app/backtest/runners/backtest_runner.py](../../app/backtest/runners/backtest_runner.py) 라인 407~418: `ml_crash_predictions`, `ml_mode`(soft_gate/rerank/hard_gate), `ml_probability_threshold_soft/hard`, `ml_top_k_block_limit`, `ml_penalty_weight`
- 라인 955~1080: 후보 선정 루프 내부의 ML overlay (soft_gate/rerank/hard_gate 분기)
- [app/run_backtest.py](../../app/run_backtest.py) 라인 105, 338, 1647~1673: `run_predictive_risk_sweep` 디스패치

---

## 경계선상 (판단 필요)

- [app/utils/param_loader.py](../../app/utils/param_loader.py): 전체 파일은 SSOT/Main Run 전반의 파라미터 검증기. 복사 시 `_validate_trackb_*` 함수만 발췌하거나 전체 복사 후 新 프로젝트 맞게 조정 필요

- [app/backtest/reporting/experiment_registry.py](../../app/backtest/reporting/experiment_registry.py): `predictive_risk_compare.json` 을 읽어 실험 registry 를 만드는 모듈. Track A(contextual_guard) 와 Track B 를 같이 처리. 新 프로젝트 운영 레이어에서 필요 여부 미정

- [app/backtest/reporting/evidence_writer.py](../../app/backtest/reporting/evidence_writer.py) 라인 800~820: `predictive_risk_compare.json` 을 읽어 evidence 에 렌더. SSOT/Main Run evidence 에 묶여있어 제외가 타당하나, ML 결과를 別도로 보고 싶으면 부분 추출 후보

- [pc_cockpit/views/helpers/predictive_risk_panel.py](../../pc_cockpit/views/helpers/predictive_risk_panel.py): UI(Streamlit) 이므로 규칙상 제외. 但 비-UI 로직(데이터 로딩/정규화)이 섞여있으면 新 프로젝트가 다시 씀

- [app/backtest/reporting/handoff_pack.py](../../app/backtest/reporting/handoff_pack.py) 라인 42, 188: `predictive_risk_compare.json` 참조. handoff 자동 감지 용도. 복사 여부는 新 프로젝트 운영 정책 의존

- [docs/handoff/HANDOFF_P204_ML.md](HANDOFF_P204_ML.md) / HANDOFF_P204_ML.json / _CHECKLIST.md: "P204 ML" 이름이지만 2026-04-21 현재 Track B(P210) 와는 별개 historical 문서. ML 용어만 겹침, Track B 와 직접 연결 없음
