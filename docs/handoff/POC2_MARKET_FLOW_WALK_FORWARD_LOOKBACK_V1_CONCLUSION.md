# Market Flow ML Walk-forward Lookback v1 — Conclusion (DONE)

작성일: 2026-07-05
성격: Ridge baseline v1 의 과거 반복 성능을 evidence 로 남기는 룩백 실행. 시장 판단 UI / 자동 매매 / AI Sessions 연결 작업이 아니다.

---

## 1. 완료 판정 — DONE

지시문 §13 AC-1 ~ AC-12 모두 충족. `state=ok`, 예측 110 건, 제외 1 건 (`feature_row_missing_on_kodex_date`), 연도별 요약 10 구간 (2017 ~ 2026), Ridge · simple baseline 전체 성능 산출, 기존 baseline artifact 미변경. FIX r1 로 grid 기준을 labeled row index → KODEX200 거래일 index 로 정정 (지시문 Q2 (a) 확정).

---

## 2. 사용 SQLite 범위

`state/market/market_data.sqlite` read only. 외부 API / FDR / Yahoo / pykrx / KRX CSV 호출 0건 (자동 테스트 `test_12_no_external_data_calls` 검증).

- KODEX200 / KOSPI / VIX / ETF universe / breadth / coverage — 기존 `build_dataset()` 재사용 (한 번 계산).

---

## 3. Walk-forward 학습 규칙 (지시문 §5)

### 3.1 데이터 누수 방지 (§5.2)

- `build_dataset()` 은 전체 SQLite snapshot 에서 **1회** 만들고 재사용 (feature 정의 자체가 forward-looking 을 배제 — 5d/20d lookback + VIX strictly-prior).
- 각 예측 기준일 `t` 마다:
  1. `target_end_date < t` 인 labeled row 만 training subset 으로 filter.
  2. StandardScaler 를 해당 subset 에만 **새로 fit**.
  3. Ridge(alpha=1.0) 를 해당 subset 에만 **새로 fit**.
  4. `t` 시점 feature 를 transform 후 예측.
- 전체 기간 fit scaler / 모델 재사용 **금지**.

### 3.2 Anchor 및 grid (§5.1, Q2 (a) 확정 — FIX r1 정정)

- **최초 anchor t0**: 아래 조건을 모두 만족하는 가장 이른 **KODEX200 거래일**.
  - `target_end_date < t0` 인 labeled row 가 **756 개 이상**.
  - t0 feature 계산 가능 (labeled row 존재).
  - t0 이후 정확히 20 번째 KODEX200 거래일 actual target 존재.
- **이후 기준일**: **KODEX200 거래일 index 기준** 20 간격 고정 grid (`t0, t0+20, t0+40, ...`). labeled row index 가 아님 — build_dataset 결과에는 excluded (kodex/kospi lookback insufficient / target horizon unavailable) 된 KODEX 거래일이 빠져 있으므로.
- 중간 후보에서 feature 부재 / actual target 부재 / dataset builder 와 KODEX 시퀀스 불일치 시 → prediction row 미생성, `excluded_reason_counts` 기록. **다음 후보는 여전히 20 KODEX 거래일 뒤 grid 위치 유지 (skip 이 grid 를 밀지 않음)**. 자동 테스트 `test_3` / `test_3b` 로 검증.

### 3.3 단순 기준 예측 (§5.3)

각 기준일마다 동일 training subset 의 target 평균을 `simple_baseline_prediction_pct` 로 기록. Ridge 와 simple baseline 은 **반드시 동일한 학습 범위** 사용 (자동 테스트 `test_6` / `test_7` 검증).

---

## 4. 산출물

- `state/ml/market_flow_walk_forward_predictions_latest.csv` — 예측 행별 상세.
- `state/ml/market_flow_walk_forward_latest.json` — summary (`schema_version=market_flow_walk_forward_v1`).

**기존 baseline artifact 미변경** (자동 테스트 `test_13` 검증):
- `state/ml/market_flow_baseline_latest.json` — 그대로.
- `state/ml/market_flow_training_dataset_latest.csv` — 그대로.

---

## 5. 실측 결과 (real SQLite, 2026-07-05)

| 항목 | 값 |
|---|---|
| status | ok |
| prediction_count | 110 |
| excluded_prediction_count | 1 (`feature_row_missing_on_kodex_date`) |
| evaluation.start_date | 2017-07-06 |
| evaluation.end_date | 2026-06-01 |
| yearly buckets | 10 (2017 ~ 2026) |
| model | standard_scaler_ridge, ridge_alpha=1.0, sklearn 1.9.0 |

### 5.1 전체 성능

| Metric | Ridge | simple_baseline | ridge - simple |
|---|---|---|---|
| MAE | 5.2466 | 5.0685 | +0.1781 |
| RMSE | 7.8969 | 7.9827 | −0.0857 |
| directional_accuracy | 0.5273 | 0.5727 | −0.0455 |

**해석은 남기지 않는다** (지시문 §6 금지). 성능 판정은 다음 별도 설계 판단에서 한다.

### 5.2 연도별 (target_end_date 연도 기준)

`state/ml/market_flow_walk_forward_latest.json` 의 `yearly_metrics` 참조. 10 개 연도 (2017 ~ 2026) 모두 존재.

---

## 6. AC 충족 (지시문 §13)

| AC | 결과 |
|---|---|
| AC-1 target_end_date < as_of_date 조건 학습 | ✅ (`test_1`) |
| AC-2 최초 예측 756 이상 gate | ✅ (`test_2`) |
| AC-3 KODEX200 거래일 index 기준 20 간격 고정 grid (skip 이 grid 를 밀지 않음) | ✅ (`test_3` + `test_3b`) |
| AC-4 target = 이후 정확히 20 번째 KODEX200 거래일 수익률 | ✅ (`test_4`) |
| AC-5 Ridge / simple baseline 동일 학습 범위 | ✅ (`test_6` / `test_7`) |
| AC-6 전체 metrics 산출 | ✅ (summary artifact) |
| AC-7 연도 단위 요약 | ✅ (`yearly_metrics` 10 개) |
| AC-8 기준일 이후 정보 미포함 | ✅ (`test_5` scaler fit 검증) |
| AC-9 기존 baseline artifact 유지 | ✅ (`test_13`) |
| AC-10 외부 호출 / 신규 API / DB table / UI / 자동 행동 없음 | ✅ |
| AC-11 기존 축1·Discovery·Holdings·Preview·Sessions·PENDING·OCI·Telegram 미변경 | ✅ |
| AC-12 실제 SQLite 실행 + 테스트 + 정적 검사 통과 | ✅ |

---

## 7. 자동 테스트 결과

| 항목 | 결과 |
|---|---|
| backend 전체 | **755 passed** (738 → 755, 신규 17) |
| black `--check app tests scripts` | PASS |
| flake8 `app tests scripts` | PASS |
| frontend lint / build | 변경 없음 (지시문 §10 UI 금지) |

**신규 테스트 17건** — `tests/test_market_flow_walk_forward.py`:
1. training row 는 `target_end_date < as_of_date` 만
2. anchor 는 756 gate 통과 (KODEX200 거래일 기준)
3. KODEX200 거래일 index 기준 20 간격 고정 grid
3b. skip 이 grid 를 밀지 않음 (FIX r1 신규)
4. target = 20 번째 KODEX200 거래일 수익률
5. scaler 는 training subset 만 fit (anchor 이후 데이터 접근 없음)
6. Ridge / simple baseline 동일 training 범위
7. simple baseline = training target 평균
8. 오차·방향 일치 정의대로
9. 연도별 요약 = prediction CSV 일치
10. training row 부족 시 unavailable + 사유 기록
11. 재현성 (동일 SQLite → 동일 CSV / metrics)
12. 외부 FDR 호출 없음
13. 기존 baseline CSV / JSON 미변경
14. VIX strictly-prior · target horizon 20 · feature 컬럼 유지
15. summary schema 계약 (schema_version / walk_forward_rule)
16. helper 단위: `_build_prediction_grid_kodex` 는 순수히 KODEX index 20 간격 (FIX r1 신규)

---

## 8. 알려진 한계

- Ridge test directional_accuracy (0.5273) 는 simple baseline (0.5727) 보다 낮음. 이 evidence 는 다음 설계 판단에서 사용.
- Ridge baseline v1 은 시장 판단 근거 참조점수 이상의 용도로 사용 금지 (자동 매매 / AI Sessions 연결 금지 — 지시문 §10).
- 최소 학습 행 gate 756 미확보 시 unavailable — 현재 실측은 gate 충족 (첫 예측 2017-07-06).

---

## 9. 변경 파일 목록

**신규**:
- `app/market_flow_walk_forward.py`
- `scripts/run_market_flow_walk_forward.py`
- `tests/test_market_flow_walk_forward.py`
- `docs/handoff/POC2_MARKET_FLOW_WALK_FORWARD_LOOKBACK_V1_CONCLUSION.md` (본 문서)

**수정**:
- `.gitignore` (신규 walk-forward artifact 2 경로)
- `docs/STATE_LATEST.md`
- `docs/handoff/POC2_B_NEXT_ACTIONS.md`
- `docs/handoff/POC2_FEATURE_INVENTORY.md`
- `docs/handoff/POC2_MARKET_FIRST_OPERATING_DIRECTION.md`
- `docs/backlog/BACKLOG.md`

`docs/MASTER_PLAN.md` 는 지시문 §12 대로 변경하지 않음.

---

## 10. 다음 활성 Step

- 미결정 (설계자 지정 대기).
- Ridge · simple baseline evidence 를 기반으로 한 후속 판단은 별도 STEP.
