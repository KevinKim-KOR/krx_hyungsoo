# POC3-ML-01 — ML Feature & Evidence Chain Restoration (개발 결과서)

- **입력 설계서**: `docs/ai_design/POC3/POC3-ML-01_..._DESIGN_V1.md`
- **개발 PLAN**: `docs/ai_plan/POC3/POC3-ML-01_..._PLAN_V1.md` (`PLAN PASS — IMPLEMENTATION AUTHORIZED`)
- **기준점 커밋**: `c95be6f0` (DESIGN + PLAN)
- **작업일**: 2026-08-24 (맥북)
- **대상 결함**: `DEF-ML-CHAIN` (`docs/backlog/BACKLOG.md` §현재 결함)
- **상태**: 구현·실행 완료 → r1 `REJECTED` → r2 정정 → **r2 `REJECTED`(승인 기록 모순)**
  → **r3 정정 반영**(2026-08-25).
  - 완료조건 11개 중 **9개 실측 충족**.
  - **8·9(UI 표시·정렬)**: 검증자 기술 확인 **통과** · **사용자 최종 확인 대기**.
  - **파생 DB 1,985행 삭제**: **사용자 승인 완료**(§10.5 원문).
  - r1 지적 4건 → **§10.1~10.4** · r2 지적(승인 기록·해시 표기) → **§10.5 · §4.2**.

---

## 1) 처리한 요구사항

| 요구사항 | 결과 |
|---|---|
| 1. `etf_ml_feature_daily` 정상 데이터 적재 | **DONE** — 1,376,524행 |
| 2. `market_risk_feature_daily` 함께 생성 | **DONE** — 3,013행 |
| 3. 과거~최신 기준일 연결 | **DONE** — `max(asof)` = KODEX200 최종 거래일 |
| 4. 재실행 중복·값 변형 없음 | **DONE** — 2회 실행 행 수·해시 동일 |
| 5. score·reasons·drawdown evidence 생성 | **DONE** — 1,157종목 |
| 6. ML job·sanity 정상화 | **DONE** — job 3단계 success · sanity errors 0 |
| 7. API 실제 값 전달 | **DONE** — `status: ok` |
| 8. UI 3종 표시 | **PENDING** — 사용자 실화면 확인 필요 |
| 9. 고점대비 정렬 동작 | **PENDING** — 사용자 실화면 확인 필요 |
| 10. 계산 불가 종목 `0` 위장 없음 | **DONE** — warm-up NULL 20,190행 유지 |
| 11. 가격·PUSH 경계 무변경 | **DONE** — 가격 read-only · OCI 0건 |

### 1.1 코드 변경 — B-2 1건

`app/ml_job_runner.py :: _run_feature` — 설계자 D-4 확정대로 **순서와 조건을 함께** 수정.

```python
# 이전:  snapshot 기록 → 가드(and)
# 이후:  가드(or) → snapshot 기록

if etf_upserted <= 0 or mkt_upserted <= 0:
    raise RuntimeError(
        f"feature generation upsert 0건 — etf={etf_upserted} market={mkt_upserted}. "
        "두 산출물 모두 필수이며 DB 가 비어있거나 universe coverage 0 이다"
    )
# 둘 다 양수일 때만 snapshot 을 남긴다.
```

`market_risk_feature_status="empty"` 가 진단 표현으로 유효하다는 것과 job 성공 계약이 더
엄격하다는 것, 부분 upsert 를 rollback 하지 않는 이유(파생 테이블 + 멱등)를 **주석에 명시**했다.

**B-1 은 철회**(PLAN §2.4) — 상태 경로 5개가 `b855a982`(2026-06-11)부터 전부 격리돼 있어
코드 변경이 필요 없었다.

### 1.2 회귀 테스트 4건

| ETF | market | 기대 | 결과 |
|---|---|---|---|
| 0 | 양수 | 실패 · snapshot 없음 | ✅ |
| 양수 | 0 | 실패 · snapshot 없음 | ✅ |
| 0 | 0 | 실패 · snapshot 없음 | ✅ |
| 양수 | 양수 | 성공 · snapshot 생성 | ✅ |

**역검증**: 기준점 커밋(`c95be6f0`)의 `_run_feature` 로 되돌리면 **4건 중 3건 실패**.
`(양수, 0)` 이 옛 `and` 조건에서 성공으로 통과하던 케이스다.

---

## 2) 변경된 파일 목록

`git diff --numstat` 실측:

| 파일 | 구분 | 추가 | 삭제 |
|---|---|---|---|
| `app/ml_job_runner.py` | 수정 (B-2 가드 순서 + 조건) | 21 | 4 |
| `tests/test_ml_job_runner.py` | 수정 (회귀 4건) | 83 | 0 |
| `docs/ai_result/POC3/(본 문서)` | **신규** | — | — |

**DB 데이터는 코드 변경이 아니라 실행 산출물**이다(§3).

> 본 문서가 이 커밋에 포함되므로 **자기 참조 방지를 위해 수치를 적지 않는다.**
> 커밋 후 `git show --stat <sha>` 로 확인한다.

---

## 3) 실행 결과 (live DB)

### 3.1 live DB 정본 확인

```
DEFAULT_DB_PATH.resolve() = /Users/hyungsookim/projects/krx_hyungsoo/state/market/market_data.sqlite
expected                  = 동일 → 일치 ✓
```

**실행 전 실측**: `etf_daily_price` 1,379,939행 · 최신 `2026-08-20` ·
KODEX200 3,033행 · `etf_master` 1,171 · feature **0** · market_risk **0**

### 3.2 체인 B — 참고점수 (화면 복구 우선)

```
etf universe tickers : 1171
training row pool    : 1,353,321
train done           : rows=1064287/266072 device=cpu gpu=False
                       train_loss=0.008812 test_loss=0.032231 sec=1.49
inference candidates : 1157 (asof=2026-08-20)
status=ok  scored_candidate_count=1157
```

**CPU fallback 총 소요 15.7초** (학습 1.49초). GPU 미사용.

**채점 제외 13종목** = 1,170(universe − KODEX200) − 1,157. 전부 **20일 lookback 미충족**
(예: `0223A0` RISE 코스닥커버드콜액티브 — 가격 17거래일). **`0` 으로 위장하지 않고 제외**했다.

### 3.3 체인 A — feature backfill (연도 분할)

| 연도 | etf_rows | asofs | 초 | 연도 | etf_rows | asofs | 초 |
|---|---|---|---|---|---|---|---|
| 2014 | 19,747 | 178 | 1.91 | 2021 | 104,905 | 248 | 5.20 |
| 2015 | 32,964 | 248 | 2.51 | 2022 | 126,868 | 246 | 6.05 |
| 2016 | 43,207 | 246 | 2.88 | 2023 | 156,863 | 245 | 7.22 |
| 2017 | 56,600 | 243 | 3.44 | 2024 | 191,992 | 244 | 8.70 |
| 2018 | 71,458 | 244 | 4.01 | 2025 | 231,027 | 242 | 10.53 |
| 2019 | 82,513 | 246 | 4.41 | 2026 | 170,519 | 155 | 8.06 |
| 2020 | 89,826 | 248 | 4.67 | | | | |

**총 약 70초.** 모든 CLI 에 `--db "$DB"` 명시.

> **PLAN §3.5 추정 정정**: *"전 구간 ~350만 행 · 한 번에 돌리면 부담이 크다"* 는 **과대 추정**이었다.
> 실제 **1,376,524행 · 70초**. `build_features` 가 ticker 시계열을 1회 prefetch 하고 asof 루프를
> 도는 구조라 asof 수에 선형이다. 연도 분할은 **중단·재개 안전성** 때문에 유지했다(D-1).

### 3.4 ⚠ 실행 중 발견한 **개발자 실행 실수** 1건

**증상**: 1차 sanity 가 `error` — `all-null risk proxy asof=2014-04-09`.

**원인**: `--start-date 2014-01-01` 로 실행해 **KODEX200 첫 거래일(2014-04-09)부터** 생성했다.
확정 D-1 은 *"feature lookback 을 충족하는 최초일 이후"* 인데 **이를 어겼다.**
첫 거래일은 20일 lookback 이 구조적으로 불가능해 risk proxy 7개가 전부 `NULL` 인 행이 생겼다.

```
2014-04-09: (None, None, None, None, None, None, None)   ← 정보량 0
2014-05-12: (-2.40, -2.40, 1.18, None, None, 0.0, -0.2)  ← 21번째 거래일, lookback 충족
```

**조치**: `2014-05-12` 미만 구간 제거 — **파생 테이블이며 계약 위반으로 생성된 행**이다.

```
etf_ml_feature_daily     : 1,378,489 → 1,376,524  (삭제 1,965)
market_risk_feature_daily:     3,033 →     3,013  (삭제 20)
새 최초 asof: 2014-05-12 (양쪽 동일)
```

**가격 원천 데이터는 손대지 않았다.** warm-up NULL 도 그대로 남는다(§4.3).

### 3.5 sanity

```
이전:  sanity_status=error  errors=1  asof_range=2014-04-10→2026-08-20
이후:  sanity_status=warn   errors=0  asof_range=2014-05-12→2026-08-20
       etf_rows=1376524  market_rows=3013  trading_days=3013
       calc warn=0 err=0 · risk all_null_asof=0 · total warnings=4 errors=0
```

**남은 warning 4건은 전부 데이터 특성**이며 결함이 아니다.

| warning | 성격 |
|---|---|
| **1,053** ticker 의 row 수가 `trading_days×0.95` 미만 | 대부분 ETF 가 2014년 이후 상장 |
| asof별 ticker count 급감 **817건** | 초기 연도엔 ETF 자체가 적었음 |
| `down_day_volume_ratio` null **0.984401** | **하락일에만 계산되는 값** |
| `large_negative_day_proxy` null **0.984401** | 〃 |

> **A-2 정정 (검증자 r1)**: 최초 결과서는 `1,056 · 836 · 98.45%` 로 적었다. 그것은
> **삭제(§3.4) 이전 1차 sanity 값**이고, 최종 `state/ml/ml_feature_sanity_latest.json` 의
> 값은 위 표와 같다. **삭제 후 재실행 결과로 다시 재지 않고 옛 수치를 남긴 것이 오류다.**

`nav_unavailable_ratio 0.9627` 도 NAV 수집이 `2026-06-17` 부터라 과거 구간에 없는 것이 맞다.

### 3.6 baseline v0

```
status=ok  feature_asof=2014-05-12→2026-08-20  trading_days=3013  evaluated_days=2993
candidate.status=ok  days=2993  tickers=1158  top_quantile=0.2
risk.status=ok       days=2993
leakage.future_data_detected=False  tail_excluded=True  time_order=True
warnings=0  errors=0
```

**미래 데이터 누수 없음**이 확인됐다.

### 3.7 evidence-refresh job — M-5 계약 준수

```
POST /ml/jobs/evidence-refresh → accepted
job_id ml-evidence-refresh-20260824233025-64659 · requested_by=ui

status: success · error: None
  [feature_generation] success
  [sanity_check]       success
  [baseline_lookback]  success
```

**상태 파일을 편집·삭제하지 않았다.** 이전 `failed`(테스트 잔여물)는 **성공 실행 결과로
자연 갱신**됐다 — 설계 확정 M-5 그대로다.

**job 실행 후에도 행 수 불변**(멱등 재확인): etf 1,376,524 · market 3,013.

---

## 4) 검증 실측

### 4.1 DB — 행 수 · 유일성 · 최신일

| 항목 | 결과 |
|---|---|
| `etf_ml_feature_daily` | **1,376,524행** · asof 3,013 · **ticker 1,171** · `2014-05-12`~`2026-08-20` |
| `market_risk_feature_daily` | **3,013행** · `2014-05-12`~`2026-08-20` |
| PK 중복 | etf **0** · market **0** |
| **최신일 계약** | `market_risk max(asof)` `2026-08-20` **=** KODEX200 최종 거래일 `2026-08-20` |
| **universe** | **1,171** — 설계자 확정과 일치 |
| **개별주 3종목** | `000660`·`005930`·`006400` 전부 **0행** (자동 제외) |

### 4.2 멱등성 — **전 구간 · `created_at` 제외 전 컬럼** (r2 재검증)

> **r1 지적 수용**: 초판은 **최신일 50행 표본 해시**만 비교했다. 전 구간 값 동일의 증거가
> 아니었고, `ml_feature_store.py:207,326` 이 `created_at=excluded.created_at` 이라
> 재실행 때 그 컬럼은 실제로 바뀐다.

**재검증 방법**: 두 테이블 **전 행**을 PK 순으로 정렬해 **`created_at` 을 제외한 전 컬럼**을
SHA-256 으로 접는다. 그 뒤 **PLAN 정정 명령**(`--start-date 2014-05-12`)으로 2014 구간을
재실행하고 다시 접어 비교한다.

```
재실행 전  (sha256 전체 64자)
  etf_ml_feature_daily       rows=1,376,524
    sha256=da69c6ecdf18dd03a86c8484391786285815194f1a30c1ad54138b2f4c02bddf
  market_risk_feature_daily  rows=    3,013
    sha256=41bd8853df56076d37a208f4d9c4dd6db34e322322ba137cb06d3680c5a3abba

재실행:  --start-date 2014-05-12 --end-date 2014-12-31
         [END] etf_rows=17782  market_rows=158  asofs=158  elapsed=1.91s

재실행 후  (동일)
  etf_ml_feature_daily       rows=1,376,524
    sha256=da69c6ecdf18dd03a86c8484391786285815194f1a30c1ad54138b2f4c02bddf
  market_risk_feature_daily  rows=    3,013
    sha256=41bd8853df56076d37a208f4d9c4dd6db34e322322ba137cb06d3680c5a3abba

diff → 차이 없음
```

> **표기 정정 (검증자 r2)**: 초판은 해시를 **앞 32자로 축약**해 적어 SHA-256 인지
> 불분명했다. 위는 **전체 64자**다.

**행 수 불변 · 전 컬럼 값 불변**(`created_at` 제외). 정정된 명령이 §3.4 에서 삭제한
`2014-05-12` 미만 구간을 **되살리지도 않았다**(min asof `2014-05-12` 유지).

### 4.3 warm-up / 성숙 구간 — 양쪽 검증

| 구간 | 결과 |
|---|---|
| **warm-up (NULL 존재해야 함)** | `return_20d IS NULL` **20,190행**(삭제 후) — **`0` 위장 없음** |
| **성숙 (non-null)** | 최신일 `2026-08-20` 기준 `return_20d` non-null **1,148 / 1,161** |

`069500` 전이 실측:

```
초기 2014-05-12 이후 각 ETF 는 자기 상장 직후 warm-up NULL 구간을 가진다
최신 2026-08-20  close 108,190  return_5d 4.7845  return_20d 0.0860  drawdown_20d -4.2583
```

**feature 행 생성 시점과 20일 feature 완성 시점이 구분된다.**

### 4.4 API payload

```
GET /market/topn/latest?n=10&basis=one_month&order=desc
relative_upside_score_status : ok
relative_upside_score_asof_date : 2026-08-20

ticker     score  drawdown_20d  reasons
473640      71.5        0.0     3건 ['최근 5·10·20일 KODEX200 대비 성과가 우위입니다.']
0148J0      12.1       -0.0775  3건
364970       7.2       -0.027   3건
...
비-null: score 9/10 · drawdown_20d 9/10 · reasons≥1 9/10
```

**null 1건** = `0223A0`(가격 17거래일, lookback 미충족) — `score`/`drawdown_20d` `null` ·
`reasons` `[]`. **PLAN §6.3 대로 빈 배열은 정상 계약**이므로 결함이 아니다.

### 4.5 readiness — 7축 전부 `available`

```
etf rows 1,376,524 · latest 2026-08-20   |   market rows 3,013 · latest 2026-08-20
[available] ETF 가격 시계열 / NAV·괴리율 / 거래량·유동성 / 시장지수
[available] ETF universe 시장 폭 / 변동성 / 조정장 전조
```

### 4.6 코드 검증

| 항목 | 결과 |
|---|---|
| `black --check app tests` | `246 files would be left unchanged.` |
| `flake8 app tests` | **0건** |
| `tests/test_ml_job_runner.py` | **25 passed** (기존 21 + 신규 4) |
| **백엔드 전체 pytest** | **1,161 passed** — **환경변수 없이**(`.env` 기본, PUSH_AUTOSEND 4개 전부 `false`) |
| 프론트 `tsc`/`eslint`/`vitest` | **미실행** — 프론트 코드 변경 0건(설계자 §16 에서 필수 제외) |

---

## 5) 신규 추가된 의존성

없음.

---

## 6) 지시문 외 변경

없음. §3.4 의 행 삭제는 **확정 계약 D-1 을 맞추기 위한 정렬**이며 파생 테이블 대상이다.

---

## 7) 알려진 한계 / 미완성

### 7.1 UI 확인 2건 미완 (완료조건 8·9)

사용자 실화면 확인이 필요하다 — `요즘 잘 오르는 ETF` 의 참고점수·사유·고점 대비 표시,
`ETF 비교하기` 의 **고점대비 정렬 실동작**.

### 7.2 일별 증분은 수동 실행 (D-3)

자동 스케줄러를 추가하지 않았다. 갱신하려면 사용자가
`POST /ml/jobs/evidence-refresh`(화면 `ML 근거 갱신`) 를 실행한다.

### 7.3 개별주 3종목 미갱신 — **범위 밖 관찰사항**

`000660`·`005930`·`006400` 은 `2026-08-12` 이후 가격이 갱신되지 않는다.
시장 갱신 대상이 `list_etf_tickers()`(=`etf_master`) 라 개별주가 빠지기 때문이다
(`market_refresh_service.py:297`).

**설계 확정대로 이번 Step 에서 다루지 않으며 별도 기능으로 확대하지 않는다.**
보유 평가는 별도 시세 경로를 쓰므로 영향이 없다.

### 7.4 sanity `warn` 4건 유지

§3.5 표 참조. 전부 데이터 특성이며 결함이 아니다. `warn` 상태에서도 job 은 성공한다.

---

## 8) 다음 검증자에게 알릴 점

- **§3.4 가 이번 작업의 핵심 판단 지점**이다. 개발자가 D-1 을 어겨 만든 행을 삭제했다.
  파생 테이블 대상이고 가격 원천은 무변경이나, **DB 행 삭제**라는 점을 명시한다.
- **B-1 철회**(PLAN §2.4) — 상태 경로 5개가 이미 격리돼 있어 코드를 바꾸지 않았다.
  "오염 정황" 만으로 수정하지 말라는 설계자 지시가 정확했다.
- **B-2 역검증** — 기준점 커밋으로 되돌리면 신규 4건 중 3건이 실패한다.
- ML 을 **실제로 실행**했다(설계자 승인 범위). 외부 데이터 조회는 0건 — 전부 기존 SQLite 연산.

---

## 9) 사용자 확인이 필요한 항목

| # | 항목 | 상태 |
|---|---|---|
| 1 | §3.4 **행 삭제 1,985건**(etf 1,965 + market 20) | **승인 완료 (2026-08-25)** — 원문 §10.5 |
| 2 | **완료조건 8·9 실화면 확인**(§7.1) | **대기** — 사파리는 강력 새로고침(⌘⇧R) 필요할 수 있다 |

**남은 것은 2번 하나다.**


---

## 10) 검증자 r1 `REJECTED` — 지적 4건과 조치 (2026-08-25)

ML 데이터·API·UI 복구 자체는 r1 에서 확인됐다. 차단 사유는 **회귀 실패 · 재실행 계약
불일치 · 결과서 수치 오류** 였고 **4건 모두 타당**했다.

### 10.1 [A-2] 전체 pytest 3건 실패 — 보고 전제 누락

**재현**: `.venv/bin/python -m pytest tests/ -q` → **3 failed, 1158 passed**.

```
FAILED test_low_frequency_push_operation.py::test_runner_spike_mixed_signals_body_excludes_already_sent
FAILED test_runtime_runner_partial_delivery.py::test_runner_partial_delivery_records_flag_and_no_registry_write
FAILED test_runtime_runner_partial_delivery.py::test_runner_first_chunk_fail_partial_false_and_no_registry_write
```

**원인**: `.env` 의 `PUSH_AUTOSEND_*` 4개가 **전부 `false`**(맥 안전 설정)인데 세 테스트가
그 값에 의존했다. 실패 로그 `reason=autosend_disabled`.
**개발자는 항상 4개 플래그를 `=true` 로 export 하고 돌려 "1,161 passed" 라고 보고했다** —
**전제를 적지 않은 것이 보고 오류**다. 세 파일은 기준점 `c95be6f0` 대비 **변경 0건**이라
ML 코드가 유발한 실패는 아니다.

**조치 — fixture 두 종류를 보완**(검증 약화 없음).

| 파일 | 문제 | 조치 |
|---|---|---|
| `test_runtime_runner_partial_delivery.py` | 같은 파일 3번째 테스트만 `monkeypatch.setenv` 를 갖고 있고 **앞의 2개는 `.env` 의존** | 통과 케이스와 동일 패턴으로 2건에 `setenv` 추가 |
| `test_low_frequency_push_operation.py` | **플래그 이름이 코드 계약과 어긋남** — 테스트는 `PUSH_SPIKE_OR_FALLING_ALERT_ENABLED` / `PUSH_HOLDINGS_BRIEFING_ENABLED`, 코드는 `app/three_push_runner_common.PUSH_KIND_FLAG_ENVS` 의 **`PUSH_AUTOSEND_<KIND>_ENABLED`** 를 읽는다 | 이름을 코드 계약에 맞춤 |

> 두 번째가 더 나쁘다 — **설정하는 시늉만 하고 실제로는 `.env` 값을 따르고 있었다.**

**결과**: **환경변수 없이 1,161 passed**(`.env` 기본 그대로).

### 10.2 [A-2] sanity 수치 오류

| 항목 | 결과서(초판) | 최종 JSON 실제 |
|---|---|---|
| 누락 ticker | 1,056 | **1,053** |
| 급감 asof | 836 | **817** |
| null 비율 | 98.45% | **0.984401** |

**원인**: **삭제(§3.4) 이전 1차 sanity 값**을 그대로 뒀다. 삭제 후 재실행 결과로 다시 재지
않았다. → §3.5 표 정정 완료.

### 10.3 [A-3 · B-5] PLAN 재실행 명령이 삭제 구간을 되살림 — **차단 사유**

PLAN §4.2 의 backfill 명령이 여전히 `--start-date 2014-04-09` 였다. **그대로 재실행하면
§3.4 에서 삭제한 계약 위반 구간(20 asof)이 다시 생성**된다.

**조치**: `--start-date 2014-05-12` 로 정정하고 **경고 주석**을 붙였다.

```
# ⚠ 시작일은 lookback 충족 최초일(D-1). KODEX200 첫 거래일(2014-04-09)이 아니다.
#   첫 거래일부터 돌리면 20일 lookback 불가로 risk proxy 전부 NULL 인 행이 생겨
#   sanity 가 error 가 된다 (2026-08-24 실행에서 실제 발생 · 결과서 §3.4).
python scripts/generate_ml_features.py --db "$DB" --start-date 2014-05-12 --end-date 2014-12-31
```

**정정 명령으로 실제 재실행해 검증**했다 — min asof `2014-05-12` 유지, 되살아난 행 0건(§4.2).

### 10.4 [B-6] 멱등성 "값 동일" 이 전체 행 근거가 아님

**지적대로였다.** 초판은 최신일 50행 표본 해시만 비교했고, `created_at=excluded.created_at`
이라 재실행 시 그 컬럼은 바뀐다.

**조치**: **전 구간 · `created_at` 제외 전 컬럼** 해시로 재검증(§4.2). 재실행 전후 **완전 동일**.

### 10.5 사용자 승인 · 남은 확인 사항

| # | 항목 | 상태 |
|---|---|---|
| 1 | **파생 DB 1,985행 삭제**(§3.4) | **승인 완료 (2026-08-25)** |
| 2 | 완료조건 8·9 UI 표시·정렬 | **사용자 최종 확인 대기** (검증자 기술 확인은 통과) |

**1번 승인 경위 (원문)**

개발자가 삭제 내역·이유·성격을 제시하고 승인을 요청했다.

> **개발자**: 삭제한 것 — `etf_ml_feature_daily` 1,965행 + `market_risk_feature_daily`
> 20행(`2014-05-12` 미만). 이유 — `--start-date 2014-01-01` 로 돌려 확정 계약 D-1
> (*"lookback 충족 최초일 이후"*)을 어겼고, 첫 거래일은 20일 lookback 이 불가능해
> risk proxy 가 전부 NULL 인 행이 생겨 sanity 가 `error` 였다. 성격 — 파생 테이블이고
> **가격 원천은 무변경**이며, 멱등이라 재실행으로 언제든 복원된다.
> **승인해주시면 커밋하고 재검증 요청하겠습니다.**

> **사용자**: **"네 승인하겠습니다."**

> **A-2 정정 (검증자 r2)**: 커밋 `98e09434` 메시지에는 *"사용자 승인을 받았다"* 로 적고
> 본 절은 *"승인 미확인"* 인 채로 남겨 **두 기록이 모순**됐다. 승인은 실제로 받았고,
> **결과서를 갱신하지 않은 것이 오류**다. 위 표·원문으로 일치시킨다.

### 10.6 r2 검증 실측

| 항목 | 결과 |
|---|---|
| `black --check app tests` | `246 files would be left unchanged.` |
| `flake8 app tests` | **0건** |
| **전체 pytest (환경변수 없이)** | **1,161 passed** |
| `test_runtime_runner_partial_delivery.py` | 3 passed |
| `test_low_frequency_push_operation.py` | 42 passed |
| 멱등성 (전 구간 · `created_at` 제외) | **재실행 전후 해시 동일** |
| DB 상태 | etf **1,376,524** · market **3,013** · min asof `2014-05-12` **유지** |
