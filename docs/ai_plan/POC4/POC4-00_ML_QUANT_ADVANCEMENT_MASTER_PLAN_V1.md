# POC4-00 — ML·퀀트 고도화 현황조사 및 Master Plan V1

```text
CURRENT_ACTION   = SURVEY_AND_PLAN_ONLY
CODE_CHANGE      = 0
OCI_WRITE        = 0
PUSH_CHANGE      = 0
EXTERNAL_SEND    = 0
DEPENDENCY_ADDED = 0
```

- **작성**: 개발자(VSCode Claude) · **독자**: 설계자
- **입력**: 설계자 채팅 지시(2026-09-23) · `POC3_STATUS = CLOSED` · `FIRST_STEP = POC4-00`
- 조사와 PLAN 을 한 문서에 담는다(설계자 지시 — 별도 조사 문서를 만들지 않는다).

---

# 제1부 · 사실조사

조사 규율: **"파일이 있다" 는 "운영 중이다" 가 아니다.** 모든 항목을 세 단계로
판정하고 근거를 `파일:줄` 로 인용한다.

```text
ORPHANED     정의만 있고 호출처가 없다
REACHABLE    호출처는 있으나 운영 진입점에서 이어지지 않는다 (수동 CLI 포함)
OPERATIONAL  운영 진입점(API 라우트·러너·cron·화면)에서 경로가 이어진다
```

---

## 0. 먼저 — 이 조사의 결론 한 줄

**고도화할 baseline 이 이미 측정됐고 `REJECT` 판정을 받았다.**
`state/ml/validity/relative_upside_validity_v1_latest.json` 실측:

```text
verdict.final                        REJECT      ceiling  RESEARCH_ONLY
e2.ic_filter_universe.mean           -0.0435     ← 예측력이 음수
e2.ic_simple_momentum_diagnostic     +0.0226     ← 단순 모멘텀이 학습 모델보다 낫다
e2.top_decile_gross.mean             -0.0080 /월
e2.turnover.mean                      0.8261     ← 월 82.6% 교체
e2.score_top10_basket.win_rate        0.4483
R3_negative (net 비양수)              True
```

POC4 는 "작동하는 모델을 더 좋게" 가 아니라 **"작동하지 않는 것으로 측정된
모델을 대체"** 하는 작업이다. 이 전제를 PLAN 전체가 따른다.

---

## 1. ML baseline 모델·학습·추론과 실제 사용 여부 (지시 §1)

### 1-1. 모델 실체

`app/ml_relative_upside_model.py`

```text
구조     단일 선형회귀 (1-layer, bias, MSE loss) — nn.Linear(7,1) 상당
학습     torch + Adam, 전체배치 gradient descent (미니배치 없음)  :183-193
분할     walk-forward **1회** split · complete.sort((asof_date, ticker))  :132, :154-159
추론     raw prediction 보관 + 후보군 내 상대순위 0~100 정규화(display)  :253
```

`complete.sort(key=lambda r: (r.asof_date, r.ticker))` 로 **날짜 정렬이 확인된다**
— 랜덤 셔플 누수는 없다.

### 1-2. 도달성 판정

| 대상 | 판정 | 근거 |
|---|---|---|
| `app/api_ml_*.py` 라우터 5개 | **OPERATIONAL** | `app/api.py:133·136·139·142·146` 에 `include_router` 등록 · `frontend/lib/api/{mlReadiness,mlSanity,mlBaselineV0,mlJobs}.ts` 가 호출 · 화면 「**ML 실험**」(`LeftSidebar.tsx:103`) |
| `ml_relative_upside_model.train_walk_forward` | REACHABLE | `scripts/run_ml_relative_upside_score_v0.py` · `app/ml_job_runner.py` 경유. 수동/작업 실행이며 cron 없음 |
| `app/ml_score_validity_*.py` 4개 | **REACHABLE** | 호출처는 `scripts/run_ml_score_validity_eval_v1.py` 와 tests 뿐. API·cron·화면 0건 |
| `scripts/run_ml_score_validity_eval_v1.py` | REACHABLE | 저장소에서 이 파일을 참조하는 곳은 `tests/test_ml_score_validity_cli.py:26` 뿐 |
| `state/ml/validity/...v1_latest.json` (885KB) | **ORPHANED** | 쓰는 코드 1곳, **읽는 코드 0건** |
| `app/market_flow_*.py` 6개 | REACHABLE | `scripts/run_market_flow_*.py` 만. `app/api*.py`·`frontend/`·`deploy/` 에 `market_flow` 문자열 0건 |
| `BacktestRunner` | **ORPHANED** | **저장소에 정의가 없다.** `CLAUDE.md:25` · `AGENTS.md:108` · `docs/agent/VERIFY_RULES.md:108` 의 "운영 경로 예시" 문구로만 존재 — **stale 규칙 문구, 정정 대상** |

### 1-3. ML 이 운영 판단에 쓰이는가 — **아니다**

```bash
grep -rn "relative_upside|ml_score|참고점수" app/three_push_runtime/ app/runtime_evidence/ app/draft*.py
# 히트 0건
```

**PUSH 본문·보유 선정·장중 급등락 어디에도 ML 점수가 들어가지 않는다.**
ML 은 「ML 실험」 화면 표시 전용이고 운영 판단과 완전히 분리돼 있다.
POC3 가 만든 운영 PUSH 를 건드리지 않는다는 설계자 전제와 구조적으로 일치한다.

---

## 2. feature · label · 예측기간 · 학습대상 (지시 §2)

### 2-1. 모델이 쓰는 feature — 7개

`app/ml_relative_upside_features.py:233` `FEATURE_COLUMNS`

```text
return_5d · return_10d · return_20d
excess_return_5d · excess_return_10d · excess_return_20d   (KODEX200 대비)
drawdown_20d
```

`ASSUMPTIONS` Q1 의 evidence 가 말하는 "factor 1개 추가 ≈ 10줄" 의 그 구조다.

### 2-2. label · 예측기간

```text
label     future_excess_return_20d   (20거래일 후 KODEX200 대비 초과수익)
horizon   20거래일
```

> **`ASSUMPTIONS` Q6 제약**: "하락 예측이 아니라 **위험 구간 분류**" 가 불변
> 표현이다. 현재 label 은 회귀(초과수익 크기)이고 Q6 의 분류 축과 다르다.
> POC4 에서 label 을 손대면 Q6 와 충돌하는지 먼저 확인해야 한다 — §12-2.

### 2-3. 이미 계산됐지만 모델이 안 쓰는 feature

`etf_ml_feature_daily` 실측 (PC 1,382,327행 · 2014-05-12~2026-08-27 · ticker 1,174)

```text
쓰는 것    return_5/10/20d · excess_return_5/10/20d_vs_kodex200 · drawdown_20d
안 쓰는 것 volatility_20d · volume_ratio_20d · nav · nav_market_price ·
           nav_discount_rate_pct · nav_status
```

**추가 수집 없이 바로 쓸 수 있는 feature 가 이미 6개 더 있다.**

---

## 3. 보유 데이터 — 시작일·종목수·결측·생존편향 (지시 §3)

### 3-1. PC vs OCI 실측

| 테이블 | PC | OCI |
|---|---:|---:|
| `etf_daily_price` | **1,405,608행 · 2014-04-09~2026-09-21** | 1,345,284행 |
| `etf_ml_feature_daily` | **1,382,327행** | **0행** |
| `market_benchmark_daily_price` | 6,211행 | 6,232행 |
| `etf_nav_daily` | 11,530행 | 5,705행 |
| `krx_etf_daily_price_unadjusted` | **1,168행 · 2026-09-11 하루치** | 30,310행 · 2026-08-13~09-18 |
| `market_risk_feature_daily` | 3,018행 | **0행** |
| `state/ml/` artifact | 6개 + `validity/` (2026-08-30) | **디렉터리 없음** |

**ML 은 PC 전용이고 OCI 에 흔적이 없다** — `PROJECT_ORIGIN_INTENT §10` 의
"PC 는 ML·백테스트·PARAM 후보 계산, OCI 는 운영" 경계와 일치한다.

`krx_etf_daily_price_unadjusted` 는 PC 에 **하루치뿐**이다(OCI 는 25일 롤링).
백테스트는 `etf_daily_price`(12.4년)를 쓰므로 막히지 않는다.

### 3-2. 생존편향 — **확인됨, POC4-01 최우선**

```text
2018-06-01 상장 289종목 중 2026-09-21 에 없는 종목      0
전체 1,186 ticker 중 중도 종료                          15 (1.3%)
그 15개의 마지막 관측일                                  전부 2026-07 이후
연도별 distinct ticker   2014:118 → 2016:208 → 2020:392 → 2023:714 → 2026:1,186
```

12년간 상장폐지 ETF 가 **하나도 없다.** 현재 상장 종목 기준으로 과거를
backfill 한 형태다. `etf_master` 에 상장폐지 표식 컬럼도 없다(`last_seen_at` 만).

코드도 이를 인정한다 — `app/ml_score_validity_eval.py:8`
*"생존편향으로 이번 Step 의 최대 최종 판정은 RESEARCH_ONLY 다"*.

**이대로 5년 백테스트를 돌리면 수익률이 과대평가된다.**

### 3-3. 결측·소스 전환

```text
소스 전환   NAVER_FDR (2014-04-09~2026-03-05, 1,251,396행)
          → FinanceDataReader (2026-02-19~2026-09-21, 154,212행)
          겹침 구간 2026-02-19~03-05 — (ticker,date) PK 중복 0건
```

행 중복은 없으나 **두 소스의 가격 기준이 달랐다면 경계에서 수익률 점프가
생긴다. 검증 코드 없음 — 미확인.**

---

## 4. PC / OCI artifact 목록 (지시 §4)

| artifact | 위치 | 갱신 | 읽는 코드 |
|---|---|---|---|
| `ml_baseline_v0_report_latest.json` | PC | 2026-08-30 | `app/api_ml_baseline.py` → 화면 |
| `ml_feature_sanity_latest.json` | PC | 2026-08-30 | `app/api_ml_sanity.py` → 화면 |
| `ml_feature_snapshot_latest.json` | PC | 2026-08-30 | 화면 |
| `ml_job_status_latest.json` | PC | 2026-08-30 | `app/api_ml_jobs.py` → 화면 |
| `relative_upside_score_latest.json` (856KB) | PC | 2026-08-30 | `app/api_ml_relative_upside.py` → 화면 |
| `validity/relative_upside_validity_v1_latest.json` (885KB) | PC | 2026-08-29 | **0건 — ORPHANED** |
| `market_flow_*` 선언 경로 4종 | — | — | **파일 자체가 없다** (이 PC 에서 실행된 적 없음) |

artifact 6개가 **2026-08-30 에서 멈춰 있다** — 약 3.5주 stale.

---

## 5. PARAM 생성·승인·OCI 전달에서 재사용할 부분 (지시 §5)

POC3-02C 가 만든 구조가 **그대로 쓸 수 있는 상태**다.

```text
PC 산출          generator.generate() — effective_config_hash 로 동일 결과면 새 버전 없음
사용자 승인       POST /intraday-config/approve-and-apply  (멱등 — 재시도가 승인을 덮지 않음)
OCI 전달         scripts/sync_intraday_config.py :: deploy() — 8단계 사슬
                 precheck(원격 쓰기 전 직전 active 확보) → scp → atomic rename →
                 remote apply → checksum read-back → sync 이력 기록
상태 조회         GET /intraday-config/state — active 와 후보를 **필드로 분리**
```

**POC4 가 재사용할 조각**

| 자산 | 위치 | 왜 |
|---|---|---|
| 버전·승인·활성·sync 4테이블 | `app/intraday_config/store.py` | 모델·PARAM 후보에 스키마 그대로 적용 가능 |
| `effective_config_hash` | `schema.py:149` | 결과 동일 시 버전 미생성 — 모델 재학습에도 같은 원리 |
| 승인 멱등성 | `api_intraday_config.py:172` | 전달 실패 재시도가 승인을 다시 찍지 않음 |
| `deploy()` 8단계 + read-back | `scripts/sync_intraday_config.py:172` | OCI 전달 신뢰성 확보 완료 |
| active/후보 상태 분리 | `api_intraday_config.py:189` | "지금" 과 "적용하면" 을 섞지 않는 계약 |
| `market_benchmark_store` upsert | `(benchmark_id, date)` PK | KOSPI200 지수를 **DDL 변경 없이** 추가 가능 |

---

## 6. UI 에서 ML evidence 가 판단에 연결되는 위치 (지시 §6)

```text
화면      「ML 실험」 (LeftSidebar.tsx:103 · hint "학습 자료 상태 · baseline · 참고점수")
호출      mlReadiness · mlSanity · mlBaselineV0 · mlJobs · relativeUpside
데이터    state/ml/*.json 을 API 가 읽어 표시
판단 연결  **없음** — §1-3
```

**표시만 한다.** 백테스트 결과(`validity/`)는 화면에 아예 없다.

---

## 7. 백테스트 코드와 가정 (지시 §7)

### 7-1. 진짜 백테스트는 하나뿐

`app/ml_score_validity_*.py` 4개 + `scripts/run_ml_score_validity_eval_v1.py`

```text
리밸런싱   월말 신호일 t → 익일 진입(eval.py:173) → 차월말+1 거래일 청산
           months_ahead = 1(1M) · 3(3M)
라벨       ETF 수익률 − KODEX200 수익률, 진입·청산일 동일, 보간·이월 금지(:217-230)
거래비용   cost_drag = 실측 교체비율 × 편도bp/10000 × 2   (metrics.py:234)
           COST_BPS_GRID=(0,10,25,50) · PRIMARY_COST_BP=25.0   (eval.py:56-57)
PIT 규율   truncate_history(:190 `date <= t`) · is_pit_eligible(:485 상장 20거래일 warmup)
누수 검사  L1(미래 입력)·L2(진입 전 라벨)·L3(target 종료) — **현 산출물 전부 0건 통과**
```

### 7-2. 없는 것

```text
슬리피지·호가 스프레드·체결가정        0건
수수료/증권거래세 분해                  0건 (편도 bp 하나로 뭉뚱그림)
MDD · 전략 변동성 · Sharpe · equity curve  0건
  → grep "max_drawdown|equity_curve" app/ scripts/ frontend/app  히트 0
  → drawdown_20d 는 **종목 feature** 이지 전략 MDD 가 아니다
총수익(분배금 반영) 기준               없음 — price_basis "분배금 미반영, SOURCE_CLOSE"
운영 판단 흐름(PUSH·보유선정)의 백테스트  없음
```

### 7-3. `market_flow_*` 는 백테스트가 아니다

KODEX200 의 20거래일 단순수익률을 맞히는 **회귀**다(MAE/RMSE/방향정확도).
포지션·비용·회전율 개념이 없다. 다만 walk-forward 규율
(`MINIMUM_TRAIN_ROW_COUNT=756` · 20거래일 고정 grid)은 제대로 갖춰져 있고,
`market_flow_v2_predictor.py:39 predict_three_models_at_kodex_date` 는
**여러 모델을 동일 training subset 으로 fit 하는 공정비교 골격**이다 —
POC4-03 의 직접 템플릿. 단 **산출물이 이 PC 에 하나도 없다**(미실행).

---

## 8. 누수·미래참조·가격혼합 위험 (지시 §8)

| # | 위험 | 상태 | 근거 |
|---|---|---|---|
| L-1 | 랜덤 셔플 분할 | **없음** | `model.py:132` 날짜 정렬 · `:154-159` 시간순 절단 |
| L-2 | 전체기간 통계 정규화 | **없음** | feature 정규화 코드 0건. `normalize_to_display_scores` 는 화면용 |
| L-3 | **경계 label 누수** | **있음** | train 끝 20거래일의 `future_excess_return_20d` 가 test 구간 가격으로 계산됨. **embargo 없음** |
| L-4 | 백테스트 PIT | **처리됨** | `truncate_history` `date <= t` · L1/L2/L3 검사 0건 통과 |
| L-5 | 중첩 표본 | **부분 처리** | 3M IC 에 Newey-West(lag=2) + 분기말 비중첩 표본. bootstrap block 6개월 고정 — 민감도 분석 없음 |
| L-6 | **조정/무조정 혼재** | **있음** | `etf_daily_price`(SOURCE_CLOSE) vs `krx_etf_daily_price_unadjusted`(무조정) 공존. **백테스트와 운영 신호가 서로 다른 가격 기준을 쓴다** |
| L-7 | 분배락 | **미반영** | `market_timeseries_naver_yahoo_adapter.py:11` "Close 만 사용, Adj Close 금지". ETF 간 분배금 차이가 초과수익에 편향으로 남음 |
| L-8 | 소스 전환 경계 | **미확인** | §3-3 |
| L-9 | 생존편향 | **있음** | §3-2 — 가장 큰 위험 |

---

## 9. KRX200 대비 성과 측정 가능 여부 (지시 §9)

**가능하다. 단 지수가 아니라 ETF 대리다.**

```text
KOSPI200/KRX200 **지수** 시계열      DB 에 없음
  market_benchmark_daily_price 의 benchmark_id = KOSPI · VIX · US500 · IXIC · ^SOX
  코드 전체에 KOSPI200/KS200/KRX200 심볼 0건
KODEX 200 ETF (069500)              **3,055행 · 2014-04-09~2026-09-21 · close 결측 0**
```

기존 백테스트가 이미 069500 대비 초과수익으로 145개 월간 시점을 산출했다.
**지금 상태에서 측정 가능**하고, 지수를 원하면 `market_benchmark_store` 에
`benchmark_id` 하나 추가(DDL 변경 불필요 · `refresh_benchmarks` 한 줄).

`PROJECT_ORIGIN_INTENT §5` 의 실패 기준도 "**KODEX 200** 대비 초과 수익" 이라
현재 대리 벤치마크가 프로젝트 원 기준과 일치한다.

**벤치마크 최신성 격차**: KOSPI 최신 2026-09-17 vs ETF 최신 2026-09-21(4일).
US500·IXIC·^SOX 는 각 10행뿐이라 사실상 사용 불가.

---

## 10. RF·XGBoost·LightGBM 사용 가능 여부 (지시 §10)

```text
있음    torch 2.13.0 · scikit-learn 1.9.0 · numpy 2.4.6 · pandas 2.3.3 · scipy 1.18.0
없음    xgboost · lightgbm · statsmodels
```

- **RF 는 지금 가능** (sklearn 내장, 신규 의존성 0).
- **XGBoost·LightGBM 은 설치 필요** → `CLAUDE.md §7` 상 **사용자 명시 승인 대상**.

### ⚠ 과거 확정 제약과 충돌

`requirements.txt` 가 세 곳에서 금지를 명시한다.

```text
:18-19  "단일 회귀 baseline 만 사용, RF/XGB/LGBM 비교 금지, 자동 튜닝 금지"
:25     "StandardScaler + Ridge(alpha=1.0) 만 사용. RF/XGB/LGBM/자동 튜닝/모델 비교 금지."
```

`app/ml_relative_upside_model.py:3-6` 도 같은 제약을 반복한다.

**POC4-03 은 이 제약의 정면 해제를 전제로 한다.** 설계자·사용자가 명시 해제해야
착수할 수 있다 — §12-1.

---

# 제2부 · Master Plan

## 11. 단계 구성

설계자 초안을 유지하되, 조사 결과로 **각 단계의 내용과 순서 근거**를 채웠다.

| 단계 | 이름 | 핵심 | 선행 |
|---|---|---|---|
| **POC4-00** | 현황조사·Master Plan | 이 문서 | — |
| **POC4-01** | 데이터·백테스트 기반 정비 | 생존편향 · 성과지표 · embargo | 00 |
| **POC4-02** | 기존 baseline 재현 | REJECT 결과를 회귀 기준값으로 고정 | 01 |
| **POC4-03** | RF/XGBoost/LightGBM 비교 | 공정비교 · 과최적화 방지 | 02 · **제약 해제** |
| **POC4-04** | 모델·PARAM 후보 자동 산출 | 버전·해시·후보 생성 | 03 |
| **POC4-05** | 승인·OCI 전달 및 evidence 연결 | 02C 구조 재사용 | 04 |

파일명 순서는 유지한다.

---

## 12. 착수 전 설계자 확정이 필요한 것 — **3건**

### 12-1. RF/XGB/LGBM 금지 제약 해제 (POC4-03 차단)

`requirements.txt:18-19,25` 와 `ml_relative_upside_model.py:3-6` 의 "모델 비교
금지·자동 튜닝 금지" 를 **명시 해제**해야 한다. 개발자가 자체 해석으로 넘기지
않는다.

```text
확인 필요  (a) 제약 해제 범위 — 비교만 허용? 자동 튜닝도 허용?
          (b) xgboost·lightgbm 신규 의존성 추가 승인 (사용자 명시 승인 대상)
          (c) 승인 전까지 RF(sklearn)만으로 진행할지
```

### 12-2. label 축 확정 — `ASSUMPTIONS` Q6 와의 관계

현재 label 은 **회귀**(`future_excess_return_20d`)인데 Q6 는 "하락 예측이 아니라
**위험 구간 분류**" 를 불변 표현으로 못박았다.

```text
확인 필요  POC4 가 (a) 회귀 축을 계속 쓰는가
          (b) Q6 의 분류 축으로 옮기는가
          (c) 둘 다 두는가
```

Q6 는 `OPEN` 상태이고 선행 조건(시계열 적재)이 상당 부분 충족됐다 — 이 판단이
POC4-01 의 label 설계를 좌우한다.

### 12-3. 생존편향 처리 방침 (POC4-01 차단)

상장폐지 ETF 데이터가 **없다**. 외부 데이터 도입은 설계자 지시상 금지
("데이터가 없어 5년 백테스트가 불가능하면 임의 보간하거나 외부 데이터를 바로
도입하지 않는다").

```text
선택지  (a) 현 상태 유지 + 백테스트 최종 판정 상한을 RESEARCH_ONLY 로 고정
            (지금 코드가 이미 그렇게 한다 — eval.py:8)
        (b) 상장폐지 목록 확보 경로를 POC4-01 에 별도 과제로 세움
        (c) 편향 방향·크기의 민감도 분석으로 하한을 추정
```

**개발자 제안: (a)+(c).** (b) 는 외부 데이터 도입이라 별도 승인이 필요하다.

---

## 13. POC4-01 — 데이터·백테스트 기반 정비

### 13-1. 할 일

| # | 내용 | 근거 |
|---|---|---|
| 1 | **성과지표 추가** — MDD · 전략 변동성 · Sharpe · 누적 equity curve | §7-2 전부 0건 |
| 2 | **embargo 도입** — train 끝 `horizon` 만큼 잘라 경계 label 누수 차단 | L-3 |
| 3 | **거래비용 분해** — 슬리피지 · 수수료 · 증권거래세를 bp 하나에서 분리 | §7-2 |
| 4 | **생존편향 민감도 분석** — 편향 방향·크기 하한 추정 | §3-2 · 12-3 |
| 5 | **소스 전환 경계 검증** — NAVER_FDR ↔ FDR 겹침 구간 가격 정합 | L-8 |
| 6 | **가격 기준 단일화 선언** — 백테스트는 `etf_daily_price` 하나만 | L-6 |
| 7 | **분배금 처리 결정** — price return 유지 시 그 한계를 산출물에 명시 | L-7 |

### 13-2. 재사용 (신규 작성 아님)

```text
app/ml_score_validity_eval.py    truncate_history · build_calendar · forward_excess · is_pit_eligible
app/ml_score_validity_metrics.py spearman · circular_block_bootstrap_ci · newey_west_t ·
                                 replaced_fraction · cost_drag · win_rate · shuffle_control_verdict
app/ml_score_validity_screen.py  증분 절단 SQLite — 운영 함수를 수정하지 않고 입력만 PIT 화
app/market_flow_walk_forward.py  MINIMUM_TRAIN_ROW_COUNT=756 · 고정 grid anchor
```

**누수 검사 L1/L2/L3 계약**(`report.py:558-565`)은 그대로 유지·확장한다.

### 13-3. 예상 변경 파일

```text
수정  app/ml_score_validity_metrics.py   (MDD·변동성·Sharpe·equity curve 추가)
     app/ml_score_validity_report.py    (지표 payload 확장)
     app/ml_score_validity_eval.py      (embargo · 비용 분해)
신규  tests/test_ml_backtest_metrics.py  (지표 산식 계약)
     tests/test_ml_backtest_embargo.py   (경계 누수 차단 실증)
```

**KS-10 주의**: `app/ml_score_validity_report.py` 는 현재 **626줄**(NEAR 600 진입).
지표를 더하면 650 을 넘길 수 있다 — 넘으면 분리하거나 중단·보고한다.

---

## 14. POC4-02 — 기존 baseline 재현

### 14-1. 목표

`REJECT` 산출물을 **회귀 기준값**으로 고정한다. "고쳤더니 좋아졌다" 를 주장하려면
출발점이 재현 가능해야 한다.

```text
재현 대상  IC -0.0435 · top_decile_gross -0.0080 · turnover 0.8261 ·
          win_rate 0.4483 · 145 평가시점 · leakage L1/L2/L3 0건
재현 명령  python scripts/run_ml_score_validity_eval_v1.py
```

`determinism` 키가 산출물에 이미 있어 **결정성 재실행 검사**가 가능하다.

### 14-2. 주의

- POC4-01 에서 embargo·지표를 더하면 **재현값이 바뀐다.** 그래서 순서가
  01 → 02 가 아니라 **"01 적용 전 원본 재현" → "01 적용 후 재측정"** 두 번이다.
- 원본 재현이 안 되면 그 자체가 결함이다(artifact 가 2026-08-29 자라 코드가
  그 사이 바뀌었을 수 있다).

---

## 15. POC4-03 — RF / XGBoost / LightGBM 비교

### 15-1. 공정비교 규율

```text
동일 training subset 으로 fit         market_flow_v2_predictor.py:39 골격 재사용
동일 feature 집합 · 동일 walk-forward grid · 동일 평가시점
하이퍼파라미터는 train 구간 안에서만 선택 (test 를 보지 않는다)
seed 고정 · 결정성 재실행 검사
```

### 15-2. 비교 대상

| 모델 | 의존성 | 상태 |
|---|---|---|
| 기존 baseline (선형회귀, torch) | 있음 | 재현값 §14 |
| **단순 모멘텀** | 없음 | **IC +0.0226 — 현재 최강. 반드시 포함** |
| RF (sklearn) | **있음** | 즉시 가능 |
| XGBoost | **없음** | 승인 필요 |
| LightGBM | **없음** | 승인 필요 |

> 조사에서 나온 가장 중요한 비교 대상은 **단순 모멘텀**이다. 학습 모델(−0.0435)
> 보다 예측력이 높다(+0.0226). 이를 이기지 못하면 ML 을 쓸 이유가 없다.

### 15-3. 과최적화 방지

```text
walk-forward 재fit          기준일마다 · 미래 미사용
embargo                     horizon 만큼 (POC4-01)
음성 대조(N-1 negative control)  이미 구현 — report.py, 현 |mean| 임계 이하 통과
bootstrap CI + Newey-West t  이미 구현 — block 길이 민감도 추가
모델 수 제한                 위 5개 고정. 변형·튜닝 횟수를 산출물에 기록
판정 임계 사전 고정           A1~A5 (report.py:52-56) 를 실험 전에 확정
```

**"여러 번 돌려 좋은 것을 고른다" 를 금지**하고, 시도 횟수를 산출물에 남긴다.

---

## 16. POC4-04 — 모델·PARAM 후보 자동 산출

```text
PC 가 산출       학습 → 백테스트 → 후보 PARAM(모델 종류·하이퍼파라미터·feature 집합)
버전 관리        effective_config_hash 동일하면 새 버전 없음 (schema.py:149 원리 재사용)
산출물           state/ml/ 밑 버전된 artifact + DB 버전 테이블
승인 대상        사용자가 **버전 전체**를 승인 — 값 하나씩 편집하는 화면 만들지 않음
```

POC3-02C 의 `intraday_config` 4테이블 구조를 스키마째 본뜬다.

---

## 17. POC4-05 — 승인·OCI 전달 및 evidence 연결

```text
승인·전달   approve-and-apply + deploy() 8단계 + checksum read-back 재사용
화면        「ML 실험」 에 백테스트 결과를 **처음으로** 연결 (§4 — 현재 ORPHANED)
            active 와 후보를 필드로 분리 (02C P1 교훈)
운영 연결    ML 점수를 PUSH·선정에 넣을지는 **별도 판단** — 이 단계 범위 밖
```

> **설계자 확인 필요**: 설계자 지시는 "기존 운영 PUSH 를 건드리지 않는다" 이다.
> POC4-05 의 "판단 evidence 연결" 이 **화면 표시까지**인지, **PUSH 본문까지**인지
> 명확히 해야 한다. 현재 ML 은 운영 판단에 0건 연결(§1-3)이다.

---

## 18. 평가 지표 (설계자 지정)

| 지표 | 현재 | POC4 |
|---|---|---|
| KRX200 대비 수익률 | **있음** (069500 대리) | 유지 |
| MDD | **없음** | POC4-01 추가 |
| 변동성 | 종목 feature 만 | 전략 수준 추가 |
| 회전율 | **있음** (turnover 0.8261) | 유지 |
| 승률 | **있음** (win_rate 0.4483) | 유지 |
| 거래비용 반영 성과 | **있음** (net by cost bp) | 슬리피지 분해 추가 |
| Sharpe · equity curve | **없음** | 추가 |
| IC · 분위스프레드 | **있음** | 유지 |

---

## 19. 5년 walk-forward 백테스트 가능 여부 — **가능**

```text
가격 이력    2014-04-09 ~ 2026-09-21 (12.4년) · 1,405,608행
벤치마크     KODEX200 069500 · 3,055행 · 결측 0
feature      1,382,327행 · 2014-05-12 ~ 2026-08-27
거래일 축    3,038일 · 월말 149 · 평가시점 145 (기존 산출 실적)
walk-forward 규율 · PIT 절단 · 누수 검사  이미 구현
```

**5년은 물론 12년도 가능하다.** 단 §12-3 의 생존편향 때문에 최종 판정 상한은
`RESEARCH_ONLY` 로 유지하는 것이 정직하다.

---

## 20. KS-10 측정 (현재값)

```text
전수 484 · TRIGGER 0 · NEAR 7
```

POC4 가 건드릴 파일 중 주의 대상:

```text
626  app/ml_score_validity_report.py   ← NEAR. POC4-01 에서 지표 추가 시 650 초과 위험
641  app/api.py                        ← NEAR. 라우터 추가 시 주의
646  scripts/run_three_push_runtime_oci.py  ← 동결선 648. POC4 는 건드리지 않는다
```

---

## 21. 죽은 코드·미연결 artifact 정리 대상

| 대상 | 조치 제안 |
|---|---|
| `BacktestRunner` 언급 (`CLAUDE.md:25`·`AGENTS.md:108`·`VERIFY_RULES.md:108`) | **stale 문구 정정** — 존재하지 않는 심볼을 운영 경로 예시로 듦 |
| `state/ml/validity/...json` (885KB) | POC4-05 에서 reader 를 만들어 화면 연결 |
| `market_flow_*` 산출물 4종 | 미실행 — POC4-03 에서 쓸지 폐기할지 결정 |
| `etf_ml_feature_daily` 미사용 feature 6개 | POC4-03 feature 후보로 편입 |

---

## 22. 이 PLAN 의 한계 (정직하게)

1. **조사 자동화가 일부 실패했다.** 6개 영역 병렬 조사 중 1개만 완주하고 5개가
   stall 했다. 나머지는 개발자가 직접 훑었고, **`backtest` 영역만큼의 깊이는
   아니다.** 특히 `app/ml_baseline_*.py` 계열(baseline v0)과
   `app/ml_feature_*.py` 의 내부 계산은 얕게 봤다.
2. **소스 전환 경계(L-8)는 미확인**이다. 검증하려면 코드를 돌려야 하는데 이
   단계는 `CODE_CHANGE = 0` 이다.
3. **생존편향의 크기·방향을 정량화하지 못했다.** 상장폐지 목록이 없어서다.
4. artifact 가 2026-08-30 자라 **현 코드로 재현되는지 확인하지 않았다**(POC4-02
   첫 과제).

---

## 23. 설계자에게 묻는 것 (요약)

```text
Q1  RF/XGB/LGBM 금지 제약 해제 범위 + xgboost·lightgbm 의존성 승인     §12-1
Q2  label 축 — 회귀 유지 / Q6 분류로 이동 / 병행                        §12-2
Q3  생존편향 처리 방침 — (a)+(c) 제안, (b) 는 외부 데이터라 별도 승인   §12-3
Q4  POC4-05 "evidence 연결" 범위 — 화면까지인가 PUSH 본문까지인가       §17
Q5  단계 수 조정 필요 여부 (현재 초안 6단계 유지)                       §11
```

확정되면 `POC4-01` 부터 착수한다. 이 단계에서는 코드·DB·OCI·PUSH 를 변경하지
않았다.
