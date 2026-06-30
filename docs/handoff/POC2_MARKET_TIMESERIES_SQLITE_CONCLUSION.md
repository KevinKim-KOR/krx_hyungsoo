# 시장 시계열 SQLite 기반 보강 — Conclusion (PARTIAL)

작성일: 2026-06-30
측정 방식: `wc -l` (Bash) 통일.

이 문서는 위험 evidence·국면·백테스트의 기반이 되는 ETF/KODEX200 일별 종가 시계열을
기존 시장 SQLite (`state/market/market_data.sqlite`) 로 적재하는 STEP 의 종료 기록이다.

---

## 1. 완료 판정 — PARTIAL

이번 STEP 은 **PARTIAL** 로 보고한다. 사유:

```text
- 지시문 §1 / §4 / Q1 답: 승인된 KRX 데이터마켓 공식 다운로드 자료를 PC 에서
  CLI 로 SQLite 에 적재하는 경로로만 진행한다.
- 본 개발 환경에서는 KRX 데이터마켓 자료에 직접 접근할 수 없다.
- 따라서 (1) CLI 도구 / (2) SQLite 데이터 계약 / (3) 결측 분류·재개·중복방지
  로직 / (4) fixture 기반 자동 테스트 까지 완료한다.
- 실제 KODEX200 2010-01-01 ~ 최신 적재 (AC-2), KODEX200 결측 검증 (AC-3),
  ETF universe 적재 (AC-4), 결측 분류 실측 (AC-5) 은 사용자가 PC 에서
  KRX 자료를 직접 받아 CLI 로 적재한 뒤 채워질 영역이다.
- FDR 로 대신 호출해 DONE 처리하지 않는다 (Q2 답).
```

검증자(Codex) 통과 후 사용자가 PC 에서 다음을 실행하면 DONE 으로 승격된다.

```bash
# 1) KODEX200 벤치마크 (2010-01-01 ~ 최신)
python -m scripts.ingest_krx_timeseries benchmark \
    --csv data/krx/kodex200_2010_2026.csv \
    --benchmark-id 069500 --benchmark-name "KODEX 200" \
    --price-basis "<자료 명시 가격 기준>"

# 2) ETF universe (재개 가능, 중복 방지)
python -m scripts.ingest_krx_timeseries etf \
    --csv data/krx/etf_universe_daily.csv \
    --price-basis "<자료 명시 가격 기준>"

# 3) 상태 요약
python -m scripts.ingest_krx_timeseries status
```

---

## 2. 실제 소스 검증 대상과 결과

| 대상 | 식별자 | 실제 최초 제공일 | 최신 제공일 | 거래일 수 | 비고 |
|---|---|---|---|---|---|
| 벤치마크 (KODEX200) | 069500 | (사용자 실측 필요) | (사용자 실측 필요) | (사용자 실측 필요) | 본 STEP 코드 환경에서는 미실측 |
| 오래된 ETF (최초 관측 가장 이른) | (사용자 실측 후 기록) | — | — | — | KRX 자료 기반 휴리스틱 선정 |
| 중간 상장 ETF (관측 시작 중앙값) | (사용자 실측 후 기록) | — | — | — | 동일 |
| 최근 상장 ETF (최초 관측 가장 늦은) | (사용자 실측 후 기록) | — | — | — | 동일 |

지시문 §4 원칙:

- 기존 universe 메타데이터만으로 추정하지 않는다.
- KRX 자료에서 실제 확인된 최초 관측일을 기준으로 선정한다.
- 임의 대체 source 추가, 빈값·0·직전값·추정값 채움 모두 금지.

가격 기준 (조정 종가 / 원시 종가) 도 본 STEP 코드 환경에서 확정하지 않는다 — KRX 자료의 실제 필드/문서로만 기록한다 (CLI `--price-basis` 인자).

---

## 3. KODEX200 확보 범위와 결측 검증 결과

| 항목 | 값 |
|---|---|
| 요청 범위 시작 | 2010-01-01 |
| 요청 범위 끝 | 소스 최신 기준일 |
| 실제 관측 범위 | (사용자 실측 후 기록) |
| 설명되지 않는 결측 | (사용자 실측 후 기록) |
| 검증 통과 | (사용자 실측 후 기록) |

지시문 §5 / AC-3:

- KODEX200 에 설명되지 않는 결측이 있으면 **전체 ETF 대량 적재로 진행하지 않는다.**
- 휴장일은 결측으로 간주하지 않는다.
- KODEX200 의 관측 거래일 집합이 이후 ETF 상장 후 결측 판정의 **기준 달력**이다.

본 STEP 의 자동 테스트 (`tests/test_market_timeseries_ingestion.py`) 는 KODEX200 적재 후 그 거래일 집합이 `_count_post_listing_missing` 의 기준이 되는 흐름을 fixture 로 검증했다.

---

## 4. ETF universe 적재 수와 상태별 건수 (실측 후 기록)

본 STEP 코드 환경에서는 실측 0건. 사용자 PC 실행 후 아래 자리에 채워진다.

| 상태 | 의미 | 건수 |
|---|---|---|
| normal | 정상 적재 | (실측 후) |
| partial | 부분 적재 (post-listing 결측 존재) | (실측 후) |
| missing_confirm | 충돌·bad price → 확인 필요 | (실측 후) |
| source_missing | 소스에 ticker 자체 없음 | (실측 후) |
| failed | 적재 실패 | (실측 후) |
| listing_unknown | 상장일/시작일 확인 불가 | (실측 후) |

상태 enum 은 `app/market_timeseries_ingestion_store.py` 의 `STATUS_*` 상수로 고정. 별도 status 추가 금지.

---

## 5. 상장 전 / 소스 미제공 / 상장 후 결측 구분 기준

`app/market_timeseries_ingestion_service.py` 의 `_count_post_listing_missing` 가 다음 규칙으로 분류한다.

```text
- 상장 전 날짜
  → 정상 비존재. observed/missing 모두 카운트 X.

- 소스 제공 시작일 이전
  → source_missing 범위. CSV 에 ticker 자체가 없으면 IngestionInput.source_missing=True
    → status=source_missing.

- 확인된 시계열 범위 [series_start, series_end] 안의 KODEX200 거래일 중
  ETF 가격이 없는 경우
  → post_listing_missing_count 로 카운트.
  → 건수 > 0 이면 status=partial.

- 동일 (ticker, date) 가 충돌 가격으로 들어오면 (batch 내 또는 기존 DB)
  → 자동 선택 X. status=missing_confirm. 충돌 row 는 적재 X (기존 가격 보존).

- 0 이하·NaN·None·비수치 close
  → 적재 제외. status=missing_confirm.

- 벤치마크 (KODEX200) 거래일 집합이 비어 있는 상태에서 ETF 적재
  → KODEX200 선행 적재 (지시문 §5) 가 안 된 상태이므로 ETF 를 normal 로
    표시하지 않는다. status=partial + error_summary="benchmark_calendar_unavailable".
```

### 기존 가격 충돌 보호 (FIX r1, 2026-06-30)

지시문 §6.1: "기존 가격 데이터와 충돌하는 동일 종목·동일 날짜 값이 발견되면
임의로 덮어쓰지 않는다." 보호 위해:

- `fetch_existing_close_map` (ETF) / `fetch_existing_benchmark_close_map` (KOSPI 등 지수) 가 적재 직전 기존 SQLite close 를 read.
- `_split_by_existing_conflict` 가 (1) 기존 close=NULL or ≤0 → 적재 허용, (2) 동일 값 (eps≤1e-9) → 적재 허용 (ON CONFLICT 흡수), (3) 다른 값 → 적재 제외 + conflict_dates 누적.
- 충돌 row 가 1개 이상이면 status=missing_confirm + error_summary=`existing_price_conflict: dates=...`.
- 모든 row 가 충돌이면 적재 0건 + error_summary=`all_rows_conflict_with_existing`.

### CLI ETF universe 가드 (FIX r1 + r2, 2026-06-30)

지시문 §7: "전체 적재 대상은 기존 SQLite 의 현재 ETF universe 를 사용한다."
보호 위해:

- `scripts/ingest_krx_timeseries.py etf` 가 universe 결정 기준을 **CSV 가
  아닌 기존 SQLite `etf_master`** 로 변경.
- `etf_master` 가 비어 있으면 CLI 가 rc=2 로 즉시 거부 (universe 갱신 선행 요구).
- `--ticker` 로 지정한 ticker 도 동일 — universe 비어있거나 universe 에 없으면 rc=2 로 거부 (FIX r2 — 가드 우회 차단).
- CSV 에는 있으나 universe 에 없는 ticker 는 skip + 경고 출력.

### CLI 출력 인코딩 안전 (FIX r2, 2026-06-30)

Windows 기본 콘솔 코드페이지 (cp949 등) 에서 비ASCII 문자 (em dash, 한글 등) 출력 시 `UnicodeEncodeError` 로 CLI 가 정상 rc 반환 전 crash. 보호 위해:

- CLI 의 모든 stdout / stderr 출력 메시지는 ASCII 만 사용.
- 모듈 로드 시 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` (Python 3.7+) — 가능한 환경에서 UTF-8 로 전환, 실패 시 무시.
- 자동 테스트 `test_cli_output_is_ascii_safe` 가 모든 CLI 출력이 ASCII 인코딩 가능함을 검증.

금지 규칙 (지시문 §7):

- 0 으로 채우기 / 직전값 채우기 / 보간 → 모두 금지.
- 상장 전 데이터를 결측 오류로 처리 → 금지.
- 현재 universe 만으로 생존자 편향 0 으로 주장 → 금지 (역사적 universe 재구성은 본 STEP 범위 외).

---

## 6. 적재 재개 검증 결과

`tests/test_market_timeseries_ingestion.py::test_resume_skips_normal_tickers` + `tests/test_ingest_krx_timeseries_cli.py::test_cli_etf_skips_already_normal` 가 다음을 검증.

- 이미 `status=normal` 인 종목은 다음 실행에서 자동 skip (재개 가능).
- 동일 CSV 두 번 실행해도 (ticker, date) PK 의 `ON CONFLICT DO UPDATE` 로 중복 행 0건.
- `--force` 플래그로 강제 재적재 가능.

`list_pending_tickers` 가 `status != normal` 인 ticker 만 반환 → 사용자 CLI 가 점진 적재를 정확히 이어받음.

---

## 7. SQLite SSOT 원칙

```text
가격 시계열 SSOT:
  ETF        → 기존 etf_daily_price (재사용, 신규 가격 테이블 신설 X)
  KODEX200   → 기존 etf_daily_price (ETF 이므로 동일 테이블)
  KOSPI      → 기존 market_benchmark_daily_price (지수 — 별도 유지)

적재 상태 SSOT:
  market_timeseries_ingestion_state (신규, 단일 종목당 1행, ticker PK)

JSON / 파일:
  - KRX 다운로드 자료는 보조 입력 (CSV/ZIP).
  - export artifact 는 허용.
  - 시계열 또는 적재 상태의 SSOT 로 사용 X.

신규 DB 엔진: 없음.
신규 가격 테이블: 없음.
```

기존 초과수익 / 상대상승 / 시장 국면 계산이 읽는 가격 테이블 경로는 변경 0건. `fetch_price_history`, `fetch_benchmark_history` 등 read API 그대로.

---

## 8. 이번 Step 에서 하지 않은 범위

지시문 §9 / AC-10 / AC-11 준수:

- 위험 점수 / 위험 evidence 계산
- 시장 국면 라벨 / 추세 전환 거리
- ML 축2 학습·추론
- 백테스트 결과 / 성과 화면
- 새 UI / 새 API / 새 응답 필드
- OCI / Telegram / PARAM 변경
- 신규 DB 엔진 / 신규 가격 테이블
- 역사적 ETF universe 재구성 (생존자 편향 해소)
- 자동 매수·매도·비중 조절

본 STEP 은 **데이터 기반 STEP**이다. 사용자가 PC 에서 실제 KRX 자료로 적재를 완료한 뒤 위험 evidence / 국면 / ML 축2 / 백테스트 STEP 들이 본 SQLite 상태를 기반으로 진행된다.

---

## 9. 자동 테스트 / 검증 결과

| 항목 | 결과 |
|---|---|
| backend 전체 테스트 | **650 passed** (627 → 650, 신규 23 케이스 — FIX r1 +6, FIX r2 +2) |
| black | PASS |
| flake8 | PASS |
| frontend lint | PASS |
| frontend build | PASS |
| 새 UI / API / ML / OCI / Telegram | 0건 |

신규 테스트 (23건):

- `tests/test_market_timeseries_ingestion.py` (15) — 결측 분류, KODEX200 적재, batch 충돌·bad price → missing_confirm, 재개 skip, ON CONFLICT 흡수, 상태 카운트, 기존 가격 충돌 보호 (3, FIX r1), benchmark calendar 없음 → partial (1, FIX r1).
- `tests/test_ingest_krx_timeseries_cli.py` (8) — CSV → benchmark / ETF 적재, skip-already-normal, source_missing, status, universe 가드 — ticker not in universe 거부 / universe empty 거부 (2, FIX r1), **--ticker 우회 차단 / CLI 출력 ASCII 안전 (2, FIX r2)**.
- `tests/test_market_data_store.py` — 테이블 목록 4 → 5종 갱신

---

## 10. 변경 파일 목록

- `app/market_data_store.py`: 수정 (`MARKET_TIMESERIES_INGESTION_STATE_DDL` 추가, `init_db` 에 포함, `fetch_existing_close_map` 추가 — FIX r1).
- `app/market_benchmark_store.py`: 수정 (`fetch_existing_benchmark_close_map` 추가 — FIX r1).
- `app/market_timeseries_ingestion_store.py`: 신규 (state row + read/write/count/pending/clear).
- `app/market_timeseries_ingestion_service.py`: 신규 (결측 분류 + ingest ETF/벤치마크).
- `scripts/ingest_krx_timeseries.py`: 신규 (CLI — benchmark / etf / status 서브커맨드).
- `tests/test_market_timeseries_ingestion.py`: 신규 (15 케이스 — 초기 11 + FIX r1 +4).
- `tests/test_ingest_krx_timeseries_cli.py`: 신규 (8 케이스 — 초기 4 + FIX r1 +2 + FIX r2 +2).
- `tests/test_market_data_store.py`: 수정 (테이블 목록 검증).
- `docs/STATE_LATEST.md`: 수정.
- `docs/handoff/POC2_B_NEXT_ACTIONS.md`: 수정.
- `docs/handoff/POC2_FEATURE_INVENTORY.md`: 수정 (§2.35 추가).
- `docs/handoff/POC2_MARKET_TIMESERIES_SQLITE_CONCLUSION.md`: 신규 (본 파일).

`docs/ASSUMPTIONS.md` / `docs/backlog/BACKLOG.md` 는 실제 소스 범위 / 생존자 편향 관련 상태가 새로 확정된 경우에만 최소로 갱신한다 — 본 STEP 은 코드 환경에서 미실측이므로 갱신 0건.

---

## 11. 알려진 한계

- **실측 미완료**: KRX 데이터마켓 자료 접근이 본 환경에서 불가능 — AC-1~AC-5 의 실측 부분은 사용자 PC 실행 후 채워진다.
- **가격 기준 미확정**: 조정 종가 / 원시 종가 여부는 KRX 자료 명시 필드로만 기록. CLI `--price-basis` 인자 필수.
- **표본 4종 미선정**: 실제 KRX 자료 적재 후 휴리스틱 (가장 이른 / 중앙값 / 가장 늦은) 으로 선정 후 본 문서 §2 에 기록.
- **생존자 편향**: 현재 universe 는 운영 중 ETF 만 포함. 과거 상장폐지 ETF 포함한 역사적 universe 재구성은 본 STEP 범위 외 (BACKLOG).
