# POC5-02 개발 결과서 — PRICE_OUTCOME_MATURITY

작성 2026-10-07 · 갱신 2026-10-07(검증자 r1 VERIFIED · 사용자 결정 반영) · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex)

```text
STATUS                 = IMPLEMENTED_VERIFIED_DEPLOYED — 검증자 r1 VERIFIED(2026-10-07) · 설계자 RESULT `PASS_TO_DEPLOY_AFTER_GATE`(2026-10-07) · 커밋 `f0711340` · **OCI pull 2026-10-07 22:19:31(사용자 · POC5-03 `4e92d0c5` 와 함께 · 배포 게이트 = 01B 첫 거래일 확인 전 — 01B 는 2026-10-08 10:13 확인 통과 · 설계자 2026-10-08 '예외 기록 · 현재 배포 유지 사후 수용 · 롤백 · 재검증 · PRIMARY 시작일 변경 없음')** · 첫 실행 2026-10-08 08:10 `no_ledger`(원장 생성 전) · 09:20 `ok` 대상 32 · INSERT 0 · 대기 111(실측) · 첫 결과 행(MATURED +1) 확인 = 2026-10-12 08:10 이후(10-09 한글날 휴장 · 운영 캘린더 실측)
                         (배포 게이트 = POC5-01B 첫 거래일 2026-10-08 운영 확인 · 설계서 §10)
STEP_ID                = POC5-02 가격 결과 성숙
DESIGNER_RESULT        = PASS_TO_DEPLOY_AFTER_GATE(2026-10-07 · 보유 이력 요청 = 필요성 인정 · POC5-03 제외 · 별도 소형 설계 · 금액 · 수량은 holdings 에만) — 원문 = 설계서 끝
VERIFIER               = r1 VERIFIED(2026-10-07 · A-1 ~ A-4 통과 · B-1 ~ B-6 없음 · 문서 3곳은 검증자가 직접 정정 — 이 결과서 회귀 시간 0:06:17 → 0:06:22 · PROGRAM_TRUTH 함수명을 `Calendar` 메서드로 · STATE_LATEST 진행 상태)
DESIGN                 = docs/ai_design/POC5/POC5-02_PRICE_OUTCOME_MATURITY_DESIGN_V1.md (설계자 2026-10-07 · 끝에 PLAN 판정 원문)
PLAN                   = docs/ai_plan/POC5/POC5-02_PRICE_OUTCOME_MATURITY_PLAN_V1.md (설계자 PASS_TO_IMPLEMENT 2026-10-07 · Q-C 정정 2건 · §8)
PREDECESSOR/SUCCESSOR  = POC5-01B → POC5-03
BASE_COMMIT(코드 기준)  = 9cbbd419 (POC5-01B 커밋)
CODE_FILES             = 신규 2(ledger_outcome · ledger_outcome_prices) · 수정 3(ledger_store legacy_summary · 배치 main · 대조 CLI) · cron · 의존성 · 외부 조회 · FDR 0
TESTS                  = 새 테스트 1파일 31 passed · conftest 원장 격리에 .env 경로 1줄
REVIEW                 = 2관점 독립 검토 1회(계약 정확성 / 격리 · 안전) — 코드 결함 4 · 테스트 격리 1 · 테스트 공백 다수 모두 반영(§6-2)
SABOTAGE               = 검토 때 43종(27 + 16) 중 17종 탐지 → 반영 뒤 놓친 변이 대표 8종 재시험 8종 모두 탐지(§8-3)
KS-10                  = 트리거 0 · 배치 스크립트 580 → 596(근접선 600 아래) · 새 모듈 최대 501
BACKEND_FULL_REGRESSION= 2935 passed / 0 failed · exit 0 · 382.63s(2026-10-07 17:41 ~ 17:47 · 최종 코드) · PC state/logs 1,153파일 해시 전후 동일 · 회귀 시작 뒤 코드 변경 0
CONTRACT_DIFFERENCE    = 배치 status · 상태 JSON · stdout JSON · exit code · 08:30 PUSH 불변 · 01B ledger_store DDL · 4테이블 테스트 불변
```

## 0. 요약

08:10 · 09:20 배치 `main()` 이 기존 기록과 결과 JSON 출력을 끝낸 뒤 `ledger_outcome.run_maturity` 를 한 번 부른다(예외는 배치 logger 에 종류만 · 결과는 건수 한 줄). 게이트는 두 개다 — 원장 플래그(환경변수 · 없으면 `.env` 의 `DECISION_LEDGER_ENABLED` 한 키만 직접 읽음 · 배치 프로세스는 `.env` 를 올리지 않는다)와 원장 파일이 이미 있음(만들지 않음).

대상은 원장의 `FINALIZED` · `PRIMARY_LIVE` · `off_schedule=0` run 의 `evaluable=1` item 이다. 보유 · 장중 ticker(기존 `classify_assets` 로 ETF 표 / 코스피 개별주 표) · 사업군(실제 판정 ticker · ETF 표) · 시장 `SP500`(KOSPI 결과의 연결 주체) · 기초지수 그룹(ticker 마다)에 +1/+5/+20 거래일 원시 결과를 새 표 `price_outcome` 에 한 번씩 INSERT 한다.

날짜는 운영 거래일 캘린더만으로 정한다(설계자 Q-C 정정). `MATURED` 는 +1 부터 그 horizon 까지 예상 종가가 모두 저장됐을 때만이고, 빠진 날이 채우기 창(ETF 21 · 개별주 31 거래일) 안이면 행을 쓰지 않고 기다린다 · 지나면 `PRICE_MISSING`.

---

## 1. 처리한 요구사항

| # | 요구사항(설계서 · PLAN · 판정) | 결과 | 근거 |
|---|---|---|---|
| 1 | §2 원장에 `price_outcome` 1개 · 미래 테이블 0 | DONE | `ledger_outcome.DDL`(PK event_id · item_seq · series_id · horizon · 인덱스 status) · 01B DDL 불변 |
| 2 | §2 · §4 대상 = PRIMARY_LIVE · off_schedule=0 · evaluable=1 · 모든 disposition | DONE | `_load_targets` · `test_targets_include_all_dispositions_and_exclude_unevaluable_and_legacy` |
| 3 | §2 08:10 · 09:20 격리 실행 | DONE | 배치 `main()` 의 `_price_outcome_maturity`(출력 뒤 · dry-run 제외 · 09:20 skipped 날 포함) |
| 4 | §3 계열 · FDR 대체 0 | DONE | ETF 표 · 개별주 표 · KOSPI(`benchmark_id='KOSPI'`)만 · 테스트 대역 FDR 표 값(×10)이 섞이지 않음 |
| 5 | §4 기초지수 ticker 별 원시 결과 | DONE | `index_group` → ticker 마다 series · t0 = 메시지가 쓴 `price_asof` 종가 |
| 6 | §5 t0 · 대체 금지 | DONE | 보유 · 장중 = 01B t0 · KOSPI = 사건일 이전 마지막 저장 종가 · 없으면 `T0_MISSING` |
| 7 | §5 +n 날짜(15:30 기준 · 08:30 · 15:40) · Q-C 정정 ① 캘린더만 | DONE | `px.Calendar`(운영 `trading_day_lag` 규칙 · 가격표로 휴장 추론 0) · `test_horizon_dates_differ_for_pre_open_intraday_and_close` |
| 8 | §6 기록 컬럼 · 원시 소수 · `source_collected_at` | DONE | 평가일 행 `collected_at` · KOSPI `created_at` · `test_close_event_value_columns` |
| 9 | §6 상태 5종 · Q-C 정정 ② 경로 완전성 · 채우기 창 | DONE | `_horizon` · 창 경계 테스트(ETF 21 · 개별주 31) · KOSPI 결측 테스트 |
| 10 | §7 idempotent · 실패 격리 · 재시도 큐 · daemon · 상태 JSON 0 | DONE | INSERT OR IGNORE · 반복 실행 테스트 · 배치 main 실패 주입 · import 실패 테스트 |
| 11 | Q-A classify 재사용 · UNKNOWN 재시도 · 코스닥 UNSUPPORTED | DONE | `_series_of` · `test_unknown_class_retries_and_unlisted_stock_is_unsupported` · 표 정지 시에도 창 뒤 UNSUPPORTED |
| 12 | Q-B `market/SP500` → KOSPI | DONE | subject 그대로 · series `benchmark:KOSPI` |
| 13 | Q-D 대조 CLI `--legacy` | DONE | `ledger_store.legacy_summary`(읽기 전용) · 기본 출력 불변 테스트 |
| 14 | 추가 승인: `path_points` · `.env` 한 키 읽기 | DONE | 진단용(불완전 경로로 최대 · 최소를 확정하지 않음) · `flag_enabled` 가 다른 키를 올리지 않음 테스트 |
| 15 | §8 AC 10 · 마지막 전체 회귀 · 라이브 불변 · KS-10 | DONE | §8 |
| 16 | 문서(PROGRAM_TRUTH · STATE_LATEST) | DONE | §2 |
| 17 | OCI 배포 · 첫 확인 | 대기 | 01B 첫 거래일 확인 뒤(§10) |

## 2. 변경된 파일 목록

| 파일 | 변경 | 줄(HEAD → 지금) |
|---|---|---|
| `app/three_push_runtime/ledger_outcome.py` | 신규 — 게이트 · 대상 선택 · 계열 · 날짜 · 상태 · DDL · INSERT-once · 진입 | 501 |
| `app/three_push_runtime/ledger_outcome_prices.py` | 신규 — 시장 DB `mode=ro` 조회 · 운영 거래일 `Calendar` · 보유 · 자산 구분 | 250 |
| `app/three_push_runtime/ledger_store.py` | 수정 — `legacy_summary`(읽기 전용) | 495 → 547 |
| `scripts/run_oci_market_data_batch.py` | 수정 — `_price_outcome_maturity` · `main()` 2곳 호출 | 580 → 596 |
| `scripts/run_decision_ledger_reconcile.py` | 수정 — `--legacy` 선택 출력 | 64 → 82 |
| `tests/conftest.py` | 수정 — 원장 격리에 `ledger_outcome.ENV_PATH` → tmp 1줄 | 611 → 615 |
| `tests/test_poc5_02_price_outcome.py` | 신규 | 701 |
| `docs/ai_design/POC5/POC5-02_PRICE_OUTCOME_MATURITY_DESIGN_V1.md` | 신규 — 설계자 원문 · 끝에 PLAN 판정 원문 | 215 |
| `docs/ai_plan/POC5/POC5-02_PRICE_OUTCOME_MATURITY_PLAN_V1.md` | 신규 — PLAN · §8 판정 반영 | 182 |
| `docs/ai_result/POC5/POC5-02_PRICE_OUTCOME_MATURITY_RESULT.md` | 신규(이 문서) | |
| `docs/PROGRAM_TRUTH.md` | 수정 — POC5-02(머리 · §4 · §7.1 · C-4 · §12 · 부록 A) · POC5-01B 상태 문구(§4-1) | 969 → 974 |
| `docs/STATE_LATEST.md` | 수정 — 머리 · POC5-01B 배포 기록(§4-1) | 2807 → 2807 |
| `docs/ai_design/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_DESIGN_V1.md` | 수정 — 01B 설계자 RESULT 판정 원문(§4-1) | |
| `docs/ai_result/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_RESULT.md` | 수정 — 01B 설계자 RESULT · OCI 배포 기록(§4-1) | |

## 3. 신규 추가된 의존성

없음(표준 라이브러리 · 기존 모듈 `trading_day_lag` · `holdings_price_basis` · `krx_stock_sync` · `ledger_store` 만).

## 4. 지시문 외 변경

1. **POC5-01B 상태 기록이 같은 커밋 대상에 섞여 있다** — 01B 설계자 RESULT `PASS_TO_DEPLOY` 원문(01B 설계서 끝) · OCI pull(2026-10-07 15:56:59) · 개발자 확인 기록(01B 결과서) · PROGRAM_TRUTH · STATE_LATEST 의 01B '미배포' 문구 → '배포 · 첫 거래일 확인 전'. 지금 사실과 문서를 맞추려고 함께 고쳤다(01B 코드 변경 0). 01B 첫 거래일 확인(10-08) 뒤 종료 기록에서 다시 갱신한다.
2. **`price_outcome` 은 01B `ledger_store` DDL 에 넣지 않았다** — 성숙 모듈이 이미 있는 원장에 자기 `CREATE TABLE IF NOT EXISTS` 를 실행한다(PLAN §2-2 · 01B 4테이블 테스트 · 러너 불변). meta `schema_version.price_outcome = price_outcome.v1` 1회.
3. **보유 판별에 기존 `krx_stock_sync.holdings_tickers` 를 재사용** — 파일 없음 · 손상 = 모름(매도 판정 안 함) · 보유 0 = 빈 집합(검토 A-F1 반영).
4. **`px.Calendar`** — 운영 `trading_day_lag._trading_day_test` 를 실행당 한 번 만들어 쓴다(같은 규칙 · 성능 · 검토 A-F3).

## 5. 알려진 한계 / 미완성

1. **보유 이력(매수 · 매도 날짜)이 없다** — `holdings_latest.json` 은 지금 목록뿐이라(덮어쓰기) 매도 판정은 '사건 때 보유 · 지금 목록에 없음 · 그 종목 가격이 끊김' 으로 추정한다. 그래서 **재매수**(팔았다가 다시 산 경우)는 판 기간의 결측이 '매도 뒤 추적 중단' 이 아니라 `PRICE_MISSING` 으로 이름이 붙을 수 있다(가격 값 자체는 틀리게 저장되지 않음). 사용자가 보유 이력(매수 · 매도 시점 · 금액) 기록을 요청했다(2026-10-07 · BACKLOG §8 · 설계자 판단 대기 · §7-4).
2. **개별주 표가 지원하지 않는 종목(코스닥 등)의 판정 시점** — 개별주 표가 사건 뒤로 전진했으면 바로, 표가 멈춰 있으면(코스피 개별주 보유 0) 31거래일 채우기 창이 지난 뒤 `UNSUPPORTED_PRICE_SOURCE` 다.
3. **`PRICE_MISSING` 확정이 늦다** — 빠진 날이 채우기 창(ETF 21 · 개별주 31 거래일)을 지나야 확정된다(설계자 Q-C 정정 · 그 전에는 행 없음 = 대기).
4. **08:10 성숙이 08:30 러너와 가까울 수 있다** — 08:10 배치가 08:27 까지 KRX 를 기다리는 날. 원장 쓰기는 `BEGIN IMMEDIATE` 1회 짧은 INSERT 묶음이고, 읽기 · 계산은 쓰기 밖이다(검토 실측 6,000행 잠금 32.7 ms).
5. **배치 로그 줄 순서** — 성숙 로그(stderr · 파일 핸들러)가 결과 JSON(stdout · 버퍼) 보다 cron 로그 파일에서 먼저 보일 수 있다(stdout 내용 · exit code 는 같다).
6. **거래정지는 고려하지 않는다** — 거래량을 저장하지 않아 판별할 수 없지만(설계 §2 제외), 사용자가 ETF · 대형주만 투자해 고려 대상이 아니라고 정했다(2026-10-07).

## 6. 다음 검증자(Codex)에게 알릴 점

### 6-1. 판단이 어려웠던 부분

1. **채우기 창 기준일** — 창은 '오늘의 T-1 로 끝나는 W 거래일'(ETF 21 = `krx_store.REQUIRED_TRADING_DAYS` · 개별주 31 = `krx_stock_sync.WINDOW_TRADING_DAYS`)이다. 빠진 날이 창 첫날이면 대기, 하루 뒤 `PRICE_MISSING`(테스트로 고정).
2. **`UNTRACKED_AFTER_EXIT`** — 사건 때 `held=1` · 지금 보유 목록에 없음(목록을 읽었을 때만) · 그 종목 개별주 행이 첫 빠진 날 전에 끊김 · ETF 표가 평가일까지 지남. ETF 는 전 종목 snapshot 이라 매도 뒤에도 쌓여 이 상태가 없다.
3. **완료 item 건너뛰기** — `(event_id, item_seq)` 별 기존 행 수가 기대 수(계열 수 × 3) 이상이면 날짜 계산 전에 뺀다. `UNSUPPORTED` 는 계열 1개(`unsupported:<ticker>`)로 센다.

### 6-2. 독립 검토(2026-10-07 · 2관점 · 읽기 전용 · 사본 파괴 시험) 반영

- 코드 결함 4건(모두 수정 + 테스트):
  - A-F1(중간) 보유 파일이 없으면 빈 목록 → 보유 중 개별주가 모두 매도로 판정 → `holdings_tickers` 재사용(파일 없음 · 손상 = 모름).
  - A-F2(낮음) 매도 판정이 평가일 전에 확정 → ETF 축이 **평가일**까지 지난 뒤만.
  - A-F3 · B-7(중간) 실행 시간이 누적 item 수에 비례(캘린더 CSV 를 item 당 약 30회 다시 읽음 · 완료 item 도 날짜 계산 · 검토 실측 2,000 대상 15.3초 · 완료 뒤에도 15.1초) → 캘린더 실행당 1회 · 완료 item 은 날짜 계산 전에 제외(§8-4).
  - A-F4(낮음) 코스피 개별주 보유 0 이면 코스닥 종목이 영원히 대기 → 31거래일 창이 지나면 `UNSUPPORTED`.
- 테스트 격리 1건: B-1 `flag_enabled` 가 라이브 `.env` 를 읽어 결과가 개발자 · OCI `.env` 에 따라 달라짐 → `ENV_PATH` 모듈 상수 + conftest 가 tmp 로 바꿈.
- 테스트 공백(반영): 채우기 창 경계 · KOSPI 결측(뒤 날짜 · 미래 평가일) · 값 컬럼(사건일 · 직전일 종가 · 수집 시각 · KOSPI t0 날짜 · 평가일 최저 max_down) · 매도 대조군 · 시장 DB 읽기 전용 · 계산 중 원장 쓰기 잠금 없음 + INSERT OR IGNORE · import 실패 격리 · 09:20 skipped 날 · 출력 뒤 순서 · legacy 읽기 전용 · `.env` 다른 키 미노출.

## 7. 사용자 확인이 필요한 항목

1. **배포 시점** — 01B 첫 거래일(2026-10-08 09:35 이후) 확인 → 검증자 · 설계자 RESULT → 커밋 · push(승인) → OCI `git pull`(사용자). cron · `.env` 변경 0(01B 플래그를 그대로 쓴다). pull 시각은 거래일 15:45 이후나 비거래일 권장(배치 08:10 · 09:20 과 겹치지 않게).
2. **01B 상태 문구가 이 커밋 대상에 함께 있다**(§4-1).
3. 사용자 소유 `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` 는 손대지 않았고 stage 하지 않는다.
4. **보유 이력 기록 요청**(사용자 2026-10-07) — holdings 에 매수 · 매도 시점과 금액을 남기는 기능. BACKLOG §8 'holdings 스키마 확장' 항목의 재검토 트리거(사용자 명시 요구)에 도달했다고 기록했다. 설계자 판단(2026-10-07): 필요성 인정 · POC5-03 에 넣지 않음 · 별도 소형 설계로 매수 · 매도 시점과 금액 · 금액 · 수량은 holdings 에만(원장 밖) · POC5-02 결과는 다시 계산하지 않음.

---

## 8. 검증 실측 (2026-10-07)

### 8-1. 테스트

- `tests/test_poc5_02_price_outcome.py` 31 passed(AC 1 ~ 9 · Q-A ~ Q-D · 검토 반영 13개 포함 · 3회 연속 같음).
- 관련 묶음(01B 원장 3파일 · 배치 단계 · 시장 데이터 갱신 · POC5-02): 구현 직후 131 passed.

### 8-2. 정적 검사

- `black --check` · `flake8` · `py_compile`: 바뀐 · 새 Python 7파일 통과(2026-10-07).

### 8-3. 파괴 시험

- 검토 때(사본): 관점 A 27종 중 10종 · 관점 B 16종 중 7종 탐지. 놓친 것은 대부분 테스트 공백(창 크기 · KOSPI 규칙 · 값 컬럼 · ro 연결 · REPLACE · import 격리 등)과 코드 결함 4건에 걸린 변이였다.
- 반영 뒤(사본 · 변이마다 되돌린 뒤 저장소와 `filecmp` 일치 · 끝에 `diff -rq` 0): ETF 창 21 → 5 · 개별주 창 31 → 21 · KOSPI all → any · 보유 모름을 빈 집합으로 · 매도 판정 축 기준을 첫 빠진 날로 · 코스닥 창 게이트 제거 · 시장 DB 쓰기 연결 · INSERT OR REPLACE — **8종 모두 탐지**.

### 8-4. 성능

- 고친 뒤(맥북 · 임시 DB · `scratchpad/perf02.py`): 대상 1,320건(66 run × ETF 20) — 첫 실행 0.14초(INSERT 3,500 · 대기 460) · 바로 다시 실행 0.03초(남은 대상 380 · INSERT 0).
- 고치기 전(검토 실측 · 같은 맥북 · 조건 다름): 대상 2,000건 15.3초 · 완료 뒤 다시 실행 15.1초(캘린더 CSV 를 대상마다 다시 읽음).
- 캘린더를 실행당 1회만 읽는 것과 끝난 item 을 건너뛰는 것을 테스트로 고정했다(`test_calendar_is_read_once_and_done_items_are_skipped`).

### 8-5. KS-10 · 줄 수

- 트리거 0. 근접(백엔드 ≥ 600) 6개는 이번 단계 밖이고 그대로다(`api.py` 642 · `scripts/ops02c/reverse_verify_guards.py` 638 · `ml_score_validity_report.py` 626 · `holdings_market_evidence.py` 616 · `runtime_evidence/sector_signal.py` 611 · `draft.py` 602). 테스트 ≥ 1,450 0개.
- 이번 단계 파일: 배치 스크립트 580 → 596(근접선 600 아래) · 새 모듈 501 · 250 · `ledger_store.py` 495 → 547 · 대조 CLI 64 → 82 · 새 테스트 701 · `docs/PROGRAM_TRUTH.md` 969 → 974 · `docs/STATE_LATEST.md` 2807 → 2807(같은 줄 안 수정).

### 8-6. 백엔드 전체 회귀 · 라이브 보호

- `caffeinate -i .venv/bin/python -m pytest -q -p no:cacheprovider tests/` → `2935 passed, 1 warning in 382.63s (0:06:22)` · exit 0(2026-10-07 17:41 ~ 17:47 · 01B 마지막 회귀 2904 + POC5-02 31).
- 회귀 시작 뒤 바뀐 Python 파일 0(`find -newer` 실측).
- PC `state/` · `logs/` 1,153파일 sha256 전후 `diff` 0. 테스트의 배치 로그는 conftest 가 tmp 로 돌린다(라이브 `logs/oci_market_data_batch.log` 9월 23일 이후 불변).
- 프론트 변경 0.

## 9. git 상태

2026-10-07 `git status --short --untracked-files=all` 실측(검증자 제출 직전):

- staged 14 = 신규 `A` 6(모듈 2 · 테스트 1 · 설계서 · PLAN · 이 결과서) · 수정 `M` 8(`ledger_store.py` · 배치 스크립트 · 대조 CLI · `tests/conftest.py` · `docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md` · 01B 설계서 · 01B 결과서) — 모두 오른쪽 열 공백(staged = 작업 트리 · unstaged 0).
- 01B 설계서 · 결과서 · PROGRAM_TRUTH · STATE_LATEST 의 01B 부분은 상태 기록이다(§4-1 · 01B 코드 변경 0).
- 남은 것: `?? docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` 1건(사용자 소유 · stage 하지 않음).
- 기준 커밋: POC5-01B 커밋 `9cbbd419` 위 변경이다. 이 단계 커밋은 아직 없다.
- 검증자 r1 VERIFIED 뒤 바뀐 것(코드 0): 검증자 직접 정정 3곳 · 상태 문구(이 결과서 머리 · `docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md`) · 사용자 결정 반영(§5-1 재매수 · §5-6 거래정지 · §7-4 보유 이력 요청) · `docs/backlog/BACKLOG.md` §8 'holdings 스키마 확장' 재검토 트리거 도달 기록 1줄 → staged 15(신규 `A` 6 · 수정 `M` 9 · unstaged 0).

## 10. 배포 절차

1. POC5-01B 첫 거래일(2026-10-08) 운영 확인 · 01B 종료 기록.
2. 검증자 → 설계자 RESULT 판정 → 커밋 · push(사용자 승인).
3. OCI `git pull`(사용자) — cron · `.env` 변경 0.
4. 첫 확인(개발자 · OCI 읽기 전용): pull 다음 거래일 08:10 · 09:20 `logs/oci_market_data_batch.log` 의 `price outcome maturity:` 줄 · 원장 `price_outcome` 행 수 · 상태별 건수 · 배치 status · exit code 가 이전과 같음.
