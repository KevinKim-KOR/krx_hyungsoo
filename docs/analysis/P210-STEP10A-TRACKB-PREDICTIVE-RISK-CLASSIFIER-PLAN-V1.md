# P210-STEP10A Track B Predictive Risk Classifier — 구현 계획서
> asof: 2026-04-13
> 상태: PLAN (구현 승인 대기)
> 선행 완료: P209-STEP9A/9B/9C + P206-P208 legacy closeout

---

## 0. 이 문서의 목적

P210-STEP10A 구현을 시작하기 전에 다음을 정의한다:
1. 어떤 파일을 어떤 순서로 만들고 수정하는가
2. 각 단계에서 무엇을 검증하는가
3. ML 파이프라인의 누수 방지 메커니즘
4. burn-in 구간 처리 방식
5. 예상 리스크와 완화 방안

---

## 1. 사전 조건 확인 (이미 확인됨)

| 항목 | 상태 |
|---|---|
| price_data 형식 | MultiIndex (code, date), OHLCV 컬럼 (close/open/high/low/volume) |
| 069500 benchmark | dynamic_etf_market 모드에서 자동 로드 |
| rebalance_trace | top_candidates_ranked (rank/code/score) 포함 |
| scikit-learn | requirements.txt 에 `>=1.0.0` 명시 |
| `app/backtest/ml/` | 미존재 → 신규 생성 |
| Step9C 결과 | B1_pos3_raew_pre_entry_guard = CAGR 16.67% / MDD 11.03% 최상위 |

---

## 2. 구현 단계 (순서 고정)

### PHASE 1: SSOT + Validator (코드 변경 최소, 검증 가능)

**목표**: 설정 블록 추가 + param_loader 검증 함수 + SSOT 로드 확인

**파일**:
- `state/params/latest/strategy_params_latest.json` — `trackb_predictive_risk_classifier` + `trackb_predictive_risk_classifier_experiments` 블록 추가
- `app/utils/param_loader.py` — 검증 함수 2개 추가 + `_extract_params_strict` 에 연결

**검증**:
- `load_params_strict()` 호출 시 6개 실험군 정상 로드
- 잘못된 baseline_profile / ml_mode / model_family 입력 시 즉시 ValueError
- `black --check` / `flake8` / `py_compile`

### PHASE 2: ML 파이프라인 핵심 (신규 모듈)

**목표**: `app/backtest/ml/predictive_risk_classifier.py` 신규 생성

**책임 분리 (단일 파일, 내부 함수 분리)**:
```
predictive_risk_classifier.py
├── build_dataset()          — 전체 리밸런스 시점 × 후보 종목 데이터셋 생성
├── generate_labels()        — crash label 생성 (미래 구간, 누수 검증 포함)
├── generate_features()      — feature 생성 (과거 구간만, v1 feature set)
├── check_leakage()          — assertion: feature 날짜 < label 시작 날짜
├── walk_forward_train()     — expanding window 학습 + per-date prediction
├── predict_for_rebalance()  — 단일 리밸런스 시점에서 후보 종목 위험 확률 예측
└── format_training_report() — training_report.md/json 생성
```

**Feature Set v1** (리밸런스 시점에 알 수 있는 값만):

| Feature | 설명 | 데이터 소스 |
|---|---|---|
| `ret_1d`, `ret_3d`, `ret_5d`, `ret_10d`, `ret_20d` | 최근 N일 수익률 | price_data close |
| `vol_5d`, `vol_10d`, `vol_20d` | 실현 변동성 (annualized std) | price_data close |
| `drawdown_from_peak_20d` | 최근 20일 고점 대비 낙폭 | price_data close |
| `vol_spike_5d_20d` | 단기/중기 변동성 비율 | vol_5d / vol_20d |
| `relative_return_vs_069500_5d` | 벤치마크 대비 상대수익률 5일 | price_data close |
| `relative_return_vs_069500_20d` | 벤치마크 대비 상대수익률 20일 | price_data close |
| `scanner_score` | 스캐너 점수 (momentum) | rebalance_trace.top_candidates_ranked |
| `selection_rank` | 선택 순위 | rebalance_trace.top_candidates_ranked |

총 14개 feature (scanner_score / selection_rank 포함). 거래량 변화율은 데이터 품질에 따라 선택적 추가.

**Label 정의**:
- 양성(1): 다음 20영업일 내 `max_drawdown <= -5%` OR `cumulative_return <= -7%`
- 음성(0): 위 조건 미충족
- 라벨 생성: `generate_labels(price_data, ticker, rebalance_date, horizon=20)`
- 누수 방지: `assert feature_date < label_start_date` (check_leakage)

**Walk-Forward Expanding**:
```
리밸런스 시점들: [d1, d2, d3, ..., dN]

d1~d(k-1): train set (k >= min_train_samples / avg_candidates_per_rebalance)
d(k):       predict → crash probabilities for candidates
d(k+1):     train set += d(k) actuals → predict d(k+1) candidates
...
```

### PHASE 3: BacktestRunner 통합 (기존 파일 수정)

**목표**: `backtest_runner.py` 에 ML prediction 수신 + 적용 경로 추가

**핵심 설계**: runner 는 ML 모델을 직접 학습하지 않는다. 외부에서 per-rebalance-date prediction dict 을 받아 selector 단계에서 적용만 한다.

**새 파라미터** (BacktestRunner.run):
```python
ml_crash_predictions: Optional[Dict[str, Dict[str, float]]] = None,
# {rebalance_date_str: {ticker: crash_probability, ...}}
ml_mode: Optional[str] = None,  # "soft_gate" | "hard_gate" | "rerank" | None
ml_probability_threshold_soft: float = 0.55,
ml_probability_threshold_hard: float = 0.70,
ml_top_k_block_limit: int = 1,
trackb_ml_experiment_name: Optional[str] = None,
trackb_baseline_profile: Optional[str] = None,
```

**적용 위치**: selector_after_ranking_before_final_selection (기존 toxic filter 훅과 동일 위치, 별도 분기)

**적용 로직**:
- `soft_gate`: crash_prob >= soft_threshold 인 후보 중 **상위 1개만** 보류 (top_k_block_limit=1). 다음 순위 승격.
- `rerank`: scanner_score 에서 `crash_prob * penalty_weight` 차감하여 순위 재정렬. penalty_weight = Step10A 에서는 1.0 고정.
- `hard_gate`: crash_prob >= hard_threshold 인 후보 전부 제거. (참고용, 우선순위 낮음)

**Burn-in 처리** (지시문 추가 참고):
```python
if ml_crash_predictions is None or rebalance_date_str not in ml_crash_predictions:
    # EXPLICIT BURN-IN FALLBACK: ML 예측 불가 구간.
    # silent fallback 이 아니라 "ML 데이터 부족으로 기존 규칙 유지" 명시 분기.
    # pre_entry_guard 가 활성화된 baseline 은 기존 guard 규칙대로 동작.
    # guard 미활성 baseline 은 무필터 동작.
    _ml_burnin_count += 1
    # → 기존 경로 (guard 있으면 guard, 없으면 plain selection)
```
- 이것은 silent fallback 이 아니라 **명시적 burn-in 분기**
- meta 에 `ml_burnin_rebalance_count` 기록
- evidence / training_report 에 burn-in 구간 길이 명시

**메타 저장** (지시문 요구 17개 필드):
```python
"trackb_ml_experiment_name": trackb_ml_experiment_name,
"trackb_baseline_profile": trackb_baseline_profile,
"trackb_ml_mode": ml_mode,
"trackb_model_family": ...,  # sweep 에서 주입
"trackb_label_horizon_days": ...,
"trackb_label_crash_drawdown_threshold": ...,
"trackb_predicted_positive_count": _ml_predicted_positive_count,
"trackb_soft_gate_hits_total": _ml_soft_gate_hits,
"trackb_hard_gate_hits_total": _ml_hard_gate_hits,
"trackb_rerank_changes_total": _ml_rerank_changes,
"trackb_promoted_candidates_by_rebalance_date": _ml_promoted_by_rebal,
"trackb_avg_candidates_before_ml": ...,
"trackb_avg_candidates_after_ml": ...,
"trackb_ml_burnin_rebalance_count": _ml_burnin_count,
```

### PHASE 4: Sweep + Compare (신규 모듈)

**목표**: `app/backtest/reporting/predictive_risk_compare.py` 신규 생성

**패턴**: `toxic_filter_compare.py` / `contextual_guard_compare.py` 와 동일 아키텍처

**핵심 차이점**: sweep 전에 ML 학습이 먼저 수행되어야 함

**실행 순서**:
```
1. 각 실험군의 baseline profile 에서 max_positions / allocation_mode 해석
2. 해당 baseline 으로 "라벨용 백테스트" 실행 (guard 적용 상태 그대로)
   → rebalance_trace + price_data 에서 dataset 구축
3. walk_forward_train() → per-date predictions dict 생성
4. predictions 를 runner 에 주입하여 "ML 적용 백테스트" 실행
5. formatted result 에서 성능 + ML 메타 수집
6. 전체 실험군 compare 산출물 생성
```

**6개 본선 + 2개 보조군 실험 매트릭스**:

| Variant | Baseline Profile | ML Mode | Model Family |
|---|---|---|---|
| A0_operational_no_ml | operational_control_a0 | none | - |
| A1_operational_soft_gate_lr | operational_control_a0 | soft_gate | logistic_regression |
| A2_operational_rerank_lr | operational_control_a0 | rerank | logistic_regression |
| B0_research_no_ml | research_candidate_b1 | none | - |
| B1_research_soft_gate_lr | research_candidate_b1 | soft_gate | logistic_regression |
| B2_research_rerank_lr | research_candidate_b1 | rerank | logistic_regression |
| (B3_research_soft_gate_rf) | research_candidate_b1 | soft_gate | random_forest |
| (B4_research_rerank_rf) | research_candidate_b1 | rerank | random_forest |

**Compare 산출물**:
- `predictive_risk_compare.md` / `.json` / `.csv`
- Q1~Q4 진단:
  - Q1: soft_gate 가 B1 baseline MDD 낮추는가
  - Q2: rerank 가 hard exclusion 보다 수익 훼손 적은가
  - Q3: LR 만으로 의미 있는 개선 있는가
  - Q4: Step10B 승격 후보 존재하는가
- **predictive_risk_training_report.md** 별도 생성

### PHASE 5: run_backtest.py 통합

**목표**: Full Backtest 실행 시 Step10A sweep 연결

**순서**:
```
1. Main backtest (운영 기준)
2. Step9B toxic_filter sweep (SSOT 에 있으면)
3. Step9C contextual_guard sweep (SSOT 에 있으면)
4. Step10A predictive_risk sweep (SSOT 에 있으면) ← 신규
5. dynamic_evidence_latest.md 생성 (모든 sweep 이후)
6. legacy holding/allocation sweep — 항상 skip
```

**legacy sweep 처리 원칙 (보정, 2026-04-13)**:
지시문 "holding structure 재실험 금지" 에 따라, Step10A 가 활성화된
상태에서는 **full run 에서도 legacy holding/allocation sweep 을 실행하지
않는다**. `analysis_only` 플래그와 무관하게, `trackb_predictive_risk_classifier_experiments`
가 SSOT 에 존재하면 legacy sweep 은 스킵한다. 이는 Step9B/9C 에서도
`analysis_only` 로 처리했던 것을 더 엄격하게 적용하는 것이다.

**format_result** 에 `trackb_*` 메타 15+ 필드 주입 (runner 가 반환하는 값 직접 subscript)

### PHASE 6: Evidence + UI

**evidence_writer.py**:
- `_render_trackb_predictive_risk_section()` 신규 추가
- `predictive_risk_compare.json` 로드하여 비교표 렌더링
- Main Run 의 ML 메타 표시 (burn-in 상태면 burn-in 표시)
- 기존 Track A 섹션 이후, Promotion Verdict 이전에 배치

**UI helpers**:
- `pc_cockpit/views/helpers/predictive_risk_panel.py` 신규 생성
  - `render_predictive_risk_panel_for_parameters(p)` — Parameters 탭
  - `render_predictive_risk_compare_expander(base_dir)` — Backtest 탭
  - `render_predictive_risk_training_expander(base_dir)` — Backtest 탭 (training summary)
  - `render_predictive_risk_evidence_caption(bt_meta)` — Evidence 탭
- `parameter_editor.py` / `workflow.py` 에 helper 호출 연결

---

## 3. Burn-in 구간 처리 상세

### 문제

- `min_train_samples = 200`
- 백테스트 시작 후 약 200 / (avg_candidates_per_rebalance × rebalances_per_month) 개월 동안 ML 학습 불가
- 추정: 3년 백테스트 (2023-04 ~ 2026-04) 에서 약 37개 리밸런스, 평균 7후보 → 첫 ~29개 리밸런스는 학습 데이터 부족 (약 200/7 ≈ 29)
- 이 경우 prediction dict 에 해당 날짜가 **없음**

### 해결

```python
# predictive_risk_classifier.py::walk_forward_train()
for rebal_idx, rebal_date in enumerate(all_rebalance_dates):
    train_data = dataset[dataset["rebalance_date"] < rebal_date]
    if len(train_data) < min_train_samples:
        # burn-in: 이 시점은 예측 불가 → predictions dict 에 key 없음
        training_log.append({
            "predict_date": str(rebal_date),
            "status": "BURN_IN",
            "train_samples": len(train_data),
            "min_required": min_train_samples,
        })
        continue
    # 정상 학습 + 예측
    ...
```

```python
# backtest_runner.py::run() — selector 단계
if ml_crash_predictions is not None and _d_str in ml_crash_predictions:
    # ML 예측 존재 → soft_gate / rerank / hard_gate 적용
    ...
else:
    # EXPLICIT BURN-IN FALLBACK (rule 6/7 준수):
    # ML 데이터 부족 또는 미활성 구간. silent skip 이 아니라
    # "예측 불가 → 기존 규칙 유지" 명시 분기.
    _ml_burnin_count += 1
    # pre_entry_guard 활성 baseline 은 기존 guard 로 동작
    # guard 미활성 baseline 은 plain selection
```

- meta 에 `trackb_ml_burnin_rebalance_count` 기록
- training_report 에 burn-in 구간 수 + 첫 유효 예측 날짜 명시
- evidence 에 burn-in 상태 표시

---

## 4. 누수 방지 체크리스트

| 체크포인트 | 구현 위치 | 방법 |
|---|---|---|
| Feature 는 예측 시점 이전 정보만 | `generate_features()` | `price_data[price_data.index <= rebal_date]` strict 필터 |
| Label 은 예측 시점 이후 구간 | `generate_labels()` | `price_data[rebal_date < index <= rebal_date + horizon]` |
| Train/predict 시간 분리 | `walk_forward_train()` | `train_data["rebalance_date"] < predict_date` strict 부등식 |
| Assertion 검증 | `check_leakage()` | `assert max(feature_dates) < min(label_dates)` per sample |
| Training report 기록 | `format_training_report()` | leakage_check_passed: bool 필드 |

---

## 5. 예상 리스크 및 완화

| 리스크 | 영향 | 완화 |
|---|---|---|
| 학습 데이터 부족 (class imbalance) | crash=1 비율 낮을 수 있음 → 모델이 항상 0 예측 | class_weight="balanced" 사용 + training_report 에 positive_ratio 기록 |
| Burn-in 구간이 길어 유효 예측 구간이 짧음 | 성능 비교 의미 약화 | min_train_samples 를 100 으로 낮추는 보조 실험은 Step10B 로 미룸 |
| rebalance 횟수 적음 (37회/3년) | prediction 표본 부족 | 이번 단계는 "가능성 확인" 목적. 통계적 유의성은 주장하지 않음 |
| feature 수 > 유효 학습 표본 | overfitting | LR 은 regularization (C=1.0), RF 는 max_depth 제한 (5) |
| pipeline 실행 시간 | sweep 8개 × 학습 시간 | walk_forward 는 순차 처리 (지시문 원칙). 병렬 금지 |

---

## 6. 실행 예상 순서 및 검증 포인트

| 단계 | 파일 | 검증 |
|---|---|---|
| PHASE 1 | SSOT + param_loader | `load_params_strict()` 정상 로드 + 잘못된 입력 reject |
| PHASE 2 | `predictive_risk_classifier.py` | unit-level: dataset 생성 → leakage assertion 통과 → walk_forward 실행 → predictions dict 반환 |
| PHASE 3 | `backtest_runner.py` | predictions 주입 후 실행 → trackb_* 메타 17개 반환 |
| PHASE 4 | `predictive_risk_compare.py` | 6~8개 실험군 sweep → compare 산출물 3종 + training_report 생성 |
| PHASE 5 | `run_backtest.py` | `--analysis-only` 로 Full Backtest → sweep 정상 + evidence 반영 + legacy sweep 미재실행 |
| PHASE 6 | evidence + UI | `dynamic_evidence_latest.md` 에 Track B 섹션 존재 + Parameters/Backtest/Evidence UI 표시 |
| FINAL | 정적 게이트 | `black --check` / `flake8` / `py_compile` 전 파일 clean |

---

## 7. 수정 금지 범위 재확인

- dynamic scanner / hybrid B+D / safe asset / allocation 로직 변경 금지
- holding structure / Tune 재실행 금지
- live 경로 주입 / 운영 SSOT 자동 승격 금지
- deep learning / LLM / 외부 API 예측 금지
- objective / verdict 기준 (CAGR>15, MDD<10) 변경 금지
- 새 UI 페이지 추가 금지
- znotes/ 접근 금지

---

## 8. 최종 산출물 목록

### 신규 파일
- `app/backtest/ml/__init__.py`
- `app/backtest/ml/predictive_risk_classifier.py`
- `app/backtest/reporting/predictive_risk_compare.py`
- `pc_cockpit/views/helpers/predictive_risk_panel.py`

### 수정 파일
- `state/params/latest/strategy_params_latest.json`
- `app/utils/param_loader.py`
- `app/backtest/runners/backtest_runner.py`
- `app/run_backtest.py`
- `app/backtest/reporting/evidence_writer.py`
- `pc_cockpit/views/workflow.py`
- `pc_cockpit/views/parameter_editor.py`

### 산출물 (gitignore, 매 실행 재생성)
- `reports/tuning/predictive_risk_compare.md` / `.json` / `.csv`
- `reports/tuning/predictive_risk_training_report.md` / `.json`
- `reports/tuning/dynamic_evidence_latest.md` (Track B 섹션 추가)
- `reports/backtest/latest/backtest_result.json` (trackb_* 메타 주입)

---

## 9. 구현 기본안 (지시문에 의해 고정, 별도 승인 불요)

아래 항목은 지시문이 이미 충분히 고정했으므로 별도 승인 대기 없이
구현 기본안으로 확정한다.

- **PHASE 순서**: PHASE 1~6 순서대로 순차 진행
- **Feature Set v1**: 위 14개 feature 구성 그대로 사용 (scanner_score / selection_rank 포함)
- **Burn-in fallback**: prediction dict 에 key 없으면 기존 규칙 유지 +
  meta 기록. rule 6/7 위반이 아닌 명시적 분기 (baseline-aware fallback)
- **모델 하이퍼파라미터**: LR: C=1.0, penalty="l2", class_weight="balanced" /
  RF: n_estimators=100, max_depth=5, class_weight="balanced". 이 단계 튜닝 금지
- **보조군 B3/B4**: 본선 6개만 먼저 구현. RF 보조군은 본선 완료 후 필요 시 추가

즉시 PHASE 1 부터 구현을 시작한다.
