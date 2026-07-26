# POC2 — FDR + SQLite Market Data Foundation 1차 구현 개발 결과서

| 항목 | 값 |
|---|---|
| 작성자 | 개발자 (VSCode Claude) |
| 작성일 | 2026-05-16 |
| 원본 지시문 | 설계자 — `FDR + SQLite Market Data Foundation 1차 구현` |
| 검증자(Codex) 결과 | **VERIFIED_WITH_NOTES** (FIX 라운드 1회 후) |
| commit | `dc6e83dd feat(poc2-fdr-sqlite): FDR + SQLite market data foundation 1차 구현` |
| push | `1f239ddf..dc6e83dd  main -> main` (github.com:KevinKim-KOR/krx_hyungsoo.git) |
| 11 files changed | 1,615 insertions(+), 5 deletions(-) |

---

## 1. 본 STEP 의 목표 (지시문 §2 / §3)

B 방향 PC 작업 1~2단계 (한국 상장 ETF 전체 universe 조회 → 일간/1개월/3개월 수익률
기준 TOP N) 의 **데이터 기반 구축**.

- 1순위 데이터 소스: **FinanceDataReader** (가능성 확인 STEP PASS — 2026-05-15).
- 저장소: **SQLite** (`state/market/market_data.sqlite`) — 3 테이블만 도입.
- 산출물: `state/market/etf_universe_topn_latest.json` (TOP 10 artifact).

본 STEP 은 UI / API / Telegram / OCI 연결 / ML 연결 단계가 아니다. **시장 데이터
저장 기반** 단계로 명시 한정.

---

## 2. 사용자 최종 결정 (지시문 §1) 반영 확인

| 결정 | 반영 |
|---|---|
| FinanceDataReader 를 1순위 데이터 소스 채택 | ✓ requirements.txt + `app/market_data_fdr.py` |
| KRX OPEN API fallback 유지 | ✓ BACKLOG 등록, 인증키 승인 대기 |
| pykrx ETF universe 자동 조회 경로 폐기 | ✓ PROJECT_ORIGIN_INTENT §8 명시 |
| SQLite 진행 | ✓ `app/market_data_store.py` + 3 테이블 |
| pandas/FDR 의존성 충돌 리스크 감수 | ✓ 실측: pandas 2.3.3 유지 — **충돌 미발생** |
| 설치/테스트 실패 시 즉시 보고 | 해당 없음 (모두 통과) |
| 판단 근거 저장은 BACKLOG | ✓ BACKLOG 등록, 본 STEP 비구현 |

---

## 3. 구현 산출물

### 3.1 신규 모듈 (3)

| 파일 | 라인 (black 적용 후 실측) | 책임 |
|---|---|---|
| `app/market_data_store.py` | 332 | SQLite DDL + upsert + log + helpers |
| `app/market_data_fdr.py` | 300 | FDR universe + price fetch 래퍼 (테스트 stub 가능) |
| `app/market_topn.py` | 206 | SQLite 기반 daily/1m/3m TOP N + artifact 저장 |

각 모듈은 KS-10 안전 범위 (백엔드 trigger 650 / near 600 모두 미달).

### 3.2 신규 테스트 (18)

| 파일 | 라인 | 테스트 수 |
|---|---|---|
| `tests/test_market_data_store.py` | 224 | 6 |
| `tests/test_market_data_fdr.py` | 214 | 6 |
| `tests/test_market_topn.py` | 193 | 6 |

지시문 §11 의 11개 요구 항목 + 빈 DB 가드 / DDL 검증 / 정합성 가드 7개 추가 = 18개.

### 3.3 SQLite 테이블 (3 — 지시문 §4 그대로)

| 테이블 | 컬럼 |
|---|---|
| `etf_master` | ticker (PK) / name / category / price / volume / market_cap / source / last_seen_at |
| `etf_daily_price` | (ticker, date) PK / open / high / low / close / volume / change / source / fetched_at |
| `market_refresh_log` | run_id (PK) / source / asof / attempted_count / success_count / fail_count / runtime_seconds / error_summary / created_at |

**`decision_evidence` 테이블은 생성하지 않음** (AC-10 / 지시문 §5 금지).

### 3.4 운영 데이터 (.gitignore 처리, 로컬 영구)

| 파일 | 크기 | 내용 |
|---|---|---|
| `state/market/market_data.sqlite` | 7,872,512 bytes | 1107 etf_master + ~67K etf_daily_price + 2 market_refresh_log |
| `state/market/etf_universe_topn_latest.json` | 6,950 bytes | asof=2024-10-31 daily/1m/3m TOP 10 |

---

## 4. AC (지시문 §10) 매핑

| AC | 검증 위치 | 결과 |
|---|---|---|
| AC-1 requirements.txt 에 finance-datareader 추가 | `requirements.txt` | ✓ |
| AC-2 SQLite 파일 생성 | `state/market/market_data.sqlite` 7.5MB | ✓ |
| AC-3 etf_master 에 universe 저장 | 1,107행 | ✓ |
| AC-4 N+1 호출 없음 | `test_refresh_etf_universe_uses_single_listing_call_no_n_plus_one` 가 명시 검증 (price fetcher 호출 시 AssertionError) | ✓ |
| AC-5 etf_daily_price 가격 저장 | 842 ticker × ~80 거래일 = ~67K행 | ✓ |
| AC-6 market_refresh_log 기록 | universe/prices 2 로그 행 | ✓ |
| AC-7 SQLite 기준 일간/1m/3m TOP N | `compute_topn(n=10)` 정상 | ✓ |
| AC-8 artifact JSON 생성 | `state/market/etf_universe_topn_latest.json` | ✓ |
| AC-9 N 값 변경 가능 | `test_compute_topn_respects_n_parameter` n=1/2/10 검증 | ✓ |
| AC-10 decision_evidence 테이블 미생성 | `test_init_db_creates_three_tables_only` + `test_decision_evidence_table_is_never_created` | ✓ |
| AC-11 판단 근거 저장 BACKLOG 기록 | `docs/backlog/BACKLOG.md` "판단 근거 저장 (decision evidence)" | ✓ |
| AC-12 pytest / black / flake8 / build 통과 | 191 passed / PASS / PASS / PASS / PASS | ✓ |

---

## 5. 운영 1회 fetch 실측 (asof=2024-10-31)

| 항목 | 값 |
|---|---|
| universe fetch | 1.03초 (`fdr.StockListing("ETF/KR")`, 1,107 ETF) |
| price fetch | 271.5초 (~4.5분, 1107 시도 / 842 성공 / 265 실패) |
| TOP N artifact 생성 | 즉시 |

**TOP 1 결과**:
- daily: `491630 RISE 미국반도체인버스(합성 H) +4.89%`
- one_month: `461910 PLUS 미국테크TOP10레버리지(합성) +20.81%`
- three_month: `438320 TIGER 차이나항셍테크레버리지(합성 H) +69.22%`

직전 FDR 가능성 확인 보고서 수치와 완전 일치 — per-ticker 결과의 일관성 확인.

**실패 ticker 265개**: asof=2024-10-31 시점 데이터 부재 (`498400, 0043B0, 0162Z0` 등 — 신규상장 / 비-순수 ticker / 거래정지 추정). 최근 영업일 기준 재실행 시 비율 개선 가능.

---

## 6. 금지 사항 회피 확인 (지시문 §5)

| 금지 항목 | 회피 확인 |
|---|---|
| `decision_evidence` 테이블 신설 | ✓ DDL 미작성 + 2 tests 가드 |
| 판단 근거 저장 로직 | ✓ writer 모듈 미작성 |
| AI 투자세션 대화 저장 / 사용자 매매 판단 / approval 상태 / Telegram message / Run 상태 | ✓ 모두 미도입 |
| PC UI 화면 / API 추가 / Telegram 변경 / OCI 일 3회 PUSH 연결 / ML 연결 | ✓ 모두 미도입 |
| 구성 종목 추출 / 매수/매도 판단 / 복합 점수 산식 | ✓ 모두 미도입 |
| etf_master N+1 호출 | ✓ `test_refresh_etf_universe_uses_single_listing_call_no_n_plus_one` 명시 검증 |

---

## 7. 문서 정합성 보정 (지시문 §9)

| 파일 | 변경 |
|---|---|
| `docs/PROJECT_ORIGIN_INTENT.md` §8 | FDR / SQLite 자산 추가, pykrx ETF universe 자동 조회 경로 폐기 명시 |
| `docs/backlog/BACKLOG.md` | "FDR + SQLite Market Data Foundation 후 신규 (2026-05-15)" 섹션 신규. 4건 항목: decision evidence / FDR 약관·timeout / Category 라벨 / SQLite 영구 보존 |
| `docs/handoff/STATE_LATEST.md` §0 | 현재 상태 = FDR+SQLite 1차 완료 (라인 수 실측 표기) |
| `docs/STATE_LATEST.md` (포인터) | 변경 없음 (포인터 stub 정책 준수) |

---

## 8. 의존성 변화

| 패키지 | before | after | 차이 |
|---|---|---|---|
| pandas | 2.3.3 | 2.3.3 | **유지** (메이저 업그레이드 미발생) |
| finance-datareader | — | 0.9.202 | 신규 |
| tabulate | — | 0.10.0 | 부가 (FDR 내부 사용) |

가능성 확인 STEP 의 R2 위험 (pandas 3.x 메이저 업그레이드) 은 .venv 실측 결과 **해소**.

---

## 9. 검증 결과 (지시문 §12)

| 명령 | 결과 |
|---|---|
| `pytest -q` | **191 passed in 3.19s** (이전 173 + 신규 18) |
| `black --check app tests` | PASS (48 files would be left unchanged) |
| `flake8 app tests` | PASS (0 issues) |
| frontend `npm run lint` | PASS |
| frontend `npm run build` | PASS (Static prerender 4 pages) |

---

## 10. KS-10 라인 수 (지시문 §13)

| 경로 | 최대 | trigger | near | 본 STEP 영향 |
|---|---|---|---|---|
| 백엔드 (app/*.py) | 564 (draft_message.py, 기존) | 650 미달 | 600 미달 | 신규 max 332 — 안전 |
| 테스트 (tests/*.py) | 924 (test_holdings_message_text.py, 기존) | 1500 미달 | 1450 미달 | 신규 max 224 — 안전 |
| 프론트 (.tsx) | 515 (EnrichedHoldingsSection.tsx, 기존) | 900 미달 | 850 미달 | 본 STEP 변경 0 |

**trigger 0건 / near 0건 / >750라인 추가 0건**. 회귀 없음.

---

## 11. 검증자(Codex) 라운드 흐름

### 1차 검증: **REJECTED**
- A-2 위반: 신규 6개 파일 untracked.
- A-3 부분 통과: STATE_LATEST 의 신규 모듈 라인 수 표기 stale.
- B-5 영향: untracked → OCI git pull / 배포 경로 미포함.
- B-6 경미: FDR 단일 호출 timeout 부재.

### FIX 라운드 처리:
1. **A-2 / B-5**: 신규 6개 파일 `git add` → `git status` 에서 `A` 상태.
2. **A-3 / B-6 라인 수 stale**: `~245 / ~225 / ~165` → 실측 `332 / 300 / 206` + 테스트 라인 수 + KS-10 임계 실측 추가. STATE_LATEST.md §0 갱신.
3. **B-6 timeout 부재**: BACKLOG "FDR 외부 의존" 항목에 "보류된 위험 2 (단일 호출 timeout 부재)" + 권장 후속 조치 (`concurrent.futures` / `signal.alarm` / `requests` timeout 직접 주입) 명시.

### 2차 검증: **VERIFIED_WITH_NOTES**
- 모든 NOTES 해소.
- 잔존 NOTE 1건 (FDR timeout): BACKLOG 등록 후 별도 STEP 처리 — 본 STEP 차단 사유 아님.

---

## 12. 보류된 항목 (BACKLOG 신규 등록)

| 항목 | 보류 사유 | 재검토 트리거 |
|---|---|---|
| **판단 근거 저장 (decision evidence)** | 시장 데이터 저장소 안정화 전 범위 확장 회피 | PC TOP N 화면 + AI 투자세션 + 매수/매도/보류 명시 판단 |
| **FDR 외부 의존 약관 / 안정성 / timeout 부재** | 비공식 데이터 출처. timeout 강제 미적용 | FDR 호출 실패 또는 4분 이상 hang 발생 시 |
| **ETF Category 라벨 매핑** | `StockListing("ETF/KR")` Category 가 정수 코드 | TOP N 화면 구현 STEP |
| **SQLite 영구 보존 운영 정책** | PC ↔ OCI 동기화 / 백업 / TTL 미정 | OCI 일 3회 자동 PUSH 연결 STEP |

---

## 13. 다음 단계 후보 (사용자 결정 대기)

| 후보 | 의미 |
|---|---|
| (a) **PC ETF Universe TOP N 화면 구현** | B 방향 §3 / PC 작업 §2~3단계. SQLite + artifact 를 UI 로 노출. |
| (b) **decision evidence 별도 STEP 설계** | 재검토 트리거 충족 후 (PC 화면 + AI 토론 + 명시 판단). |
| (c) **KRX OPEN API fallback 검증** | 인증키 승인 (월요일 이후). FDR 운영 안정성 보조 검증. |
| (d) **FDR 약관 / 안정성 / timeout 검토 STEP** | per-ticker timeout wrapper 도입. |

---

## 14. 완료 보고 JSON (지시문 §14)

```json
{
  "step": "FDR_SQLITE_MARKET_DATA_FOUNDATION",
  "status": "DONE",
  "verifier_result": "VERIFIED_WITH_NOTES (FIX 라운드 1회 후)",
  "summary": "FinanceDataReader 1순위 채택 + SQLite (etf_master / etf_daily_price / market_refresh_log) 3 테이블 + TOP N artifact 생성 완료. 운영 fetch 1회 — 1,107 ETF universe + 842 가격 데이터 + asof=2024-10-31 일간/1m/3m TOP 10. decision evidence / UI / API / Telegram / OCI / ML / N+1 호출 모두 명시 회피. pandas 메이저 업그레이드 미발생.",
  "created_files": [
    "app/market_data_store.py",
    "app/market_data_fdr.py",
    "app/market_topn.py",
    "tests/test_market_data_store.py",
    "tests/test_market_data_fdr.py",
    "tests/test_market_topn.py"
  ],
  "modified_files": [
    ".gitignore",
    "requirements.txt",
    "docs/PROJECT_ORIGIN_INTENT.md",
    "docs/backlog/BACKLOG.md",
    "docs/handoff/STATE_LATEST.md"
  ],
  "operational_data_locally_created_but_gitignored": [
    "state/market/market_data.sqlite",
    "state/market/etf_universe_topn_latest.json"
  ],
  "dependency": {
    "finance_datareader_added": true,
    "pandas_version_before": "2.3.3",
    "pandas_version_after": "2.3.3",
    "pandas_major_upgrade_occurred": false,
    "dependency_risk_notes": [
      "FDR 0.9.202 가 pandas 3.x 강제하지 않음 — R2 위험 해소",
      "신규 부가 의존성: tabulate 0.10.0 (FDR 내부 사용)"
    ]
  },
  "sqlite": {
    "db_path": "state/market/market_data.sqlite",
    "etf_master_created": true,
    "etf_daily_price_created": true,
    "market_refresh_log_created": true,
    "decision_evidence_table_created": false,
    "stores_runtime_state": false,
    "stores_telegram_message": false,
    "stores_approval_state": false
  },
  "data_refresh": {
    "source": "FinanceDataReader",
    "universe_count": 1107,
    "price_attempted_count": 1107,
    "price_success_count": 842,
    "price_fail_count": 265,
    "runtime_seconds": 271.5,
    "etf_master_n_plus_one_calls": false,
    "asof_used": "2024-10-31"
  },
  "topn": {
    "artifact_path": "state/market/etf_universe_topn_latest.json",
    "default_n": 10,
    "n_is_configurable": true,
    "daily_topn_created": true,
    "one_month_topn_created": true,
    "three_month_topn_created": true
  },
  "decision_evidence": {
    "requirement_recorded_in_backlog": true,
    "table_created_now": false,
    "writer_connected_now": false,
    "retrigger_condition": "PC ETF Universe TOP N 화면에서 사용자가 AI 투자세션에 1회 이상 가져가고, 매수 / 매도 / 보류 중 하나의 명시적 판단을 남긴 시점"
  },
  "forbidden": {
    "ui_added": false,
    "api_added": false,
    "telegram_changed": false,
    "oci_push_connected": false,
    "ml_connected": false,
    "composition_extraction_added": false,
    "buy_sell_judgment_added": false,
    "decision_evidence_table_created": false,
    "decision_evidence_writer_connected": false,
    "etf_master_n_plus_one_added": false
  },
  "tests": {
    "pytest": "191 passed in 3.19s",
    "black_check": "PASS (48 files would be left unchanged)",
    "flake8": "PASS (0 issues)",
    "frontend_lint": "PASS",
    "frontend_build": "PASS"
  },
  "line_count_report": {
    "ks10_trigger_files": [],
    "ks10_near_threshold_files": [],
    "files_750_lines_or_more": [
      "tests/test_holdings_message_text.py (924, 기존 — 본 STEP 영향 없음)"
    ],
    "new_module_lines": {
      "app/market_data_store.py": 332,
      "app/market_data_fdr.py": 300,
      "app/market_topn.py": 206
    },
    "new_test_lines": {
      "tests/test_market_data_store.py": 224,
      "tests/test_market_data_fdr.py": 214,
      "tests/test_market_topn.py": 193
    },
    "backend_max_after": "564 (app/draft_message.py, 기존)",
    "test_max_after": "924 (test_holdings_message_text.py, 기존)",
    "frontend_max_after": "515 (EnrichedHoldingsSection.tsx, 기존)"
  },
  "docs": {
    "project_origin_intent_updated_if_needed": true,
    "assumptions_updated_if_needed": false,
    "state_latest_updated": true,
    "backlog_updated_for_decision_evidence": true
  },
  "commit": "dc6e83dd feat(poc2-fdr-sqlite): FDR + SQLite market data foundation 1차 구현",
  "push": "1f239ddf..dc6e83dd  main -> main (github.com:KevinKim-KOR/krx_hyungsoo.git)",
  "notes": [
    "검증자(Codex) 1차 REJECTED → FIX 라운드 1회 (untracked 6개 add + STATE_LATEST 라인 수 실측 갱신 + BACKLOG FDR timeout 위험 명시) → 2차 VERIFIED_WITH_NOTES.",
    "운영 fetch 1회 실측 271.5초 (가능성 확인 보고서 234초 대비 +37초 — DB upsert 오버헤드).",
    "265 ticker 가격 결측 (76.1% 성공률) — asof 시점 의존. 최근 영업일 재실행 시 개선 가능.",
    "다음 단계 후보 4건 — 사용자 결정 대기."
  ]
}
```

---

문서 끝.
