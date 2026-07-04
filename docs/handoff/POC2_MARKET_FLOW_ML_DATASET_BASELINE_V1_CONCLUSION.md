# Market Flow ML Dataset + Baseline v1 — Conclusion (PARTIAL)

작성일: 2026-07-03
성격: 시장 전체 흐름을 읽기 위한 첫 ML 학습 데이터셋과 단일 Ridge baseline. 시장 판단 UI / 자동 매매 / AI Sessions 연결 작업이 아니다.

---

## 1. 완료 판정 — PARTIAL

지시문 §7.1 명시:
> "sklearn이 기존 선언 환경에 없으면 새 패키지를 추가하지 말고 PARTIAL로 보고한다."

현재 `requirements.txt` 에 scikit-learn 이 선언되어 있지 않고, 기존 ML 축1 은 `torch` 만 사용. 신규 의존성 추가 금지 원칙 그대로 유지:

- 데이터셋 생성 / VIX strictly-prior 정렬 / ETF breadth·coverage / 시간 순서 split 로직 → **전부 구현·자동 테스트 통과**.
- Ridge baseline 학습·평가·최신 추론 → **status=unavailable** + `unavailable_reason="sklearn_not_installed"` 로 정직 기록.
- **DONE 승격 두 조건 (사용자 판단 대기)**: (1) `scikit-learn` 승인 + `requirements.txt` 선언, (2) KOSPI 시계열 보강 (실측 `validation split=0` 해소). 두 조건 모두 충족되어야 baseline validation·test metrics 산출 가능. sklearn 단독 승인만으로는 불가 (§10 상세).

---

## 2. 사용 SQLite 범위

| 소스 | 테이블 |
|---|---|
| KODEX200 | `etf_daily_price` (ticker=`069500`) |
| KOSPI | `market_benchmark_daily_price` (benchmark_id=`KOSPI`) |
| VIX | `market_benchmark_daily_price` (benchmark_id=`VIX`) |
| ETF universe (breadth) | `etf_master` + `etf_daily_price` |
| missing_confirm 제외 | `market_timeseries_ingestion_state` (status=`missing_confirm`) |

외부 API / FDR / Yahoo / pykrx / KRX CSV 호출 0건 (자동 테스트 `test_10_no_external_data_calls` 검증).

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

## 8. 성능 결과

sklearn 미설치 상태에서 실측 (기본 SQLite `state/market/market_data.sqlite`):

```
[market-flow-baseline] status=unavailable
[dataset] rows=90 start=2026-01-21 end=2026-06-05 excluded=2911
[split] train=34 / validation=0 / test=18
[val]  {'mae': None, 'rmse': None, 'directional_accuracy': None}
[test] {'mae': None, 'rmse': None, 'directional_accuracy': None}
[latest_inference] status=unavailable
                   reason=sklearn_not_installed
```

- **Dataset 90 rows** 실제 생성. KOSPI 시계열이 2025-12-19 부터 존재하여 상대적으로 짧음.
- **Excluded 2911** 대부분 `kospi_lookback_insufficient` + `kospi_missing_on_asof` (KOSPI 시계열 확보 이전 KODEX200 거래일) + `kodex_lookback_insufficient` (초반 20 거래일).
- **Split 실측**: train=34 / **validation=0** / test=18. Validation 이 비어 있는 이유는 target overlap 방지 필터가 val 구간을 모두 제거했기 때문 (val 시작 근처 labeled 행의 `target_end_date` 가 test 시작일을 침범 → 필터로 삭제). 원인은 KOSPI 시계열 짧음으로 labeled 행 밀도 부족.
- Baseline metrics 는 sklearn 부재로 산출 불가 — artifact 에 `null` 기록.

---

## 9. 최신 추론 가능 여부

- `latest_inference.status = "unavailable"`
- `unavailable_reason = "sklearn_not_installed"`
- 무라벨 최신 feature 행 자체는 `build_dataset` 결과의 `unlabeled_latest_row` 로 준비되어 있음 — sklearn 활성화 시 즉시 예측 가능.

---

## 10. 알려진 한계

- **sklearn 미설치**: 신규 의존성 추가 금지 원칙 그대로 유지. `torch` 기반 대체 baseline 은 지시문 §4 "단일 baseline (Ridge)" 고정 위반이라 도입하지 않음.
- **KOSPI 시계열 짧음**: 2025-12-19 부터 실측 저장. 이전 구간의 KODEX200 기준일은 excluded. 확보되면 자동으로 dataset 증가.
- **Validation split 0행 (실측)**: 지시문 §8.2 target overlap 방지 필터가 val 구간을 모두 제거. sklearn 만 설치해도 val=0 이면 `validation` metrics 산출 불가. **DONE 승격 두 조건**:
  1. `scikit-learn` 승인 + `requirements.txt` 선언.
  2. **KOSPI 시계열 보강** — labeled 행 밀도가 확보되어야 val split 이 정상화. 두 조건이 모두 충족되어야 baseline 이 실 metrics 로 산출된다. sklearn 단독 승인만으로는 DONE 승격 불가.
- **행동 문구·시장 라벨·임계치**: 지시문 §12 금지 그대로. `latest_inference` 는 수익률 예측값일 뿐 상승/하락/위험 등급 부여 X.

---

## 11. 자동 테스트 결과

| 항목 | 결과 |
|---|---|
| backend 전체 | **729 passed** (714 → 729, 신규 15) |
| black `--check app tests scripts` | PASS |
| flake8 | PASS |
| frontend lint / build | 변경 없음 (지시문 §12 UI 금지 그대로) |

**신규 테스트 15건** — `tests/test_market_flow_baseline.py`:
1. target 은 KODEX200 이후 정확히 20번째 거래일 수익률
2. VIX source_date 는 as_of_date 보다 엄격히 이전
3. 동일 날짜 VIX 미사용
4. ETF breadth 에서 인버스/레버리지/합성/선물형/missing_confirm 제외
5. coverage_count/coverage_ratio 정의대로 계산
6. 필수 입력 없으면 임의 보정 X, unavailable 처리
7~8. 시간 순서 split + target overlap 방지
9. 재현성 (같은 fixture 에서 feature/target/split 동일)
10. 외부 데이터 호출 없음 (FDR 감시)
11. 무라벨 최신 feature 행에서만 latest inference
+ helper 단위 (median / percentile / strictly-prior VIX)
+ 통합 스모크 (sklearn 감지 stub → unavailable 마킹)
+ CSV 컬럼 순서 고정

---

## 12. 변경 파일 목록

- `app/market_flow_dataset.py`: 신규 (SQLite reader + feature/breadth/coverage 계산 + build_dataset). 452 줄 (wc -l 실측).
- `app/market_flow_baseline.py`: 신규 (split + train/evaluate + CSV/JSON writer + run_baseline). 327 줄 (wc -l 실측). B-2/B-3 지적 반영으로 dataset 로직은 별도 파일로 분리. 두 파일 합계 779 줄.
- `scripts/run_market_flow_baseline.py`: 신규
- `.gitignore`: 수정 (신규 artifact 2 경로 추가)
- `docs/handoff/POC2_MARKET_FIRST_OPERATING_DIRECTION.md`: 수정 (§6 "다음 활성 Step" 을 이번 STEP 완료 상태 + DONE 승격 두 조건으로 정정)
- `tests/test_market_flow_baseline.py`: 신규 (15 케이스)
- `docs/STATE_LATEST.md`: 수정
- `docs/handoff/POC2_B_NEXT_ACTIONS.md`: 수정
- `docs/handoff/POC2_FEATURE_INVENTORY.md`: 수정
- `docs/handoff/POC2_MARKET_FLOW_ML_DATASET_BASELINE_V1_CONCLUSION.md`: 신규
- `docs/backlog/BACKLOG.md`: 수정 (baseline 확인 이후 고도화 항목 추가)

`docs/MASTER_PLAN.md` 는 지시문 §4 대로 변경하지 않음.

---

## 13. AC 충족 (지시문 §15)

| AC | 결과 | 비고 |
|---|---|---|
| AC-1 SQLite 만 사용 dataset 생성 | ✅ | |
| AC-2 각 행에 기준일 / feature / target_end_date / target | ✅ | |
| AC-3 KODEX200 기준일 이후 정보가 feature 에 미포함 | ✅ | |
| AC-4 VIX strictly-prior 만 사용 | ✅ | |
| AC-5 정상 ETF universe 필터 + coverage 적용 | ✅ | |
| AC-6 제외 사유·coverage artifact 기록 | ✅ | |
| AC-7 시간 순서 split + overlap 방지 | ✅ | |
| AC-8 baseline metrics artifact 기록 | PARTIAL | (1) sklearn 미설치 + (2) 실측 validation split=0. 두 조건 모두 해결되어야 metrics 산출. |
| AC-9 최신 추론 가능 여부 / unavailable 사유 | ✅ | reason=sklearn_not_installed |
| AC-10 외부 호출 / 신규 API / DB 테이블 / UI 없음 | ✅ | |
| AC-11 기존 ML axis1 / Discovery / Holdings / Preview / Sessions / PENDING / OCI / Telegram 미변경 | ✅ | |
| AC-12 관련 테스트 + 기존 전체 테스트 / 정적 검사 통과 | ✅ | 729 passed |

---

## 14. 다음 활성 Step 후보 (사용자 결정 대기)

1. **scikit-learn 승인 여부 결정** — 승인만으로 metrics 산출되지 않음. #2 와 함께 필요.
2. **KOSPI 시계열 장기 보강** — 2014~2025 구간을 KRX CSV 등으로 수동 보정. 이 조건이 함께 충족되어야 validation split 이 정상화되어 baseline metrics 가 산출된다.
3. baseline 확인 이후 모델 고도화·전략 백테스트 (BACKLOG 이관, 본 STEP 범위 외).
