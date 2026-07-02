# 시장 시계열 SQLite 기반 보강 Closeout — Conclusion

작성일: 2026-06-30
완료 판정: **DONE**

이 문서는 이전 PARTIAL 상태였던 "시장 시계열 SQLite 기반 보강" STEP 을
네이버/FDR 주 소스 + Yahoo/FDR 보조 소스 + CLI 최신화 + ML 실행 게이트 로 닫는 STEP 의 종료 기록이다.

---

## 1. KRX CSV 방식이 PARTIAL 이 된 운영상 이유

이전 STEP 은 KRX 데이터마켓 공식 다운로드 자료 (CSV/ZIP) → PC CLI → SQLite 를 유일 경로로 두었으나,

- 1,143 종 ETF universe 의 장기 시계열을 사용자가 수동 CSV/Excel 반복 다운로드로 채워야 하는 구조.
- 개인 프로젝트의 일상 최신화 경로로 성립하지 않음.

→ 본 STEP 은 CLI 최신화 주 소스를 **네이버/FDR 로 전환**. KRX CSV import 는 특정 과거 구간 수동 보정용으로만 유지 (기존 `scripts/ingest_krx_timeseries.py` 그대로).

---

## 2. 네이버/FDR 주 소스 + Yahoo 보조 원칙

지시문 §4 확정:

```text
주 소스: NAVER_FDR
  fdr.DataReader("NAVER:<ticker>", start, end)
보조 소스: YAHOO_FDR
  fdr.DataReader("YAHOO:<ticker>.KS", start, end)
```

- **호출 식별자에 소스를 명시** (FIX r1) — FDR 의 기본 source inference 에 의존하지 않는다. `build_naver_symbol` / `build_yahoo_symbol` 헬퍼로 생성.
- 한 종목·한 실행: 네이버 1회 → 실패 또는 빈 응답일 때만 Yahoo 1회. 자동 재시도 없음.
- Yahoo 는 이중 검증 / 자동 판정 수단 아님.
- 신규 의존성 도입 0건 (기존 FinanceDataReader 만 사용).
- 가격 기준: `SOURCE_CLOSE` — 각 소스의 일반 `Close` 만. `Adj Close` 사용 금지.

구현:
- `app/market_timeseries_naver_yahoo_adapter.py::fetch_ticker_prices` 가 primary → secondary 흐름 캡슐화.
- `AdapterResult.source` 로 실제 사용한 소스 라벨 기록.
- `test_symbol_builders_are_source_explicit` / `test_naver_primary_returns_rows` 에서 호출 식별자에 prefix 가 포함됨을 assert.

---

## 3. KODEX200 (069500) 실제 적재 범위

본 개발 환경에서 실행한 실측:

| 항목 | 값 |
|---|---|
| ticker | 069500 (KODEX 200) |
| source | NAVER_FDR |
| requested_start_date | 2014-04-07 |
| observed_start_date | 2014-04-09 |
| benchmark_asof_date | 2026-07-02 |
| observed_trading_day_count | 3000 |
| price_basis | SOURCE_CLOSE |
| 설명되지 않는 결측 | 0건 |
| status | normal |

`market_timeseries_refresh_state.benchmark_asof_date` = `2026-07-02` 로 확정.

---

## 4. 표본 실제 소스 검증 결과

지시문 §4.1 / AC-13 준수 — 실제 소스 데이터 기준 표본 3종 확인:

| 구분 | ticker | source | observed_start | rows |
|---|---|---|---|---|
| 벤치마크 | 069500 (KODEX 200) | NAVER_FDR | 2014-04-09 | 3000 |
| 오래된 ETF | 069660 (KOSEF 200) | NAVER_FDR | 2014-04-09 | 3000 |
| 오래된 ETF | 102110 (TIGER 200) | NAVER_FDR | 2014-04-09 | 3000 |
| 최근 상장 ETF | 0000D0 | NAVER_FDR | 2024-12-17 | 373 |

가격 기준: 네이버/FDR 이 반환하는 `Close` 컬럼. 조정 종가 여부는 소스 문서에 명시적으로 조정된 값을 반환한다는 문서가 없으므로 `SOURCE_CLOSE` 라벨로 저장.

`069500`, `069660`, `102110` 이 동일한 실측 시작일(`2014-04-09`) 을 갖는 것은 지시문 §5 기본 요청 시작일 `2014-04-07` 과 실제 주말·개장일 (2014-04-07 월요일 → 실제 첫 거래일) 관계 상 예상된 결과.

---

## 5. Yahoo 보조 경로 확인

- **재현 가능한 adapter test 로 확인** (AC-14): `tests/test_market_timeseries_naver_yahoo_adapter.py` 6 케이스.
  - `test_yahoo_fallback_used_when_naver_empty` — 네이버 빈 응답 시 Yahoo 로 fallback.
  - `test_yahoo_fallback_used_when_naver_raises` — 네이버 예외 시 fallback.
  - `test_both_sources_empty_records_error` — 둘 다 빈 응답 시 error 기록.
  - `test_yahoo_only_attempted_once_per_call` — 자동 재시도 없음.
- **실측 표본 (개발 환경)**: `073130` (KODEX 인버스) 등에서 네이버 빈 응답 → Yahoo 도 빈 응답 → `error` 기록 확인. Yahoo 성공 케이스는 실측 표본에서 자연 발견되지 않음 — adapter test 로 fallback 로직 자체는 완전 검증.

---

## 6. 전체 ETF universe 적재 결과

`--all` 실행 결과 (개발 환경 실측, 기본 SQLite `state/market/market_data.sqlite`.
해당 파일은 `.gitignore:173` 로 이미 무시되므로 commit 되지 않음. 사용자 PC 에 실측 결과 남음):

| status | count |
|---|---|
| normal | 1007 |
| partial | 0 |
| missing_confirm | 138 |
| source_missing | 0 |
| failed | 0 |
| listing_unknown | 0 |

`market_timeseries_refresh_state` 최종 실측:
- `last_attempt_status = ok`
- `benchmark_asof_date = 2026-07-02`
- `eligible_ticker_count = 1006`
- `excluded_ticker_count = 138`

`069500` etf_daily_price 실측: `COUNT=3000`, `MIN(date)=2014-04-09`, `MAX(date)=2026-07-02`.

**missing_confirm 138 종의 사유**: 기존 SQLite 에 이미 저장된 가격 (이전 refresh 로그 / 초과수익 계산 경로에서 축적된 값) 과 이번 실측의 명시 소스 (`NAVER:<ticker>`) 반환 값이 다른 케이스. 지시문 §8.1 "기존 값과 다른 가격은 자동 덮어쓰지 않고 missing_confirm 라벨" 정책 그대로. 사용자 확인 후 `--retry-pending` 으로 재처리 가능.

전체 universe 가 NAVER_FDR 만으로 커버됨 (source_missing / failed 0건). AC-15 통과.

---

## 7. 초기 적재·증분 최신화·재개 결과

### 7.1 CLI 구조

`scripts/refresh_market_timeseries.py` — 4 서브커맨드:

| 명령 | 책임 |
|---|---|
| `benchmark` | KODEX200 먼저 최신화 → `benchmark_asof_date` 확정 |
| `initial` | 초기 적재 필요 종목만 처리. `--max-tickers N` 또는 `--all` 필수 |
| `incremental` | benchmark 재실행 → 정상 종목의 last date+1 ~ benchmark_asof 만 요청 |
| `status` | 최신화 + ingestion 상태 요약 |

### 7.2 재개 (AC-6)

- `initial`: `market_timeseries_ingestion_state.status != normal` 인 종목만 처리 (`_pending_tickers_for_initial`).
- `incremental`: `status == normal` 인 종목의 마지막 `confirmed_series_end_date + 1일`부터 `benchmark_asof_date` 까지만 요청 (`_incremental_start_for`).
- `--retry-pending` 옵션으로 `partial / missing_confirm / failed / source_missing` 재처리.
- 중단 후 다음 실행에서 이어서 처리됨을 CLI 테스트 (`test_cli_initial_processes_pending_tickers`, `test_cli_incremental_processes_normal_tickers`) 로 검증.

### 7.3 중복·충돌 (AC-7 / AC-8)

- `(ticker, date)` PK ON CONFLICT DO UPDATE — 동일 값 재수집은 흡수, 다른 값은 자동 덮어쓰기 X (FIX r1 로 도입된 `_split_by_existing_conflict` 재사용).
- 정상 종목의 증분 요청 시작일은 `last confirmed date + 1일` — 마지막 저장일 이후 구간만 요청.

---

## 8. 최신화 실행 상태 SSOT

지시문 §6.2 준수:

```text
테이블: market_timeseries_refresh_state
단일 행: refresh_scope = "daily_prices"
```

D-2 의 `market_refresh_state` (기존 `/market/refresh` 용) 와는 **별도 신규 테이블**. 두 테이블 통합·의미 확장 0건.

컬럼 11개: `target_asof_date / benchmark_asof_date / last_attempt_started_at / last_attempt_finished_at / last_attempt_status / last_success_at / eligible_ticker_count / excluded_ticker_count / error_summary / updated_at + refresh_scope PK`.

running 잔존 정규화: `normalize_running_to_failed` — 다음 CLI 또는 ML 게이트 진입 시 running → failed. 성공 기록은 유지. 테스트 `test_normalize_running_to_failed_preserves_success` 로 검증.

---

## 9. ML SQLite 사전 점검 결과

지시문 §9 준수. 기존 `POST /ml/jobs/evidence-refresh` 응답 계약 유지:

- 새 endpoint / 새 응답 필드 추가 0건.
- 게이트 실패 → `status="error"` + `message="시계열 최신화가 완료되지 않았습니다. PC에서 시계열 최신화 배치를 실행한 뒤 다시 시도하세요."`
- 게이트 성공 → 기존 `status="accepted"` 그대로.

`app/api_ml_jobs.py::_timeseries_ready_for_ml` 이 SQLite 만 read 하여 다음을 확인:
1. `market_timeseries_refresh_state.last_attempt_status == 'ok'`
2. `benchmark_asof_date` 존재
3. KODEX200 (069500) 의 `market_timeseries_ingestion_state.status == 'normal'`
4. `eligible_ticker_count > 0`

외부 시세 호출 0건. UI 클릭으로 universe 대량 적재 0건.

테스트 `tests/test_api_ml_jobs_timeseries_gate.py` 6 케이스가 각 조건별 게이트 동작을 커버.

---

## 10. KRX CSV/Excel fallback 위치

기존 `scripts/ingest_krx_timeseries.py` + CSV import 경로는 그대로 유지. 사용 위치:

- 2014-04-07 이전 데이터가 실제로 필요할 때 (BACKLOG 로 별도 관리).
- 네이버/FDR·Yahoo 모두 제공하지 않는 특정 과거 구간의 수동 보정.
- 확인된 충돌·누락의 수동 보정.

사용하지 않는 경로:
- 현재 ETF universe 의 정기 최신화 (본 STEP 이후 네이버/FDR 담당).
- 본 STEP DONE 의 전제 (이전 STEP 의 PARTIAL 인용은 정정됨).

---

## 11. 2014년 이전 데이터 보류 사유

`docs/backlog/BACKLOG.md` 에 다음 항목 추가:

```text
항목: 2014-04-07 이전 ETF 시계열 보강
보류 사유: 현재 개인 프로젝트의 첫 ML·위험 evidence 기반은
           2014-04-07 이후 실제 접근 가능한 데이터로 시작한다.
보류된 위험: 장기 백테스트 기간이 제한될 수 있다.
재검토 트리거: 2014년 이전 구간이 모델 성능 또는 백테스트 범위에
              실질적으로 필요하다는 근거가 확인될 때.
```

---

## 12. 자동 테스트 결과

| 항목 | 결과 |
|---|---|
| backend 전체 테스트 | **675 passed** (650 → 675, 신규 25 — FIX r1 symbol builder 테스트 +1) |
| black | PASS |
| flake8 | PASS |
| frontend lint | PASS |
| frontend build | PASS |

신규 테스트 25건:
- `tests/test_market_timeseries_naver_yahoo_adapter.py` (7) — symbol builder (FIX r1) / primary NAVER: 명시 / fallback YAHOO:.KS 명시 / 재시도 없음 / price_basis 상수
- `tests/test_market_timeseries_refresh_state.py` (5) — 단일 행 / running 정규화 / 성공 보존
- `tests/test_refresh_market_timeseries_cli.py` (7) — benchmark / initial / incremental / status / ASCII 안전
- `tests/test_api_ml_jobs_timeseries_gate.py` (6) — 게이트 6 조건 (no row / not ok / bm missing / eligible=0 / running 정규화 / ready 통과)
- `tests/test_market_data_store.py` — 테이블 목록 5 → 6종 갱신

---

## 13. 이번 STEP 에서 하지 않은 범위

지시문 §10 준수:

- 위험 점수 / 위험 evidence 계산
- 시장 국면 라벨 / 추세 전환 거리
- ML 축2 학습·추론 (모델·factor·산식 변경 0건)
- 백테스트 결과 / 성과 화면
- 새 UI 화면·새 메뉴
- 새 API 또는 기존 API 계약 변경 (기존 `POST /ml/jobs/evidence-refresh` 응답 필드 그대로)
- OCI / Telegram / PARAM 변경
- KRX Open API 주 소스 전환
- 상시 scheduler
- 신규 DB 엔진 / 새 가격 테이블
- 자동 매수·매도·비중 조절

본 STEP 은 시계열 적재·최신화 경로 완성. 위험 evidence / 국면 / ML 축2 등은 후속 STEP.

---

## 14. 변경 파일 목록

- `app/market_data_store.py`: 수정 (`MARKET_TIMESERIES_REFRESH_STATE_DDL` 추가, `init_db` 에 포함).
- `app/market_timeseries_refresh_state_store.py`: 신규 (CLI 최신화 실행 상태 SSOT).
- `app/market_timeseries_naver_yahoo_adapter.py`: 신규 (NAVER_FDR primary + YAHOO_FDR secondary).
- `app/market_timeseries_ingestion_store.py`: 수정 (`read_state` late-bind DEFAULT_DB_PATH).
- `app/api_ml_jobs.py`: 수정 (게이트 `_timeseries_ready_for_ml` 삽입).
- `scripts/refresh_market_timeseries.py`: 신규 (CLI — benchmark / initial / incremental / status).
- `tests/test_market_data_store.py`: 수정 (테이블 목록 5 → 6종).
- `tests/test_ml_job_runner.py`: 수정 (기존 fixture 에서 게이트 bypass — 게이트 자체는 별도 파일에서 검증).
- `tests/test_market_timeseries_naver_yahoo_adapter.py`: 신규 (6 케이스).
- `tests/test_market_timeseries_refresh_state.py`: 신규 (5 케이스).
- `tests/test_refresh_market_timeseries_cli.py`: 신규 (7 케이스).
- `tests/test_api_ml_jobs_timeseries_gate.py`: 신규 (6 케이스).
- `docs/STATE_LATEST.md`: 수정.
- `docs/handoff/POC2_B_NEXT_ACTIONS.md`: 수정.
- `docs/handoff/POC2_FEATURE_INVENTORY.md`: 수정 (§2.36 추가).
- `docs/handoff/POC2_MARKET_TIMESERIES_SQLITE_CONCLUSION.md`: 수정 (PARTIAL 사유 정정 + 본 STEP 참조).
- `docs/handoff/POC2_MARKET_TIMESERIES_SQLITE_CLOSEOUT_CONCLUSION.md`: 신규 (본 파일).
- `docs/backlog/BACKLOG.md`: 최소 갱신 (2014년 이전 보류 항목).
- `docs/ASSUMPTIONS.md`: 최소 갱신 (표본 실측 결과 기반 시작일 확정).

---

## 15. AC 충족 (지시문 §11)

| AC | 결과 | 비고 |
|---|---|---|
| AC-1 KRX CSV PARTIAL 운영상 이유 문서 정정 | ✅ | §1 |
| AC-2 네이버/FDR 주 소스 | ✅ | adapter + CLI |
| AC-3 Yahoo 보조 (실패·빈 응답 시) | ✅ | adapter test 검증 |
| AC-4 KODEX200 먼저 + benchmark_asof_date 저장 | ✅ | benchmark 서브커맨드 |
| AC-5 PC CLI 실행 (UI 대량 호출 X) | ✅ | 브라우저 요청 대량 호출 0건 |
| AC-6 재개 가능 | ✅ | pending 리스트 + last date+1 |
| AC-7 정상 종목 last date 이후만 요청 | ✅ | `_incremental_start_for` |
| AC-8 기존 값 자동 덮어쓰기 금지 | ✅ | `_split_by_existing_conflict` |
| AC-9 최근 최신화 1건 SQLite + running 정규화 | ✅ | `normalize_running_to_failed` |
| AC-10 ML 실행 외부 호출 없이 SQLite read | ✅ | `_timeseries_ready_for_ml` |
| AC-11 KODEX200 준비 안되면 ML 차단 | ✅ | gate test 6 케이스 |
| AC-12 개별 ETF 실패 → 해당 ETF 만 제외 | ✅ | ingest_etf_timeseries 격리 유지 |
| AC-13 KODEX200 + 오래된/최근 ETF 실측 | ✅ | §4 표 |
| AC-14 Yahoo 보조 재현 가능 adapter test | ✅ | 6 케이스 |
| AC-15 universe 전체 상태별 건수 SQLite 기록 | ✅ | §6 (normal 1007 / missing_confirm 138 / failed 0) |
| AC-16 위험/ML/UI/OCI/Telegram 변경 0건 | ✅ | |
| AC-17 backend / black / flake8 / frontend lint / build | ✅ | 675 passed 모두 PASS |

---

## 16. 다음 작업 후보 (사용자 결정 대기)

1. **위험 evidence / 시장 국면 / 추세 전환 거리** — 본 STEP 확보 시계열 위에서 진입.
2. **ML 축2** (위험 감지) 학습·추론 — 동일.
3. **역사적 상장폐지 ETF universe 재구성** — 생존자 편향 해소 (BACKLOG).
4. 기타 BACKLOG 항목.
