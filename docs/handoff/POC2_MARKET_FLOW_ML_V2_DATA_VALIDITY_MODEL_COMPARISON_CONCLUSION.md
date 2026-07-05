# Market Flow ML v2 — Data Validity + Model Comparison Conclusion (DONE)

작성일: 2026-07-05
성격: Ridge 부진 원인이 ETF breadth·coverage 데이터인지, feature 구성 자체인지 분리 측정. 시장 판단 UI / 자동 매매 / AI Sessions 연결 작업이 아니다.

---

## 1. 완료 판정 — DONE

지시문 §13 AC-1 ~ AC-13 모두 충족. `status=ok`, 공통 예측 110 건, 제외 1건 (`feature_row_missing_on_kodex_date`), coverage quartile Q1~Q4 각 28/27/27/28, 연도별 요약 10 구간. 기존 baseline / walk-forward artifact 미변경. Full Ridge / Core Ridge / Simple Baseline 세 모델의 전체·연도별·coverage 분위별 metrics 산출.

---

## 2. 사용 SQLite 범위

`state/market/market_data.sqlite` read only. 외부 API / FDR / Yahoo / pykrx / KRX CSV 호출 0건 (자동 테스트 `test_14_no_external_calls` 검증).

`build_dataset()` 은 전체 SQLite snapshot 에서 **1회** 계산 (Q2 (a) 확정).

---

## 3. 세 예측 방식 정의 (§6)

### 3.1 Full Ridge — 13 feature (기존)

| 카테고리 | 컬럼 |
|---|---|
| 시장 가격 흐름 | `kodex200_return_5d_pct`, `kodex200_return_20d_pct`, `kospi_return_5d_pct`, `kospi_return_20d_pct` |
| ETF breadth | `etf_breadth_positive_ratio_20d`, `etf_breadth_median_return_20d_pct`, `etf_breadth_spread_p90_p10_20d_pct` |
| VIX | `vix_close_lagged`, `vix_return_5obs_pct`, `vix_return_20obs_pct` |
| Coverage | `etf_eligible_count`, `etf_coverage_count_20d`, `etf_coverage_ratio_20d` |

### 3.2 Core Ridge — 7 feature

| 카테고리 | 컬럼 |
|---|---|
| 시장 가격 흐름 | `kodex200_return_5d_pct`, `kodex200_return_20d_pct`, `kospi_return_5d_pct`, `kospi_return_20d_pct` |
| VIX | `vix_close_lagged`, `vix_return_5obs_pct`, `vix_return_20obs_pct` |

(ETF breadth 3개 + Coverage 3개 제외.)

### 3.3 Simple Baseline

각 기준일의 동일 training row target 평균.

---

## 4. 공통 Walk-forward 계약 (§5)

- **공통 grid**: KODEX200 거래일 index 기준 20 간격 고정 (walk-forward v1 그대로).
- **Anchor `t0`**: `target_end_date < t0` labeled row ≥ 756 + t0 feature 확보 + t0 이후 20 KODEX 거래일 target 확보.
- **공통 학습 범위**: Simple / Full / Core 세 모델이 **동일한 as_of_date / training row / actual target / target_end_date** 를 사용. Core Ridge 가 feature 수가 적다는 이유로 더 많은 기준일을 사용하는 것을 금지 (자동 테스트 `test_2` / `test_4` 검증).
- **Full feature 부재 시**: 세 모델 모두 제외 + 사유 기록 (자동 테스트 `test_7`).
- **scaler/model fit**: 각 기준일마다 Full/Core scaler + Ridge 새로 fit (Q1 (b) numpy 명시).
- **skip 후 grid 유지**: walk-forward v1 계약 동일 (`test_6`).

---

## 5. 산출물

- `state/ml/market_flow_v2_data_validity_latest.json` — target 분포 + coverage 분포 · 분위 (§8.1).
- `state/ml/market_flow_v2_model_comparison_predictions_latest.csv` — 공통 예측 행별 상세 (§8.2, `coverage_quartile` 포함).
- `state/ml/market_flow_v2_model_comparison_latest.json` — summary (§8.3).

**기존 artifact 미변경** (자동 테스트 `test_15`):
- `state/ml/market_flow_baseline_latest.json` — 그대로 (generated_at `2026-07-05T06:54:55Z`).
- `state/ml/market_flow_training_dataset_latest.csv` — 그대로.
- `state/ml/market_flow_walk_forward_latest.json` — 그대로.
- `state/ml/market_flow_walk_forward_predictions_latest.csv` — 그대로.

---

## 6. 실측 결과 (real SQLite, 2026-07-05)

### 6.1 실행 조건

| 항목 | 값 |
|---|---|
| status | ok |
| 공통 예측 수 | 110 |
| 제외 예측 수 | 1 (`feature_row_missing_on_kodex_date`) |
| 평가 기간 | 2017-07-06 ~ 2026-06-01 |
| Anchor gate | 756 학습 행 (`target_end_date < t0`) |
| Grid 간격 | KODEX200 거래일 20 |
| sklearn / numpy | 1.9.0 / 2.4.6 |

### 6.2 전체 성능

| Metric | Simple Baseline | Full Ridge (13) | Core Ridge (7) |
|---|---|---|---|
| MAE | 5.0685 | 5.2466 | **4.9499** |
| RMSE | 7.9827 | 7.8969 | **7.7084** |
| directional_accuracy | 0.5727 | 0.5273 | **0.5909** |

Diff:
- Full - Simple: MAE +0.1781 / RMSE −0.0857 / DA −0.0455
- Core - Simple: MAE **−0.1186** / RMSE **−0.2742** / DA **+0.0182**
- Full - Core: MAE +0.2967 / RMSE +0.1885 / DA −0.0636

### 6.3 Coverage quartile (진단용, §7.3)

- 경계 (numpy quantile method="linear"): q25=0.2528 / q50=0.3679 / q75=0.6090
- Q1 count=28 / Q2 count=27 / Q3 count=27 / Q4 count=28

| Quartile | Simple DA | Full DA | Core DA |
|---|---|---|---|
| Q1 (낮은 coverage) | 0.5714 | 0.5357 | 0.7500 |
| Q2 | 0.6296 | 0.5185 | 0.5556 |
| Q3 | 0.4815 | 0.5185 | 0.4074 |
| Q4 (높은 coverage) | 0.6071 | 0.5357 | 0.6429 |

**해석은 남기지 않는다** (지시문 §8.3 금지). 성능 판정 · 모델 채택 · 폐기는 다음 별도 설계 판단에서.

---

## 7. 자동 테스트 결과

| 항목 | 결과 |
|---|---|
| backend 전체 | **772 passed** (755 → 772, 신규 17) |
| black `--check app tests scripts` | PASS |
| flake8 `app tests scripts` | PASS |
| frontend lint / build | 변경 없음 (지시문 §10 UI 금지) |

**신규 테스트 17건** — `tests/test_market_flow_v2_model_comparison.py`:
§11.1 ~ §11.17 (일부는 유사 grouping으로 결합) — Full/Core 정확 분리 / 세 모델 공통 학습 / target_end_date 누수 방지 / scaler refit / simple baseline mean 일치 / grid+skip / Full 부재 시 세 모델 동시 제외 / error·direction 정의 / target 분포 연도 일치 / coverage 통계 공통 row 기준 / quartile numpy_linear / 동점 empty unavailable / 전체·연도·분위 metrics CSV 일치 / 외부 호출 없음 / 기존 artifact 미변경 / 재현성 / summary schema.

---

## 8. 알려진 한계

- **역사적 ETF universe 생존 편향**: 현재 SQLite 는 상장폐지된 과거 ETF 를 포함하지 않음. 초기 구간 coverage (2017년 앞부분) 은 낮음 (지시문 §2 명시).
- **Core Ridge 도 evidence**: v2 는 세 모델을 공정 비교하는 evidence 산출이지 채택·폐기 판정 아님 (지시문 §3 명시). Ridge baseline v1 은 여전히 시장 판단 근거 참조점수 이상의 용도로 사용 금지.
- **Coverage quartile 은 사후 진단용**: 학습·기준일 제외·feature 계산·예측값에 절대 사용하지 않음 (지시문 §7.3 명시).

---

## 9. 변경 파일 목록

**신규** (v2 코드는 책임별 3 모듈로 분리 — FIX r1 B-2/B-3 정정):
- `app/market_flow_v2_predictor.py` — feature 상수 (Full 13 / Core 7) + 세 모델 예측 함수 (137 줄).
- `app/market_flow_v2_diagnostics.py` — target 분포 / coverage 분포 / quartile 계산 · 배정 / 모델 metrics 집계 (299 줄).
- `app/market_flow_v2_model_comparison.py` — main runner + artifact writer + monkeypatch 재-export (298 줄).
- `scripts/run_market_flow_v2_model_comparison.py`
- `tests/test_market_flow_v2_model_comparison.py`
- `docs/handoff/POC2_MARKET_FLOW_ML_V2_DATA_VALIDITY_MODEL_COMPARISON_CONCLUSION.md` (본 문서)

**수정**:
- `requirements.txt` (numpy==2.4.6 명시 고정 — Q1 (b) 확정)
- `.gitignore` (v2 artifact 3 경로 추가)
- `docs/STATE_LATEST.md`
- `docs/handoff/POC2_B_NEXT_ACTIONS.md`
- `docs/handoff/POC2_FEATURE_INVENTORY.md` (2.41 신규 entry)
- `docs/handoff/POC2_MARKET_FIRST_OPERATING_DIRECTION.md`
- `docs/backlog/BACKLOG.md`

`docs/MASTER_PLAN.md` 는 지시문 §12 대로 변경하지 않음.

---

## 10. AC 충족 (지시문 §13)

| AC | 결과 |
|---|---|
| AC-1 SQLite 만 read + 외부 호출 없음 | ✅ (`test_14`) |
| AC-2 Full 13 / Core 7 feature artifact 명시 | ✅ (summary `model_definitions`) |
| AC-3 세 모델 동일 기준일·학습 행·실제 target | ✅ (`test_2`, 단일 함수 내 fit) |
| AC-4 `target_end_date < as_of_date` 유지 | ✅ (`test_3`) |
| AC-5 기준일별 scaler / Ridge 새로 fit | ✅ (`test_4`) |
| AC-6 target 분포 연도별 기록 | ✅ (`data_validity.target_distribution_by_target_end_year`) |
| AC-7 coverage 분포 전체·연도별·분위별 기록 | ✅ |
| AC-8 quartile 은 진단용 (행 제외 · 채택 · 행동 기준 X) | ✅ (`test_12` 동점 empty unavailable) |
| AC-9 세 모델 전체·연도·분위별 MAE·RMSE·DA | ✅ (`metrics` / `yearly_metrics_by_target_end_year` / `coverage_quartile_metrics`) |
| AC-10 기존 baseline·walk-forward artifact 미변경 | ✅ (`test_15` sentinel + generated_at 확인) |
| AC-11 신규 API·DB·UI·자동 행동 없음 | ✅ |
| AC-12 기존 축1·Discovery·Holdings·Preview·Sessions·PENDING·OCI·Telegram 미변경 | ✅ |
| AC-13 real SQLite + 테스트 + 정적 검사 통과 | ✅ (772 passed) |

---

## 11. 다음 활성 Step

- 미결정 (설계자 지정 대기).
- v2 evidence 를 기반으로 한 후속 판단 (feature 조합 · target 재정의 등) 은 별도 STEP.
