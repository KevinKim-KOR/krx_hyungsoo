# P210-STEP10A Track B Predictive Risk Classifier 종료 + P210-STEP10B Hand-off
> asof: 2026-04-13
> 상태: **완료** (구현 + 실행 검증 완료, 결과는 no-op/negative)
> 직전 문서: [P209_STEP9C_close_and_TrackB_handoff.md](P209_STEP9C_close_and_TrackB_handoff.md)

---

## 0. 이 문서의 목적

P210-STEP10A Track B ML classifier 연구 챕터를 종료하고,
다음 단계로 넘기는 hand-off 문서.

---

## 1. Step10A 결론: ML pipeline 정상 작동, 실제 개입 0회

### 1.1 실행 결과

6개 실험군 (A0~A2, B0~B2) sweep 이 정상 완료됨.
그러나 **ML 이 단 한번도 실제 예측/게이트 개입을 하지 못했음**.

| Rank | Variant | Profile | ML Mode | CAGR | MDD | Soft Gate | Rerank | Burnin | Verdict |
|---:|---|---|---|---:|---:|---:|---:|---:|---|
| 1 | B0_research_no_ml | research_candidate_b1 | none | **16.682%** | **11.028%** | 0 | 0 | 0 | REJECT |
| 2 | B1_research_soft_gate_lr | research_candidate_b1 | soft_gate | 16.682% | 11.028% | 0 | 0 | 28 | REJECT |
| 3 | B2_research_rerank_lr | research_candidate_b1 | rerank | 16.682% | 11.028% | 0 | 0 | 28 | REJECT |
| 4 | A0_operational_no_ml | operational_control_a0 | none | 12.411% | 12.745% | 0 | 0 | 0 | REJECT |
| 5 | A1_operational_soft_gate_lr | operational_control_a0 | soft_gate | 12.411% | 12.745% | 0 | 0 | 28 | REJECT |
| 6 | A2_operational_rerank_lr | operational_control_a0 | rerank | 12.411% | 12.745% | 0 | 0 | 28 | REJECT |

### 1.2 원인: 데이터 규모 한계

- `min_train_samples = 200`
- `total_labeled_samples = 183` (전 기간)
- `predicted_dates = 0` / `burnin_dates = 28` / `total_rebalance_dates = 28`
- 즉 **학습에 필요한 최소 데이터가 전 기간에 걸쳐서도 확보되지 못함**
- `positive_ratio = 71.0%` (183개 중 130개 양성) — 양성이 매우 많은 불균형

결론: 파이프라인 구현 오류가 아니라 **3년 backtest 기간 × 15종목 universe 규모에서
min_train_samples=200 의 walk-forward expanding 은 한번도 학습/예측에 진입 불가**.

### 1.3 Main Run 대표 성능 (변동 없음)

| 지표 | 값 |
|---|---:|
| CAGR | 12.4111% |
| MDD | 12.7446% |
| Sharpe | 1.1035 |
| Verdict | **REJECT** |

### 1.4 연구 최고 후보 (변동 없음)

`B0_research_no_ml` (= `g4_pos3_raew` + `pre_entry_guard`): CAGR 16.682% / MDD 11.028%
— ML 이 개입하지 못했으므로 Step9C 의 `B1_pos3_raew_pre_entry_guard` 결과와 동일.

---

## 2. 구현 파일 목록

### 신규 파일 4개
- `app/backtest/ml/__init__.py`
- `app/backtest/ml/predictive_risk_classifier.py` (~560줄)
- `app/backtest/reporting/predictive_risk_compare.py` (~540줄)
- `pc_cockpit/views/helpers/predictive_risk_panel.py` (~200줄)

### 수정 파일 7개
- `state/params/latest/strategy_params_latest.json` — `trackb_*` 2개 블록
- `app/utils/param_loader.py` — 검증 함수 2개 + 상수 4개
- `app/backtest/runners/backtest_runner.py` — ML overlay 로직 + trackb_* 메타 14개
- `app/run_backtest.py` — sweep 연결 + format_result trackb_* 메타 + ML 파라미터 전달
- `app/backtest/reporting/evidence_writer.py` — Track B 섹션 렌더러
- `pc_cockpit/views/parameter_editor.py` — helper 호출
- `pc_cockpit/views/workflow.py` — compare/training/evidence helper 호출

### 산출물 (매 실행 재생성)
- `reports/tuning/predictive_risk_compare.md/.json/.csv`
- `reports/tuning/predictive_risk_training_report.md/.json`
- `reports/tuning/dynamic_evidence_latest.md` (Track B 섹션)
- `reports/backtest/latest/backtest_result.json` (trackb_* 14필드)

---

## 3. ML 파이프라인 구조 (정상 작동 검증됨)

### Feature Set v1 (14개)
ret_1d/3d/5d/10d/20d, vol_5d/10d/20d, drawdown_from_peak_20d,
vol_spike_5d_20d, relative_return_vs_benchmark_5d/20d, scanner_score,
selection_rank

### Label 정의
양성(1): 다음 20영업일 내 max_dd <= -5% OR cum_return <= -7%

### 학습
walk_forward_expanding, LR (C=1.0, l2, balanced), min_train_samples=200

### Leakage check
assertion 검증 통과 (max feature_date < min label_date)

### Burn-in 처리
prediction dict 에 key 없으면 기존 규칙 유지 (명시적 분기, meta 기록)

### Guard 계약 보존
ML overlay 는 guard 이후 결과 위에서만 동작.
soft_gate 승격 소스 = guard_survived_pool.
rerank 대상 = guard_survived_pool 전체 재정렬.
guard 탈락 후보 부활 불가.

---

## 4. Step10B 진입 가이드

### 4.1 가용 옵션

**Option 1 — min_train_samples 하향 (e.g. 50~100)**
- 현재 183개 labeled samples 로도 학습 가능하게
- 장점: 구현 변경 최소 (SSOT 값만 변경)
- 단점: overfitting 리스크 증가, 모델 안정성 저하

**Option 2 — label_horizon 축소 (e.g. 10일)**
- 더 많은 labeled samples 확보 가능
- 장점: 같은 데이터로 더 많은 학습 표본
- 단점: 예측 의미가 달라짐 (단기 crash vs 중기 crash)

**Option 3 — RF 보조군 추가 (B3/B4)**
- 계획서에 선택적 보조군으로 이미 정의됨
- min_train_samples 하향과 병행 시 효과 검증 가능

**Option 4 — P210 전체 종료 선언**
- Track A (규칙) + Track B (ML) 모두 현재 데이터 규모에서 한계 확인
- CAGR>15 AND MDD<10 동시 달성은 현재 universe/regime 조합에서 불가 판정
- 승격 기준 재검토 또는 universe 확장으로 전환

**권장**: Option 1 (min_train_samples 하향) 을 먼저 시도.
SSOT 값 변경만으로 재실행 가능.

### 4.2 절대 금지
- live 경로 주입 금지
- 운영 SSOT 자동 승격 금지
- deep learning / LLM / 외부 API 금지

---

## 5. 검증 증거

- 실행: `--analysis-only` Full Backtest (2026-04-13 17:19)
- legacy sweep: `holding_structure 15:48 / allocation 15:48` 불변
- 정적 게이트: `black --check / flake8 / py_compile` clean
- evidence Track B 섹션: L132~ 존재
- backtest_result trackb_* 14필드: 전체 존재
