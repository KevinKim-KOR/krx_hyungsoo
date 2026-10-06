# POC3-02D-OPS-04 개발 결과서 — REMAINING OPERATIONAL CORRECTIONS

작성 2026-10-06 · 갱신 2026-10-06(검증자 r1 정정 · 설계자 2026-10-06 판정 반영 · 재제출 전 점검 재작업) · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex)

```text
STATUS                 = IMPLEMENTED_VERIFIED — 검증자 r2 VERIFIED(2026-10-06 · 위험 LOW · 범위 폭주 NONE) · 커밋 · push 사용자 승인(2026-10-06) · 설계자 RESULT 판정 대기 · OCI pull 은 사용자(미반영)
VERIFIER               = r2 VERIFIED(2026-10-06 · A-1 ~ A-4 통과 · B-1 ~ B-6 없음 · 위험 LOW — §5-2 · §5-3 한계는 코드와 일치 · 설계자 RESULT 판정에 함께 전달 · 범위 폭주 NONE) ← r1 REJECTED(2026-10-06 · A-1 · A-2 · A-3) → 처리 §6-0-1: ① 보강 = 09:20 회차 창에 시작한 실행만(설계자 수용 2026-10-06) ② `RemoteProtocolError` — r1 정정에서 뺐다가 설계자 결정(2026-10-06)으로 일시 오류에 포함 ③ 줄 수 재실측(§8-1)
SELF_CHECK             = 재제출 전 개발자 점검(2026-10-06): PLAN §2-1 2 · 3 이탈 2건 → 사용자 결정 '유지'로 PLAN 원문대로 재작업(§6-0-2 · 개별주 = ETF 와 독립된 곁 작업) · 문구 과대 1건 정정 + 한계 기록(§5-2)
DESIGNER_2026-10-06    = OPS-04 REMEDIATION_IN_PROGRESS · RemoteProtocolError 포함 · 동등성 도구 rc 2 결함 아님 · POC5-01B HOLD(OPS-04 VERIFIED 전 진입 금지) — 원문 = 설계서 끝
STEP_ID                = POC3-02D-OPS-04 남은 운영 정정 6건
DESIGN                 = docs/ai_design/POC3/POC3-02D-OPS-04_REMAINING_OPERATIONAL_CORRECTIONS_DESIGN_V1.md (설계자 2026-10-04 · 끝에 PLAN 판정 · 2026-10-06 판정 · 사용자 결정 원문)
PLAN                   = docs/ai_plan/POC3/POC3-02D-OPS-04_REMAINING_OPERATIONAL_CORRECTIONS_PLAN_V1.md (설계자 CONDITIONAL_PASS + 사용자 승인 2건 → PASS 2026-10-04)
PREDECESSOR/SUCCESSOR  = POC5-01A(종료 — IMPLEMENTED_VERIFIED_DEPLOYED_OPERATION_CONFIRMED 2026-10-06 · 설계자 ACCEPTED_CLOSED) / POC5-01B(HOLD)
BASE_HEAD(구현 기준)    = 87238e1e (POC5-01A 구현 커밋) · 그 뒤 POC5-01A 종료 문서 커밋 19882ff3(코드 변경 0) · 이 단계 변경 = 검증자 r2 VERIFIED 뒤 커밋 1개(사용자 승인 2026-10-06 · SHA 는 `git log` 로 확인)
IMPLEMENTATION_GATE    = 사용자 결정 2026-10-04 '로컬 구현 먼저'
MOCKUP                 = 항목 3 · 6 화면 문구 사용자 확정 2026-10-06 (구현 전 1회 · 추가 3건 포함)
CODE_FILES             = 운영 26 (신규 3 · 수정 23 = .gitignore 포함) · 테스트 13 (신규 3 · 수정 10) · DB 파일 · API · 메뉴 · cron · 의존성 0 · 시장 DB 표 1개 추가(사용자 승인)
NEW_TESTS              = 백엔드 새 3파일 119 (09:20 보강 50 · 개별주 공식 종가 42 · ① 두 행 27 · `--collect-only`) · 프론트 기존 3파일에 추가
REVIEW                 = 1차(구현) 조사 지도 4 + 반박 4 · 백엔드 3관점 + 반박 3 · 화면 2관점 + 반박 2 / 2차(재작업) PLAN · 코드 · 문서 3관점 + 관점별 반박 / 3차 결과서 · 문서 최종 대조 2관점 — 확인된 지적 모두 반영(§6-1)
SABOTAGE               = 1차 18종 · r1 정정 4종 · 재작업 12종(12/12) · 재작업 검토 반영 7종(7/7) — 사본 폴더(§8-4)
BACKEND_FULL_REGRESSION= 2833 passed / 0 failed · exit 0 · 379.30s (최종 코드 · 2026-10-06 19:49:26 ~ 19:55:47) · PC state/ · logs/ 1,153파일 hash 전후 동일
FRONTEND               = vitest 24파일 296 passed · eslint · tsc rc 0(2026-10-06 19:56 재실행 · 프론트 변경은 r1 전 그대로) · production build rc 0(저장소 밖 사본 · r1 전)
OCI_EVIDENCE           = 2026-10-06 읽기 전용 — 새 기동 읽기 명령을 OCI 에서 그대로 실행 rc 0 · 5블록 · 장중 대표 ETF `정상 27/27` · 운영 기준 활성 `일치 14/14`
KRX_EVIDENCE           = sto/stk_bydd_trd 1회 조회 3번(승인된 API · 읽기만 · §8-6) — 필드 · 공개 시각 실측
```

## 0. 요약

설계서의 여섯 항목을 최소 변경으로 닫았다.

| 항목 | 결과 | 핵심 |
|---|---|---|
| 1 개별주 공식 종가 | 구현 | 시장 DB 에 표 `krx_stock_daily_price_unadjusted` · `sto/stk_bydd_trd` · 보유 코스피 개별주 행만 · **KRX 단계의 곁 작업**(KOSPI 재시도와 같은 자리 · ETF 와 독립 · 같은 시각표 · 마감 08:27 · 09:20 보강) · 목표일은 저장될 때까지 칸마다 · 창은 목표일 저장과 무관 · 보유 PUSH 개별주 파생값 = KRX 공식 종가(FDR 읽기 제거) |
| 2 FDR 실패 고지 | 구현 | 08:30 배치 고지에서 FDR 단계 조건만 제거 · 배치가 안 돈 날 고지 유지 |
| 3 대표 ETF 행 | 구현 | 「OCI 운영·적용」 ① `장중 대표 ETF` 행 · 기존 기동 시 SSH 읽기에 블록 1개 |
| 4 단절 가드 | 운영 코드 변경 없음 | 기존 5경로 가드 확인 · 새 6번째 경로(개별주 KRX)에만 테스트 추가 |
| 5 09:20 재시도 | 구현 | 첫 호출이 일시 오류(timeout · 연결 오류 · `RemoteProtocolError` · 429 · 5xx)인 창 날짜만 09:20 회차에 1회 더 · 날짜별 하루 최대 2회 |
| 6 PARAM 의미 | 구현 | ② 카드 '전달' 문구 · ① `운영 기준 활성` 행(OCI 러너 유효값 14개 비교 · 요청 때) · ② 전달 뒤 ① 다시 읽기 |

## 1. 처리한 요구사항

| # | 요구사항(설계서 §6 AC · PLAN) | 상태 | 근거 |
|---|---|---|---|
| AC1 | 보유 개별주 일별 파생값 = KRX 공식 무조정 | DONE | `holdings_price_basis.py` 개별주 분기 · `krx_stock_store` · `krx_stock_sync.HoldingsStockTask` · §8-3. 범위 = PUSH(보유 브리핑 · 장중 위험) — PC 미리보기는 FDR 그대로(§5-7) |
| AC2 | 보유 ETF 파생값이 FDR 조정값과 섞이지 않음 | DONE | OPS-03 계약 유지(`holdings_price_basis` ETF 분기 · 테스트 `test_etf_uses_krx_closes_even_when_fdr_differs` 등) |
| AC3 | FDR 실패만으로 포괄 경고 없음 | DONE | `runner_market_briefing.batch_failure_reasons` · 테스트 `test_fdr_failure_alone_no_longer_sends_notice_only_body` |
| AC4 | ① 한 행에서 대표 ETF 상태 · 기준일 · 수량 | DONE | `oci_status_rows.representatives_job` · OCI 실측(§8-5) |
| AC5 | 누락 거래일 파생값 미계산 · 다른 값 · 발송 계속 | DONE | 기존 5경로(§1-4) + 개별주 경로 테스트 3건 |
| AC6 | 09:20 은 필요한 누락일만 1회 · 추가 cron · 다른 자료원 0 | DONE | `krx_backfill.call_allowed` · `fill_missing(reinforcement)` · 보강 표시 = 09:20 회차 창(09:20:00 ~ 09:29:59 KST)에 시작한 `run_krx_only` 만(`in_reinforcement_window` · 설계자 수용 2026-10-06) · 일시 오류 = `krx_target_checks.is_transient_fetch_error`(설계자 2026-10-06 범위) |
| AC7 | PARAM 전달 · 활성 구분 · 자동 활성화 없음 | DONE | ② 카드 문구 · ① `운영 기준 활성` 행 · 원격 쓰기 0 |
| AC8 | 기존 PUSH 동작 · POC5-01A 경계 유지 · 신규 DB · API · 메뉴 0 | DONE | 러너 파일 변경 0 · `fetch_history` 서명 유지 · 새 API 0(기존 GET 응답 `jobs` 행) |
| AC9 | focused test · 전체 회귀 | DONE | §8 |
| AC10 | 실화면에서 두 질문에 답할 수 있음 | DONE | OCI 실측으로 두 행 값 확인(§8-5) · **사용자 실화면 확인 완료 2026-10-06**(§7) |
| PLAN §2-1 2 | 시점 = 08:10 KRX 단계의 곁 작업(KOSPI 재시도와 같은 자리 · 마감 08:27 공유) + 09:20 보강 | DONE(재작업) | `krx_target_sync._stock_task` · `_Sides` · `HoldingsStockTask.run_due` — §6-0-2 |
| PLAN §2-1 3 | 창 21 + 10 · 처음 한 번 창 · 그 뒤 날마다 T-1 1호출 · 하루 1회 ledger | DONE(재작업) | 창 31거래일 · 목표일 저장 조건 제거 · 창 날짜 = ledger · 목표일 = ledger 밖(§4-2) |
| PLAN §2-5 | ledger `retryable` · 09:20 만 1회 더 · 개별주 누락일도 같은 규칙 | DONE | `krx_backfill` · `HoldingsStockTask._fill` |
| PLAN §4-3 | 목업 1회 | DONE | 2026-10-06 사용자 확정 |
| PLAN §4-2 | 최종 build 저장소 밖 사본 1회 | DONE | rc 0(r1 전 · 그 뒤 프론트 변경 0) |

### 1-4. 항목 4 — 경로별 기존 테스트(운영 코드 변경 없음)

| 경로 | 기존 테스트(누락일 고정) |
|---|---|
| 보유 브리핑 기준일 · 고점 대비 | `test_holdings_selection.py` `test_base_close_must_be_exactly_the_reference_trading_day` · `test_incomplete_aux_window_drops_only_the_note_not_the_selection` |
| 장중 보유 위험 고점 대비 | `test_poc3_02d_ops03_holdings.py` `test_risk_previous_close_date_is_calendar_t1_on_batch_failure` |
| 장중 사업군 5 · 20일 | `test_sector_signal.py` `test_trend_returns_do_not_substitute_older_close` · `test_poc3_02d_ops03_intraday.py` `test_missing_d5_date_fails_closed_instead_of_shifting` |
| 08:30 기초지수 | `test_poc3_02d_ops03_briefing.py` · `test_poc3_02d_ops03_krx_batch.py` `test_s10_missing_required_date_fails_closed` |
| ETF 가격 계열 | `test_poc3_02d_ops03_price_basis.py` `test_etf_missing_krx_base_is_not_filled_from_fdr` · `test_etf_drawdown_omitted_when_krx_window_incomplete` |
| **개별주 KRX(새 경로)** | 새 테스트 `test_stock_missing_base_or_window_day_is_not_filled` · `test_stock_without_krx_rows_never_falls_back_to_fdr` · `test_risk_stock_window_gap_omits_only_drawdown` |

분할 · 병합 탐지 조사는 하지 않았다(설계자 Q5 a).

## 2. 변경된 파일 목록

운영 코드(신규 3 · 수정 23). 줄 수 = 작업 트리 `wc -l` 실측(2026-10-06 · 괄호 = HEAD).

| 파일 | 변경 | 줄 |
|---|---|---|
| `app/market_briefing/krx_stock_store.py` | 신규 — 개별주 표 · 보유 행 고르기 · 읽기 전용 reader | 221 |
| `app/market_briefing/krx_stock_sync.py` | 신규 — 개별주 곁 작업 `HoldingsStockTask`(목표일 ledger 밖 · 창 ledger · 별도 ledger · 다음 칸에서 멈춤) · `attempt_once` · `holdings_tickers` | 432 |
| `app/oci_status_rows.py` | 신규 — ① 두 행 · 원격 블록 2개(KS-10 때문에 `oci_startup_status` 에서 분리) | 254 |
| `app/market_briefing/krx_backfill.py` | 수정 — ledger `retryable` · `call_allowed` · `write_ledger` · 09:20 보강 · `REINFORCEMENT_WINDOW` · `in_reinforcement_window` · 죽은 `read_calls_today` 제거 | 271 (184) |
| `app/market_briefing/krx_target_checks.py` | 수정 — `is_transient_fetch_error`(`RemoteProtocolError` 포함) · `http_status` · 시도 기록 `transient` | 324 (293) |
| `app/market_briefing/krx_target_sync.py` | 수정 — 보강 표시 · 개별주 곁 작업 만들기(`_stock_task`) · 곁 작업 묶음(`_Sides` · 예외 격리) · 단계 시작 시각 1회 | 594 (494) |
| `app/market_briefing/krx_sync.py` | 수정 — `KRX_STOCK_DAILY_URL` · `_default_stock_fetcher` | 520 (501) |
| `app/market_briefing/render.py` | 수정 — 고지 주석 | 245 (246) |
| `app/runtime_evidence/holdings_price_basis.py` | 수정 — 개별주 = KRX 공식 종가 · 계약 이름 · evidence | 333 (311) |
| `app/runtime_evidence/holdings_selection_source.py` | 수정 — 죽은 `load_price_history` 제거 | 115 (137) |
| `app/runtime_evidence/holdings_selection.py` · `holdings_risk.py` · `holdings_selection_flow.py` | 수정 — 주석 · docstring | 373 · 428 · 460 |
| `app/three_push_runtime/market_data_batch.py` | 수정 — `krx_holdings_stocks` 기록 | 512 (507) |
| `app/three_push_runtime/runner_market_briefing.py` | 수정 — FDR 고지 조건 제거 | 248 (247) |
| `scripts/run_oci_market_data_batch.py` | 수정 — `reinforcement`(09:20 회차 창 판정 · 기록 `backfill_reinforcement`) · `krx_holdings_stocks` · `_now` · `run_krx_only` docstring | 580 (563) |
| `app/oci_startup_status.py` | 수정 — 블록 2개 · 숨은 `oci_param_values` · 행 재노출 | 371 (343) |
| `app/api_oci_startup_status.py` | 수정 — 요청 때 `운영 기준 활성` 행 | 76 (54) |
| `app/api_three_push_param.py` | 수정 — '전달' 메시지 · `latest_param_path` · `last_sync_succeeded` | 389 (359) |
| `app/api.py` | 수정 — 주석 1줄(원래부터 근접 600 위 파일) | 642 (641) |
| `frontend/app/components/OciStatusView.tsx` | 수정 — 두 행 라벨 · 상태 · `reloadKey` | 238 (221) |
| `frontend/app/components/ThreePushParamCard.tsx` | 수정 — '전달' 문구 · 안내 1줄 · `onDelivered` | 222 (206) |
| `frontend/app/components/ApprovalTelegramView.tsx` | 수정 — ② → ① 다시 읽기 연결 | 61 (55) |
| `frontend/lib/api/ociStartupStatus.ts` · `threePushParam.ts` | 수정 — 주석 | 31 · 50 |
| `.gitignore` | 수정 — `state/market/krx_stock_backfill_ledger.json*` | — |

테스트(신규 3 · 수정 10): 신규 `tests/test_poc3_02d_ops04_krx_backfill_retry.py`(631) · `tests/test_poc3_02d_ops04_krx_stock_prices.py`(1,057) · `tests/test_poc3_02d_ops04_oci_status_rows.py`(400). 수정 `tests/conftest.py`(라이브 KRX 가드에 개별주 경계 · `_SYNC_STATUS_PATH` 격리) · `tests/_helpers.py`(`stock_basis_source`) · `tests/test_holdings_selection.py` · `tests/test_poc3_02d_ops03_briefing.py` · `tests/test_poc3_02d_ops03_consumer_isolation.py` · `tests/test_poc3_02d_ops03_krx_batch.py` · `tests/test_poc3_02d_ops03_price_basis.py` · `frontend/app/components/{OciStatusView,ThreePushParamCard,ApprovalTelegramView}.test.tsx`.

문서: `docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md`(최종 업데이트 줄 · POC5 블록 '다음' 줄 — OPS-04 상태 · POC5-01A 종료 수용 · POC5-01B HOLD) · `docs/backlog/BACKLOG.md` · 설계서(신규 · 끝에 판정 · 사용자 결정 원문) · PLAN(신규 · 확정) · 이 결과서(신규).

## 3. 신규 추가된 의존성

없음(httpx 는 기존 의존성 · OCI · PC 모두 0.28.1 실측).

## 4. 지시문 외 변경 (PLAN 이 정하지 않은 개발자 결정)

1. **개별주 '빈 날' 은 날짜 단위**(그날 보유 개별주 행이 하나라도 있으면 저장된 날). 거래정지 종목 때문에 매일 창 전체를 다시 부르지 않으려는 선택이다. 대신 나중에 새로 보유한 개별주는 그 뒤 날짜부터 쌓인다(BACKLOG 등재).
2. **개별주 목표일(T-1)은 ledger 밖 · 저장될 때까지 칸마다**(ETF 목표일 시도와 같다 · `krx_backfill` 머리말 '목표일 시각표 시도는 채우기가 아니다'). PLAN §2-1 3 '날마다 T-1 1호출' 은 08:10 첫 칸에 저장되는 평소 경우다 — 공개 전이면 08:10 배치 최대 4회 + 09:20 · 수동 실행 각 1회. PLAN §2-5 '개별주 누락일도 같은 규칙' 은 창 날짜에 적용했다.
3. **헛조회 방지 = 응답에 보유 행이 하나도 없으면 그 실행을 끝낸다**(목표일 · 창 어느 날이든). 재작업 전의 '목표일이 저장돼야 창을 채운다' 조건을 대체했다(그 조건은 PLAN §2-1 3 이탈이었다 · §6-0-2). 목표일이 저장되지 않은 채 끝나면 `no_held_kospi_stocks`, 저장된 날이면 `incomplete`. 코스피 개별주 보유 0 이면 실행(08:10 배치 · 09:20 · 수동)마다 목표일 1회 — 목표일이 아직 공개 전이면 창 날짜 1개를 더 부른 뒤 끝난다(실행당 2회 · 창 날짜는 ledger 로 실행마다 다른 날).
4. **목표일 조회가 원천 오류인 칸은 창을 부르지 않는다**(ETF 채우기와 같은 규칙 · 설계자 RESULT STEP 6 — 불통 중 ledger 소모 방지). 창 조회가 원천 오류면 그 칸을 끝내고 다음 칸이 남은 날을 잇는다.
5. **창 채우기는 자기 다음 칸 시각에서 멈추고 그 칸에서 잇는다** · **칸마다 시각을 다시 읽는다**(재작업 검토 지적 반영) — 개별주 칸은 ETF 칸과 같아 ETF 시도는 많아야 개별주 호출 1회만큼 늦고, 앞 곁 작업이 오래 걸려도 08:27 뒤 새 개별주 시도가 없다. KOSPI 재시도 칸은 따로 정해져 다를 수 있다(§5-3).
6. **곁 작업 묶음 `_Sides`** — 같은 칸이면 넘겨받은 순서(KOSPI → 개별주) · 예외를 낸 곁 작업만 그 실행에서 뺀다. 곁 작업을 만들다 예외 = `holdings_stocks = {status: unexpected:…}` · 칸을 돌다 예외 = `stopped = unexpected:…` · ETF 단계가 예외로 끝나면 개별주 요약을 로그 한 줄로 남긴다(배치 상태에는 실리지 않는다 · 호출 · 저장은 일어난다).
7. **ledger 의 빈 `retryable` 은 쓰지 않는다** — PLAN 의 모양 `{date_kst, calls, retryable}` 에서 비었을 때만 키를 뺀다(옛 형식과 같아 롤백 안전 · 기존 정확 비교 테스트 유지).
8. **보강은 09:20 회차 창(09:20:00 ~ 09:29:59 KST)에 시작한 `run_krx_only` 만**(검증자 r1 정정 · 설계자 수용 2026-10-06) — cron 09:20 줄과 수동 `--krx-only` 는 같은 명령이라 시작 시각으로 가른다(`krx_backfill.in_reinforcement_window` · 실행 기록 `backfill_reinforcement`). 창 밖 수동 실행(08:40 · 10:05 등)은 보강하지 않는다. T-1 을 08:10 에 받은 날은 보강 기회도 남는다(테스트 `test_manual_krx_only_outside_0920_window_does_not_reinforce`) — 못 받은 날은 §5-2. cron 변경 0.
9. **죽은 코드 제거**: `krx_backfill.read_calls_today`(이번에 대체) · `holdings_selection_source.load_price_history`(개별주 FDR 을 더 읽지 않아 호출 0) · 재작업 전 `krx_stock_sync.sync_holdings_stocks` · `krx_target_sync._sync_stocks`(곁 작업으로 대체). `load_basis_history` 의 `fetch_history` 인자는 POC5-01A 경계 때문에 서명에 남겼다(쓰지 않음).
10. **화면(목업 밖 세부 · 사용자 확인 완료)**: '운영 기준 활성' `확인 불가` 문구 변형 2개(`전달한 운영 기준을 읽지 못함` · `전달한 운영 기준과 비교하지 못함`) · 안내 1줄은 `전달 완료` 일 때만 · 카드 실패 안내 문단과 진행 중 버튼(`전달 진행 중...`)도 '전달' · `확인 필요` 메시지 '한 번 더 전달 후' · '— 전달만 되고 활성화되지 않음' 꼬리말은 **지금 PC 운영 기준이 실제로 전달된 경우에만**(전달 기록의 PARAM 이 지금 기준과 같을 때 · 식별자는 내부 비교만).
11. **값 비교 규칙**: `enabled_push_kinds` 는 집합(러너는 포함 여부만 본다 · 순서만 다르면 일치) · 분모 = 정책 키 수 + 두 쪽 종류 합집합 수(같으면 14).
12. **② 전달 뒤 ① 다시 읽기**(`onDelivered` → `reloadKey`) — PLAN §2-6 '같은 세션에서 값을 바꿔 적용하면 바로 다름' 을 지키려면 필요했다. OCI 는 다시 읽지 않는다.
13. **`app/oci_status_rows.py` 분리** — `oci_startup_status.py` 가 580줄(근접 600)이 돼 새 책임을 새 모듈로 옮겼다(동작 동일 · 재노출).
14. **conftest 격리 추가**: `api_three_push_param._SYNC_STATUS_PATH` — 그 전에는 `/state` 테스트가 라이브 PC 전달 기록을 읽고 있었다(읽기만).
15. **PLAN §1-4 사실 정정**: 행 순서 창 `resolve_window` 의 호출부 `krx_sync.sync_krx_daily` 는 운영 호출이 0인 죽은 경로다(PLAN 은 '08:10 정합성 판정 기록에 쓰인다' 고 적었다). 고치지 않았다.
16. **개발 중 실제 KRX 조회 3회 · OCI 읽기 확인**(§8-6) — 필드 이름 · 공개 시각을 저장소에 근거로 남기기 위해서다.
17. **PROGRAM_TRUTH 의 지난 문구 3곳 정정**(이 단계 대조 중 발견 · OPS-03 배포 전 표현) — 정기 스케줄 행 · scheduler · 평상시 자동 운영의 'OPS-03 배포 회차에 바뀐다(아직 적용 전)' → '2026-10-01 배포로 바뀌었다(2026-10-02 부터)'. `sync_krx_target` docstring '예외를 올리지 않는다' 도 실제(ETF 단계 예외는 곁 작업을 마저 돈 뒤 다시 올림 · OPS-03 부터 같은 동작)대로 고쳤다.

## 5. 알려진 한계 / 미완성

1. **영업일의 개별주 공개 시각 미실측** — 2026-10-06 실측: 휴일 10-05 08:10 에 ETF 10-02 자료는 이미 있었고(OCI 로그 1,171행), 개별주 10-02 는 10-06 00시대 0행 · 10:1x 942행. 영업일에 08:24 까지 공개 전이면 09:20 1회가 마지막이고, 그때도 공개 전이면 그날 목표일은 다음 날 창 채우기로 들어간다 — **배포 뒤 첫 영업일 08:10 `krx_holdings_stocks.target_attempts` 로 확인**(§10).
2. **08:10 에 ETF T-1 을 못 받은 날, 창 밖 수동 `--krx-only`(예 08:40)가 ETF 목표일을 조회하면 OPS-03 하루 1회 가드(확정 계약 7 · `attempted`)가 09:20 정기 회차를 통째로 건너뛴다** → 그날 09:20 보강(ETF · 개별주 창 · 목표일 재시도)이 돌지 않는다. 테스트 `test_manual_krx_only_attempting_t1_blocks_the_0920_run` 로 지금 동작을 고정했다. 설계자 2026-10-06 '이번 라운드는 r1 3건만' 에 따라 고치지 않았다(설계자 RESULT 판정 때 보고).
3. **첫 실행(표 없음) · 장애 뒤처럼 창이 빈 날** — 개별주 호출이 많다(창 30날 + 목표일 = 08:10 배치 최대 34회 · 목표일이 첫 칸에 저장되면 31회 · 호출당 timeout 40초). 다음 칸 시각에서 멈추므로 ETF 시도는 많아야 개별주 호출 1회만큼 늦는다. KOSPI 재시도 칸은 벤치마크 단계 시각으로 정해진다 — KRX 단계가 KOSPI 칸 직전 60초 안에 시작하면(그 칸이 개별주 · ETF 칸에서 빠짐) 그 KOSPI 재시도는 개별주 다음 칸까지 밀려 합쳐질 수 있다(KOSPI 는 PC 표시용 · 08:30 입력 아님). 실제 응답 시간은 미실측이다.
4. ledger 잠금 없음 — 겹친 수동 실행이면 날짜별 2회 상한이 깨질 수 있다(기존부터 있던 경쟁 · BACKLOG).
5. 09:20 에 T-1 도 없고 목표일 조회가 원천 오류면 채우기를 부르지 않아 그날 보강 기회를 잃는다(원천 불통 중 채우기 금지 계약 · ETF 테스트 고정 · 개별주도 같은 규칙).
6. ETF 창 채우기 결과는 로그에 따로 남지 않는다(배치 상태 JSON · 09:20 기록 · ledger) — 개별주 곁 작업은 칸마다 로그 한 줄(목표일 저장 여부 · 남은 날 수 · 멈춘 사유 · 호출 날짜 목록은 배치 상태 JSON 에만). 09:20 이 `already_loaded` 면 같은 날 수동 `--krx-only` 가 09:20 기록을 덮는다.
7. AC1 범위는 PUSH 다 — PC 보유 미리보기 · PC 보유 evidence 단기 흐름은 FDR 그대로 · 08:10 FDR 단계도 보유 개별주를 계속 갱신한다(배치 상태 · 스파이크 판정 결합 그대로).
8. 기존부터 있던 화면 문제(이번에 바꾸지 않음): 전달 결과 `partial`(검증만 실패) → 카드 `미전달` · 실패 문구 끝 '운영 상세에서 마지막 확인 시각을 확인하세요.'(그런 화면 없음) · dt `적용 기준` · `마지막 적용` · `적용 내용 해시` · 화면 머리 · ② 제목 · 사이드바 힌트는 목업대로 그대로.
9. POC5-01A 동등성 도구(`scripts/poc5_01a/runner_split_equivalence.py`)는 이제 rc 2 — 그 단계가 '바뀌면 안 되는 기존 모듈' 로 고정한 20개 중 4개를 이번에 의도적으로 고쳤다. 설계자 2026-10-06: 결함 아님 · 고치지 않음 · 과거 증명은 `87238e1e` 기준.
10. 목업 생성기 `scripts/build_market_briefing_mockups.py` ⑨ 는 여전히 `fdr_price_failed` 사유를 넘긴다(개발 도구 · 출력 문구 같음 · 고치지 않음).
11. 연도 파일 없는 해의 평일 기본 운영은 사용자 확정 계약이라 그대로다 — 개별주 창도 그 축을 쓰므로 그런 해에는 평일 휴장일을 날마다 1회 부르고 그날 상태가 `incomplete` 다(ETF 채우기와 같은 구조).
12. 09:20 회차 창(10분) 안에서 시작한 수동 `--krx-only` 는 cron 과 구별되지 않는다 · cron 이 09:30 뒤에 시작하면 보강하지 않는다. 창 판정은 PC · OCI 시계를 KST 로 바꿔 본다.
13. 보유 코스피 개별주가 모두 창 시작 뒤 상장한 종목이면 상장 전 창 날짜에서 실행마다 끝나 창이 늦게 찬다(상태 `incomplete` · 설계 범위 = 현재 보유 3종 밖).

## 6. 다음 검증자(Codex)에게 알릴 점

### 6-0-1. 검증자 r1 REJECTED(2026-10-06) 처리

| 지적 | 처리 |
|---|---|
| A-1 · A-3 수동 `--krx-only` 가 보강(PLAN §2-5 이탈 · 08:40 수동이 09:20 기회를 먼저 씀) | 보강 표시를 09:20 회차 창에 시작한 실행만으로 좁혔다(§4-8 · 설계자 수용 2026-10-06). 테스트: 08:40 수동 호출 0 · ledger 그대로 → 09:20 보강 1회 → 10:05 수동 호출 0 · 창 경계 6건(+ UTC 입력). T-1 을 못 받은 날의 다른 경로(하루 1회 가드)는 §5-2 한계 |
| A-1 `RemoteProtocolError` 가 잘못된 HTTP 응답까지 재시도(승인 범위 확대) | r1 정정에서 뺐다 → **설계자 2026-10-06 결정으로 일시 오류에 포함**(연결 끊김 · 잘못된 응답 모두 · 오류 문자열로 나누지 않는다 · 원문 = 설계서 끝). 테스트: `illegal status line` · `server disconnected` 모두 일시 오류 · 08:10 실패 → 09:20 보강 1회 시나리오에 `remote_protocol` 추가 |
| A-2 결과서 '바뀐 파일 최대 571' 오류 | 바뀐 Python · TS 전부를 다시 쟀다(§2 · §8-1) — 최대 `app/api.py` 642(주석 1줄 · HEAD 641) |

### 6-0-2. 재제출 전 개발자 점검(2026-10-06) 처리

r1 정정 뒤 PLAN 계약 문장으로 다시 대조했다. 이 점검의 '코드 재작업' 두 건은 사용자 결정으로 했다. 설계자 2026-10-06 판정('이번 라운드는 3건만 · 추가 구조 개선 없음')은 이 재작업보다 뒤에 왔다. 그래서 사용자에게 다시 물었고, 사용자는 **'유지'** 를 골랐다. 근거는 이것이 구조 개선이 아니라 확정 PLAN 원문과의 일치 정정이라는 점이다.

| 발견 | 처리 |
|---|---|
| PLAN §2-1 2 이탈 — 개별주가 **ETF T-1 을 받은 뒤에만** 돌았다(ETF 실패 날 호출 0) · 목표일을 ledger 하루 1회로 불러 08:15 · 08:20 · 08:24 재시도가 없었다 | 개별주를 **KRX 단계의 곁 작업**(`HoldingsStockTask` · KOSPI 재시도와 같은 자리 · `_Sides`)으로 바꿨다 — ETF 와 독립 · 같은 시각표 · 마감 08:27 · 같은 시각이면 ETF 먼저 · 09:20 · 수동 = 1칸 |
| PLAN §2-1 3 이탈 — '목표일이 저장돼야 창을 채운다' 조건(PLAN 에 없음 · 목표일이 공개 전이면 그날 창 0) | 조건을 없앴다. 헛조회 방지는 '응답에 보유 행이 없으면 그 실행 끝'(§4-3) |
| 문구 과대 — '창 밖 수동 실행은 보강 기회도 쓰지 않는다' 는 T-1 을 08:10 에 받은 날에만 맞다 | 코드 주석 · 테스트 docstring · PROGRAM_TRUTH · 이 결과서 문장을 좁혔다 · 한계 §5-2 · 테스트로 지금 동작 고정 |
| r1 정정이 작업 트리에만 있고 staged 가 아니었다 | 이번에 모두 stage(§9) |
| `run_krx_only` docstring 에 09:20 회차 창 조건 누락 | 추가(+ 개별주 곁 작업 · 하루 1회 가드는 ETF 목표일 시도만 센다) |
| 결과서 §9 git 수치 · POC5-01A 상태가 지난 값 | 교체(§9 · 머리말) |

### 6-1. 검토에서 확인돼 반영한 지적

- 1차(구현) 백엔드(3관점 · 반박 검증 · 24건 중 실제 9건): 보유 코스피 개별주 0 일 때 09:20 헛조회 30회(→ 그때 목표일 저장 조건 · 재작업에서 '보유 행 없는 응답이면 실행 끝' 으로 대체) · 08:10 호출부가 보강 표시를 넘기지 않음을 실제 호출 자리에서 고정 · 개별주 ledger 안전 분기 3건 · 저장 실패 분기 · 마감 공유 · 헛도는 단언 2건.
- 1차 화면(2관점 · 반박 검증 · 17건 중 실제 4건): PROGRAM_TRUTH 옛 문구 3곳 · ① 다시 읽기가 앞선 오류를 지우지 않음 · 꼬리말이 다른 PARAM 의 전달 기록을 믿음 → PC 기준 식별자 내부 대조.
- 2차(재작업 · PLAN · 코드 · 문서 3관점). PLAN 관점 4건 중 실제 3건이다. 코드 6건 · 문서 7건은 반박 단계 에이전트가 멈춰서, 개발자가 코드를 직접 읽어 확인했다. 반영한 것:
  - **창 채우기가 다음 ETF 시도를 늦출 수 있음**(ETF 08:10 실패 · 창이 빈 날 · 호출 1회 9초 이상) → 다음 칸에서 멈춤(§4-5)
  - **같은 칸의 앞 곁 작업이 오래 걸리면 개별주 마감 판정 · 기록 시각이 어긋남** → 시각 다시 읽기
  - **ETF 단계 예외면 개별주 기록 유실** → 로그 한 줄
  - **창 날짜 `no_held_rows` 를 `no_held_kospi_stocks` 로 적음** → 목표일 저장 여부로 가름
  - **테스트 공백 3**: 할 일을 다 하면 남은 칸을 비움 · ledger 쓰기 실패 메모리 되돌림 · 칸별 멈춤 사유 초기화
  - **문서 문구 8**: 첫 실행 최대 34회 · 상태 이름 · `run_krx_only` docstring 의 ETF/개별주 구분 · 연도 파일 없는 해 · `stopped` 조건 · ledger 설명 · 창 31 = 21 + 10 설명 · 결과서 미갱신
- 3차(최종 대조 · 결과서 · 문서 2관점 · 코드 동작 결함 0): 문장 14건 정정 — KOSPI 지연 범위(개별주 칸 = ETF 칸 · KOSPI 칸은 다를 수 있음 · §5-3) · 보유 0 호출 수(목표일 공개 전이면 실행당 2회) · 로그 범위(ETF 채우기만 로그 없음) · STATE 변경 범위 · STATE POC5 '다음' 줄 OPS-04 상태 · PROGRAM_TRUTH OPS-03 지난 문구 3곳(§4-17) · 보강 대상 = 첫 호출(보강 아닌 실행) · `sync_krx_target` docstring 예외 설명 · `transient` 는 배치 JSON 만 · 호출 수 요약에 보강 1회 · 결과서 staged 문장(§9 실측으로 해소).
- 반박된 지적: 1차 백엔드 15 · 화면 13(주로 PLAN 결정 그대로 · 실제 도달 불가 · 기존 동작) · 2차 1(최근 상장 종목만 보유 — 범위 밖 · 상태 이름만 고치고 §5-13 한계).

### 6-2. 판단이 어려웠던 부분

1. **재작업과 설계자 '3건만' 지시**(§6-0-2) — 사용자 결정으로 유지했다. 검증 기준은 확정 PLAN §2-1 2 · 3 원문이다.
2. **개별주 목표일 ledger 밖**(§4-2) — PLAN '날마다 T-1 1호출' 과 '하루 1회 ledger' 를 함께 읽은 해석이다(ETF 목표일과 같은 구분). 호출 수는 공개 전인 날에만 늘어난다(08:10 배치 최대 4 + 09:20 1).
3. **09:20 회차 창 10분**(§5-12) — 창 안 수동 실행은 cron 과 구별되지 않는다. cron 이 먼저 보강한 날짜는 날짜별 2회 상한이 막는다.
4. **KS-10** — `krx_target_sync.py` 494 → 594(+100 · 근접 600 아래 · 트리거 650 아래). 이 단계에서 보강 표시 · 곁 작업 묶음(`_Sides` · `_stock_task`) 책임이 더해졌다. 개별주 본체는 새 모듈 `krx_stock_sync.py` 에 있다.
5. **개별주 목표일 공개 시각**(§5-1) — 첫 영업일 확인 전에는 '영업일 08:10 공개' 를 주장하지 않는다.

### 6-3. 확인할 곳

- 개별주 응답 필드(2026-10-06 실측): `BAS_DD` · `ISU_CD`(6자리) · `ISU_NM` · `MKT_NM`(KOSPI) · `SECT_TP_NM` · `TDD_CLSPRC` · `TDD_OPNPRC` · `TDD_HGPRC` · `TDD_LWPRC` · `CMPPREVDD_PRC` · `FLUC_RT` · `ACC_TRDVOL` · `ACC_TRDVAL` · `MKTCAP` · `LIST_SHRS` · ETF 없음 · 공개 전 0행.
- 곁 작업 시나리오 테스트(`tests/test_poc3_02d_ops04_krx_stock_prices.py`): `test_stock_task_runs_on_timetable_even_when_etf_t1_not_obtained` · `test_0810_etf_goes_first_then_stock_task_and_etf_table_untouched` · `test_slow_stock_window_fill_does_not_push_back_etf_attempts` · `test_stock_slot_rereads_the_clock_after_a_slow_side_task` · `test_other_side_task_error_does_not_stop_the_stock_task` · `test_stock_step_error_is_recorded_and_other_side_task_keeps_running` · `test_etf_stage_exception_logs_the_stock_summary` · `test_window_fills_even_when_target_is_not_stored_and_target_retries`.
- 원격 블록은 로컬 bash 로 실제 실행해 테스트한다(`test_remote_blocks_run_in_bash_read_only` — DB 해시 · 수정 시각 불변).
- 라이브 KRX 가드가 새 경계를 막는다(`test_live_guard_blocks_default_stock_fetcher`).

## 7. 사용자 확인이 필요한 항목

**2026-10-06 사용자 확인 완료** — 아래 1 · 2 · 3 · 6 을 확인 · 동의했다(사용자: "다 확인했습니다. 좋습니다."). 재작업 유지는 사용자 결정(2026-10-06 · §6-0-2)이다.

1. **발송 내용 변화**(배포 뒤):
   - 보유 브리핑 · 장중 위험 알림에 개별주 3종(000660 · 005930 · 006400)의 20거래일 하락 판정 · 고점 대비가 다시 나온다(개별주 표가 차면 · 지금은 늘 `20거래일 데이터 확인 불가` 그룹). 반영 첫날 12:30 · 15:40 변화분에 개별주 변화가 나올 수 있다.
   - 08:30 시장 브리핑: 낼 내용이 없는 날 FDR 단계만 실패했으면 예전에는 '고지만 담은 본문' 을 보냈지만 이제 보내지 않는다(1건 → 0건).
   - 09:20 보강이 창 날짜를 채우면 같은 날 09:30 부터 장중 「신규 진입 검토」 · 12:30 · 15:40 ETF 고점 대비가 돌아올 수 있다.
2. **목업 밖 화면 세부**(§4-10).
3. **실화면 확인**(AC10) — PC 백엔드 재기동 뒤 「OCI 운영·적용」 ① 두 행 · ② 카드.
4. **재작업 뒤 바뀐 것은 발송 · 화면이 아니다** — 개별주 값이 채워지는 조건이 넓어졌다(ETF 실패 날도 · 목표일 재시도). 1 의 발송 변화 범위 안이다. 프론트 변경 0.
5. **커밋 · push** — 검증자 r2 VERIFIED 뒤 사용자 승인(2026-10-06). **OCI pull** 은 사용자 몫 · 따로 정한다.
6. **개발 중 실제 KRX 조회 3회**(§8-6 · 승인된 API · 읽기만).
7. **운영 참고(§5-2)** — 08:10 에 ETF T-1 을 못 받은 날 09:20 전에 수동 `--krx-only` 를 돌리면 그날 09:20 보강이 돌지 않는다.

## 8. 검증 실측

### 8-1. 형식 · 정적

- black · flake8: 바뀐 Python 파일 전부 통과(`git diff HEAD` 의 Python 30개 · black --check · flake8 · py_compile rc 0 · 2026-10-06 19:56).
- 프론트: `npx tsc --noEmit` rc 0 · `npm run lint` rc 0 · `npx vitest run` 24파일 296 passed(2026-10-06 19:56).
- production build: 저장소 밖 사본(`frontend/` rsync · node_modules 링크)에서 `npm run build` rc 0(r1 전 · 그 뒤 프론트 변경 0) · 저장소 `frontend/.next` 손대지 않음.
- KS-10(바뀐 · 새 Python · TS 전부 `wc -l` 실측 · §2): 운영 코드 최대 `app/api.py` **642**(주석 1줄 · HEAD 641 · 원래부터 근접 600 위 · 트리거 650 아래) · 그다음 `app/market_briefing/krx_target_sync.py` 594 · `scripts/run_oci_market_data_batch.py` 580. 프론트 최대 `OciStatusView.tsx` 238(근접 850 아래). 테스트 최대 `tests/test_poc3_02d_ops04_krx_stock_prices.py` 1,057(근접 1,450 아래 · OPS-04 항목 1 전용).

### 8-2. focused test

- 새 3파일 119(09:20 보강 50 · 개별주 공식 종가 42 · ① 두 행 27 · `--collect-only`).
- 재작업 · 검토 반영 뒤 KRX 묶음(`test_poc3_02d_ops04_krx_stock_prices.py` · `test_poc3_02d_ops04_krx_backfill_retry.py` · `test_poc3_02d_ops03_kospi_retry.py` · `test_poc3_02d_ops03_krx_batch.py`): 178 passed.
- (참고 · 재작업 전 값) 바뀐 영역 주변 묶음 1,583 passed(2026-10-06 오전 · 검토 반영 전).

### 8-3. 동작 확인(대표 시나리오 · 테스트)

- 개별주 곁 작업: ETF 먼저 · ETF 실패 날도 시각표대로 · 목표일 공개 전이면 창을 먼저 채우고 다음 칸에 목표일 · 목표일 원천 오류 칸은 창 호출 0 · 창 원천 오류면 다음 칸이 잇는다 · 보유 행 없는 응답이면 실행 끝 · 마감 08:27(앞 곁 작업이 늦어도) · 다음 칸에서 멈춤 · 09:20 1칸 + 보강 · 별도 ledger · 보유 행만 · ETF 표 불변 · 곁 작업끼리 예외 격리 · ETF 단계 예외 로그 · 저장 실패 기록.
- 가격 기준: 개별주 = KRX 종가(FDR 이 달라도) · 표 못 읽으면 그 종목만 닫힘 · KRX 행 없으면 FDR 로 되돌아가지 않음 · 구간 빠지면 고점 대비만 생략.
- 09:20 보강: 일시 오류(timeout · 연결 · `RemoteProtocolError` · 503 · 429)만 · 영구(404 · 401 · RuntimeError · 검증 실패) 아님 · 3번째 호출 없음 · 08:10 재채우기 · 수동 `run` 보강 없음 · 창 밖 수동 보강 없음 · T-1 미확보 날 08:40 수동 → 09:20 건너뜀(§5-2 고정).

### 8-4. 파괴 시험(사본 폴더 · 저장소 · state · logs 미접촉)

- 1차 18종 중 처음 15종 탐지. 못 잡은 3종 가운데 실제 위험 2종(S13 · S17)에 테스트를 더했고, 재시험에서 모두 탐지했다. r1 정정 뒤 4종도 모두 탐지했다.
- 재작업 12종 12/12 탐지(KRX 묶음 기준선 173 passed) — 개별주 곁 작업 빠짐 · 목표일 저장 조건 부활 · 목표일 원천 오류 뒤 창 호출 · 창 `no_held_rows` 계속 · 마감 검사 제거 · `_Sides` 예외 격리 제거 · ETF 첫 시도 앞 곁 작업 · 창 원천 오류에서 실행 종료 · 보강 표시 끊김 · 저장된 목표일 재조회 · 목표일 ledger 하루 1회 · 상태 이름.
- 재작업 검토 반영 7종 7/7 탐지(기준선 178 passed) — 다음 칸 멈춤 · 시각 다시 읽기 · ETF 예외 로그 · 상태 이름 · 남은 칸 비우기 · 칸별 멈춤 사유 초기화 · ledger 쓰기 실패 메모리 되돌림.

### 8-5. OCI 실측(2026-10-06 · 읽기 전용)

- 새 기동 읽기 명령(PC 코드가 만든 그대로)을 OCI 에서 1회 실행: rc 0 · 5블록 · 출력에 `param-` 없음.
- `장중 대표 ETF` = `정상` `기준일 10/2 · 27/27 준비됨 (10/6 09:20 확인)` · `운영 기준 활성` = `일치` `(14/14)` — OCI 활성 버전(09-07)과 PC 기준(10-04)은 다르지만 값 14개가 같다.
- PC · OCI KRX 키 같음(해시 앞 12자리 대조 · 값 미출력) · httpx 0.28.1 둘 다.

### 8-6. KRX 조회(승인된 `sto/stk_bydd_trd` · 읽기만 · PC)

| 시각(KST) | basDd | 결과 |
|---|---|---|
| 10-06 00:2x | 20261002 | HTTP 200 · 0행(익영업일 08:00 전) |
| 10-06 00:2x | 20261001 | HTTP 200 · 942행 · 필드 확정 · 보유 3종 종가 |
| 10-06 10:1x | 20261002 | HTTP 200 · 942행 · 보유 3종 포함 |

### 8-7. 전체 회귀

백엔드 전체 `pytest tests` 1회(최종 코드 · 재작업 · 설계자 결정 · 검토 반영 뒤): **2833 passed · 0 failed · exit 0 · 379.30s**(2026-10-06 19:49:26 ~ 19:55:47 KST · `caffeinate -i`). 실행 전후 PC `state/` · `logs/` 1,153파일 sha256 목록이 같다(diff 0) — 라이브 상태를 쓰지 않았다. r1 정정 뒤 실행(같은 날 16:41 ~ 16:47)은 2818 passed 였다(+15 = 개별주 29 → 42 · 09:20 보강 48 → 50). 이 회귀 뒤에 바뀐 것은 최종 대조(§6-1 3차)로 고친 docstring · 주석 3파일(`krx_stock_sync.py` · `krx_target_sync.py` · `run_oci_market_data_batch.py` · 로직 0 · 줄 수 그대로)과 문서뿐이다 — py_compile · black · flake8 · KRX 묶음 4파일 178 passed 로 다시 확인했다.

## 9. git 상태

검증자 r2 는 커밋 전 staged 45개(신규 `A` 9 · 수정 `M` 36 · unstaged 0)를 기준으로 판정했다. 구성 = 운영 26 · 테스트 13 · 문서 6(`docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md` · `docs/backlog/BACKLOG.md` · 설계서 · PLAN · 이 결과서). 그 45개를 커밋 1개로 남겼다(사용자 승인 2026-10-06) — 커밋 내역은 `git show --stat <SHA>` 로 확인한다. VERIFIED 뒤 커밋 전에 바꾼 것은 상태 문구뿐이다(이 결과서 머리말 · §7-5 · §9 · §10-1 · `docs/STATE_LATEST.md` · `docs/PROGRAM_TRUTH.md` 최종 반영 줄). `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` 는 사용자 소유 untracked 파일이라 커밋하지 않았다. 커밋 SHA 는 이 문서에 적지 않는다(자기참조).

## 10. 배포 절차(승인 뒤)

1. 검증자 r2 VERIFIED(2026-10-06) → 커밋 · push(사용자 승인 2026-10-06) → 설계자 RESULT 판정.
2. OCI `git pull`(사용자 · 거래일 08:05 ~ 15:45 제외). cron · `.env` 변경 없음(기존 KRX 키).
3. PC 백엔드 재기동 — ① 두 행이 보인다(원격 블록은 PC 코드라 OCI 코드가 필요 없다).
4. OCI 읽기 전용 확인: 새 모듈 3개 · `.gitignore` · import.
5. 첫 영업일: 08:10 `krx_holdings_stocks`(mode `scheduled` · slots · `target_attempts` 결과 = 영업일 공개 시각 §5-1 · 첫 채우기 `called` 수 · status · stopped) · 개별주 표 행 수 · 08:30 정상 · 09:15 보유 브리핑 개별주 파생값 · 09:20 기록 · 로그 Traceback 0.
6. 롤백 = 커밋 revert + OCI pull. 새 표 · 개별주 ledger 는 남아도 옛 코드가 읽지 않는다 · ETF ledger 의 `retryable` 은 옛 코드가 무시한다(`calls` 만 읽음).
