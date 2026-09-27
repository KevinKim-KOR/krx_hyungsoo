# POC3-02D-OPS-01 개발 결과서 — PRE_PRIMARY_OPERATIONAL_CORRECTIONS

작성일: 2026-09-27 · 작성자: 개발자(VSCode Claude) · 수신: 설계자 → 검증자

```text
STEP_ID                   = POC3-02D-OPS-01
STEP_NAME                 = PRE_PRIMARY_OPERATIONAL_CORRECTIONS
PREDECESSOR / SUCCESSOR   = POC5-00 / POC3-02D-OPS-02 (설계자 RESULT 판정 · 그 뒤 POC5-01A)
PLAN                      = CONFIRMED (설계자 PASS_WITH_MANDATORY_AMENDMENT_R2 · Q1~Q27)
IMPLEMENTATION            = C1~C7 DONE (저장소 코드 · 미커밋)
RED_ON_BASE_CODE          = C2~C7 47건 실패 · C1 수집 오류 2파일 + 판정 대조 1건 (§1-3)
BACKEND_FULL_REGRESSION   = 2,347 passed / 0 failed / 0 errors (exit 0 · 338s · render.py 주석 반영 뒤 재실행)
BLACK / FLAKE8 / COMPILE  = 변경 · 신규 Python 28파일 전부 통과
MOCKUPS_08:00             = ①~⑦ 7건 작업 기준 코드와 byte 동일
MANIFEST_02B-1            = 7 입력 sha256 전부 일치 (manifest 섹션만 실행)
CHECK_SCRIPT_LIVE         = exit 0 · resolver 선택 krx_etf_basic_20260927.csv
PC_LIVE_STATE             = 221 파일 sha256 불변 + 새 CSV 1개 추가 (STEP 1 대비)
PC_PUSH_AUTOSEND_*        = 4줄 모두 false
OCI                       = HEAD 8bf843e6 · 추적 파일 변경 0 · 마지막 pull 2026-09-26 15:22 (이 단계 전)
KS10_TRIGGER              = 0 (러너 646줄 · 변경 0)
DESIGNER_RESULT_DECISION  = PASS_TO_VERIFIER (설계자 2026-09-27 · 원문은 설계서 끝)
VERIFIER                  = VERIFIED (2026-09-27 · 읽기 전용 정적 검증 · C1~C7 한정 · 위험 MEDIUM = 알려진 기존 위험(Q8 · OPS-02) · 범위 폭주 NONE)
COMMIT_PUSH_OCI           = 커밋(검증자 VERIFIED · STATE_LATEST 1차 갱신 뒤 · 이 문서 포함) · push 별도 승인 대기 · OCI pull 대기
FOLLOW_UP                 = POC3-02D-OPS-02 — OCI 상세 링크 · Q8 인접 상태 저장 결함 · 낡은 역검증 ⑦ · 목업 ⑦ 제목 정리(설계자 결정 · PRIMARY 전) · 후보: KOSPI stale 화면 문구(Q19 · 2026-09-26 PLAN 판정 · 포함 여부는 OPS-02 PLAN 때 판정)
PRIMARY_COHORT            = NOT_STARTED (OPS-02 뒤 POC5-01A)
```

입력 문서

- 설계서: `docs/ai_design/POC3/POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_DESIGN_V1.md` (R1 · R2 · RESULT 판정 원문 포함)
- PLAN: `docs/ai_plan/POC3/POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_PLAN_V1.md`
- 작업 기준 코드: 커밋 `3b6e3257`(작업 시작 시점). OCI 는 `8bf843e6` 이고 둘 사이는 문서 3개뿐이다(PLAN §2).

**사실 성격 표기**(설계자 번호 지시): 실제 발생 = 운영 기록으로 실측된 결함 · 발생 추정 = 코드와 기록으로는 확실하지만 사용자 화면 · 원문 미확인 · 잠재 = 결함 경로는 확인됐지만 운영 발생 0건.

---

## 0. 한눈에

| 정정 | 내용 | 사실 성격 | 바뀐 것 | 작업 기준 코드에서의 결함 재현(RED) |
|---|---|---|---|---|
| C1 | 08:00 기초지수 구역 복구 | 실제 발생 | 공용 resolver · pending gate · `refresh_due` · 판정 창 검사 · 08:00 안내 1줄 · 새 CSV `20260927` | 같은 입력에서 `CSV_REFRESH_REQUIRED` → 이제 `ok` + pending 1건 (§1-3) |
| C2 | 폐지 spike 필수 판정 | 발생 추정 | 필수 목록 = 운영 3종 | 지금 cron 모양에서 `DEGRADED` → 이제 `OPERATING` |
| C3 | 장중 본문 `현재가 —` | 실제 발생(사용자 원문 2026-09-27 확인) | '기준' 다음 줄에 실행 시각 | run() 관통에서 `현재가 — · 직전 종가 2026-08-25` |
| C4 | 잘린 보유 급락의 잘못된 억제 | 잠재 | 저장 대상을 본문 기준으로 재계산 | '잘린 급락이 발송 완료로 저장됐다' |
| C5 | Telegram 실패 집계 | 잠재 | `send_failed` · '발송 실패 N회' · 성공도 최종 status | 전송 실패 회차가 `no_signal` 로 집계 |
| C6 | `message_text_length=0` | 실제 발생(기록 결함) | 조립 본문 길이 기록 | 발송 행 길이 0 (본문 114자 · 115자) |
| C7 | KOSPI 09-17 정지 | 실제 발생 | `failed + source_stale:` · 공용 lag helper | 멈춘 KOSPI 를 `ok` 로 기록 |

C3 은 PLAN 에서 '발생 추정'이었다. 사용자가 실수신 원문(`현재가 ㅡ. 직전 종가 2026-09-22` · 손으로 옮김)을 전달해 실제 발생으로 확인됐다.

---

## 1. 처리한 요구사항

### 1-1. STEP 별

| STEP | 판정 | 비고 |
|---|---|---|
| STEP 1 사실 기준선 | DONE | PC `state/`(`state/ml/research` 제외) 221파일 sha256 · `git status` 기록. OCI 기준값 읽기(2026-09-26). 사용자 입력 3건 수신: C3 원문 · C1 CSV 원본 · upstream 커밋 시각 |
| STEP 2 C1~C7 구현 | DONE | 아래 1-2 |
| STEP 3 집중 · 전체 회귀 | DONE | §1-4 |
| STEP 4 운영 상태 불변 | DONE | §1-5 |
| STEP 5 결과서 · 판정 | DONE | 이 문서. 설계자 `PASS_TO_VERIFIER` → 검증자 `VERIFIED`(2026-09-27 · 읽기 전용 정적 검증 · C1~C7 한정 — OCI 적용 · PRIMARY 승인 아님) |
| STEP 6 commit · push | PARTIAL | 커밋 수행(설계자 진행 순서 3 · 이 결과서 포함 — 커밋 내역은 `git log` 로 본다). push 는 별도 승인 대기 |
| STEP 7 OCI 적용 · 사후 실측 | SKIPPED | 같은 이유. pull 직전 대조 절차는 §5 |

### 1-2. 정정 항목

| 요구사항 | 판정 | 근거(코드 · 테스트) |
|---|---|---|
| C1 공용 resolver(Q1 · Q2 · Q25) | DONE | `app/market_briefing/official_csv.py :: resolve_official_csv` 를 07:20(`krx_sync`) · 08:00(`runner_market_briefing`)이 같이 부른다. 파일명 상수 `OFFICIAL_ETF_CSV` 제거. 테스트 `test_0720_and_0800_share_one_resolver` · `test_resolver_*` 6건 |
| C1 pending gate(Q1 (c)) | DONE | `meta_gate.evaluate_consistency` 가 d20 종가 없는 API 전용을 `api_only_pending` 으로 기록. 테스트 `test_api_only_*` · `test_sync_*pending*` · `test_pending_ticker_has_zero_numeric_impact` |
| C1 `refresh_due`(Q23) | DONE | `meta_gate.apply_refresh_due` · `carry_refresh_due`. 경계 6 · 5 · 0 · `CSV_REFRESH_REQUIRED` 단독 · 주기 유지 · 새 주기 · 해제 테스트 |
| C1 08:00 안내 1줄(Q24) | DONE | `render.CSV_REFRESH_NOTICE` · `flow._refresh_notice_cycle` · 전체 발송 성공 뒤 `refresh_notice_cycle_id` 저장. 테스트 `test_refresh_notice_*` 4건 |
| C1 판정 창 검사(Q27) | DONE | `meta_gate.verdict_stale_reason` · `flow._verdict_stale`. 테스트 `test_stale_*` 3건 · `test_verdict_window_check_normalizes_dates_and_fails_closed` |
| C1 `20260909` 고정(Q3) | DONE | 장중 생성기 · 02B-1 재현 · ops02c 역검증은 변경 0. 테스트 `test_fixed_20260909_consumers_do_not_use_resolver` |
| C1 검증 스크립트 | DONE | `scripts/check_krx_etf_basic_csv.py`(PC 전용 · 외부 호출 0). 테스트 `test_check_script_exit_codes` |
| C1 새 CSV 반영 | DONE | `state/market_meta/krx_etf_basic_20260927.csv` · 원본과 SHA-256 동일(§1-6) |
| C2 필수 목록 교체(Q14) | DONE | `app/oci_startup_status.py :: _REQUIRED_PUSH_KINDS` = `market_briefing` · `holdings_briefing` · `holdings_risk_alert`. 문구 · API · 프론트 변경 0 |
| C3 실행 시각(Q9 (a)) | DONE | `holdings_risk_flow.py` 인자 1줄 `quote_asof=format_quote_asof(runtime_kst)`. 사용자 원문 확인 뒤 수정 |
| C4 저장 대상 재계산(Q6 · Q7) | DONE | `holdings_risk_flow.py` — `out.intraday` 대입 **전** 지역 변수로 계산 · 본문 대체 분기에서 `outcome.save_entries` 에 대입. `merge_worst` 변경 0 |
| C4 인접 결함 2개 tmp 재현(Q8) | DONE | §8. 고치지 않았다 |
| C5 `send_failed`(Q11~Q13) | DONE | `intraday_checkup_tally.OUTCOME_SEND_FAILED` · `intraday_alert_render.render_checkup_summary(send_failed=)` · `apply_intraday_records` 최종 status 확정 |
| C6 길이 기록 | DONE | `assemble_holdings_risk_push` 끝 `diagnostics["message_text_length"]` |
| C7 감지 정정 A(Q17 · Q26) | DONE | `market_benchmark_store.refresh_kospi_benchmark` · 공용 `app/trading_day_lag.py`. `market_benchmark_batch.py` 변경 0 |
| C7 source 교체 · 날짜 밀어 넣기 금지 | DONE(0건) | 외부 호출 0 |
| 문서: PROGRAM_TRUTH(Q15 · PLAN §9) | DONE | §2 파일 목록 |
| 문서: 옛 crontab 문서 SUPERSEDED(Q15) | DONE | 머리 1줄 |
| 문서: STATE_LATEST | DONE(1차) · PARTIAL | 1차: 검증자 `VERIFIED` 뒤 · 커밋 전 갱신 완료(설계자 진행 순서 3). 2차: STEP 7 사후 실측 뒤 다시 갱신한다(PLAN §9) |
| 문서: POC5 원장 문서(`send_failed` · 길이 0 = 미기록) | SKIPPED | PLAN §9 — POC5-01 PLAN 때 |

### 1-3. 결함 재현(RED) — 작업 기준 코드 `3b6e3257`

같은 실행에서 만들었다. `git archive 3b6e3257` 로 뽑은 사본에 이번 테스트 파일만 넣어 돌렸다(저장소 · git 메타데이터 변경 0).

**C2~C7** — 테스트 4파일 · 99건 중 **47 failed · 52 passed**. 52건은 회귀 고정용(정책 비활성 · 일일 상한 · 렌더 기본값 등)이라 기준 코드에서도 통과가 맞다. 실패 사유(대표):

| 정정 | 기준 코드 실패 사유 (pytest `--tb=line` 원문) |
|---|---|
| C2 | `assert 'DEGRADED' == 'OPERATING'`(지금 cron 모양) · `assert 'OPERATING' == 'DEGRADED'`(옛 cron — `holdings_risk_alert` 누락 미감지) |
| C3 | `AssertionError: 현재가 — · 직전 종가 2026-08-25` |
| C4 | `잘린 급락이 발송 완료로 저장됐다` · `잘린 급락이 억제됐다: no_new_or_worsened` · `잘린 악화가 worst 로 기록됐다` |
| C5 | `assert 'no_signal' == 'send_failed'`(전송 실패 · 부분 전송 · 금지 문구 · raw 식별자 · registry 손상) · 새 필드 · 인자 없음(`AttributeError` · `TypeError`) |
| C6 | `assert (114 > 0 and 0 == 114)` · `assert (115 > 0 and 0 == 115)` |
| C7 | `멈춘 KOSPI 를 ok 로 숨겼다`(배치 관통) · `assert 'ok' == 'failed'`(마지막 종가 NaN) · 새 인자 `calendar_dir` 없음(`TypeError`) · 공용 모듈 없음(`ImportError`) |

**C1** — 테스트 3파일은 새 모듈 `official_csv` 가 없어 수집 오류(`ImportError` 2파일)다. 동작 재현은 같은 입력(공통 1,000종 + API 전용 신규 1종 · 기초지수명 동일)으로 판정 함수를 직접 대조했다.

```text
[기준 코드]  status= CSV_REFRESH_REQUIRED api_only= ['NEW01'] pending= (필드 없음)
[작업 트리]  status= ok api_only= ['NEW01'] pending= [{'ticker': 'NEW01', 'first_loaded': '2026-09-22', 'stored_trading_day_count': 3, 'remaining_trading_days': 18}]
```

### 1-4. STEP 3 검증 실측

| 항목 | 결과 |
|---|---|
| `black --check` · `flake8` · `py_compile` | 변경 · 신규 Python 28파일 — `28 files would be left unchanged` · flake8 출력 0 · compile ok |
| 전체 pytest | `2347 passed, 1 warning in 337.62s` · exit 0 (새 CSV · 마지막 코드 변경인 `render.py` 주석 반영 뒤 · 라이브 DB 사본 sha256 세션 전후 같음) |
| 08:00 목업 7건 | `scripts/build_market_briefing_mockups.py --md <tmp>` — 기준 코드 출력과 diff 0(①~⑦ 발송 여부 · 사유 · 글자 수 · 지수 상태 · 본문) |
| 02B-1 MANIFEST | `reproduce.py manifest` — 7 입력 sha256 전부 '일치' · exit 0. 통계 섹션은 실행하지 않았다 |
| C1 검증 스크립트(라이브 폴더) | `--meta-dir state/market_meta` → `resolver 선택: krx_etf_basic_20260927.csv · csv_asof=2026-09-27 · 행 1175` · `결과: 통과` · exit 0 |
| 본문 byte 동일 | C4 통합 본문 · 안내가 없을 때 08:00 본문 · `send_failed=0` 인 15:40 줄 · 목업 7건 |
| 역검증 `scripts/ops02b2/reverse_verify_guards.py` | ①~⑥ · ⑧~⑩ OK · ⑦ `!!` · exit 1. **기준 코드에서도 출력이 같다**(diff 0 · §6) |

테스트 수(함수 정의 `def test_` · 기준 → 지금): 새 파일 `test_poc3_02d_ops01_holdings_risk_flow.py` 0 → 33(수집 44) · contracts 68 → 88 · batch 23 → 38 · flow_through 10 → 21 · startup_status 8 → 12 · benchmark_store 6 → 16 · benchmark_freshness 24 → 27 · topn_api 21 → 22.

### 1-5. STEP 4 운영 상태 불변

| 항목 | 결과 |
|---|---|
| PC `state/` sha256 (STEP 1 과 같은 명령) | 222행. STEP 1 대비 diff 는 추가 1행 `0f0c0742…22314  state/market_meta/krx_etf_basic_20260927.csv` 뿐 — 나머지 221파일 불변 |
| PC `.env` `PUSH_AUTOSEND_*` | 4줄 모두 `false`(값 외 출력 안 함) |
| 실발송 · 외부 호출 | 0. 테스트는 tmp 경로 · tmp DB · stub. 이번에 **추가한** 테스트는 라이브 DB 허용 목록(`tests/_live_db_legacy_readers.txt`)에 없어 라이브 DB 를 열면 가드가 실패시킨다 — 전체 통과. 변경 파일 중 `test_runtime_runner_dry_run.py` 의 기존 2건만 목록에 있고(격리 1줄 추가), 그 2건은 세션 읽기 전용 사본만 연다. 가드 출력: 라이브 DB 2개 sha256 세션 전후 같음 |
| OCI (읽기 전용) | `git rev-parse` `8bf843e6` · 추적 파일 변경 0 · reflog 마지막 `2026-09-26 15:22:13 pull` |

### 1-6. 새 CSV 대조 (PLAN C1 '반영 전 PC 대조')

- 원본 `~/Downloads/KRX_증권상품_ETF_전종목기본정보_20260927.csv` 373,228 byte · 저장본 `state/market_meta/krx_etf_basic_20260927.csv` — `cmp` 동일 · SHA-256 `0f0c074240e66c6d7a3406861c287dc63b8137c7aa497e5db509fae9f8722314` 둘 다 같음.
- **출처 사용자 확인 완료**: 사용자가 KRX 에서 직접 다운로드한 파일이다(사용자가 2026-09-27 대화에서 확인 · 다운로드일 2026-09-27). 메뉴는 KRX Data Marketplace `증권상품 > ETF > 전종목 기본정보`(파일명 · 설계자 판정 표와 같음).
- **설계자 원본 대조**(RESULT 판정 2026-09-27): 373,228 bytes · SHA-256 · CP949 · 17열 · 데이터 1,175행 · 신규 8종 모두 존재 · 누락 0 — 위 개발자 대조와 같다.
- **날짜의 뜻**: 추석 연휴 중 받은 파일이라 파일명 날짜 `20260927`(= `csv_asof`)은 **다운로드 · 스냅샷 날짜**이고 거래 기준일이 아니다. ETF 기본정보는 종가가 아니므로 휴장일에 받아도 된다. 코드도 이 날짜를 거래일 · 최신성 판단에 쓰지 않는다. 쓰는 곳은 기록(07:20 판정 JSON `csv_asof_date` · 08:00 실행 기록의 `official_csv`), 검증 스크립트 출력, CSV 파일끼리의 선택(날짜 파싱 `date_parse` · 동일 날짜 묶음 `duplicate_date` · 최신 순)이다.
- 내용 검사 통과 · 1,175행. `--compare` 대 `20260909`: 추가 8(`0227L0` · `0238C0` · `0238F0` · `0239Y0` · `0239Z0` · `0240J0` · `0241R0` · `0242S0`) · 삭제 1(`465780`) · 기초지수명 변경 0.
- OCI 정합성 JSON(2026-09-27 읽기 · 판정 `evaluated_at 2026-09-24T22:20:12Z` · `api_basis_date 20260922` · `CSV_REFRESH_REQUIRED`)의 `api_only` 8종 → 새 CSV 에 **모두 있음**(누락 0). 기초지수명 불일치 0.

---

## 2. 변경된 파일 목록

`git status --short --untracked-files=all` 기준(보고 직전 실측 출력은 §10). 사용자 소유 `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`(untracked)는 건드리지 않았고 staged 대상이 아니다.

**운영 코드**

| 파일 | 구분 | 정정 |
|---|---|---|
| `app/market_briefing/official_csv.py` | 신규 | C1 resolver |
| `app/trading_day_lag.py` | 신규 | C7 공용 거래일-lag helper |
| `app/market_briefing/meta_gate.py` | 수정 | C1 pending · `refresh_due` · 판정 창 · 기록 필드 |
| `app/market_briefing/krx_sync.py` | 수정 | C1 resolver 호출 · pending 입력 · `evaluated_*` 기록 |
| `app/market_briefing/krx_store.py` | 수정 | C1 첫 적재일 · 적재 거래일 수 조회 |
| `app/market_briefing/flow.py` | 수정 | C1 판정 창 검사 · 안내 줄 · C7 helper 본체 이전(같은 이름 유지) |
| `app/market_briefing/render.py` | 수정 | C1 안내 문구 · `META_GATE_STALE` 안내 |
| `app/three_push_runtime/runner_market_briefing.py` | 수정 | C1 resolver 폴더 · 안내 주기 저장 |
| `scripts/run_oci_market_data_batch.py` | 수정 | C1 resolver 폴더 · `refresh_due` 기록 · 로그 |
| `app/oci_startup_status.py` | 수정 | C2 |
| `app/runtime_evidence/holdings_risk_flow.py` | 수정 | C3 · C4 · C5 · C6 |
| `app/runtime_evidence/intraday_checkup_tally.py` | 수정 | C5 |
| `app/runtime_evidence/intraday_alert_render.py` | 수정 | C5 |
| `app/market_benchmark_store.py` | 수정 | C7 |

**데이터 · 스크립트**

| 파일 | 구분 | 비고 |
|---|---|---|
| `state/market_meta/krx_etf_basic_20260927.csv` | 신규 | C1 공식 CSV(git 추적 폴더 · OCI 로 pull 된다) |
| `scripts/check_krx_etf_basic_csv.py` | 신규 | C1 검증 스크립트 |
| `scripts/build_market_briefing_mockups.py` | 수정 | Q27 필드 채움 · ⑥ 적재 5거래일 시드 |
| `scripts/ops02b2/reverse_verify_guards.py` | 수정 | fixture 에 Q27 필드 |

**테스트**

| 파일 | 구분 |
|---|---|
| `tests/test_poc3_02d_ops01_holdings_risk_flow.py` | 신규(Q22 승인) — C3 · C4 · C5 · C6 |
| `tests/test_market_briefing_contracts.py` · `test_market_briefing_batch.py` · `test_market_briefing_flow_through.py` | 수정 — C1 |
| `tests/test_oci_startup_status.py` | 수정 — C2 |
| `tests/test_market_benchmark_store.py` · `test_market_benchmark_freshness.py` · `test_market_topn_api.py` | 수정 — C7 |
| `tests/conftest.py` · `test_market_refresh_state_persistence.py` · `test_runtime_runner_dry_run.py` | 수정 — 격리(§4) |

**문서**

| 파일 | 구분 |
|---|---|
| `docs/ai_design/POC3/POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_DESIGN_V1.md` | 신규 — 설계자 R1 · R2 · RESULT 판정 원문 · 사용자 입력 |
| `docs/ai_plan/POC3/POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_PLAN_V1.md` | 신규 — 확정 PLAN |
| `docs/ai_result/POC3/POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_RESULT.md` | 신규 — 이 문서 |
| `docs/ai_design/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_DESIGN_V1.md` · `docs/ai_plan/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_PLAN_V1.md` | 수정 — 설계자 보완 판정(C1~C7 분류) 기록 |
| `docs/PROGRAM_TRUTH.md` | 수정 — 머리글 · §4 · §5.2 · §7.2 · §8 · §9 C-3(신규) · 장중 급등락 절 · §9-D · §11 · §13-4 · §13 뒤 'UNKNOWN / 별도 확인' 블록 · 부록 A |
| `docs/handoff/OCI_LOW_FREQUENCY_TELEGRAM_PUSH_OPERATION_V1_CRONTAB.md` | 수정 — SUPERSEDED 1줄 |
| `docs/STATE_LATEST.md` | 수정 — 검증자 `VERIFIED` 뒤 1차 갱신(POC3 Step 표 · 다음 순서 · PRIMARY 조건) |

---

## 3. 신규 추가된 의존성

없음.

---

## 4. 지시문 외 변경

- **테스트 격리 4파일**: resolver 와 KOSPI 판정 축이 저장소 `state/market_meta` 를 읽게 되면서, 경로를 넘기지 않던 기존 테스트가 실제 CSV · 캘린더를 읽지 않게 했다. 운영 코드 변경이 아니다.
  - `tests/conftest.py`: 08:00 러너 · 07:20 배치의 `MARKET_META_DIR` 을 격리 폴더로.
  - `test_runtime_runner_dry_run.py`: 캘린더 폴더(`calendar.CALENDAR_DIR`)를 빈 tmp 로.
  - `test_market_refresh_state_persistence.py` · `test_market_topn_api.py`(`_isolate_market_meta`): 캘린더 폴더를 빈 tmp 로 + 갱신 성공 뒤 장중 설정 재산출(`market_refresh_service._regenerate_intraday_config`)을 no-op 로. 재산출은 고정 CSV `20260909` 를 읽는 이 테스트들의 대상 밖 뒷단이다.
- **목업 · 역검증 fixture**: Q27 로 판정 창 필드가 없으면 `META_GATE_STALE` 이 되므로 두 스크립트의 가짜 판정에 `evaluated_*` 를 채웠다. 목업 ⑥ 은 빈 DB 대신 적재 5거래일(21 미만)로 시드해 원래 결과(`stale`)를 유지했다 — 기준 코드 목업과 diff 0.
- **resolver 거부 사유 추가**: 설계 목록(날짜 파싱 · 이름 패턴 · 동일 날짜 · CP949 · 컬럼 · 단축코드 중복 · 빈 기초지수명) 외에 `read_error` · `csv_parse` · `no_rows` · `empty_ticker` 를 둔다. 모두 fail-loud 쪽이다.
- **검증 스크립트 보강**: 폴더 검사에서 ① 선택 날짜 이상인데 거부된 후보, ② resolver 후보 패턴(`krx_etf_basic_*.csv`)에 안 걸리는 비슷한 이름(대소문자 · 밑줄 누락 · `.CSV` · `.csv.txt`)을 실패(exit 1)로 본다. 새 CSV 가 조용히 안 쓰이는 경우를 드러내기 위해서다.
- **`render.py` 주석 1곳(설계자 RESULT 판정 반영)**: `META_GATE_STALE` 문구 재사용 주석의 '(설계자 확인 대상)' 을 '설계자 승인(2026-09-27) · 판정 창을 확인하지 못한 경우에만 · 정상 0개는 생략' 으로 바꿨다. 주석만 바뀌었고 동작 · 문구는 같다(`black` · `flake8` 통과 · 시장 브리핑 테스트 3파일 181 passed).
- **PROGRAM_TRUTH 위치 stale 같은 패턴 일괄 정정**: PLAN 이 지정한 §5.2 · §9-D 외에 §11 · 부록 A 의 'OCI 상태 = `diagnostics`' 도 고쳤다(2026-08-16 에 `oci_status` 로 분리됨). §11 의 `DataStatusView` '정상 메뉴 진입점 제거됨' 행은 같은 날 `data_status` 복원으로 틀린 문장이라 `oci_status` 행으로 바꿨다.

---

## 5. 알려진 한계 / 미완성

- **반영 시점**: C1 · C3~C6 과 C7 의 OCI 07:20 배치 경로는 OCI `git pull`(STEP 7) 전까지 운영에서 돌지 않는다. C2 와 C7 의 PC 수동 갱신(`POST /market/refresh`) 경로는 PC 백엔드를 이 코드로 재기동할 때 바로 바뀐다. PROGRAM_TRUTH 머리글에 같은 구분을 적었다.
- **pull 직전 대조(STEP 7)**: pull 직전에 OCI 정합성 JSON `api_only` 를 다시 읽어 새 CSV 와 대조한다. d20 종가가 있는데 새 CSV 에 없는 ticker 가 있으면 멈추고 보고한다(PLAN STEP 7).
- **평일 fallback 축**(C7 · 08:00 최신성 관문 공통 · PLAN C7): 캘린더가 실행 연도를 덮지 않으면 공휴일을 모른다. 저장소 캘린더는 2026 하나라 2027 년에는 **평일 휴장일 다음 배치마다** 정상 KOSPI 도 lag 2 로 `failed` 가 된다(첫 사례 2027-01-04 07:20 · 1월 1일 휴장 다음 · 다음 날 01-05 은 lag 0 으로 ok). 2027 캘린더 파일을 넣으면 해소된다(POC5-00 Q17 · 선행조건 아님).
- **07:20 · 08:00 사이 CSV 바뀜**(Q4): 코드 가드가 없다. 08:00 이 고른 파일의 SHA 를 07:20 판정의 SHA 와 비교하지 않는다. 운영 규칙 '07:15~08:05 pull 금지'로만 막는다.
- **08:00 에서만 CSV 가 못 쓰이는 경우**: 07:20 판정이 ok 인데 08:00 resolver 가 유효 파일을 못 찾으면 기초지수 구역은 `CSV_REFRESH_REQUIRED` 로 닫힌다. 안내 1줄은 07:20 `refresh_due` 만 보므로, 그 값이 거짓이면 붙지 않는다(참이면 붙는다). 위 pull 금지 시간대를 어겨야 생기는 경우다.
- **C2 주석 줄 필터 없음**(Q14): 주석 처리된 `--push-kind` 도 등록으로 센다. OCI 실측 주석 줄 0건.
- **C5 · flag off 회차**: 러너가 금지 문구 · raw 식별자 검사를 자동발송 flag 검사보다 먼저 한다(`scripts/run_three_push_runtime_oci.py:407-442` · 변경 0). 그래서 flag 가 꺼진 상태에서 그 검사에 걸린 회차는 `failed` 로 끝나 관측 · 집계를 쓰고, 이제 `send_failed` 로 센다(전에는 잠정값). flag-off 회차가 집계를 쓰는 것 자체는 기존 동작이다. OCI 는 flag 가 true 다.
- **C5 · `_finish` 밖 예외 종료**: 발송 뒤 상태 저장 예외 등으로 `_finish` 를 거치지 않으면 집계 틱이 남지 않는다(PLAN C5 · POC5-01 최외곽 종료 확정이 맡음).
- **C6 과거 0**: 배포 전 `holdings_risk_alert` 행의 0 은 미기록이다. 고치지 않는다(backfill 금지). POC5 원장 문서 기록은 POC5-01 PLAN 때.
- **C7 화면 문구**(Q19): 「오늘의 투자 점검」 KOSPI 머리('수익률·위치 자료 없음')는 stale 을 구분하지 않는다. 「요즘 잘 오르는 ETF」 시장 배경 카드는 'N/A — KOSPI 시계열이 수집되지 않았습니다.'(사실과 다른 사유) 아래에 영문 경고 'KOSPI benchmark is stale (…)' 을 함께 보인다(`app/market_regime.py:410-416` · 기존). PLAN C7 '영향'은 이 영문 경고 줄을 빠뜨렸다. 문구 정리는 후속 `POC3-02D-OPS-02` 후보.
- **첫 화면 OCI 한 줄 링크(기존 · 이번 확인)**: 「오늘의 투자 점검」 OCI 한 줄의 '진단·상태에서 상세 보기 →' 는 아직 「개발·실험용」(`diagnostics`)으로 간다(`frontend/app/components/today/OciStatusOneLine.tsx:58`). 2026-08-16 분리 뒤 그 화면에는 OCI 상세가 없고, 상세는 「OCI 운영 상태」에 있다. 이번 단계에는 섞지 않는다 — 후속 `POC3-02D-OPS-02` 에서 「OCI 운영 상태」로 연결한다(설계자 결정 2026-09-27).
- **C7 upsert NaN 덮어쓰기(기존)**: upstream 이 이미 저장된 날짜에 NaN 종가를 주면 upsert 가 유효 종가를 덮어쓴다. 이번 범위 밖.
- **Q8 인접 결함 2개**: 재현만 했다(§8). 후속 `POC3-02D-OPS-02` 에서 고치고, POC5-01A PRIMARY 시작 전에 끝낸다(설계자 결정 2026-09-27).
- **역검증 ⑦ · 목업 ⑦ 제목(기존)**: 현 계약(2026-09-18 부터 내용이 같아도 발송)에서 폐기 대상이다. 후속 `POC3-02D-OPS-02` 에서 정리한다(설계자 결정 2026-09-27 · §6-9).

---

## 6. 다음 검증자(Codex)에게 알릴 점

1. **C4 재계산 위치**: `out.intraday = intraday` 대입 **전**에 지역 변수로 계산하고, 본문 대체 분기(`elif intraday.will_send()`)에서만 `outcome.save_entries` 에 넣는다. `out` 은 `RiskAssembly` 라 여기에 넣으면 저장에 반영되지 않는다(PLAN C4 조건 1). 테스트는 러너가 쓴 상태 파일로 확인한다.
2. **Q27 적용 범위**: 판정 창 검사는 저장된 판정의 status 와 무관하게 먼저 한다. 판정 JSON 이 아예 없으면 기존대로 `api_fetch_failed`(`no_0720_result`)다. 창이 21일 미만이면 d20 을 `None` 으로 비교한다(07:20 도 같은 규칙으로 기록).
3. **`META_GATE_STALE` 본문 문구 — 설계자 승인(2026-09-27)**: `STATUS_API_FETCH_FAILED` 의 승인 문구 '기초지수 정보는 최신 기준을 확인하지 못해 제외했습니다.' 를 재사용한다(`render.py:62`). 승인 조건은 '현재 판정 창을 확인하지 못한 경우에만 · 후보 0개에는 쓰지 않음'이고, 코드가 이미 그렇다.
   - 이 문구가 나가는 status 는 `META_GATE_STALE`(`flow._verdict_stale` 사유 `evaluated_window_missing` · `api_basis_date_mismatch` · `window_d20_mismatch`)와 기존 `api_fetch_failed`(07:20 판정 없음 `no_0720_result` 등) 둘뿐이다(`render.INDEX_NOTICE`).
   - 정상 0개(`no_candidate_normal`)는 안내 없이 구역을 생략한다(`render.py:160-161` · 기존 테스트 `test_zero_candidate_omits_block_without_notice` 가 '제외했습니다' 부재를 고정).
4. **07:20 이 판정하지 못한 날**: `refresh_due` · 주기 id 는 직전 값을 잇고 reason 은 `not_evaluated` 다. 거짓으로 적으면 주기가 끊겨 같은 요청을 다시 알리기 때문이다. 그날 JSON 은 판정 창을 비워 저장하므로(`krx_sync._save_not_evaluated`) 08:00 은 `META_GATE_STALE`(`evaluated_window_missing`)로 보고 안내에 쓰지 않는다.
5. **'가장 이른 pending' 의 정의**: 첫 적재일 오름차순(없으면 뒤) → ticker 순의 맨 앞. 목록은 자르지 않는다.
6. **`csv_rows` 기록값 변화**: 옛 계산은 `줄바꿈 수 − 1` 이었다. 두 CSV 모두 마지막 행 뒤에 줄바꿈이 없어 1 적게 셌다(`20260909` 1,167). 이제 resolver 가 읽은 행 수라 1,168(`20260927` 은 1,175)이다.
7. **Q26 유효 종가**: `Close` 가 유한하고 > 0 인 행만 신선한 자료로 본다(inf · NaN · 0 · 음수 제외). 같은 날짜가 두 번 오면 upsert 처럼 뒤 행을 쓴다. 배치 기록의 `kospi_as_of`(DB 최대 날짜)와 error 의 `as_of`(유효 종가 마지막 날짜)는 다를 수 있다.
8. **C5 부분 전송 성공**: `status == "sent"` 이어도 `partial_delivery` 면 잠정값을 유지한다(발송 완료로 세지 않는다).
9. **역검증 ⑦ `!!`**: `scripts/ops02b2/reverse_verify_guards.py` ⑦ 'fingerprint 반복 억제'는 2026-09-18 `02C-OPS-01` 에서 '내용이 같아도 발송'으로 바뀐 뒤로 실패한다. 작업 기준 코드 사본에서도 출력이 같다(diff 0 · exit 1). 이번 변경과 무관하다. 목업 ⑦ 제목 '동일 fingerprint (미발송)' 과 결과 '발송 = 예' 가 어긋나는 것도 같은 원인(기존). 설계자 결정(2026-09-27): 둘 다 현 계약 검증으로 쓰지 않고 `POC3-02D-OPS-02` 에서 정리한다이다.
10. **C3 시각 = 러너 시작 시각**: 종목별 체결 시각이 아니다(Q9 (a)). 헤더 HH:MM · 구 본문 '시세' 와 같은 값.
11. **C2 는 화면 증거 없음**: 수정 전 화면 값은 보지 못했다(PLAN C2 사실). 코드에 실측 cron 을 대입한 판정이다.

---

## 7. 사용자 확인이 필요한 항목

확인 완료(설계자 RESULT 판정 2026-09-27): KRX CSV 출처 · 다운로드일(§1-6) · `META_GATE_STALE` 문구(§6-3) · 첫 화면 OCI 링크와 Q8 결함 · 역검증 ⑦ 의 처리(후속 `POC3-02D-OPS-02` · §5).

남은 항목:

1. **pull 뒤 달라지는 것**(STEP 7 뒤 실화면 확인):
   - 08:00 시장 브리핑에 '오늘 볼 기초지수'와 기준 줄 '국내 {날짜} 종가'가 돌아온다(추정 · 최신성 관문은 별도).
   - 새 CSV 가 필요해지면 08:00 본문 끝에 `※ 운영 안내: KRX ETF 전종목 기본정보 CSV를 갱신해 주세요.` 가 한 번 붙는다. 이 줄을 보면 CSV 를 새로 받아 전달해 주세요.
   - 「장중 급등락」 '기준' 다음 줄에 시각이 찍힌다.
   - 넓은 하락일에는 잘린 보유 급락이 다음 틱에 나가 조건형 발송이 늘 수 있다(상한은 그대로).
   - 발송 실패가 있던 날만 15:40 줄 끝에 '· 발송 실패 N회' 가 붙는다.
   - 「OCI 운영 상태」는 PC 백엔드 재기동 뒤 OPERATING 으로 보여야 한다.
   - 연휴 뒤 첫 거래일에 07:20 · 08:00 운영을 확인한다(설계자 진행 순서 5).
2. **push · OCI pull**: 커밋까지 했다. 설계자 진행 순서대로 검증자 `VERIFIED` → `STATE_LATEST` 갱신 → 커밋 · push(별도 승인) → OCI pull. OCI pull 은 거래일 15:40 뒤 ~ 다음 거래일 07:15 전에, 07:15~08:05 는 피한다.

---

## 8. Q8 인접 결함 tmp 재현 (고치지 않음)

작업 기준 코드 사본(`q8_repro/head_copy`)에서 tmp 경로 · 대역 전송기로 돌렸다. 저장소 · 라이브 state 변경 0. 결과 파일은 개발자 scratchpad `q8_repro/out/*.json` 6개.

**결함 1 — 이미 발송된 사업군 · 보유 급등 신호가 다른 상태로 바뀌었는데 전달되지 못하면, 그 뒤로 계속 억제된다.**

| 경우 | 틱 2 (상태 변화) | 틱 3 · 4 |
|---|---|---|
| 1a 구역 상한에 잘림 | `sent` · 본문에 `T00009`(ENTRY_REVIEW→AVOID_CHASE) · `H00001`(U5_7→U7_10) 없음 · 저장 상태는 새 상태로 바뀜 · `last_sent_at` 은 틱 1 그대로 | 두 신호 모두 본문에 다시 나오지 않고 틱 4 `skipped/no_new_or_worsened` |
| 1b 전송 실패 | `failed/telegram_send_error` · 저장 상태는 새 상태로 바뀜 | `skipped/no_new_or_worsened` 2회 |
| 1c 부분 전송 | `sent`(부분) · 저장 상태는 새 상태로 바뀜 | `skipped/no_new_or_worsened` 2회 |

대조: 1a 에서 틱 2 에 처음 나온 `T00003` 은 틱 3 에 발송됐다(발송 이력이 없던 신호는 영향 없음).

**결함 2 — 장중 조립 중간(`out.intraday` 대입 뒤)에 예외가 나면, 구 본문만 나가는데도 사업군 · 급등 신호가 발송 완료로 기록된다.**

| 주입 위치 | 틱 1 | 틱 2 (같은 신호 · 주입 없음) |
|---|---|---|
| `:302` diagnostics 갱신 예외 | 구 본문 발송(`H00001` 만) · `T00009` · `H00002` `last_sent_at=t+0` 기록 | `skipped/no_new_or_worsened` — 한 번도 안 나간 두 신호가 억제됨 |
| `:336` 회차 결과 계산 예외 | 같음 | 같음 |
| 주입 없음(대조) | 통합 본문에 세 신호 모두 | `skipped` (정상 억제) |

두 결함 모두 C4 와 같은 계열(발송되지 않은 신호를 발송 완료로 기록)이지만 사업군 · 급등 상태 저장 경로라 이번 범위 밖이다(Q8). C4 재계산 자체는 대입 전에 두어 이 경로를 새로 만들지 않았다.

**처리(설계자 결정 2026-09-27)**: 운영 정확성에 영향이 있으므로 후속 `POC3-02D-OPS-02` 에 넣고 POC5-01A PRIMARY 시작 전에 끝낸다.

---

## 9. KS-10 (`wc -l` 실측 2026-09-27)

| 파일 | 줄 | 기준 |
|---|---|---|
| `scripts/run_three_push_runtime_oci.py` | 646 | 변경 0 (백엔드 트리거 650) |
| `app/runtime_evidence/holdings_risk_flow.py` | 491 | 근접선 600 미만 |
| `app/market_briefing/krx_sync.py` | 437 | |
| `app/market_briefing/flow.py` | 427 | |
| `app/market_briefing/meta_gate.py` | 415 | |
| `app/market_briefing/official_csv.py` | 324 | 신규 |
| `app/market_benchmark_store.py` | 298 | |
| `app/market_briefing/krx_store.py` | 298 | |
| 그 밖의 변경 운영 파일 | 94~343 | |
| `tests/test_market_briefing_contracts.py` | 1,406 | 테스트 트리거 1,500 · 근접선 1,450 미만. 다음 C1 테스트는 새 파일로 |
| `tests/test_market_briefing_batch.py` | 1,137 | |
| `tests/test_poc3_02d_ops01_holdings_risk_flow.py` | 944 | 신규(Q22) |
| `tests/test_intraday_alert_flow_through.py` | 1,298 | 추가 0 |

트리거 0 · 근접 0.

---

## 10. git 상태 (커밋 직전 실측)

`git status --short --untracked-files=all` — staged 37(`A ` 8 · `M ` 29 · `docs/STATE_LATEST.md` 1차 갱신 포함) · 오른쪽 칸(작업 트리 변경) 0 · untracked 1.
`git diff --cached --stat` — 37 files changed(줄 수는 이 결과서 자신이 포함돼 바뀌므로 적지 않는다). 커밋 뒤 내역은 `git show --stat <커밋>` 으로 본다.

- untracked 1 = `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` — 사용자 소유 파일이라 건드리지 않고 staged 하지 않았다(이번 단계와 무관).
- 신규 8(`A `): `app/market_briefing/official_csv.py` · `app/trading_day_lag.py` · 설계서 · PLAN · 이 결과서 · `scripts/check_krx_etf_basic_csv.py` · `state/market_meta/krx_etf_basic_20260927.csv` · `tests/test_poc3_02d_ops01_holdings_risk_flow.py`.
- 이 상태로 커밋한다(설계자 진행 순서 3). push 는 별도 승인 · OCI pull 은 그 뒤다.
