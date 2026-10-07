# POC5-02 — 가격 결과 성숙 개발 PLAN V1

```text
STEP_ID        = POC5-02
DESIGN         = docs/ai_design/POC5/POC5-02_PRICE_OUTCOME_MATURITY_DESIGN_V1.md (설계자 2026-10-07)
UPPER          = docs/ai_plan/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_PLAN_V1.md §2-6 · §2-7 (Q1 ~ Q30 확정 · 다시 묻지 않음)
BASE_COMMIT    = 9cbbd419 (POC5-01B 커밋 · 코드 기준)
STATUS         = PLAN 확정 — 설계자 PASS_TO_IMPLEMENT(2026-10-07 · 재제출 불필요 · Q-A · Q-B · Q-D 승인 · Q-C 정정 승인 · 원문 = 설계서 끝 · §8)
조사            = 설계서 §9 7항목 — 코드 읽기 전용 3묶음(01B item → 가격 계열 · 가격 표 · 배치 연결 지점) + 개발자 직접 확인
설계자 질문      = 4건(§6 · 코드와 설계가 실제로 맞지 않는 것만)
```

## 0. 요약

설계서대로 만들 수 있다. 새 모듈 2개가 08:10 · 09:20 배치 끝에서 원장의 `PRIMARY_LIVE` 평가 가능 item 을 읽어 `price_outcome` 에 한 번씩 INSERT 한다. 외부 조회 · cron · 의존성 · FDR 은 0 이다. 기존 배치 status · 상태 JSON · stdout · exit code 는 바꾸지 않는다.

코드와 설계가 맞지 않는 곳이 4곳 있어 추천안과 함께 묻는다(§6).
1. 01B item 에 ETF/개별주 구분이 없다(Q-A).
2. 01B 시장 item 에 KOSPI 항목이 없다(Q-B).
3. 빈 날 채우기 창 때문에 '저장된 날짜 축' 으로 세면 결과가 계산 시각에 따라 달라진다(Q-C).
4. legacy 진단의 범위가 코드로 정해지지 않는다(Q-D).

## 1. 사실조사 (설계서 §9)

### 1-1. 01B item → 가격 계열 (§9-1)

| subject | 저장 값(01B) | 가격 계열 · series_id | t0 |
|---|---|---|---|
| `ticker`(보유 브리핑 `axis=briefing` · 장중 `axis=risk`) | values: 20일 수익률 · 매입대비 % 등 · **자산 유형 없음** | ETF → `krx_etf:<ticker>` · 개별주 → `krx_stock:<ticker>`(Q-A) | 01B `t0_price` · `t0_price_asof`(Naver 현재가 · `localTradedAt`) |
| `sector`(subject = 사업군 키) | values: `ticker`(실제 판정에 쓴 대표 또는 대체) · `used_alternate` | `krx_etf:<values.ticker>` — 대표 · 대체 모두 ETF 표에서만 읽는다(sector_signal.py:197-222) | 01B `t0_price`(병합 시세) |
| `market`(subject = `SP500`) | values: S&P500 수익률 · asof 등 · t0 NULL · **KOSPI 항목 없음** | `benchmark:KOSPI`(Q-B) | 성숙 단계가 계산(Q-B) |
| `index_group`(subject = 운용사\|기초지수) | values: `tickers`(수익률에 쓴 ticker · 2개 이상) · `price_asof`(최신 종가일) · t0 NULL | ticker 마다 `krx_etf:<ticker>`(평균 없음 · 설계 §4) | 그 ticker 의 `values.price_asof` 종가(메시지가 쓴 확정 종가) |
| `index_block` · `sector_block` | ticker 없음 | 대상 아님(행 0) — `index_block` 은 정상 후보 0 인 날 `evaluable=1` 이지만 가격 대상이 없다 | — |

- 사건 시각 구분: `evaluation_run.schedule_expected`(off_schedule=0 이면 예정 HH:MM 과 정확히 같다). 08:30 시장 · 09:15 · 12:30 보유 · 09:30 ~ 15:20 장중 = '15:30 이전' · 15:40 보유 CLOSE = '15:30 이후'.

### 1-2. 가격 표 · 날짜 축 · 수집 시각 · 보유 판별 (§9-2 · §9-6)

| 표 | 키 · 날짜 | 수집 시각 | 저장 범위 | 빈 날 채우기 |
|---|---|---|---|---|
| `krx_etf_daily_price_unadjusted` | PK(date, ticker) · `YYYY-MM-DD` | `collected_at`(UTC · upsert 때 갱신) | 전 ETF(매도 뒤에도 쌓임) | T-1 로 끝나는 21거래일 창 |
| `krx_stock_daily_price_unadjusted` | 같은 6열 | `collected_at` | **현재 보유 코스피 개별주만**(코스닥 0 · 매도 다음 적재일부터 중단) | 31거래일 창(날짜 단위) |
| `market_benchmark_daily_price` | PK(benchmark_id, date) · `benchmark_id='KOSPI'` | `created_at`(UTC · 행 기록 시각) | KOSPI 공식 종가(OPS-03 부터 `KRX_OPEN_API/idx_kospi_dd_trd`) | 없음(저장 최신일부터 T-1 까지만) |

- 세 표 모두 `state/market/market_data.sqlite`. 읽기 전용(`mode=ro`) helper 는 ETF · 개별주 종가 읽기(`read_holdings_etf_prices` · `read_holdings_stock_prices`)뿐이고, 날짜 목록 · KOSPI 읽기는 쓰기 연결(CREATE + commit)이다 → 새 모듈에 `mode=ro` 읽기 함수를 둔다.
- 거래일 helper(`trading_day_lag`)는 뒤로 걷는 함수만 있다. 앞으로 n 거래일은 새로 만든다(같은 캘린더 규칙).
- 보유 판별: `state/holdings/holdings_latest.json`(현재 목록만 · 매도일 · 이력 없음 · `app/holdings.py`). 01B item 에는 사건 시점 `held` 만 있다.
- 자산 유형 판별: `holdings_price_basis.classify_assets` — ETF 마스터 CSV 또는 ETF 표 적재 기록이면 ETF, 둘 다 읽었는데 없으면 STOCK, 하나라도 못 읽으면 UNKNOWN(외부 조회 0).

### 1-3. 배치 연결 지점 (§9-3)

- `scripts/run_oci_market_data_batch.py :: main()`(568-576)에서 결과 JSON 을 출력한 **뒤**, `sys.exit` 바로 **앞** 한 곳. 이 시점에 08:10(`run` → `_finish` → 상태 JSON 저장)과 09:20(`run_krx_only` → 보강 상태 저장)의 기존 기록 · 로그가 모두 끝났고, exit code 는 result status 로 이미 정해져 있다.
- 기존 테스트가 직접 부르는 `run()` · `run_krx_only()` 안에는 넣지 않는다(그 경로 불변).
- dry-run 은 건너뛴다. 09:20 이 `skipped_already_ran_today` 여도 돈다(idempotent).
- **배치 프로세스는 `.env` 를 환경변수로 올리지 않는다**(`load_dotenv_file` 호출 0 · 개발자 grep 확인). 그래서 `env_bool(DECISION_LEDGER_ENABLED)` 를 그대로 쓰면 OCI 에서도 늘 꺼진다(§2-1 게이트).
- 08:10 배치는 KRX 단계가 08:27 까지 기다릴 수 있어 성숙 쓰기가 08:30 시장 러너와 가까워질 수 있다 → 쓰기는 짧은 트랜잭션 1회(§2-3).

### 1-4. 평가 날짜 fixture (§9-4)

| 사건 | 예 | +1 | +5 | +20 |
|---|---|---|---|---|
| 08:30 시장(KOSPI) · 기초지수 ticker | 10-08(목) 08:30 | 10-08 종가 | 그 날부터 5번째 거래일 | 20번째 |
| 09:15 보유 · 장중 틱(15:30 이전) | 10-08 09:15 | 10-08 종가 | 〃 | 〃 |
| 15:40 보유 CLOSE(15:30 이후) | 10-08 15:40 | 다음 거래일(10-12 · 10-09 한글날 휴장) 종가 | 10-12 부터 5번째 | 20번째 |

테스트는 임시 캘린더(휴장 1일 포함) · 임시 가격 DB 로 위 세 경우를 고정한다(AC 1).

### 1-5. 변경 파일 · KS-10 (§9-7 · 2026-10-07 `wc -l`)

| 파일 | 지금 | 변경 | 예상 |
|---|---|---|---|
| 새 `app/three_push_runtime/ledger_outcome.py` | — | 대상 선택 · 계열 결정 · 날짜 · 상태 · DDL · INSERT-once · 진입 함수 | ~350 |
| 새 `app/three_push_runtime/ledger_outcome_prices.py` | — | 가격 표 · 캘린더 · 보유 목록 읽기 전용 | ~150 |
| `scripts/run_oci_market_data_batch.py` | 580 | `main()` 에 격리 호출 1곳(약 8줄) | ~588 |
| `scripts/run_decision_ledger_reconcile.py` | 64 | legacy 진단 출력(Q-D 판정에 따라) | ~100 |
| 새 테스트 `tests/test_poc5_02_price_outcome.py` | — | AC 1 ~ 9 | ≤ 900 |

- 01B `ledger_store.py` 의 DDL · `connect` · '4테이블' 테스트는 바꾸지 않는다(§2-2).
- 저장소 KS-10: 트리거 0 · 근접 6(백엔드 `api.py` 642 · `reverse_verify_guards.py` 638 · `ml_score_validity_report.py` 626 · `holdings_market_evidence.py` 616 · `sector_signal.py` 611 · `draft.py` 602). 이번 후보 중 600 이상이 되는 파일은 없다(배치 스크립트 ~588).

## 2. 구현 계획 (판정 뒤)

### 2-1. 실행 게이트 · 격리

- `main()` 의 결과 출력 뒤 · `sys.exit` 앞에서 `ledger_outcome.run_maturity(logger)` 를 `try / except Exception` 으로 1회 부른다. 예외는 배치 logger 에 종류만 남기고 삼킨다. result dict · 상태 JSON · stdout 은 건드리지 않는다.
- 게이트 두 개(둘 다 통과해야 연결):
  1. 원장 플래그 — 환경변수가 있으면 그것, 없으면 `.env` 에서 `DECISION_LEDGER_ENABLED` 한 키만 직접 읽는다(`krx_sync.read_api_key` 와 같은 방식 · 배치 전체에 `.env` 를 올리지 않는다 · 다른 키 값은 읽지 않음).
  2. 원장 파일이 이미 있음 — 없으면 연결하지 않는다. 원장 파일 · 폴더는 러너만 만든다(PC · 플래그 없는 OCI 에서 파일 · mkdir · chmod 0).
- 로그: 기존 배치 logger 에 `price outcome maturity:` 한두 줄(대상 · INSERT · 상태별 건수 · 실패 시 예외 종류). 새 로그 파일 · 상태 JSON 0.

### 2-2. `price_outcome` 테이블 · INSERT-once

```text
price_outcome  PK (event_id, item_seq, series_id, horizon)
               series_id(`krx_etf:<ticker>` · `krx_stock:<ticker>` · `benchmark:KOSPI`) · horizon(1 · 5 · 20)
               t0_price · t0_price_asof · signal_date_close · previous_close · eval_date · eval_price
               return_raw · max_up_raw · max_down_raw · path_points · price_basis · status
               computed_at · source_collected_at
               INDEX (status)
```

- 새 모듈이 **이미 있는 원장**에 연결한 뒤 자기 `CREATE TABLE IF NOT EXISTS price_outcome` 를 실행한다. 01B 러너는 이 테이블을 모른다.
- 연결은 `ledger_store.connect`(권한 0700/0600 확인 · WAL · busy_timeout 5000)를 재사용한다 — 게이트 2 가 파일 존재를 먼저 확인하므로 새로 만들지 않는다.
- meta: `schema_version.price_outcome = price_outcome.v1` 을 INSERT OR IGNORE(01B `schema_version` 값은 그대로).
- 쓰기: 원장 · 가격 읽기와 계산은 쓰기 트랜잭션 밖에서 끝내고, `BEGIN IMMEDIATE` 1회에 `INSERT OR IGNORE` 묶음만 넣는다. UPDATE · DELETE 경로 0.
- `path_points` 는 설계 최소 컬럼 밖의 추가 1개다 — 최대 상승 · 하락을 계산한 종가 개수(경로 일부가 빠졌는지 보이게).

### 2-3. 대상 선택 · 계열 · 상태

- 대상 = `run_state=FINALIZED` ∧ `cohort=PRIMARY_LIVE` ∧ `off_schedule=0` 인 run 의 `evaluable=1` item 중 subject `ticker` · `sector` · `market` · `index_group`. 세 horizon 이 모두 있는 (item, series) 는 건너뛴다.
- 계열: §1-1 표(Q-A · Q-B 판정 반영). 한 번 정한 series_id 는 그 item 의 모든 horizon 에 같다.
- 상태와 기록 시점:

| 상태 | 조건 | 기록 |
|---|---|---|
| `UNSUPPORTED_PRICE_SOURCE` | 지원 계열이 없음(Q-A) | 3 horizon 즉시 |
| `T0_MISSING` | t0 를 정할 수 없음(현재가 없음 · KOSPI/기초지수 기준 종가 없음) — 다른 가격으로 대체하지 않음 | 3 horizon 즉시 |
| `MATURED` | +1 부터 그 horizon 까지 **예상 종가가 모두** 저장됨(평가일 하나만으로는 안 됨 · 설계자 Q-C 정정) | 그 horizon |
| `UNTRACKED_AFTER_EXIT` | 개별주 · 사건 때 `held=1` · 지금 `holdings_latest.json` 에 없음 · 그 종목 개별주 표 마지막 날 < 평가일 · ETF 표(공통 축)는 평가일을 지남 | 그 horizon |
| `PRICE_MISSING` | 경로(+1 ~ horizon)에 빠진 종가가 있고, 빠진 날이 모두 그 계열의 backfill 기간(ETF 21 · 개별주 31 거래일 창)을 지났음 — KOSPI 는 채우기가 없어 그 뒤 날짜가 저장되면 확정 | 그 horizon |
| (PENDING) | 위에 해당 없음 — 빠진 날이 아직 backfill 기간 안이거나 아직 적재될 차례가 아님 · 행 없음 | — |

- 날짜: +n 은 **기존 운영 거래일 캘린더만**으로 정한다(연도 CSV · 없으면 평일 fallback · 가격표 행 유무로 휴장을 추론하지 않음 · 적재 상태가 바뀌어도 평가일 불변 · 설계자 Q-C 정정).
- `return_raw = eval_price / t0_price - 1` · `max_up_raw` · `max_down_raw` = t0 대비 +1 ~ 평가일 종가 경로의 최대 · 최소(원시 소수 · 반올림 0). 경로가 완전할 때(MATURED)만 계산한다 — `path_points` 는 진단용이고 불완전 경로로 최대 · 최소를 확정하지 않는다.
- `signal_date_close` = 사건일 종가 · `previous_close` = 사건일 직전 거래일 종가(없으면 NULL).
- `source_collected_at` = 평가일 행의 `collected_at`(ETF · 개별주) · KOSPI 는 `created_at`(행 기록 시각) · 없으면 NULL.
- `price_basis` = `KRX_ETF_UNADJUSTED` · `KRX_STOCK_UNADJUSTED` · `KRX_KOSPI_INDEX` + 자산 판별 원천(`etf_master_csv` · `krx_table`).

## 3. 문서

- PROGRAM_TRUTH: §7.1 decision evidence DB(OCI 5테이블) · C-4 배치 끝 성숙 단계 · §12 확인 방법 · 부록 A symbol · 머리 최종 반영.
- STATE_LATEST: POC5 블록 '다음' · 머리.
- 결과서 `docs/ai_result/POC5/POC5-02_PRICE_OUTCOME_MATURITY_RESULT.md`.

## 4. 검증 계획 (줄인 방식)

| AC | 테스트(임시 원장 · 임시 가격 DB · 임시 캘린더 · 임시 보유 파일) |
|---|---|
| 1 | §1-4 세 경우의 +1/+5/+20 날짜 |
| 2 | ETF · 개별주 · KOSPI 가 지정 표만 읽음 · FDR 표(`etf_daily_price`)를 열지 않음(읽기 기록 대역) |
| 3 | 같은 입력 두 번 → 행 · 값 같음 |
| 4 | 평가일 행 누락 = PENDING → Q-C 조건 뒤에만 PRICE_MISSING |
| 5 | 매도 뒤 개별주 = UNTRACKED_AFTER_EXIT · 보유 중 결측 = PRICE_MISSING 규칙 |
| 6 | t0 없음 = T0_MISSING · 대체 0 |
| 7 | sent · suppressed · cut · not_selected 포함 · evaluable=0 · LEGACY · off_schedule=1 제외 |
| 8 | 시장 = KOSPI 원시값만 · 방향 판정 컬럼 0 |
| 9 | `main()` 성숙 예외 주입 → stdout · 상태 JSON · exit code 같음 · 플래그 없음 · 원장 파일 없음이면 원장 파일 · 폴더 생성 0 |
| 10 | 마지막 전체 회귀 1회 · 라이브 해시 · KS-10 |

검토 + 파괴 시험은 구현 뒤 1회(코드 · 문서 묶음 · 백그라운드)만 한다.

## 5. 배포 · 롤백

- 게이트: POC5-01B 첫 거래일(2026-10-08) 운영 확인 뒤(설계 §10). 커밋 · push(승인) → OCI `git pull`(사용자). cron · `.env` 변경 0(01B 플래그를 그대로 쓴다).
- 첫 확인(개발자 · OCI 읽기 전용): pull 다음 거래일 08:10 · 09:20 배치 로그의 `price outcome maturity:` 줄 · `price_outcome` 행 수 · 상태별 건수 · 배치 status · exit code 가 이전과 같음.
- 롤백: 커밋 revert + pull. `price_outcome` 테이블은 남아도 읽는 곳이 없다. 01B 플래그를 끄면 성숙도 함께 멈춘다.

## 6. 설계자 질문 (코드 · 확정 계약과 실제로 맞지 않는 것만)

| # | 설계 · 확정 문장 | 코드 사실 | 추천안 |
|---|---|---|---|
| **Q-A** | §3 · §9-1 'item 으로 가격 계열을 유일하게 정함' · 'KRX 상장 보유주 = 개별주 표' | 01B ticker item 에 ETF/개별주 구분이 없다(ledger_items.py:134-141 · 239-243 · 판별 결과는 실행 기록 진단에만). 개별주 표는 **코스피 보유주만** 저장한다(코스닥 0 · krx_stock_store.py:10) | 성숙 때 기존 `classify_assets`(로컬 CSV · ETF 표만 · 외부 0)를 다시 적용해 계열을 정하고 판별 원천을 `price_basis` 에 남긴다. `UNKNOWN`(원천 하나를 못 읽음)은 행을 쓰지 않고 다음 실행에서 다시 본다. STOCK 인데 개별주 표에 그 종목 행이 한 번도 없으면(코스닥 등) `UNSUPPORTED_PRICE_SOURCE` |
| **Q-B** | §3 · §5 '시장 브리핑의 한국 시장 = KOSPI' · '08:30 사건은 당일 KOSPI 종가가 +1' · POC5-00 §2-6 'S&P500 상태와 한국 시장 원시 결과를 나란히' | 01B 시장 item 은 `market/SP500` 1행뿐이고 KOSPI 항목 · t0 가 없다(ledger_market.py:47-67) | SP500 item(`evaluable=1` = 전망 UP/DOWN/FLAT)을 `benchmark:KOSPI` 결과의 주인으로 고정한다. t0 = 사건일 이전 마지막 저장 KOSPI 종가(메시지 시점에 확정된 값) · `t0_price_asof` = 그 날짜. 01B 에 KOSPI item 을 더하는 안은 01B 계약 변경이라 비추천 |
| **Q-C** | §5 '실제 적재된 공통 날짜 축에서 n번째' · §6 '축이 다음 날짜까지 전진하면 PRICE_MISSING' · POC5-00 Q17 | ETF 표는 21거래일 · 개별주 표는 31거래일 창에서 빠진 날을 **나중에 채운다**(krx_backfill · krx_stock_sync). 그래서 ① 저장된 날짜로 세면 같은 사건의 +5 · +20 날짜가 계산 시각에 따라 달라지고(INSERT-once 로 굳음) ② 축이 전진하자마자 PRICE_MISSING 을 쓰면 다음 날 채워질 행을 결측으로 굳힌다 | (a) **추천**: n번째는 한국 거래일 캘린더 축(운영 PUSH 와 같은 `trading_day_lag` 규칙 — 연도 CSV · 없으면 평일 fallback 에 ETF 표 저장일로 휴장 건너뛰기)으로 세고, `MATURED` 는 평가일 행이 저장됐을 때만 쓴다. `PRICE_MISSING` 은 평가일이 그 계열의 채우기 창 밖으로 밀려난 뒤에만 확정한다(KOSPI 는 채우기가 없어 그 뒤 날짜가 저장되면 바로). (b) Q17 문구대로 저장된 날짜로 세되, 평가일까지의 구간이 채우기 창 밖으로 나간 뒤에만 기록 — +1 결과가 약 21거래일 늦어져 비추천 |
| **Q-D** | §2 '과거 실행 건수 · 연결 상태를 보는 legacy 진단' · POC5-00 §2-7 '실행 연결 · 건수 진단만' | 원장의 `LEGACY_DIAGNOSTIC` run 과 원장 이전 runtime 실행(`runtime_execution_status`)이 모두 '과거 실행' 이 될 수 있어 범위가 코드로 정해지지 않는다 | 기존 읽기 전용 대조 CLI 에 `--legacy` 출력을 더한다: 원장 cohort 별 run 수 · runtime `run_id` 연결 수 · 원장 이전(first_active_at 전) runtime send 실행 수(kind 별). 가격 outcome 0 · JSONL · 외부 0 |

## 7. 사용자 확인 항목

1. 매도 판별은 '지금 보유 목록에 없음' 으로만 한다(보유 이력 저장 없음). 재매수 · 보유 중 거래정지는 `UNTRACKED_AFTER_EXIT` · `PRICE_MISSING` 과 정확히 구분하지 못한다 — 알려진 한계로 둔다.
2. 이 PLAN 은 아직 커밋하지 않았다. POC5-01B 종료 커밋과 함께 올리거나 따로 올리는 것은 01B 첫 거래일 확인 뒤 정한다.

## 8. 설계자 판정 반영 (2026-10-07 · PASS_TO_IMPLEMENT · 원문 = 설계서 끝)

| 항목 | 판정 | 반영 |
|---|---|---|
| Q-A | 승인 | `classify_assets` 재사용 · `UNKNOWN` 은 행 없이 재시도 · 개별주 표가 지원하지 않는 종목(코스닥 등)은 `UNSUPPORTED_PRICE_SOURCE` |
| Q-B | 승인 | `market/SP500` item 이 KOSPI 결과의 연결 주체(subject 는 그대로) |
| Q-C | 정정 승인 | ① 날짜는 기존 운영 거래일 캘린더만 · 가격표 행으로 휴장 추론 금지 · 평가일 불변 · 연도 파일 없으면 평일 fallback ② `MATURED` = +1 ~ horizon 예상 종가 전부 저장 · 빠졌으면 backfill 기간 안 = PENDING · 지나면 `PRICE_MISSING` ③ `path_points` 진단용(불완전 경로로 최대 · 최소 확정 금지) — §2-3 |
| Q-D | 승인 | 대조 CLI 선택 `--legacy` 출력 · 기본 출력 불변 |
| 추가 | 승인 | `path_points` 컬럼 · 배치에서 `.env` 의 `DECISION_LEDGER_ENABLED` 한 키만 직접 읽기 |
| 문구 | 정정 | §0 '새 모듈 하나' → '새 모듈 2개' |

