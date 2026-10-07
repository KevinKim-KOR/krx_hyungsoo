# POC5-01B 개발 결과서 — OPERATIONAL_DECISION_EVENT_LEDGER

작성 2026-10-07 · 갱신 2026-10-07(검증자 r1 REJECTED 정정) · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex)

```text
STATUS                 = IMPLEMENTED_VERIFIED — 검증자 r3 VERIFIED(2026-10-07 · 위험 NONE · 범위 폭주 NONE) · 커밋 · push(사용자 승인 2026-10-07) · 설계자 RESULT 판정 대기 · OCI 배포는 설계자 RESULT 판정 뒤
                         사용자 승인(배포 게이트 = OPS-04 첫 거래일 확인 · 종료 · 설계서 §10)
STEP_ID                = POC5-01B 운영 의사결정 이벤트 원장
VERIFIER               = r1 REJECTED(2026-10-07 · A-1 · A-2 · A-3 · 위험 MEDIUM · 범위 폭주 NONE) → 처리 §6-0 → r2 REJECTED(2026-10-07 · r1 지적 모두 해결 · A-2 · A-3 = §8-5 원장 모듈 최대 줄 수 516 → 실측 514 · 코드 재작업 없음 · 위험 NONE) → §8-5 정정 → **r3 VERIFIED**(2026-10-07 · A-1 ~ A-4 통과 · B-1 ~ B-6 없음 · 위험 NONE · 범위 폭주 NONE)
DESIGN                 = docs/ai_design/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_DESIGN_V1.md (설계자 2026-10-06 새 판 · 끝에 PLAN 판정 원문)
PLAN                   = docs/ai_plan/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_PLAN_V1.md (설계자 PASS_WITH_MANDATORY_AMENDMENTS 2026-10-06 · 필수 보정 5)
PREDECESSOR/SUCCESSOR  = POC5-01A + POC3-02D-OPS-04 → POC5-02
BASE_COMMIT(코드 기준)  = a308353c (OPS-04 커밋)
CODE_FILES             = 신규 5(원장 모듈 4 + 대조 CLI 1) · 수정 10(러너 1 + 수집 자리 8 + .env.example) · DB 스키마(runtime_state) · cron · 의존성 · 공개 API 0
TESTS                  = 원장 새 테스트 3파일 71 passed(저장소 26 · 항목 20 · 러너 25) · 기존 테스트 3파일은 대역 서명만(단언 변경 0)
REVIEW                 = 3관점 독립 검토 1회 · 지적 17 · 실제 12(반박 검증) — 결함 5 · 문서 1 · 테스트 공백 6 모두 반영(§6-2)
SABOTAGE               = 검토 때 14종 중 13종 탐지(L13 놓침) → 보강 뒤 놓친 L13 · 약한 L5 · 테스트 공백 변형 7종 모두 탐지 · r1 정정 4종 · 옆칸 정정 4종 탐지(§8-3)
KS-10                  = 트리거 0 · sector_signal.py 595 → 611 NEAR(보정 5 · 600 ~ 649 기록 후 계속)
BACKEND_FULL_REGRESSION= 2904 passed / 0 failed · exit 0 · 377.35s(2026-10-07 13:46 ~ 13:53 · r1 정정 + 옆칸 정정 최종 코드) ·
                         PC state/logs 1,153파일 해시 전후 동일 · 회귀 시작 뒤 코드 변경 0
CONTRACT_DIFFERENCE    = 본문 · 판정 · 순서 · 발송 수 · 상태 파일 · DB · JSONL · 예외 종류 · 메시지 · exit code 차이 0.
                         단, run() 밖으로 나가는 예외의 traceback 에 원장 모듈 frame 이 더해진다 — 원장 비활성이면 경계 frame 1개 · 원장이 켜진 실행의 insert_status 예외만 2개(경계 + wrap_insert_status)(§6-1)
```

## 0. 요약

OCI 의 운영 PUSH 3종(시장 · 보유 브리핑 · 장중 알림)이 `mode=send` 로 돌 때 전용 SQLite(`state/decision/decision_evidence.sqlite`)에
실행 진입부터 종료까지의 상태(run) · 이미 계산된 종목 · 사업군 · 시장 항목(item) · 전달 결과와 분할 전 본문 · SHA-256(delivery) ·
1회 기록 meta 를 남긴다. 켜는 방법은 OCI `.env` 의 `DECISION_LEDGER_ENABLED=true` 한 줄이다(기존 OCI 역할 표식이 없어 설계서 §3 의
전용 플래그). 플래그가 없거나 dry-run · spike · PC 이면 원장 코드는 아무것도 하지 않는다(파일 open · mkdir · chmod 0회).

러너에는 데코레이터 1개 · 진입 1문장 · `_finish` 안 종료 확정 1문장 · 조립 결과와 발송 본문을 문맥에 싣는 2문장만 더했다.
record 에는 키를 더하지 않는다(DB · JSONL · stdout 불변). 항목 값은 flow 아래 계산 함수 · 결과 객체의 **기본값 있는 수집 자리**로
운반한다(Q-B) — 이미 계산 · 조회된 값만 담고, 새 계산 · 재조회는 0 이다(시세 조회 수 동일 테스트).

원장 쓰기 실패는 PUSH 결과 · 예외 전파를 바꾸지 않는다. 그 실행의 원장 쓰기만 멈추고 기존 logger 에 event_id · 단계 · kind ·
예외 종류만 남긴다. 종료 기록이 실패하면 STARTED 행이 gap 으로 남고, 읽기 전용 대조 CLI 가 정상 · 누락 · gap · 원장에만 있음을 구분한다.

---

## 1. 처리한 요구사항

| # | 요구사항(설계서 · PLAN) | 결과 | 근거 |
|---|---|---|---|
| 1 | §2 OCI 전용 DB 1개 · 4테이블(run · item · delivery · meta)만 · 미래 테이블 0 | DONE | `ledger_store.DDL` · 테스트 `test_connect_secures_dir_and_file_and_creates_only_four_tables` |
| 2 | §2 운영 3종만 · spike 제외 | DONE | `ledger_context.CONTRACT_VERSIONS` · `is_active` · 테스트 `test_dry_run_pc_and_spike_write_nothing` |
| 3 | §2 · §5-2 진입 event_id · STARTED best-effort INSERT | DONE | `LedgerRun.start` · 실패 시 그 실행 원장 중단 · PUSH 계속(`test_ledger_write_failure_does_not_change_push[insert_started]`) |
| 4 | §2 · §5-5 · §5-6 최외곽 종료 확정 · 미포착 예외 failed 확정 뒤 같은 예외 | DONE | `@boundary` + `ContextVar` · `_finish` 안 `led.finalize(rec)` · 테스트 조립 예외 · mark_sent 예외 · insert_status 예외 3종 |
| 5 | §2 · §5-4 flow 반환값 additive payload · 추가 조회 · 재계산 금지 | DONE | 수집 자리 8파일(§2) · `test_intraday_sectors_same_lookups_and_items_recorded`(시세 조회 수 동일) |
| 6 | §2 · §6 비선정 · 억제 · 상한 잘림 · 자료없음 항목 | DONE | `ledger_items` · `ledger_market` · 항목 테스트 16 |
| 7 | §2 kind 별 계약 버전 상수 | DONE | `CONTRACT_VERSIONS`(`<kind>.v1`) · meta `contract_version.<kind>.<v>` |
| 8 | §2 · §7 원장 · runtime 기록 · gap 대조(읽기 전용 · ID · 건수만) | DONE | `scripts/run_decision_ledger_reconcile.py` · `ledger_store.reconcile`(`mode=ro`) |
| 9 | §2 낡은 Decision Outcome Ledger 선행조건 정정 · KS-11 변경 근거 | DONE | MASTER_PLAN · POC3-00 지도 7곳 주석 · KILL_SWITCHES KS-11 기록 · ASSUMPTIONS §3(Q-G) · POC2 인계 문서 2개 미수정(보정 4) |
| 10 | §2 STATE_LATEST §6 Next action 주석(PLAN §3) | DONE | canonical 순서 5번 아래 '[2026-09-26 POC5-00 Q27]' 주석 2줄(OPS-04 종료 커밋 `f0eb6f06` 뒤 · §7-3) · KS-11 기록 위치에 STATE §6 추가 |
| 11 | §3 기본 비활성 · 기존 역할 표식 재사용(없으면 전용 플래그 1개) · hostname 추정 금지 | DONE | `DECISION_LEDGER_ENABLED`(PLAN §1-2 조사: 역할 표식 0건) · `.env.example` |
| 12 | §3 수동 send = off_schedule · PRIMARY 통계 제외 | DONE(Q-A 한계) | `schedule_for` · cohort · `test_off_schedule_first_run_is_legacy_and_sets_no_primary_start` |
| 13 | §3 · AC 10 테스트는 임시 DB · Telegram 대역만 · live 미접근 | DONE | conftest autouse `_isolated_decision_ledger` · 라이브 가드 legacy 목록 추가 0 · state/logs 해시 전후 비교(§8-6) |
| 14 | §4 run 필수 항목 | DONE | `evaluation_run` 22컬럼(PLAN §1-6) · 시장 태그 = `tags_json` |
| 15 | §4 item 필수 항목 | DONE | `signal_item`(+ `evaluable` · §4-1) |
| 16 | §4 delivery 필수 항목(chunk 수 = 계획 chunk 수 · 보정 2) | DONE | `planned_chunk_count = len(_split_message_for_telegram(text))` · 발송 미시도면 NULL |
| 17 | §4 meta(schema · PRIMARY 시작일 · 배포 커밋 · 계약 버전) | DONE | `ledger_meta` INSERT OR IGNORE · git 실패면 키를 비움(Q-F) |
| 18 | §4 스냅샷 · 종료 확정 1회 · 짧은 트랜잭션 · WAL · busy timeout · 재시도 큐 없음 | DONE | `finalize` BEGIN IMMEDIATE · run_state 확인 · rowcount 확인 · UPDATE 경로 0(`test_no_code_path_updates_item_or_delivery`) |
| 19 | §4 권한 OCI 로컬 사용자 한정(보정 1: 못 맞추면 그 실행 원장 중단) | DONE | `_secure` 폴더 0700 · DB 0600 재확인 · 실패 → `LedgerUnavailable` |
| 20 | §6 전이 · exposure(Q-C · Q-D) · 비선정 · 자료없음은 비움 | DONE | `apply_transitions` · 같은 날 같은 state 첫 노출만 PRIMARY · 같은 계열 약화 = repeat |
| 21 | §6 시장: S&P500 상태 · 태그 · 선택된 기초지수 그룹 · ticker | DONE | `market_items` · `market_tags`(Q-H) · `IndexCandidate.tickers` |
| 22 | §7 실패 로그(event_id · 단계 · kind · 예외 종류만) | DONE | `LedgerRun._fail` |
| 23 | §8 AC 1 · 2 비활성 · 활성 동등 | DONE(§6-1 traceback frame — 비활성 1개 · 활성 실행의 insert_status 예외 2개) | `test_ledger_on_off_keeps_body_record_history_db_state_and_order` 3 kind |
| 24 | §8 AC 3 ~ 9 | DONE | §8-2 표 |
| 25 | §8 AC 10 · PLAN §4 파괴 시험 1회 · 검토 1회 · 전체 회귀 마지막 1회 · KS-10 | DONE | §8-3 ~ §8-6 |
| 26 | PLAN 보정 3 배포 시각 · OCI 플래그 추가(사용자 작업) | 대기 | 배포 단계(§10) |
| 27 | PROGRAM_TRUTH 갱신(§4 :126 · :130 · 새 CLI · §7.1 · §9 · 부록 A) | DONE | 머리 · §2 그림 · §3 책임 표 · §4(runner · CLI · DB 경로) · §7.1(runtime DB · decision evidence DB) · §9 C 그림 · 흐름 · C-1 · C-2 · C-4 · 장중 급등락 · §10 · §11 · §12 · UNKNOWN · 부록 A · C(용어) — 운영 동작을 적은 줄은 '저장소 코드 · OCI 미배포 · 플래그 없으면 비활성' 표기(심볼 색인 줄은 `POC5-01B` 만) |

## 2. 변경된 파일 목록

| 파일 | 변경 | 줄(HEAD → 지금) |
|---|---|---|
| `app/three_push_runtime/ledger_store.py` | 신규 — 연결 · 권한 · DDL · STARTED · 종료 트랜잭션 · meta · 직전 평가 조회 · 대조 | 495 |
| `app/three_push_runtime/ledger_items.py` | 신규 — 보유 브리핑 · 장중 item · disposition · 전이 · exposure | 514 |
| `app/three_push_runtime/ledger_market.py` | 신규 — 시장 item · 태그(§4-2) | 176 |
| `app/three_push_runtime/ledger_context.py` | 신규 — 활성 판정 · 예정 시각 · 문맥 객체 · 경계 데코레이터 · 비밀값 검사 | 411 |
| `scripts/run_decision_ledger_reconcile.py` | 신규 — 읽기 전용 대조 CLI | 64 |
| `scripts/run_three_push_runtime_oci.py` | 수정 — import 1 · `@_ledger.boundary` · `begin` · `wrap_insert_status` · `finalize` · `attach_assembly` · `attach_send` · 머리 docstring '하지 않는 것: 신규 DB' 에 원장 단서 2줄(§4-10) | 517 → 529 |
| `app/market_briefing/evidence.py` | 수정 — `IndexCandidate.tickers` | 254 → 257 |
| `app/market_briefing/flow.py` | 수정 — `BriefingOutcome.outlook/index` | 465 → 469 |
| `app/runtime_evidence/holdings_selection.py` | 수정 — `select_holdings(observations=None)` | 373 → 401 |
| `app/runtime_evidence/holdings_selection_flow.py` | 수정 — `HoldingsSelectionOutcome.observations` | 460 → 465 |
| `app/runtime_evidence/holdings_risk.py` | 수정 — `select_risk_holdings(evaluated=None)` | 428 → 443 |
| `app/runtime_evidence/holdings_risk_flow.py` | 수정 — `HoldingsRiskOutcome.evaluated` · `RiskAssembly.intraday_eval`(격리 경로 None) | 538 → 548 |
| `app/runtime_evidence/sector_signal.py` | 수정 — `SectorOutcome.evaluated` · `quotes` + append 1개 | 595 → 611(NEAR) |
| `app/runtime_evidence/intraday_alert_flow.py` | 수정 — `IntradayAssembly.config_version_id` · `_load_active_sectors(meta=None)` · `build_sector_outcome(config_meta=None)` · `outcome.quotes` · `IntradayAssembly.surge_error`(급등 선정 예외 종류 · r1 정정) | 577 → 592 |
| `.env.example` | 수정 — `DECISION_LEDGER_ENABLED=` 키 이름과 주석 | 28 → 33 |
| `tests/conftest.py` | 수정 — autouse `_isolated_decision_ledger`(플래그 delenv · 원장 경로 · 캘린더 경로 tmp) | 591 → 611 |
| `tests/test_poc5_01b_ledger_store.py` | 신규 | 402 |
| `tests/test_poc5_01b_ledger_items.py` | 신규 | 738 |
| `tests/test_poc5_01b_ledger_runner.py` | 신규 | 604 |
| `tests/test_intraday_alert_integration.py` | 수정 — 대역 서명만(`meta=None`) | 481 → 483 |
| `tests/test_poc3_02d_ops03_consumer_isolation.py` | 수정 — 대역 서명만 | 730 → 732 |
| `tests/test_poc3_02d_ops03_intraday.py` | 수정 — 대역 서명만 | 491 → 495 |
| `docs/KILL_SWITCHES.md` | 수정 — KS-11 변경 근거 기록(2026-09-26 POC5-00) · 기록 위치에 STATE_LATEST §6 | 188 → 203 |
| `docs/PROGRAM_TRUTH.md` | 수정 — 01B 반영(§1 #27) · `POC5-01A` 배포 전 표현 3곳 정리(§4-8) | 947 → 969 |
| `docs/STATE_LATEST.md` | 수정 — 머리 최종 업데이트 · POC5 '다음' · PRIMARY 시작 조건 · §6 Next action 5번 주석 | 2805 → 2807 |
| `docs/backlog/BACKLOG.md` | 수정 — §11 PARAM JSON/DB 항목에 01B 처리 줄(§4-9) | 739 → 740 |
| `docs/ASSUMPTIONS.md` | 수정 — §3 A-7(Q-G) | 342 → 348 |
| `docs/MASTER_PLAN.md` | 수정 — canonical 순서 5번 주석 | 216 → 218 |
| `docs/ai_design/POC3/POC3-00_PC_JUDGMENT_UI_INTEGRATED_IMPLEMENTATION_MAP_V2.md` | 수정 — 80 · 111 · 112 · 127 · 128 · 210 · 290 행 '[2026-09-26 POC5-00 Q27]' 주석 | 372 → 372 |
| `docs/ai_design/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_DESIGN_V1.md` | 수정 — 설계자 새 판으로 교체(이전 판 = `a0a2c514`) · 끝에 PLAN 판정 원문 | 224 → 220 |
| `docs/ai_plan/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_PLAN_V1.md` | 신규 | 289 |
| `docs/ai_result/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_RESULT.md` | 신규(이 문서) | |


## 3. 신규 추가된 의존성

없음(원장 모듈은 표준 라이브러리 `sqlite3` · `subprocess` · `contextvars` 만 쓴다 · OCI 에 pydantic 없음 · POC5-01A §1-11).

## 4. 지시문 외 변경

1. **`signal_item.evaluable` 컬럼 추가**(PLAN §1-6 DDL 에 없음 · `INTEGER NOT NULL DEFAULT 1`).
   - 이유: 검토 결함 logic-1 · logic-2. 보유로 제외된 사업군(코드상 UNEVALUABLE) · 급등을 평가하지 못한 회차 · 자료없음 행을 직전 평가에서 빼야 PLAN §1-4 '평가 불가는 회복으로 세지 않는다' 와 설계서 §6 '비선정이면 event type · exposure 를 비운다' 가 성립한다.
   - `previous_item` 은 `evaluable=1 AND off_schedule=0 AND FINALIZED` 의 최근 1건만 읽는다. 처음 PLAN 의 'disposition 으로 건너뛰기' 는 이 컬럼으로 대신했다.
2. **시장 item · 태그를 `ledger_market.py` 로 분리**(PLAN §1-8 은 `ledger_items.py` 하나 · 예상 ~450). 분리하지 않으면 `ledger_items.py` 가 650 을 넘는다. 책임도 시장(관찰 · 태그)과 보유 · 장중(전이)으로 갈린다.
3. **대체 ETF 시세 운반 위치** — PLAN §2-1 은 'IntradayAssembly 의 대체 ETF 시세' 였다. 실제로는 `build_sector_outcome` 이 이미 병합한 시세 사전 참조를 `SectorOutcome.quotes` 에 싣는다(사업군 item 의 t0 는 그 결과 객체에서 읽는 것이 자연스럽다). 처음 구현(시세 사전을 한 번 더 읽음)은 기존 테스트의 대체 조회 횟수 단언에 걸려 이 방식으로 바꿨다.
4. **`build_sector_outcome(config_meta=None)` 선택 인자** — PLAN 은 `_load_active_sectors` 선택 인자만 적었다. 그 함수를 부르는 `build_sector_outcome` 이 값을 받아 넘겨야 해서 같은 모양의 선택 인자를 하나 더 뒀다(기본값이면 지금과 동일 · 2-튜플 반환 유지).
5. **기존 테스트 3파일 대역 서명** — `_load_active_sectors` 를 `meta=` 키워드로 부르게 되어, 그 함수를 `logger` 하나만 받는 대역으로 바꿔 끼우던 5곳(lambda 4 · 함수 1)이 TypeError 가 됐다. 대역 서명에 `meta=None` 만 더했다(단언 변경 0).
6. **`holdings_risk.select_risk_holdings` 의 `classify_day_drop` 호출 위치** — 관측에 state 를 담으려고 `if day_drop is None` 앞으로 당겼다(`day_drop` 이 None 이면 계산하지 않는 가드 포함 · 판정 · 반환 동일).
7. **conftest 가 원장 캘린더 경로(`ledger_context.CALENDAR_DIR`)도 tmp 로 돌린다** — PLAN §4 는 원장 경로 · 플래그만 적었다. `primary_start_date` · `after_kr_market_closure` 판정이 `state/market_meta` 를 읽으므로 라이브 경로를 열지 않게 했다.
8. **PROGRAM_TRUTH 의 `POC5-01A` 배포 전 표현 3곳 정리** — §4 runner 행 '(저장소 코드 · OCI 는 pull 뒤)' · C-1 근거 · 부록 A `_finish` '저장소 코드부터'. 01A 는 2026-10-04 OCI pull · 10-06 운영 확인으로 끝났는데 남아 있었다. 01B 가 같은 행을 고치면서 함께 배포 완료로 바꿨다.
9. **BACKLOG §11(PARAM JSON/DB 불일치) 처리 줄** — 이 항목의 재검토 트리거가 'POC5-01B 설계' 다. PLAN §2-4 문장대로 원장 `param_id` = 러너가 실제로 읽은 DB 활성 PARAM 임을 기록했다(새 결정 아님 · 남은 위험 그대로).
10. **러너 머리 docstring 2줄** — '이 스크립트가 하지 않는 것: 신규 DB' 가 01B 로 사실이 아니게 되어 '(단 POC5-01B 운영 원장 DB — DECISION_LEDGER_ENABLED=true ∧ send ∧ 운영 3종일 때만 쓴다 · 플래그는 OCI .env 에만 둔다)' 2줄을 더했다(로직 0 · 527 → 529).
11. **`IntradayAssembly.surge_error` 필드(검증자 r1 정정 · §6-0)** — PLAN §2-1 수집 자리 목록에 없던 결과 객체 필드 1개다. 보유 급등 선정 예외를 원장이 알 수 있게 한다(Q-B 와 같은 방식 · 기본값 None · record · diagnostics · JSONL · 본문 · 판정 불변 · `intraday_alert_flow.py` 589 → 592).

## 5. 알려진 한계 / 미완성

1. **예정 시각 판정(Q-A · 설계자 승인 한계)**: cron 이 1분 넘게 늦게 시작하면 `off_schedule=1` 로 잡혀 PRIMARY 통계에서 빠진다. 예정 시각 상수(시장 08:30 · 보유 `SLOT_TIME_LABEL` · 장중 7틱)는 cron 을 바꾸면 같이 고쳐야 한다. 평일 휴장일 실행은 `off_schedule=0` 이지만 `primary_start_date` 는 거래일에만 정한다.
2. **발송 전 동기 쓰기**: 활성이면 `begin()` 이 preflight · 시세 조회 · 발송보다 먼저 meta INSERT OR IGNORE 3번과 STARTED INSERT 1번을 한다.
   - 다른 연결이 원장 쓰기 잠금을 쥐고 있으면 발송이 늦어진다. 검토 재현(스크래치 DB): 잠금 없음 0.011초 · 2초 잠금 2.04초 · 7초 잠금 5.24초 뒤 원장 중단(PUSH 계속 · STARTED 0행).
   - 첫 활성 실행과 git 이 실패한 실행은 발송 전에 `git rev-parse`(timeout 5초)를 한 번 더 부른다.
   - 검토 반박 검증에서 결함 아님(결과 · 순서 · 본문 동일)으로 판정했다. 지금 원장을 쓰는 프로세스는 러너뿐이고 12:30 에만 두 실행이 겹친다.
3. **실제 전달 chunk 수는 모른다** — `telegram_send` 가 돌려주지 않는다(Q-E). `planned_chunk_count` 는 같은 본문의 계획 chunk 수다.
4. **기존 장중 관측 저장은 급등 선정 예외 회차를 회복으로 기록한다(원장과 다름 · 기존 동작)** — 원장은 r1 정정으로 그 회차의 '상태 없음' 행을 평가 불가로 둔다(§6-0). 그러나 기존 `sector_signal_state.mark_absent_entries` 는 급등 관측이 빈 회차에 보유 급등 entry 를 `SIGNAL_ABSENT`(회복)로 기록한다(관측에 없고 `unevaluable` 에도 없음 · `intraday_alert_flow.py` 의 `_unevaluable_tickers` 는 급등 예외를 넣지 않는다). PUSH 억제 동작을 바꾸는 일이라 01B 범위가 아니어서 고치지 않았다 — 다음 설계자 차례에 전달한다.
5. **대조 하한** — runtime 행은 `started_at ≥ first_active_at` 만 본다(PLAN §2-6). 첫 활성 때 두 실행이 동시에 시작해 늦게 시작한 쪽이 `first_active_at` 을 먼저 쓰면 먼저 시작한 실행이 `ledger_only` 로 보일 수 있다(동시 실행 = 12:30 뿐 · 검토 판정 도달 불가에 가까움).
6. **종료 트랜잭션 잠금 시간은 이력에 비례한다** — 직전 평가 조회가 subject 인덱스 + 정렬이다. 검토 실측(PC · 합성 이력): item 70,000(약 1년치) 88.0 ms · 350,000(약 5년치) 406.0 ms. busy timeout 5초보다 작다.
7. **시장 상위 2 밖 기초지수 그룹은 기록하지 않는다** — 코드가 보존하지 않는다(PLAN §1-3 · 설계서 §6 은 선택된 그룹만 요구).
8. **traceback frame 추가** — §6-1.
9. **`sector_signal.py` 611줄 NEAR** — PLAN 예상 598. 필드 2개와 append 튜플 1개를 black 이 여러 줄로 폈다(보정 5 · 기록 후 계속).
10. **발송 본문을 문맥에 싣는 시점** — `attach_send` 는 `telegram_send` 가 돌아온 뒤다. `telegram_send` 자체가 예외를 내면(지금 코드는 3-튜플을 돌려주고 예외를 내지 않는다) delivery 본문 · SHA 가 비고 run 은 failed 로 확정된다.
11. **PC · OCI 판별 없음** — 활성 조건은 플래그 ∧ send ∧ 운영 3종뿐이다(설계서 §3 · PLAN §1-2 · 기존 역할 표식 없음). PC 비활성은 PC `.env` 에 플래그가 없다는 설정에 기댄다(지금 PC `.env` 에 키 없음). PC `.env` 에 같은 줄이 들어가고 send 로 돌면 같은 경로의 PC AI 세션 DB 에 원장 4테이블이 생기고 폴더 · 파일 권한이 0700 · 0600 으로 바뀐다.
12. **잠재(지금 도달 불가) — 사업군 커버리지 임계가 50% 미만이면** provider 장애 회차에 사업군별 '상태 없음' 행이 평가 가능(`evaluable=1`)으로 남아 회복으로 세어질 수 있다(기존 상태 파일은 그 회차를 보존한다). 승인 PARAM 의 `sector_min_coverage_pct` 는 80(`generator.CONFIRMED_POLICY` 고정 · 개별 편집 화면 없음)이라 provider 장애는 늘 커버리지 미달과 함께 와 사업군 행이 생기지 않는다(옆칸 검토 재현).
13. **정책 행을 아예 못 읽은 회차(`intraday_config_unavailable`)는 사업군 구역 행을 남기지 않는다** — 정책 꺼짐과 같은 경로라 회복 오기록은 없지만, 원장에서 그 회차의 사업군 장애를 따로 찾을 수는 없다(실행 기록 diagnostics 에는 남는다 · 기록 완결성 · 이번 범위 밖).

## 6. 다음 검증자(Codex)에게 알릴 점

### 6-0. 검증자 r1 REJECTED(2026-10-07) 처리

| 지적 | 처리 |
|---|---|
| A-1 · A-3 급등 선정 예외 회차가 '급등 평가됨' 으로 기록돼, 전날 U5_7 → 예외 회차 → 같은 U5_7 이 `reentry_after_recovery / PRIMARY` 가 됨(PLAN §1-4 '평가 불가는 회복으로 세지 않는다' 위반) | ① 장중 조립이 급등 선정 예외를 격리할 때 `IntradayAssembly.surge_error` 에 예외 종류를 남긴다(결과 객체 필드 · record · diagnostics · JSONL 에는 넣지 않음 · 본문 · 판정 불변). ② `risk_items` 의 급등 평가 여부 = 정책 활성 ∧ `surge_error` 없음. ③ 급등을 평가하지 못한 회차(예외 · 정책 꺼짐 · 장중 조립 격리)의 '상태 없음' 행은 **직전 상태와 상관없이** 평가 불가(`evaluable=0`)로 저장한다 — 직전이 급락 계열이어도 그 회차에 급등이었는지 모르기 때문이다(전에는 직전이 급등 계열일 때만 막았다). 테스트: 검증자 재현 시나리오(전날 U5_7 → 예외 → U5_7 = `repeat_exposure / SECONDARY`) · 대조군(급등 평가 회차의 '상태 없음' 뒤 U5_7 = `reentry_after_recovery`) · 직전 급락 계열 · 실제 장중 흐름에서 `select_surge_holdings` 예외(끔 · 켬 기존 기록 같음 · 원장 '상태 없음' 행 평가 불가) |
| A-2 · A-3 traceback frame 을 1개로 축소 보고(실제 원장 비활성 insert_status 예외 2개) | ① 원장이 꺼져 있으면 `wrap_insert_status` 가 원래 함수를 그대로 돌려준다(감싸지 않음). 그래서 비활성 실행은 어느 예외든 경계 frame 1개다. 원장이 켜진 실행의 insert_status 예외만 2개(경계 + 감싸기)다. ② 이 수를 테스트로 고정했다(`test_traceback_frames_added_by_ledger` 4경우 — `ledger_context.py` frame 수). ③ 결과서 · PROGRAM_TRUTH · 모듈 docstring 의 '1개' 문구를 이 실측으로 바꿨다 |
| (개발자 자체 · r1 정정 뒤) 같은 종류의 다른 경로 전수 검토 — 2관점 · 읽기 전용 · 임시 DB 재현 | 장중(예외 격리 · 조기 return · sqlite 삼킴 · continue 분기 · 일일 상한)과 보유 브리핑(표 못 읽음 · 기준 종가 없음 · 시세 없음 · 축 없음 · 선정 중간 예외)에서 '평가 못 한 축이 평가된 비활성 행으로 남는' 결함은 더 없었다. 시장 쪽 2건을 고쳤다: ① 미국 입력 없음(SP500 `NONE`) · 기초지수 구역 장애 · 장중 사업군 구역 장애 행이 `data_unavailable` 인데 `evaluable=1` 이었다(전이에는 영향 없음 · 컬럼 정의와 모순) → `evaluable=0`. ② 직전 시장 run 의 미국 기준일을 모르면 `same_us_session` 을 `False` 로 단정했다 → 모름(`null`). 테스트 3곳 보강 |

1. **traceback frame 추가(설계서 §8 AC 1 '완전히 같다' 와의 차이)**: `@_ledger.boundary` 는 원장 활성 여부와 상관없이 `run()` 을 감싼다. 그래서 `run()` 밖으로 나가는 예외(조립 · mark_sent · insert_status 등)의 traceback 에 `ledger_context.py … in _wrapped` frame 이 더해진다 — 원장 비활성이면 경계 frame 1개 · 원장이 켜진 실행의 insert_status 예외만 2개(경계 + wrap_insert_status). 예외 종류 · 메시지 · `__context__` · exit code · DB · JSONL 은 같다. 파이썬에서 감싸는 함수 frame 을 traceback 에서 뺄 방법이 없어 그대로 둔다. cron 로그(stderr)의 traceback 텍스트가 이만큼 달라진다.
2. **독립 검토(2026-10-07 00:03 완료 · 읽기 전용 · 3관점: 동등성 · 안전 / item · 전이 정확성 / 저장소 · 견고성 · 테스트 품질)** — 지적 17건마다 반박 검증을 붙였다. 실제 12건 · 아님 5건.
   - 결함 5건(모두 코드 수정 + 테스트):
     - logic-1(high) 보유 제외 사업군 행에 전이가 붙어, 매도 뒤 첫 실림이 `repeat_exposure/SECONDARY` 가 됨 → `evaluable=0` · 전이 없음 · 직전 평가 제외.
     - logic-2 급등을 평가하지 못한 회차의 state None 이 회복으로 세어짐 → `surge_unknown`.
     - logic-4 사업군 `held` 가 신호 유무로 흔들림 → 보유 집합(`holding_rows`) 기준.
     - logic-5 조립 전에 끝난 시장 run 에 `input_delay=True` → 점검 결과가 있을 때만 판정 · item 이 있을 때만 태그.
     - logic-6 자료없음 행에 판정에서 버린 시세가 t0 로 저장 → cause=current_price · 장중 unavailable 은 t0 None.
   - 문서 1건: safety-2(boundary docstring 의 'traceback 그대로' 문구) → §6-1 처럼 고침.
   - 테스트 공백 6건(store-1 파일 0600 갈래 · store-2 트랜잭션 중간 실패 롤백 · store-3 -wal/-shm 단언이 연결을 닫은 뒤 검사 · store-4 `_git_head` 실패 → None · store-5 tags_json · cohort 단언 · store-9 대조 `mode=ro`) → 모두 테스트를 고치거나 더했다.
   - 아님 5건: safety-1(발송 전 동기 쓰기 지연 · §5-2 에 기록) · logic-3(아래 6-3) · store-6(대조 하한 · §5-5) · store-7(장기 잠금 시간 · §5-6) · store-8(KS-10 NEAR 기록 필요 · §5-9).
3. **보유 item 의 `t0_price` 와 `values.profit_loss_pct`** — 둘을 함께 보면 매입가를 근사로 되돌릴 수 있다(검토 재현: 61.23 대 실제 61.234). PLAN §1-3 이 item 에서 뺀 개인값(quantity · avg_buy_price · 투자금 · 평가금 · account_group · `privacy_detector.py:127` 대상)에는 `profit_loss_pct` 가 없다. 그래서 검토 반박 검증은 계약 위반이 아니라고 판정했고, 그대로 뒀다. 원장 파일은 0600 · OCI 로컬 사용자 한정이다. 사용자 확인 항목으로도 올린다(§7-2).
4. **수집 자리(Q-B)의 기본값 동등성** — 수집 인자 · 필드는 기본값이면 지금과 같다. 원장이 꺼져 있어도 flow 는 늘 수집 목록을 채운다(`build_holdings_selection` · `build_holdings_risk_alert` · `select_sector_signals` 가 목록을 넘김). 이 목록은 diagnostics · record · JSONL · 본문 · fingerprint 에 들어가지 않는다(AC 1 · 2 동등성 테스트 3 kind + 장중 사업군).
5. **`RiskAssembly.intraday_eval` 과 `intraday`** — `intraday` 는 본문 대체 회차만 채워지는 기존 필드(발송 진척 저장용)다. 원장은 일일 상한 · 신호 없음 회차를 포함한 같은 객체 참조 `intraday_eval` 을 읽는다. 장중 조립 예외 격리 경로는 둘 다 None 이다.
6. **같은 경로의 PC 파일** — PC 에는 같은 경로(`state/decision/decision_evidence.sqlite`)에 기존 AI Sessions DB(`app/decision_evidence_store.py` · 테이블 `ai_session_records` · 2026-08-12 생성)가 있다. POC5-00 Q5 · Q22(사용자 승인 2026-09-26)대로 OCI 는 새 파일, PC 는 기존 파일에 나중 단계(POC5-03)에서 테이블을 더한다. 원장 코드는 `decision_evidence_store` 를 import 하지 않고, PC 에서는 비활성이라 이 파일을 열지 않는다. 회귀 전후 이 파일 해시가 같다(§8-6).
7. **판정 경계에서 고른 것**
   - 사업군 `held` 행(보유 제외)의 disposition 은 `not_selected` 이고 계산된 state 는 값으로 남긴다(PLAN §1-3 표).
   - 장중 조립 예외 격리 회차는 보유 급락 item 만 만든다(PLAN §1-3).
   - 시장 `index_block` 은 구역 상태 1행이다. `no_candidate_normal` 은 not_selected, 그 밖 장애 상태는 data_unavailable 이다.
8. **문서 반영 범위에서 일부러 뺀 곳**
   - STATE_LATEST §6 의 '현재 상태 (2026-07-26)' 줄 끝 `next_step_gate = FIRST_REAL_DECISION_CYCLE_V1` 은 날짜가 박힌 당시 기록이라 주석을 달지 않았다(PLAN §3 '현재형 gate 문장에만'). 같은 절 canonical 순서 5번 주석이 3 → 5 를 덮는다.
   - PROGRAM_TRUTH 의 `oci_runtime_status_latest.json` 근거(§3 '실패 기록' 행 · §9 C 그림 · status 파일 성격)는 POC5-00 5-10 이 짚은 기존 낡은 표기라 고치지 않았다. 01B 대조 상대(`runtime_execution_status`)는 새 행 · §7.1 runtime DB 행에 따로 적었다.

## 7. 사용자 확인이 필요한 항목

1. **배포(보정 3)**: OPS-04 종료(2026-10-07 · 커밋 `f0eb6f06` · push) → 검증자 VERIFIED · 설계자 RESULT 판정 → 커밋 · push(승인) → OCI `git pull` → OCI `.env` 에 `DECISION_LEDGER_ENABLED=true` 한 줄 추가(pull · 플래그 모두 사용자 작업). 시각은 거래일 15:45 이후나 비거래일이다. 롤백은 그 한 줄을 지우면 즉시 비활성이다.
2. **원장에 남는 것**: 분할 전 본문 전문(POC5-00 Q9 확정 · 비밀값이 든 본문만 본문 보류 · SHA 유지)과 보유 item 의 현재가 · 매입대비 %(§6-3)가 OCI 로컬 파일(0600)에 남는다.
3. **문서 커밋 순서**: OPS-04 종료 커밋 `f0eb6f06`(2026-10-07 · push)을 먼저 했다. 그 뒤 01B 의 PROGRAM_TRUTH · STATE_LATEST 를 반영하고 01B 파일만 stage 했다(§9).
4. **사용자 소유 문서** `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` 는 손대지 않았고 stage 하지 않는다.

---

## 8. 검증 실측 (2026-10-07)

### 8-1. 테스트

- 원장 새 테스트: `tests/test_poc5_01b_ledger_store.py` 26 · `…_items.py` 20 · `…_runner.py` 25 = 71 passed(r1 정정 · 항목 +4 · 러너 +5).
- 러너 테스트는 기존 rig(보유 급락 러너 · 시장 흐름 통과 · 보유 정기 PUSH 계약 · 장중 흐름 통과)를 tmp 경로로 재사용한다. 장중 시나리오는 `assemble_intraday_alert` 에 tmp DB 를 `functools.partial` 로 넘긴다(라이브 DB 읽기 허용 목록 추가 0).
- Telegram 은 대역만 쓴다(실발송 0).

### 8-2. 수용 기준 대응

| AC | 테스트 |
|---|---|
| 1 · 2 | `test_ledger_on_off_keeps_body_record_history_db_state_and_order`(시장 · 보유 · 장중 급락): 본문 · record · JSONL · runtime DB 행 · 상태 파일 · 부수효과 호출 순서 · 발송 수 동일 · 끄면 원장 파일 0. `test_intraday_sectors_same_lookups_and_items_recorded`: 사업군 경로 시세 조회 수 동일 |
| 3 | `test_dry_run_pc_and_spike_write_nothing` · `test_is_active_requires_flag_send_and_operating_kind` |
| 4 | `test_send_failure_and_partial_are_finalized` · `test_skip_runs_are_finalized_with_items_and_skipped_delivery` |
| 5 | `test_assembly_exception_is_finalized_failed_and_reraised` · `test_mark_sent_exception_after_send_keeps_delivery_sent` · `test_insert_status_exception_is_ledger_only_failed` · `test_main_exit_code_same_with_ledger` |
| 6 | `test_ledger_write_failure_does_not_change_push[insert_started · finalize]` · `test_permission_failure_stops_ledger_but_not_push` · 저장소 롤백 2종 |
| 7 | 항목 테스트 16 · `test_select_holdings_observes_every_evaluated_ticker`(실제 함수) |
| 8 | `test_secret_in_body_withholds_body_but_keeps_sha` · 러너 동등성 테스트의 SHA 비교 |
| 9 | `test_reconcile_separates_ok_missing_gap_and_ledger_only` · `test_reconcile_cli_prints_counts_and_returns_zero` |
| 스냅샷 | `test_finalize_once_second_is_rejected_and_rows_unchanged` · `test_no_code_path_updates_item_or_delivery` · `test_meta_put_once_never_overwrites` |

### 8-3. 파괴 시험 (검토 1회 · 저장소 사본에서 · 저장소 파일 변경 0)

- 검토 때(2026-10-07 00:03 완료): 14종 중 13종 탐지. 놓친 것은 L13(`select_holdings` 가 비선정 종목 관측을 빠뜨림) 하나였다. 약한 L5(두 번째 종료 확정 가드 제거)는 가드가 아니라 PK 충돌 예외 종류 차이로만 잡혔다.
- 보강 뒤(2026-10-07 · 사본 · 변이마다 되돌린 뒤 저장소와 `filecmp` 일치 확인 · 끝에 `diff -rq` 차이 0):

| 변이 | 결과 | 잡은 테스트 |
|---|---|---|
| L13 비선정 관측 생략 | 탐지 | `test_select_holdings_observes_every_evaluated_ticker` |
| L5 run_state 확인 · UPDATE 조건 · rowcount 확인 모두 제거 | 탐지(`DID NOT RAISE`) | `test_finalize_once_second_is_rejected_and_rows_unchanged` |
| 종료 트랜잭션 ROLLBACK 생략 | 탐지 | 위 테스트 · `test_mid_transaction_failure_rolls_back_items_already_inserted` |
| git 실패를 `unknown` 으로 | 탐지 | `test_git_head_returns_none_outside_a_git_checkout` |
| 시장 태그 저장 생략 | 탐지 | `test_market_run_carries_tags_and_primary_cohort` |
| cohort 를 PRIMARY_LIVE 로 고정 | 탐지 | `test_off_schedule_first_run_is_legacy_and_sets_no_primary_start` |
| cohort 를 LEGACY_DIAGNOSTIC 로 고정 | 탐지 | `test_market_run_carries_tags_and_primary_cohort` |
| 대조를 쓰기 가능 연결로 | 탐지 | `test_reconcile_separates_ok_missing_gap_and_ledger_only` |
| DB 파일 0600 확인 생략 | 탐지 | `test_connect_secures_dir_and_file_and_creates_only_four_tables` · `test_db_file_permission_failure_stops_before_any_table` 외 1 |
| (r1) `risk_items` 가 `surge_error` 를 보지 않음 | 탐지 | `test_surge_selection_exception_run_is_unevaluable_not_recovery` 외 2 |
| (r1) 장중 조립이 `surge_error` 를 남기지 않음 | 탐지 | `test_surge_selection_exception_is_unevaluable_and_keeps_records` |
| (r1) 급등 미평가 '상태 없음' 행을 평가 가능으로 | 탐지 | `test_unevaluated_surge_run_is_not_recovery` 외 3 |
| (r1) 비활성에도 insert_status 를 감쌈 | 탐지 | `test_traceback_frames_added_by_ledger[False-insert_status_from_record-1]` |
| (옆칸) SP500 `NONE` 행을 평가 가능으로 | 탐지 | `test_market_items_outlook_candidates_and_index_states` |
| (옆칸) 기초지수 구역 장애 행을 평가 가능으로 | 탐지 | `test_market_items_outlook_candidates_and_index_states` |
| (옆칸) 사업군 구역 장애 행을 평가 가능으로 | 탐지 | `test_risk_isolated_intraday_records_only_held_drop_and_block_rows` |
| (옆칸) 직전 미국 기준일을 모를 때 `same_us_session=False` | 탐지 | `test_same_us_session_unknown_when_previous_asof_missing` |

### 8-4. 정적 검사

- `black --check` · `flake8` · `py_compile`: 변경 · 신규 Python 21파일 통과.

### 8-5. KS-10 (2026-10-07 `wc -l` 실측)

- 트리거 0(백엔드 650 이상 0 · 테스트 1,500 이상 0 · 프론트 900 이상 0).
- 근접: 백엔드 `api.py` 642 · `scripts/ops02c/reverse_verify_guards.py` 638 · `ml_score_validity_report.py` 626 · `holdings_market_evidence.py` 616 · **`runtime_evidence/sector_signal.py` 611(이번 단계 · 595 → 611)** · `draft.py` 602, 프론트 `JudgmentWorkbenchView.tsx` 855.
- 새 원장 모듈 최대 `ledger_items.py` 514 · 러너 529.

### 8-6. 백엔드 전체 회귀 · 라이브 보호

- r1 정정 + 옆칸 정정 최종 코드: `caffeinate -i .venv/bin/python -m pytest -q -p no:cacheprovider tests/` → `2904 passed, 1 warning in 377.35s (0:06:17)` · exit 0(2026-10-07 13:46 ~ 13:53). 첫 회귀(2894 · 00:12 ~ 00:19)보다 원장 테스트 10개(61 → 71)가 늘었다. 중간 회귀(r1 정정만 · 13:32 ~ 13:38)는 2903 passed 였다.
- 회귀 시작 뒤 바뀐 Python 파일 0(`find app scripts tests -newer <회귀 전 해시 파일>` 실측).
- PC `state/` · `logs/` 1,153파일 sha256 을 회귀 전후로 떠서 `diff` 차이 0. 같은 경로의 PC AI Sessions DB(§6-6)도 포함된다.
- 프론트 변경 0(프론트 검사 생략).

## 9. git 상태

2026-10-07 `git status --short --untracked-files=all` 실측(검증자 r3 판정 기준):

- staged 32 = 신규 `A` 10(원장 모듈 4 · 대조 CLI 1 · 테스트 3 · PLAN · 이 결과서) · 수정 `M` 22(수집 자리 운영 코드 8 · 러너 1 · `.env.example` 1 · 테스트 4 · 문서 8) — 모두 오른쪽 열 공백(staged = 작업 트리).
- 남은 것: `?? docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` 1건 — 사용자 소유라 stage 하지 않는다(§7-4).
- 기준 커밋: OPS-04 종료 커밋 `f0eb6f06`(2026-10-07 · push) 위에 쌓인 변경이다. 검증자 r3 VERIFIED 뒤 이 32개를 커밋 1개로 남기고 push 했다(사용자 승인 2026-10-07). VERIFIED 뒤 커밋 전에 바꾼 것은 상태 문구뿐이다(이 결과서 머리 · §9 · §10 · `docs/STATE_LATEST.md` · `docs/PROGRAM_TRUTH.md` 최종 반영 줄). 커밋 SHA 는 이 문서에 적지 않는다(자기참조 · `git log` 로 확인).

## 10. 배포 절차

1. OPS-04 첫 거래일(2026-10-07) 확인 · 종료 커밋 — 완료(`f0eb6f06` · push).
2. 01B PROGRAM_TRUTH · STATE_LATEST 반영 — 완료(2026-10-07) → 검증자 r3 VERIFIED(2026-10-07) → 설계자 RESULT 판정(대기).
3. 커밋 · push — 완료(사용자 승인 2026-10-07 · 검증자 VERIFIED 뒤 · 설계자 RESULT 판정 전 · OPS-04 와 같은 순서).
4. OCI `git pull` → `.env` 에 `DECISION_LEDGER_ENABLED=true`(사용자 · 거래일 15:45 이후나 비거래일).
5. 첫 거래일 확인(개발자 · OCI 읽기 전용): 원장 4테이블 행 수 · STARTED 잔류 0 · 대조 CLI(정상 = runtime send 행 수) · 폴더 0700 · 파일 0600 · 로그 원장 오류 0 · reflog pull 시각 인용.
