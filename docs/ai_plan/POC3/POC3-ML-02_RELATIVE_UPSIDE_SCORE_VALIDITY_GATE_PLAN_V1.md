# POC3-ML-02 — Relative Upside Score Validity Gate · 개발 PLAN V1

- **작성**: 개발자 (VSCode Claude)
- **수신**: 설계자
- **작성일**: 2026-08-29
- **개정**: 2026-08-29 — 설계자 판정 `PLAN_REVISE_REQUIRED` 수용. 수정사항 1~8 을
  본 파일 전체에 통합. **V2 를 만들지 않고 같은 파일을 수정**했다.
  변경된 절에 `[개정 2026-08-29]` 표시.
- **성격**: 개발 PLAN (모호점 포함). **구현 전 회신 문서** — 코드·DB·artifact 변경 0건.
- **대응 설계서**: `docs/ai_design/POC3/POC3-ML-02_RELATIVE_UPSIDE_SCORE_VALIDITY_GATE_DESIGN_V1.md`
- **상태**: **`PLAN PASS — IMPLEMENTATION AUTHORIZED`** (설계자, 2026-08-29).
  구현 전 확정사항 5건(§13)을 본 파일에 반영 완료. 재제출 없이 구현 착수.

> **문서 형태에 대한 알림**
> 설계서 §1 은 "플랜은 채팅으로 제출하며 별도 PLAN 문서를 만들지 않는다" 이나,
> 사용자가 2026-08-29 "ai_design에 추가하면서 plan을 세워주시기 바랍니다" 로
> 파일 작성을 지시했고, 확정된 표준 흐름(DESIGN→PLAN 파일→확정→구현→RESULT)도
> 파일 기준이다. 따라서 **본 파일 + 동일 내용 채팅 제출** 둘 다 수행한다.

---

## 0. 본 PLAN 의 3대 전제 [개정 2026-08-29]

설계자가 명시를 요구한 세 문장을 최상단에 못박는다. 이하 모든 절은 이 셋과
모순되지 않는다.

> **① `E2 는 현재 v0 실행 레시피의 point-in-time 재현이며 신규 학습 정책이 아니다.`**
>
> **② `신호 생성일과 진입가격 날짜는 같지 않다.`**
>
> **③ `생존편향으로 인해 이번 Step 의 최대 최종 판정은 RESEARCH_ONLY 다.`**

---

## 1. 확인한 현재 실행 경로

설계서 §5 가 지정한 5개 범위만 조사했다. 아래는 전부 이번에 실측한 값이다.

### 1.1 현재 화면 점수 생성 경로 (= 검증 대상, "chain B")

| 단계 | 파일 | 실측 |
|---|---|---|
| feature 계산 | `app/ml_relative_upside_features.py` | 241줄 |
| 학습·추론·정규화 | `app/ml_relative_upside_model.py` | 279줄 |
| snapshot 생성·저장 | `app/ml_relative_upside_score.py` | 242줄 |
| CLI entrypoint | `scripts/run_ml_relative_upside_score_v0.py` | 272줄 |
| API | `app/api_ml_relative_upside.py` | — |

동작: `etf_master` 의 전체 ticker → `fetch_price_history` 로 `etf_daily_price`
직접 read → 069500 기준 feature 7개 계산 → 단일 `nn.Linear(7,1)` walk-forward
1회 split(80/20) 학습 → 최신 기준일 cross-section 추론 → **후보군 내 순위 기반
0~100 정규화** → JSON 저장.

### 1.2 현재 살아있는 산출물 (실측)

`state/ml/relative_upside_score_run_latest.json`:

```
status ok / asof_date 2026-08-20 / generated_at 2026-08-24T14:23:58Z
model_name relative_upside_v0_linear
train_row_count 1,064,287  (2014-05-12 ~ 2025-07-01)
test_row_count    266,072  (2025-07-01 ~ 2026-07-22)
train_loss 0.00881223101168871 / test_loss 0.03223104402422905
epochs 200 / lr 0.001 / device cpu / cuda_available false / train_seconds 1.4925737919984385
candidate_count 1157 / scored_candidate_count 1157
```

`state/ml/relative_upside_score_latest.json` — 859,312 bytes, candidates 1,157건,
`schema_version = relative_upside_score.v0`.

### 1.3 feature 컬럼 (실측 · `FEATURE_COLUMNS`)

`return_5d`, `return_10d`, `return_20d`, `excess_return_5d`,
`excess_return_10d`, `excess_return_20d`, `drawdown_20d` — **7개**.

학습 target: `future_excess_return_20d`
= `(close[i+20]/close[i] − 1) − (kodex[date[i+20]]/kodex[date[i]] − 1)`.

### 1.4 화면 소비 경로

- `app/api_market_topn_service.py:108 merge_relative_upside_score()` 가 snapshot 을
  읽어 `compute_topn` 후보에 머지.
- `app/market_topn.py:73 compute_topn()` 기본값 실측:
  `DEFAULT_N = 10`, `DEFAULT_BASIS = "one_month"`, `DEFAULT_ORDER = "desc"`,
  `exclude_inverse/leveraged/synthetic/futures = True`.
  **[정정 2026-08-29 · C-4]** `compute_topn` 은 `asof` 인자를 받지만 그것만으로는
  과거 재현이 되지 않는다. §1.10 참조.
- 프론트 `CandidateTable.tsx:86-99` 와 `JudgmentWorkbenchView.tsx:448` 이
  **`relative_upside_score` 로 후보를 재정렬**한다. → 점수는 장식이 아니라
  사용자가 보는 순서를 실제로 바꾸는 값이다.

**화면 Top 10 은 ML 점수 상위 10개가 아니다.** 1개월 수익률 desc 로 뽑은 10개에
점수를 나중에 붙여 순서만 바꾼다. 이 순서를 §4.12 에서 그대로 재현한다.

### 1.5 가격 DB · KODEX200 benchmark (실측)

`state/market/market_data.sqlite` (415,211,520 bytes)

| 항목 | 실측값 |
|---|---|
| `etf_master` | 1,174 |
| `etf_daily_price` 행 | 1,385,752 |
| `etf_daily_price` ticker | 1,177 |
| 가격 구간 | 2014-04-09 ~ 2026-08-27 |
| KODEX200(069500) 유효종가 | 3,038행 · 2014-04-09 ~ 2026-08-27 |
| `market_benchmark_daily_price` | `KOSPI`, `VIX` |

`etf_daily_price` 에만 있고 `etf_master` 에 없는 3종은 `000660 · 005930 · 006400`
(개별주, 2026-03-30~2026-08-12) — A/B 확인에서 나온 그 3종목이다. ETF 아님.

### 1.6 가격의 의미 — `price_basis` 계약 실측 [개정 2026-08-29 · 설계자 수정 8]

설계자 지시대로 기존 source 계약을 확인했다. **UNKNOWN 이 아니라 명시 계약이
존재한다.**

| 근거 | 내용 |
|---|---|
| `app/market_timeseries_naver_yahoo_adapter.py:11` | "가격 필드: Close 만 사용. **Adj Close 사용 금지**. `price_basis="SOURCE_CLOSE"`." |
| `app/market_timeseries_naver_yahoo_adapter.py:22` | `PRICE_BASIS = "SOURCE_CLOSE"` |
| `app/market_data_fdr.py:225` | `close=_to_optional_float(raw["Close"])` — FDR 경로도 일반 Close |
| `docs/handoff/POC2/POC2_MARKET_TIMESERIES_SQLITE_CLOSEOUT_CONCLUSION.md:37` | "가격 기준 `SOURCE_CLOSE` — 각 소스의 일반 `Close` 만. `Adj Close` 사용 금지." |
| DB 실측 | `market_timeseries_ingestion_state` 1,145행 **전부** `price_basis = SOURCE_CLOSE` · NULL 0건 |
| `etf_daily_price.source` 실측 | `NAVER_FDR` 1,251,396 · `FinanceDataReader` 134,356 |

→ **판정: 비수정 종가(`SOURCE_CLOSE`).** 따라서 본 Step 의 모든 수익률은
**`price return`(분배금 미반영)** 이다. 결과서 모든 지표 표에 이 라벨을 단다.
`UNKNOWN_PRICE_RETURN_SEMANTICS` 판정 제한 조건은 **적용하지 않는다** (확인됨).

**남는 한계 (판정 아닌 진단으로 보고)**: ETF 와 KODEX200 이 같은 기준이라
초과수익 계산 자체는 자기정합적이지만, **분배금 성향이 높은 ETF 는 price return
기준에서 체계적으로 불리하게 측정**된다. 분배금 데이터는 DB 에 없고 신규 외부
수집은 제외 범위이므로 크기를 정량화할 수 없다. 한계로만 명시한다.

### 1.7 market-risk / regime 경로 (실측)

| 항목 | 실측값 |
|---|---|
| `market_risk_feature_daily` | 3,013행 · 2014-05-12 ~ 2026-08-20 |
| `etf_ml_feature_daily` (chain A) | 1,376,524행 · 2014-05-12 ~ 2026-08-20 |
| regime 라벨 규칙 | `app/market_regime.py:228 _label_at()` |

`_label_at(closes, i)` 는 `closes[:i+1]` 만 사용한다 — **이미 완전한 point-in-time**
이다. 시장 상태별 슬라이스에 신규 규칙 없이 그대로 쓸 수 있다.
`_score_kodex200` 점수 → `_label_from_score` → `bull / neutral / bear`.

### 1.8 관련 테스트 (실측)

`tests/test_ml_relative_upside_features.py` 119줄 ·
`test_ml_relative_upside_model.py` 91줄 ·
`test_ml_relative_upside_score.py` 178줄 ·
`test_api_ml_relative_upside.py` 350줄 = **738줄**.

전부 단위 동작 테스트다. **점수의 예측력을 평가하는 테스트·스크립트는 0건**이다.

### 1.9 설계서 전제와 실제 코드가 충돌하는 지점 3건

**(C-1) model artifact 가 존재하지 않는다.** 설계서 §4.1 은 "model/artifact
경로와 식별 방법" 을 요구하지만, 스크립트는 모델을 메모리에서 학습하고 추론 후
**버린다**. `run_latest.json` 에 loss 와 구간만 남고 가중치는 어디에도 저장되지
않는다. → §2.1 에서 **재현 모델** 로 다룬다 (동결 모델이라 부르지 않는다).

**(C-2) 배포 모델의 train/test 경계에 target 중첩이 있다.** [개정 2026-08-29 ·
설계자 수정 1] 실측 구간이 train `~2025-07-01`, test `2025-07-01~` 로 같은 날짜에서
맞닿는다.

> **train/test 경계의 target 중첩으로 내부 `test_loss` 의 독립성이 훼손됐다.
> 다만 충분히 뒤의 E1/E2 forward 평가까지 곧바로 누수됐다는 뜻은 아니다.**

동결 대상이므로 고치지 않고 **진단으로만 보고**한다. `test_loss = 0.0322` 를
일반화 성능 근거로 인용하지 않는다.

**(C-3) forward horizon 이 ticker 마다 달력 길이가 다르다.**
`fetch_price_history` 는 `close IS NULL OR close<=0` 행을 제외한다. 결측이 있는
ticker 는 index 가 압축되어 "20거래일 뒤" 가 실제로는 더 긴 달력 기간이 된다.
학습 target 은 동결이라 그대로 두고, **평가 라벨만** §2.4 에서 달력 기준으로
별도 정의한다.

### 1.10 [정정 2026-08-29] C-4 — `compute_topn(asof=...)` 는 과거를 재현하지 않는다

PLAN 최초본 §1.4 에서 "`compute_topn` 은 `asof` 인자를 받으므로 과거 기준일
재현이 가능하다" 고 적었다. **이 주장은 틀렸다.** 구현 착수 시 동작을 실측해
확인했다.

`app/market_topn_helpers.py:140 _compute_period()` 는 최신가를 **`history[-1]`**
에서 가져온다. 그리고 `app/market_topn.py:207` 은 `fetch_price_history(tk)` 를
**날짜 제한 없이** 호출한다. 따라서 `asof` 는 **기준(base) 날짜만** 바꾸고
**최신(latest) 날짜는 바꾸지 못한다.**

실측 (`compute_topn(n=10, asof="2016-06-30")`):

```
rank 1  139260  TIGER 200 IT  selected_return_pct = 1017.2577
```

139260 의 2016-05~07 종가는 11,785 ~ 12,804 로 연속적이고 급등이 없다(실측).
1017% 는 **2026년 최신가 대 2016-05-31 기준가**로 계산된 값이다.

**운영 영향 0건 (실측)**: `compute_topn(` 호출자를 전수 확인한 결과
`app/api_market_topn.py:83` · `app/draft.py:183` · `app/draft_three_push.py:302,328` ·
`app/api_decision_draft_preview.py:90,216` · `app/api_holdings_market_evidence.py:196`
**어느 곳도 `asof` 를 넘기지 않는다.** 전부 default(`None`) →
`_latest_date_in_db()` → DB 최신일이므로 `history[-1]` 과 일치한다.
즉 **운영 결함이 아니다.** `asof` 인자가 과거 날짜로 쓰인 적이 없을 뿐이다.

**조치**: 운영 코드를 고치지 않는다(제외 범위). 대신 §4.12 의 U2 재현을
**절단 임시 DB + `compute_topn` 무수정 호출** 로 수행한다. 본 항목을 결과서
"지시문 외 변경 / 발견 사항" 에 그대로 싣는다.

---

## 2. 평가 데이터 계약

### 2.1 검증 대상 식별 — 재현 기술자 [개정 2026-08-29 · 설계자 수정 2]

C-1 때문에 artifact 경로로는 동결이 불가능하다. **"동일 모델" 이라고 먼저
선언하지 않고, 재현에 성공했는지를 게이트로 판정**한다.

**재현 기술자 = 아래 6개**

| 항목 | 값 | 방법 |
|---|---|---|
| score 버전 | `relative_upside_score.v0` / `relative_upside_v0_linear` | 상수 기록 |
| 코드 | `ml_relative_upside_{features,model,score}.py` 3파일 | 파일별 sha256 + git commit SHA |
| **입력 데이터 절단일** | **2026-08-20** (기존 실행 `asof_date`). **현재 DB 전체(~08-27)가 아니다** | `date <= '2026-08-20'` 로 절단한 `(ticker,date,close)` 투영의 sha256 |
| hyperparameter | seed 42 / epochs 200 / lr 1e-3 / split 0.8 / `nn.Linear(7,1)` | 상수 기록 |
| 실행 환경 | torch **2.13.0** · device cpu · hostname | 기록 |
| 재현 계수 | 선형 계수 7개 + bias | 결과 JSON 에 기록 |

### 2.2 E1 재현 게이트 [개정 2026-08-29 · 설계자 수정 2]

PyTorch 결과는 실행 환경에 따라 미세하게 달라질 수 있으므로 **비트 단위 완전
일치를 요구하지 않는다.** 아래 4개를 사전 정의한 허용범위로 판정한다.

| # | 검사 | 허용범위 |
|---|---|---|
| G-1 | **후보 집합 일치** | 재현 후보 ticker 집합 == snapshot 1,157종 집합. **차집합 0건** (완전 일치 요구) |
| G-2 | **계수 허용오차** | 재현 계수 7+bias 를 기록. 참조 계수가 없으므로 **기록·보고만** 하고 게이트로 쓰지 않음 |
| G-3 | **점수 최대 절대오차** | `max |재현 display_score − snapshot display_score| ≤ 1.0` (0~100 스케일에서 1점) |
| G-4 | **순위 일치율** | 재현 순위 대 snapshot 순위의 Spearman **≥ 0.999** 그리고 top-100 집합 일치율 **≥ 0.95** |

- **G-1·G-3·G-4 전부 통과 → `E1_RECONSTRUCTED`.** E1 평가를 수행한다.
- **하나라도 실패 → `E1_UNAVAILABLE`.** 실패한 게이트와 실측 편차를 보고하고
  **E2 만 수행**한다. 재현 실패를 숨기거나 허용범위를 사후 완화하지 않는다.

G-2 를 게이트에서 뺀 이유: 저장된 참조 계수가 존재하지 않으므로(C-1) 대조 대상이
없다. 없는 기준으로 통과/실패를 만들지 않는다.

### 2.3 산식을 바꾸지 않는 방법

1. 평가 모듈은 feature·모델 계산을 **재구현하지 않고 import 한다** —
   `build_feature_rows_for_ticker`, `train_walk_forward`, `predict_raw_scores`,
   `normalize_to_display_scores`, `compute_topn`, `_label_at` 를 그대로 호출.
2. 위 운영 모듈 **변경 0줄**. §6 에서 파일 단위로 못박는다.
3. 테스트로 강제한다: 평가 경로가 만든 feature 값이
   `build_feature_rows_for_ticker` 출력과 **완전 일치**하지 않으면 실패 (T-9).

### 2.4 평가 달력 — 신호일과 진입일의 분리 [개정 2026-08-29 · 설계자 수정 3]

> **`신호 생성일과 진입가격 날짜는 같지 않다.`**

같은 날 종가로 신호를 만들면서 그 종가로 매수할 수는 없다. 계약을 다음으로 한다.

| 항목 | 정의 |
|---|---|
| **판단일 `t`** | 월말 거래일 (KODEX200 유효종가 기준) |
| **진입일 `e(t)`** | `t` 다음 KODEX200 거래일 |
| **진입가격** | `e(t)` 종가 |
| **청산·교체일** | 다음 리밸런싱 진입일 `e(t')` |
| **청산가격** | `e(t')` 종가 |
| **benchmark** | ETF 와 KODEX200 이 **동일한 `e(t)` · `e(t')`** 사용 |
| **결측** | `e(t)` 또는 `e(t')` 에 유효 종가가 없으면 **제외 + 사유 기록**. 보간·이월 금지 |

```
forward_excess_1m = ( P_etf(e(t')) / P_etf(e(t)) − 1 )
                  − ( P_kodex(e(t')) / P_kodex(e(t)) − 1 )
```

feature 는 `t` 까지의 가격만, 라벨은 `e(t)` 이후 가격만 사용한다.
`t < e(t) < t' < e(t')` 이므로 1개월 구간은 **서로 겹치지 않는다**.
3M 은 `t'` 를 3개월 뒤 월말로 바꿔 동일 정의.

**실측 표본 (진입 `t+1` 반영)**

| 항목 | 실측 |
|---|---|
| KODEX200 거래일 | 3,038 |
| 월말 거래일 | 149 |
| **1M 표본** | **147** (첫 `t`=2014-04-30 → 진입 2014-05-02 · 청산 2014-06-02 / 끝 `t`=2026-06-30 → 진입 2026-07-01 · 청산 2026-08-03) |
| 3M 중첩 / 비중첩(분기말) | **145 / 48** |
| **E2 평가 가능 기준일** (v0 레시피가 모델을 산출하는 첫 시점 이후) | **145** (2014-06-30 ~ 2026-06-30) |
| E2 평가 가능 달력연도 | **13** (2014: 7 · 2015~2025 각 12 · 2026: 6) |
| 견고성 부분집합 (학습이력 250거래일 이상) | **134** (2015-05-29 ~ 2026-06-30) |

cross-section 크기 (그날 유효종가 ticker 수, 실측): 2014-04-30 → 105 ·
2016-04-29 → 163 · 2018-04-30 → 287 · 2020-04-29 → 351 · 2022-04-29 → 490 ·
2024-04-30 → 760 · 2026-04-30 → 1,099 · 2026-06-30 → 1,146.

**주 통계는 145 기준일 전체**로 낸다. 학습 이력이 얇은 초기 구간을 임의로 잘라내면
그것이 곧 신규 정책이 되므로, 대신 **134 부분집합 결과를 견고성 표로 병기**한다.
기준일별 학습행 수를 결과 JSON 에 그대로 기록한다.

### 2.5 중첩 구간 처리

- **1M**: `e(t)`→`e(t')` 가 다음 구간의 시작과 맞물리므로 **구조적으로 비중첩**.
  145개 독립 표본.
- **3M**: 월 단위 기준일이면 3중 중첩. 2단계로 처리 —
  (a) **주 통계는 분기말 기준일만 사용한 비중첩 표본(48)**,
  (b) 중첩 포함 145 표본도 함께 보고하되 Newey–West(lag 2) 보정 t 를 붙인다.

### 2.6 universe 와 생존편향 [개정 2026-08-29 · 설계자 수정 7]

**상장 시점** — `market_timeseries_ingestion_state.confirmed_listing_date` 를
확인했으나 **1,145행 전부 NULL** (실측). 사용 불가.
따라서 **첫 유효종가일 + 20거래일** 을 편입 가능 시점 proxy 로 쓴다.
기준일 `t` 에서 이 조건을 못 채운 ticker 는 제외 → 아직 존재하지 않던 ETF 를
과거에 넣는 look-ahead 를 차단한다.

**상장폐지 — 복원 불가 (실측으로 확정)**

| 측정 | 결과 |
|---|---|
| 최신 유효종가 < 2026-08-27 인 ticker | 21 |
| **2020-01-01 이전 시작 & 2026-01-01 이전 종료 ticker** | **0** |
| `etf_master` 의 상장·폐지일 컬럼 | **없음** |
| `confirmed_listing_date` 채워진 행 | **0 / 1,145** |

12년 구간에서 "과거에 시작해 중간에 사라진" ticker 가 **0건**이다.
→ **DB 는 현재 상장 종목만 담고 있고, 2014~2026 사이 상장폐지된 ETF 는 가격까지
통째로 부재한다. 기존 데이터로 point-in-time universe 복원 불가.**

**편향의 방향·크기에 대한 서술 (설계자 지시로 정정)**

일반적으로 낙관 편향 위험이 크지만, **횡단면 IC 와 분위 스프레드에 미치는 정확한
방향과 크기는 현재 데이터로 측정할 수 없다.** ("성과를 좋은 방향으로만 왜곡한다"
는 이전 단정은 삭제했다.)

판정 상한의 근거는 다음 한 문장이다.

> **편향의 크기와 방향을 정량화할 수 없으므로 `ADOPT` 의 충분한 근거로 사용할 수 없다.**

따라서 **이번 Step 의 실제 가능 판정은 둘 뿐이다.**

- survivor-only 데이터에서도 실패 → **`REJECT`**
- 수치 기준 통과 → 최대 **`RESEARCH_ONLY`**

> **`생존편향으로 인해 이번 Step 의 최대 최종 판정은 RESEARCH_ONLY 다.`**

검증이 헛도는 것은 아니다. **낙관적일 가능성이 있는 데이터에서도 실패하면 현재
점수를 버릴 강한 근거가 된다.**

### 2.7 읽는 데이터 / 안 읽는 데이터

| 읽는다 | 안 읽는다 | 이유 |
|---|---|---|
| `etf_daily_price` (chain B 원천) | `etf_ml_feature_daily` (chain A) | 화면 점수는 chain A 를 쓰지 않는다. chain A 로 평가하면 **다른 숫자**를 검증하게 된다 |
| `etf_master` (이름·태그) | — | 태그 분류용 |
| `market_regime._label_at` | `market_risk_feature_daily` | regime 라벨 컬럼이 없음. `_label_at` 이 정본 |

chain A/B 일치 여부는 **진단 1건**으로만 넣는다(§4.11). 판정에는 안 쓴다.

---

## 3. 누수·편향 방지 방법

### 3.1 E2 정의 — v0 레시피의 PIT 재현 [개정 2026-08-29 · 설계자 수정 1]

> **`E2 는 현재 v0 실행 레시피의 point-in-time 재현이며 신규 학습 정책이 아니다.`**

기준일 `t` 마다 **정확히 다음 5단계만** 수행한다.

1. **기준일 `t` 이후 가격을 입력에서 제거** — `fetch_price_history` 결과를
   `date <= t` 로 절단.
2. **기존 feature/model/score 함수를 변경 없이 호출** —
   `build_feature_rows_for_ticker` → `train_walk_forward` →
   `predict_raw_scores` → `normalize_to_display_scores`.
3. **현재 `train_walk_forward` 의 80/20 split 과 학습 동작을 그대로 사용** —
   split 비율·epoch 200·lr 1e-3·seed 42·정렬 규칙 전부 무변경.
4. 해당 시점에 실제로 생성됐을 점수를 재현.
5. **별도 purge·embargo 규칙을 추가하지 않는다.**

**시점 정합성은 절단만으로 성립한다.** `build_feature_rows_for_ticker` 는
`i + 20 < n` 일 때만 target 을 채우므로, history 를 `t` 에서 자르면
`target_end <= t` 인 행에만 target 이 생긴다. 즉 **`target_end <= t` 조건은
추가 규칙 없이 자동으로 만족**된다 [확정 2026-08-29 · 확정사항 2 — 부등호 통일] — 이것이 v0 레시피 그대로 두면서 시점
정합성을 지키는 방법이다.

**이전 PLAN 의 20거래일 embargo 는 제거했다.** 그것을 넣으면 평가 대상이
`relative-upside v0` 가 아니라 **수정된 신규 레시피**가 되어 결과 전체가
무의미해진다.

### 3.2 평가 방식 2종

| 방식 | 정의 | 표본 | 성격 |
|---|---|---|---|
| **E1 재현 모델** | §2.2 게이트 통과 시, 2026-08-20 절단 입력으로 재현한 모델을 그대로 써서 학습 종료 이후 월말만 평가 | 약 12 | 화면의 그 숫자. 표본이 작아 슬라이스 불가 |
| **E2 PIT 재현** (주) | §3.1 의 5단계를 각 월말에 반복 | **145** | 같은 레시피의 PIT 성능. 연도별·시장별 슬라이스 가능 |

E1 이 `E1_UNAVAILABLE` 이면 E2 만 수행하고 그 사실을 결과서 최상단에 적는다.

**전 구간 feature panel 선생성 금지** [확정 2026-08-29 · 확정사항 1]

> 원시 가격 이력은 메모리에 한 번 적재할 수 있다. 다만 각 기준일 `t` 에서는
> 반드시 `date <= t` 로 절단한 가격 이력을 기존 feature 함수에 전달해 해당
> 시점의 feature 와 target 을 생성한다. 미래까지 생성한 feature panel 을
> `asof_date` 만으로 잘라 사용하는 것은 **금지**한다.

이유: 전 구간 panel 에서 `asof_date <= t` 로만 자르면 그 행의 target 이 `t`
이후 가격을 담을 수 있다. 절단은 **가격 이력 단계**에서 해야 한다.

**실행시간**: 배포 실행은 1,064,287행 200epoch full-batch CPU 학습에
**1.4926초**(실측)였다. E2 는 145회 재적합 + 145회 절단 feature 재생성이므로
전체는 그보다 훨씬 크다. **추정치를 보고하지 않고 구현 후 실측**한다.
60분 초과 시 S-5 로 중단하고 재범위화를 제안한다.

### 3.3 누수 차단과 검사 [개정 2026-08-29 · 설계자 수정 6]

**실제 누수 차단은 아래 3개로 판정한다.**

| # | 검사 | 통과 기준 |
|---|---|---|
| **L-1 미래 입력 제거** | 기준일 `t` 의 feature·학습에 쓰인 가격 날짜의 최대값 ≤ `t` | 위반 0건 |
| **L-2 날짜 assertion** | 라벨에 쓰인 날짜의 최소값 = `e(t)` > `t` | 위반 0건 |
| **L-3 target 종료일 검사** | 학습에 쓰인 행의 **`target_end <= t`** — `t` 종가까지 확인한 뒤 판단하므로 `t` 에서 끝나는 과거 label 은 사용 가능하다 [확정 2026-08-29 · 확정사항 2] | 위반 0건 |

**label shuffle 은 누수 판정 수단이 아니다.** 미래수익이 feature 에 들어 있어도
라벨을 다시 섞으면 상관이 사라질 수 있으므로, 누수 전체를 발견하는 검사가 아니다.

| # | 검사 | 분류 | 방법 |
|---|---|---|---|
| **N-1 label shuffle** | **통계·metric 구현의 negative control** | **고정 seed 0~99, 총 100회** permutation. 각 기준일 안에서 라벨 치환 후 permutation 별 평균 IC 산출 | **100개 평균 IC 의 전체 평균 절대값 < 0.01** **그리고** **100개 값의 2.5%~97.5% 구간에 0 포함** [확정 2026-08-29 · 확정사항 4] |

N-1 결과 **하나만으로 "누수 있음/없음" 을 단정하지 않는다.** 불충족 시 누수로
단정하지 않고 **`metric 구현 이상 의심`** 으로 보고하고 중단한다(§9 S-1).

| # | 추가 | 방법 | 기준 |
|---|---|---|---|
| L-4 재현성 | 같은 seed 로 2회 실행 | 타임스탬프 제외 JSON 완전 일치 |

### 3.4 편향 진단 (판정을 바꾸지 않고 반드시 보고)

- **B-1 생존편향**: §2.6 의 실측 4줄과 정정된 서술을 그대로 싣는다.
- **B-2 제외 상품군 민감도** [개정 2026-08-29 · 설계자 수정 4]:
  주 지표 전체를 **(a) 필터 universe(주)** 와 **(b) 전체 universe(진단)** 두 벌로 낸다.
  **이것은 "베타를 잡았다는 증명" 이 아니다.** 0~100 정규화가 순위의 단조 변환이면
  필터 universe 내부 순서는 바뀌지 않으므로, 전체 universe 결과는
  **제외 상품군(인버스·레버리지·합성·선물)에 결과가 얼마나 민감한지 보는 진단**
  으로만 표현한다.
- **B-3 종목명 태깅 시점**: 태그는 `classify_etf_tags` 가 **현재 이름**으로
  분류한다. 과거에 개명한 ETF 는 오분류될 수 있다 — 한계로 명시.
- **B-4 horizon 불균질(C-3)**: 학습 target 의 달력 길이 분포를 낸다.
- **B-5 price return** [개정 2026-08-29]: §1.6 대로 `SOURCE_CLOSE` 확정.
  모든 지표에 `price return (분배금 미반영)` 라벨. 분배금 성향 차이로 인한
  체계적 편차는 정량화 불가 — 한계로 명시.

---

## 4. 평가 지표와 산식

기준일 `t` 마다 cross-section 을 만들고, 날짜별 통계를 구한 뒤 날짜에 대해 집계한다.
`s_i` = display score(0~100), `y_i` = §2.4 정의의 forward excess return.

| # | 지표 | 산식 |
|---|---|---|
| 4.1 | **순위상관 (주 지표)** | 날짜별 Spearman `IC_t`; 보고값 = `mean(IC)`, `sd(IC)`, `IR = mean/sd`, **6개월 block bootstrap 95% CI**, `t = mean/(sd/√n)` (**참고 수치**) |
| 4.2 | **분위 스프레드** | 날짜별 5분위 → `Q5 − Q1` 평균 forward excess + 분위별 평균 |
| 4.3 | **상위군 대 KODEX200** | 상위 10% 및 top-N 바스켓의 forward excess **평균·중앙값** (gross/net) |
| 4.4 | **승률** | (a) 종목 단위: 상위군 (t,i) 중 `y_i > 0` 비율 (b) **날짜 단위**: 상위군 동일가중 바스켓이 KODEX200 을 이긴 월 비율 |
| 4.5 | **연도별** | 4.1~4.4 를 달력연도별로. **각 연도 표본 수 n 병기** (실측 13개 연도) |
| 4.6 | **시장 상태별** | `_label_at` 로 `t` 를 bull/neutral/bear 로 나눠 4.1~4.4 재계산. **신규 규칙 0건** |
| 4.7 | **커버리지** [개정] | 분모 = 해당 날짜의 **PIT 편입 가능 필터 universe** (§2.6 상장 proxy 통과 + 인버스·레버리지·합성·선물 제외). 분자 = `is_complete_for_inference` 통과 + `e(t)`·`e(t')` 가격 존재. 결측 사유를 `lookback_부족 / KODEX_날짜없음 / close_결측 / 진입일_가격없음 / 청산일_가격없음` 로 분해 |
| 4.8 | **turnover** | 상위 N 바스켓의 월간 교체 비율 = `|이번달 △ 지난달| / N` — **월별 실측값을 그대로 기록** |
| 4.9 | **거래비용** [개정] | 편도비용 `c ∈ {0, 10, 25, 50}bp`. **월별 비용 = 그 달 실측 turnover × c × 2**(매도+매수). 평균 turnover 를 쓰지 않는다. gross/net 두 벌 |
| 4.10 | **불확실성** | (a) **bootstrap 계약 고정** [확정 2026-08-29 · 확정사항 3] — 방식 **circular moving-block bootstrap** · block 길이 **6개월** · 반복 **2,000회** · seed **42** · CI **percentile 2.5% / 97.5%**. 대상 = IC 평균 · 분위 스프레드 · net 상위군 수익 (b) 3M 중첩본은 Newey–West(lag 2) t (c) 모든 평균에 n 병기 |

### 4.11 보조 진단 (판정 미사용)

- chain A(`etf_ml_feature_daily`) 대 chain B 의 `return_20d`·`drawdown_20d` 불일치율.
- **단순 20일 초과수익 순위 대비 ML 순위 Spearman** — ML 이 단순 모멘텀 정렬에
  무엇을 더하는지. 배포 snapshot 이 이미 `simple_vs_ml_rank_comparison` 을 갖고 있다.
- 상위군에 동일 기초지수가 몰린 정도 (기초지수 매핑이 DB 에 없어 이름 기준 근사 —
  근사임을 명시하고 판정에 쓰지 않는다).

### 4.12 U2 — 화면 후보 생성 순서 재현 [개정 2026-08-29 · 설계자 수정 4]

화면의 Top 10 은 ML 점수 상위 10개가 아니다. 각 과거 기준일 `t` 에서 **아래 순서를
그대로 재현**한다.

1. 인버스·레버리지·합성·선물 **제외**
2. **`one_month desc` 기준으로 Top 10 선정** (`compute_topn(asof=t, n=10,
   basis="one_month", order="desc")` 를 그대로 호출)
3. 그 10개에 relative-upside 점수 결합
4. **점수로 화면 표시 순서 재정렬** (`CandidateTable` 정렬 규칙과 동일)
5. **상위 절반(5개)과 하위 절반(5개)** 의 향후 초과수익 비교

**과거 재현 방법 [정정 2026-08-29 · C-4]**: `compute_topn(asof=t)` 만으로는
재현되지 않는다(§1.10). 대신 **`date <= t` 로 절단한 임시 SQLite 를 만들어
`compute_topn(asof=t, db_path=<임시>)` 를 호출**한다. 이렇게 하면 `history[-1]`
이 `t` 시점 최신가가 되어 5단계가 그대로 성립한다.

이는 §3.1 의 "기준일 `t` 이후 가격을 입력에서 제거" 와 **같은 원리**다 —
운영 함수를 고치지 않고 **입력만 PIT 로 만든다**. `compute_topn` 은
**호출만 하고 수정하지 않는다.** 선정 규칙을 평가 모듈에 재구현하지 않는다.

임시 DB 는 리밸런싱 날짜 순서대로 **증분 적재**한다(전체를 145회 복사하지
않는다). 임시 DB 는 `tmp` 경로에 만들고 실행 후 삭제하며, 라이브
`state/market/market_data.sqlite` 는 **read-only** 로만 연다.

### 4.13 운영 가정

| 항목 | 가정 | 근거 |
|---|---|---|
| 운영 주기 | 월 1회, **판단 = 월말 거래일 / 진입 = 다음 거래일 종가** | 저빈도 운영 + §2.4 |
| 동일 시점 중복 ETF | 각각 독립 종목으로 유지, 쏠림 정도는 진단으로만 | 기초지수 매핑 부재. 임의 그룹핑은 신규 데이터라 제외 범위 위반 |
| 점수군 구성 | 5분위(주) + top-10 바스켓(운영 대응) + 화면 슬레이트 상/하위 절반(U2) | `DEFAULT_N = 10` 과 정합 |
| 가중 | 동일가중 | 화면이 순서만 보여주고 비중을 제시하지 않음 |
| 신규 상장 | 첫 유효종가 + 20거래일 이후 편입 | §2.6 |
| 상장폐지 | 데이터 부재 → 처리 불가, 판정 상한으로 선언 | §2.6 |
| 가격 결측 | 해당 (t, ticker) 제외 + 사유 기록. 보간 금지 | 기존 결측 원칙 |
| 경계 | **참고점수의 예측력만 평가.** 매수·매도 신호·임계값·자동 리밸런싱 산출 0건 | 설계서 §6 |

---

## 5. 사전 판정 기준 (구현 전 고정) [개정 2026-08-29 · 설계자 수정 5]

주 기준은 **E2 · 1M · 필터 universe** 다. 모든 통계 판정은 **6개월 block
bootstrap 95% CI** 로 하고, **t 값은 참고 수치로만 보고**한다.

### 5.1 수치 기준 통과 조건 — 아래 전부 충족

| # | 조건 | 선택 근거 |
|---|---|---|
| A-1 | 평균 rank IC **≥ 0.03** **그리고** **bootstrap 95% CI 하한 > 0** (§4.10 고정 계약) | 0.03 은 횡단면 랭킹의 통상 하한. CI 하한 조건은 시계열 자기상관을 t 검정보다 정직하게 반영한다 |
| A-2 | 상위 10% 평균 forward excess **≥ +0.30%/월**, **편도 25bp 를 월별 실측 turnover 에 적용한 net 기준**, **중앙값 > 0**, **그리고 net 값의 bootstrap 95% CI 하한 > 0** | 0.30%/월 ≈ 연 3.7%. 저빈도·참고용 운영에서 이보다 작으면 비용·오차에 묻힌다. 중앙값 조건은 이상치 한 건이 평균을 끄는 경우를 차단 |
| A-3 | 연도별 평균 IC 가 **평가 가능 13개 연도 중 9개 이상에서 양(+)**, **그리고 bull·neutral·bear 세 상태 모두에서 양(+)** (부호만, 크기 무관) | 부호 일관성은 "진짜 효과 대 국면 부산물" 을 가르는 최소선. 연 12표본에 크기 조건을 걸면 과적합. 13개 중 9개 = 기존 2/3 비율 유지 |
| A-4 | **실제 화면 Top 10(§4.12)** 에서 점수 **상위 절반 − 하위 절반 평균 > 0**, **그리고 상위 절반이 이긴 월 비율 > 50%** | ADOPT 급 근거는 실제로 표시되는 자리에서 나와야 한다. 평균 하나로는 소수 월의 큰 차이에 끌리므로 월 비율을 함께 건다 |
| A-5 | L-1~L-4 전부 통과 **그리고** 커버리지 ≥ **90%** (분모 = §4.7 의 PIT 편입 가능 필터 universe) | 커버리지가 낮으면 지표가 특정 부분집합만 대변 |
| A-6 | **E1 의 명백한 반박이 없을 것** — E1 의 **평균 IC 와 화면 슬레이트 차이가 둘 다 음수**이면 반박으로 본다 (`E1_UNAVAILABLE` 이면 이 조건은 판정 불가로 표기하고 미적용) | 재현 모델이 두 축 모두에서 반대로 나오면 E2 결론을 그대로 못 쓴다. 한 축만 음수인 것은 표본 12개에서 흔하므로 반박으로 치지 않는다 |

**A-1~A-6 전부 충족 → `RESEARCH_ONLY`** (§2.6 판정 상한. ADOPT 도달 불가).

### 5.2 `REJECT` — 아래 하나라도 해당

| # | 조건 | 근거 |
|---|---|---|
| R-1 | 평균 IC **< 0** 이고 bootstrap **CI 상한 < 0** | **음의 예측력** — 방향 자체가 반대 [확정 2026-08-29 · 확정사항 5] |
| R-2 | 평균 IC 절대값 **< 0.01** 이고 CI 가 **0 을 포함** | **사실상 잡음** — 구분 불가 |
| R-3 | 상위 10% net(25bp) 평균 forward excess **≤ 0** | 비용을 넣으면 남는 게 없음 |
| R-4 | **bear 표본이 12개 이상**이고, 평균 IC **< −0.02** **이면서 bootstrap CI 상한도 < 0** | 하락장 역방향은 화면에 두는 것 자체가 해롭다. 다만 표본이 얇으면 우연이므로 3중 조건 |

### 5.3 그 외

`RESEARCH_ONLY` 로 판정하되 **미충족 항목을 전부 명시**한다. 여기에는 A-1~A-6 중
일부만 통과한 경우, 표본 부족으로 A-3 판정 불가인 경우, `E1_UNAVAILABLE` 인
경우가 모두 포함된다. "통과" 와 "판정 불가" 를 섞어 쓰지 않는다.

### 5.4 수치와 무관하게 판정을 제한하는 조건

| # | 조건 | 효과 |
|---|---|---|
| **P-1** | **상장폐지 생존편향의 크기·방향을 정량화할 수 없다** (§2.6 — 실측 확정, **현재 참**) | **최종 판정 상한 `RESEARCH_ONLY`.** ADOPT 도달 불가 |
| P-2 | L-1~L-3 중 하나라도 위반 | 판정 산출 중단 (§9) |
| P-3 | 연도별 평가 가능 연도 < 8 (현재 실측 13) 또는 어느 시장 상태 표본 < 12 | 해당 슬라이스 "판정 불가" 표기, A-3 미충족 처리 |
| P-4 | 커버리지 < 90% | A-5 미충족 |
| ~~P-5~~ | ~~`UNKNOWN_PRICE_RETURN_SEMANTICS`~~ | **미적용** — §1.6 에서 `SOURCE_CLOSE` 확인 완료 |

### 5.5 충돌 규칙

**1M 대 3M** — 1M 이 주, 3M 이 보조.
- 1M 이 A-1~A-6 충족 & 3M 평균 IC 가 음수이고 **CI 상한 < 0** → 결과서에
  "1개월 한정 · 3개월에서 반전" 을 명시하고 **RESEARCH_ONLY 안에서 근거 약화**로 기록.
  근거: 1개월에만 있고 3개월에 뒤집히는 우위는 단기 반전·미시구조일 가능성이 크다.
- 3M 만 충족, 1M 미충족 → 주 기준 미충족. 보조로 대체하지 않는다.
- 둘 다 REJECT 조건 → **REJECT**.

**전체 대 연도별·시장별** — 안정성(A-3)은 **필요조건**이다.
- 전체 통과 & A-3 실패 → A-3 미충족으로 기록 (RESEARCH_ONLY 근거 약화).
- 전체 REJECT & 일부 연도만 양호 → **REJECT 유지**. 좋은 연도만 골라내지 않는다.
- 전체 애매 & 모든 슬라이스 양(+) → 상향 없음. 상향은 A-1·A-2 수치 충족으로만 가능.

---

## 6. 구현 변경 예상 파일

**신규만 만든다. 운영 경로 변경 0건.**

| 파일 | 구분 | 내용 |
|---|---|---|
| `app/ml_score_validity_eval.py` | 신규 | panel 구성 · §2.4 라벨 · §3.1 E2 재현 · §2.2 E1 게이트 |
| `app/ml_score_validity_metrics.py` | 신규 | IC·분위·승률·turnover·비용·block bootstrap·NW (KS-10 대비 분리) |
| `scripts/run_ml_score_validity_eval_v1.py` | 신규 | CLI entrypoint |
| `tests/test_ml_score_validity_eval.py` | 신규 | §7 |
| `tests/test_ml_score_validity_metrics.py` | 신규 | §7 |
| `state/ml/validity/` | 신규 디렉터리 | 산출물 |

**변경하지 않는 파일**
`app/ml_relative_upside_features.py` · `app/ml_relative_upside_model.py` ·
`app/ml_relative_upside_score.py` · `scripts/run_ml_relative_upside_score_v0.py` ·
`app/market_topn.py` · `app/market_topn_helpers.py` · `app/market_regime.py` ·
`app/api*.py` · 프론트 전체 · `.env` · cron · OCI 경로.

**기존 산출물 미변경**: `relative_upside_score_latest.json` ·
`relative_upside_score_run_latest.json` · `ml_baseline_v0_report_latest.json` —
§2.2 게이트 대조 목적의 **read 만**.

**신규 의존성**: **없음.** Spearman·block bootstrap·Newey–West 는 표준 라이브러리와
이미 쓰는 `torch`/`numpy` 범위에서 직접 구현한다. (scipy·statsmodels 추가는
사용자 승인 대상이라 애초에 배제.)

---

## 7. 테스트 계획

전부 합성 fixture 기준. **라이브 `state/` 경로에 쓰지 않는다** — `tmp_path` +
`monkeypatch` 격리.

| # | 테스트 | 통과 조건 |
|---|---|---|
| T-1 | 알려진 답 rank IC | 완전 단조 panel → 1.0, 완전 역단조 → −1.0 |
| T-2 | **진입일 분리** | 신호일 `t`, 진입 `e(t)`, 청산 `e(t')` 로 계산됨. `t` 종가가 진입가로 쓰이면 실패 |
| T-3 | **E2 무추가규칙** | 절단 history 로 `train_walk_forward` 를 호출할 때 인자가 default(split 0.8/200/1e-3/seed 42) 그대로임. embargo·purge 인자 주입 0건 |
| T-4 | target 종료일 | 절단만으로 **`target_end <= t`** 가 성립함 (부등호 통일 — 확정사항 2) |
| T-5 | **N-1 negative control** | 고정 seed 0~99 · 100회 permutation → 전체 평균 절대값 < 0.01 이고 2.5~97.5% 구간에 0 포함 |
| T-6 | 상장 PIT 필터 | 첫 종가 이전 기준일에 그 ticker 미등장 |
| T-7 | 3M 비중첩 추출 | 분기말만 선택, 겹치지 않음 |
| T-8 | **turnover·비용 (월별 적용)** | 월별 실측 turnover 로 비용이 붙음. 평균 turnover 사용 시 실패 |
| T-9 | **산식 동결** | 평가 경로 feature 값 == `build_feature_rows_for_ticker` 출력 (완전 일치) |
| T-10 | **U2 순서 재현** | 필터 → `one_month desc` Top 10 → 점수 결합 → 점수 재정렬 순서. ML 점수로 먼저 10개를 뽑으면 실패 |
| T-11 | 결측 미보간 | 결측 (t,ticker) 가 0% 로 채워지지 않고 제외됨 |
| T-12 | **E1 게이트** | G-1·G-3·G-4 실패 시 `E1_UNAVAILABLE` 반환하고 E1 지표를 산출하지 않음 |
| T-13 | 커버리지 분모 | 분모가 PIT 편입 가능 **필터** universe 임 (전체 universe 사용 시 실패) |
| T-14 | 결정성 | 같은 seed 2회 실행 → 타임스탬프 제외 JSON 일치 |
| T-15 | 경로 격리 | 라이브 `state/ml/relative_upside_score_latest.json` sha256 실행 전후 동일 |

기존 738줄 회귀도 전량 재실행한다.

---

## 8. 산출물과 문서 갱신

### 8.1 산출물 경로

| 경로 | 내용 |
|---|---|
| `state/ml/validity/relative_upside_validity_v1_latest.json` | 재현 기술자(§2.1) · **E1 게이트 결과(`E1_RECONSTRUCTED`/`E1_UNAVAILABLE`) + 4개 게이트 실측값** · 재현 계수 7+bias · 기준일별 IC·학습행수 · 연도별 · 시장별 · 커버리지(사유 분해) · **월별 turnover** · 비용 민감도 4종 · bootstrap CI · L-1~L-4 · N-1 · `price_basis` 라벨 |
| `state/ml/validity/relative_upside_validity_v1_run_latest.json` | status · 시각 · **실행 시간** · **실행 노드**(hostname·device·torch 버전) · 오류 |

**OCI 전달 0건 · Telegram 0건 · PARAM 0건.**

### 8.2 사람이 읽는 결과

`docs/ai_result/POC3/POC3-ML-02_RELATIVE_UPSIDE_SCORE_VALIDITY_GATE_RESULT.md`
— 표준 7섹션 + 주요 지표 표 + 연도별/시장 상태별 안정성 표 + 누수·결측·생존편향
진단 + **최종 `RESEARCH_ONLY` 또는 `REJECT`** (§2.6 상한) + 실행 시간·노드.

### 8.3 갱신 대상 문서

| 문서 | 갱신 | 조건 |
|---|---|---|
| `docs/STATE_LATEST.md` | O | 항상 |
| `docs/ai_design/POC3/POC3-ML-02_..._DESIGN_V1.md` | O | 설계자 확정 시 `[확정]` 표기 |
| 본 PLAN 파일 | O | 확정 회신을 V1 에 반영 (**V2 안 만듦**) |
| `docs/PROGRAM_TRUTH.md` | 조건부 | 본 Step 은 화면·API·계약을 바꾸지 않으므로 **기본 갱신 없음**. 판정 결과로 화면 문구가 바뀌면 그때 |
| `docs/backlog/BACKLOG.md` | 조건부 | 설계자 판정 후에만. 임의 등재 금지 |

---

## 9. 중단 조건

| # | 조건 | 조치 |
|---|---|---|
| S-1 | L-1·L-2·L-3 중 위반 발생, 또는 N-1 분포 이상 | 지표를 **보고하지 않는다**. 결함 보고 후 중단 |
| S-2 | T-9 실패 (평가 feature ≠ 운영 feature) | 재현 위반. 중단 |
| S-3 | 어떤 기준일에서 커버리지 < 70% | 지표 산출 전 커버리지 먼저 보고 후 판단 요청 |
| S-4 | 운영 모듈을 고쳐야만 진행 가능한 상황 | 중단 + 설계자 질의 (자체 해석 금지) |
| S-5 | Mac 실행이 **60분** 초과 | 중단, PC 실행으로 재범위화 제안 |
| S-6 | 라이브 `state/ml/` 산출물 변경 정황 | 즉시 중단 + 복구 |
| S-7 | 설계서 전제와 코드가 추가 충돌 (C-1~C-4 외 신규) | 중단 + 질의 |

---

## 10. 설계자 판정 반영 대조표 [개정 2026-08-29]

| 설계자 수정 요구 | 반영 위치 | 상태 |
|---|---|---|
| 1. E2 embargo 제거 · v0 레시피 재현 | §0 ①, §3.1 (5단계), T-3 | **반영** |
| 1. C-2 표현 정정 | §1.9 C-2 (인용문 그대로) | **반영** |
| 2. E1 = 재현 모델 · 게이트 4종 | §2.1(절단일 2026-08-20), §2.2, T-12 | **반영** |
| 3. 신호일 ≠ 진입일 | §0 ②, §2.4, T-2 | **반영** |
| 4. U2 화면 순서 재현 · 전체 universe 표현 하향 | §4.12, §3.4 B-2, T-10 | **반영** |
| 5. 판정 기준 수정 (CI 하한·월별 비용·A-4·R-4·커버리지 분모·E1 반박) | §5.1 A-1·A-2·A-4·A-6, §5.2 R-4, §4.7, §4.9, T-8·T-13 | **반영** |
| 6. label shuffle 의미 하향 | §3.3 (L-1~L-3 판정 / N-1 negative control), T-5 | **반영** |
| 7. 생존편향 서술 정정 + 상한 유지 | §0 ③, §2.6 (단정 삭제·근거 문장 교체·가능 판정 2종) | **반영** |
| 8. 가격 의미 확인 | §1.6 (`SOURCE_CLOSE` 확정 · price return 명시 · P-5 미적용), §3.4 B-5 | **반영** |

**유지 승인 항목** — 1M 주/3M 보조 · 월 1회 저빈도 · 필터 universe 주 평가 ·
3M 비중첩+중첩 병행 · 연도별·시장별 안정성 · turnover 와 0·10·25·50bp 민감도 ·
신규 모델·튜닝·UI·OCI 변경 금지 · 평가 모듈/테스트 파일 분리 · 운영 산출물 불변 ·
외부 데이터 미추가 · 60분 중단 조건 — **전부 그대로 유지**했다.

**M-1~M-5 판정 반영**: M-1 수용(§4.12·§3.4) · M-2 부분수용(§3.1 로 재정의) ·
M-3 수용(§2.6·P-1) · M-4 부분수용(§2.4 진입일 분리) · M-5 부분수용(§5.1).

---

## 11. 본 PLAN 단계에서 하지 않은 것

- 구현·백필·학습·평가 **실행 0건**
- 코드·DB·artifact 수정 **0건** (DESIGN·PLAN 문서 2개 작성만)
- 신규 모델·feature 변경·모델 비교·튜닝·외부 데이터 **0건**
- UI·OCI·PUSH·cron **0건**
- 로컬 holdings 가격 문제 **미착수** (A/B 판정대로 BACKLOG)
- **V2 문서 생성 0건** — 본 파일을 수정했다
- 커밋·푸시 — 사용자 지시 대기

## 12. 남은 모호점

**없음.** M-1~M-5 는 설계자 판정으로 전부 확정됐고, 수정 요구 1~8 도 위 대조표대로
반영했다. 추가 질문 없이 착수 가능하다.

단, 착수 전 확인만 1건: **§2.2 의 E1 게이트 허용범위**(G-3 점수 최대 절대오차
`≤ 1.0` · G-4 Spearman `≥ 0.999` · top-100 일치율 `≥ 0.95`)는 참조 계수가 없는
상태에서 개발자가 제안한 값이다. 설계자가 다른 값을 원하면 지정해 달라.
지정이 없으면 위 값으로 진행한다.


---

## 13. 설계자 최종 확정사항 반영 (2026-08-29) — `PLAN PASS`

설계자 판정 **`PLAN PASS — IMPLEMENTATION AUTHORIZED`**. 구현 전 확정사항 5건을
본 파일에 반영했다. 재제출 없이 구현에 착수한다.

| # | 확정사항 | 반영 위치 |
|---|---|---|
| 1 | **전 구간 feature panel 선생성 금지** — 기준일마다 `date <= t` 로 절단한 가격 이력을 feature 함수에 전달 | §3.2 (교체 문구 인용) · T-3 · L-3 |
| 2 | **target 종료일 부등호 통일 `target_end <= t`** | §3.1 · §3.3 L-3 · T-4 |
| 3 | **bootstrap 계약 고정** — circular moving-block · block 6개월 · 2,000회 · seed 42 · percentile 2.5/97.5 | §4.10 · §5.1 A-1 |
| 4 | **N-1 통과 기준 수치화** — seed 0~99 100회 · 평균 절대값 < 0.01 · 2.5~97.5% 에 0 포함 | §3.3 N-1 · T-5 |
| 5 | **R-1 정정** — R-1 = 평균 IC < 0 이고 CI 상한 < 0 (음의 예측력) / R-2 = 잡음 | §5.2 |

### E1 게이트 허용범위 — 설계자 승인 (2026-08-29)

개발자 제안값을 그대로 승인받았다.

- G-1 후보 **1,157종 완전 일치**
- G-3 점수 최대 절대오차 **≤ 1.0**
- G-4 Spearman **≥ 0.999**
- G-4 Top 100 집합 일치율 **≥ 0.95**

E1 은 보조 평가이고, 하나라도 실패하면 **기준을 완화하지 않고 `E1_UNAVAILABLE`**
로 처리한다.

### 최종 확정 계약

- E2: 현재 v0 레시피의 **PIT 재현**
- E1: **게이트 통과 시에만** 재현 모델로 사용
- **판단일과 실제 진입일 분리**
- **실제 화면 Top 10 생성 순서 재현**
- 모든 수익률은 **`price return`(분배금 미반영)**
- 생존편향으로 **최종 판정 상한은 `RESEARCH_ONLY`**
- 가능한 최종 결과는 **`RESEARCH_ONLY` 또는 `REJECT`**
- 신규 모델·튜닝·UI·OCI·PUSH 변경 **없음**
