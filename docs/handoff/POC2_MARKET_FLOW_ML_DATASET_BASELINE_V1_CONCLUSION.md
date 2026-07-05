# Market Flow ML Dataset + Baseline v1 — Conclusion (DONE)

작성일: 2026-07-03 (PARTIAL 진입) → 2026-07-05 (Closeout DONE)
성격: 시장 전체 흐름을 읽기 위한 첫 ML 학습 데이터셋과 단일 Ridge baseline. 시장 판단 UI / 자동 매매 / AI Sessions 연결 작업이 아니다.

---

## 0. Closeout (2026-07-05) — DONE 승격 요약

2026-07-03 시점 두 개의 PARTIAL 원인이 모두 해소되어 DONE 판정:

- **(1) scikit-learn 승인·선언**: 지시문 §6 명시 승인 하에 `scikit-learn==1.9.0` 을 `requirements.txt` 에 정확 고정 (§6 "실제 설치된 정확한 버전 고정" 재현성 요건, FIX r1 정정). StandardScaler + Ridge(alpha=1.0) 외 사용 금지 (RF/XGB/LGBM 비교·자동 튜닝 금지) — 승인 조건 그대로 유지.
- **(2) KOSPI 시계열 보강**: 신규 CLI `python -m scripts.refresh_market_timeseries kospi` 로 NAVER_FDR 주 소스에서 2870 행 신규 삽입 (2014-04-10 ~ 2025-12-18). 기존 130 행 overwrite=false. YAHOO_FDR 미조회. 총 3000 KOSPI 행 확보. artifact: `state/market/kospi_history_closeout_latest.json`.

Real SQLite 기반 baseline 실측:

| 항목 | 값 |
|---|---|
| status | ok |
| dataset row_count | 2960 (2014-05-13 ~ 2026-06-05) |
| Split | train=1756 / validation=572 / test=592 |
| Validation | MAE=3.995 / RMSE=5.014 / directional_accuracy=0.4615 |
| Test | MAE=7.855 / RMSE=11.061 / directional_accuracy=0.4932 |
| latest_inference | status=ok / as_of=2026-07-03 / pred=+5.495% |
| VIX alignment | strictly_prior_observation (유지) |
| sklearn version | 1.9.0 |

**행동 문구 미포함 / UI 변경 0건 / 신규 endpoint 0건 / 상시 외부 호출 0건** (KOSPI 외부 조회는 `kospi` 서브커맨드 1회 실행 시에만). 기존 backend 738 passed.

**주의 (한계)**: Test set directional_accuracy 0.4932 는 랜덤(0.5) 근처. Ridge baseline v1 은 시장 판단 근거 참조점수 이상의 용도로 사용하지 말 것 (자동 매매 / AI Sessions 연결 금지).

---

## 1. 완료 판정 — DONE (2026-07-05)

2026-07-03 PARTIAL 이후 §0 Closeout 두 조건 (scikit-learn 승인 + KOSPI 시계열 보강) 모두 충족. real SQLite 실행에서 status=ok / 세 split 모두 >0 / metrics·latest_inference 실측 확보. 이전 PARTIAL 판정 근거였던 지시문 §7.1 문구는 종결.

---

## 2. 사용 SQLite 범위

| 소스 | 테이블 |
|---|---|
| KODEX200 | `etf_daily_price` (ticker=`069500`) |
| KOSPI | `market_benchmark_daily_price` (benchmark_id=`KOSPI`) |
| VIX | `market_benchmark_daily_price` (benchmark_id=`VIX`) |
| ETF universe (breadth) | `etf_master` + `etf_daily_price` |
| missing_confirm 제외 | `market_timeseries_ingestion_state` (status=`missing_confirm`) |

`build_dataset` / `run_baseline` 은 외부 API / FDR / Yahoo / pykrx / KRX CSV 호출 0건 (자동 테스트 `test_10_no_external_data_calls` 검증). KOSPI 시계열 보강 CLI (`kospi` 서브커맨드) 는 지시문 §5·§6 승인 하에 NAVER_FDR / YAHOO_FDR 만 호출 (2026-07-05 Closeout 신설).

---

## 3. Feature 축과 target 정의

### 3.1 Feature (13개)

| 카테고리 | 컬럼 |
|---|---|
| 시장 가격 흐름 | `kodex200_return_5d_pct`, `kodex200_return_20d_pct`, `kospi_return_5d_pct`, `kospi_return_20d_pct` |
| ETF breadth | `etf_breadth_positive_ratio_20d`, `etf_breadth_median_return_20d_pct`, `etf_breadth_spread_p90_p10_20d_pct` |
| VIX 위험 참고 | `vix_close_lagged`, `vix_return_5obs_pct`, `vix_return_20obs_pct` |
| 데이터 coverage | `etf_eligible_count`, `etf_coverage_count_20d`, `etf_coverage_ratio_20d` |

### 3.2 Target

```text
target_future_kodex200_return_20d_pct
= ((close[t+20] / close[t]) - 1) * 100
```

KODEX200 거래일 기준 이후 **정확히 20번째 거래일** 단순 수익률 (%). 상승/하락 라벨·임계치·행동 문구 없음 (자동 테스트 `test_1` 검증).

---

## 4. VIX Strictly-Prior 정렬 원칙 (지시문 §5.1)

- VIX 는 as_of_date 보다 **엄격히 이전** 인 가장 최근 관측일만 사용.
- `vix_source_date < as_of_date` 항상 성립.
- 동일 날짜 VIX 는 feature 에 사용 금지 (자동 테스트 `test_2` / `test_3` 검증).
- 각 행에 `vix_source_date` / `vix_lag_calendar_days` 기록.

VIX 이전 관측값이 전혀 없으면 해당 날짜는 excluded. 외부 호출 / 임의 대체값 / 0 채움 / forward fill 0건.

---

## 5. 시간 순서 split + target overlap 방지 (지시문 §8)

### 5.1 분할

정렬된 labeled 행을 시간 순서 60% / 20% / 20% 로.

### 5.2 target overlap 방지

- `train` 행의 `target_end_date < validation 시작일` — 자동 테스트 `test_7`.
- `validation` 행의 `target_end_date < test 시작일` — 자동 테스트 `test_8`.
- 무작위 셔플 / KFold / shuffle split 0건.

---

## 6. Artifact 경로

| 파일 | 경로 |
|---|---|
| Dataset CSV | `state/ml/market_flow_training_dataset_latest.csv` |
| Baseline JSON | `state/ml/market_flow_baseline_latest.json` |

두 경로는 `.gitignore` 아래 (`state/`) — commit 되지 않음.

---

## 7. Baseline 모델과 고정 alpha

```text
StandardScaler + Ridge Regression
Ridge alpha = 1.0
```

- 신규 Python 패키지 추가 0건.
- 모델 선택 / alpha 탐색 / feature 선택 / hyperparameter tuning 0건.
- 재현성: 입력 행 날짜 오름차순 정렬 / feature 컬럼 순서 고정 / 무작위 셔플 X / 임의 샘플링 X.

---

## 8. 성능 결과 (2026-07-05 Closeout 실측)

Real SQLite (`state/market/market_data.sqlite`) 기반 baseline 실행 결과:

```
[market-flow-baseline] status=ok
[dataset] rows=2960 start=2014-05-13 end=2026-06-05 excluded=41
[split] train=1756 / validation=572 / test=592
[val]  {'mae': 3.9952, 'rmse': 5.0140, 'directional_accuracy': 0.4615}
[test] {'mae': 7.8547, 'rmse': 11.0612, 'directional_accuracy': 0.4932}
[latest_inference] status=ok as_of=2026-07-03 pred=+5.495%
```

- **Dataset 2960 rows** (2014-05-13 ~ 2026-06-05). KOSPI 역사 시계열 보강 후 dataset 규모가 90 → 2960 rows 로 확대.
- **Excluded 41** — `kodex_lookback_insufficient=20` + `kospi_lookback_insufficient=1` + `target_horizon_unavailable=20` (초반/말단 lookback / target 미확보).
- **Split**: train=1756 (2014-05-13 ~ 2021-07-01) / validation=572 (2021-07-30 ~ 2023-11-24) / test=592 (2023-12-26 ~ 2026-06-05).
- **KOSPI source summary** (baseline artifact `kospi_source_summary` 필드): selected_source=NAVER_FDR / inserted_row_count=2870 / overwrite_performed=false / existing_row_count_before=130 / application_range 2014-04-10 ~ 2025-12-18.

---

## 9. 최신 추론 가능 여부

- `latest_inference.status = "ok"`
- `as_of_date = 2026-07-03`, `predicted_future_kodex200_return_20d_pct = +5.4952`
- Ridge 는 전체 labeled 데이터 (train+val+test) 로 재학습 후 무라벨 최신 행에 대해 예측 — 지시문 §7.3 그대로.

---

## 10. 알려진 한계

- **Test set directional_accuracy 0.4932 은 랜덤(0.5) 이하** — Ridge baseline v1 은 시장 판단 근거 참조점수 이상의 용도로 사용 금지. 자동 매매 / AI Sessions 연결 금지 (§4 절대 고정).
- **YAHOO_FDR 폴백 실경로는 real 실행에서 미검증** — NAVER 가 첫 시도에 충족했기 때문. 자동 테스트 (fixture-stubbed) 로만 검증.
- **행동 문구·시장 라벨·임계치**: 지시문 §12 금지 그대로. `latest_inference` 는 수익률 예측값일 뿐 상승/하락/위험 등급 부여 X.

---

## 11. 자동 테스트 결과

| 항목 | 결과 |
|---|---|
| backend 전체 | **738 passed** (729 → 738, 신규 9) |
| black `--check app tests scripts` | PASS |
| flake8 `app tests scripts` | PASS |
| frontend lint / build | 변경 없음 (지시문 §12 UI 금지 그대로) |

**신규 테스트 9건** — `tests/test_kospi_history_closeout.py`:
1. NAVER 충족 시 NAVER 선택 + YAHOO 미조회
2. NAVER 불충족 + YAHOO 충족 시 YAHOO 만 저장
3. 둘 다 불충족 시 SQLite 미변경 + status=unavailable
4. 기존 KOSPI 행 overwrite 금지 (동일 date close 유지)
5. NAVER + YAHOO 신규 행 혼합 금지
6. artifact §8.1 필수 필드 존재
7. KODEX range 부재 시 unavailable
8. 경계 분리 (benchmark/incremental/initial/vix/status 는 KOSPI DataReader 호출 안 함)
9. artifact 경로 상수 확인

기존 `tests/test_market_flow_baseline.py` 15건은 그대로 유지 (외부 호출 없음, unavailable 시나리오 stub 포함).

---

## 12. 변경 파일 목록 (2026-07-05 Closeout)

**신규**:
- `app/kospi_history_closeout.py` — KOSPI 역사 보강 코어 (362 줄, wc -l 실측)
- `tests/test_kospi_history_closeout.py` — §10 자동 테스트 9 케이스 (476 줄)

**수정**:
- `requirements.txt` — `scikit-learn==1.9.0` 정확 고정 (§6 승인)
- `app/market_flow_baseline.py` — `sklearn_version` + `kospi_source_summary` 필드
- `scripts/refresh_market_timeseries.py` — `kospi` 서브커맨드 추가
- `.gitignore` — 신규 state artifact + 백업 패턴 3줄
- `docs/STATE_LATEST.md`, `docs/handoff/POC2_B_NEXT_ACTIONS.md`, `docs/handoff/POC2_FEATURE_INVENTORY.md`, `docs/handoff/POC2_MARKET_FIRST_OPERATING_DIRECTION.md`, `docs/backlog/BACKLOG.md` — Closeout 상태 반영

`docs/MASTER_PLAN.md` 는 지시문 §4 대로 변경하지 않음.

---

## 13. AC 충족 (2026-07-05 Closeout)

| AC | 결과 | 비고 |
|---|---|---|
| AC-1 SQLite 만 사용 dataset 생성 | ✅ | build_dataset / run_baseline SQLite read only |
| AC-2 각 행에 기준일 / feature / target_end_date / target | ✅ | |
| AC-3 KODEX200 기준일 이후 정보가 feature 에 미포함 | ✅ | |
| AC-4 VIX strictly-prior 만 사용 | ✅ | `vix_alignment=strictly_prior_observation` |
| AC-5 정상 ETF universe 필터 + coverage 적용 | ✅ | |
| AC-6 제외 사유·coverage artifact 기록 | ✅ | excluded_reason_counts 세 항목 |
| AC-7 시간 순서 split + overlap 방지 | ✅ | 60/20/20 고정 |
| AC-8 baseline metrics artifact 기록 | ✅ | val/test MAE·RMSE·directional_accuracy 모두 실측 |
| AC-9 최신 추론 가능 여부 | ✅ | status=ok, pred=+5.495% |
| AC-10 KOSPI closeout artifact §8.1 형태 | ✅ | `state/market/kospi_history_closeout_latest.json` |
| AC-11 baseline artifact §8.2 (kospi source summary) | ✅ | `kospi_source_summary` 필드 |
| AC-12 신규 UI / DB 테이블 / 상시 외부 호출 없음 | ✅ | 외부 호출은 `kospi` 서브커맨드 실행 시에만 |
| AC-13 기존 ML axis1 / Discovery / Holdings / Preview / Sessions / PENDING / OCI / Telegram 미변경 | ✅ | |
| AC-14 관련 테스트 + 전체 테스트 / 정적 검사 통과 | ✅ | 738 passed |

---

## 14. 다음 활성 Step 후보 (사용자 결정 대기)

- 미결정 (설계자 지정 대기).
- baseline 확인 이후 모델 고도화·전략 백테스트는 BACKLOG 이관 (본 STEP 범위 외).
