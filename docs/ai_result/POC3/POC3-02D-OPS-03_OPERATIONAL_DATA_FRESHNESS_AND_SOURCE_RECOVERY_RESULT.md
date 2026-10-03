# POC3-02D-OPS-03 개발 결과서 — OPERATIONAL_DATA_FRESHNESS_AND_SOURCE_RECOVERY

작성일: 2026-09-30(설계자 RESULT 판정 보완 반영) · 종료 갱신 2026-10-02(배포 · 첫 거래일 실측 · 한국 거래일 계약 정정) · 작성자: 개발자(VSCode Claude) · 수신: 검증자(설계자 RESULT STEP 7 — 보완 뒤 설계자 재판정 없이)

```text
STATUS               = IMPLEMENTED_VERIFIED_DEPLOYED_OPERATION_CONFIRMED (2026-10-02) — 설계자 종료 수용 2026-10-02(RECHECK_20261006 = WAIVED_BY_USER · 7d507951 = 비차단 · 다음 정기 OCI pull · 잔여 판단 5건 → POC3-02D-OPS-04 · 원문 = 설계서 끝)
DEPLOYMENT           = CONFIRMED (커밋 7feddf2c · OCI pull + cron 3줄 2026-10-01 · read-back 16:32 — §8-1 · §8-2)
OPERATION            = CONFIRMED (2026-10-02 첫 거래일 실측 · 사용자 결정으로 10-06 재실측 생략 — §8-5)
IMPLEMENTATION       = DONE
BLOCKING_ITEM        = NONE
USER_UI_CHECK        = PASSED (2026-09-30 1차 화면 · 보완 화면 STEP 4: 제목 · 출처 · KOSPI 기준일 · 정비 큐 = 2026-10-01 00:4x 사용자 회신 '화면과 문구 좋습니다')
USER_TEXT_CHECK      = APPROVED (B · C · D 문구 · 보완 새 문구 R1-1 · R4-2b · R4-2c · R4-4 = 2026-10-01 00:4x 사용자 회신 '화면과 문구 좋습니다')
PRICE_BASIS_CONTRACT = ETF_KRX_UNADJUSTED__STOCK_FDR (개별주 파생값은 혼합 확정으로 늘 fail-closed)
DESIGNER_RESULT      = PASS_WITH_MANDATORY_AMENDMENTS (2026-09-30) — 보완 뒤 설계자 재판정 없이 검증자

STEP_ID                   = POC3-02D-OPS-03
STEP_NAME                 = 운영 데이터 최신성·자료원 복구
PREDECESSOR / SUCCESSOR   = POC3-02D-OPS-02 / POC5-01A (개방 — 설계자 STEP 8 · OPS-03 운영 확인 2026-10-02 · 설계자 정정 2026-10-02: POC5-01A = 세 PUSH 러너 기계 분리 → POC3-02D-OPS-04 → POC5-01B 운영 원장)
PLAN                      = CONFIRMED (설계자 PASS_WITH_MANDATORY_AMENDMENTS 2026-09-29 · 확정 계약 15항목 · RESULT 판정 STEP 1~8 이 그 위에 우선)
VERIFIER                  = VERIFIED (r3 · 2026-10-01 · A-1~A-4 · B-1~B-6 통과 · 위험 NONE · 범위 폭주 MINOR) — r1 REJECTED(A-1 기존 날짜 행이 있으면 건수 확인 없이 성공 · A-2 `untracked` 표기 충돌) · r2 REJECTED(A-2 옛 함수 테스트 호출처 1파일로 적음 · 실제 2파일) 정정 뒤 · §1-0
CURRENT_OPERATION         = OPERATING (2026-10-02 · OPERATING_DEGRADED 해제 — 원인 국내 T-2 · KOSPI 정지 둘 다 해소 · §8-5)
POST_DEPLOY_CHECK         = 2026-10-03 — 종료 커밋 7d507951 OCI 반영 확인(2026-10-02 17:56 KST pull · §12) · 아래 줄의 'OCI 미반영' 은 작성 당시 기록
COMMIT / PUSH / OCI       = 커밋 7feddf2c · push 2026-10-01(사용자 승인) · OCI pull + cron 3줄 2026-10-01(사용자) · read-back 16:32(리드 읽기 전용) — 종료 커밋(한국 거래일 계약 정정 · §11)은 OCI 미반영 · 다음 pull 때 적용
CRON                      = 변경 완료 2026-10-01 (13줄 · PATH 제외 · 08:10 배치 · 08:30 시장 브리핑 · 09:20 `--krx-only` 추가 — §8-2)
RED_ON_BASE_CODE          = 1차: 7e60f536 사본 + 새 테스트 — briefing 25/25 실패 · intraday 16/18 실패 · 5파일 수집 오류 · KospiStatusSurfaces 7/9 실패 / 보완: 보완 전 스테이지 사본 + 새 테스트 — 백엔드 3파일 수집 오류(파일당 1건 · 93건 미실행 · 새 모듈 없음 · import 단계) · dependencyDirection 1/2 실패 — §1-4
SABOTAGE                  = 1차 A 7 · B 9 · C 8 · D 11 · LENS1 19/24 · LENS3 104/114 · M1~M14 14/14 · 리드 2/2 / 보완 STEP 1 18 · STEP 2·6 20 · STEP 3 22 · 프론트 6 전부 탐지 · LENS3 90/94(실제 공백 3 → 테스트 추가 · 동작 동일 1) · 수정 라운드 9/9 · 리드 개별주 1(3건 실패) — §1-4
BACKEND_FULL_REGRESSION   = 2,703 passed / 0 failed (exit 0 · 371.31s · 1 warning = fastapi testclient StarletteDeprecationWarning 제3자 · 2026-10-01 15:4x · 검증자 r1 정정까지 모든 코드 변경 뒤 마지막 1회 · 커밋 7feddf2c) — 종료 커밋 회귀는 §11
PC_LIVE_STATE             = PC `state/` · `logs/`(`state/ml/research` 제외) 226파일 sha256 전체 회귀 전후 동일(diff 0바이트)
OPS03_NEW_TESTS           = 백엔드 10파일 292건(collect 실측 2026-10-02 · 7feddf2c 때 286 · 종료 커밋 briefing_calendar 40 → 45 · krx_batch 46 → 47) 전체 회귀에 포함 · 프론트 KospiStatusSurfaces 21 · dependencyDirection 2
FRONTEND                  = vitest 24파일 · 287건 통과 · tsc rc 0 · eslint rc 0 (커밋 7feddf2c 워크플로 최종 실측) · 종료 커밋 전체 vitest 24파일 287(`OciStatusView.test.tsx` 7) · tsc 0 · eslint 0(2026-10-02)
PRODUCTION_BUILD          = 저장소 밖 사본(node_modules 심링크)에서 `npx next build` rc 0 · Next.js 15.5.15 · ✓ Compiled successfully · 정적 4/4 · `/` 76.1 kB · First Load 178 kB · 저장소 `frontend/.next` mtime 전후 동일 · dev 서버 200 유지
BLACK / FLAKE8 / COMPILE  = 변경 · 신규 Python 67파일 — black "67 files would be left unchanged" · flake8 rc 0 · py_compile rc 0 (리드 개별주 변경 뒤 재실측 · 커밋 7feddf2c)
OCI / TELEGRAM            = OCI 쓰기 0 · 실발송 0 · OCI 접속은 읽기 전용만(sqlite mode=ro · crontab -l · 로그 읽기)
KS10_TRIGGER              = 0 (러너 646줄 변경 0 · 변경 백엔드 모듈 최대 sector_signal.py 599 → 종료 커밋 595 · §9)
```

입력 문서

- 설계서(설계자 원문 · PLAN 판정 원문 · STEP 12 시나리오 · 끝 절 '설계자 RESULT 판정' 원문 STEP 1~8): `docs/ai_design/POC3/POC3-02D-OPS-03_OPERATIONAL_DATA_FRESHNESS_AND_SOURCE_RECOVERY_DESIGN_V1.md`
- PLAN: `docs/ai_plan/POC3/POC3-02D-OPS-03_OPERATIONAL_DATA_FRESHNESS_AND_SOURCE_RECOVERY_PLAN_V1.md` ('확정 계약' 15항목)
- 작업 기준 코드: `7e60f536`(OPS-02 배포 확인 문서 커밋 · 코드는 `eff609a0` 과 같음)

---

## 0. 한눈에

| 문제(실측) | 바뀐 것 | 기준 코드 재현(RED) |
|---|---|---|
| 08:00 기초지수 · 장중 신규 진입 5일 · 20일이 매일 T-2 (KRX 는 익영업일 08:00 공개 · 07:20 수집) | (cron 2026-10-01 적용) 배치 08:10 · KRX 목표일(T-1) 단일 조회 08:10 · 08:15 · 08:20 · 08:24 · 마감 08:27 · 브리핑 08:30 · 09:20 KRX 전용 보강 1회 | krx_batch · stages 수집 오류(새 모듈) |
| 국내 최신성이 `lag ≤ 1` 이라 T-2 통과 | `actual_basis_date == expected_previous_trading_day` · 아니면 구역 생략 + 설계자 문구 1줄 | briefing 25/25 · intraday 16/18 실패 |
| 5일 · 20일이 저장 행 위치 기준 | 거래일 캘린더 날짜 기준 · 날짜가 없으면 fail-closed | 같음 |
| KOSPI FDR KS11 09-17 정지 · 09-17 값 비공식 · (1차 구현 · 설계자 RESULT 지적) 08:10 1회 | KRX `idx/kospi_dd_trd` 공식 종가 · 09-17 증거 뒤 정정 · T-1 이 아니면 08:15 · 08:20 · 08:24 재시도(ETF 와 독립) | kospi · kospi_retry 수집 오류(kospi_retry 는 보완 전 스테이지) |
| S&P500 나이 상한 없음 | NYSE 공식 휴장 CSV · 기대 완료 세션 일치 때만 전망 | briefing_calendar 수집 오류 |
| FDR 한 종목 실패 → 미국 · KRX 미실행 · FDR timeout 없음 | 단계 격리 · 요청당 20초 · 단계 180초 | stages 수집 오류 |
| 배치 실패일 보유 20거래일 기준일이 T-21 | 캘린더 T-20 | holdings 수집 오류 |
| 보유 PUSH 과거 종가(FDR 조정) · 현재가(Naver 무조정) 혼합 | ETF = KRX 무조정 · 개별주 = FDR 경로지만 혼합 확정으로 파생값 늘 닫음 | price_basis 수집 오류 |
| (1차 구현 · 설계자 RESULT 지적) 활성 설정을 못 읽으면 ② 건너뜀 · 대표 1종 폐지면 08:30 까지 막힘 | 적재 = ①③④⑤ · 대표 커버리지는 장중 신규 진입만 막음 · 08:30 은 자기 관문 | consumer_isolation 수집 오류(보완 전 스테이지) |
| (1차 구현 · 설계자 RESULT 지적) 09:20 · 재실행이 같은 창 날짜를 다시 부를 수 있음 | 날짜별 하루 1회 ledger · 원천 불통 중 채우기 미룸 | 같음(보완 전 스테이지) |
| KOSPI 화면 `(KS11)` 제목 · 출처 없음 · 하단 날짜 = KODEX200 · (1차 구현) lib → components import | `KOSPI (보조)` · `출처: 한국거래소(KRX)` · KOSPI 기준일 · 정비 큐 항목 · `lib/kospiStatus.ts` | KospiStatusSurfaces 로드 실패 · dependencyDirection 1/2(보완 전 스테이지) |
| 배치 실패 고지 없음 | 08:30 브리핑 안 1줄(하루 1회) · KOSPI 만 실패면 없음 | briefing 실패 |

---

## 1. 처리한 요구사항

### 1-0. 검증자 r1 · r2 REJECTED(2026-10-01) 처리

| 지적 | 처리 |
|---|---|
| A-1 · B-6 — 같은 날짜에 행이 하나라도 있으면 건수 · 내용 비교 없이 `kept_existing` 성공(`krx_target_checks.py:183` · 테스트가 40행 저장 + 39행 응답을 성공으로 기대) | 정정 — `_save_and_read_back` 이 저장분 `{종목: 종가}` 를 이번 snapshot 과 비교한다. 같을 때만 그대로 둔다. 다르면 `krx_store.replace_date`(한 트랜잭션: 그 날짜 DELETE + INSERT)로 바꿔 쓰고, 새 쓰기 · 바꿔 쓰기 모두 `krx_store.rows_on` 으로 다시 읽어 종목 · 종가 · 건수가 같아야 성공이다. 어긋나면 그 날짜를 비우고 `readback_mismatch` 실패(fail-closed). 판정까지 끝난 T-1 은 이 경로에 오지 않는다(`already_loaded` · 확정 계약 2 그대로). 테스트: 같으면 유지 · 다르면 교체 3가지(부분 저장 · 저장분이 더 많음 · 값 다름) · 교체 뒤 read-back 어긋남 → 날짜 비움 · 교체는 한 트랜잭션. 무력화(옛 '행 있으면 유지' 복원) → 새 테스트 4건 실패 확인 · 원본 cmp 복구 |
| 같은 표에 쓰는 다른 경로 | `krx_store.upsert_snapshot` 호출처 grep — 운영 경로는 `krx_target_checks` 하나. 옛 함수 `krx_sync.sync_krx_daily`(옛 역탐색) · `initial_backfill` 의 호출처 전수(`grep -rn 'sync_krx_daily(\|initial_backfill(' --include='*.py' .` · 2026-10-01 · r2 A-2 정정): 운영 코드(`app/` · `scripts/` · `deploy/`) **0** · 테스트 2파일 — `tests/test_market_briefing_batch.py`(`sync_krx_daily` 11곳 · `initial_backfill` 3곳) · `tests/test_market_briefing_flow_through.py:445`(`sync_krx_daily` 1곳). 그 밖의 언급은 호출이 아니다 — `tests/conftest.py:562` · `:567` 주석 · `app/market_briefing/krx_target_sync.py:173` docstring · `krx_sync.py:358` docstring · `__all__`. 옛 계약 테스트용으로 남아 있고 OPS-03 ⑤ 대상 경로가 아니다. 목업 · 역검증 스크립트는 tmp DB |
| A-2 — 결과서 §2 · §8 · STATE_LATEST · PROGRAM_TRUTH 의 `untracked` 표기가 실제 staged 와 충돌 | 정정 — `grep -n untracked` 로 결과서 · `docs/STATE_LATEST.md` · `docs/PROGRAM_TRUTH.md` · `docs/handoff/OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` 전부 찾아 이번 단계 파일의 표기를 'git 에 추가됨(staged)' 으로 바꿨다. 남은 `untracked` 는 사용자 소유 master handoff(실제 untracked) · `--untracked-files=all` 명령 · 옛 단계 이력 줄뿐 |
| A-2 — 조건 ⑤ 를 DONE 으로 보고했으나 기존 행 분기는 검증하지 않음 | 위 정정으로 코드가 계약과 같아졌다 · §1-1 계약 3 행 · PROGRAM_TRUTH C-4 ⑤ 서술을 실제 동작으로 교체 |

### 1-1. 확정 계약 15항목 (설계자 RESULT 판정 개정 반영 · 코드 · 테스트)

약칭: kts = `app/market_briefing/krx_target_sync.py` · checks = `krx_target_checks.py` · backfill = `krx_backfill.py` · batch = `scripts/run_oci_market_data_batch.py` · mdb = `app/three_push_runtime/market_data_batch.py` · rmb = `runner_market_briefing.py` · retry = `app/market_benchmark_kospi_retry.py` · hpb = `app/runtime_evidence/holdings_price_basis.py` · 테스트 파일은 `tests/test_poc3_02d_ops03_<이름>.py` 의 `<이름>`.

| # | 계약 | 코드 | 테스트 | 판정 |
|---|---|---|---|---|
| 1 | 시간 계약 08:10 · 08:15 · 08:20 · 08:24 · 08:27 · 08:30 · 09:30 | `render.HEADER`(`render.py:38`) · kts `ATTEMPT_SLOTS`(:57) · `STAGE_DEADLINE`(:58) · KOSPI 재시도도 같은 시각표(retry `retry_slots` :61 → kts `attempt_plan` :98) · 목업 스크립트 · 역검증 ops02b2 ② | briefing `test_header_is_0830` · krx_batch `test_schedule_boundaries` · kospi_retry `test_retry_slots_follow_krx_schedule`(7) | DONE — OCI 반영 2026-10-01 · 첫 거래일 확인 2026-10-02(§8-5) |
| 2 | 07:20 폐지 · 08:10 전체 · 단계 격리 · FDR timeout · FDR · 미국 회차당 1회 · 08:27 뒤 fail-closed · 성공 T-1 을 덮지 않음 | batch `run`(:65 · 수집 → FDR → 벤치마크 → artifact → 상태 먼저 기록 `krx: pending`(:190-191) → KRX(:195) → KOSPI 재시도 반영 · 종료 status 다시 계산(:197-198)) · mdb `FDR_REQUEST_TIMEOUT_SECONDS`(:160 · 20초) · `FDR_STAGE_TIME_BUDGET_SECONDS`(:164 · 180초) · 이미 받은 T-1(kts :279) · checks `_save_and_read_back` 기존 날짜 안 씀(:175) · kts `_record_failure` T-1 판정 보존(:457) | krx_batch_stages `test_s6_*` 5건 · `test_success_path_order_and_state_written_before_krx_wait` · `test_fdr_timeout_is_injected_only_inside_the_block` · `test_fdr_time_budget_stops_starting_new_tickers` · krx_batch `test_no_new_attempt_after_deadline_when_attempts_are_slow` · `test_s10_backfill_stops_at_0827_deadline` · `test_s12_*` 3건 | DONE |
| 3 | KRX 적재 성공 조건 — 설계자 RESULT STEP 2 로 **①③④⑤**(② 대표 커버리지는 소비자 격리로 이동) | checks `check_response`(:92 · 대표 목록을 받지 않음 · ① 반환 기준일 ③ 95% ④ `validate_snapshot` · `relation_violation` :59) · `_save_and_read_back`(:175 · ⑤ 저장 뒤 다시 읽은 행(종목 · 종가 · 건수)이 이번 snapshot 과 같아야 성공 · 같은 날짜에 같은 내용이 있으면 다시 쓰지 않고, 다르면(판정 전 중단으로 남은 부분 저장 · 다른 값) 한 트랜잭션에서 바꿔 쓴 뒤 다시 읽는다 · 어긋나면 그 날짜를 비운다(fail-closed · 검증자 r1 A-1) · `krx_store.rows_on` · `replace_date`) · 대표 판정은 적재 뒤 `evaluate_representatives`(:225) → kts `_record_representatives`(:418) | krx_batch `test_s4_only_t2_returned_is_not_success` · `test_s5_bad_response_is_retried_and_never_partially_saved`(6) · `test_s5_zero_volume_rows_are_not_relation_violations` · `test_readback_mismatch_rolls_back_the_date` · `test_s12_existing_t1_rows_are_kept_only_when_identical` · `test_s12_existing_t1_rows_that_differ_are_replaced_and_read_back`(3) · `test_s12_replaced_rows_that_do_not_read_back_leave_the_date_empty` · `test_replace_date_is_one_transaction` · consumer_isolation `test_load_success_does_not_depend_on_representatives_in_checks` | DONE(r1 A-1 정정) |
| 4 | 95%(고정 행 수 금지) | checks `MIN_ROW_RATIO = 0.95`(:33) · 기준 = 목표일 앞 최근 저장일 행 수(`krx_store.baseline_row_count` :348) | `test_s5_row_ratio_boundary_is_95_percent_of_previous_load` | DONE |
| 5 | 5일 · 20일 = 거래일 날짜 · 빠지면 fail-closed | `krx_store.resolve_calendar_window`(:477 · `CalendarWindow` :431) · `sector_signal.trend_returns`(:288) · `holdings_selection_source.trading_day_axis`(:103) · 연도 파일 없는 해 = 평일 기본(5월 1일 · 12월 31일 제외) · 저장 자료 없는 평일은 휴장으로 건너뜀(`trading_day_lag._trading_day_test` `stored` · 종료 커밋 §11 — 7feddf2c 의 `unconfirmed_days` 창 닫기는 한국 거래일 계약 정정으로 삭제) | krx_batch `test_s10_*` · intraday `test_missing_d5_date_fails_closed_instead_of_shifting` · `test_missing_non_required_day_keeps_calendar_d20_value` · krx_batch `test_uncovered_year_unstored_weekday_is_skipped_window_stays_usable` · `test_fallback_year_closes_may_1_and_dec_31_only` · holdings `test_uncovered_year_unstored_weekday_is_skipped_not_emptied` · `test_uncovered_year_gap_reaches_both_holdings_flows` · intraday `test_trend_basis_uncovered_year_unstored_weekday_is_skipped` | DONE(연도 파일 없는 해 규칙은 종료 커밋 · §11) |
| 6 | 국내 = 기대 T-1 정확 일치 · 없으면 구역 생략 + 한 줄 · T-2 대체 금지 · 재발송 금지 | `flow._index_block`(:182 · 첫 관문 :203-215 → `STATUS_PREV_DAY_MISSING`) · `render.INDEX_NOTICE[STATUS_PREV_DAY_MISSING]`(:68) · 재발송 차단은 기존 일 단위 registry | briefing `test_t2_only_omits_index_with_designer_line_and_no_t2_leak` · `test_basis_later_than_expected_is_not_fresh` · `test_t1_missing_wins_over_unusable_csv` · `test_batch_notice_once_per_day_through_runner` | DONE |
| 7 | 09:20 KRX 전용 보강 1회 — 설계자 RESULT STEP 6: T-1 재조회 없이 21거래일 창 누락일만 · 같은 날짜 하루 1회 · 호출 기록 | batch `run_krx_only`(:433 · `max_attempts=1` · 하루 1회 = mdb `KRX_REINFORCEMENT_STATE_PATH` :122 · 08:10 상태 JSON 안 덮음) · CLI `--krx-only`(:544) · T-1 미확보면 목표일 1회 · 이미 받은 날은 목표일 조회 0 + 채우기(kts :279-295) · 채우기 = backfill `fill_missing`(오늘 아직 안 부른 날만 · ledger) · 목표일 조회가 `fetch_error` 인 동안 채우기 미룸(kts :326-334) | krx_batch_stages `test_s11_*` 4건 · `test_krx_only_flag_is_parsed_and_exclusive` · krx_batch `test_s11_already_loaded_run_fills_window_gap_without_t1_refetch` · `test_s10_backfill_waits_while_target_fetch_cannot_reach_source` · `test_s10_no_backfill_when_every_target_attempt_is_fetch_error` · consumer_isolation `test_same_window_date_not_called_twice_across_0810_retry_0920_rerun` | DONE · cron 1줄 2026-10-01 추가 · 10-02 09:20 실행 확인(§8-5) |
| 8 | 장중: T-1 미확보면 「신규 진입 검토」만 생략 · 회피 · 보유 급등락 계속 · `추세 기준 YYYY-MM-DD 종가` · (RESULT STEP 2) 활성 대표 27종 T-1 100% 일 때만 진입 검토 | `sector_signal.resolve_trend_basis`(:243) · `select_sector_signals`(:370 · 대표 T-1 커버리지 :394-409) · 종목 T-1 없음 `ticker_not_t1`(:87) · `intraday_alert_render.TREND_BASIS_LINE`(:77) · `trend_basis_line`(:209) · 설정 읽기 실패 `intraday_alert_flow.config_read_error`(:169 · :424-437) | intraday `test_t2_only_omits_entry_but_keeps_avoid` · `test_t1_loaded_shows_entry_with_trend_basis_line` · `test_alternate_without_t1_row_is_excluded_alone` · `test_run_t2_only_sends_avoid_and_counts_omission` · `test_unevaluable_entry_is_not_recorded_as_recovery` · consumer_isolation 대표 관문 테스트(§1-2 STEP 2) | DONE |
| 9 | KOSPI 공식 종가 · 정상 = T-1 일치(C7 lag ≤ 1 폐기) · 09-17 정정 ①~⑥ · (RESULT STEP 3) 08:10 결과가 T-1 이 아니면 08:15 · 08:20 · 08:24 재시도 · 마감 08:27 · ETF 와 독립 · 09:20 재조회 없음 · Telegram 없음 · (STEP 4) 출처 · KOSPI 기준일 · 정비 큐 | `market_benchmark_store.refresh_kospi_benchmark`(:343 · `KOSPI_SOURCE` :177 · `_fetch_dates` :227 저장 최신일 포함 ~ T-1 · 재시도는 `include_latest` · `_store_fetched` :427 증거 → 저장 → read-back) · retry `KospiRetry`(:148 · `latest_confirmed` :115 · `apply` :264) · batch `_benchmark_stage`(:262) → `_krx_stage(side_task=…)`(:195) · `kospi_freshness`(`market_benchmark_freshness.py:148`) 사용처 = 적재 판정(store :514) · `market_regime`(:157) · `api_market_topn_service`(:367) · 조회 = `krx_sync._default_kospi_fetcher`(:94) · 화면 = `MarketContextCard.tsx:114` · `:124` · `today/KospiHeadline.tsx:142-143` · `today/maintenanceQueue.ts:85-96` · `today/KospiChart.tsx`(:20 · :39) | kospi 38건(`test_first_run_corrects_0917_with_evidence_and_fills_to_t1` · `test_evidence_is_written_before_the_overwrite` · `test_no_evidence_no_overwrite` · `test_all_layers_import_the_same_freshness_function` · `test_batch_compute_and_api_agree` 등) · kospi_retry 39건 · `KospiStatusSurfaces.test.tsx` 21건 | DONE — ② 영향 날짜 전체 대조는 OCI 읽기 전용 대조(§1-6) · ③④ 실제 정정 = 2026-10-02 08:10 첫 OCI 실행(09-17 6724.34 → 6715.41 · 증거 JSON · §8-5) |
| 10 | 범위: FDR 순서 · FDR timeout · 보유 20거래일 기준일 밀림 · 조정/무조정 혼합 | 순서 · timeout = 계약 2 · 기준일 = `trading_day_axis` · 가격 기준 = 설계자 RESULT STEP 1 선택지 (a) — hpb `load_basis_history`(:223 · 흐름 `holdings_selection_flow.py:144` · `holdings_risk_flow.py:103`) · ETF = `krx_store.read_holdings_etf_prices`(:261 · 읽기 전용) · 개별주 = FDR 경로 · 파생값 늘 fail-closed(hpb :269-274) | holdings 10건(`test_batch_failure_does_not_slip_the_20_day_base` · `test_risk_previous_close_date_is_calendar_t1_on_batch_failure` · `test_missing_base_close_is_data_unavailable_not_shifted` 등) · price_basis 27건 | **DONE** — 선택지 (a) · 개별주는 혼합 확정으로 파생값 늘 닫음(근거 §1-2 STEP 1) |
| 11 | NYSE 공식 휴장 CSV(출처 · 작성일 · hash) · 기대 완료 세션 · 다음 해 readiness(한국 readiness 는 설계자 2026-10-02 정정으로 삭제 — 미국만) | `app/us_trading_calendar.py`(`expected_completed_session` :184 · `session_check` :229 · `calendar_readiness` :288 · `MARKETS = ("NYSE",)` :280) · `state/market_meta/nyse_holidays_2026.csv` · `2027.csv`(머리 주석 source_url · retrieved_at_utc · page/table sha256) · rmb `_sp500_input`(:57) · 배치 `calendar_readiness`(미국만) · `oci_startup_status.calendar_job`(:292 · 미국 행) · `trading_day_basis_job`(:281 · 한국 고정 문구 행) | briefing_calendar 45건(`test_repo_csv_matches_official_notice_and_records_provenance` · `test_expected_session_dst_est_and_early_close_boundaries` · `test_sp500_input_fresh_only_on_expected_session` · `test_readiness_is_us_only_november_check_and_december_warning` · `test_oci_status_korea_basis_row_is_always_normal` · `test_oci_status_us_calendar_row` 등) · `OciStatusView.test.tsx` 1건 | DONE — 한국 거래일은 평일 기본 운영 · 다음 해 파일로 경고하지 않음(종료 커밋 · §11) |
| 12 | cron 선행 변경 금지 · 배포 순서 | kts 08:00 전 시작 = KRX 건너뜀(`MODE_SKIPPED_BEFORE_OPEN` :254-258 · 표 · 정합성 JSON 안 건드림) · KOSPI 재시도도 없음(`retry_slots`) | krx_batch `test_started_before_0800_is_skipped_and_touches_nothing` · kospi_retry `test_started_before_0800_makes_no_retry` | DONE(코드 가드) — 배포 2026-10-01 · pull 과 cron 같은 회차(§8-1) |
| 13 | 실패 고지: 08:30 국내 1줄 · 09:20 도 실패면 생략 + 집계 · PUSH 영향 장애 하루 1회 · KOSPI PC 전용 = Telegram 없음 · 매 틱 반복 금지 | rmb `batch_failure_reasons`(:104 · 입력 = 상태 JSON 없음 · `refresh_date_kst` ≠ 오늘 · `stage_status.fdr_price` ≠ ok) · `render.BATCH_FAILURE_NOTICE`(:79 · 문구 · 발동 조건 그대로 · 주석 :72-78 은 개별주 늘 닫힘 뒤 영향으로 리드가 다시 고침) · `render_notice_only`(:220) · `flow.py:377-409` · 고지만 본문엔 CSV 안내 없음(:440) · 집계 `intraday_checkup_tally.py:163-164`(`entry_omitted`) · `intraday_alert_render.ENTRY_OMITTED_SUMMARY`(:79) · 15:40 요약 생략 사유(`holdings_selection_flow.py:257-263`) | briefing `test_batch_failure_reasons_inputs_are_limited`(8) · `test_notice_only_body_has_no_csv_notice_while_refresh_cycle_is_live` · `test_batch_notice_once_per_day_through_runner` · kospi `test_kospi_only_failure_is_pc_only_no_telegram_notice` · kospi_retry `test_all_four_slots_fail_stale_etf_on_time_no_telegram_notice` · intraday `test_tally_counts_entry_omitted_ticks_without_schema_change` · `test_summary_without_omission_is_byte_identical` · consumer_isolation `test_run_delisted_representative_sends_avoid_and_counts_omission` · `test_intraday_alert_flow_through.py::test_1540_summary_omission_names_config_read_failure` | DONE — B3 발동 입력은 결정 항목(§7-3 (2)) |
| 14 | 시나리오 12개 · 첫 거래일 실측 | 실측 필드 = 배치 상태 JSON · 09:20 기록 · 실행 기록(§8-4) | §1-3 · §8-5 | DONE — 시나리오 · 첫 거래일 실측 2026-10-02 통과(§8-5 · 10-06 재실측은 사용자 결정으로 생략) |
| 15 | POC5-01A 는 OPS-03 운영 확인 뒤 · 중단 보고 조건 | 새 유료 자료원 · 신규 키 · 운영 DB 스키마 변경 0 | — | 충족 — OPS-03 `IMPLEMENTED_VERIFIED_DEPLOYED_OPERATION_CONFIRMED`(2026-10-02) · POC5-01A 개방 · 중단 보고 조건 해당 0 |

### 1-2. RESULT 보완 (2026-09-30) — 설계자 RESULT 판정 STEP 1~7

| STEP | 요구 | 코드 | 테스트 | 판정 |
|---|---|---|---|---|
| 1 | 가격 기준 (a) + 가드 · 계약 10 DONE | hpb(신규 293 · 종료 커밋 311 · §11) · `krx_store.read_holdings_etf_prices`(:261) · 모듈 계약 `krx_store.py:16-26` · 흐름 2곳 · `holdings_selection_render.py:53-56` | price_basis 27 · 기존 보유 테스트 대역 교체(`tests/_helpers.py:307-351`) | DONE |
| 2 | 대표 ETF 검증과 소비자 격리 | checks(신규 281) · `app/intraday_config/representatives.py`(신규 99) · kts `_record_representatives`(:418) · mdb `write_batch_state`(:58-60) · `sector_signal.select_sector_signals`(:394-409) · `intraday_alert_flow`(:169 · :269 · :424-437) | consumer_isolation 27 · intraday · krx_batch 수정 | DONE · 해석 2건(§6) |
| 3 | KOSPI 재시도 | retry(신규 306) · kts `_wait_for`(:396) · `_drain_side`(:409 · :205 · :208) · store `refresh_kospi_benchmark(recheck_latest=)` · `market_benchmark_batch.refresh_kospi`(:54) · batch :195-198 | kospi_retry 39 | DONE |
| 4 | KOSPI 화면 3건 · 정비 큐 | `MarketContextCard.tsx` · `today/KospiHeadline.tsx` · `lib/marketDiscoveryCopyText.ts:153` · `today/maintenanceQueue.ts:85-96` | KospiStatusSurfaces STEP 4 describe 4개 · `TodayInvestmentCheckView.test.tsx` 1건 | DONE(코드 · 테스트) · 보완 화면 · 새 문구 사용자 확인 완료 2026-10-01(§7-1) |
| 5 | 프론트 의존 방향 | `frontend/lib/kospiStatus.ts`(신규 141) · `KospiStatusNote.tsx` 153 → 51 · `frontend/eslint.config.mjs` `no-restricted-imports` | `frontend/lib/dependencyDirection.test.ts` 2 | DONE |
| 6 | 기타 판단 승인 · 09:20 채우기 한도 · 기술부채 | backfill(신규 184) · `.gitignore:199` · `docs/backlog/BACKLOG.md` §16(:666) | consumer_isolation ledger 7건 · krx_batch `test_s10_*` | DONE |
| 7 | 검증 보완 10항목 | 아래 STEP 7 표 | | DONE · 7 · 10 = 리드 최종 실측 |
| 8 | 배포 순서 | §8 | | DONE — 배포 2026-10-01 · 첫 거래일 실측 2026-10-02(§8-5) |

**STEP 1 — 보유 PUSH 가격 기준 (선택지 (a) + 가드)**

- 경로: 과거 종가를 읽는 보유 흐름은 두 곳 — 보유 브리핑 `holdings_selection_flow.py:144` · 장중 위험 `holdings_risk_flow.py:103` — 둘 다 hpb `load_basis_history`(:223)만 쓴다. 러너 호출부 2곳은 그대로(새 인자 `price_basis_source` 기본 None = 운영 원천).
- 구분(hpb `classify_assets` :148): ETF = 공식 ETF 마스터 CSV(`resolve_official_csv(state/market_meta)` · 시장 브리핑과 같은 resolver)에 있음 또는 KRX 무조정 표에 적재 기록 있음(CSV 날짜 뒤 상장) · 개별주 = 두 원천을 모두 읽었고 어디에도 없음 · 미상 = 그 밖(한쪽이라도 못 읽음 · 추측 안 함) → 파생값 닫음. 구분 원천은 `class_source`. 구현 에이전트 읽기 전용 확인: 최신 CSV `krx_etf_basic_20260927.csv`(1175종) 기준 보유 29종 = ETF 26 · 개별주 3(000660 · 005930 · 006400).
- ETF: 20거래일 전 종가 · 구간 종가는 KRX 무조정 표에서만(`read_holdings_etf_prices` · `mode=ro` · 표를 만들지 않음 · 못 읽으면 예외 → `krx_unreadable`). ETF 에는 `fetch_history` 를 부르지 않는다(FDR fallback · 혼합 없음).
- 값 칸(R1-1): 현재가는 정상인데 20거래일 기준 종가를 못 쓰면 `■ 데이터 확인 필요` 그룹 · `20거래일 데이터 확인 불가`(`holdings_selection_render.py:53-56`) — ETF KRX 기준일 종가 없음 · KRX 표 못 읽음 · 개별주 · 자산 유형 미상. `현재가 조회 실패` 는 현재가 자체 실패일 때만(둘 다면 현재가 실패). 구간 종가가 빠지면 `고점 대비` 만 생략(R1-2 · 새 문구 없음 · evidence `derived.window = missing:N`).
- 실시간 급등락 · 전일 대비는 Naver 등락률 그대로(`test_risk_stock_mismatch_omits_drawdown_but_keeps_day_drop` — 급락 `D5_7` 유지 · 고점 대비만 None).
- evidence: 보유 브리핑 `holdings_price_basis`(`holdings_selection_flow.py:176`) · 장중 위험 `risk_price_basis`(`holdings_risk_flow.py:143`) → 러너 `record.update(diagnostics)` 로 실행 기록 JSONL. 위 = `contract` · `etf_master`(CSV 이름 · `unreadable:X`) · `krx_table`(`ok` · `unreadable:X`) · `tickers`. 종목별 = `asset_type` · `class_source` · `price_source`(`KRX_OPEN_API/etf_bydd_trd` · `FinanceDataReader`) · `price_basis`(`unadjusted` · `fdr_naver`) · 개별주 `guard{t1, fdr_close, naver_prev_close, diff_pct, ok}` · 닫힌 경우 `reason`(`price_basis_mismatch` · `asset_type_unknown` · `krx_unreadable`) · `derived{base_close, window}`(닫힘 = `blocked`). 테스트 `test_evidence_fields_reach_assembly_diagnostics_as_json` · `test_runner_record_and_history_carry_price_basis`(실제 `run()` JSONL).
- 개별주(STEP 1-6 · 1-7): FDR 경로 그대로 · KRX 가격을 읽지 않는다(구분용 적재 기록 여부만). **파생값(20거래일 수익률 · 고점 대비)은 가드 결과와 무관하게 늘 닫는다**(hpb :269-274 · `reason=price_basis_mismatch` · `derived=blocked`). 가드(FDR 캘린더 T-1 종가 vs Naver 전일 종가 = 현재가 ÷ (1 + 등락률) · 0.5%)는 그날 차이 기록으로만 남는다. FDR 은 계속 읽는다(가드 기록 · 연도 파일 없는 해에 저장된 평일 = 거래일 근거 — `test_blocked_stock_dates_still_confirm_weekdays_in_uncovered_year`).
- 늘 닫는 근거 — 표본 대조(작업 폴더 `stock_price_basis_sample.md` · 10:11 · 10:32 두 번 같은 결과)와 리드 원인 확인(KRX OPEN API `sto/stk_bydd_trd?basDd=20260929` · 기존 키 · 1회 읽기 · 942행 · 코드 경로에 넣지 않음):

| 종목 | KRX 공식 09-29 종가 | Naver basic 전일 종가(역산) | FDR(Naver fchart) 09-29 일봉 | FDR / Naver 전일 − 1 |
|---|---:|---:|---:|---:|
| 000660 SK하이닉스 | 1,765,000 | 1,765,049.1 | 1,790,000 | +1.414% |
| 005930 삼성전자 | 272,500 | 272,500(원문 `compareToPreviousClosePrice`) | 275,000 | +0.917% |
| 006400 삼성SDI | 511,000 | 511,014.1 | 517,000 | +1.171% |

  Naver basic 현재가 · 전일 대비는 KRX 정규장 기준(`stockExchangeType` 09:00~15:30 · 시간외 NXT 는 별도 `overMarketPriceInfo`). FDR 개별주 일봉 종가는 정규장 종가가 아니다(시간외 체결 포함 추정) → 현재가(정규장)와 **구조적 혼합** = 설계자 STEP 1-7 발동. T-1 가드가 통과하는 날에도 T-20 종가는 같은 성격이라는 보장이 없어 날마다 판정하는 가드로는 부족하다(리뷰 LENS1-4).
- 무력화: 옛 동작(가드 통과 시 파생값 사용)으로 되돌리면 `test_stock_uses_fdr_and_never_reads_krx_prices` · `test_stock_derived_values_always_fail_closed_guard_is_recorded`(4) · `test_risk_drawdown_uses_krx_for_etf_and_fdr_for_stock` 3건 실패(리드 확인 · 원본 복구).
- 모듈 계약: `krx_store.py:16-26` — 기존 승인 소비처(장중 사업군 추세 · 장중 설정 선택 · 생성)를 적고, 이번 개정으로 더한 예외는 보유 PUSH ETF 가격 증거뿐 · 개별주 · UI · ML 금지.
- 배경(1차 OCI 읽기 전용 실측 · 리드): `krx_etf_daily_price_unadjusted` ↔ `etf_daily_price` 같은 (ticker, date) 1,102행 중 6행 차이(FDR < KRX · 0.2~0.6% · 분배락 뒤 증분 재수집 `mdb.refresh_approved_prices` :265). ETF 는 이제 FDR 계열을 읽지 않는다. 가격수익률이다(분배 포함 총수익률과 섞지 않음).

**STEP 2 — 대표 ETF 검증과 소비자 격리**

- KRX 전체 적재 = ① 기준일 ③ 행 수 95% ④ 관계식 · 중복 · 0행 · 결측 ⑤ read-back 으로 독립 판정(checks `check_response` :92 · `attempt_once` :135).
- 대표 판정 = 적재 성공 뒤(첫 적재 · 이미 받은 날) checks `evaluate_representatives`(:225) · 규칙은 배치 · 장중 공용 `representatives.evaluate_coverage`. 상태 `ok` · `intraday_config_unavailable`(활성 설정 · 대표 목록을 모름 · 대표 없는 사업군이 하나라도 있으면 목록 전체를 모름) · `representative_missing`(T-1 행에 없는 대표) · T-1 행을 못 읽으면 `not_evaluated`(예외 안 올림 · 설계자 세 상태 밖). 적재 실패일에는 판정하지 않는다.
- 기록: kts `out["representatives"]` = `{source, status, expected_previous_trading_day, count, missing, representatives_refresh_due}` · `out["representatives_refresh_due"]` → 배치 상태 JSON `krx_representatives` · `representatives_refresh_due`(batch `_krx_stage` :407-408 · mdb `write_batch_state` 선택 인자 · 옛 호출은 None) · 09:20 기록에도 같은 키.
- 설계자 `refresh_due = true` = 별도 필드 `representatives_refresh_due`(장중 설정 재승인 필요). 정합성 JSON `refresh_due`(08:30 CSV 갱신 안내)는 건드리지 않는다 — 섞으면 CSV 안내가 잘못 나간다(`test_config_unavailable_load_ok_briefing_ok_entry_omitted` 가 `refresh_due` False · 안내 없음 확인).
- 08:30 기초지수: 08:30 조립 경로(rmb → `flow` · `evidence` · `krx_store` · `meta_gate` · `official_csv` · `render` · `calendar`)는 `representatives` · `intraday_config` 를 import 하지 않는다(grep · `krx_store.py:18` docstring 언급만). 같은 패키지의 08:10 배치 모듈 `krx_target_sync.py:50` · `krx_target_checks.py:27` 만 대표 커버리지 기록용으로 import 한다. 자기 관문 그대로 — T-1 저장 · 정합성 조인 95%(`meta_gate.MIN_JOIN_COVERAGE` :48) · d5 · d20 창 · 그룹당 세 날짜 종가 있는 종목 2개 이상(`evidence.MIN_TICKERS_PER_INDEX` :33). 설정 없음 · 대표 폐지 날에도 적재 → 조립 관통 `index_status == ok`(consumer_isolation). '필요 종목 커버리지' 전용 관문은 새로 만들지 않았다(해석 · §6).
- 장중 신규 진입: `select_sector_signals`(:394-409) — 활성 대표 전부가 이력에 **기대 T-1 날짜** 종가(`str(d)[:10] == t1` :400)를 가져야 진입 검토 · 아니면 구역 전체 생략 · 회피는 그대로. 사유 우선순위 `trend_not_t1` → `intraday_config_unavailable` · `representative_missing`. 진단 `intraday_entry_omitted_reason` · `intraday_representatives`. D2 보존 목록 `ENTRY_UNEVALUABLE_REASONS`(`intraday_alert_flow.py:328`)에 두 사유 추가 — 생략 틱이 직전 진입 관측을 회복으로 적지 않게.
- 설정 읽기 실패 vs 꺼짐: 저장소 읽기 예외 · payload JSON 손상 = `intraday_config_unavailable`(`config_read_error` :169 · `skip_reason` · `intraday_entry_omitted_reason` · `intraday_config_error` :424-437) · 활성 버전 없음 · `enabled=false` = `policy_disabled`. 정책은 읽혔는데 사업군 목록이 없으면 `intraday_config_unavailable`(`build_sector_outcome` :247 · :269). 15:40 요약 생략 사유 `intraday_checkup_summary_omitted` 도 같은 구분(`holdings_selection_flow.py:257-263`). 발송 동작은 같다.
- 테스트(consumer_isolation): `test_config_unavailable_load_ok_briefing_ok_entry_omitted` · `test_delisted_representative_load_ok_briefing_ok_entry_omitted` · `test_delisted_representative_intraday_omits_entry_keeps_avoid` · `test_partial_representatives_missing_omits_entry_keeps_avoid` · `test_delisted_representative_with_window_rows_still_omits_entry`(폐지 전 창 행은 남고 T-1 행만 없는 실제 모양) · `test_all_27_representatives_present_entry_runs` · `test_representative_missing_keeps_previous_entry_observation` · `test_intraday_config_read_failure_is_recorded_apart_from_disabled` · `test_disabled_or_unset_policy_stays_policy_disabled`(2) · `test_run_config_unavailable_counts_entry_omitted` · `test_run_delisted_representative_sends_avoid_and_counts_omission` · `test_batch_state_records_representatives_and_backfill` · `test_reinforcement_record_carries_representatives_and_backfill` · `test_representative_read_failure_is_recorded_not_raised`.

**STEP 3 — KOSPI 재시도**

- 첫 시도 = 08:10 벤치마크 단계(batch `_benchmark_stage` :262). 결과가 기대 T-1 이 아니면 retry `KospiRetry`(:148)가 KRX 단계 시각표의 곁 작업(`side_task`)으로 08:15 · 08:20 · 08:24 에 다시 조회 · 마감 08:27(`retry_slots` :61 · 시작 뒤 60초 이상 남은 시각만 · 08:00 전 시작 = 재시도 없음 · 08:27 뒤 시작 = 벤치마크 단계 1회뿐).
- ETF 와 독립: kts `_wait_for`(:396 · ETF 시도 사이) · `_drain_side`(:409 · ETF 판정 · 정합성 JSON 을 쓴 뒤 :208 · ETF 단계 예외 경로 :205) · 같은 시각이면 ETF 먼저 · 곁 작업 예외는 삼킴(`_run_side` :384). ETF 가 성공 · 실패 · 건너뜀으로 끝나도 남은 KOSPI 시각은 돈다.
- 멈춤: T-1 저장 즉시. 재시도 안 함 = `api_key_missing` · `expected_date_unknown` · 무결성 오류라도 기준일이 이미 T-1(`_t1_stored` :74). 밀린 시각은 1회로 합친다.
- 저장 최신일 재확인(`latest_confirmed` :115 · 리뷰 LENS1-1): 이번 실행이 첫 시도 전 저장 최신일을 `ok` 로 확인했고 그 시도에 무결성 오류(`evidence_write_failed` · `store:` · `readback_mismatch`)가 없을 때만 `recheck_latest=False`(그 뒤 빠진 날만 · store `_fetch_dates(include_latest=False)` :227). 아니면 저장 최신일을 다시 포함한다 — 첫 시도가 09-17 에서 예외로 멈춰도 09-17 정정이 영영 빠지지 않게.
- 기록(키 · 가격 값 없음): `kospi_attempts` = 시도별 `kind` · `slot` · `at_kst` · `calls`[date · rows · result · error_type] · `result` · `as_of` · `error` · `error_type` · `kospi_retry` = `mode` · `slots` · `retries` · `stopped`(t1_stored · not_retriable · deadline · pending · no_retry_window · slots_exhausted) → 배치 상태 JSON(mdb `write_batch_state` 선택 인자).
- 다시 세기(`apply` :264): 재시도가 있었으면 `benchmark_refresh.kospi` = 이번 실행 합친 결과(상태 · 기준일 · 오류 = 마지막 시도 · `calls` · `replaced` · `written` · `rows_written` 합 · `attempts` · `corrections` 이어 붙임 · `before` = 첫 시도 · `evidence_path` = 마지막) · benchmark 상태 다시 계산(단계 예외 `unexpected:` 가 있으면 `failed` 유지 :278) · `kospi_as_of` 갱신 · batch 가 종료 status 를 다시 정한다(:197-198) — KOSPI 만 늦게 성공한 날은 `success_with_benchmark_failure` → `success`.
- 09:20 `--krx-only` = KOSPI 호출 0(재시도 객체를 만들지 않음). 네 번 모두 실패 = 저장 기준일 그대로 → `kospi_freshness` 판정 `source_stale` · Telegram 경고 없음(`batch_failure_reasons` 는 KOSPI 를 보지 않음).
- 테스트(kospi_retry 39): `test_0810_not_t1_then_0815_success_stops_and_etf_is_unaffected` · `test_etf_ok_at_0810_while_kospi_succeeds_at_0820` · `test_etf_fails_every_slot_while_kospi_ok_at_0810_makes_no_extra_call` · `test_kospi_retries_while_etf_still_retrying_and_etf_goes_first_at_shared_slot` · `test_etf_fails_every_slot_kospi_still_retries_at_0824` · `test_etf_stage_exception_still_runs_remaining_kospi_slots` · `test_all_four_slots_fail_stale_etf_on_time_no_telegram_notice` · `test_krx_only_0920_never_calls_kospi` · `test_first_attempt_stopped_on_stored_latest_is_rechecked_by_the_retry` · `test_latest_confirmed`(6) · `test_retry_rechecks_until_the_stored_latest_is_confirmed` · `test_benchmark_stage_exception_stays_failed_after_kospi_retry_success` · `test_first_attempt_correction_evidence_survives_the_retry_merge` · `test_attempt_records_have_no_key_or_price_values` 등.

**STEP 4 — KOSPI 화면 3건 · 정비 큐 (PC 화면만)**

| # | 코드 | 문구 · 동작 |
|---|---|---|
| 4-1 제목 | `MarketContextCard.tsx:114` | `KOSPI (보조)`(옛 `(KS11) KOSPI (보조)`) · 프론트 소스의 `KS11` 은 주석 1곳(:112)뿐 |
| 4-2 출처 | `lib/kospiStatus.ts:51` `KOSPI_SOURCE_LINE` 한 상수 | `출처: 한국거래소(KRX)` — 시장 배경 카드 KOSPI 칸 맨 아래 한 줄(`MarketContextCard.tsx:124` · 상태와 무관하게 늘) · 「오늘의 투자 점검」 KOSPI 카드 하단 한 줄 · AI 복사 텍스트 KOSPI **값 줄** 끝(`marketDiscoveryCopyText.ts:153` · 값이 없는 상태 줄은 그대로 · 「AI Sessions로 넘기기」 질문도 같은 생성기) · 차트에는 따로 달지 않음 |
| 4-3 기준일 | `today/KospiHeadline.tsx:28-30` · `:142-143` | `마지막 자료 기준일` = KOSPI `as_of_date`(백엔드 `MarketContextKospi` 에 이미 있음) · 없으면 날짜를 내지 않고 KODEX200 날짜로 대신하지 않는다 |
| 정비 큐 (PLAN STEP 7-4) | `today/maintenanceQueue.ts:85-96` | KOSPI 화면 판정이 정상 · 휴장일이 아니면 VIX 지연과 같은 모양 항목 1개(`heavy` · 이동 「요즘 잘 오르는 ETF」 · 버튼 `시장 자료 업데이트로` · 시장 응답 성공일 때만) · 문구 = 확정 사유 문장 끝 마침표를 뺀 것 + 기준 줄이 있으면 ` (기준 줄)` · ⓘ = 상태 한 줄(`kospiStatusText`) · 응답에 시장 배경이 없으면 「자료원 확인 실패」 항목 |

테스트: `KospiStatusSurfaces.test.tsx` describe 「설계자 RESULT STEP 4-1 · 4-2」(:227) · 「4-2 · 4-3」(:243) · 「4-2 — AI 복사 텍스트 출처」(:270) · 「STEP 4 · PLAN STEP 7-4 — 정비 큐」(:290) · `TodayInvestmentCheckView.test.tsx:353`(실화면 통합) · `KospiStatusNote.test.tsx` 제목 검사 2곳 `/^KOSPI \(보조\)/`. 무력화 6종(KS11 복구 · 출처 제거 2 · KODEX200 날짜 · 정비 항목 제거 · lib → components import) 각각 5 · 2 · 3 · 7 · 1 · 1건 실패.

**STEP 5 — 프론트 의존 방향**

- 판정 · 문구(`kospiStatusView` :74 · `kospiStatusText` :126 · `kospiValuesUsable` :136 · 배지 · 사유 문구표 · 타입 · `KOSPI_SOURCE_LINE`)를 `frontend/lib/kospiStatus.ts` 로 옮겼다(import 는 `./api` 타입뿐 · React · JSX 없음). 문구는 옮기기 전과 바이트 같음(차이 = `QueryPhase` → `KospiQueryPhase` 이름 · 새 출처 상수).
- `KospiStatusNote.tsx` 153 → 51 — 배지 · 상태 줄 컴포넌트만 남기고 lib 를 import(다시 내보내기 없음). 호출부(`KospiChart.tsx:20` · `TransferToAISessionsCard.tsx:25` · `lib/etfExposureDraft.ts:17` · `lib/marketDiscoveryCopyText.ts:21` · 테스트 2)가 lib 를 import.
- 검사 2중: `frontend/eslint.config.mjs` `lib/**` 에 `no-restricted-imports`(regex · 별칭 · 상대 경로) + `frontend/lib/dependencyDirection.test.ts`(lib 모든 `.ts/.tsx` 의 import · export from · 동적 import · require 검사 · 검사기 자기 점검 1건). eslint 는 동적 import · require 를 못 잡고 vitest 가 맡는다. 워킹트리 `frontend/lib` 에서 `app/components` 로 가는 import = 0(grep).

**STEP 6 — 승인 항목 · 09:20 채우기 한도 · 기술부채**

- 승인(설계자 STEP 6 · 코드 그대로): S&P500 직전 행 = 바로 앞 세션 · FDR 요청당 20초 · 단계 180초 · 배치 실패 + 낼 내용 없음 → 머리 + 고지 1줄 · 15:40 `신규 진입 검토 생략 N회` · 차트 배지 · 경고색 · KOSPI T-1 판정은 화면 API · 과거 재현은 별도 평가 기준일 · 09:20 T-1 재조회 없이 창 누락일만.
- ledger(backfill · 신규): 파일 `state/market/krx_backfill_ledger.json`(KRX 표와 같은 폴더 · `{"date_kst": …, "calls": {날짜: n}}` · `.gitignore:199` `krx_backfill_ledger.json*` = 저장 중 임시 파일 포함). 범위 = 목표일로 끝나는 21거래일 창 안 빠진 날(목표일 제외). **같은 날짜 KST 하루 1회**(08:10 첫 채우기 · 같은 실행 `backfill_retry` · 09:20 · 수동 재실행 합산). 부르기 **전에** 원자적 기록 · 기록 못 쓰면 부르지 않음 · 오늘 쓴 ledger 를 못 읽으면 멈춤(지난날 파일이면 새로 시작) · KST 날짜가 바뀌면 새로 시작 · 조회 오류면 멈춤. 목표일 T-1 시각표 시도는 ledger 밖.
- 호출 기록(`fill_missing` 반환 → 배치 상태 · 09:20 기록 `krx_backfill` = `{backfill, backfill_retry}` · batch :409-411): `missing_before` · `called` · `skipped_called_today` · `filled` · `failed` · `stopped` · `calls_today`.
- 채우기 시점(kts :326-341): 목표일 조회가 원천에 닿은(`fetch_error` 아님) 첫 시도 뒤 · 원천 불통 중에는 미룬다(리뷰 LENS2-F1 — 불통 중에 부르면 ledger 가 그 날짜를 오늘 부른 것으로 남겨 원천이 돌아와도 못 부름). `backfill_retry` = 첫 채우기가 `stopped`(원천 오류 · 마감)였고 뒤 시도에서 T-1 을 받았을 때 한 번 더(오늘 안 부른 날만). 이미 받은 날(09:20 · 재실행)도 채운다(:288-293 · 빈 날 없으면 조회 0).
- 테스트: consumer_isolation `test_same_window_date_not_called_twice_across_0810_retry_0920_rerun` · `test_new_kst_day_resets_ledger` · `test_fill_is_bounded_to_21_trading_day_window` · `test_unreadable_ledger_written_today_stops_fill` · `test_unreadable_ledger_from_previous_day_starts_fresh` · `test_ledger_write_failure_makes_no_fill_call` · `test_default_ledger_sits_next_to_krx_table` · krx_batch `test_s10_backfill_retried_once_after_later_t1_success` · `test_s10_backfill_waits_while_target_fetch_cannot_reach_source` · `test_s10_no_backfill_when_every_target_attempt_is_fetch_error`.
- 기술부채: `docs/backlog/BACKLOG.md` §16 첫 항목(:666) — `scripts/ops02c/reverse_verify_guards.py` ④ 미성립 원인 = 뒤쪽 `POLICY_RANGES` 검사(`app/intraday_config/schema.py:243-248`)가 같은 입력을 다시 거부하는 이중 가드 · `7e60f536` 에서도 같음.

**STEP 7 — 검증 보완 10항목**

| # | 항목 | 결과 |
|---|---|---|
| 1 | 가격 기준 계약 | price_basis 27건 통과(+ holdings 10) |
| 2 | 대표 설정 없음 · 상장폐지 · 일부 누락 소비자 격리 | consumer_isolation 27건 통과 |
| 3 | KOSPI 08:10 실패 후 후속 슬롯 성공 | `test_0810_not_t1_then_0815_success_stops_and_etf_is_unaffected` · `test_etf_ok_at_0810_while_kospi_succeeds_at_0820` · `test_first_attempt_stopped_on_stored_latest_is_rechecked_by_the_retry` 통과 |
| 4 | KOSPI 네 번 모두 실패 | `test_all_four_slots_fail_stale_etf_on_time_no_telegram_notice` · `test_etf_fails_every_slot_kospi_still_retries_at_0824` 통과 |
| 5 | KOSPI 출처 · 기준일 UI | KospiStatusSurfaces 21건 · TodayInvestmentCheckView 38건 통과 |
| 6 | 프론트 의존 방향 | dependencyDirection 2건 통과 · eslint rc 0 · lib → components grep 0 |
| 7 | 백엔드 전체 회귀 | 2,703 passed / 0 failed (exit 0 · 371.31s · 1 warning = fastapi testclient StarletteDeprecationWarning 제3자 · 2026-10-01 15:4x · 검증자 r1 정정까지 모든 코드 변경 뒤 마지막 1회) |
| 8 | 프론트 전체 · tsc · eslint | vitest 24파일 287건 · tsc rc 0 · eslint rc 0 |
| 9 | 프론트 production build | 저장소 밖 사본에서 `npx next build` rc 0(머리 `PRODUCTION_BUILD`) — dev 서버가 켜져 있어 저장소 안 build 금지 규칙(DEV_RULES §10) 준수 |
| 10 | PC 운영 파일 hash 불변 | PC `state/` · `logs/`(`state/ml/research` 제외) 226파일 sha256 전체 회귀 전후 동일(diff 0바이트) |

### 1-3. 설계자 검증 시나리오 12개 (설계서 STEP 12)

| # | 시나리오 | 테스트 |
|---|---|---|
| 1 | 08:10 바로 T-1 | krx_batch `test_s1_t1_returned_at_0810_first_attempt` · briefing `test_t1_present_shows_index_with_t1_basis` · intraday `test_t1_loaded_shows_entry_with_trend_basis_line` |
| 2 | 08:15 · 08:20 · 08:24 중간 성공 | krx_batch `test_s2_success_on_later_slot`(3) · kospi_retry `test_0810_not_t1_then_0815_success_stops_and_etf_is_unaffected` |
| 3 | 08:27 까지 미공개 | `test_s3_not_published_until_0827_fails_closed` · `test_no_new_attempt_after_deadline_when_attempts_are_slow` · kospi_retry `test_deadline_passed_makes_no_new_attempt` |
| 4 | T-2 만 반환 | `test_s4_only_t2_returned_is_not_success` · briefing `test_t2_only_omits_index_with_designer_line_and_no_t2_leak` · intraday `test_t2_only_omits_entry_but_keeps_avoid` · kospi `test_t2_only_is_stale_even_though_old_lag_rule_passed` |
| 5 | 0행 · 급감 · 대표 ETF 일부 누락 | `test_s5_bad_response_is_retried_and_never_partially_saved`(not_published ×2 · row_drop · invalid_snapshot ×3) · `test_s5_row_ratio_boundary_is_95_percent_of_previous_load` · 대표 누락 = 적재 성공 · 장중 진입만 생략(consumer_isolation `test_partial_representatives_missing_omits_entry_keeps_avoid` · `test_delisted_representative_load_ok_briefing_ok_entry_omitted`) |
| 6 | FDR 일부 실패 · timeout | krx_batch_stages `test_s6_*` 5건 · `test_real_refresh_price_history_counts_timeout_as_ticker_failure` |
| 7 | KOSPI 만 실패 | kospi `test_kospi_only_failure_is_pc_only_no_telegram_notice` · `test_fetch_exception_stops_immediately_and_is_source_failure` · kospi_retry `test_all_four_slots_fail_stale_etf_on_time_no_telegram_notice` |
| 8 | 미국 휴장일 | briefing_calendar `test_expected_session_weekday_monday_and_holidays`(7) · `test_expected_session_dst_est_and_early_close_boundaries`(8) · `test_missing_year_uses_weekday_fallback_conservatively` |
| 9 | 한국 휴장일 | krx_batch `test_s9_expected_t1_skips_korean_holidays` · `test_s9_sync_fetches_only_the_calendar_t1_after_holidays` · briefing `test_korean_holiday_expected_day_skips_the_holiday` · holdings `test_base_day_skips_holidays` · intraday `test_trend_window_uses_trading_days_across_holiday` |
| 10 | 하루 가격 누락의 5일 · 20일 | krx_batch `test_s10_*` 9건 · intraday `test_missing_d5_date_fails_closed_instead_of_shifting` · `test_missing_non_required_day_keeps_calendar_d20_value` · holdings `test_batch_failure_does_not_slip_the_20_day_base` · consumer_isolation ledger 7건 |
| 11 | 09:20 복구 성공 · 실패 | krx_batch_stages `test_s11_*` 4건 · krx_batch `test_s11_already_loaded_run_fills_window_gap_without_t1_refetch` · kospi_retry `test_krx_only_0920_never_calls_kospi` |
| 12 | 재실행 시 중복 저장 · 중복 발송 없음 | `test_s12_rerun_does_not_refetch_or_duplicate` · `test_s12_t1_judgment_is_not_overwritten_by_later_failure` · `test_s12_existing_t1_rows_are_kept_only_when_identical` · `test_s12_existing_t1_rows_that_differ_are_replaced_and_read_back`(3) · briefing `test_batch_notice_once_per_day_through_runner` · kospi `test_rerun_same_day_rechecks_t1_once_and_rewrites_nothing` · consumer_isolation `test_same_window_date_not_called_twice_across_0810_retry_0920_rerun` · `test_poc3_02d_ops02_regular_push_contract.py::test_market_next_day_same_fp_sends_and_same_day_rerun_is_duplicate` |

새 백엔드 테스트 10파일 292건(`pytest --collect-only` 실측 2026-10-02 · 커밋 7feddf2c 때 286): briefing 25 · briefing_calendar 45(7feddf2c 40) · consumer_isolation 27 · holdings 10 · intraday 18 · kospi 38 · kospi_retry 39 · krx_batch 47(7feddf2c 46) · krx_batch_stages 16 · price_basis 27. 새 프론트: `KospiStatusSurfaces.test.tsx` 21건(`vitest list`) · `frontend/lib/dependencyDirection.test.ts` 2건.

### 1-4. RED · 무력화

- **RED 1차** — `7e60f536` 사본에 새 테스트만: briefing 25/25 실패 · intraday 16/18 실패(통과 2 = `test_avoid_only_body_has_no_trend_line` · `test_summary_without_omission_is_byte_identical` — 생략이 없으면 기존과 같아야 한다는 보존 테스트) · briefing_calendar · holdings · kospi · krx_batch · krx_batch_stages 수집 오류 · KospiStatusSurfaces 7/9 실패(당시 9건).
- **RED 보완** — 보완 전 스테이지 상태 사본에 이번 라운드 새 테스트만: consumer_isolation 27 · kospi_retry 39 · price_basis 27 모두 수집 오류(`krx_backfill` · `market_benchmark_kospi_retry` · `holdings_price_basis` 없음 — **import 단계 RED**) · `dependencyDirection.test.ts` 1/2 실패(`kospiStatus.ts` 없음 · 스테이지 상태 실제 위반 2건 `lib/etfExposureDraft.ts:17` · `lib/marketDiscoveryCopyText.ts:21`). 리뷰 LENS3 이 수정된 기존 백엔드 테스트를 스테이지 코드에 돌린 결과: low_frequency_push 7 · runtime_runner_forwarding 1 · holdings_risk_alert_runner 22 · holdings_selection 6 · holdings_selection_state 2 · ops01_holdings_risk_flow 39 · ops03_intraday 3 실패 · intraday_alert_flow_through 18 실패 + 24 오류 · ops03_holdings · krx_batch 수집 오류. `7e60f536` 사본의 프론트: KospiStatusSurfaces · KospiStatusNote 로드 실패 · TodayInvestmentCheckView 1 실패. 동작 차이의 탐지는 아래 무력화가 보인다.
- **무력화 1차**: 구현 A 7 · B 9 · C 8 · D 11 전부 실패 · 리뷰 LENS1 24 중 19(미탐지 5 → 테스트 추가) · LENS3 114 중 104(실제 공백 7 → 수정 · 동작 동일 3) · 수정 M1~M14 14/14 · 리드 보강 2/2.
- **무력화 보완**: STEP 1 18종(ETF FDR 사용 · fallback · 혼합 · 가드 끔 · 허용 폭 5% · 미상 → 개별주 · 개별주 KRX 읽기 · 문구 · evidence 누락 · 읽기 helper 표 생성 등) · STEP 2 · 6 20종(② 되살림 · CSV `refresh_due` 에 섞음 · 설정 없음을 ok · 장중 관문 끔 · ledger 무시 · 미기록 · 날짜 안 바뀜 · 손상 파일 · 기록 실패에도 호출 · 창 밖 채움 등) · STEP 3 22종 · 프론트 6종 — 전부 탐지. 리뷰 LENS3 94종 중 90 탐지 · 미탐지 4 = 실제 공백 3(ETF 전부 실패 시 KOSPI 08:24 · ETF 단계 예외 뒤 KOSPI 남은 시각 · 장중 대표 T-1 날짜 조건 → 테스트 추가) + 동작 동일 1(정비 큐 `&& kospi.reason`). 수정 라운드 9종 9/9(기준 실패 집합과 비교). 리드 개별주 늘 닫힘 1종(3건 실패).

### 1-5. 리뷰 지적과 처리

**보완 라운드** (리뷰 4개 → 수정 라운드 → 리드)

| 지적 | 출처 | 처리 |
|---|---|---|
| KOSPI 재시도가 저장 최신일 재확인을 건너뜀 → 첫 시도 예외 시 09-17 정정이 영영 빠짐(격리 DB 재현) | LENS1-1 | FIXED — retry `latest_confirmed`(:115) · 테스트 3 |
| 대표 커버리지 운영 상태를 읽는 곳이 없음(화면 미표시) | LENS1-2 | SKIPPED — 화면 새 행 · 새 문구 = 설계자 · 사용자 결정(§7-3 (3)) |
| 설정 읽기 실패가 `policy_disabled` 로 기록 | LENS1-3 | FIXED — `config_read_error`(:169 · :424-437) · 15:40 요약 사유(`holdings_selection_flow.py:257-263`) · 테스트 4 |
| 개별주 가드가 T-1 하루만 봄 | LENS1-4 | 리드 결정 — 개별주 파생값 늘 fail-closed(KRX 공식 종가로 혼합 확정 · §1-2 STEP 1) |
| B3 문구 · 발동 조건이 STEP 1 뒤 사실과 다름 | LENS1-5 | 주석 FIXED(`render.py:72-78` · 개별주 늘 닫힘 뒤 리드가 다시 고침) · 문구 · 조건은 SKIPPED(사용자 승인 문구 · 확정 PLAN STEP 7-3 입력 · §7-3 (2)) |
| 구간 종가가 빠지면 `고점 대비` 를 표시 없이 생략 | LENS1-6 | SKIPPED — 기존 설계자 확정 '보조값만 생략' · R1-2 해석(§6) |
| `krx_store` 모듈 설명 '예외는 하나뿐' 이 사실과 다름 | LENS1-7 · LENS4-F1 | FIXED — `krx_store.py:16-26` |
| 채우기 중 `fetch_error` 난 창 날짜를 T-1 성공 뒤에도 그날 다시 못 부름 | LENS1-8 | 목표일 원천 불통 경우 FIXED(LENS2-F1) · 나머지 SKIPPED — 설계자 STEP 6 '같은 날짜 하루 1회' 와 충돌(§7-3 (5)) |
| 08:30 기초지수 '필요 종목 커버리지' 전용 관문 없음 | LENS1-9 | SKIPPED — 기존 관문으로 판정(§1-2 STEP 2 · §6) |
| 출처 줄이 KODEX200 블록 아래 카드 끝 → KODEX200 에도 적용되는 듯 읽힘 | LENS1-10 | SKIPPED — 줄 위치 = 사용자 실화면 결정(§7-1) |
| 08:10 원천 불통 때 빈 날 채우기가 그날 막힘 | LENS2-F1 | FIXED — kts :326-334 · 테스트 2 |
| 벤치마크 단계 예외 뒤 KOSPI 재시도 성공 → `partial` 로 기록 | LENS2-F2 | FIXED — retry :278 · 테스트 1 |
| ETF 분할 같은 가격 사건 가드 없음 | LENS2-F3 | SKIPPED — 설계 수준(§5 · §7-3 (4)) |
| ETF 네 시각 모두 실패 시 KOSPI 08:24 재시도 테스트 없음 | LENS3-1 | FIXED(테스트) `test_etf_fails_every_slot_kospi_still_retries_at_0824` |
| ETF 단계 예외 뒤 KOSPI 남은 시각 테스트 없음 | LENS3-2 | FIXED(테스트) `test_etf_stage_exception_still_runs_remaining_kospi_slots` |
| 장중 대표 T-1 날짜 조건 테스트 없음 | LENS3-3 | FIXED(테스트) `test_delisted_representative_with_window_rows_still_omits_entry` |
| 새 공식 CSV 소비자(hpb `DEFAULT_META_DIR`)가 테스트 격리에서 빠짐 | LENS4-F2 | FIXED — `tests/conftest.py:277-282` |
| 공용 테스트 대역이 테스트 모듈 안 | LENS4-F3 | FIXED — `tests/_helpers.py:307-351` · import 12곳 |
| `sector_signal.py` 599줄 | LENS4-N1 | 결함 아님(600 미만 · §9) |
| 기존 테스트의 네트워크 시도 18건(yahoo · naver · 기존 경로) | LENS4-N2 | 이번 작업 무관 · 새 모듈 경유 0 · 미처리 |

**1차 라운드** (처리 끝 · 요약): 기존 테스트 2건 실패 → `_fixtures.py` 캘린더 고정 · 09:20 상태 파일 `.gitignore:196` · 캘린더 없는 해 fail-closed(L2-2 · 종료 커밋에서 한국 거래일 계약에 맞게 되돌림 · §11) · d5 · d20 저장 없음 → 생략 집계(L2-3) · FDR 단계 180초(L2-5) · `MIN_SLOT_GAP` 60초(L2-6) · 09:20 금지 호출 테스트 기록형으로(L3①) · 미탐지 가드 5 테스트 추가 · naive 시각 테스트 04:30 · KOSPI ② 전체 대조(F3 → §1-6) · 09:20 · 재실행 창 채우기(F5 → 이번 라운드 ledger 로 바뀜 · §1-2 STEP 6) · 조정/무조정 혼합(F2 → 이번 라운드 STEP 1 로 DONE).

### 1-6. KOSPI 09-17 정정 — 영향 날짜 전체 대조 (확정 계약 9 ②)

OCI 읽기 전용 실측(2026-09-30 05:4x KST · `ssh oci-krx` · sqlite `mode=ro` · 쓰기 0 · 리드).

- OCI `market_benchmark_daily_price` KOSPI 3,052행(2014-04-10 ~ 2026-09-17): source `NAVER_FDR` 2,870행 · `FinanceDataReader/KS11` 182행.
- 공식 기준값 = PC 연구 DB(`state/ml/research/krx_etf_universe.sqlite` · KRX `etf_bydd_trd` 응답 원문)의 `IDX_IND_NM='코스피'` ETF `OBJ_STKPRC_IDX` 2,718일(2015-08-24 ~ 2026-09-21 · 같은 날 서로 다른 값 0일).
- 공통 2,716일 대조 → **불일치 1일 = 2026-09-17**(OCI 6724.34 `FinanceDataReader/KS11` vs 공식 6715.41). 정지된 원천(FDR KS11) 182행은 전부 대조됐다. 대조 기준 없는 336행 = 2014-04-10 ~ 2015-08-21 `NAVER_FDR`(연구 DB 시작 전 · 정지 원천 아님).
- 코드 경로: `_fetch_dates`(store :227)가 저장 최신일(09-17 · 포함)부터 기대 T-1 까지 거래일마다 1회 조회 → `_store_fetched`(:427)가 값 · source 가 다른 행이면 **덮기 전에** 증거 JSON(기존 값 · source · created_at · 행 sha256 · 새 값 · `stage=before_write`)을 쓰고, 못 쓰면 저장 0 → upsert → 날짜별 read-back → 증거에 `after_write`. 첫 시도가 09-17 에서 멈추면 재시도가 09-17 을 다시 포함한다(§1-2 STEP 3).

---

## 2. 변경된 파일 목록

이 절 = 커밋 `7feddf2c` 의 파일(102파일). 종료 커밋(한국 거래일 계약 정정)의 파일 · 줄 수는 §11.

줄 수 = `wc -l` 기준 커밋(`git show 7e60f536:<파일>`) → 작업 트리 · 2026-09-30 20:4x KST `git status --short --untracked-files=all` 의 모든 파일을 다시 쟀다. `(보완)` = 이번 라운드 신규(지금은 모두 git 에 추가됨 · staged · §10).

**백엔드 — 수정**
- `app/market_briefing/flow.py` 429 → 465 · `render.py` 212 → 246 · `krx_store.py` 298 → 542 · `krx_sync.py` 437 → 501
- `app/three_push_runtime/market_data_batch.py` 375 → 507 · `runner_market_briefing.py` 161 → 247
- `app/trading_day_lag.py` 125 → 268 · `app/oci_startup_status.py` 279 → 331
- `app/market_benchmark_store.py` 273 → 537 · `market_benchmark_batch.py` 272 → 310 · `market_benchmark_freshness.py` 122 → 177 · `market_regime.py` 470 → 493 · `market_topn.py` 405 → 410 · `market_refresh_service.py` 490 → 499
- `app/api_market_topn.py` 188 → 196 · `app/api_market_topn_service.py` 439 → 452
- `app/runtime_evidence/sector_signal.py` 408 → 599 · `intraday_alert_flow.py` 470 → 577 · `intraday_alert_render.py` 287 → 321 · `intraday_checkup_tally.py` 192 → 210
- `app/runtime_evidence/holdings_risk.py` 426 → 428(주석) · `holdings_risk_flow.py` 508 → 538 · `holdings_selection.py` 354 → 372 · `holdings_selection_flow.py` 424 → 459 · `holdings_selection_render.py` 147 → 152 · `holdings_selection_source.py` 118 → 142

**백엔드 — 신규**: `app/market_briefing/krx_target_sync.py` 494 · `app/us_trading_calendar.py` 367 · (보완) `app/market_briefing/krx_target_checks.py` 293 · `app/market_briefing/krx_backfill.py` 184 · `app/intraday_config/representatives.py` 99 · `app/market_benchmark_kospi_retry.py` 306 · `app/runtime_evidence/holdings_price_basis.py` 293

**데이터 — 신규**: `state/market_meta/nyse_holidays_2026.csv` 21 · `nyse_holidays_2027.csv` 20 (ignore 대상 아님 · 커밋해야 OCI 로 간다)

**스크립트 — 수정**: `scripts/run_oci_market_data_batch.py` 343 → 563 · `scripts/build_market_briefing_mockups.py` 465 → 538 · `scripts/ops02b2/reverse_verify_guards.py` 427 → 434

**프론트 — 수정**: `frontend/app/components/today/KospiChart.tsx` 101 → 133 · `today/KospiHeadline.tsx` 144 → 151 · `today/maintenanceQueue.ts` 168 → 183 · `KospiStatusNote.tsx` 153 → 51 · `KospiStatusNote.test.tsx` 307 → 307 · `MarketContextCard.tsx` 142 → 148 · `DashboardView.tsx` 769 → 774 · `DashboardView.test.tsx` 253 → 275 · `OciStatusView.tsx` 214 → 219 · `OciStatusView.test.tsx` 145 → 161 · `TodayInvestmentCheckView.test.tsx` 781 → 810 · `TransferToAISessionsCard.tsx` 206 → 211 · `frontend/lib/etfExposureDraft.ts` 150 → 155 · `frontend/lib/marketDiscoveryCopyText.ts` 392 → 396 · `frontend/eslint.config.mjs` 29 → 47

**프론트 — 신규**: `frontend/app/components/KospiStatusSurfaces.test.tsx` 373 · (보완) `frontend/lib/kospiStatus.ts` 141 · `frontend/lib/dependencyDirection.test.ts` 88

**테스트 — 신규**: `tests/test_poc3_02d_ops03_briefing.py` 462 · `_briefing_calendar.py` 388 · `_holdings.py` 273 · `_intraday.py` 490 · `_kospi.py` 619 · `_krx_batch.py` 811 · `_krx_batch_stages.py` 515 · (보완) `_consumer_isolation.py` 719 · `_kospi_retry.py` 868 · `_price_basis.py` 534

**테스트 — 수정**: `tests/_helpers.py` 295 → 351(보유 가격 기준 대역) · `tests/conftest.py` 572 → 582(KOSPI 네트워크 경계 가드 · hpb CSV 폴더 격리) · `tests/low_frequency_push/_fixtures.py` 306 → 352 · `low_frequency_push/test_runner_fail_closed.py` 420 → 424 · `runtime_evidence/test_runtime_runner_forwarding.py` 165 → 170 · `test_holdings_risk_alert_runner.py` 809 → 814 · `test_holdings_selection.py` 675 → 688 · `test_holdings_selection_state.py` 796 → 806 · `test_intraday_alert_flow_through.py` 1298 → 1342 · `test_intraday_alert_render.py` 467 → 471 · `test_market_benchmark_freshness.py` 683 → 704 · `test_market_benchmark_store.py` 469 → 68 · `test_market_briefing_batch.py` 1137 → 1140 · `test_market_briefing_contracts.py` 1406 → 1427 · `test_market_briefing_flow_through.py` 752 → 791 · `test_market_topn_api.py` 788 → 824 · `test_oci_market_data_refresh.py` 762 → 768 · `test_poc3_02d_ops01_holdings_risk_flow.py` 947 → 956 · `test_poc3_02d_ops02_kospi_display.py` 376 → 348 · `test_poc3_02d_ops02_regular_push_contract.py` 221 → 227 · `test_sector_signal.py` 461 → 509

**기타 — 수정**: `.gitignore` 282 → 289 (`state/market/oci_krx_reinforcement_state.json` :196 · `state/market/krx_backfill_ledger.json*` :199 · `state/market/kospi_source_corrections/` :249)

**문서 — 신규**: 설계서 685(설계자 RESULT 판정 원문 포함) · PLAN 384 · 이 결과서

**문서 — 수정**: `docs/PROGRAM_TRUTH.md` 696 → 887 · `docs/STATE_LATEST.md` 2764 → 2822 · `docs/KILL_SWITCHES.md` 188 → 188 · `docs/PROJECT_ORIGIN_INTENT.md` 367 → 367 · `docs/ASSUMPTIONS.md` 342 → 342 · `docs/MASTER_PLAN.md` 216 → 216(시장 브리핑 08:00 → 08:30 개정 표기 · 줄 수 불변) · `docs/backlog/BACKLOG.md` 697 → 704(§16 기술부채) · `docs/ai_result/POC3/POC3-OPS-02B-2_MARKET_BRIEFING_MOCKUPS.md` 223 → 557 · `docs/handoff/OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` 346 → 378(OPS-03 cron 3줄 절) · OPS-02 첫 자연 발송 관측 기록 — `docs/ai_result/POC3/POC3-02D-OPS-02_RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS_RESULT.md` 662 → 662 · `docs/handoff/POC3-02D-OPS-02_RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS_HANDOFF_2026-09-29.md` 144 → 144

**이번 단계 아님**: `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`(untracked · 사용자 소유 · 커밋 제외 · 손대지 않음)

## 3. 신규 추가된 의존성

없음 — 새 라이브러리 0. 외부 호출 경로는 1차의 KRX `idx/kospi_dd_trd`(기존 키 · 사용자 승인 2026-09-29) 하나이고, 보완 라운드의 KOSPI 재시도는 같은 경로를 08:15 · 08:20 · 08:24 에 다시 부를 뿐이다. 리드의 KRX `sto/stk_bydd_trd` 1회 조회는 원인 확인용 읽기이고 코드 경로에 없다(`app/` grep = hpb docstring 1곳). production build 는 기존 `node_modules` 를 썼다.

## 4. 지시문 외 변경

- **1차 라운드 판단 — 설계자 RESULT STEP 6 에서 승인**: S&P500 직전 행 조건 · FDR 단계 180초 · 고지만 발송(`render_notice_only`) · 15:40 생략 요약 · 차트 배지 · KOSPI T-1 판정 화면 API 한정 · 09:20 창 채우기. 승인 밖으로 남은 1차 변경: `MIN_SLOT_GAP` 60초(L2-6) · 캘린더 없는 해 fail-closed(L2-2 · 종료 커밋에서 되돌림 · §11) · 보유 장중 위험 경로에도 캘린더 축(`holdings_risk_flow.py`) · 「OCI 운영·적용」 거래일 달력 행(종료 커밋에서 `거래일 기준`(한국) · `미국 휴장일 달력` 두 행으로 나눔 · §11) · 옛 FDR KS11 KOSPI 테스트 13건 제거(`test_market_benchmark_store.py` 469 → 68) · NYSE 공식 페이지 1회 조회(CSV 근거).
- **`backfill_retry` 조건 좁힘**: 1차 'failed 또는 stopped' → `stopped` 만 — ledger 뒤에는 `failed` 만 있으면 다시 부를 날이 없다.
- **채우기를 원천 불통 뒤로 미룸**(kts :326-334) — STEP 6 목적(09:20 누락일 보강)이 불통 중 ledger 기록으로 깨지지 않게(LENS2-F1).
- **KOSPI 재시도의 종료 status 다시 세기 · `benchmark_refresh.kospi` 합치기**(retry `apply`) — 첫 시도의 09-17 정정 증거 기록을 잃지 않게.
- **대표 판정 기록 이름 `representatives_refresh_due`** — 설계자 문장은 `refresh_due = true`. 기존 `refresh_due` 는 CSV 갱신 안내라 따로 두었다. T-1 행을 못 읽으면 `not_evaluated`(설계자 세 상태 밖).
- **ETF 구분에 KRX 표 적재 기록 추가**(CSV 날짜 뒤 상장 ETF) · 한쪽 원천만 읽히면 개별주로 확정하지 않고 미상.
- **R1-1 조합 문구 `20거래일 데이터 확인 불가`** — 설계자 문구 `데이터 확인 불가` 앞에 대상을 붙였다(§7-1).
- **테스트 기반**: 보유 대역 `tests/_helpers.py` 로 이동 · `conftest.py` hpb CSV 폴더 격리 · ETF 에 FDR 이력을 가정하던 기존 보유 테스트는 같은 이력을 KRX 표 대역으로 넣게 바꿈(단언 뜻 그대로) · `test_ticker_without_t1_row_is_excluded_alone` → `test_alternate_without_t1_row_is_excluded_alone`(대표 누락은 이제 구역 생략이라 사업군 단위 제외는 대체 종목으로 검증).
- **프론트 판단**: 출처 줄은 두 카드에서 상태와 무관하게 늘 한 줄 · 오늘 카드 하단은 두 확정 문구를 ` · ` 로 한 줄 · 시장 배경이 없는 응답은 정비 큐 「자료원 확인 실패」 항목 · `TodayInvestmentCheckView.test.tsx` `renderView` 대기 기준을 시장 판정 줄의 `· 기준일` 로.

## 5. 알려진 한계 / 미완성

- **종료 커밋은 OCI 미반영** — OCI 는 `7feddf2c` 로 돈다. 한국 거래일 계약 정정(§11)은 다음 OCI pull(거래일 15:40 뒤 · cron 변경 없음) 때 반영된다. 급하지 않다 — 「OCI 운영·적용」 거래일 행은 PC 가 계산하고(PC 백엔드가 이 코드로 뜨면 보인다), 나머지는 한국 연도 파일이 없는 해(2027~)에만 영향이 있다.
- **개별주 3종 파생값 늘 닫힘** — 정규장 종가 원천이 승인될 때까지 000660 · 005930 · 006400 의 20거래일 수익률 · `고점 대비` 가 나오지 않는다(§7-1 · §7-3 (1)).
- **ETF 분할 가드 없음** — 20거래일 창 안 액면분할이면 분할 전 무조정 T-20 종가와 분할 뒤 현재가를 비교한다(`classify_decline` 상한 없음 · LENS2-F3 · §7-3 (4)).
- **채우기 조회 오류 날짜는 그날 다시 부르지 않음** — 그 날짜가 d5 · d20 · T-20 이면 그날 08:30 기초지수 · 장중 진입 검토 · ETF 20거래일 값이 닫히고 다음 날 채워진다(§7-3 (5)).
- **대표 커버리지 상태는 PC 화면에 없음** — OCI 배치 상태 JSON · 09:20 기록 · 로그 · 장중 실행 기록에만 남는다(§7-3 (3)). 사용자에게 보이는 신호는 15:40 `신규 진입 검토 생략 N회` 뿐.
- **KRX 공개 완료 시각은 하루 실측뿐** — 공식 FAQ 는 '08:00 부터' 만 말한다. 첫 거래일(10-02)은 08:10:31 첫 시도에 T-1 을 받았다. 08:27 까지 못 받는 날의 빈도는 `krx_attempts` · `kospi_attempts` 로 쌓인다.
- **PC KOSPI** — PC 화면은 PC DB 를 읽는다(PC 수동 갱신 `POST /market/refresh` 때 같은 정정 · 전환). OCI 의 08:15~08:24 재시도는 PC 화면을 바꾸지 않는다.
- **KRX 표 잠금** — 보유 흐름은 `mode=ro` · sqlite 기본 대기로 읽는다. 그때 쓰기 잠금이면 그 회차만 ETF 파생값이 닫히고 `unreadable:OperationalError` 로 기록된다.
- **실행 기록 크기** — 가격 기준 evidence 가 보유 기록마다 붙는다(구현 에이전트 실측 32종 기준 약 6.7KB/회).
- **`scripts/ops02c/reverse_verify_guards.py` ④** — 기존 미성립 · 기술부채 등록(BACKLOG §16).

## 6. 다음 검증자(Codex)에게 알릴 점

- **주석 · docstring 정정(동작 변화 0)**: 개별주 늘 닫힘 변경 뒤 사실과 달라진 주석을 고쳤다 — `render.py:72-78`(B3 는 승인 문구 · FDR 단계만 실패한 날 보유 영향은 사실상 없음 · 발동 입력은 설계자 결정) · `holdings_price_basis.py:27` · `_stock_guard` docstring · `holdings_selection_flow.py:135`. 마지막 전체 회귀(2,703 passed)는 이 정정 · 검증자 r1 정정 뒤에 돌렸다.
- **개별주 늘 닫힘은 가드 무관**: `guard.ok` 가 true 여도 `reason=price_basis_mismatch` · `derived=blocked` 다(hpb :269-274). 가드는 그날 FDR 과 Naver 전일 종가 차이의 기록일 뿐이다. 테스트 이름 `test_stock_derived_values_always_fail_closed_guard_is_recorded` 로 바뀌었다(옛 날마다 판정 가드 테스트 대체).
- **해석 — R1-2(LENS1-6)**: STEP 1-2 '해당 파생값만 `데이터 확인 불가`' 를 20거래일 기준 종가에는 값 칸 문구로, 구간 종가(`고점 대비`)에는 기존 설계자 확정 '보조값만 생략' 으로 적용했다.
- **해석 — 08:30 커버리지(LENS1-9)**: STEP 2 '실제 필요한 종목의 커버리지' 를 기존 관문(정합성 조인 95% · 그룹당 유효 종목 2개 이상 · d5 · d20 창)으로 충족한다고 보았다. 약 196종만 따로 센 커버리지는 없다.
- **설정 읽기 실패 틱은 15:40 집계 틱이 아니다**: 사업군 평가가 없는 틱을 쓰면 빈 관측이 상태 파일에 남아 직전 관측을 회복으로 적을 위험(D2)이 있어 진단 필드 · `skip_reason` · 15:40 생략 사유에만 남긴다. 사업군 목록만 없는 경우는 생략으로 센다.
- **`latest_confirmed` 는 보수적**: 저장 최신일 결과가 `ok` 일 때만 확인으로 본다 — 그 날짜 응답이 비면 재시도마다 그 날짜를 한 번 더 부른다(최대 3회).
- **KRX 결과가 배치 상태에 늦게 들어갈 수 있다**: KOSPI 가 끝까지 실패하면 마지막 상태 쓰기가 08:24 + 조회 1회 뒤다. 그동안 `stage_status.krx = pending`. 08:30 브리핑은 KRX 전에 먼저 쓴 상태와 정합성 JSON 만 읽는다(`batch_failure_reasons` 는 `fdr_price` 만).
- **하루 1회 기록은 목표일 시도만 센다**: `run_krx_only` 의 `attempted = bool(krx_attempts)`(batch :470) — T-1 을 이미 받은 날의 채우기 호출은 `attempted=False` 로 남는다. 채우기 자체의 하루 1회는 ledger 가 보장한다.
- **증거 · ledger 파일은 git 밖**: `state/market/kospi_source_corrections/`(`.gitignore:249`) · `state/market/krx_backfill_ledger.json*`(:199).
- **`tests/test_market_benchmark_store.py` 469 → 68 줄 · 16 → 3건** — 폐지된 FDR KS11 · C7 lag 계약 테스트 13건 제거 · `test_poc3_02d_ops02_kospi_display.py` 수집 29 → 27건(상태표 17 → 15 · `lag` → `is_fresh` · T-2 기대값 `ok` → `stale`).
- **계산 경로 KOSPI T-1 판정은 화면 API(`/market/topn/latest`)에만**(설계자 STEP 6 승인) — 다른 `compute_topn` 호출부는 `today_kst` 없이 옛 판정(`market_regime.py:156` 분기).
- **KOSPI 오류 문자열 형식**: `source_stale:as_of=…,expected=…,lag=…[,reason=…]`(예전 `ref=`). 화면은 앞부분 `source_stale:` 만 본다.
- **국내 기준일 관문이 맨 앞**(`flow.py:203`) — 판정 파일이 없고 T-1 도 없으면 설계자 문구가 나간다(`test_flow_consumes_0720_result_only` 사전 데이터 변경).
- **KRX 관계식 검사 정의**: 저 ≤ 시 ≤ 고 · 저 ≤ 종 ≤ 고 · 시 · 고 · 저 모두 0 = 거래 없음 통과 · 일부만 0 = 위반(연구 DB 750거래일 720,356행 위반 0).
- **RED 보완은 import 단계**: 새 백엔드 3파일의 RED 는 새 모듈이 없어서다. 동작 차이는 §1-4 무력화(구현 66종 + 리뷰 94종 + 수정 9종)가 보인다.
- **KS-10 여유**: `sector_signal.py` 599(커밋 7feddf2c · 근접선 600 바로 아래 · 이번 라운드 대표 관문 +38) → 종료 커밋 595. 다음 변경 전에 분리를 고려해야 한다(LENS4-N1).
- **LENS4-N2**: 전체 회귀에서 socket 을 막으면 기존 테스트 18건이 yahoo · naver 접속을 시도한다(`refresh_vix` · `refresh_us_index` · `refresh_nav_universe` · HEAD 부터). 새 모듈 경유 0.

## 7. 사용자 확인이 필요한 항목

### 7-1. 보완 새 문구 · 화면 (사용자 확인 완료 — 2026-10-01 '화면과 문구 좋습니다')

| # | 위치 | 문구(정확히) | 확인할 것 |
|---|---|---|---|
| R1-1 | Telegram 「보유 종목 관찰 브리핑」(09:15 · 12:30 · 15:40) `■ 데이터 확인 필요 (N)` 그룹 종목 둘째 줄 값 칸 `holdings_selection_render.py:55` | `20거래일 데이터 확인 불가` | 설계자 문구 `데이터 확인 불가` 에 `20거래일` 을 붙인 조합 문구. 현재가는 정상인데 20거래일 기준 종가를 못 쓸 때. `현재가 조회 실패` 는 현재가 실패 때만. 그룹 제목 · 상태 identity 는 그대로 |
| R4-2b | PC 「오늘의 투자 점검」 KOSPI 카드 하단 1줄 `today/KospiHeadline.tsx:142-143` | `마지막 자료 기준일 YYYY-MM-DD · 출처: 한국거래소(KRX)` (KOSPI 기준일이 없으면 `출처: 한국거래소(KRX)` 만) | 두 확정 문구를 ` · ` 로 한 줄에 이은 모양 · 줄 위치(KODEX200 블록 아래 카드 끝 — KODEX200 에도 적용되는 듯 읽힐 수 있다 · LENS1-10) |
| R4-2c | AI 복사 텍스트 `[시스템 시장 판정]` KOSPI 값 줄 `lib/marketDiscoveryCopyText.ts:153`(「AI Sessions로 넘기기」 질문도 같음) | `- KOSPI 보조 기준: 20거래일 +1.20%, 60거래일 +3.40% · 출처: 한국거래소(KRX)` | 값 줄에만 붙는다 · 상태 줄(`- KOSPI 보조 기준: 기준일 지연 · …`)은 그대로. D2 의 '정상 · 휴장일이면 기존 줄 byte 동일' 은 이제 사실이 아니다(끝에 출처) |
| R4-4 | PC 「오늘의 투자 점검」 「자료 최신화 필요」(정비 큐) KOSPI 항목 `today/maintenanceQueue.ts:85-96` · 버튼 `시장 자료 업데이트로` | `KOSPI 원자료가 최근 거래일까지 갱신되지 않았습니다 (KOSPI 기준일 2026-09-28 · 1거래일 지연)` / `KOSPI 원자료를 불러오지 못했습니다 (…)` / `저장된 KOSPI 자료가 없습니다` / `KOSPI 수익률을 계산할 자료가 충분하지 않습니다 (KOSPI 기준일 …)` / `KOSPI 최신성 판정이 아직 실행되지 않았습니다` · ⓘ = 상태 한 줄 | 새 낱말 없음 · 모양(끝 마침표 뺌 · 괄호 기준 줄)은 VIX 항목을 따랐다 |

보완 화면 실화면 확인(STEP 4): R4-1 시장 배경 카드 제목 `KOSPI (보조)` · R4-2a 같은 카드 KOSPI 칸 맨 아래 `출처: 한국거래소(KRX)`(helper 작은 글씨 · 늘 한 줄) · R4-2b 오늘 카드 하단 날짜가 KOSPI 기준일인지(KODEX200 날짜 아님) · R4-4 정비 큐 KOSPI 항목(KOSPI 가 정상 · 휴장일이면 없음). PC 백엔드 · 프론트가 이 코드로 뜬 뒤 보인다.

**개별주 UX 영향(STEP 1 · 늘 닫힘)**: 000660 · 005930 · 006400 은 09:15(전체 현재 상태)와 변화가 없는 12:30 · 15:40(전체 현재 상태 발송)에 `■ 데이터 확인 필요` 그룹 · 값 칸 `20거래일 데이터 확인 불가` 로 나온다. 다른 종목 변화가 있는 12:30 · 15:40 은 변화분만 보내 세 종목이 나오지 않는다(identity `DATA_UNAVAILABLE_OR_STALE:ACTIVE` 가 슬롯 사이에 같다 · `holdings_selection_state.py:129-146` · `holdings_selection_flow.py:208-230`). 배포 뒤 첫 슬롯(다음 거래일 09:15)은 전체 현재 상태라 `■ 새로 선정` 이 아니다. 세 종목을 보유하는 동안 선정 0건 미발송(`skipped/no_selection`)은 생기지 않는다. 장중 위험 알림은 급락 판정 그대로이고 `고점 대비` 보조값만 빠진다.

### 7-2. 승인된 문구 (USER_TEXT_CHECK = APPROVED · 2026-09-30)

| # | 위치 | 문구 |
|---|---|---|
| B1 | 시장 브리핑 머리 `render.HEADER` | `[시장 흐름 브리핑] 08:30` |
| B2 | 기초지수 자리 1줄 `render.INDEX_NOTICE[STATUS_PREV_DAY_MISSING]` | `국내 기초지수는 직전 거래일 자료를 확인하지 못해 제외했습니다.` |
| B3 | 본문 맨 끝 1줄(CSV 안내보다 앞) `render.BATCH_FAILURE_NOTICE` | `※ 운영 안내: 오늘 아침 보유 종목 시세 갱신이 끝나지 않아 고점 대비 값이 빠질 수 있습니다.` — 발동 입력은 §7-3 (2) |
| B4 | 낼 내용 없음 + 배치 실패 `render_notice_only()` | `[시장 흐름 브리핑] 08:30` + 빈 줄 + B3 |
| B5 · B6 · B7 | 「OCI 운영·적용」 거래일 행(종료 커밋 · 설계자 2026-10-02 화면 계약 · §11) | 한국 = `거래일 기준` · `평일 기본 운영 · 등록된 공휴일·명절·5월 1일·12월 31일 제외`(설계자 문구 · 늘 정상 · `oci_startup_status.trading_day_basis_job`) / 미국 = `미국 휴장일 달력`(리드 새 라벨 · §7-4) · `준비 필요` · `미국 {올해}년·{다음 해}년 파일 있음` 등(`calendar_job`) |
| C1 | 「신규 진입 검토」 구역 머리 다음 줄 `TREND_BASIS_LINE` | `추세 기준 YYYY-MM-DD 종가` |
| C2 | 15:40 장중 점검 요약 끝 `ENTRY_OMITTED_SUMMARY` | ` · 신규 진입 검토 생략 N회` — 이제 추세 기준일 미확인 · 대표 누락 · 사업군 목록 없음 회차를 센다 |
| D1 | 「코스피 가격 흐름」 차트 아래 `today/KospiChart.tsx` | `[배지] KOSPI 기준일 YYYY-MM-DD · N거래일 지연` · 정상이면 줄 없음 |
| D2 | AI 복사 텍스트 KOSPI 상태 줄 | `- KOSPI 보조 기준: {배지} · {기준 줄} · {사유}` — 값 줄은 R4-2c |
| D3 · D4 | 스냅샷 `market_context_snapshot.kospi` 새 키 · LEGACY 영문 KOSPI 경고 숨김 | (문구 추가 없음) |

재사용(새 문구 아님): 미국 자료가 기대 세션이 아니면 기존 `SENTENCE_NO_OUTLOOK`. 날짜 값만 바뀌는 곳: 보유 브리핑 `기준: 20거래일 전 종가 YYYY-MM-DD`(캘린더 T-20) · 장중 `직전 종가 YYYY-MM-DD`(캘린더 T-1).

### 7-3. 설계자 · 사용자 결정 (남은 것)

1. **개별주 정규장 종가 원천** — KRX 주식 일별 `sto/stk_bydd_trd`(KOSPI · 리드 1회 조회로 942행 확인) · `ksq_bydd_trd`(KOSDAQ · 미확인)를 개별주 원천으로 승인하면 개별주 파생값을 되살릴 수 있다. 새 외부 호출 경로 · 새 저장(테이블 또는 기존 표 확장) 필요 → 사용자 승인 · 설계자 계약 대상. 이번 라운드에서 하지 않았다.
2. **B3 발동 입력에서 FDR 을 뺄지** — 가격 기준 변경 뒤 FDR 가격 단계 실패의 보유 영향은 사실상 없다(ETF = KRX · 개별주는 늘 닫힘). 배치 자체가 안 돈 날(상태 JSON 없음 · `refresh_date_kst` ≠ 오늘)은 KRX 도 안 돌아 ETF `고점 대비` 가 빠지므로 B3 가 맞다. FDR 단계만 실패한 날의 B3 는 과잉 고지일 수 있다. 확정 PLAN STEP 7-3 입력이라 임의로 빼지 않았다.
3. **대표 커버리지 상태 화면 표시** — (a) 「OCI 운영·적용」 기존 읽기 전용 SSH 명령에 배치 상태의 `krx_representatives.status` · `missing` 을 더해 행 1개 추가(새 문구 사용자 확인 필요) (b) OCI 상태 JSON · 로그 기록으로 충분.
4. **ETF 분할 가드** — 최소안 = ETF 에도 T-1 가드(KRX T-1 종가 vs Naver 전일 종가 · 분할 당일만 잡고 창 안 과거 분할은 못 잡음) · 또는 알려진 한계로 유지.
5. **채우기 중 조회 오류 날짜의 같은 날 재호출** — 설계자 STEP 6 '같은 날짜를 하루에 반복 호출하지 않으며' 를 문자 그대로 따랐다. 응답이 없었던 호출(`fetch_error`) 날짜만 T-1 성공 뒤 1회 더 허용(두 번째 호출도 기록)할지. 목표일 자체가 원천 불통인 경우는 이미 미룬다(LENS2-F1).

### 7-4. 종료 커밋 화면 (사용자 화면 확인 대상)

- 「OCI 운영·적용」 ① 의 미국 행 라벨 `미국 휴장일 달력` — 리드가 붙인 새 라벨이다(옛 `거래일 달력`). 한국 행 `거래일 기준` · 내용 문구는 설계자 확정이다. PC 백엔드 · 프론트가 이 코드로 뜬 뒤 보인다(§11).

---

## 8. 배포 절차 · 첫 거래일 실측 (확정 계약 12 · 14 · 설계자 RESULT STEP 8)

### 8-1. 순서 — 실행 기록

1. 커밋 `7feddf2c`(102파일 · 13680+/1184-) · push origin/main(`7e60f536..7feddf2c` · 사용자 승인 2026-10-01 16:2x). **함께 올린 신규 파일**: 1차 = `app/market_briefing/krx_target_sync.py` · `app/us_trading_calendar.py` · `state/market_meta/nyse_holidays_2026.csv` · `nyse_holidays_2027.csv` · 새 테스트 7파일 · `frontend/app/components/KospiStatusSurfaces.test.tsx` · 설계서 · PLAN · 이 결과서 / 보완 신규 = `app/market_briefing/krx_target_checks.py` · `app/market_briefing/krx_backfill.py` · `app/intraday_config/representatives.py` · `app/market_benchmark_kospi_retry.py` · `app/runtime_evidence/holdings_price_basis.py` · `frontend/lib/kospiStatus.ts` · `frontend/lib/dependencyDirection.test.ts` · `tests/test_poc3_02d_ops03_consumer_isolation.py` · `_kospi_retry.py` · `_price_basis.py`. `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` 는 사용자 소유 — 올리지 않았다.
2. 거래일 15:40 뒤 사용자 OCI pull(PLAN STEP 9-2) — 2026-10-01.
3. **같은 회차에** 사용자가 crontab 세 줄 변경(8-2) — 2026-10-01.
4. 리드 읽기 전용 read-back(2026-10-01 16:32): OCI HEAD `7feddf2c` · 추적 변경 0 · `state/market_meta/nyse_holidays_2026.csv` · `2027.csv` 있음 · pydantic · fastapi · starlette 를 막고 새 모듈 import 정상 · `expected_previous_trading_day("2026-10-02")` = 2026-10-01 · OCI Python 3.12.3 · America/New_York zoneinfo 정상 · crontab 13줄(8-2).
5. PC 백엔드 재기동 — PC 화면(「OCI 운영·적용」 · PC KOSPI)만 바뀐다 · OCI 운영과 무관(이 문서에 시각 기록 없음).
6. 다음 거래일 2026-10-02 08:10 · 08:30 · 09:15 · 09:20 · 09:30 실측(8-4 표대로) — 통과(8-5).
7. 다음 월요일(연휴로 10-06) 재실측 — 사용자 결정(2026-10-02)으로 생략(8-5).
8. 결과서 · `STATE_LATEST` · `PROGRAM_TRUTH` · handoff 최종 갱신 → `IMPLEMENTED_VERIFIED_DEPLOYED_OPERATION_CONFIRMED` · POC5-01A 개방(2026-10-02).

pull 과 cron 변경 사이에 옛 07:20 cron 이 새 코드를 돌리면 KRX 단계 · KOSPI 재시도는 08:00 전 시작이라 건너뛴다(kts :254-258 · 표 · 정합성 JSON 안 건드림). OCI pull 금지 시간 '07:15~08:05' → '08:05~08:35'(PLAN STEP 9-3). rollback = 코드 revert + OCI pull → crontab 원복(PLAN STEP 9-4).

### 8-2. OCI crontab (서버 시간대 `Asia/Seoul` · 2026-10-01 변경(사용자) · read-back 16:32 · 12줄 → 13줄(PATH 제외))

- 바꿨다: `20 7 * * 1-5 … scripts/run_oci_market_data_batch.py >> logs/oci_market_data_batch.log 2>&1` → `10 8 * * 1-5 …`(같은 명령)
- 바꿨다: `0 8 * * 1-5 … --push-kind market_briefing --mode send >> logs/low_freq_push_cron.log 2>&1` → `30 8 * * 1-5 …`
- 추가했다: `20 9 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_oci_market_data_batch.py --krx-only >> logs/oci_market_data_batch.log 2>&1`
- 나머지(09:15 · 12:30 · 15:40 보유 브리핑 · 09:30 ~ 15:20 보유 위험) 그대로.
- 저장소 `docs/handoff/OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` §0 ~ §10 은 UTC 기준 옛 이력(`00 23 * * 0-4`) — 실제 서버는 KST 다. 파일 앞 'OPS-03. cron 3줄' 절(KST · 2026-10-01 적용).
- 「OCI 운영·적용」 화면은 `--push-kind` 줄만 본다(`oci_startup_status.py:170-171` 추출 · :111-115 필수 3종) — 08:10 · 09:20 배치 줄 누락은 화면에 안 보이므로 read-back 이 유일한 확인이다.

### 8-3. 첫 OCI 실행 예상 (코드 근거 · 배포 전 기록 — 실측은 8-5)

- KOSPI: 08:10 첫 시도가 저장 최신일 09-17 부터 T-1 까지 약 8~10회 KRX 조회 · 09-17 1건 정정(6724.34 → 6715.41) · 증거 `state/market/kospi_source_corrections/kospi_correction_<UTC>.json`(gitignore). T-1 이 아니면 08:15 · 08:20 · 08:24 재시도(첫 시도가 09-17 을 확인하지 못했으면 09-17 부터 다시).
- KRX ETF: 목표일 T-1 시도 + 창(21거래일) 빈 날 중 오늘 아직 안 부른 날만 1회 · ledger `state/market/krx_backfill_ledger.json` 생성(gitignore).
- 배치 상태 JSON 첫 기록은 KRX 대기 전(`stage_status.krx = "pending"`) · KRX · KOSPI 재시도 뒤 다시 기록.
- 보유 브리핑 · 장중 위험: ETF 과거 종가 = KRX 표 · 개별주 3종 = `20거래일 데이터 확인 불가`(§7-1).

### 8-4. 첫 거래일 실측 체크리스트 (설계서 STEP 12 · 2026-10-02 이 표대로 실측 — 결과 8-5)

| 실측 | 기록 위치(OCI) | 볼 필드 |
|---|---|---|
| 08:10~08:27 수집 기록 | `state/market/oci_market_data_batch_state.json`(`mdb.write_batch_state` :37) · 전체 기록은 `logs/oci_market_data_batch.log`(배치 JSON 출력) | `stage_status`(collect · fdr_price · benchmark · artifact · krx) · `krx_target_date` · `krx_stage_mode` · `krx_attempts`(at_kst · target · http · rows · priced_rows · result · error_type) · `krx_basis_date` · `krx_representatives`(status · missing · count) · `representatives_refresh_due` · `krx_backfill`(backfill · backfill_retry 의 missing_before · called · skipped_called_today · filled · failed · stopped · calls_today) · `calendar_readiness` · 로그의 `window` · `price_failures` · `price_budget_skipped` |
| KOSPI 공식 종가 · 재시도 | 배치 상태 JSON · 배치 로그 `benchmark_refresh.kospi` · 증거 폴더 | `kospi_as_of` · `kospi_attempts`(kind · slot · at_kst · calls · result · as_of · error_type) · `kospi_retry`(mode · slots · retries · stopped) · `source` · `expected_as_of_date` · `calls` · `corrections` · `evidence_path` · `before` · `after` |
| 08:30 발송 · 국내 기준일 | `state/three_push/oci_runtime_history.jsonl` 의 `market_briefing` 기록 · Telegram 본문 `기준` 줄 | `index_status` · `index_diagnostics`(T-1 없으면 `expected_previous_trading_day` · `actual_basis_date`) · `batch_failure_notice` · 본문 `국내 YYYY-MM-DD 종가` = T-1 |
| 미국 기준일 | 같은 기록 | `sp500_asof` · `sp500_expected_session` · `sp500_fresh` · `sp500_session_check` |
| 09:20 보강 실행 여부 | `state/market/oci_krx_reinforcement_state.json`(`KRX_REINFORCEMENT_STATE_PATH`) · ledger `state/market/krx_backfill_ledger.json` · 같은 배치 로그 | `date_kst` · `status` · `attempted` · `krx_stage_mode`(`already_loaded` 면 T-1 조회 없음) · `krx_attempts` · `krx_representatives` · `representatives_refresh_due` · `krx_backfill` · ledger `calls` |
| 09:15 · 12:30 · 15:40 보유 브리핑 · 09:30~ 장중 위험 가격 기준 | `oci_runtime_history.jsonl` 의 보유 브리핑 · 장중 위험 기록 | `holdings_price_basis` · `risk_price_basis`(contract · etf_master · krx_table · tickers 의 asset_type · class_source · price_source · price_basis · guard · reason · derived) — ETF = `KRX_OPEN_API/etf_bydd_trd` · 개별주 3종 = `price_basis_mismatch` |
| 09:30 장중 추세 기준일 · 대표 관문 | `oci_runtime_history.jsonl` 의 `holdings_risk_alert` 기록 · 15:40 집계 `state/three_push/intraday_checkup_tally_latest.json` | `intraday_trend_basis`(expected_previous_trading_day · table_latest · d5 · d20 · missing_days · usable) · `intraday_entry_omitted` · `intraday_entry_omitted_reason` · `intraday_representatives` · `intraday_config_error` · 틱의 `entry_omitted` · 본문 `추세 기준 YYYY-MM-DD 종가` |
| 사용자 경고 중복 0 | Telegram 수신 · `oci_runtime_history.jsonl` | 08:30 발송 1회 · 고지 줄 1회 이하 · 장중 틱마다 경고 없음 · KOSPI 실패 Telegram 0 |

### 8-5. 첫 거래일 운영 실측 (2026-10-02)

OCI 읽기 전용(리드 · 08:54 · 10:26 · 배치 상태 JSON · 09:20 보강 기록 · 실행 기록 · 로그 · 쓰기 0).

| 시각 | 항목 | 결과 |
|---|---|---|
| 08:10 | KRX 목표일 T-1(10-01) | 08:10:31 첫 시도 `ok` · http 200 · 1,171행 · `write=inserted` · read-back 1,171 · `krx_stage_mode=scheduled` |
| 08:10 | 창 빈 날 채우기 | 09-30 1회 조회 · filled · `calls_today {2026-09-30: 1}` |
| 08:10 | 대표 ETF | `krx_representatives` status ok · 27/27 · missing [] · `representatives_refresh_due=false` |
| 08:10 | KOSPI | `kospi_as_of=2026-10-01` · `kospi_retry.retries=0 · stopped=t1_stored` · 증거 `state/market/kospi_source_corrections/kospi_correction_20261001T231019982599Z.json` · stage after_write · readback_ok true · 09-17 6724.34(`FinanceDataReader/KS11` · old_row_hash f75b6b0a…) → 6715.41(`KRX_OPEN_API/idx_kospi_dd_trd`) · before 3,052행 as_of 09-17 → after 3,060행 as_of 10-01 · 새 날짜 8개(09-18 ~ 10-01) |
| 08:10 | 배치 | status `success` · stage_status 전부 ok · price_data_as_of 10-01 |
| 08:30 | 시장 브리핑 | 08:30:02 `sent` 1회 · index_status ok · price_asof 10-01 · lookback latest 10-01 · d5 09-22 · d20 09-01 · api_ticker_count 1,171 · sp500_asof 10-01 = expected 10-01 · fresh · batch_failure_notice reasons [] |
| 09:15 | 보유 브리핑 | `sent` · `holdings_price_basis` contract ETF_KRX_UNADJUSTED__STOCK_FDR · etf_master krx_etf_basic_20260927.csv · krx_table ok · 29종(ETF 26 window 전부 ok · 닫힌 ETF 0) · 개별주 3종 reason price_basis_mismatch · derived blocked · 그날 guard diff 000660 -0.271 · 005930 -0.548 · 006400 -0.004 |
| 09:20 | KRX 보강 | `oci_krx_reinforcement_state.json` status ok · krx_stage_mode already_loaded · attempted false · 목표일 조회 0 · backfill called [] |
| 09:30 | 장중 | `sent` · intraday_trend_basis expected 10-01 = table_latest 10-01 · d5 09-22 · d20 09-01 · usable · entry_omitted false · 대표 27/27 ok · sector states AVOID_CHASE · AVOID_DROP · ENTRY_REVIEW · sent_today 1 |
| — | 오류 · 중복 | 배치 로그 · 발송 로그 traceback · error 0 · 시장 브리핑 1회 · 배치 실패 고지 없음 |

- 발송 본문은 OCI 기록에 길이(`message_text_length`)만 있다 — 본문 줄은 사용자 Telegram 으로 확인한다(리드는 본문을 직접 보지 못함).
- 원인 해소: 국내 T-2(08:30 국내 기준일 = T-1 10-01 · 장중 추세 기준 = T-1) · KOSPI 정지(09-17 정정 · 10-01 까지 8일 적재) → 운영 상태 `OPERATING_DEGRADED` 해제 → `OPERATING`.
- 사용자 결정(2026-10-02 · 원문 = 설계서 끝 절 '사용자 결정'): 10-06 까지 기다리지 않고 10-02 실측 기준으로 통과 · 1인 운영이라 그렇게까지 빡빡하게 관리하지 않아도 된다 → 설계자 STEP 8 의 다음 월요일(연휴로 10-06) 재실측을 생략하고 이 실측으로 `IMPLEMENTED_VERIFIED_DEPLOYED_OPERATION_CONFIRMED` · `POC5-01A` 개방(설계자 STEP 8).

---

## 9. KS-10 (`wc -l` 실측 2026-09-30 20:4x · 기준 커밋 7e60f536 → 작업 트리)

| 파일 | 줄 | 비고 |
|---|---|---|
| `scripts/run_three_push_runtime_oci.py` | 646 → 646 | 변경 0 |
| `app/runtime_evidence/sector_signal.py` | 408 → 599 | 변경 백엔드 모듈 최대 · 근접선 600 바로 아래(LENS4-N1) · 종료 커밋 595(§11) |
| `app/runtime_evidence/intraday_alert_flow.py` · `scripts/run_oci_market_data_batch.py` | 470 → 577 · 343 → 563 | |
| `app/runtime_evidence/holdings_risk_flow.py` · `app/market_benchmark_store.py` | 508 → 538 · 273 → 537 | |
| `app/market_briefing/krx_target_sync.py` | 신규 494 | 1차 595 → 적재 판정 · 채우기를 `krx_target_checks.py` 293 · `krx_backfill.py` 184 로 분리 |
| `frontend/app/components/DashboardView.tsx` | 769 → 774 | 변경 프론트 컴포넌트 최대 · 850 미만 |
| `tests/test_market_briefing_contracts.py` · `test_intraday_alert_flow_through.py` | 1406 → 1427 · 1298 → 1342 | 테스트 근접선 1,450 미만 |
| `tests/test_poc3_02d_ops03_kospi_retry.py` | 신규 868 | 새 테스트 최대 |

## 10. git 상태

`git status --short --untracked-files=all` 실측(2026-10-01 · 검증자 r1 정정 뒤 15:5x 재고 r2 정정 뒤 다시 재어 같은 값 · 검증 회차 보고 직전 · 커밋 전 측정 — 커밋 뒤에는 staged 0 이 정상) — staged 102(수정 `M ` 77 = 코드 · 테스트 · 설정 66 + 문서 11 · 신규 `A ` 25 = 코드 · 테스트 · 데이터 22 + 설계서 · PLAN · 이 결과서) · 오른쪽 열(unstaged) 0 · `??` 1 = 사용자 소유 `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`(올리지 않는다). `git diff --cached --shortstat` = 102 files changed, 13680 insertions(+), 1184 deletions(-)(이 절을 채우기 직전 값). 이 측정 상태가 커밋 `7feddf2c` 가 됐다(2026-10-01 · 사용자 승인). 종료 커밋의 파일은 §11.

---

## 11. 종료 커밋 — 한국 거래일 계약 정정 (설계자 2026-10-02)

원문 = 설계서 끝 절 '설계자 정정 — 한국 거래일 계약 복원'. 새 결정이 아니라 2026-09-11 사용자 확정 계약을 복원한다.

```text
한국 거래일   주말 · 확인된 공휴일·명절·대체공휴일 · 5월 1일 · 12월 31일 = 휴장 · 그 밖의 평일 = 운영
연도 파일     정확도를 높이는 보조자료 · 없으면 평일 기본 운영 · 연 2~3회 오판은 결함이 아니다
다음 해 파일  필수 아님 · 없어도 `준비 필요` · `오래됨` · `STALE` · 마감 경고를 내지 않는다
미국 NYSE     휴장일 파일 계약 그대로(정정 대상 아님)
```

**적용 범위**: 이 커밋 코드는 OCI 미반영이다(OCI 는 `7feddf2c`). 다음 OCI pull(거래일 15:40 뒤 · cron 변경 없음) 때 적용된다. 급하지 않다 — 「OCI 운영·적용」 거래일 행은 PC 가 계산하고(PC 백엔드가 이 코드로 뜨면 보인다), 나머지는 한국 연도 파일이 없는 해(2027~)에만 동작이 다르다(2026 은 `krx_trading_days_2026.csv` 가 덮는다). 설계자 지시대로 실측 중간에 재배포하지 않았고, 거래일 관련 테스트만 고쳤다.

| 파일 | 바뀐 것 |
|---|---|
| `app/market_briefing/calendar.py` | `FIXED_HOLIDAYS_MMDD = {(5, 1), (12, 31)}`(:179) · `is_fallback_trading_day(d)`(:182 · 평일이고 5월 1일 · 12월 31일이 아님) · `_fallback_verdict`(:187)가 사용 — 연도 파일 없는 해의 PUSH 거래일 판정 |
| `app/trading_day_lag.py` | `weekday_axis_before`(:38) · `_trading_day_test`(:141)가 같은 규칙 · `_trading_day_test(stored=, anchor=)` · `trading_days_ending`(:198) · `trading_days_back`(:225) · `trading_window_dates`(:247)에 `stored` 인자 — 연도 파일 없는 해에 anchor 이전 평일은 저장된 날만 거래일로 센다(저장 자료 없는 평일 = 휴장으로 건너뜀 · 창을 닫지 않음). `unconfirmed_days` 삭제 — OPS-03 리뷰 L2-2 의 fail-closed(파일 없는 해에 평일 휴장 뒤 약 20거래일씩 구역을 닫던 동작)를 계약에 맞게 되돌렸다 |
| 호출부 3곳 | `krx_store.resolve_calendar_window`(:477 · 저장 날짜를 먼저 읽어 넘김 · `CalendarWindow.unconfirmed_days` 필드 삭제) · `holdings_selection_source.trading_day_axis`(:103 · `stored_dates` 를 넘김 · 빈 축 규칙 삭제) · `sector_signal.resolve_trend_basis`(:243 · `stored_days` 를 넘김) |
| `app/runtime_evidence/holdings_price_basis.py` | `FETCH_EXTRA_TRADING_DAYS = 10`(:78) · `_fetch_days`(:212) — KRX ETF 종가를 축 20 + 앞쪽 10거래일 읽는다(건너뛰어 앞으로 늘어난 기준일 종가를 놓치지 않게 · 리드가 테스트로 발견한 실제 결함) |
| `app/us_trading_calendar.py` | 달력 준비 상태 `MARKETS = ("NYSE",)`(:280) — 한국 파일 유무로 경고하지 않는다 · `calendar_readiness_for_dir`(:324)는 NYSE 만 읽는다(배치 JSON `calendar_readiness` 도 미국만) |
| `app/oci_startup_status.py` | `trading_day_basis_job()`(:281) — job `trading_day_basis` · `SUCCESS` · `평일 기본 운영 · 등록된 공휴일·명절·5월 1일·12월 31일 제외`(설계자 문구 · 늘 추가 · :246) · `calendar_job`(:292)은 미국 전용(`미국 {올해}년·{다음 해}년 파일 있음` 등) |
| `frontend/app/components/OciStatusView.tsx` | 라벨 `trading_day_basis` = `거래일 기준`(설계자) · `trading_calendar` = `미국 휴장일 달력`(리드 새 라벨 · 사용자 화면 확인 대상 · §7-4) |

**테스트**(거래일 관련만 · 설계자 지시): briefing_calendar — 달력 준비 미국 전용 · 한국 행 늘 정상 · 미국 행(`test_readiness_is_us_only_november_check_and_december_warning` · `test_readiness_current_year_missing_warns_any_month_us_only` · `test_readiness_from_directory_reads_content` · `test_oci_status_korea_basis_row_is_always_normal` · `test_oci_status_us_calendar_row` · `test_oci_status_us_row_all_present_and_old_output` · `test_oci_status_us_current_year_missing`) · krx_batch `test_uncovered_year_unstored_weekday_is_skipped_window_stays_usable` · `test_fallback_year_closes_may_1_and_dec_31_only` · holdings `test_uncovered_year_unstored_weekday_is_skipped_not_emptied` · `test_uncovered_year_gap_reaches_both_holdings_flows`(두 흐름 모두 계산) · intraday `test_trend_basis_uncovered_year_unstored_weekday_is_skipped` · price_basis `test_etf_uses_krx_closes_even_when_fdr_differs`(KRX 조회 범위 30거래일) · `OciStatusView.test.tsx`(1건 바뀜 · 모두 7건).

**줄 수**(`wc -l` · `git show 7feddf2c:<파일>` → 작업 트리 · 2026-10-02 실측):

| 파일 | 줄 |
|---|---|
| `app/market_briefing/calendar.py` | 256 → 269 |
| `app/market_briefing/krx_store.py` | 542 → 538 |
| `app/oci_startup_status.py` | 331 → 343 |
| `app/runtime_evidence/holdings_price_basis.py` | 293 → 311 |
| `app/runtime_evidence/holdings_selection_source.py` | 142 → 137 |
| `app/runtime_evidence/sector_signal.py` | 599 → 595 |
| `app/trading_day_lag.py` | 268 → 278 |
| `app/us_trading_calendar.py` | 367 → 361 |
| `frontend/app/components/OciStatusView.tsx` · `OciStatusView.test.tsx` | 219 → 221 · 161 → 174 |
| `tests/test_poc3_02d_ops03_briefing_calendar.py` · `_holdings.py` · `_intraday.py` · `_krx_batch.py` · `_price_basis.py` | 388 → 420 · 273 → 279 · 490 → 491 · 811 → 831 · 534 → 535 |

**검증**: OPS-03 새 테스트 10파일 `pytest --collect-only` 292건(briefing_calendar 45 · krx_batch 47) · 프론트 `OciStatusView.test.tsx` 7 passed · tsc 0 · eslint 0(바뀐 2파일) · 백엔드 전체 회귀 = 2,709 passed / 0 failed(exit 0 · 393.21s · 2026-10-02 10:4x · 종료 커밋 코드 전부 뒤 마지막 1회 · PC `state/` · `logs/` 226파일 sha256 전후 동일) · 프론트 전체 vitest 24파일 287 · tsc 0 · eslint 0.

**문서**(같은 커밋): 설계서(끝 절 설계자 정정 · 사용자 결정 원문 기록) · 이 결과서(종료 갱신) · `docs/STATE_LATEST.md` · `docs/PROGRAM_TRUTH.md` · PLAN(확정 계약 11 정정 주석) · `docs/handoff/OCI_THREE_PUSH_CRONTAB_TEMPLATE.md`(OPS-03 절 적용 기록) · 신규 인계 `docs/handoff/POC3-02D-OPS-03_OPERATIONAL_DATA_FRESHNESS_AND_SOURCE_RECOVERY_HANDOFF_2026-10-02.md`. `docs/backlog/BACKLOG.md` 에는 한국 다음 연도 달력 항목이 없었다(grep 0 · 변경 없음). 커밋 SHA 는 `git log` 로 확인한다.

## 12. 2026-10-03 후속 배포 확인

```text
한국 거래일 계약 정정 커밋 7d507951은 2026-10-02 17:56 KST OCI pull로 반영됐다. OCI HEAD는 7d507951이며 OCI runner blob은 저장소 기준 blob
f256677020232600627d207c54baf5081c70c6e2와 일치한다. OPS-03은 재개방하지 않는다.
```

확인 방법(2026-10-03 · 개발자 · OCI 읽기 전용 명령 1회): `git log --oneline -3` 맨 위 `7d507951` · `.git/FETCH_HEAD` 수정 시각 2026-10-02 17:56:26 KST · `git hash-object scripts/run_three_push_runtime_oci.py` = `f256677020232600627d207c54baf5081c70c6e2`(저장소 HEAD `7d507951` 의 같은 파일 blob 과 같음) · 추적 파일 변경 0(`git status --short` 에는 기존 백업 · 옛 빈 DB 같은 untracked 만). 위 본문의 'OCI 미반영 · 다음 pull' 기록은 작성 당시 사실이라 그대로 둔다(설계자 2026-10-03 판정).
