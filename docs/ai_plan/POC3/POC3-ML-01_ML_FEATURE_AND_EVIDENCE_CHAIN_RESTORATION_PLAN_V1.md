# POC3-ML-01 — ML Feature & Evidence Chain Restoration (개발 PLAN V1)

- **작성**: 개발자
- **수신**: 설계자
- **작성일**: 2026-08-24 (**최종 보완 반영본** — 설계자 확정 M-1~M-5 · D-1~D-4 적용)
- **입력 설계서**: `docs/ai_design/POC3/POC3-ML-01_ML_FEATURE_AND_EVIDENCE_CHAIN_RESTORATION_DESIGN_V1.md`
- **대상 결함**: `DEF-ML-CHAIN` (`docs/backlog/BACKLOG.md` §현재 결함)
- **상태**: **`PLAN PASS`** → 구현 완료(`f21143e7`) → **검증자 REJECTED r1 정정 반영**(2026-08-25).
  결과서 `docs/ai_result/POC3/POC3-ML-01_..._RESULT.md`.
  추가 PLAN 문서·재검토 요청 없음. 다음 보고는 **구현 결과서**(`ai_result/`).
- **본 PLAN 작성 중 수행**: 코드·DB **읽기 전용 확인만**.
  코드 0건 · DB write 0건 · 상태 파일 0건 · ML job 실행 0건 · 외부 조회 0건 · **커밋 0건**.

---

## 0. 이번 보완에서 바뀐 것

### 0.1 모호점·결정 — 전부 확정됨 (미결 0건)

| # | 확정 내용 | PLAN 반영 |
|---|---|---|
| M-1 | `ai_design`·`ai_plan`·`ai_result` 는 정식 산출물. 그 외 조사·중간보고 문서 금지 | 본 PLAN 외 문서 생성 0건 |
| M-2 | **두 독립 체인**. 체인 A 를 체인 B 입력으로 표현 금지. **둘 다 완료 범위** | §1 · §4.2 실행순서 |
| M-3·M-4 | `market_risk_feature_daily` **선택 아님** — 함께 적재, baseline·sanity·readiness 필수 입력 | §3.4 · §5 |
| M-5 | `failed` 상태 파일 **직접 수정·삭제 금지**. 성공 실행 결과로 자연 갱신 | §4.2-8 · §8 |
| D-1 | **전체 가용 기간** backfill (상장 이후 ~ 가격 최신일, 분할 실행) | §3.5 · §4.2 |
| D-2 | 체인 A universe = **가격 존재 ETF 전체**. 소비 필터와 혼동 금지 | §3.4 |
| D-3 | 일별 증분 **수동 실행**. 스케줄러·OCI 변경 금지 | §4.1 |
| D-4 | **B-2 포함** — 생성 → 0건 가드 → 성공 확인 → snapshot 기록 | §3.2 |

### 0.2 ⚠ 조사로 **뒤집힌** 개발자 판단 3건

| # | 이전 PLAN | 재확인 결과 |
|---|---|---|
| **B-1** | *"테스트 격리 누락 정황 → 수정 필요"* | **철회.** 5개 경로 전부 격리돼 있고 **2026-06-11부터 완비**(§2.4). 코드 변경 안 함 |
| **`drawdown_from_high_pct`** | 이전 보고에서 이 이름으로 "실측 None" 이라 적음 | **존재하지 않는 필드다.** `.get()` 이 없는 키에 `None` 을 준 것을 실측으로 오인(§6.2) |
| **"코드 결함이 없다"** | 단정 | **하향.** *"읽기 전용 확인에서는 결함을 찾지 못했다. 실제 실행 검증 전까지 코드 정상은 확정하지 않는다"* (§2.3) |

---

## 1. 현재 코드 경로

**두 개의 독립 체인이다**(M-2 확정).

### 1.1 체인 A — feature 적재

```
etf_daily_price + market_benchmark_daily_price + etf_nav_daily
  → app/ml_feature_builder.build_features()
  → app/ml_feature_store.upsert_etf_features / upsert_market_risk_features
  → etf_ml_feature_daily (PK asof,ticker) · market_risk_feature_daily (PK asof)
  → state/ml/ml_feature_snapshot_latest.json
  → sanity · baseline · readiness
```

| 구분 | 경로 |
|---|---|
| CLI | `scripts/generate_ml_features.py` — `--start-date` `--end-date` `--lookback-days` `--ticker` **`--db`** `--no-snapshot` |
| Job | `POST /ml/jobs/evidence-refresh`(`api_ml_jobs.py:130`) → `ml_job_runner` 3단계 |
| 소비 | `ml_feature_sanity` · `api_ml_readiness` · `ml_baseline_v0` · `ml_baseline_targets` · `ml_baseline_candidate` · `ml_baseline_risk` |

### 1.2 체인 B — 참고점수·사유·고점대비

```
etf_daily_price          ← feature 테이블을 거치지 않는다
  → app/ml_relative_upside_features.build_feature_rows_for_ticker()
  → app/ml_relative_upside_model.train_walk_forward / predict_raw_scores (torch)
  → app/ml_relative_upside_score.save_score_snapshot
  → state/ml/relative_upside_score_latest.json (+ _run_latest.json)
  → api_market_topn_service.merge_relative_upside_score()
  → GET /market/topn/latest → 화면
```

| 구분 | 경로 |
|---|---|
| CLI | `scripts/run_ml_relative_upside_score_v0.py` — **인자 `--candidates` 하나뿐** |
| API | `POST /market/relative-upside/run`(`api_ml_relative_upside.py:86`) → `main(argv=[])` **동기 호출** |
| 화면 | `CandidateCards.tsx:84,202` · `CandidateTable.tsx:296,300` · `HoldingsCompareView.tsx:172-173`(정렬) |

**근거**: `ml_relative_upside_features.py` 는 `fetch_price_history`(=`etf_daily_price`) 만 쓰고
feature 테이블을 import 하지 않는다.

---

## 2. 0행 및 evidence 부재 원인

### 2.1 확인된 사실

| # | 사실 | 근거 |
|---|---|---|
| 1 | 입력 데이터 충분 | KODEX200 **3,033거래일** `2014-04-09`~`2026-08-20` · 가격 ticker **1,174** · KOSPI **6,111행** |
| 2 | `build_features` 0행 조건은 2개뿐 | `ml_feature_builder.py:250`(KODEX200 부재) · `:266`(asof 창 공집합). **둘 다 해당 없음** |
| 3 | upsert 정상 커밋 | `ml_feature_store.py:105-112` `con.commit()` |
| 4 | 0건 가드 존재 | `ml_job_runner.py:337` — `etf<=0 **and** mkt<=0` 시 `RuntimeError` |
| 5 | **live 에 feature snapshot 없음** | `state/ml/` 에 `ml_feature_snapshot_latest.json` **부재** |
| 6 | 점수 snapshot 파일 없음 | `relative_upside_score_latest.json` 부재 → `merge_relative_upside_score` 가 `status="unavailable"`(`api_market_topn_service.py:123-130`) |
| 7 | **API 실측 (정정된 필드명)** | `GET /market/topn/latest?n=5&basis=one_month&order=desc` → `status="unavailable"` · 후보 5건 전부 `relative_upside_score=None` · **`drawdown_20d=None`** · `reasons` 길이 0 |
| 8 | torch 사용 가능 | `torch 2.13.0`. CUDA 없으면 **CPU fallback**(`ml_relative_upside_model.py:92-101`) |
| 9 | 가격은 job 이전부터 존재 | `market_refresh_log` — 1,140종목 대량 적재 `2026-06-17T14:17Z`. job 은 `2026-08-17T04:00Z` |

### 2.2 실패 job 의 정체 — 재조사 결과

| 확인 | 결과 |
|---|---|
| `requested_by="test"` 를 넘기는 곳 | **`tests/test_ml_job_runner.py` 뿐**(10곳). API 는 `requested_by="ui"`(`api_ml_jobs.py:157`) |
| 그 테스트가 step 함수를 가짜로 바꾸나 | **그렇다** — `monkeypatch.setitem(_STEP_FUNCS, ...)`(`:150-153,208,226,250,278`) |
| 남은 상태의 내용 | `feature_generation=success` · `sanity_check=failed` · `baseline=skipped` |

**정합적 해석**: feature 단계는 **가짜 함수라 success**, sanity 단계는 **진짜 함수가 live DB
(0행)를 읽어 error**. 산출물이 live 경로에 남은 것은 **job 스레드가 fixture teardown 이후까지
살아남아 monkeypatch 가 원복된 뒤 기록**했기 때문으로 본다.

> 이 스레드 누수는 **A11(2026-08-17)에서 teardown 이 스레드를 `join` 한 뒤 락을 해제하도록
> 고쳐 이미 해소**됐다. 날짜도 일치한다.

### 2.3 결론 (표현 하향 — 설계자 §12)

> **읽기 전용 코드 확인에서는 현재 0행을 설명하는 코드 결함을 찾지 못했다.
> 실제 실행 검증 전까지 코드 정상은 확정하지 않는다.**

가장 정합적인 설명은 **"live DB 대상으로 실행된 적이 없다"** 이며, §4.2 실행으로 검증한다.

### 2.4 B-1 확인 결과 — **코드 변경 불필요** (설계자 §3)

`_run_sanity`·`_run_baseline` 이 기록하는 **모든 상태 경로를 열거**했다.

| 단계 | 기록 경로 | 정의 위치 | 테스트 격리 |
|---|---|---|---|
| feature | `SNAPSHOT_PATH` | `scripts/generate_ml_features.py` | ✅ `monkeypatch.setattr(gmf, "SNAPSHOT_PATH", ...)` |
| sanity | `SANITY_SNAPSHOT_PATH` | `app/api_ml_sanity` (함수 내부 import — `ml_job_runner.py:350`) | ✅ `monkeypatch.setattr(api_ml_sanity, ...)` |
| baseline | `BASELINE_REPORT_PATH` | `app/api_ml_baseline` (함수 내부 import — `:375`) | ✅ `monkeypatch.setattr(api_ml_baseline, ...)` |
| job status | `JOB_STATUS_PATH` | `ml_job_runner` | ✅ |
| job status(API) | `JOB_STATUS_PATH` | `api_ml_jobs` | ✅ |

**5개 경로 전부 격리돼 있다.** 함수 내부 import 라 `monkeypatch.setattr` 이 호출 시점에
반영된다. 격리 fixture 는 **`b855a982`(2026-06-11)부터 완비** — 2026-08-17 job 보다 앞선다.

> **따라서 B-1 은 철회한다.** 설계자 §3 대로 *"이미 모두 격리됐다면 코드 변경하지 않고
> 근거만 기록"*. 이전 PLAN 의 "오염 정황" 추정은 **원인 지목이 틀렸다** — 경로 격리 누락이
> 아니라 **스레드 누수**였고 그것은 A11 에서 이미 고쳐졌다(§2.2).

---

## 3. 구현 계획

### 3.1 코드 변경 없이 되는 것

| 목적 | 사용 |
|---|---|
| feature backfill · 증분 | `scripts/generate_ml_features.py` |
| sanity | `scripts/check_ml_feature_sanity.py` |
| baseline | `scripts/run_ml_baseline_v0.py` |
| 점수·사유·고점대비 | `scripts/run_ml_relative_upside_score_v0.py` |

### 3.2 코드 변경 — **B-2 1건만** (D-4 확정)

| 변경 파일 | 함수 | 현재 | 변경 후 |
|---|---|---|---|
| `app/ml_job_runner.py` | `_run_feature` | ① 생성 → ② **snapshot 기록**(`:333-335`) → ③ 0건 가드(`:337`) | ① 생성 → ② **0건 가드** → ③ 성공 확인 → ④ **snapshot 기록** |

**효과**: upsert 0건인 실패 job 이 *"성공한 것처럼 보이는 snapshot"* 을 남기지 않는다.

**범위 제한(설계자 D-4)**: `_write_status` 원자적 교체(A11) 로 **범위를 확장하지 않는다.**

**회귀 테스트**: `_run_feature` 가 0건일 때 **`RuntimeError` 발생 + snapshot 파일 미생성**을
검증하는 테스트 1건 추가(`tests/test_ml_job_runner.py`).

### 3.3 DB write 범위

**두 테이블만. 신규 테이블 0건.**

```sql
etf_ml_feature_daily       INSERT ... ON CONFLICT(asof, ticker) DO UPDATE
market_risk_feature_daily  INSERT ... ON CONFLICT(asof)         DO UPDATE
```

`etf_daily_price` · `market_benchmark_daily_price` · `etf_nav_daily` **read-only**.

### 3.4 데이터 생성 계약

| 항목 | 계약 | 근거 |
|---|---|---|
| feature 입력·lookback | 5/10/20일 수익률 · KODEX200 대비 초과수익(5/10/20) · `volatility_20d` · `drawdown_20d` · `volume_ratio_20d` · NAV 4필드 | 컬럼 20개 실측 |
| 거래일 기준 | **KODEX200(`069500`) 시퀀스** | `ml_feature_builder.py:249` |
| 생성 가능 최초일 | KODEX200 기준 **20거래일 이후** ≈ `2014-05-13`. **ETF 별로는 각자 상장 이후 20거래일**(D-1) | 최장 lookback 20 |
| **universe (D-2 최종)** | **`etf_master` 등록 + 가격 존재 ETF = 1,171.** `list_etf_tickers()` 가 그대로 정답 | `market_data_store.py:330-333` |
| 유일성 | `(asof, ticker)` / `(asof)` PK | `ml_feature_store.py:45,52` |
| 멱등성 | `ON CONFLICT DO UPDATE` — **재실행 시 행 증가 0** | `:189,301` |
| 부분 실패 | 시계열 없는 ticker 는 `missing_series_count` 집계 후 건너뜀 | `:283-289` |
| 결측 | lookback 부족 → `None`. NAV 없으면 `nav_status` 구분. **`0` 대체 없음** | 완료조건 10 |
| `market_risk` | **함께 적재**(M-3·M-4). 분리 실행 경로 없음 | `generate_ml_features.py:104-105` |

### 3.5 backfill 범위·배치 (D-1 확정)

**전체 가용 기간.** 각 ETF 상장 이후 + lookback 충족 최초일 ~ 가격 최신일(`2026-08-20`).

| 구간 | asof 수 | 예상 행 수 |
|---|---|---|
| 1년 | ~245 | ~287,000 |
| **전 구간(2014~)** | ~3,013 | **~3,500,000** |

`build_features` 는 ticker 별 전체 시계열을 메모리 prefetch 한다(`:280-290`).
→ **연도 단위 분할 실행**(D-1 *"안전한 기간 단위"*). 멱등이라 중단·재개 안전.

---

## 4. 실행 계획

### 4.1 live DB 계약 (설계자 §12 — 필수)

| 항목 | 값 |
|---|---|
| **live SQLite 절대경로** | `/Users/hyungsookim/projects/krx_hyungsoo/state/market/market_data.sqlite` |
| **정본 확인 방법** | `python -c "from app.market_data_store import DEFAULT_DB_PATH; print(DEFAULT_DB_PATH.resolve())"` 가 위 경로와 **일치** + 파일 크기 **136,921,088 bytes** |
| **실행 전 가격 실측** | `etf_daily_price` **1,379,939행** · 최신 `2026-08-20` · KODEX200 **3,033행** · KOSPI **6,111행** |
| **실행 후 확인** | 같은 DB 에서 `etf_ml_feature_daily` / `market_risk_feature_daily` **행 수 · `max(asof)`** |

**환경 변수 고정** (default 의존 제거):

```bash
DB=/Users/hyungsookim/projects/krx_hyungsoo/state/market/market_data.sqlite
```

> **⚠ 체인 B CLI 에는 `--db` 인자가 없다.** `run_ml_relative_upside_score_v0.py` 의 argparse
> 인자는 **`--candidates` 하나뿐**이며 `list_etf_tickers()`·`fetch_price_history()` 의
> `DEFAULT_DB_PATH` 기본값을 그대로 쓴다. → **§7 판단 요청 ①**

### 4.2 실행 순서 (설계자 §15 — 화면 복구 우선)

```bash
DB=/Users/hyungsookim/projects/krx_hyungsoo/state/market/market_data.sqlite

# 1. live DB · artifact 경로 확인
python -c "from app.market_data_store import DEFAULT_DB_PATH; print(DEFAULT_DB_PATH.resolve())"
sqlite3 "$DB" "select count(*), max(date) from etf_daily_price;"

# 2~3. 체인 B 후보 계약 확인 후 실행  (§5 · --db 인자 없음 → §7-①)
python scripts/run_ml_relative_upside_score_v0.py

# 4. API 확인
curl -s "http://127.0.0.1:8000/market/topn/latest?n=10&basis=one_month&order=desc"

# 5. 화면 3종 + 고점대비 정렬 확인

# 6. 체인 A 전체 backfill — 연도 단위 분할, --db 명시
#    ⚠ 시작일은 **lookback 충족 최초일**(D-1). KODEX200 첫 거래일(2014-04-09)이 아니다.
#      첫 거래일부터 돌리면 20일 lookback 불가로 risk proxy 전부 NULL 인 행이 생겨
#      sanity 가 error 가 된다 (2026-08-24 실행에서 실제 발생 · 결과서 §3.4).
python scripts/generate_ml_features.py --db "$DB" --start-date 2014-05-12 --end-date 2014-12-31
# ... 연도별 반복 ...
python scripts/generate_ml_features.py --db "$DB" --start-date 2026-01-01 --end-date 2026-08-20

# 7. sanity · baseline
python scripts/check_ml_feature_sanity.py --db "$DB"
python scripts/run_ml_baseline_v0.py --db "$DB"

# 8. job 성공 확인 — 상태 파일을 편집하지 않는다 (M-5)
curl -s -X POST "http://127.0.0.1:8000/ml/jobs/evidence-refresh"
curl -s "http://127.0.0.1:8000/ml/jobs/latest"

# 9. 전체 완료 검증 (§6)
```

> `check_ml_feature_sanity.py` · `run_ml_baseline_v0.py` 의 `--db` 인자 존재 여부는
> **착수 시 먼저 확인**하고, 없으면 §7-① 과 같은 처리로 올린다.

### 4.3 실행 환경 (D-3 확정)

| 작업 | 환경 | 근거 |
|---|---|---|
| 과거 backfill (일회성) | **PC 또는 맥** | 순수 SQLite 연산 · 외부 호출 0 · GPU 불필요 |
| **일별 증분** | **수동 실행** | D-3 — 자동 스케줄러 추가 금지 |
| 점수 계산 | PC 권장 / 맥 가능 | torch 2.13.0 · CUDA 없으면 CPU fallback |
| **OCI** | **역할 없음 · 변경 0건** | ML 산출물 **OCI 전달 금지**(`ml_relative_upside_score.py:11`) |

**PC 는 ML 계산 주체일 뿐 PUSH 발송 주체가 아니다.**

### 4.4 실패 시 재개

| 대상 | 재개 |
|---|---|
| feature | **멱등** — 실패 구간만 재실행 |
| 점수 | `main()` 예외 시 **기존 snapshot 변경 0건**(`api_ml_relative_upside.py:11-15`) |
| job | 단계 실패 시 이후 `skipped`, 이전 산출물 유지(`:417-428`) |

---

## 5. 체인 B 후보 입력 계약 (설계자 §13 — 코드 확인 결과)

| 질문 | 확인 결과 | 근거 |
|---|---|---|
| `--candidates` 형식·source | **콤마 구분 ticker 문자열.** 사용자가 직접 지정 | `run_ml_relative_upside_score_v0.py:80-82,155-156` |
| **`main(argv=[])` 시 후보 결정** | `args.candidates` 가 `None` → **`all_tickers` 전체에서 KODEX200 만 제외** | `:157-158` |
| `all_tickers` source | **`list_etf_tickers()` = `etf_master` 전체(1,171)** | `market_data_store.py:330-333` |
| 학습 대상 | 동일 universe 전체 시계열로 walk-forward 1회 split | `:98,142` |
| 후보 ETF 포함 | **포함**(전체이므로) | |
| **보유 ETF 포함** | **포함**(전체이므로). 단 `etf_master` 에 없는 **개별주는 제외** | `etf_master` 는 ETF universe |
| 가격 부족 | `history` 없으면 `continue`, `is_complete_for_inference` 불충족이면 제외 | `:163-176` |
| 상장폐지 | 별도 처리 없음 — 가격이 없으면 자동 제외 | |
| 중복 ticker | `etf_master` PK 가 ticker 라 중복 불가 | |
| **snapshot 최종 범위** | **최신 asof feature 가 완성된 ticker 전부** | `:170-176` |

### ⚠ 설계자 §13 *"근거 없이 1,174종목 전체를 torch 점수 대상으로 확장하지 않는다"* 에 대해

**확장이 아니라 기존 계약이 이미 전체다.** `POST /market/relative-upside/run` →
`main(argv=[])` → 전체 universe. 화면의 참고점수 실행 버튼이 이 경로를 쓴다.

**개발자는 이 계약을 바꾸지 않는다.** 좁히려면 설계 결정이 필요하다 → **§7 판단 요청 ②**.

> 화면 요구(후보 ETF + 보유 ETF 값이 빠지지 않을 것)는 **전체 대상이면 자동 충족**된다.

---

## 6. evidence 필드 계약 (설계자 §14)

### 6.1 단계별 대응표

| 단계 | 실제 필드명 | 위치 |
|---|---|---|
| **score snapshot** | `relative_upside_score` · `relative_upside_reasons` · **`drawdown_20d`** | `ml_relative_upside_score.py:99-140` |
| **API payload** | `relative_upside_score` · `relative_upside_reasons` · **`drawdown_20d`** | `api_market_topn_models.py:129-131` |
| **프론트 타입** | `relative_upside_score` · `relative_upside_reasons` · **`drawdown_20d`** | `frontend/lib/api/market.ts:81-83` |
| **프론트 표시** | `c.drawdown_20d != null ? c.drawdown_20d * 100 : null` | `CandidateCards.tsx:84` · `CandidateTable.tsx:296` |
| **정렬 sort key** | **`"drawdown"`** (내부 키 문자열) → 값은 `c.drawdown_20d` | `HoldingsCompareView.tsx:43,172-173` |

### 6.2 세 명칭의 관계 — 확정

| 명칭 | 정체 |
|---|---|
| **`drawdown_20d`** | **유일한 실제 데이터 필드.** snapshot → API → 프론트까지 **이름이 동일**하다 |
| **`drawdown`** | **프론트 정렬 키 문자열일 뿐.** 데이터 필드가 아니다 |
| **`drawdown_from_high_pct`** | **존재하지 않는다.** `grep -rn` 결과 `app/`·`frontend/` **0건** |

> **⚠ 개발자 오류 정정**: 이전 보고에서 API 실측이라며 `drawdown_from_high_pct=None` 을
> 적었다. **`.get()` 이 없는 키에 `None` 을 돌려준 것**이며 측정이 아니었다.
> 올바른 키로 재측정한 결과는 §2.1-7 이다(`drawdown_20d` 키 존재 확인 + 값 `None`).
>
> 이는 2026-08-16 에 고친 `candExcess` 버그(없는 키 `excess_return_pct` 를 읽어 항상 `—`)
> 와 **같은 유형**이다.

### 6.3 `relative_upside_reasons=[]` 계약

**빈 배열은 정상 허용된다.** `build_reasons`(`ml_relative_upside_score.py:41-98`)는
**조건부 append** 구조다.

```
if all(v is not None for v in (ex5, ex10, ex20)):   → 조건 불충족 시 아무것도 안 넣음
if dd is not None:                                   → 마찬가지
```

입력 feature 가 `None` 이면 사유가 하나도 안 붙을 수 있다.

> **따라서 "모든 ticker 의 reasons 가 비어 있지 않아야 한다" 는 AC 를 만들지 않는다**
> (설계자 §14). 대신 **snapshot 전체에서 reasons 가 1개 이상인 ticker 가 존재**하는지로
> 생성 동작을 확인한다(§6 검증).

---

## 7. 설계자 최종 확정 (2026-08-24) — 미결 0건

### 7.1 feature universe = **1,171 ETF** (확정)

**계약**: *"`etf_master` 에 등록되어 있고 가격 데이터가 존재하는 ETF 전체"*

| 구분 | 값 |
|---|---|
| **ETF feature universe** | **1,171** |
| 가격 테이블 전체 ticker | 1,174 |
| 차이 | **보유 개별주 3종목** |

**1,174 는 ETF 수가 아니라 `etf_daily_price` 의 전체 ticker 수였다.**

#### 차이 3종목 — 조사 결과 (확인된 사실)

| 항목 | `000660` | `005930` | `006400` |
|---|---|---|---|
| 이름(holdings 입력값) | SK하이닉스 | 삼성전자 | 삼성SDI |
| `etf_master` 등록 | **없음 — ETF 가 아님** | 〃 | 〃 |
| 가격 행 수 | 93 | 93 | 93 |
| 가격 기간 | 2026-03-30 ~ **2026-08-12** | 〃 | 〃 |
| 2026-08-20 도달 | **아니오** | 아니오 | 아니오 |
| holdings 포함 | **예**(오픈뱅킹 1주) | **예**(ISA 3주) | **예**(오픈뱅킹 1주) |
| universe seed 포함 | 아니오 | 아니오 | 아니오 |
| 후보·score 참조 | **아니오**(`list_etf_tickers()` 가 `etf_master` 기준이라 구조적 제외) | 〃 | 〃 |
| 상장폐지·비활성 근거 | **없음** — 갱신 대상에서 빠진 것일 뿐(`market_refresh_service.py:297`) | 〃 | 〃 |

#### 취급 (확정)

| 대상 | 처리 |
|---|---|
| ETF feature · relative-upside score | **제외** |
| 보유자산 · holdings evidence | **유지** |
| `market_risk` universe breadth | **제외** |
| 가격 데이터 삭제 | **금지** |

> `2026-08-12` 이후 미갱신은 **ML Step 을 막지 않는다.**
> **결과서의 범위 밖 관찰사항으로만 남기고 별도 기능으로 확대하지 않는다.**

> **개발자 이전 추정 정정**: *"`etf_master` 에서 사라진 종목"* 이라고 했으나 틀렸다.
> **처음부터 ETF 가 아니었다.**

### 7.2 CLI `--db` — 확정

| CLI | `--db` | 처리 |
|---|---|---|
| `generate_ml_features.py` | **있음** | `--db "$DB"` **명시** |
| `check_ml_feature_sanity.py` | **있음** | `--db "$DB"` **명시** |
| `run_ml_baseline_v0.py` | **있음** | `--db "$DB"` **명시** |
| `run_ml_relative_upside_score_v0.py` | **없음**(`--candidates` 만) | **인자 추가하지 않는다.** 실행 전 `DEFAULT_DB_PATH.resolve()` 가 live 절대경로와 **불일치하면 중단** |

### 7.3 B-2 가드 — **순서 + 조건 동시 수정** (확정)

```text
기존:  etf_upserted <= 0 and market_upserted <= 0
변경:  etf_upserted <= 0 or  market_upserted <= 0
```

**근거**: 두 산출물 모두 evidence-refresh job 의 **필수**이며, 하나라도 없으면 sanity·baseline 이
정상 완료될 수 없다.

`market_risk_feature_status="empty"` 는 **job 성공 허용 의미가 아니다** — CLI 단독 실행 ·
과거/부분 적재 DB · readiness 조회 · 실패 원인 표시의 **진단 표현**으로 계속 유효하다.
**상태 모델은 `empty` 를 표현할 수 있으나 job 성공 계약은 더 엄격하다.**

**최종 순서**

```text
feature 생성 · DB upsert
→ ETF 또는 market 중 하나라도 0건이면 실패
→ snapshot 미생성
→ 둘 다 양수일 때만 snapshot 생성
```

**부분 upsert 가 DB 에 반영됐어도 rollback 을 추가하지 않는다** — 파생 테이블 + 멱등 upsert 라
실패 구간 재실행으로 복구한다.

**테스트 4종**: `(0, 양수)` · `(양수, 0)` · `(0, 0)` → 실패 + snapshot 없음 /
`(양수, 양수)` → 성공 + snapshot 생성.

### 7.4 실행 환경 — **Mac 고정** (확정)

- 최초 backfill · 체인 B 실행: **Mac**
- live DB: **현재 Mac 절대경로**. **PC·OCI·DB 복사 경로 추가 없음**
- 체인 B 는 **CPU fallback 실행 후 소요시간 기록**

---

## 8. 검증 계획 (설계자 §16 반영)

### 8.1 최신일 검증 — 구체화

`feature max(asof) <= price max(date)` 만으로는 **오래된 feature 도 통과**하므로 아래로 한다.

| 대상 | 기준 |
|---|---|
| `market_risk_feature_daily.max(asof)` | **요청 종료일의 마지막 KODEX200 거래일과 일치** |
| ETF feature | **가격·lookback 을 충족한 대상별 예상 최신일과 일치** |
| 미달 ticker | **누락 사유가 집계**됨(`missing_data_summary`) |

### 8.2 필수 검증 항목

| 구분 | 항목 |
|---|---|
| 변경 코드 테스트 | B-2 회귀 1건(0건 시 `RuntimeError` + snapshot 미생성) + `tests/test_ml_job_runner.py` **21건** 재통과 |
| ML 관련 테스트 | `test_ml_feature_sanity.py` 등 feature·sanity·score 테스트 |
| **백엔드 전체 pytest** | **1회** (직전 기준 1,157 passed) |
| DB | 행 수 · 유일성(PK 중복 0) · **멱등성(동일 구간 2회 실행 → 행 수·값 동일)** · 최신일(§8.1) |
| **warm-up / 성숙 구간 구분** | **feature 행 생성 시점 ≠ 20일 feature 완성 시점.** warm-up 구간은 `return_20d IS NULL` 행이 **존재**해야 하고(결측 위장 없음), 성숙 구간은 **non-null** 이어야 한다 — **양쪽 모두 검증** |
| API payload | `relative_upside_score_status == "ok"` · `relative_upside_score` · `drawdown_20d` 비-null · **reasons 는 1개 이상인 ticker 존재**(§6.3) |
| UI | 참고점수 · 사유 · 고점 대비 표시 + **`고점대비` 정렬 시 순서 실제 변경** |
| job | `POST /ml/jobs/evidence-refresh` → `status=success`. **상태 파일 편집 0건**(M-5) |

**프론트 코드를 변경하지 않으므로 `tsc`·`eslint`·`vitest` 전체 실행은 필수에서 제외**(설계자 §16).

---

## 9. 범위 밖

설계서 §5 전부 유지. `FDR timeout` · 신규 endpoint·테이블·외부 조회 · 신규 ML 모델 ·
RF/XGB/LGBM/Optuna · 새 점수 공식·임계값 · 매수·매도 자동화 · UI 재설계 · BACKLOG 재조사 ·
PC package 정식 PUSH 복귀 · 관련 없는 운영 코드 정리.

**추가 제한**: `_write_status` 원자적 교체(A11) 로 **범위 확장 없음**(D-4).
**`고점 대비` 열·정렬 유지**, 표시 형태 변경 없음.

---

## 10. 부수 기록

실패로 남은 ML job 은 **테스트 스레드 누수의 잔여물**이며(§2.2), 그 누수는 **A11 에서 이미
해소**됐다. 설계 확정(M-5)대로 **상태 파일을 건드리지 않는다** — §4.2-8 의 성공 실행으로
자연 갱신된다.
