# POC5-01A — 세 PUSH 러너 기계 분리 PLAN V1 (확정 · 설계자 PASS 2026-10-03)

```text
STEP            = POC5-01A 세 PUSH 러너 기계 분리
DESIGN          = docs/ai_design/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_DESIGN_V1.md (설계자 정정 원문 2026-10-02 · PLAN 판정 원문 2026-10-03)
PREDECESSOR     = POC3-02D-OPS-03 (IMPLEMENTED_VERIFIED_DEPLOYED_OPERATION_CONFIRMED 2026-10-02)
SUCCESSOR       = POC3-02D-OPS-04 → POC5-01B 운영 원장 (설계자 정정 STEP 4)
PLAN_DECISION   = PASS (설계자 재판정 2026-10-03 · 1차 REVISE_AND_RESUBMIT 의 필수 보정 4건 모두 CLOSED · OPEN_BLOCKERS NONE) · Q1~Q6 (a) 확정 유지
IMPLEMENTATION  = 로컬 구현 승인 — §3-1 기준점 검사 4개 중 하나라도 실패하면 즉시 중단 · 범위 A · B · D · E 기계 분리뿐
COMMIT/PUSH/OCI = 별도 사용자 승인 유지(이 판정에 포함되지 않음)
이번 조사의 변경   = 코드 · 테스트 · DB · cron · OCI 변경 0 (문서만 · 테스트 읽기 실행 1회 · OCI 읽기 명령 1회)

판정 보정 4건 → 반영 위치:
  1 KS-10 전체 인벤토리     §1-13 — 추적 .py/.ts/.tsx 560개 실측 · TRIGGER 0 · NEAR 7
  2 변경 파일 목록          §2-4 — 코드 5개(신규 4 = 운영 모듈 3 + 검증 스크립트 1 · 수정 1 = 러너) · 테스트 0 · 문서 5
  3 동등성 기준점 고정       §1-0 · §3-1 — 기준 HEAD 7d507951 · 러너 blob f256677020232600627d207c54baf5081c70c6e2 · 비교 전 확인 4단계
  4 monkeypatch 경계 증거   §1-8 — 14개 이름 각각 처리(러너 잔류 / 호출 시 전달) · 원래 행 · 결합 시점 · 새 모듈 직접 import 0
                            (정정 2026-10-04 · 검증자 r1 A-2: 처음 13개 → `is_already_sent` 누락 · 전체 테스트 런타임 전수 기록으로 14개 확정)

사실조사 요약:
  러너         646줄 · run() 128~594행(467줄) · CLI 597~646행 · 종료 = return _finish( 27곳
  중단 조건     해당 0 (§5) — run() 소스를 읽는 테스트 1건이 spike 신선도 블록 위치를 고정 → 그 블록은 옮기지 않는다
  예외 층       러너가 잡는 예외는 PARAM 읽기 · 비밀값 2곳 · 나머지 미포착 예외는 run() 밖으로 빠진다 → 그대로(최외곽 확정 = POC5-01B · Q3)
  import       러너 import 시 app/scripts 모듈 67개 · 외부 패키지 0 · fastapi · pydantic · starlette 차단해도 정상(실측)
  분리안        새 운영 모듈 3개 — 실행 기록 · 사전 검사 · kind 조립/판정 · 러너 646 → 약 516줄(범위 510~525)
```

- **작성**: 개발자(VSCode Claude) · **독자**: 설계자 · **작성** 2026-10-02 · **재제출** 2026-10-03
- **기반 문서 확인**: `PROJECT_ORIGIN_INTENT` §4 · §10 · `KILL_SWITCHES` KS-10(백엔드 650 트리거 · 600 근접 · 트리거 5 '같은 대형 파일에 신규 책임' · Cleanup 시작 때 전 파일 실측 의무) · `ASSUMPTIONS` PC · OCI 역할 경계.
- **조사 방법**: 러너 전문 · 호출 모듈 읽기 · 테스트 전수 AST 스캔 · import 실측 · 러너 구동 테스트 16파일 기준선 실행 · 전 파일 줄 수 실측 · git blob 실측 · OCI 읽기 명령 1회. 모두 읽기 전용이다. 재현 명령은 부록 A.

---

## 1. 사실조사

### 1-0. 동등성 기준점 (판정 보정 3)

실측(2026-10-03):

| 항목 | 값 |
|---|---|
| PLAN 실측 HEAD | `7d507951abf8acea2a1218e2612be5d60bc448da` (2026-10-02 17:27 KST) |
| 러너 blob(`git rev-parse HEAD:scripts/run_three_push_runtime_oci.py`) | **`f256677020232600627d207c54baf5081c70c6e2`** |
| 러너 작업 트리 blob(`git hash-object`) | 같음(`f2566770…`) |
| 러너 마지막 변경 커밋 | `b79d14687fab54fc9a7f340e8c523655c47c2256` |
| 코드 작업 트리 변경(`git diff HEAD -- '*.py' '*.ts' '*.tsx'`) | 0줄 |
| OCI HEAD(읽기 전용 · `git log -1`) | `7d507951` · `.git/FETCH_HEAD` 2026-10-02 17:56 KST · OCI 러너 blob 도 `f2566770…` |

- 이 PLAN · 설계서 커밋으로 HEAD 는 움직이지만 러너 blob 은 그대로다. 그래서 기준은 **blob 으로 고정**하고, 구현 직전 HEAD 는 §3-1 절차로 결과서에 기록한다.
- 설계자가 '재확인 불가'로 둔 `7d507951` 의 OCI 반영은 **반영됨**이다(위 표). 01A pull 에 다른 운영 변경이 섞이지 않는다(Q6).
- **바뀌면 안 되는 기존 모듈 blob**(HEAD `7d507951` · `git ls-tree` 실측). 결과서에서 `git hash-object` 로 전부 같음을 보인다:

  | 파일 | blob |
  |---|---|
  | `app/three_push_runtime/__init__.py` | `88fd0193ff563d5d323085430c900e09859ea247` |
  | `app/three_push_runtime/market_data_batch.py` | `c576cf95a88d8133f84d16f578d986b16c733260` |
  | `app/three_push_runtime/non_trading_day.py` | `9ca6b7f3e778f1d9167c90e33ef34fc2d0340cc1` |
  | `app/three_push_runtime/price_refresh.py` | `dcf9123e09ead85549be1caa3e5bfe751431b786` |
  | `app/three_push_runtime/registry_key.py` | `eef5e515814b955d55a5beda45270203120bd756` |
  | `app/three_push_runtime/runner_diagnostics.py` | `1601e5611eff35b68dfc4b76a686510a29cc9c40` |
  | `app/three_push_runtime/runner_duplicate.py` | `5cbfa237dda9cbae0a1016def2074591a03907d8` |
  | `app/three_push_runtime/runner_evidence.py` | `3c6e30f764bc23a957729b8de41b5ca0be0716fe` |
  | `app/three_push_runtime/runner_market_briefing.py` | `865ac1bf25e073ac5c564dea7852e89b5c39f019` |
  | `app/three_push_runtime/runner_spike.py` | `4c35b08697a296ea3968801c8dd35da98a06c732` |
  | `app/three_push_runtime/spike_body.py` | `1b55c52a183a9b09e44cc99e14118f68cff7d766` |
  | `app/three_push_runtime/spike_freshness.py` | `581fbefa656014e01a9c48254f579fe08cab802c` |
  | `app/three_push_runtime/target_tickers.py` | `f20f371a04f030585a94e64e7578cb5575c639b0` |
  | `app/three_push_runner_common.py` | `305c39c4a52c36eb8c29dcf5a26607b56e482ba5` |
  | `app/three_push_runtime_message_builder.py` | `9443292e75587155f379e46bb603536e5911f78c` |
  | `app/runtime_evidence/holdings_risk_flow.py` | `4295f46e589884ee0dbbf39c74a12aec74bb60db` |
  | `app/runtime_evidence/holdings_selection_flow.py` | `e3e24881c0508c2451c1e7f6f6ff32c80f102650` |
  | `app/runtime_execution_status_store.py` | `09e815be0f7666dd25913d84e6baf6d8eee67dd0` |
  | `app/runtime_sent_registry_store.py` | `880c0ffd930db9c4268424cd57f80306b379ecf1` |
  | `tests/conftest.py` | `fc020a162598ba21078d2cd033cddafac40148e3` |

  `tests/` 전체는 `git diff <구현 기준 HEAD> -- tests/` 0줄로 보인다.

### 1-1. 러너 전체 call graph (항목 1)

`scripts/run_three_push_runtime_oci.py`(646줄) 구성:

| 행 | 내용 |
|---|---|
| 1~25 | docstring |
| 27~56 | sys.path · `three_push_runner_common` import · `load_dotenv_file()`(56 — 뒤 import 보다 먼저 `.env` 적재) |
| 58~103 · 118~125 | 모듈 import · 상태 경로 상수 `HOLDINGS_SELECTION_STATE_PATH`(90) · `HOLDINGS_RISK_STATE_PATH`(92) · `_HISTORY_PATH`(109) |
| 128~594 | `run(push_kind, mode, slot_id)` 467줄 |
| 600~646 | CLI `_parse_args` · `main`(종료 코드) |

`run()` 순서와 부르는 함수:

```text
140 setup_logging(f"three_push_runtime_runner.{push_kind}")      # logger 이름 = 운영 로그 경로
144 started_at(datetime.now) · 145 kst_now_iso() · 146 kst_today_date()
148 record dict 21키 초기화 (정정 2026-10-04: 처음 '23키' 는 오기 · 독립 검토 실측)
172 _finish closure (1-2)
201 §1  read_active_param_dict() → param_from_dict()             try/except Exception → param_load_error
213     assert_no_sensitive_keys(param)                           try/except RuntimeError → param_secret_exposed
222 §1-b slot_id 검사(holdings_briefing)
239 §2  param.is_push_kind_enabled
254 §3  price_refresh.refresh_runtime_quotes(push_kind, _collect_target_tickers) · evaluate_price_refresh   (지연 import)
283 §3-a2 spike 신선도: draft_three_push._load_universe_artifact_for_spike · spike_freshness.check_spike_freshness
299 §3-b spike 재평가 함수 준비(universe_reevaluator · 지연 import)
324 §3-c 보유 브리핑 조립 holdings_selection_flow.assemble_holdings_push(holdings.load · market_data_store.fetch_price_history 지연 import)
349 §3-d 장중 조립 holdings_risk_flow.assemble_holdings_risk_push · record[PENDING_KEY]
371 §3-e 시장 브리핑 조립 runner_market_briefing.assemble
380 §4  runner_evidence.assemble_legacy_evidence(build_runtime_message=…) · runner_diagnostics.forward_diagnostics
401     runner_spike.apply_spike_reevaluation
407 §4-c check_forbidden_wording · §4-b check_raw_identifiers
422 §5  dry-run 종료
435 §6  env_bool(PUSH_AUTOSEND_ENABLED) · env_bool(PUSH_KIND_FLAG_ENVS[kind])
450 §6-b spike no-signal
476 §6-c 판정: 보유 조립 실패 → 비거래일 → runner_market_briefing.decide → 장중 skip → 보유 skip(빈 선정 상태 저장 503)
521 §7  중복: spike = runner_spike.resolve_spike_duplicates / 그 밖 = runner_duplicate.check_plain_duplicate
557 §8  telegram_send → record_send_success → runner_market_briefing.save_state_after_send → _finish
```

### 1-2. `run()` 부터 `_finish` 까지 모든 종료 경로 (항목 2)

`_finish`(172~192)는 closure 다. 순서: `holdings_risk_flow.apply_intraday_records`(예외 삼킴) → status · reason · error · finished_at(179 `datetime.now`) → `insert_status_from_record`(181 · DB · fail-closed) → JSONL 1줄 append(182~184) → 로그 → record 반환.

`return _finish(` 는 27곳이다(AST 실측):

| 단계 | 행 · status/reason |
|---|---|
| §1 · §1-b · §2 | 207 failed/param_load_error · 217 failed/param_secret_exposed · 225 failed/slot_id_required · 228 failed/slot_id_invalid · 245 skipped/push_kind_not_in_param |
| §3 | 265 failed/runtime_price_refresh_error · 274 `*refresh_fail`(runtime_price_all_failed · runtime_price_partial_failed) · 295 failed/freshness_stale(spike) |
| §4 | 393 `*ev_fail`(runtime_evidence_error · runtime_message_build_error) · 404 `*spike_fail` · 410 failed/forbidden_wording · 419 failed/raw_identifier_exposed |
| §5 dry-run | 425 `*holdings_fail` · 432 dry_run_success |
| §6 · §6-b | 437 skipped/autosend_disabled · 442 skipped/push_kind_disabled · 456 · 465 skipped/no_signal(spike) |
| §6-c | 477 `*holdings_fail` · 481 skipped/non_trading_day · 485 `*mb_fail` · 495 skipped/장중 skip_reason · 509 skipped/보유 skip_reason |
| §7 | 538 `*spike_fail` · 554 `*dup_fail`(registry_corrupted · duplicate_runtime) |
| §8 | 591 sent · 594 failed/telegram_send_error |

**`_finish` 를 거치지 않는 종료**(미포착 예외 · DB · JSONL 행 없음 · `main()` 은 traceback 과 exit 1):
- 발송 전: 조립 함수 · `assemble_holdings_push`(try 0 · `holdings_selection_flow.py:393-459`) · `runner_market_briefing.assemble`(try 0 · `:136-181`) · `flow.assemble_market_briefing`(try 1 · `OSError/UnicodeDecodeError` 한 곳 · `flow.py:350-354`) 등에서 잡히지 않은 예외.
- 발송 뒤: `record_send_success` 의 `mark_sent` · `save_risk_state` · `save_state`(`runner_evidence.py:222-275` · try 없음) — Telegram 은 이미 나갔다.
- `_finish` 안: `insert_status_from_record` 예외(fail-closed · `runtime_execution_status_store.py:81-115`)면 JSONL 줄이 쓰이지 않는다.

`main()`(634~642): status 가 sent · dry_run_success · skipped 면 exit 0, 그 밖은 exit 1.

### 1-3. DB · JSONL · state 파일 쓰기 지점 (항목 3)

| 시점 | 쓰기 | 위치 |
|---|---|---|
| 모든 `_finish` | 장중 관측 `sector_signal_state_latest.json`(save_observation) · 회차 집계 `intraday_checkup_tally_latest.json`(record_tick) — pending 이 있는 send 회차만 | `holdings_risk_flow.py:479-537` |
| 모든 `_finish` | `runtime_state.sqlite` `runtime_execution_status` INSERT | `runtime_execution_status_store.py:81` |
| 모든 `_finish` | `state/three_push/oci_runtime_history.jsonl` append | 러너 182~184 |
| §6-c 보유 skip | `holdings_selection_state_latest.json` 빈 선정 상태(`save_empty_state` 일 때) | 러너 503 |
| §8 발송 성공 | `runtime_sent_registry` INSERT(mark_sent) | `runner_evidence.py:222-239` |
| §8 전체 성공 · 장중 | `holdings_risk_state_latest.json` · `sector_signal_state_latest.json`(전달 상태) | `runner_evidence.py:246-268` |
| §8 전체 성공 · 보유 | `holdings_selection_state_latest.json` | `runner_evidence.py:270-275` |
| §8 전체 성공 · 시장 | `market_briefing_state_latest.json`(예외 삼킴) | `runner_market_briefing.py:204-236` |
| 로그 | `logs/three_push_runtime_cron.log`(setup_logging) | 러너 140 |

조립 단계(§3-c · §3-d · §3-e)는 쓰지 않는다 — 장중 관측 · 집계는 pending 으로 들고 있다가 `_finish` 에서 쓴다(조립 모듈의 `save_*` · `record_tick` 호출은 `holdings_risk_flow.py:502 · 529` 두 곳뿐이고 둘 다 `apply_intraday_records` 안).

### 1-4. push kind 별 분기와 공통 분기 (항목 4)

| 분기 | 대상 | 행 |
|---|---|---|
| 공통 | PARAM · 비밀값 · kind 활성 · 가격 조회 · §4 · 금지 문구 · raw 식별자 · dry-run · 전역/kind flag · 중복 · 발송 · `_finish` | |
| `holdings_briefing` | slot 검사 · §3-c 조립 · §6-c 비거래일 · 보유 skip/ctx · 중복 슬롯 | 222 · 324 · 476~513 |
| `holdings_risk_alert` | §3-d 조립 · pending · §6-c 장중 skip/ctx | 349 · 487~498 |
| `market_briefing` | §3-e 조립 · §6-c decide · §8 시장 상태 저장 | 371 · 483 · 584 |
| `spike_or_falling_alert`(폐지 · cron 0 · PARAM 에는 남음) | §3-a2 신선도 · §3-b 재평가 · §4 재평가 · §6-b no-signal · §7 fingerprint 중복 | 283 · 299 · 401 · 450 · 522 |

§4 `assemble_legacy_evidence` 는 보유 · 장중 · 시장을 그대로 통과시킨다(`SKIP_EVIDENCE_KINDS` · `runner_evidence.py:15-20`).

### 1-5. 전송 성공 · 실패 · 부분 전송 순서 (항목 5)

```text
557 record.telegram_attempted = True
558 sent, err, partial = telegram_send(message_text)
      분할 전송(4,000자) · 실패 chunk 에서 즉시 중단 · 첫 chunk 뒤 실패면 partial=True · 예외를 올리지 않음
      (three_push_runner_common.py:252-304 · message_id 는 버린다 :321-327)
559 record.telegram_sent · telegram_partial_delivery · partial_delivery
566 sent → record_send_success: mark_sent → (ctx 있고 partial 아님) 장중: save_risk_state → 전달 상태 저장 / 보유: save_state
584       → partial 아님: 시장 상태 저장(예외 삼킴) → 591 _finish("sent")
592 else → 594 _finish("failed", "telegram_send_error", err[:400])   # 부분 전송도 여기(partial_delivery=True 기록)
_finish → apply_intraday_records: failed → 집계 send_failed · sent(부분 아님) → sent
```

실제 `telegram_send` 는 전부 성공일 때만 `sent=True` 다(부분 전송은 `sent=False, partial=True`).

### 1-6. 예외가 잡히는 층과 빠지는 층 (항목 6)

| 층 | 잡는 곳 | 결과 |
|---|---|---|
| 러너 | 201~207(Exception) · 213~217(RuntimeError) | `_finish(failed, …)` |
| 하위 helper(실패 튜플로 반환) | 가격 조회(`price_refresh.py:50-62`) · evidence/본문(`runner_evidence.py:90-110`) · 중복 조회(`runner_duplicate.py:60-64`) · spike 중복(`runner_spike.py:90-140`) · S&P500 · 배치 상태 읽기(`runner_market_briefing.py:77-87 · 127-132`) · 보유 선정(`holdings_selection_flow.py` build 안 3곳) · 장중 조립(`holdings_risk_flow.py:322-451`) | 러너가 `_finish(*fail)` |
| 하위 helper(삼키고 기록만) | `apply_intraday_records` · 시장 상태 저장 · 전달 상태 저장 | record 진단 키 |
| 잡지 않음 | 1-2 '거치지 않는 종료' | run() 밖으로 · DB · JSONL 없음 |

**이번 분리는 이 표를 바꾸지 않는다** — 새 try/except 를 넣지 않는다(설계 STEP 8 '예외 전파 · 격리 범위'). 미포착 예외의 종료 기록은 POC5-01B 가 맡는다(Q3 확정).

### 1-7. import 의존 방향과 순환 위험 (항목 7)

- 러너 → `app.*` 단방향. `app/three_push_runtime/__init__.py` 는 docstring 뿐(5줄)이라 하위 모듈을 끌어오지 않는다.
- `app` → `app.three_push_runtime` 역방향은 1곳: `holdings_selection_flow.py:80` 이 `three_push_runtime.non_trading_day` 를 **함수 안에서** import. 새 모듈은 `non_trading_day` 를 import 하지 않으므로 순환이 없다.
- `app.three_push_runtime.*` 는 `scripts.*` 를 import 하지 않는다(grep 0). 새 운영 모듈도 러너(`scripts`)를 import 하지 않는다 → 순환 0. 검증 스크립트(§2-4)는 러너를 import 하지만 운영 모듈은 검증 스크립트를 import 하지 않는다.
- 러너는 지연 import 를 쓴다(가격 조회 254 · spike 284 · 300 · 보유 325 · 350). 테스트가 원본 모듈 속성을 바꿔 끼우는 경로(`app.holdings.load` · `market_data_store.fetch_price_history` · `draft_three_push._load_universe_artifact_for_spike`)가 이 '호출 때 import' 에 기대므로, 옮길 때도 **같은 자리에서 지연 import** 로 둔다.

### 1-8. 기존 테스트가 쓰는 러너 이름 · 바꿔 끼우기 경계 (항목 8 · 판정 보정 4)

> **정정(2026-10-04 · 검증자 r1 A-2 · A-3)**: 처음 AST 스캔(2026-10-02)은 `runner` 같은 이름 변수만 봤다. 그래서 두 곳을 놓쳤다 —
> `tests/test_poc3_02d_ops01_holdings_risk_flow.py:590` 의 `monkeypatch.setattr(rig["runner"], "is_already_sent", …)`(딕셔너리 원소 형태)와
> `tests/test_poc4_02b_runner_guards.py:76 · 159`(poc4 파일 제외). 다시 셀 때는 전체 테스트(2709 passed · 2026-10-04 12:09 ~ 12:15)를 돌리면서
> 러너 모듈의 모든 속성 쓰기를 런타임에 기록했다(import 순간 모듈 클래스를 기록용으로 바꾸는 관찰 플러그인 · 동작 변경 없음).
> 결과는 **정확히 14개**다. 아래 표의 건수 · 파일은 그 기록의 '고유 호출 위치 수 · 파일 수'다(conftest 포함).

AST 전수 스캔(`tests/` · poc4 러너 제외 · fixture 로 받은 `runner` 변수 포함 · 2026-10-02 — 위 정정 참조):

- **호출 · 읽기**: `run`(13파일) · `HOLDINGS_SELECTION_STATE_PATH` 읽기(1) · `telegram_send` 읽기(1 · 원복용). `_finish` · `main` · `_parse_args` 를 직접 부르는 테스트는 없다.
- `tests/conftest.py:195-253` autouse fixture 가 러너가 import 돼 있으면 두 상태 경로 상수를 `tmp_path` 로 바꾼다.
- **함수 위치 고정 1건**: `tests/test_oci_market_data_refresh.py:316-327` 이 `inspect.getsource(runner.run)` 안에 `freshness_stale` 이 있고 그 앞에 `spike_or_falling_alert` 가 있는지 본다 → §3-a2 spike 신선도 블록(280~295)은 **run() 안에 그대로 둔다**.
- 줄 수(646 · 648 · 650)를 단언하는 테스트는 없다(grep 0).
- **기준선**(2026-10-02 · 분리 전): 러너 구동 테스트 16파일 `305 passed, 1 warning in 11.09s`(warning = fastapi testclient 제3자). 실행 뒤 `git status` 에 새 파일 · 변경 없음.

**바꿔 끼우는 이름 14개 — 처리 · 결합 시점**

공통 규칙: **14개 이름의 전역 바인딩(정의 · import)은 모두 러너에서 이동하지 않는다.** 새 운영 모듈이 이 14개 중 하나라도 스스로 import 하거나 모듈 상수로 들고 있는 경우는 0 이다 — 구현 뒤 동등성 스크립트의 AST 검사로 보인다(§3-1 ⑤).

- 처리 (가) **러너 잔류** — 쓰는 코드가 러너에 그대로 남는다(줄 변경 없음).
- 처리 (나) **호출 시 전달** — 쓰는 코드는 새 모듈로 옮기고, 러너가 그 함수를 부르는 순간 자기 전역에서 꺼내 인자로 넘긴다.

| # | 이름 · 바꿔 끼우는 테스트(건수 · 파일) | 원래 쓰는 행 | 처리 | 결합 시점(원래 → 분리 뒤) |
|---|---|---|---|---|
| 1 | `telegram_send` (30 · 12) | 558 §8 | (가) | 558 실행 때 → 같음 |
| 2 | `_collect_target_tickers` (17 · 8) | 260 §3 | (가) — 가격 조회 블록은 옮기지 않음(Q1 a) | 260 → 같음 |
| 3 | `kst_now_iso` (4 · 3) — 시간 | 145 | (가) | run 입구 1회 → 같음 |
| 4 | `kst_today_date` (7 · 3) — 시간 | 146 | (가) | run 입구 1회 → 같음 |
| 5 | `build_runtime_message` (2 · 2) | 390 §4 · 531 §7 | (가) — 기존 helper 에 인자로 넘기는 두 줄 그대로 | 390 · 531 → 같음 |
| 6 | `mark_sent` (1 · 1 · `raising=False`) | 578 §8 | (가) — `record_send_success(mark_sent=…)` 줄 그대로 | 578 → 같음 |
| 7 | `_HISTORY_PATH` (12 · 9) — 상태 경로 | 182~183 `_finish` | (나) `runner_record.finish_run(history_path=…)` · 러너 `_finish` closure 가 **매 호출마다** 전달 | 원래: `_finish` 실행 중 182행(apply_intraday_records · insert_status 뒤) → 분리 뒤: 같은 `_finish` 호출의 입구 |
| 8 | `insert_status_from_record` (2 · 2) | 181 `_finish` | (나) `finish_run(insert_status=…)` · closure 가 매 호출마다 전달 · 부르는 자리는 원래처럼 finished_at 뒤 · JSONL 앞 | 원래 181(apply 뒤) → 같은 `_finish` 호출의 입구 |
| 9 | `read_active_param_dict` (2 · 2) | 203 §1 | (나) `runner_preflight.load_param_and_check_slot(read_active_param_dict=…)` · 같은 try 안에서 부름 | 203 → 그 호출의 입구(호출 직후 try 첫 줄에서 실행) |
| 10 | `param_from_dict` (2 · 2) | 204 §1 | (나) 같은 함수 인자 · 같은 try 안 둘째 줄 | 204(read_active 실행 뒤) → 호출 입구(read_active 실행 전) |
| 11 | `kst_today` (1 · 1 · `raising=False`) — 시간 | 331 §3-c · 356 §3-d | (나) `runner_dispatch.assemble_push_kind(kst_today=…)` · **함수 객체**로 넘기고 원래 가지 안 같은 자리에서 부름 | 함수 객체 조회: 호출 입구 · 날짜 계산: 원래와 같은 자리 |
| 12 | `HOLDINGS_SELECTION_STATE_PATH` (12 · 6 · conftest 포함) — 상태 경로 | 332 §3-c · 503 §6-c · 581 §8 | 332 → (나) `assemble_push_kind(holdings_state_path=…)` · 503 → (나) `decide_after_flag_guard(holdings_state_path=…)` · 581 → (가) | 각 호출 입구(원래 블록 시작 지점) · 581 같음 |
| 13 | `HOLDINGS_RISK_STATE_PATH` (4 · 3 · conftest 포함) — 상태 경로 | 357 §3-d · 582 §8 | 357 → (나) `assemble_push_kind(risk_state_path=…)` · 582 → (가) | 호출 입구 · 582 같음 |
| 14 | `is_already_sent` (1 · 1) — 정정 2026-10-04 추가 | 534 §7 spike · 550 §7 그 밖 | (가) — 기존 helper(`resolve_spike_duplicates` · `check_plain_duplicate`)에 인자로 넘기는 두 줄 그대로 | 534 · 550 → 같음 |

- **앞당겨지는 조회(7 · 8 · 10 · 11 · 12 · 13)**: 같은 호출 안에서 이름을 읽는 순간만 블록 입구로 당겨진다. 그 사이 실행되는 코드(`apply_intraday_records` · 상태 필드 기록 · `read_active_param_dict`)는 러너 전역을 다시 묶지 않는다. 테스트 대역도 그렇다(예: `insert_status_from_record` 대역은 `lambda r: None` · `test_runtime_runner_forwarding.py:86` · `test_runtime_universe.py:319`). 테스트는 모두 `run()` 을 부르기 **전에** 바꿔 끼운다. 그래서 읽히는 값이 같다. 동등성 비교 ④가 이것을 실행으로 보인다(§3-1).
- **바꿔 끼우지 않는 다른 시간 · 모듈 참조**: `datetime.now` 144(started_at · 러너 잔류) · 179(finished_at → `finish_run` 안 원래 순서) · 576(sent_at · 러너 잔류)은 테스트가 바꾸지 않는다(스캔 0). 모듈 속성 참조(`_hrf.apply_intraday_records` · `_hrf.assemble_holdings_risk_push` · `_hrf.PENDING_KEY` · `_mb.assemble` · `_mb.decide`)는 새 모듈에서도 **모듈 속성으로 호출 때 조회**한다(`tests/_helpers.py:283` 이 `_mb.assemble` 을 바꿔 끼운다). `assemble_holdings_push`(이름 import) · `save_state` 는 테스트가 러너에서 바꾸지 않는다(스캔 0). `save_state` 는 기존 `record_send_success` 처럼 러너가 넘긴다.

### 1-9. 분리 후보별 줄 수 (항목 9)

원래 블록 줄 수(빈 줄 · 주석 포함) 대 호출 자리 줄 수(호출 모양을 scratchpad 에 적어 black 으로 정렬한 뒤 센 값):

| 후보 | 원래 행 | 원래 | 호출 자리 | 줄어듦 | 채택(Q1 a) |
|---|---|---|---|---|---|
| A 실행 기록 시작 · 종료(record 초기화 + `_finish` 본문) | 148~192 | 45 | 23 | 22 | 예 |
| B 사전 검사(PARAM · 비밀값 · slot · kind 활성) | 201~245 | 45 | 11 | 34 | 예 |
| C 가격 조회 · 판정 | 247~274 | 28 | 8 | 20 | 아니오 |
| D kind 조립(§3-c · §3-d · §3-e + 276행 ctx 초기화) | 315~375 · 276 | 62 | 15 | 47 | 예 |
| E flag 뒤 kind 판정(§6-c) | 467~513 | 47 | 12 | 35 | 예 |
| F spike 전용 2블록(§3-b · §6-b) | 297~313 · 444~465 | 39 | 9 | 30 | 아니오 |
| (고정) §3-a2 spike 신선도 | 280~295 | 16 | — | 옮기지 않음 | — |

### 1-10. 분리 후 예상 러너 줄 수 (항목 10)

- 확정안(A · B · D · E): 646 − (22 + 34 + 47 + 35) + import 증감 약 +8 = **약 516줄**(범위 510~525 · 구현 뒤 실측으로 보고). KS-10 근접(600) 밖으로 나간다.
- import 증감: 새 모듈 3개 import +11 · 쓰지 않게 되는 `holdings_risk_flow as _hrf`(78) · `assemble_holdings_push`(82~84) · `assert_no_sensitive_keys`(47) 제거 −5. 1-8 의 14개 이름과 `save_state` · `save_risk_state` 는 러너에 남는다.

### 1-11. OCI 전용 모듈 import 제약 (항목 11)

- OCI 는 API 서버를 돌리지 않아 `pydantic` 이 없다(`docs/handoff/POC3-02D-OPS-02_RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS_HANDOFF_2026-09-29.md:47`). OPS-03 배포 read-back 도 fastapi · pydantic · starlette 를 막고 새 모듈 import 를 확인했다(OPS-03 결과서 :399).
- PC 실측(2026-10-02 · `.venv` Python 3.12.13 · 세 패키지를 meta_path 로 차단): 러너 import 정상 · 새로 올라온 `app`/`scripts` 모듈 67개 · 외부 패키지 0개 · `three_push_runtime` 은 7개(registry_key · runner_diagnostics · runner_duplicate · runner_evidence · runner_market_briefing · runner_spike · target_tickers)이고 5개(price_refresh · spike_freshness · spike_body · non_trading_day · market_data_batch)는 지연 import.
- **제약**: 새 운영 모듈은 이 67개 안의 모듈만 모듈 머리에서 import 한다. 지연 import 는 지연 그대로 옮긴다. 구현 뒤 같은 차단 실측으로 '67 + 새 3 = 70' 과 외부 패키지 0 을 보고한다. 검증 스크립트는 운영 경로에서 import 되지 않는다.
- 새 운영 모듈은 `.env` 를 읽지 않는다 — 러너 56행 `load_dotenv_file()` 뒤에 import 되므로 환경변수 적재 순서도 그대로다.

### 1-12. POC5-01B 가 쓸 수 있는 안전한 주입 지점 (항목 12 · Q4 확정 = 식별까지만)

| 지점 | 무엇을 붙일 수 있나 | 주의 |
|---|---|---|
| `runner_record.new_run_record` 직후(러너 148 자리) | 실행 진입 `event_id` · STARTED 행 | 진입 전체가 모집단(POC5-00 핵심 확정 7) |
| `runner_record.finish_run` | 정상 종료 27곳 모두의 종료 상태 · 전달 결과(record 의 `telegram_sent` · `partial_delivery` · `error`) | DB · JSONL 쓰기와 같은 함수 — 순서 · 예외 격리는 01B 설계 |
| `runner_dispatch.KindAssembly` | kind 별 조립 결과(보유 · 장중 · 시장 outcome)를 additive 필드로 운반 | 본문 byte 불변(POC5-00 Q7) |
| (경계 밖) 미포착 예외 | 1-2 '거치지 않는 종료' | `run()` 소스가 테스트에 고정돼(1-8) 본문을 다른 함수로 옮기는 감싸기는 어렵다 → 01B PLAN 에서 `main()` 경계 또는 run() 안 짧은 감싸기를 비교한다(Q3) |

01A 에서는 빈 매개변수 · hook 을 만들지 않는다(Q4 확정).

### 1-13. KS-10 전체 저장소 인벤토리 — Cleanup 시작 시점 (판정 보정 1)

실측 2026-10-03 · HEAD `7d507951` · 코드 작업 트리 변경 0 · 대상 `git ls-files '*.py' '*.ts' '*.tsx'` **560개 · 158,233줄**(`wc -l`). 측정 결과 파일(경로 · 줄 수 560행)의 sha256 = `811eb85e99c0a0ccb97a200de9eb0be0c50b94166201266ffdd924d4d3d57f1e`(재현 = 부록 A).

분류 규칙(KS-10): `tests/` · `*.test.ts(x)` = 테스트(근접 1,450 · 트리거 1,500 혼재 / 2,500) · `.tsx` = 프론트 컴포넌트(근접 850 · 트리거 900) · 그 밖 `.py`(app · scripts · legacy) = 백엔드(근접 600 · 트리거 650). 프론트 `.ts`(lib · helper)는 KS-10 에 별도 문턱이 없어 컴포넌트 문턱을 보수적으로 적용했다.

| 분류 | 파일 | 줄 합계 | 최대 |
|---|---|---|---|
| 백엔드 `.py` | 265 | 71,413 | 646 |
| 프론트 `.tsx` | 68 | 16,125 | 855 |
| 프론트 `.ts` | 38 | 4,334 | 396 |
| 테스트(백엔드 165 · 프론트 24) | 189 | 66,361 | 1,427 |

**TRIGGER 0건.**

**NEAR 7건**(POC5-00 2026-09-26 인벤토리와 같은 7개 · 줄 수도 같음):

| 분류 | 줄 | 파일 | 이번 단계 |
|---|---|---|---|
| 프론트 | 855 | `frontend/app/components/JudgmentWorkbenchView.tsx` | 손대지 않음 |
| 백엔드 | **646** | `scripts/run_three_push_runtime_oci.py` | **이번 분리 대상 → 약 516(근접 해소)** |
| 백엔드 | 641 | `app/api.py` | 손대지 않음 |
| 백엔드 | 638 | `scripts/ops02c/reverse_verify_guards.py` | 손대지 않음 |
| 백엔드 | 626 | `app/ml_score_validity_report.py` | 손대지 않음 |
| 백엔드 | 616 | `app/holdings_market_evidence.py` | 손대지 않음 |
| 백엔드 | 602 | `app/draft.py` | 손대지 않음 |

**근접 문턱 바로 밖**(기록만): 테스트 `tests/test_market_briefing_contracts.py` 1,427 · `tests/test_intraday_config_integration.py` 1,423(근접 1,450 까지 23 · 27줄) · 프론트 `MarketDiscoveryView.tsx` 825. 이번 단계는 테스트 · 프론트를 고치지 않으므로 바뀌지 않는다.

**분리 뒤 기대**: 러너 약 516 · 새 운영 모듈 3개 각 200줄 미만 · 검증 스크립트 600줄 미만(백엔드 문턱) · 그 밖 파일 줄 수 불변. 결과서에서 같은 명령으로 다시 잰다.

---

## 2. 분리안 (Q1 a 확정 = A · B · D · E)

### 2-1. 파일별 이동표

| 새/기존 모듈 | 이동 전(러너) | 이동 후 함수 | 대략 줄 수 |
|---|---|---|---|
| **신규** `app/three_push_runtime/runner_record.py` | 148~170 record 21키 dict | `new_run_record(push_kind, mode, *, started_at, runtime_kst, runtime_date_kst) -> dict` | 약 75 |
| 〃 | 172~192 `_finish` 본문 | `finish_run(record, status, reason, error, *, push_kind, mode, logger, history_path, insert_status) -> dict` | |
| **신규** `app/three_push_runtime/runner_preflight.py` | 201~245 §1 · §1-b · §2 | `load_param_and_check_slot(record, *, push_kind, slot_id, logger, read_active_param_dict, param_from_dict) -> (param \| None, fail \| None)` | 약 80 |
| **신규** `app/three_push_runtime/runner_dispatch.py` | 315~375 §3-c · §3-d · §3-e | `KindAssembly`(dataclass: holdings_outcome · risk_outcome · market_outcome · intraday · fail · skip_non_trading_day · message_text) · `assemble_push_kind(record, *, push_kind, market_quotes, price_refresh_diag, slot_id, runtime_kst, runtime_date_kst, kst_today, holdings_state_path, risk_state_path, logger) -> KindAssembly` | 약 170 |
| 〃 | 467~513 §6-c | `decide_after_flag_guard(asm, *, message_text, slot_id, save_state, holdings_state_path, logger) -> (fail \| None, holdings_selection_ctx)` | |
| 러너에 남는 것 | setup_logging · 시각 3개 · `_finish` closure(1문장) · §3 가격 조회 · §3-a2 spike 신선도(고정) · §3-b · §4 · §4-b/c · §5 · §6 · §6-b · §7 · §8 · CLI | `run()` · `_parse_args` · `main` 이름 · 시그니처 불변 | 약 516 |

러너 쪽 모양(예):

```python
record = new_run_record(push_kind, mode, started_at=started_at_utc,
                        runtime_kst=runtime_kst, runtime_date_kst=runtime_date_kst)

def _finish(status, reason=None, error=None):
    return finish_run(record, status, reason, error, push_kind=push_kind, mode=mode,
                      logger=logger, history_path=_HISTORY_PATH,
                      insert_status=insert_status_from_record)
```

### 2-2. 동작 불변 규칙 (설계 STEP 8 대조)

1. **옮긴 코드의 문장 순서 · 조건 · 반환 튜플 모양**(2개 · 3개 인자)을 그대로 둔다. 러너는 `return _finish(*fail)` 로 받는다(기존 helper 와 같은 규약).
2. **14개 이름은 1-8 표대로** 처리한다 — 새 모듈의 직접 import 0.
3. **logger 는 러너 것을 넘긴다**. 새 모듈은 모듈 전역 logger 를 두지 않는다(`runner_spike` 선례 · `tests/test_runner_spike_extraction.py:178-182` — 이름 붙은 logger 에만 운영 로그 handler 가 붙는다).
4. **record 키 삽입 순서 불변** — `new_run_record` 는 같은 21키를 같은 순서로 만든다(JSONL 은 `json.dumps` 라 키 순서가 그대로 기록된다).
5. **지연 import 는 같은 자리에서 지연 import**(1-7). 모듈 머리 import 는 1-11 의 67개 안에서만.
6. **새 try/except 0 · 삼키는 예외 0 · 새 쓰기 0**. 미포착 예외 경로(1-2)는 그대로 빠진다.
7. **기존 모듈 blob 불변**(1-0 표 20개) — `scripts/ops02b2/reverse_verify_guards.py` 가 그 helper 함수들을 직접 부른다.
8. **테스트 파일 변경 0**(단언 · 바꿔 끼우는 대상 모두). 고쳐야 통과하면 그 자리에서 멈추고 보고한다.
9. **CLI · cron 명령 · 종료 코드 불변**(`--push-kind` · `--mode` · `--slot-id` · exit 0/1 규칙).

### 2-3. 하지 않는 것

원장 `event_id` · 신규 DB 쓰기 · signal payload · 새 try/except · 빈 hook · spike 경로 삭제 · `run_three_push_oci.py`(package fallback) 정리 · 문구 · 시간 · 임계 · 상한 변경 · C(가격 조회) · F(spike 2블록) 이동.

### 2-4. 변경 파일 목록 — 정식 범위 (판정 보정 2)

| 구분 | 파일 | 변경 |
|---|---|---|
| 운영 코드 | `app/three_push_runtime/runner_record.py` | 신규 |
| 운영 코드 | `app/three_push_runtime/runner_preflight.py` | 신규 |
| 운영 코드 | `app/three_push_runtime/runner_dispatch.py` | 신규 |
| 운영 코드 | `scripts/run_three_push_runtime_oci.py` | 수정(646 → 약 516) |
| 검증 코드 | `scripts/poc5_01a/runner_split_equivalence.py` | 신규 · 검증 전용(§3-1) · 운영 경로에서 import 0 · OCI 에서 실행하지 않음 · 폴더 `__init__.py` 없음(선례 `scripts/ops02b2/` 와 같음) |
| 문서 | `docs/PROGRAM_TRUTH.md` | 수정(§4 진입점 · 부록 A `runner :: _finish` → `runner_record.finish_run` 등) |
| 문서 | `docs/STATE_LATEST.md` | 수정 |
| 문서 | `docs/ai_result/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_RESULT.md` | 신규 |
| 문서 | 이 PLAN · 설계서 | 수정(확정 계약 · 판정 원문) |

**코드 파일 5개**(신규 4 = 운영 모듈 3 + 검증 스크립트 1 · 수정 1 = 러너). **테스트 0 · DB · cron · `.env` · 상태 파일 스키마 0.** 이 목록 밖 파일이 바뀌면 결과서 '지시문 외 변경'에 사유와 함께 적는다.

---

## 3. 검증 계획 (줄인 방식 — 파괴 시험 검토 1회 · 전체 회귀 마지막 1회)

### 3-1. 동등성 비교 — 기준점 고정 (판정 보정 3 · Q5 조건)

**비교 전 확인 4단계**(하나라도 다르면 구현 · 비교를 시작하지 않고 보고):

1. 구현 첫 수정 직전 `BASE_HEAD = git rev-parse HEAD` 를 결과서에 기록한다.
2. `git rev-parse BASE_HEAD:scripts/run_three_push_runtime_oci.py` == `f256677020232600627d207c54baf5081c70c6e2`.
3. 작업 트리 `git hash-object scripts/run_three_push_runtime_oci.py` == 같은 blob(첫 수정 전).
4. `git diff 7d507951 BASE_HEAD -- '*.py' '*.ts' '*.tsx'` 0줄(PLAN 실측 뒤 코드 변경 없음 — 문서 커밋만 허용).

**검증 스크립트 `scripts/poc5_01a/runner_split_equivalence.py` 동작**:

- ① 기준 러너 = `git cat-file blob f256677020232600627d207c54baf5081c70c6e2` 의 바이트. 실행 전에 git blob 해시(`sha1("blob <len>\0" + bytes)`)를 다시 계산해 상수와 같은지 확인한다. 다르면 exit 2 로 끝낸다. 같으면 그 바이트를 임시 파일 · 별도 모듈 이름으로 올린다. 비교 대상 = 작업 트리 러너. 둘을 **같은 프로세스 · 같은 실행**에서 돌린다(CLAUDE.md §2.2 — 과거 결과 재사용 없음).
- ② 대역: tmp state · tmp `runtime_state.sqlite` · Telegram stub(두 러너 모듈의 `telegram_send` 모두) · 시세 stub · `socket.connect` 차단(외부 호출 0) · 두 러너에 같은 고정 시각(`kst_now_iso` · `kst_today_date` · `kst_today`) · 같은 환경변수 flag.
- ③ 시나리오: 종료 27곳 중 도달 가능한 전부 + 부분 전송 + 미포착 예외 3종(조립 예외 · 발송 뒤 `mark_sent` 예외 · `insert_status` 예외).
- ④ 비교 항목(설계 STEP 8): Telegram 본문 byte · status · reason · error · JSONL 줄 내용과 키 순서 · `runtime_execution_status` · `runtime_sent_registry` 행 · 상태 파일 6종 존재 · 내용 · `main()` 종료 코드 · 예외 종류와 전파 여부 · 로그 줄(logger 이름 포함) · 1-8 의 14개 이름을 `run()` 전에 바꿔 끼웠을 때 두 러너가 같은 대역을 쓰는지. 실제 시계를 쓰는 `started_at` · `finished_at` · 등록부 `sent_at_utc` 만 정규화한다.
- ⑤ 정적 검사: 새 운영 모듈 3개의 AST 에 1-8 의 14개 이름 import 0 · 모듈 전역 logger 0 · 1-0 의 기존 모듈 20개 blob 이 상수와 같음.
- 출력: 시나리오별 같음/다름 표 · 기대 = 다름 0 · exit 0. 읽기 전용(저장소 · 라이브 `state/` · `logs/` 를 열지 않음).
- 도구 자체 검증: 구현 전에 '기준 러너 대 기준 러너'로 돌려 다름 0 을 먼저 보이고, 파괴 시험(§3-3)으로 다름을 잡는지 보인다.

### 3-2. 그 밖

1. **기존 테스트 무수정 통과**: 러너 구동 16파일(기준선 305 passed) → 분리 뒤 같은 수 · `git diff BASE_HEAD -- tests/` 0줄.
2. **import 실측**: 1-11 차단 실측 반복 — 67 + 새 3 = 70 · 외부 패키지 0 · 순환 0.
3. **품질 · 라이브 보호**: black · flake8 · py_compile · KS-10 전 파일 재실측(1-13 과 같은 명령) · 백엔드 전체 회귀 마지막 1회(run_in_background · 약 7분) · PC `state/` · `logs/` 전후 hash 동일.
4. **문서**: `docs/PROGRAM_TRUTH.md` · `STATE_LATEST` · 결과서(§2-4).
5. **배포 뒤 첫 거래일(OCI 읽기 전용)**: 08:30 · 09:15 · 09:30~15:20 · 12:30 · 15:40 실행 기록(JSONL) status · reason · 길이가 평소와 같은 모양 · `logs/` Traceback 0 · 발송 수 변화 0 · OCI 러너 blob = 새 blob.

### 3-3. 파괴 시험 (검토 1회)

(a) `_HISTORY_PATH` 를 호출 때가 아니라 모듈 상수로 넘기기 (b) `kst_today` 를 값으로 미리 계산 (c) §6-c 판정 두 줄 순서 바꾸기 (d) record 키 순서 바꾸기 (e) 새 모듈이 `insert_status_from_record` 를 직접 import → 기존 테스트 또는 동등성 스크립트가 잡는지 확인. 잡지 못하면 그 빈 곳을 결과서에 적고 설계자 판단.

---

## 4. 배포 · 롤백 (Q6 a 확정 = 단독 배포)

- 코드 = §2-4 의 5개. DB · cron · 상태 파일 스키마 · `.env` 변경 0.
- OCI 는 이미 `7d507951`(1-0) — 01A pull 에는 01A 코드 · 문서만 들어간다.
- OCI 반영 = 사용자 `git pull`. 시각: 거래일 15:40 실행이 끝난 뒤나 주말(실행 중 일부 파일만 바뀐 상태로 import 되는 것을 피함). 거래일 08:05 ~ 15:45 사이 금지(cron 08:10 배치 ~ 15:40 보유 브리핑).
- 첫 거래일 관찰(§3-2 ⑤) 뒤 `POC3-02D-OPS-04` 로 넘어간다.
- 롤백 = 커밋 revert + OCI pull. 분리 전용 스키마 · 데이터 변경이 없어 되돌릴 데이터가 없다(정상 실행 기록은 평소처럼 남는다 · 설계자 2026-10-03 정정).

---

## 5. 중단 조건 대조 (설계 STEP 9)

| 조건 | 판정 | 근거 |
|---|---|---|
| 메시지 · 판정 · 상태 저장 순서를 바꾸지 않고 분리할 수 없음 | 해당 없음 | 옮기는 블록은 문장 순서 그대로 · 쓰기 지점(1-3)은 같은 함수에서 같은 순서 |
| 기존 테스트가 함수 위치 자체를 운영 계약으로 사용 | **해당 없음(1건 회피)** | `getsource(runner.run)` 테스트(1-8)가 spike 신선도 블록 위치를 고정 → 그 블록을 옮기지 않는다. 14개 이름 바꿔 끼우기는 1-8 표대로 유지(테스트 수정 0) |
| 순환 import 를 피하려면 운영 동작 변경 필요 | 해당 없음 | 1-7 |
| 새 DB · API · cron · 외부 호출 필요 | 해당 없음 | 0 (검증 스크립트도 외부 호출 차단) |
| 570줄 이하로 만들려면 기능 삭제 · 의미 변경 필요 | 해당 없음 | 약 516줄 · spike 경로 유지 |

---

## 6. 설계자 확정 (2026-10-03 · 원문 = 설계서 끝 `# 설계자 PLAN 판정`)

| Q | 확정 | PLAN 반영 |
|---|---|---|
| Q1 분리 범위 | (a) A · B · D · E | §2 · 1-9 |
| Q2 테스트 고정 이름 | (a) 러너가 호출 때 전달 | 1-8 표 |
| Q3 공통 예외 종료 처리 | (a) PARAM 예외 변환 2곳만 이동 · 최외곽 예외 변환은 POC5-01B | 1-6 · 2-2 ⑥ |
| Q4 원장 writer 주입 경계 | (a) 식별까지만 | 1-12 |
| Q5 동등성 도구 | (a) 조건부 — 기준점 고정 · 변경 파일 목록 보정 | 1-0 · 3-1 · 2-4 (조건 반영) |
| Q6 OCI 반영 | (a) 01A 단독 배포 · 첫 거래일 관찰 뒤 OPS-04 | §4 |

새 질문은 없다. 재판정 요청 항목 = 필수 보정 4건 반영(맨 위 표).

---

## 7. 작업 순서 (재판정 PASS 2026-10-03)

1. 재판정 결과를 이 PLAN 맨 위 · 설계서 끝에 반영한다(완료). 선행 문서 정정(OCI 반영 확인 17곳)은 구현과 섞지 않는다.
2. §3-1 비교 전 확인 4단계 → `BASE_HEAD` 기록.
3. 검증 스크립트를 먼저 작성 · '기준 대 기준' 다름 0 확인(도구 자체 검증).
4. A → B → D → E 순서로 옮기고, 단계마다 러너 구동 16파일 + 동등성 비교.
5. 파괴 시험 검토 1회 → 품질 검사 → KS-10 재실측 → 전체 회귀 1회 → 라이브 hash.
6. `PROGRAM_TRUTH` · `STATE_LATEST` · 결과서 → 설계자 RESULT 판정 → 검증자 → 커밋(사용자 승인) → push(별도 승인) → OCI pull(사용자 · §4 시각) → 첫 거래일 읽기 전용 확인 → OPS-04.

---

## 부록 A. 재현 명령 (저장소 루트 · 읽기 전용)

```bash
# 1-0 기준점
git rev-parse HEAD
git rev-parse HEAD:scripts/run_three_push_runtime_oci.py
git hash-object scripts/run_three_push_runtime_oci.py
git log -1 --format=%H -- scripts/run_three_push_runtime_oci.py
git ls-tree HEAD app/three_push_runtime/ app/three_push_runner_common.py app/three_push_runtime_message_builder.py \
  app/runtime_evidence/holdings_risk_flow.py app/runtime_evidence/holdings_selection_flow.py \
  app/runtime_execution_status_store.py app/runtime_sent_registry_store.py tests/conftest.py

# 1-1 · 1-2 줄 수 · 종료 27곳
wc -l scripts/run_three_push_runtime_oci.py
grep -c "return _finish(" scripts/run_three_push_runtime_oci.py

# 1-13 KS-10 전 파일 인벤토리 (출력 파일 sha256 = 811eb85e…57f1e)
git ls-files '*.py' '*.ts' '*.tsx' | while read f; do printf "%s\t%s\n" "$(wc -l < "$f" | tr -d ' ')" "$f"; done > /tmp/ks10_inventory.tsv
shasum -a 256 /tmp/ks10_inventory.tsv; sort -rn /tmp/ks10_inventory.tsv | head -20

# 1-8 기준선 (러너 구동 16파일)
python -m pytest -q -p no:cacheprovider \
  tests/low_frequency_push/test_kind_flag_guard.py tests/low_frequency_push/test_runner_fail_closed.py \
  tests/low_frequency_push/test_selection_state_isolation.py tests/runtime_evidence/test_runtime_runner_forwarding.py \
  tests/test_holdings_risk_alert_runner.py tests/test_market_briefing_flow_through.py tests/test_oci_market_data_refresh.py \
  tests/test_poc3_02d_ops02_regular_push_contract.py tests/test_poc3_02d_ops03_briefing.py tests/test_runtime_runner_dry_run.py \
  tests/test_runtime_runner_partial_delivery.py tests/test_runtime_runner_spike_no_signal.py \
  tests/universe_bootstrap/test_runtime_universe.py tests/test_intraday_alert_flow_through.py \
  tests/test_poc3_02d_ops01_holdings_risk_flow.py tests/test_poc3_02d_ops02_delivery_state.py
```

14개 이름 전수: 전체 테스트를 돌리며 러너 모듈의 모든 속성 쓰기를 런타임 기록한다(정정 2026-10-04 · 첫 AST 스캔 `monkeypatch.setattr(<runner|runner_mod|mod>, …)` 은 딕셔너리 원소 형태 · poc4 파일을 놓쳤다).

## 부록 B. 이 PLAN 이 인용한 원문 경로 (설계자 OPEN_BLOCKERS 대응)

- 규칙: `CLAUDE.md`(저장소 루트)
- 설계: `docs/ai_design/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_DESIGN_V1.md` · `docs/ai_design/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_DESIGN_V1.md` · `docs/ai_design/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_DESIGN_V1.md`
- 직전 운영 단계: `docs/ai_design|ai_plan|ai_result/POC3/POC3-02D-OPS-0{1,2,3}_*` · 인계 `docs/handoff/POC3-02D-OPS-0{1,2,3}_*_HANDOFF_*.md` · `docs/handoff/POC3-02C_CLOSEOUT_2026-09-23.md`
