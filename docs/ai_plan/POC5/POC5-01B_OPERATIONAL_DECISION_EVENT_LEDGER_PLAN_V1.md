# POC5-01B — 운영 의사결정 이벤트 원장 개발 PLAN V1

```text
STEP_ID        = POC5-01B
DESIGN         = docs/ai_design/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_DESIGN_V1.md (설계자 2026-10-06 새 판)
UPPER          = docs/ai_plan/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_PLAN_V1.md §2 · §4 (Q1 ~ Q30 확정 · 다시 묻지 않음)
BASE_COMMIT    = a308353c (OPS-04 커밋 · 코드 기준)
STATUS         = PLAN 확정 — 설계자 PASS_WITH_MANDATORY_AMENDMENTS(2026-10-06 · 구현 승인 · 재제출 불필요 · 원문 = 설계서 끝) · 필수 보정 5건 · Q-A ~ Q-H 판정 반영(§8)
조사            = 설계서 §9 8항목 — 코드 조사 5영역(읽기 전용) + OCI 읽기 전용 확인 2회(2026-10-06) + PLAN 사실 · 계약 대조 2관점(지적 23건 반영)
설계자 질문      = 8건(§6) → 모두 판정 완료(§8)
```

## 0. 요약

설계서대로 만들 수 있다. 다만 코드나 확정 계약이 설계서 문장과 맞지 않는 곳이 8곳 있어 추천안과 함께 묻는다(§6). 핵심은 세 가지다.

1. **수동 실행을 가를 표식이 없다** — cron 과 수동 실행의 명령이 같다(Q-A).
2. **비선정 · 대체 ETF 값과 장중 설정 버전은 flow 반환값까지 오지 않는다** — 계산 함수 · 결과 객체에 기본값 있는 수집 자리를 더해야 한다(Q-B).
3. **'직전 평가' 를 온전히 가진 기존 저장소가 없다** — 원장 자기 행을 읽어야 한다(Q-C). 같은 날 반복 노출 규칙은 POC5-00 Q29 확정 문장과 새 설계서 §6 이 갈린다(Q-D).

새 DB 파일은 POC5-00 승인 경로(`state/decision/decision_evidence.sqlite`) 하나다. 외부 조회 · cron · 의존성 · 공개 API 추가는 0 이다. 설계서 §10 중단 조건에 해당하는 것은 없다.

## 1. 사실조사 (설계서 §9)

### 1-1. 러너 경계 (§9-1) — `scripts/run_three_push_runtime_oci.py`(517줄)

| 지점 | 위치 | 원장에 쓰는 법 |
|---|---|---|
| 실행 진입 | `run()` 134 → `new_run_record` 154-160 | 바로 뒤에 원장 문맥을 만들고 STARTED 를 INSERT 한다. 이때 알 수 있는 값은 push_kind · mode · CLI slot_id · `started_at_utc`(150) · `runtime_kst`(151) · `runtime_date_kst`(152) 뿐이다(param_id 는 preflight 뒤 · `run_id` 는 종료 INSERT 때 생김) |
| 처리된 종료 | `_finish` closure 162-177 → `finish_run`(runner_record.py:61-91) | `return _finish(...)` 19곳은 고치지 않는다. closure 안 `finish_run` **뒤에서** 원장을 확정한다 — `insert_status` · JSONL 이 실패하면 원장 확정 전에 예외가 되어 아래 경계로 간다(AC 5) |
| 미포착 예외 | `run()` 밖으로 나가는 예외(조립 · mark_sent · 상태 저장 · insert_status 등) | `main()`(505-513)은 예외를 잡지 않는다 → traceback · exit 1. 원장은 `run` 에 경계를 하나 두어 failed 확정을 시도한 뒤 **같은 예외를 bare raise** 한다 |
| 조립 결과 | `asm = assemble_push_kind(...)` 267 · `message_text = asm.message_text` 280 | `_finish` closure 는 asm 을 읽을 수 없다(196 · 216 · 225 첫 호출 시점에 미대입 → NameError · 실측). 원장 문맥 객체에 asm 을 속성으로만 싣는다 |
| 발송 | `telegram_send(message_text)` 429 · 결과 430-465 | 분할 전 본문 = 429 의 `message_text`. 결과는 문맥에 속성으로만 싣는다 |
| runtime `run_id` | `finish_run` 80 `insert_status(record)` 반환값을 버린다 | closure 가 넘기는 `insert_status` 를 반환값만 잡는 얇은 래퍼로 감싼다(시그니처 불변 · 테스트 대역이 None 을 돌려주면 run_id NULL) |

- **record 에 키를 더하지 않는다.** record 는 DB(19컬럼) · JSONL(전체) · stdout(전체)으로 나간다(runner_record.py:80-83 · 러너 509). 원장 값은 모두 별도 문맥 객체에 둔다.
- 기존 대조 키: DB · JSONL · stdout 에 모두 있는 것은 `(push_kind, started_at)` 하나다(POC5-00 §1-2 · 577/577 일치). 원장 run 에 `started_at` 을 같은 문자열로 둔다.
- 경계 방식: `run` 에 `functools.wraps` 데코레이터 하나를 두고, 문맥 객체는 `ContextVar` 로 넘긴다. 이렇게 하면 `run` 본문 약 300줄을 try 로 다시 들여쓰지 않는다. `tests/test_oci_market_data_refresh.py:316-327` 의 `inspect.getsource(runner.run)` 고정도 통과한다(getsource 가 unwrap · 조사 실측).

### 1-2. OCI 역할 표식 · 기본 비활성 (§9-2)

- **재사용할 역할 표식이 없다.** 코드 · 스크립트 · 설정에 OCI 역할 변수 · 상수가 0건이다(RUNTIME_ROLE · IS_OCI · OCI_ROLE · hostname 판정 0).
  - OCI `.env` 키(2026-10-06 읽기 전용 · 이름만): `KRX_API_KEY` · `PUSH_AUTOSEND_*` 6 · `TELEGRAM_*` 2.
  - `PUSH_AUTOSEND_*` 는 '발송 허가' 라 쓰지 않는다. OCI 에서 잠시 끄면 원장 모집단이 빠진다. 또 기존 테스트 9파일이 `setenv('PUSH_AUTOSEND_*', 'true')` 로 켠다.
  - `--environment pc|oci` 는 진단 스크립트 전용 인자라 cron 줄에 없다.
- **그래서 설계서 §3 의 '전용 환경 플래그 하나'** — `DECISION_LEDGER_ENABLED` 를 둔다(기존 `_ENABLED` 관례).
  - 읽기: 러너가 이미 쓰는 `load_dotenv_file`(러너 55) · `env_bool`(three_push_runner_common.py:128).
  - OCI `.env` 에 `DECISION_LEDGER_ENABLED=true` 한 줄 추가는 배포 때 **사용자 작업**이다(§5). `.env.example` 에 키 이름을 추가한다.
- **활성 조건** = `env_bool(DECISION_LEDGER_ENABLED) and mode == "send" and push_kind in {market_briefing, holdings_briefing, holdings_risk_alert}`.
  - 비활성이면 문맥은 no-op 이다(파일 open · mkdir · chmod 0회).
  - PC(키 없음) · dry-run · spike 는 0행이다.
  - OCI 의 autosend 끔(skip)도 원장 모집단에 남는다.

### 1-3. kind 별 item 필드 · disposition (§9-3)

**지금 flow 반환값까지 오는 값 / 오지 않는 값**

| kind | 이미 오는 것(KindAssembly · outcome · record) | 계산 함수 · helper 안에서 버려지는 것 |
|---|---|---|
| 시장 | `BriefingOutcome`(runner_dispatch.py:112-116) · record `sp500_asof` · `sp500_fresh` · `sp500_session_check` · diagnostics `outlook_state`(flow.py:370) · `index_status` · `index_candidates`(identifier) · 기준일 | Outlook 의 `sp500_return_pct` · reason(지역값 · 수익률 `ret` 은 runner_market_briefing.py:158 지역). 선정 그룹의 **ticker 목록**(`compute_index_leadership` evidence.py:185-235 의 `valid_tickers` · IndexCandidate 에 ticker 필드 없음) |
| 보유 브리핑 | `HoldingsSelectionOutcome` · `selected`(SelectedTicker) · `changes` · diagnostics `holdings_price_basis`(전 ticker) | **비선정 종목의 값**(`select_holdings` holdings_selection.py:345-347 `continue`). 실제 사용 현재가 · 시세 시각(`quote.current_price` · `price_asof` 314 · 322)은 선정 종목에도 남지 않는다 |
| 장중 | `HoldingsRiskOutcome`(selected · unavailable · changes · previous_state) · 본문 회차의 `risk_assembly.intraday`(plan · signals · suppressed) | 구간 밖 보유(holdings_risk.py:274-276). state None 사업군과 held 제외 사업군의 state(sector_signal.py:525-545). 대체 ETF 시세(intraday_alert_flow.py 지역 market_quotes). 장중 설정 `config_version_id`(`_load_active_sectors` 133 이 읽은 행에서 payload 만 꺼냄). 일일 상한 회차의 `IntradayAssembly`(holdings_risk_flow.py:438 은 본문 대체 분기만 대입) |

**disposition 매핑**(새 값 0 · 우선순위 위 → 아래)

| disposition | 시장 | 보유 브리핑 | 장중(보유 급락 · 급등 · 27 사업군) |
|---|---|---|---|
| data_unavailable | outlook `NONE`. 기초지수 구역이 **장애 상태**일 때(`prev_trading_day_missing` · API 조회 실패 · `META_GATE_STALE` · `CSV_REFRESH_REQUIRED` · 정합성 미달 · `stale` · flow.py:182-267 · 구역 단위 1행) | `DATA_UNAVAILABLE_OR_STALE`(holdings_selection.py:326-336). 본문 '데이터 확인 필요' 에 실려도 이 값이 우선이고, 원인 current_price/base_close 를 남긴다 | 보유 `outcome.unavailable`(등락률 없음). 사업군 excluded `no_quote` · `no_day_return` · `short_history` · `trend_not_t1` · `ticker_not_t1` · `representative_missing` · `intraday_config_unavailable`. 구역 전체 장애(`provider_down` · `low_coverage` · `sector_error`) |
| cut_by_daily_cap | 해당 없음 | 해당 없음 | `daily_cap_reached`(intraday_alert_flow.py:513-520) 회차의 보낼 항목(급락 new+worsened · 급등 send · 사업군 send) |
| cut_by_section_cap | 해당 없음(상위 2 는 선정 규칙) | 해당 없음(개수 상한 없음) | `plan.dropped`(intraday_alert_render.py:82-180 · reason `section_cap`) |
| sent | 방향 문장(UP/DOWN/FLAT) · 본문에 실린 후보 그룹(최대 2) | `send_full` 이면 선정 전부, 아니면 `changes.new + moved` | plan 에 실린 항목. 구 본문(정책 비활성)이면 new+worsened |
| suppressed | 해당 없음(no_change 억제 폐지) | 변화분 본문에서 빠진 '선정 − new − moved' | 급락 `changes.suppressed` · 급등 · 사업군 `.suppressed` |
| not_selected | 기초지수 정상 평가 · 후보 0(`no_candidate_normal` · flow.py:265-266 · 구역 1행). 상위 2 밖 그룹은 **코드가 보존하지 않아 기록 안 함**(설계 §6 은 선정 그룹만 요구) | 구간 밖(state None) · '정상 해소' 종목 | 활성 state 없음 · **held 제외**(계산된 state 는 값으로 남김 · excluded reason `held` 는 코드상 UNEVALUABLE 이지만 disposition 은 not_selected) |

- `sent` 는 '조립된 발송 본문에 실림' 이다. 실제 전달 여부는 같은 `event_id` 의 delivery 상태로 판정한다(Q-E).
- 장중 조립 예외 격리 회차(record `intraday_error` · holdings_risk_flow.py:443-451)에는 구 본문만 나간다. 이때 사업군 · 급등 item 은 만들지 않고 보유 급락 item 만 만든다.
- 개인값(quantity · avg_buy_price · 투자금 · 평가금 · account_group)은 item 에 넣지 않는다(privacy_detector.py:127 대상).
- 매도해 평가 대상에서 빠진 종목은 item 을 만들지 않는다.

### 1-4. 상태 구간 강도 · 회복 관측 (§9-4) — 코드에 있는 것만

| 계열 | state | 강도(코드) | 회복(비활성) 관측 |
|---|---|---|---|
| 보유 급락 | D5_7 · D7_10 · D10_PLUS | `_SEVERITY` 1 · 2 · 3 · `severity()`(holdings_risk.py:130 · 139-141 · dedupe 악화 판정에서 사용 — holdings_risk_state.py:132 · 156) | 코드 기록 없음 — 구간 밖이면 `continue`(holdings_risk.py:274-276) |
| 보유 급등 | U5_7 · U7_10 · U10_PLUS | `_SURGE_SEVERITY` 1 · 2 · 3 · `surge_severity()`(holdings_risk.py:87 · 93-95 · 호출 0건) | `SIGNAL_ABSENT`(continuous=False · sector_signal_state.py:250-283) |
| 27 사업군 | ENTRY_REVIEW · AVOID_DROP · AVOID_CHASE | **순서 상수 · 비교 함수 없음** | `SIGNAL_ABSENT` · 평가 불가(UNEVALUABLE)는 직전 관측 유지 |
| 보유 브리핑 | D5_8 · D8_10 · D10_PLUS(20거래일 하락 · holdings_selection.py:47-49 상수 · 53-57 `_DECLINE_BANDS` · `classify_decline` 101) · DATA_UNAVAILABLE_OR_STALE | 강도 상수 없음. 공개 `GROUP_ORDER`(73-78)가 강한 것부터 D10_PLUS · D8_10 · D5_8 순서를 둔다. 기존 변화 판정 `moved` 는 방향을 가리지 않는다(holdings_selection_state.py:143) | `resolved`(이전 선정 · 지금 미선정 · holdings_selection_state.py:134-150) |
| 시장 | UP · DOWN · FLAT · NONE | 전이 없음(시장 관찰) | — |

- **설계서 §6 이 이미 답한 매핑**
  - 사업군 state 끼리의 변경과 급락 D* ↔ 급등 U* 변경(주석 '급락과 별도 축')은 '비교 불가능한 상태 변경' 이다 → 새 상태의 `new_entry / PRIMARY`.
  - 평가 불가(UNEVALUABLE)는 회복으로 세지 않는다.
- **기존 dedupe 의 비교 기준은 '직전 평가' 가 아니다**
  - 급락: 그날 최악 구간이다. 비교는 holdings_risk_state.py:115-137, worst 유지는 140-158, 전체 전송 성공 뒤 저장은 161-172 다.
  - 급등 · 사업군: 마지막 성공 전달 상태(`last_delivered_state`) 다. 그와 별도로 **관측 `state`** 가 Gate 를 통과한 회차마다 덮인다(sector_signal_state.py:19-21 · 141 · 331-373). 단 관측 state 는 신호가 있던 ticker 만 담고, 날짜가 바뀌면 버리며, `finish_run` 안 `apply_intraday_records` 에서 이번 틱 값으로 덮인다 — 원장 확정보다 먼저다.

### 1-5. Telegram chunk · partial · 분할 전 본문 (§9-5)

- 분할 전 본문 = 러너 429 의 `message_text`(280 에서 정함 · 3종은 285 를 그대로 통과 · 금지문구 · raw 식별자 검사도 같은 문자열).
- 분할 = `telegram_send` 안 `_split_message_for_telegram`(three_push_runner_common.py:209 · 4,000자 · 줄 경계 · N>1 이면 `(i/N)` 머리).
- 반환 = `(sent, err, partial)` 3-튜플이다. chunk 수 · message_id 는 없다 — **실제 전달된 chunk 수는 알 수 없다**(원장은 계획 chunk 수 `planned_chunk_count` 만 남긴다 · 보정 2). 테스트 13파일 32줄이 러너의 `telegram_send` 를 이 3-튜플 대역으로 바꿔 끼우므로 반환 모양은 바꾸지 않는다.
- partial 은 2번째 이후 chunk 실패일 때만 True 다(298). 첫 chunk 실패는 err 접두가 `partial_delivery_at_chunk_1_of_N` 이어도 partial=False 다.
- delivery 상태: `telegram_attempted=False` → skipped · `sent` → sent · `partial` → partial · 그 밖 → failed.
- 비밀값: `telegram_send` 는 본문에 token · chat_id 값이 있으면 발송을 막는다(289-290). 원장 writer 도 같은 검사를 한다.
  - 걸리면 본문만 NULL · `body_withheld=1` 로 둔다.
  - `body_sha256` 은 남긴다(POC5-00 Q9 '전문 + SHA' 중 SHA 유지 · AC 8 '비밀값 없음' 충족).

### 1-6. 테이블 · 인덱스 · 짧은 트랜잭션 (§9-6)

- OCI 실측(2026-10-06 읽기 전용): Python 3.12.3 · SQLite 3.45.1(WAL · window 함수 가능) · ext4 · 실행 사용자 ubuntu · umask 0002(SSH 세션 값 · cron 값은 미실측 — 그래서 chmod 를 명시) · cron 13줄 모두 `cd /home/ubuntu/krx_hyungsoo &&`(상대경로 DB 가 저장소 기준) · cron PATH 에 `/usr/bin/git`.
- 저장소에 WAL · busy_timeout 명시 선례는 0이다. 기본 `sqlite3.connect` 의 timeout 5초가 곧 busy_timeout 5000 이다. 12:30 에는 보유 MIDDAY 와 장중 틱이 동시에 돈다.
- 연결 · 초기화 패턴은 `app/runtime_state_db.py`(경로를 호출 때 해석 · `CREATE … IF NOT EXISTS` · 초기화 캐시 · 테스트 리셋)를 따른다.
- `app/decision_evidence_store.py` 는 import 하지 않는다. 경로를 함수 기본값에 묶는 방식이고, 원장 경로가 PC 테이블 DDL(`ai_session_records`)을 돌리지 않게 하기 위해서다.
  - 같은 파일에 PC 테이블을 만드는 다른 길은 `app.api` 의 decision sessions 라우터뿐이다. OCI 는 API 서버를 돌리지 않는다(pydantic · fastapi 없음 · POC5-01A §1-11).

```text
evaluation_run  PK event_id(TEXT · 'ev_' + UTC 시각 + uuid4 8자 — decision_evidence_store._generate_id 의 '접두 + 시각 + uuid4 8자' 패턴 ·
                접두와 시각대(UTC)는 다름)
                run_state(STARTED / FINALIZED) · push_kind · contract_version · slot_id · tick(장중 HH:MM)
                · runtime_kst · runtime_date_kst · input_basis_date · mode · status · reason · error
                · started_at(= record started_at · 대조 키) · finished_at · run_id(NULL 허용) · param_id
                · config_version_id(장중 · Q-B) · off_schedule(0/1) · schedule_expected · cohort · tags_json
                INDEX (push_kind, started_at) · INDEX (run_state)
signal_item     PK (event_id, item_seq) · subject_kind(ticker / sector / market / index_group / index_block) · subject_id · held
                · state · prev_state · disposition · event_type · exposure · values_json(당시 계산값)
                · t0_price · t0_price_asof
                INDEX (subject_kind, subject_id)   — 직전 평가 조회(Q-C · Q-D)
delivery        PK event_id · delivery_status(sent / skipped / failed / partial) · telegram_sent
                · planned_chunk_count(계획 · 실제 전달 수 아님) · body_text · body_sha256 · body_withheld
ledger_meta     PK key · value · recorded_at   (INSERT OR IGNORE · 행 수정 0)
```

- 이름은 POC5-00 §2-3 개념 이름을 그대로 쓴다. meta 만 `ledger_meta` 다(PC 사본 · 일반명 충돌 방지). `price_outcome` · `user_feedback` 은 만들지 않는다(설계서 §2).
- **트랜잭션 2개**
  - 시작: `INSERT evaluation_run(STARTED)` 1문.
  - 종료: `BEGIN IMMEDIATE` → 직전 평가 SELECT(Q-C · Q-D) → `signal_item` executemany → `delivery` INSERT → `UPDATE evaluation_run SET run_state='FINALIZED', … WHERE event_id=? AND run_state='STARTED'` → rowcount==1 확인(아니면 롤백 · 오류 로그) → COMMIT.
  - 종료 확정은 같은 행 1회 갱신이다(POC5-00 §2-3 이 01B 에 맡긴 방식). item · delivery 를 UPDATE 하는 경로는 두지 않는다(스냅샷 불변).
- 연결: `sqlite3.connect(path, timeout=5.0)` + `PRAGMA busy_timeout=5000` + 초기화 때 `PRAGMA journal_mode=WAL`. 재시도 · 큐 · daemon 은 두지 않는다.
- 권한
  - DB 파일 0600 은 선례(scripts/run_holdings_publication.py:112-118 `_apply_mode_600`)를 따른다.
  - 폴더 0700(`mkdir` 뒤 `os.chmod`)은 이 단계의 새 결정이다.
  - **보정 1**: 폴더 0700 · DB 0600 을 만들거나 확인하지 못하면(chmod 실패 · stat 확인 불일치) **그 실행의 원장 쓰기를 중단**하고 오류만 기록한다 — 민감한 본문을 느슨한 권한으로 저장하지 않는다. PUSH 는 계속한다. 매 실행 쓰기 전에 폴더 · DB 권한을 stat 으로 확인한다.
  - `os.umask` 는 쓰지 않는다(프로세스 전체 영향).
  - 0600 DB 의 `-wal` · `-shm` 도 0600 이 되는 것을 PC 에서 실측했다.
- STARTED INSERT 가 실패한 실행은 그 실행의 원장 쓰기를 모두 멈춘다(item · delivery 고아 방지). 식별은 설계서 §7 대로 runtime 행과 오류 로그로 한다.

### 1-7. meta 1회 기록 (§9-7)

| 키 | 기록 | 근거 |
|---|---|---|
| `schema_version` | 초기화 때 INSERT OR IGNORE | 선례 `INSERT OR IGNORE`(app/runtime_sent_registry_store.py:53-73) |
| `first_active_at` | 첫 활성 STARTED 때 | 대조 하한(§2-6) |
| `deploy_commit` | 키가 없을 때만 `git rev-parse HEAD`(cwd=PROJECT_ROOT · timeout 5 · 예외 없음). **실패하면 아무것도 쓰지 않고 키를 비워 다음 실행에서 다시 시도한다**(Q-F 판정 · `unknown` 영구 저장 금지) | 선례 app/push_content_gap_diagnosis.py:61-74 · OCI cron PATH 에 git 있음 |
| `primary_start_date` | 첫 '활성 · 예정 시각(off_schedule=0) · 거래일'(`trading_day_lag.is_trading_day` · 외부 호출 0) 실행의 KST 날짜 | POC5-00 Q28 — 배포 시각 규칙(§5 · Q-F)과 함께 |
| `contract_version.<kind>.<version>` | 처음 관측한 시각 | 버전마다 1행이다. 계약이 바뀌어도 앞 행을 고치지 않는다 |

- kind 별 계약 버전 상수는 코드에 아직 없다(`contract_version` grep 0). 상태 파일 `SCHEMA_VERSION` 은 계약 개정 때도 바뀌지 않았으므로 쓰지 않는다. 새 상수는 원장 모듈의 dict 하나에 둔다. 값은 `<kind>.v1` 이고, legacy 라벨(POC5-00 §1-3)은 주석의 진단 정보로만 둔다.

### 1-8. 변경 파일 · 테스트 · KS-10 (§9-8 · 2026-10-06 `wc -l` 실측)

| 파일 | 지금 | 변경 | 예상 |
|---|---|---|---|
| 새 `app/three_push_runtime/ledger_store.py` | — | 연결 · DDL · STARTED · 종료 트랜잭션 · meta · 대조 순수 함수 | ~300 |
| 새 `app/three_push_runtime/ledger_items.py` | — | kind 별 item · disposition · 전이 · 태그(asm · 수집값 읽기만) | ~450 |
| 새 `app/three_push_runtime/ledger_context.py` | — | 활성 판정 · 문맥 객체 · 경계 데코레이터 · 비밀값 검사 · 예정 시각 상수 | ~200 |
| 새 `scripts/run_decision_ledger_reconcile.py` | — | 읽기 전용 대조 CLI(§2-6) | ~150 |
| `scripts/run_three_push_runtime_oci.py` | 517 | 데코레이터 1 · 문맥 연결 약 8줄 | ~527 |
| `app/market_briefing/flow.py` · `evidence.py` | 465 · 254 | `BriefingOutcome.outlook/index` · `IndexCandidate.tickers=()` | ~470 · ~257 |
| `app/runtime_evidence/holdings_selection.py` · `_flow.py` | 373 · 460 | `select_holdings(observations=None)` · `HoldingsSelectionOutcome.observations` | ~385 · ~466 |
| `app/runtime_evidence/holdings_risk.py` · `holdings_risk_flow.py` | 428 · 538 | `select_risk_holdings(evaluated=None)` · `RiskAssembly.intraday_eval` · outcome 운반 | ~436 · ~548 |
| `app/runtime_evidence/sector_signal.py` | **595** | `SectorOutcome` 에 기본값 있는 수집 필드 1줄 + append 2줄(`out` 이 늘 있어 None 가드 불필요 · 서명 불변) | **598** |
| `app/runtime_evidence/intraday_alert_flow.py` | 577 | 대체 ETF 시세 · `config_version_id` 수집(`IntradayAssembly` 필드 · `_load_active_sectors` 선택 인자) | ~586 |
| `tests/conftest.py` | 591 | 원장 경로 tmp · `DECISION_LEDGER_ENABLED` delenv autouse 1개 | ~610 |
| `.env.example` | — | 키 이름 `DECISION_LEDGER_ENABLED` | +1 |
| 새 테스트 3파일 | — | store · items · runner(기존 rig 재사용) | 각 ≤ 900 |
| 문서 | — | PROGRAM_TRUTH · KILL_SWITCHES · ASSUMPTIONS(Q-G) · MASTER_PLAN · POC3-00 지도 · STATE_LATEST(§3 · POC2 인계 문서는 고치지 않음) | — |

- 근접(600)에 가장 가까운 것은 `sector_signal.py` 다. 수집은 `SectorOutcome` 필드로 한다(`out` 이 늘 있어 None 가드가 필요 없어 자연스럽다). **보정 5**: 줄 수를 맞추려고 코드를 비틀지 않는다. 구현 뒤 600 ~ 649 이면 `NEAR` 로 기록하고 계속하며, 650 이상일 때만 멈춘다.
- `intraday_alert_flow.py` 제약 두 가지(기존 테스트가 고정함)
  - 코드에 `telegram` · `deliver` 부분 문자열을 쓰지 않는다.
  - `build_sector_outcome` 의 2-튜플 반환을 유지한다.
- 지금 저장소 전체 트리거 0 · 근접 6파일이다. 그중 이 단계 후보와 겹치는 파일은 0이다.
- 큰 테스트 파일(test_market_briefing_contracts 1,427 · test_intraday_config_integration 1,423 · test_intraday_alert_flow_through 1,342)에는 덧붙이지 않는다.

## 2. 구현 계획 (PLAN 판정 뒤)

1. **수집(additive · 반환 arity · 본문 · fingerprint · JSONL 불변)** — §1-3 '버려지는 것' 을 이미 계산된 값 그대로 담는다.
   - 함수 인자 3곳: `select_holdings(observations=None)` · `select_risk_holdings(evaluated=None)` · `_load_active_sectors` 의 config 수집.
   - 결과 객체 필드: `SectorOutcome` 수집 필드 · `IndexCandidate.tickers` · `BriefingOutcome.outlook/index` · `HoldingsSelectionOutcome.observations` · `HoldingsRiskOutcome` 평가 목록 · `IntradayAssembly` 의 대체 ETF 시세 · `config_version_id`.
   - `IndexCandidate.tickers` 는 반환 후보 객체에 값이 늘 채워진다. 본문 · fingerprint 는 identifier 만 쓰고, JSONL 은 identifier 만 싣는다(flow.py:372).
   - `RiskAssembly.intraday_eval` 은 `assemble_intraday_alert` 반환 직후 같은 객체 참조로 대입한다(일일 상한 회차 포함). except 격리 경로에서는 `out.intraday` 처럼 None 으로 되돌린다(OPS-01 결함 2 와 같은 규칙).
   - diagnostics · record 에는 넣지 않는다.
2. **원장 모듈 3개**(§1-6 · §1-7) — stdlib 만 쓴다(POC5-01A §1-11 · OCI 에 pydantic 없음).
3. **러너 연결**(§1-1)
   - 데코레이터를 단다.
   - `new_run_record` 직후 `begin` 을 부른다.
   - 조립 직후 asm 을, 발송 직후 결과를 싣는다.
   - `_finish` 안 `finish_run` 뒤에 `finalize` 를 부른다.
   - `insert_status` 래퍼로 run_id 를 잡는다.
   - 원장 오류는 기존 logger 에 `event_id` · 단계 · kind · 예외 종류만 남긴다(본문 · 비밀값 없음).
4. **run 값**
   - `input_basis_date`: 시장 = `sp500_asof`(방향 입력), 보유 = `holdings_axis_last_trading_day`(T-1), 장중 = `runtime_date_kst`. 나머지 날짜는 item `values_json` 에 둔다.
   - `param_id` = record 의 `param_id`. 러너가 실제로 읽은 DB 활성값이다 — BACKLOG §11 PARAM JSON/DB 불일치 항목의 재검토 트리거('POC5-01B 설계')에 대한 답이 된다.
   - `config_version_id` = 장중 수집값(Q-B · 시장 · 보유는 NULL).
   - `cohort`: `runtime_date_kst ≥ primary_start_date` 이면 `PRIMARY_LIVE`, 아니면 `LEGACY_DIAGNOSTIC`(POC5-00 §2-3 값).
   - **PRIMARY 통계 대상 = `cohort='PRIMARY_LIVE' AND off_schedule=0`** 으로 계약해 둔다(설계서 §3 · Q11).
5. **미포착 예외**: 경계가 failed 확정을 시도한다. 조립이 끝났으면 item 을 쓰고, 없으면 0건이다. delivery 는 record 의 `telegram_attempted/sent/partial_delivery` 로 쓴다 — 그래서 mark_sent 예외는 delivery=sent · run=failed 가 된다. 그 뒤 bare raise 한다.
6. **대조 CLI**
   - 두 DB 를 `file:…?mode=ro` 로 연다. `runtime_state_db.connection` 은 DDL 을 돌리므로 쓰지 않는다.
   - runtime 행은 `mode='send'` · 운영 3종 · `started_at ≥ ledger_meta.first_active_at` 만 대상으로 한다.
   - 키는 `(push_kind, started_at)` 이고, run_id 는 보조다.
   - 출력은 정상 · 누락(runtime 에만 있음) · STARTED gap · 원장에만 있음(`_finish` 를 거치지 않은 예외)의 ID · 건수뿐이다.
   - `.env` 를 읽지 않는다. 예외 경계는 return 3 이다(선례 scripts/run_oci_database_preflight.py).

## 3. 문서 정정 (설계서 §2 마지막 항목 · POC5-00 Q27)

- 현재형 gate 문장에만 날짜 붙은 한 줄 주석을 단다. 문구: '[2026-09-26 POC5-00 Q27] Decision Outcome Ledger 는 POC5(운영 원장)가 이어받는다 · First Real Decision Cycle PASS · 실제 판단 1건 선행 gate 는 superseded'. 본문 · 이력은 지우지 않는다. 대상:
  - `docs/MASTER_PLAN.md:14 · 16`(canonical 순서 3 → 5)
  - `docs/ai_design/POC3/POC3-00_PC_JUDGMENT_UI_INTEGRATED_IMPLEMENTATION_MAP_V2.md:80`(S-05) · `:111`(P-19) · `:112`(P-20 'P-19 이후') · `:127`(Lane POC4) · `:128`(Lane POC5 'Universe·ML · Ledger evidence 이후' — 실제 POC5 = 운영 원장이라는 점도 함께 적음) · `:210`(B-038) · `:290`(B-103)
  - `docs/STATE_LATEST.md` §6 Next action(2721 · 2723 근방)
- **보정 4**: 정정은 현재 정본(`MASTER_PLAN` · POC3 지도 · `STATE_LATEST` · `PROGRAM_TRUTH` · `KILL_SWITCHES` · `ASSUMPTIONS`)만 한다. 과거 POC2 인계 문서 두 개(`POC2_B_NEXT_ACTIONS.md` · `POC2_MOBILE_DECISION_OPERATING_SEQUENCE_ANCHOR.md`)는 고치지 않는다.
- 손대지 않는 것: 과거 기록 · 재검토 트리거(KILL_SWITCHES:106 · STATE_LATEST 과거 STEP 요약 · BACKLOG:289 · POC3-05 설계) · 사용자 소유 `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`. POC3-00 지도의 번호 전체 정리는 설계자 문서라 하지 않는다.
- KS-11 변경 근거: `docs/KILL_SWITCHES.md` 의 2026-07-26 기록 다음(맺음 문장 앞)에 기존 형식 그대로 넣는다. 형식은 `#### KS-11 변경 근거 기록` · 'KS-11 자체는 변경/약화하지 않는다' · 근거 · 기록 위치다. `docs/ASSUMPTIONS.md` §3 에도 한 항목을 더한다(Q-G 승인).
- PROGRAM_TRUTH(구현 단계)
  - §4 진입점 표: 'OCI PUSH 정식 runner' 행(:126 · 원장에 씀) · 'DB 경로 결정' 행(:130 · 새 경로 상수 · 새 플래그) · 새 CLI 행
  - §7.1: `decision_evidence.sqlite` 행에 'OCI = 운영 원장 4테이블 · PC = 세션' 을 병기
  - §9 러너 흐름
  - 부록 A: 새 모듈 · CLI symbol

## 4. 검증 계획 (줄인 방식)

| AC | 테스트(임시 DB · Telegram stub · 기존 rig 재사용) |
|---|---|
| 1 · 2 | 세 kind 대표 경로를 원장 비활성 · 활성으로 각각 돈다. 다음이 같은지 비교한다: 본문 byte · record · JSONL 줄 · runtime DB 행 · 상태 파일 · **부수효과 호출 순서**(telegram_send · mark_sent · 상태 저장 · insert_status · JSONL — 기록 대역) · **telegram_send 호출 수**. 비활성이면 원장 파일 생성 0 |
| 3 | spike · dry-run · 플래그 없음(PC) → 원장 0행 |
| 4 | sent · skip(autosend · push_kind · non_trading_day · no_selection · no_new_or_worsened · daily_cap) · 중복 · partial · Telegram 실패 → run FINALIZED · status · delivery 상태 |
| 5 · 6 | 조립 예외 · 발송 뒤 mark_sent 예외 · insert_status 예외 → 원장 failed · 같은 예외 · traceback · **`main()` exit code** 가 같다. STARTED · 종료 INSERT/UPDATE 실패를 주입하면 PUSH 결과 · 예외 전파가 같고 STARTED gap 이 남는다 |
| 7 | 비선정 · 억제 · 잘림 · 대체 ETF 가 수집값으로 기록되고, fetcher 호출 수가 활성 · 비활성에서 같음 |
| 8 | body SHA-256 = 분할 전 본문. 비밀값이 든 본문은 본문만 보류하고 SHA 는 유지 |
| 9 | 대조 CLI 4분류(tmp 두 DB) |
| 스냅샷 · 실발송 | 같은 event_id 를 두 번째로 종료 확정하면 거부되고 기존 행이 그대로다 · item · delivery 를 UPDATE 하는 코드 경로가 0 · Telegram 은 stub 호출만 있다(실발송 0 · POC5-00 §2-3 · §3-2) |
| 10 | 파괴 시험 1회 · 검토 1회(관점 중복 없음) · 전체 회귀는 마지막 1회 · KS-10 실측 |

- conftest autouse 가 원장 경로를 tmp 로 돌리고 `DECISION_LEDGER_ENABLED` 를 지운다(러너 import 때 PC `.env` 적재 대비). 원장 테스트만 tmp 경로 + setenv 로 켠다. 라이브 가드 legacy 목록에는 추가하지 않는다.

## 5. 배포 · 롤백

- 게이트: OPS-04 첫 거래일 확인 · 종료 뒤(설계서 §10).
- 배포는 다음 순서로 한다. 커밋 · push(승인) → OCI `git pull` → OCI `.env` 에 `DECISION_LEDGER_ENABLED=true` 한 줄 추가(둘 다 사용자 작업). cron 변경은 0이다.
- **시각 규칙(Q-F · 보정 3)**: pull 과 플래그 추가는 거래일 **15:45 이후**나 비거래일에 한다. 그러면 첫 활성 회차가 다음 거래일 08:30 이 되어 Q28 '코드 pull 뒤 첫 거래일' 과 맞는다.
- 첫 거래일 확인(개발자 · OCI 읽기 전용): 원장 4테이블 행 수 · STARTED 잔류 0 · 대조 CLI(정상 = runtime send 행 수) · 원장 파일 0600 · 폴더 0700 · 로그 오류 0. reflog pull 시각은 결과서에 인용한다.
- 롤백: OCI `.env` 의 플래그 한 줄을 지우면 즉시 비활성이다(코드 경로 no-op). 코드 롤백은 revert + pull 이다. 원장 파일은 남아도 읽는 곳이 없다.

## 6. 설계자 질문 (코드 · 확정 계약과 실제로 맞지 않는 것만)

| # | 설계서 · 확정 문장 | 코드 사실 | 추천안 |
|---|---|---|---|
| **Q-A** | §3 '수동 send 는 `off_schedule=true`' | cron 줄과 수동 실행의 인자가 같다. 수동을 가르는 표식이 없다. 시각표는 OCI crontab 에만 있다. 코드 상수는 보유 `SLOT_TIME_LABEL`(holdings_selection_flow.py:52)과 시장 머리 '08:30'(render.py:38)뿐이고 장중 7틱은 없다 | 원장 모듈에 kind 별 예정 시각 상수를 둔다(시장 08:30 · 보유는 `SLOT_TIME_LABEL` 재사용 · 장중 09:30 ~ 15:20 7틱). `runtime_kst` 의 HH:MM 과 평일 여부를 비교해 `off_schedule` 과 `schedule_expected` 를 남긴다. cron · CLI 변경 0. 대가: cron 시각을 바꾸면 이 상수도 같이 고쳐야 한다(OPS-03 08:00 → 08:30 같은 경우) |
| **Q-B** | §5-4 'KindAssembly 와 각 flow 결과에 payload 만 추가' · §6 비선정 기록 · §4 run 'PARAM/config ID' | 비선정 보유 값 · 시장 선정 그룹 ticker · 구간 밖 장중 보유 · state None/held 사업군 · 대체 ETF 시세 · 장중 설정 `config_version_id` 는 flow 아래 계산 함수 · helper 의 지역값으로 끝난다(§1-3) | flow 아래로 한 단계 내려가 **기본값 있는 수집 자리**를 둔다. 함수 인자 3곳과 결과 객체 필드를 쓰고(§2-1), 기본값이면 지금과 동일하다. 이미 계산 · 조회된 값만 담는다. 반환 arity · 정렬 · 본문 · JSONL 은 바꾸지 않는다(테스트 고정). 새 계산 · 재조회는 0이다 |
| **Q-C** | §6 '같은 `(push_kind, subject)` 의 직전 평가와 비교' · §5-4 '추가 조회 금지' | 직전 평가를 온전히 가진 기존 저장소가 없다. 급락 파일은 '그날 최악' 이다. 급등 · 사업군 파일의 관측 state 는 신호가 있던 ticker 만 담고, 날짜가 바뀌면 버리며, 원장 확정 전에 이번 틱으로 덮인다. 보유 브리핑 · 비신호 · 시장은 아예 없다(§1-4) | 종료 트랜잭션 안에서 **원장 자기 행**을 읽는다. 대상은 같은 kind · subject 의 가장 최근 `FINALIZED` · `off_schedule=0` item 1건이다. 평가 불가 · 자료없음은 건너뛴다. 실패하면 prev_state · event_type · exposure 를 NULL 로 둔다. 시장 · 외부 자료를 다시 조회하는 것이 아니라 '추가 조회' 가 아니라고 보는데, 확인을 부탁한다. **첫 활성일(cold start)**: 직전 행이 없으면 설계서대로 `new_entry / PRIMARY`, prev_state 는 NULL 이다. 며칠째 이어지던 상태도 첫날엔 PRIMARY 가 되므로, 집계(POC5-02 · 04)에서 `primary_start_date` 당일을 따로 볼 수 있게 meta · cohort 로 식별 가능하게 둔다 |
| **Q-D** | §6 '비활성 관측 뒤 다시 활성 = `reentry_after_recovery / PRIMARY`' · '더 강한 구간 = `worsened / PRIMARY`' 대 POC5-00 Q29 확정 보완 '**같은 날에도 같은 상태는 첫 노출만 PRIMARY**' | 장중은 1시간마다 평가한다. 같은 날 D7 → 구간 밖 → D7, 또는 D10 → D7 → D10 이 나오면 두 문장이 다른 exposure 를 준다. 또 §6 에는 같은 계열 약화(D10_PLUS → D7_10 · U10_PLUS → U5_7)에 해당하는 칸이 없다 | event_type 은 §6 대로 직전 평가 기준이다(reentry_after_recovery · worsened). exposure 는 **Q29 확정 보완을 우선**한다. 같은 KST 날짜 · 같은 subject · 같은 state 가 그날 예정 회차에서 이미 PRIMARY 였으면 SECONDARY 로 둔다(장중 오르내림에 따른 PRIMARY 부풀림 방지 · 원장 자기 읽기 1회 더). 같은 계열 약화는 `repeat_exposure / SECONDARY` 이고 prev_state 를 남긴다 |
| **Q-E** | §4 delivery `chunk 수` · §6 disposition 값 · '실제 전달된 항목만 전달 효과 표본' | `telegram_send` 는 chunk 수를 돌려주지 않는다(반환 3-튜플 · 테스트 대역 13파일 32줄). item 분류는 조립 때 끝나고, 전달 실패 · 부분 전송 · flag off · 중복은 run 단위로 뒤에 정해진다. 6값에는 '실렸으나 미전달' 이 없다 | chunk 수 = 같은 본문에 순수 함수 `len(_split_message_for_telegram(text))` 를 다시 부른 **계획 chunk 수**로 둔다(I/O 0 · 결정적). 발송을 시도하지 않았으면 NULL 이다. disposition `sent` = '조립된 발송 본문에 실림' 이고, 전달 효과 표본 = `disposition='sent' AND delivery_status='sent'` 로 정의한다(새 값 0) |
| **Q-F** | POC5-00 Q28 'pull(reflog) 뒤 첫 거래일 · 근거를 원장 meta 에' | 러너 경로에는 reflog · pull 시각을 읽는 코드가 없다. 장중 pull 이면 '첫 활성 회차 날짜' 가 그날(부분 일)이 된다 | meta `primary_start_date` = 첫 '활성 · 예정 시각 · 거래일' 실행 날짜, `deploy_commit` = `git rev-parse HEAD` 1회. **배포 시각 규칙**(15:40 뒤나 비거래일에 pull · 플래그)으로 Q28 과 맞춘다. reflog 는 결과서에 인용한다 |
| **Q-G** | §2 'KS-11 변경 근거' | KS-11 조치 문구는 '새 데이터/근거를 ASSUMPTIONS 또는 PROJECT_ORIGIN_INTENT 에 기록 후 변경' 이다. 기존 기록 3건도 모두 두 문서에 함께 기록했다. 두 문서에는 원장 언급이 0건이다 | KILL_SWITCHES KS-11 기록과 함께 `docs/ASSUMPTIONS.md` §3 '이미 답이 나온 것' 에 한 항목(근거 = POC5-00 Q27 · 2026-09-26 판정 · 사용자 승인)을 더한다. PROJECT_ORIGIN_INTENT 는 고치지 않는다 |
| **Q-H** | POC5-00 Q14 '시장 태그: FLAT/NONE · 동일 미국 세션 · 연휴 직후 · 입력 지연'(이름만 확정) | '동일 미국 세션' · '연휴 직후' 를 계산하는 코드가 0건이다. 직전 실행의 미국 세션은 상태 파일에도 없다. 또 POC5-00 §5-4 '미국 입력 신선도 상한 없음' 은 OPS-03 이후 낡았다 — 지금은 기대 세션과 일치해야 fresh 다(runner_market_briefing.py:78-102). 그래서 지연된 입력은 대부분 이미 NONE 이다 | 이미 있는 값으로만 정의한다. FLAT/NONE = outlook state. **입력 지연** = `sp500_session_check.reason ≠ ok`(미국 입력만 · Q14 근거 §5-4 그대로 · 한국 기초지수 상태는 태그로 넣지 않고 원시값으로 따로 기록). **동일 미국 세션** = 원장 직전 예정 시장 run 의 `sp500_asof` 와 같음(Q-C 와 같은 원장 자기 읽기). **연휴 직후** = 기대 T-1 과 오늘 사이에 한국 평일 휴장이 있음(로컬 캘린더 `is_trading_day` · 외부 호출 0). 한국 · 미국 중 어느 연휴를 뜻하는지 확정을 부탁한다 |

## 7. 사용자 확인 항목

1. 배포 때 OCI `.env` 한 줄 추가(`DECISION_LEDGER_ENABLED=true`)와, 배포 시각을 '거래일 15:45 이후나 비거래일' 로 하는 규칙(Q-F · 보정 3). OCI 플래그 추가와 배포는 OPS-04 종료 뒤 사용자 승인으로 한다.
2. 원장에 분할 전 본문 전문이 남는다(POC5-00 Q9 확정 · 파일 0600 · 로컬 사용자 한정). 비밀값이 든 본문만 본문을 보류하고 SHA 는 남긴다.
3. 이 PLAN 은 아직 커밋하지 않았다. OPS-04 종료 커밋과 섞지 않도록, 커밋 순서는 OPS-04 종료 때 정한다.

## 8. 설계자 판정 반영 (2026-10-06 · PASS_WITH_MANDATORY_AMENDMENTS · 원문 = 설계서 끝)

| 항목 | 판정 | 이 PLAN 에 반영한 곳 |
|---|---|---|
| Q-A | 추천안 승인 | 예정 시각 상수로 off_schedule 판정. **한계로 기록**: cron 이 1분 이상 늦게 시작하면 off_schedule 로 잡힐 수 있다 |
| Q-B | 승인 | §2-1 수집 자리(이미 계산된 값을 기본값 있는 필드로 운반) |
| Q-C | 승인 | 원장 자기 행 조회 · 첫날 `new_entry / PRIMARY` 허용 |
| Q-D | 추천안 승인 | `event_type` = 실제 전이(직전 평가) · `exposure` = 같은 날 같은 subject · state 첫 노출만 PRIMARY |
| Q-E | 조건부 승인 | 컬럼 `planned_chunk_count`(§1-5 · §1-6 · 실제 전달 chunk 수는 알 수 없음) · disposition `sent` = 본문에 실림 |
| Q-F | 조건부 승인 | 배포 시각 거래일 15:45 이후 · 비거래일(§5) · `git rev-parse` 실패 시 키를 비워 다음 실행에서 재시도(§1-7) |
| Q-G | 승인 | KILL_SWITCHES + ASSUMPTIONS 기록(§3) |
| Q-H | 한국 시장 휴장 기준 확정 | 태그 `after_kr_market_closure`(기대 T-1 과 오늘 사이 한국 평일 휴장) · 미국 휴장 영향은 `same_us_session` · 입력 지연 = 미국 입력(`sp500_session_check.reason ≠ ok`) · FLAT/NONE = outlook state |
| 보정 1 | 필수 | 권한 0700/0600 을 만들거나 확인하지 못하면 그 실행 원장 쓰기 중단 · 오류만 기록 · PUSH 계속(§1-6) |
| 보정 2 | 필수 | `planned_chunk_count`(§1-5 · §1-6) |
| 보정 3 | 필수 | 거래일 15:45 이후 · 비거래일(§5 · §7) |
| 보정 4 | 필수 | POC2 인계 문서 2개는 고치지 않음(§3) |
| 보정 5 | 필수 | 줄 수 맞추기 금지 · 600 ~ 649 = NEAR 기록 후 계속 · 650 이상만 중단(§1-8) |
