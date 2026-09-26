# POC5-00 — 운영 신호·판단 결과 원장 MASTER PLAN V1 (확정)

```text
STEP            = POC5-00 MASTER PLAN · 사실조사 (설계 §8 · §10)
DESIGN          = docs/ai_design/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_DESIGN_V1.md
PLAN_DECISION   = PASS_WITH_MANDATORY_AMENDMENT (설계자 2026-09-26) · Q1~Q30 확정(§4) · 확정 계약 §2
USER_APPROVAL   = OCI 전용 원장 SQLite 생성 · PC 기존 decision_evidence.sqlite 테이블 추가 (사용자 2026-09-26)
IMPLEMENTATION  = POC3 운영 정정 소형 PLAN → POC5-01a → 01 → 02 → 03 → 04 (단계마다 짧은 PLAN · §3)
이번 조사의 변경   = 코드 · DB · cron · flag · OCI · Telegram 변경 0 (OCI 는 읽기 명령만 · 과거 신호 뒤 수익률은 열지 않음)

사실조사 요약 (설계 §10 · 15항목 · §1 · 제출 당시 요약 — 미결·제안 표현은 §2 · §4 확정이 우선):
  1 운영 신호     OCI cron 12줄 = 시장 08:00 · 보유 09:15/12:30/15:40 · 장중 7틱(09:30~15:20) · 배치 07:20 · spike 0줄
                 발송 flag = 시장·보유·장중 true · spike false (2026-09-26 OCI 실측)
  2 연결 ID      실행마다 started_at(DB·JSONL 공통) · DB run_id(JSONL 에 없음) · duplicate_key(발송 단계까지 간 회차만)
                 발송 본문 · 본문 hash · Telegram message_id 는 어디에도 저장하지 않는다
  3 구조화 필드   회차 단위 개수·상태만 남는다 · 종목 단위 신호는 남지 않는다 · contract_version 필드 없음
                 계약 경계 시각은 OCI pull 시각(git reflog)으로 실측했다 → 확정(Q12): kind 별 코드 상수 · legacy 버전은 진단 전용
  4 기록 위치     sent·skipped·failed 사유는 DB·JSONL 모두 · partial 은 JSONL 필드 · 억제·상한·신호 없음은 개수만(일부 회차는 개수도 없음)
  5 기존 이력     JSONL 635행(06-18~09-25) · DB 577행(07-09~) — 577/577 정확 대응 · 실제 발송 행 ↔ 발송 등록부 100%
                 종목 단위 연결 0% → UNLINKABLE_LEGACY
  6 가격 source   OCI 에 이미 있다 — KRX 무조정 종가(전 ETF · 08-13~ 28일 · 결측 0 · FDR 보다 1거래일 늦게 적재)
                 · etf_daily_price OHLC(보유∪seed 41종) · 지수 종가(KOSPI 09-17 에서 멈춤) → 신규 외부 API 불필요
  7 시장 예측 대상 코드의 방향 필드는 Outlook.state(UP/DOWN/FLAT/NONE = S&P500 직전 1세션 수익률 부호) 하나다
                 한국 쪽 대상(지수·시가/종가) 필드는 없다 → 확정(Q13 (d)): 방향 적중률 없음 · S&P500 상태와 한국 시장 원시 결과만 병기
  8 보유 예측 필드 없음 · 상태는 RECENT_DECLINE 3구간(지난 20거래일 하락) + DATA_UNAVAILABLE → 상태별 원시 성과만 가능
  9 장중 상태     보유 D5_7/D7_10/D10_PLUS · U5_7/U7_10/U10_PLUS · 사업군 ENTRY_REVIEW/AVOID_DROP/AVOID_CHASE
                 (설계 §4.4 의 AVOID_SURGE 는 코드에 없다) · 상태별 outcome 정의 가능, 단 기준 가격·잘림·억제 항목은 새로 기록해야 한다
 10 저장소       원장 테이블은 어디에도 없다 → 신규 테이블 필요 · OCI→PC 데이터 전달 경로도 없다
 11 피드백 위치   PC 에 '최근 받은 메시지' 화면이 없다 · 후보 3곳(Q23)
 12 PC 미가동     OCI 07:20 배치 뒤 독립 단계에서 성숙 outcome 계산 가능(신규 cron 없음 · OCI 배포는 필요 · Q2·Q25)
 13 PRIMARY 시작  → 확정(Q28): 운영 정정(§3-1) · OCI 에 POC5-01 코드 pull 확인(reflog) 뒤 첫 KRX 거래일 (§2-7)
 14 최초 리뷰     → 확정(Q28 · Q29): 10거래일 뒤 R0 수집 점검 · R1 정기 기술통계(날짜 블록 bootstrap) · 성공 임계 없음
 15 KS-10·경계   528파일 TRIGGER 0 · NEAR 7(러너 646 · api.py 641 …) → 러너 선분리 필요 · 라이브 가드는 state/·logs/ 자동 보호
                 · Telegram 전역 차단 없음(테스트별 stub)
확정 요지 (§2 · §4):
  RAW_ONLY · 방향 적중률 없음 · PRIMARY t0 = 메시지 생성에 쓴 현재가 · 과거 종목 단위 UNLINKABLE_LEGACY
  OCI 전용 원장 state/decision/decision_evidence.sqlite · runtime_state.sqlite 변경 0 · 실행 진입부터 추적 · 누락은 명시적 gap
  PRIMARY 전 운영 정정 7건(§3-1) · 즉시 중단 조건(설계 §12) 해당 0
```

- **작성**: 개발자(VSCode Claude) · **독자**: 설계자 · **작성일**: 2026-09-26
- **입력**: 설계서 `docs/ai_design/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_DESIGN_V1.md` §0~§12(설계자 원문)
- **기반 문서 확인**: `PROJECT_ORIGIN_INTENT` §4·§10(저장소 규칙) · `KILL_SWITCHES` KS-5·KS-10·KS-11 · `ASSUMPTIONS` Q4(Layer A)·Q6(운영 계약 OPEN)
- **조사 방법**
  - 에이전트 7개가 영역별로 코드·로컬 state·문서를 읽었다(읽기 전용 · 로컬 DB 는 `mode=ro`).
  - 영역: 러너·전송 기록 · 시장 브리핑 · 보유 브리핑 · 장중 · 가격 source · 피드백 화면 · 저장소·경계.
  - OCI 는 개발자가 읽기 명령으로만 확인했다(`crontab -l` · `.env` 의 `PUSH_AUTOSEND_*` 줄 · `git reflog` · 파일 목록 ·
    `mode=ro` SQLite 조회 · 로그 건수).
  - 가격 값 · 신호 뒤 수익률 · 적중률은 출력하지 않았다(설계 §5). 건수·기간·연결 비율 외에 열람한 것은 하나다:
    시장 신 경로 행의 날짜별 status · outlook_state · index_status · 후보 수 · 본문 길이 · 실행 시각(수익률 계산 없음).
  - 사실조사 에이전트는 02B-1 결과서를 읽었지만 그 적중률 수치는 옮기지 않았다.
  - 로컬 PC 에는 OCI 운영 이력 사본이 없다. 기존 이력 수치는 모두 OCI 실측이다.

---

## 1. 사실조사 (설계 §10 · 15항목)

> §1 은 제출 당시 사실조사다. 사실은 그대로 유효하고, 안에 남은 제안 · 추천 · '확인을 받는다' 같은 미결 표현은 §2 · §4 확정이 우선한다.

### 1-1. 세 운영 push kind 의 cron · flag · 최근 이력 (항목 1)

OCI `crontab -l`(2026-09-26 실측 · 주석 제외 12줄):

```text
0 8 * * 1-5     market_briefing   --mode send
15 9 · 30 12 · 40 15 * * 1-5   holdings_briefing --slot-id OPEN / MIDDAY / CLOSE
30 9 · 30 10 · 30 11 · 30 12 · 30 13 · 30 14 · 20 15 * * 1-5   holdings_risk_alert (7틱)
20 7 * * 1-5    run_oci_market_data_batch.py
spike_or_falling_alert  0줄
```

- `.env` flag: `PUSH_AUTOSEND_ENABLED` · `_MARKET_BRIEFING_` · `_HOLDINGS_BRIEFING_` · `_HOLDINGS_RISK_ALERT_` = true ·
  `_SPIKE_OR_FALLING_ALERT_` = false.
- OCI HEAD = `8bf843e6`(저장소와 같음).
- 12:30 에는 보유 MIDDAY 와 장중 틱이 같은 분에 따로 돈다.
- 이력 파일 `state/three_push/oci_runtime_history.jsonl` 은 635행이다. 기간과 종류별 건수:

  | push kind | 행 수 | 기간 |
  |---|---|---|
  | `market_briefing` | 93 | 06-18~09-24 |
  | `holdings_briefing` | 191 | 06-18~09-25 |
  | `holdings_risk_alert` | 98 | 09-08~09-25 |
  | `spike_or_falling_alert`(폐지) | 253 | 06-18~09-07 |

- 09-24·09-25 는 세 종류 모두 `skipped/non_trading_day` 다(추석 연휴).

### 1-2. 메시지와 runtime record 를 잇는 기존 ID (항목 2)

- **실행 순서**: 러너의 처리된 종료는 모두 `_finish` 한 곳을 지난다(`scripts/run_three_push_runtime_oci.py:172-192`). 순서는 다음과 같다.
  1. 장중 관측·집계 기록(예외를 삼킴)
  2. `runtime_state.sqlite` 의 `runtime_execution_status` INSERT — fail-closed 라 실패하면 예외를 올린다
  3. JSONL 1줄 append
  4. 로그

  메시지 조립은 flag guard 앞, skip 확정은 그 뒤에 있다.
- **공통 키**:
  - `started_at`(UTC µs)이 DB·JSONL·stdout 모두에 있는 유일한 공통 필드다.
  - DB `run_id` 는 INSERT 때 생기지만 러너가 반환값을 버려 JSONL 에는 없다(`:181`).
  - OCI 실측: DB 가 시작된 07-09 이후 JSONL 577행이 모두 `(push_kind, started_at)` 로 DB 행과 정확히 대응한다(DB 에만 있는 행 0).
- **`duplicate_key`**:
  - 형식은 `push_kind::param_id::날짜[#슬롯|#HH:MM]` 이다.
  - 발송 중복 가드(§7)까지 간 회차에만 채워지고, 그 전에 끝난 skip·fail 은 빈 문자열이다.
  - 발송 등록부(`runtime_sent_registry`) 행과 문자열이 같다.
  - OCI 실측으로 실제 발송 행은 모두 등록부와 이어진다: 보유 126/126 · 장중 14/14 · 시장 51/51 · spike 46/46.
  - 등록부에만 있는 행: 보유 15(06-20~07-09) · 시장 17(06-18~07-09) — DB 첫 행(07-09 15:30 KST) 이전 발송분이다.
    도입 때 넣은 seed(문서상 47행)로 추정하지만 행 대응은 확인하지 않았다.
    spike 165 는 08-25 까지 이어지는데, spike 등록부 키가 신호별(`날짜#ticker#…`)이라 실행 행과 1:1 이 아니다(폐지 · 채점 대상 아님).
- **없는 것**:
  - Telegram 응답의 `message_id` 는 버린다(`three_push_runner_common.py:321-327`, `ok` 만 확인).
  - 발송 본문과 본문 hash 는 저장하지 않는다(record 에 `message_text_length` 만 있음).
  - `holdings_risk_alert` 는 `message_text_length` 도 항상 0 이다(채우는 코드 없음).
- **비정상 종료** — `_finish` 를 우회해 DB·JSONL 기록이 남지 않는 경로가 둘 있다.
  - 발송 뒤: `mark_sent`·상태 저장 예외(`runner_evidence.py:217-267` 무보호).
  - 발송 전: 조립 단계에서 하위 모듈이 잡지 않은 예외. `run()` 의 except 는 PARAM 로드 2곳(`:205`·`:215`)뿐이다.
    예: 시장 브리핑 `krx_store` sqlite 오류는 try/finally 만 있다(`krx_store.py:74-81`).
  - OCI 실측(`logs/low_freq_push_cron.log` 의 Traceback grep): 0건 · `database is locked`(모든 로그) 0건.

### 1-3. signal item 의 구조화 필드와 contract version (항목 3)

**버전 필드 없음**
- `contract_version`·`rule_version` 은 실행 record·DB 어디에도 없다.
- `param_id` 는 계약을 가르지 못한다. OCI 활성 PARAM `param-20260907T152806-255383` 하나가 09-08~09-25 의 계약 변경 셋을 모두 걸친다(DB 실측).
- 장중 config 는 `intraday_alert_config_version` 에 버전이 있다(`sector_rep.v1` · 2개). 하지만 틱 record 에 기록되지 않는다.
  활성 행은 `intraday-20260921T144447-168782`(2026-09-21 23:48 KST `oci_apply`) 1행뿐이라 활성화 이력이 없다.

**종류별 구조화 필드(JSONL · DB 에는 없음)**

| kind | 남는 것 | 남지 않는 것 |
|---|---|---|
| 시장 | `calendar` · `outlook_state` · `index_status` · `index_candidates`('운용사\|기초지수명' 최대 2) · `index_diagnostics` · `state_fingerprint` · `content_unchanged` | S&P500 수익률 값 · 미국 기준일 · 기초지수별 ticker·수익률 |
| 보유 | `holdings_selected_count` · `holdings_base_trading_day` · `runtime_price_refresh.target_tickers`(보유 집합) · `content_unchanged` · 15:40 요약 문자열 | 선정 종목·상태·값 · 현재가 · 기준 종가 · 비선정 종목 값 |
| 장중 | `risk_*_count` · `intraday_*_count` · `intraday_dropped_by_cap` · `intraday_daily_cap_reached` · `intraday_tally_outcome` · `risk_data_unavailable_tickers` | 신호 종목·상태·등락률 · 잘린 신호 · 억제 신호 · 틱 시점 현재가 |

종목 단위 값은 프로세스 메모리와 최신값만 덮어쓰는 상태 파일(`*_state_latest.json`)에만 있다.

**계약 경계 — OCI `git reflog` pull 시각(실측)**

| kind | 계약 | OCI 반영 | 이력 행 표지(키 존재) | 첫 적용 |
|---|---|---|---|---|
| 시장 | OLD(KOSPI 1·3개월 문장 경로) | — | `availability` 비어 있지 않음 | ~09-07 발송 |
| 시장 | NEW_V1 SP500 방향 + no_change 억제 | b077641f 09-13 23:43(0b293f40 포함) | `calendar`/`outlook_state` · `content_unchanged` 없음 | 09-14 08:00 cron 은 flag off 로 skip · cron 첫 발송 09-15 |
| 시장 | NEW_V2 내용이 같아도 매일 발송 | 0a206b07 09-18 23:43 · 3b0bee0d 23:58 | `content_unchanged` 있음 | 09-21 |
| 보유 | H0 전량 나열 | — | `holdings_selected_count` 없음 | ~09-04 |
| 보유 | H1 선정 + no_change 미발송 | 703eb56f 09-06 13:29 | 선정 수 있음 · `content_unchanged` 없음 | 09-07 |
| 보유 | H2 변화 없어도 발송 | 0a206b07 · 3b0bee0d 09-18 | `content_unchanged` 있음 | 09-21 |
| 보유 | +15:40 장중 요약 줄 | b79d1468 09-21 21:48 · 1869aba7 09-22 00:30 | `intraday_checkup_summary(_omitted)` | 09-22 CLOSE |
| 장중 | R1 [보유 급락 알림] · 조정종가 역산 분모 | 5d2614d6 09-08 00:13 | `intraday_policy_enabled` 없음 | 09-09 |
| 장중 | R2 [장중 급등락] 통합 · 무조정 등락률 분모 | b79d1468 ~ 032a2e93 09-22 00:32 · 정책 활성 09-21 23:48 | `intraday_policy_enabled=true` | 09-22 |

현행 계약(NEW_V2 · H2 · R2)의 실제 발송은 아직 적다(OCI 실측):
- 시장: NEW_V2 발송 3건(09-21 · 22 · 23). 신호 규칙(SP500 방향)이 같은 신 경로 전체로는 발송 7건이다.
  - 나머지 4건: NEW_V1 cron 발송 3건(09-15 · 17 · 18) + 09-14 21:54 KST 수동 send 1건(cron 밖 · Q11 `off_schedule`).
  - 설계 §2 의 '09-15 첫 발송'은 cron 기준으로 맞다. 09-14 08:00 cron 실행은 `push_kind_disabled` 로 skip 됐다.
- 보유 H2: 발송 4건(09-21 OPEN·MIDDAY·CLOSE · 09-22 CLOSE). 나머지는 `no_selection`
- 장중 R2: 발송 8건(09-22·23 각 4건 · 두 날 모두 일일 상한 도달)

### 1-4. sent · suppressed · no-signal · daily-cap 기록 위치 (항목 4)

| 결과 | 어디에 | 비고 |
|---|---|---|
| sent | DB `status=sent` · JSONL · 등록부 행 · 상태 파일 | |
| failed(운영 3종 경로 14종) | DB·JSONL `status=failed` + `reason` · `error` | `param_load_error` · `slot_id_required` · `slot_id_invalid` · `holdings_selection_error` · `holdings_risk_error` · `forbidden_wording` · `telegram_send_error` 등 · 이력에는 구 코드 `missing_latest_param`(dry-run)도 있음 |
| partial | JSONL `partial_delivery=true` · DB 는 `error` 문자열(`partial_delivery_at_chunk_N_of_M`)뿐 | 기록상 `failed` · 등록부 없음 |
| skipped | DB·JSONL `reason` | 공통 `push_kind_disabled` · `duplicate_runtime` · 보유 `no_selection` · 장중 `no_new_or_worsened` · `intraday_daily_cap_reached` · 시장 캘린더 사유 · `no_publishable_content` · `non_trading_day` |
| 억제(지속 신호) | 사업군 억제 **개수**(본문이 만들어진 회차만) · 보유 급락 억제 개수 | 억제된 종목·상태 없음 · 보유 급등 억제 수 없음 |
| 구역 상한에 잘림 | 개수 `intraday_dropped_by_cap` 하나 | 잘린 종목·상태는 메모리에만 |
| 일일 상한 회차 | `intraday_daily_cap_reached` · `intraday_sent_today` | 사업군 개수 진단 없음 |
| 신호 없음 | `no_new_or_worsened` · 집계 `intraday_tally_outcome=no_signal` | 신호 없음과 지속 억제를 구분하지 않음 |
| dry-run | 같은 DB·JSONL 에 `mode=dry-run` 으로 섞임 | 수동 send 와 cron send 를 가르는 필드 없음 |

보존 방식: DB 와 JSONL 은 append 만 하고 지우는 코드가 없다. 상태 파일 5종은 최신값 덮어쓰기다. 로그 회전 설정은 없다(문서).

### 1-5. 기존 history 의 기간 · 건수 · 정확한 연결 가능 비율 (항목 5)

| 단위 | 연결 가능 | 근거 |
|---|---|---|
| 실행(evaluation_run) | DB 첫 행(07-09 15:30 KST) 이후 577/577 = 100%(`(push_kind, started_at)` 정확 일치) · 그 이전 JSONL 58행은 DB 대응 없음(날짜 범위 미측정) | OCI 실측 |
| 발송(delivery) | 07-09 이후 실제 발송 행 100% ↔ 등록부(`duplicate_key`) | OCI 실측 |
| 본문 | 0% — 본문·hash·message_id 없음 | 코드 |
| 종목 신호(signal_item) | 0% — 이력에 종목 단위 없음 · 상태 파일은 덮어쓰기 | 코드 · OCI 파일 구조 |
| 시장 방향 | 신 경로 12행(dry 1 · sent 7 · skipped 4) 중 send 모드에서 `outlook_state` 가 있는 행은 9행이다(sent 7 · skipped 2: 09-14 08:00 flag off · 09-16 no_change). 나머지 skipped 2행은 비거래일이라 `calendar` 만 있다(`flow.py:270-276`). 9행 중 cron 시각 행은 8행(09-14 21:54 수동 send 제외) · 미국 입력값은 없음 | OCI 실측 |

`started_at` 대응은 같은 실행이 DB 와 JSONL 에 같은 문자열을 쓴 것이다. 따라서 사후 추정이 아니다. 다만 설계 §3 이 "시각만으로 연결하지 않는다"고 했으므로, 이 대응을 legacy 실행 연결에 써도 되는지 확인을 받았다 → 확정(Q1): 과거 실행 단위 연결 허용.

### 1-6. 1·5·20일 outcome 에 쓸 가격 source (항목 6)

OCI `market_data.sqlite` 실측(값은 출력하지 않고 건수·기간만):

| 테이블 | 내용 | 기간·범위 | 비고 |
|---|---|---|---|
| `krx_etf_daily_price_unadjusted` | KRX Open API 무조정 **종가만** · 전 ETF | 08-13~09-22 28거래일 · 캘린더 대비 결측 0 · **07:20 기준 FDR 보다 1거래일 늦게 적재**(09-25 배치 KRX 09-22 대 FDR 09-23 · 09-23 시장 기록 api_basis_date 09-21) | docstring 이 용도를 '기초지수 계산'으로 제한(`krx_store.py:16-17`) — outcome 사용은 확장 승인 필요 · 기준일은 '응답이 있는 가장 최근 날짜'(`krx_sync.py:99-120`) |
| `etf_daily_price` | FDR OHLCV(문서상 배당조정 계열) | 09-01 이후 FDR 41종 · 고가 결측 0 | OCI 갱신 대상은 **seed ∪ 현재 보유**뿐 |
| `market_benchmark_daily_price` | 종가만 · KOSPI · US500 · IXIC · ^SOX · VIX | KOSPI 는 **09-17 에서 멈춤** · 미국 3종·VIX 09-24 | KOSPI 는 FDR KS11(GitHub 캐시) |

대상별 가격 커버리지(OCI 실측 · 건수만):

| 대상 | 수 | OHLC(`etf_daily_price`) | KRX 무조정 종가 |
|---|---|---|---|
| 보유 | 29 | 29 | 26(나머지 3종은 PC 대조상 비ETF 로 추정) |
| 사업군 대표 | 27 | 4 | 27 |
| 사업군 대체 | 22 | 0 | 22 |
| KODEX200 069500 | — | FDR OHLC · 08-03 이후 시가 결측 0 | 28행 |

- 새 외부 API 없이 종가 기준 1·5·20거래일 수익률을 계산할 수 있는 범위: ETF(보유·대표·대체) 전 대상과, 비ETF 보유의 보유 기간.
  매도한 비ETF 는 다음 배치부터 갱신이 멈춘다(`UNTRACKED_AFTER_EXIT`). 설계 §12 '신규 외부 API' 에 해당하지 않는다.
- 최대 유리·불리 움직임을 고가·저가로 재는 것은 OHLC 가 있는 종목(보유·seed)만 가능하다. 사업군 대표 23/27 은 종가 경로로만 잴 수 있다.
- **제약**
  - KRX 무조정 계열은 하루치만 적재해 빠진 날을 스스로 메우지 못한다(`krx_sync.py:99-120`).
  - 07:20 배치는 FDR 한 종목만 실패해도 benchmark·KRX 적재를 건너뛴다(`run_oci_market_data_batch.py:143-146`). 로그의 09-09~09-25 완료 기록은 모두 `status=success` 였다.
  - 상장폐지·거래정지 필드는 없다. 추정 근거는 KRX 스냅샷에서 종목이 빠진 것과 OHLC 의 volume=0 뿐이다.
    KRX 계열은 거래량을 저장하지 않아(연구 원응답 2026 거래량 0 행 1,073건이 모두 종가를 가짐) 거래정지 종목이 종가가 이어지는 결과로 섞일 수 있다(Q18).
  - KRX 무조정 종가는 분배락일에 계단식으로 떨어진다. 069500 등은 분기(1·4·7·10월 말) 분배라 PRIMARY 첫 20거래일 창이 10월 말에 걸린다(Q15).
  - PC 시장 DB 는 OCI 복제본이 아니다. PC refresh 는 과거 120일을 다시 받아 덮어쓴다. 그래서 outcome 은 OCI 가격으로 계산하고 평가 가격을 outcome 행에 고정해야 재현된다.

### 1-7. 시장 브리핑의 정확한 예측 대상 (항목 7)

- **방향 필드**: `Outlook.state` 하나다. 값은 UP/DOWN/FLAT/NONE 이다(`app/market_briefing/evidence.py:56-80`).
  - 산식: `market_benchmark_daily_price` US500 의 마지막 두 행 종가 수익률 부호. 정확히 0 이면 FLAT, 입력이 stale 이면 NONE 이다.
  - 중립 구간은 없다.
- **신선도 검사**: `last_d < today_kst` 한 줄뿐이다(`runner_market_briefing.py:57`). 경과 상한이 없고, 07:20 배치 성공 여부도 보지 않는다.
- **문구**(`render.py:36-47`):
  - UP · DOWN: '직전 미국 거래일 S&P500 상승(하락)은 오늘 한국 개장에 상승(하락) 압력으로 해석됩니다.'
  - FLAT: 방향을 주장하지 않는다.
  - NONE: 방향 문장이 없다.
  - 한국 쪽 대상(KOSPI·KODEX200·시가/종가)과 기간은 문장에도 코드에도 없다.
- **검증 근거(문서)**: 이 규칙을 ADOPT 한 02B-1 Gate 의 target 은 `069500 KRX 무조정 시가 / 직전 거래일 무조정 종가 − 1`(개장 갭)이다.
  - 근거 문서: `docs/ai_result/POC3/POC3-OPS-02B-1_MARKET_INPUT_READINESS_GATE_RESULT.md` :89-97(target 산식) · :14-28(ADOPT 판정)
  - 같은 결과서 §3.1(:96-97)은 배당조정 계열이 배당락일의 갭을 지운다는 이유로 `etf_daily_price` 를 이 target 에서 뺐다.
  - 운영 DB 의 KRX 계열에는 시가가 없다(종가만 저장). 다만 069500 은 OCI `etf_daily_price` 에 FDR 시가·종가가 있다.
- **결론**: 코드만 보면 '방향 압력 정보'다. 채점 대상은 코드가 정하지 않는다 → 확정(Q13 (d)): 방향 적중률 없음.
- **'오늘 볼 기초지수'**: 단순 나열이 아니라 규칙 스크리닝이다.
  - 규칙: 주식·일반·비합성 ETF 를 (지수산출기관+기초지수명)으로 묶는다. n≥2 이고 5일·20일 중앙값이 모두 양수인 그룹 중 20일 기준 상위 2개를 고른다.
  - 본문은 '추천' 어휘를 쓰지 않는다. 기록에는 식별자만 남고 ticker·수익률은 남지 않는다.
  - 설계 §4.2 대로 원시 성과만 기록하고 추천 적중률로 부르지 않는다.
- **운영 관찰(§5-1)**: 09-17 이후 신 경로 발송 5건은 모두 `index_status=CSV_REFRESH_REQUIRED` · 후보 0개 · 본문 127자다.
  이때 코드상 본문은 '기초지수 정보는 공식 기준정보 갱신이 필요해 제외했습니다.'(`render.py:52`)를 쓴다.

### 1-8. 보유 브리핑에서 예측으로 볼 수 있는 필드 (항목 8)

- 현행 본문은 `holdings_selection_flow` 만으로 만든다. 옛 evidence 경로와 `message_holdings_briefing.py` 는 운영 러너가 부르지 않는다.
- **명시적 상태**: 종목별 `reasons{reason:{state,value}}` 하나다(`holdings_selection.py:41-57`).
  - `RECENT_DECLINE` 3구간: D5_8(−8<r≤−5) · D8_10(−10<r≤−8) · D10_PLUS(r≤−10). r = 현재가 ÷ 20거래일 전 종가 − 1 이고 소수 1자리로 반올림한다.
  - `DATA_UNAVAILABLE_OR_STALE/ACTIVE`: 시세 없음 · 시세 날짜 불일치 · 기준 종가 없음, 세 원인을 합친 상태다. 하위 원인 필드는 없다.
- **예측 필드**: 방향·목표·기간 필드는 없다. RECENT_DECLINE 은 지나간 하락을 설명하는 상태다. 그래서 적중률 대상이 아니라 '상태별 원시 성과' 대상이다.
- **대조군**: 선정기는 전 보유 종목의 20일 수익률을 계산한 뒤, 구간 밖이면 버린다(`:325-328`). 이 동작은 테스트(`test_t1`)로 고정돼 있다.
  - 비선정 종목의 판정 당시 값은 어디에도 남지 않고, 현재가도 저장되지 않아 사후 재계산이 불가능하다.
  - 대조군을 두려면 실행 중에 캡처해야 한다(Q8).
- **해소(resolved)**: 회복 · 데이터 복구 · 매도(보유 제외)를 구분하지 않는다(`holdings_selection_state.py:143-147`).
- **15:40 요약 줄**: 장중 회차 집계 파일의 틱 outcome 개수만 세어 만든 운영 집계다(`holdings_selection_flow.py:217-236`). ticker·가격·방향이 없어 투자 신호가 아니다.
- **반복 노출**: 2026-09-18 계약부터 변화가 없어도 슬롯마다 전체 상태를 보낸다. 같은 종목·상태가 하루 3회, 여러 날 반복 노출된다 → 표본 단위를 먼저 정해야 한다(Q19).

### 1-9. 장중 상태별 outcome 정의 가능성 (항목 9)

- **상태 코드**:
  - 보유 급락: D5_7 · D7_10 · D10_PLUS(`holdings_risk.py:36-53`)
  - 보유 급등: U5_7 · U7_10 · U10_PLUS(`:63-71`)
  - 사업군: ENTRY_REVIEW · AVOID_DROP · AVOID_CHASE(`sector_signal.py:42-50`). 라벨은 AVOID_CHASE='단기 급등 · 추격 주의'다.
  - 설계 §4.4 의 **AVOID_SURGE 는 코드·테스트·문서에 0건**이다(Q4).
- **판정 입력**: Naver `fluctuationsRatio`(무조정 D-1 대비 등락률)를 소수 1자리로 반올림한 값이다. 사업군 5·20일 수익률은 KRX 무조정 종가의 마지막 N+1 행으로 계산한다.
  - 보유 급등락 경계(±5/7/10)는 코드 상수다.
  - 승인 번들의 `surge_threshold_pct`·`drop_threshold_pct` 는 판정 코드가 읽지 않는다.
- **발송 제한**: 회차당 1건 · 조건형 일일 4건 · 메시지당 9종목(구역 3×3).
- **식별 가능성(신규)**:
  - 한 틱 안에서 종목은 최대 1개 상태를 가진다. 그래서 `(날짜, 틱 HH:MM, ticker, state)` 가 틱 안에서 유일하다.
  - 사업군은 `sector_key`(토큰 사전 키 · 두 config 버전에서 27개 모두 같음)로 안정적이다.
  - 대표가 조회에 실패하면 대체 ticker 로 바뀐다.
- **outcome 정의**: 가능하다. 다만 틱 시점 현재가 · 가격 시각 · 원시 등락률 · 잘린 신호 · 억제 신호는 지금 저장되지 않아 POC5-01 부터 새로 기록해야 한다.
- **현행 동작 관찰(§5)**
  - 정책이 켜진 상태에서 구역 상한에 잘린 보유 급락도 발송 성공 뒤 `worst_state` 가 기록된다. 그래서 그날 같은 구간이 억제된다(`holdings_risk_flow.py:134` · `runner_evidence.py:241-250`).
  - 집계 파일의 outcome 은 조립 시점 잠정값이라, Telegram 실패 때 `no_signal`·`suppressed` 로 남을 수 있다.

### 1-10. PC · OCI DB 위치와 신규 테이블 필요 여부 (항목 10)

- **OCI**:
  - `state/runtime/runtime_state.sqlite`(438 KB · 8테이블): PARAM 3 · 실행 기록 · 발송 등록부 · 장중 config 3
  - `state/market/market_data.sqlite`
  - `state/decision/` 은 없다.
  - 루트의 `state/runtime_state.sqlite` 는 빈 파일(0 B · 07-26)이다. 코드 기본 경로는 `state/runtime/` 아래다(`runtime_state_db.py:27`).
  - 디스크 여유는 40 GB 다.
- **PC**:
  - `runtime_state.sqlite` · `decision_evidence.sqlite`(1테이블 0행) · `market_data.sqlite`
  - 원장·신호·outcome·feedback 테이블은 양쪽 어디에도 없다 → **신규 테이블이 필요하다**.
- **저장소 규칙**(PROJECT_ORIGIN_INTENT §10-2):
  - 신규 대형 DB 금지 · 활성 데이터는 DB.
  - JSON 은 로그·archive·API·fixture 만.
  - PC 는 OCI 운영 DB 를 원격으로 열거나 쓰지 않는다 · SQLite 파일 통째 덮어쓰기 금지.
  - → 원장 정본은 DB 여야 한다. JSONL 은 정본이 될 수 없다.
- **선례**:
  - 02C-OPS-01 은 '신규 DB 파일 금지 · runtime_state.sqlite 재사용'으로 테이블 3개를 추가했다.
  - 기존 5테이블은 'schema 변경 금지' 주석이 있다(`runtime_state_db.py:31`).
  - `init_db` 가 `CREATE TABLE IF NOT EXISTS` 를 돌리므로, OCI pull 뒤 첫 실행에서 스키마가 자동으로 바뀐다 → **DB 스키마 변경 = 사용자 승인 사항**.
- **OCI→PC 전달**:
  - 저장소의 scp 는 전부 PC→OCI 다. OCI→PC 읽기는 다음뿐이다:
    PC 기동 시 1회 상태 읽기(`oci_startup_status` · 재조회 금지 계약) · POC1 outbox 요청별 SSH cat(`delivery.fetch_outbox_result`) ·
    holdings apply 뒤 원격 hash 재독출 · 장중 설정 동기화의 OCI active 조회(`sync_intraday_config._remote_active` · OCI 측 python 을 SSH 로 실행).
  - 원장 행을 가져오는 경로는 새로 만들어야 한다(Q21).
- **PC DB 오염**: PC `runtime_state.sqlite` 에 `holdings_risk_alert` send 12행(2026-09-21 21:09~21:35 KST · sent 9)과 등록부 9행이 있다.
  - 운영 시각이 아니고, 같은 초에 만든 param_id 를 쓴다 → 가드 도입(09-24) 이전 테스트·검증 흔적으로 추정한다.
  - 원장 source 는 **OCI 만**으로 한다.
- **이름 충돌**:
  - 'Decision Outcome Ledger' 는 코드 0건이고 문서에만 있다(POC3-00 지도 P-19 · MASTER_PLAN 5번 · '사용자 판단 원장' · 선행 gate 'First Real Decision Cycle PASS').
  - 제출 때는 'POC5 는 발송 신호 원장이라 대상이 다르다'로 봤다 → 확정(Q27): POC5 가 기존 미결 항목을 이어받아 완성 · 중복 원장 없음(§2-9).
  - 'outcome' 은 이미 장중 회차 결과(sent/suppressed/no_signal/failed) 이름으로 쓰인다 → 원장에서는 `price_outcome` 처럼 구분한다.

### 1-11. 피드백 카드를 놓을 위치 (항목 11)

- **최근 받은 메시지 화면**: PC 메뉴 13개 중 OCI 가 실제 발송한 메시지를 보여 주는 화면은 0개이고, 발송 이력 API 도 0개다.
- **가장 가까운 화면**: 「진단·상태 > OCI 운영 상태」다.
  - PC 기동 시 1회 읽은 스냅샷이다. 개별 PUSH 결과는 코드에서 UNKNOWN 으로 고정돼 있다.
  - 새로고침·폴링 금지 계약이 있다(설계자 Q2).
- **본문 표시 한계**: 과거 메시지는 본문이 없어 종류·시각·상태만 보여 줄 수 있다.
- **Telegram callback**: 필요 없다. 발송 payload 는 `chat_id·text·parse_mode` 뿐이고, callback 코드는 0건이다. PC 화면에서 받으면 Telegram·러너 변경이 0이다.
- **후보(메뉴 이름 기준 · 줄 수는 KS-10 여유)**
  1. 「오늘 확인 > 오늘의 투자 점검」에 새 구역
     - 본체 141줄이고, 새 컴포넌트 파일로 붙인다.
     - 매일 처음 보는 화면이라 입력률이 가장 높다.
     - 대신 POC3-01 첫 화면 구역 계약이 바뀐다.
  2. 「진단·상태 > OCI 운영 상태」 확장
     - 84줄이다.
     - 기동 시 1회 · 새로고침 금지 계약과 충돌하고, 방문 빈도가 낮다.
  3. 새 메뉴
     - 메뉴 수 13→14 불변식·테스트를 바꿔야 한다.
     - 이름은 사용자·설계자가 정한다.
  - 제외: 「보유·자료 관리 > 확인 근거」(읽기 전용 계약) · 「승인·적용」(정보 PUSH 카드 금지 확정)
- **저장 패턴**:
  - PC SQLite + 별도 `APIRouter`(예: 'AI 투자 세션' `decision_evidence`)를 따른다.
  - 테스트는 store 와 router 양쪽 `DEFAULT_DB_PATH` 를 tmp 로 바꾼다.
  - JSON 파일 저장은 저장소 규칙상 불가하다.

### 1-12. PC 미가동 중 outcome 을 만드는 방법 (항목 12)

- 가격 테이블은 행을 지우지 않는다(`DELETE` 0건). 그래서 OCI 에 입력이 계속 남는다.
- 메시지 발송과 무관하게 매일 도는 기존 실행 지점은 07:20 배치 하나다.
- **(a) 07:20 배치 뒤 독립 단계**:
  - 배치 `run()` 이 끝난 뒤, 성숙한 이벤트의 outcome 을 원장 테이블에 쓴다.
  - 배치 status·상태 파일·가격 테이블에 영향을 주지 않도록 예외를 격리한다.
  - 신규 cron 은 없다. OCI 코드 배포는 필요하다(Q2 · Q25).
- **(b) PC 지연 계산**:
  - OCI 는 이벤트만 기록하고, PC 가 켜질 때 계산한다.
  - PC 시장 DB 는 OCI 와 달라 OCI 가격을 함께 가져와야 한다 → 전달량과 재현성이 불리하다.
- **(c) 신규 cron**: 설계 §12 중단 조건이다.
- (a) 를 제안한다. 성숙 판정은 '평가일 가격 행이 실제로 적재된 뒤'로 정의한다(날짜 추정 없음).
  - 07:20 시점에 FDR(`etf_daily_price`)은 직전 거래일까지 있다 → +N 거래일은 그다음 날 아침에 성숙한다.
  - KRX 무조정 계열은 FDR 보다 1거래일 늦게 적재된 것이 관측됐다(§1-6) → 그 날짜 적재가 확인된 뒤 아침에 성숙한다.
    관측은 연휴 구간 한 번이라 지연이 상시인지는 확인하지 않았다.

### 1-13. 계약 동결 시각과 PRIMARY_LIVE_COHORT 시작일 (항목 13)

- OCI 배포는 수동 `git pull` 이다(reflog 전부 pull). push 만으로는 OCI 가 새 코드를 돌리지 않는다.
- **거래일 캘린더**:
  - `state/market_meta/krx_trading_days_2026.csv` 는 PC 와 OCI 가 같다(sha256 `3e751786…`).
  - 243거래일 중 09-11 까지 171일은 KRX 실측이고, 09-14 부터 72일은 `USER_CONFIRMED` 다.
  - 2027 파일은 없다.
  - 다음 거래일은 09-29 다. +20 거래일이 2026 캘린더 안에 드는 마지막 신호일은 12-01 이다.
- **제출 때 제안**: PRIMARY 시작일 = ① 설계자의 채점 계약 동결 ② OCI 에 POC5-01 코드 pull 확인(reflog 인용) — 둘 다 된 뒤 첫 KRX 거래일.
  → **확정(Q28)**: 운영 계약 정정(§3-1) · 코드 pull 뒤 첫 거래일(§2-7).
  - 동결 전·배포 전 이벤트는 LEGACY_DIAGNOSTIC 이다.
  - 동결일과 배포일은 원장 메타에 기록한다.

### 1-14. 최초 리뷰에 필요한 표본 수 · 거래일 제안 (항목 14)

- **발생률**(현행 계약 · OCI 실측 · 거래일당):
  - 시장: 1회(→ 확정: 방향 채점 없음 · FLAT/NONE 은 태그 · Q13 (d) · Q14)
  - 보유: 선정 0건이면 미발송 — 최근 3거래일 중 발송 4건
  - 장중: 조건형 최대 4건(09-22·23 모두 상한 도달)
- **제출 때 제안**(→ **확정은 Q28 · Q29**: 10거래일 뒤 R0 · R1 정기 기술통계 · 날짜 블록 bootstrap · 성공 임계 없음 · §2-7):
  1. **R0 수집 점검**
     - PRIMARY 10거래일 뒤 한다.
     - 연결률 100% · PENDING/PRICE_MISSING 비율 · 현행 PUSH 회귀 0 · 스냅샷 불변만 본다.
     - 신호 효과 결론은 내지 않는다.
  2. **R1 첫 효과 리뷰** — kind 별로 표본 기준을 따로 둔다. 미달이면 `INSUFFICIENT_SAMPLE` 로 보고한다.
     - 기준 근거: 비율 지표의 95% 구간 반폭 ≤ ±15%p → p=0.5 에서 n ≥ 43 (1.96·√(0.25/43) ≈ 0.149).
     - **시장**: 방향 적중률(Q13 대상)에 적용한다. UP/DOWN 이벤트 43건이 필요하다. 거래일당 1회이고 FLAT/NONE 비율은
       아직 모르므로, 최소 43거래일 + 1일 성숙이 걸린다.
     - **보유·장중**: 방향 적중률이 없다(§2-6). 원시 성과를 요약하는 비율 지표(예: 양수 수익 비율)를 쓸 때만 같은 n ≥ 43 을 적용한다.
       중앙값 같은 요약은 표본 수만 보고한다. 관측 발생률로 추정하면 다음과 같다.
       - 장중: 조건형 발송이 거래일당 최대 4건(09-22·23 모두 상한 도달)이다. 전 상태 합계 43건은 약 11거래일이지만, 상태별로는 더 길다.
       - 보유: 3거래일에 발송 4건이고 선정 0건인 날이 많다. 상태 진입 이벤트가 드물어 수개월이 걸릴 수 있다.
     - **겹치는 horizon**: 5·20일은 표본 구간이 겹친다. 비중첩 블록으로 43개를 세면 20일은 약 860거래일이 필요해 현실적이지 않다.
       그래서 두 안을 올린다. (i) 날짜 단위 블록 bootstrap 으로 CI 를 내고 n 은 이벤트 수로 센다.
       (ii) R1 에서는 1일만 판정 대상으로 하고, 5·20일은 기술 통계로만 낸다. 설계자가 정한다(Q28).
  - 성공 임계(무엇을 '좋은 신호'로 볼지)는 이 표본 기준과 별개로 Q29 에서 결과 전에 정한다.
- 설계자 판정: "기다림은 성과 판정에만 필요" → R0·R1 을 기다리는 동안 POC5-02~03 과 다른 작업은 계속한다.

### 1-15. KS-10 · 라이브 경계 · 외부 호출 위험 (항목 15)

- **KS-10 실측**(`git ls-files '*.py' '*.ts' '*.tsx'` · 528개 · 2026-09-26):
  - TRIGGER 0
  - NEAR 7: 러너 `scripts/run_three_push_runtime_oci.py` 646 · `app/api.py` 641 · `scripts/ops02c/reverse_verify_guards.py` 638 · `app/ml_score_validity_report.py` 626 · `app/holdings_market_evidence.py` 616 · `app/draft.py` 602 · `frontend/app/components/JudgmentWorkbenchView.tsx` 855
  - 러너는 650까지 4줄 남았다. 원장 책임을 러너에 더하면 트리거 5('같은 대형 파일에 신규 책임')에 해당한다 → **POC5-01 앞에 러너 기계 분리(Cleanup)가 필요하다**(Q6).
  - `app/api.py` 는 라우터 include 2줄만 늘린다.
- **라이브 가드**:
  - `tests/_live_guard.py` 는 경로 루트(state/·logs/) 기반이다. 새 테이블·새 파일도 자동으로 막는다.
  - 새 DB 파일을 쓰면 기존 러너 테스트가 fail-loud 로 막히므로, autouse 격리 fixture 를 추가해야 한다.
  - 기존 `runtime_state.sqlite` 에 테이블을 두면 기존 fixture(`_isolated_runtime_state_db`)가 그대로 격리한다.
- **Telegram**:
  - 테스트 전역 차단이 없고, 테스트 파일 16개가 각자 stub 한다. PC `.env` 에 토큰 키가 있다.
  - POC5 테스트는 `telegram_send` stub 과 '실발송 0' 단언을 기본 fixture 로 둔다.
- **외부 호출**: 시장 브리핑을 KRX 무조정 시가 갭으로 채점하거나 사업군 대표의 고가·저가를 쓰려면 적재 스키마나 대상 확장이 필요하다(신규 API 는 아니지만 운영 배치 변경) → Q13·Q15.

---

## 2. 확정 계약 (설계자 PLAN 판정 2026-09-26 · 사용자 승인 2026-09-26)

아래는 설계자 판정(설계서 끝 `# 설계자 PLAN 판정` · §4 표)을 개발 계약으로 옮긴 것이다. 판정 원문과 다른 곳이 있으면 원문이 우선한다.
세부 구현(파일 · 함수 · 테스트 목록)은 단계마다 짧은 PLAN 에서 정한다(Q26).

### 2-1. 목적 · 원칙

```text
POC5_PURPOSE              = 운영 신호 · 원시 결과 · 사용자 피드백 축적 (ML 재개 아님 · 성공/실패 label 없음)
OUTCOME_POLICY            = RAW_ONLY
MARKET_DIRECTION_ACCURACY = NOT_DEFINED
PRIMARY_T0                = RUNTIME_QUOTE_USED_IN_MESSAGE
LEGACY_ITEM_LINKAGE       = UNLINKABLE_LEGACY
RUNTIME_STATE_DB_CHANGE   = 0
```

- 기존 메시지 · 시간 · 임계값은 바꾸지 않는다(설계자 핵심 확정 1).
- 기다림은 성과 해석에만 필요하다. 개발을 막지 않는다.

### 2-2. 저장소 (Q5 · Q9 · Q22 · 사용자 승인)

- **OCI**: 전용 원장 `state/decision/decision_evidence.sqlite` 를 새로 만든다.
  - `runtime_state.sqlite` 와 분리한다.
  - 짧은 트랜잭션 · WAL · busy timeout 을 적용한다.
  - OCI 에는 지금 `state/decision/` 이 없다(§1-10).
- **PC**: 이미 있는 `state/decision/decision_evidence.sqlite` 에 원장 사본 · 피드백 테이블을 추가한다. 새 PC DB 는 만들지 않는다.
- **사용자 승인(2026-09-26)**: OCI 전용 SQLite 생성 · PC 기존 파일 테이블 추가.
- 분할 전 전문과 SHA-256 을 모두 보존한다. 파일 권한과 DB 접근은 로컬 사용자로 한정한다(Q9).
- OCI 원장과 PC 사본이 같은 상대 경로를 쓴다. 그래서 PC 에서 러너가 실행돼도 원장에 쓰지 않게 하는 장치가 필요하다(개발자 안 · OCI 전용 쓰기 가드 등).
  PC 사본 테이블은 POC5-03 동기화로만 채운다. 방식은 POC5-01 PLAN 에서 정한다. 근거: PC `runtime_state.sqlite` 의 출처 불명 12행이 PC 쪽 send 실행 흔적이었다(§1-10).
- 참고 사실(구현 PLAN 입력):
  - `.gitignore` 263~266행이 `state/decision/decision_evidence.sqlite` 와 `-journal` · `-wal` · `-shm` 을 이미 무시한다.
  - PC `app/decision_evidence_store.py` 는 경로(`DEFAULT_DB_PATH`, 31행)를 함수 정의 시점 기본값으로 묶는다.
    그래서 원장·피드백 테스트의 경로 격리 방식은 POC5-03 PLAN 에서 정한다.

### 2-3. 원장 테이블 (설계 §3 다섯 개념)

```text
evaluation_run   event_id(PK · 실행 진입 때 발급) · run_state(STARTED → 종료 상태 · 종료 미확정 = gap)
                 · push_kind(운영 3종만) · contract_version · slot/tick · runtime_kst · runtime_date_kst · input_basis_date
                 · mode(send 만) · status · reason · started_at · run_id(보조) · param_id · config_version_id
                 · off_schedule · cohort(LEGACY_DIAGNOSTIC / PRIMARY_LIVE) · tags(시장 Q14)
signal_item      event_id · item_seq · subject(ticker / sector_key / market / 기초지수 그룹) · held · state · prev_state
                 · disposition(sent / suppressed / cut_by_section_cap / cut_by_daily_cap / not_selected / data_unavailable)
                 · event_type(new_entry / worsened / reentry_after_recovery / repeat_exposure) · exposure(PRIMARY / SECONDARY)
                 · 당시 수치(kind 별) · t0(장중 · 보유 신호 = 메시지 생성에 실제 사용한 현재가 · 가격 시각 · 시장 항목 기준은 §2-6 · POC5-02 PLAN)
delivery         event_id · delivery_status(sent / skipped / failed / partial) · telegram_sent · chunk_count
                 · body_text(분할 전 전문) · body_sha256
price_outcome    event_id · item_seq · horizon(1 / 5 / 20) · t0 · 보조 기준(신호일 종가 · 전일 종가) · eval_date · eval_price
                 · price_basis(source) · distribution_in_window · return · max_up / max_down(종가 경로)
                 · status(MATURED / PRICE_MISSING / UNTRACKED_AFTER_EXIT / T0_MISSING 등) · computed_at · source_collected_at
user_feedback    (PC 전용) event_id · feedback_seq · helpfulness(도움됨 / 보통 / 불필요·혼란) · action(선택) · memo(선택) · feedback_at
```

- run · signal_item · delivery 는 이벤트 당시 **INSERT 만** 한다. 미래 결과가 당시 스냅샷을 바꾸지 않는다(설계 §11 · 테스트로 고정).
- run 은 예외적으로 '종료 상태 확정'을 1회 기록한다(초기 행 STARTED → 최외곽에서 종료 상태 · Q6). 방식(같은 행 1회 갱신 또는 종료 행 추가)은 POC5-01 PLAN 에서 정한다.
- outcome 은 결과가 확정될 때 1회 INSERT 한다(개발자 안 · POC5-02 PLAN 에서 확정). 성숙 전은 행이 없는 상태이고, 조회 때 `PENDING` 으로 표시한다.
- 'outcome' 이름이 장중 회차 결과와 겹치므로 가격 결과는 `price_outcome` 으로 부른다(§1-10).
- 테이블 · 컬럼 이름은 단계 PLAN 에서 확정한다.

### 2-4. 실행 추적 · 누락 gap (Q6 · Q7 · Q8 · Q10 · Q11)

- **순서**: POC5-01a 에서 러너를 먼저 기계 분리한다(동작 · 문구 · 순서 불변 · KS-10).
- **실행 진입**: `event_id` 를 발급하고 원장에 초기 행(STARTED)을 쓴다. `run_id` · `started_at` 은 보조키다.
- **최외곽 종료 확정**: 실행 종료 상태를 가장 바깥에서 확정한다.
  - 발송 전후의 미포착 예외도 종료 상태로 남긴다. PUSH 동작은 바꾸지 않는다.
  - 종료가 확정되지 않은 STARTED 행은 **명시적 gap** 이다.
- **100% 모집단**: '이미 DB 에 남은 실행'이 아니라 **실행 진입 전체**다(설계자 핵심 확정 7).
- **기록 실패**: PUSH 를 막지 않는다. 대신 명시적인 오류와 대조 보고를 남긴다.
  대조 대상은 원장 run · `runtime_execution_status` · gap 행이다.
- **flow payload**: flow 반환값에 기록용 payload 를 additive 로 추가한다(Q7).
  본문 byte · 판정 · 순서 동일 테스트는 필수다.
- **비선정 결과**: 이미 계산된 보유 · 27개 사업군의 비선정 결과도 기록한다(Q8). 추가 조회 · 재계산은 금지다.
- **원장 대상**: `mode=send` 만 둔다. 수동 send 는 `off_schedule=true` 로 기록하고 PRIMARY 통계에서 뺀다(Q11).
  예: 2026-09-14 21:54 KST 시장 수동 send(§1-3).

### 2-5. 계약 버전 (Q12)

- kind 별 계약 버전을 코드 상수로 관리한다.
- legacy 버전(§1-3 경계표 · OCI reflog 실측)은 진단 전용이다.
- 구 시장 메시지(KOSPI 3개월 문장 경로)는 현행 결과와 섞지 않는다(설계 §2).

### 2-6. 가격 결과 · 집계 (Q13 ~ Q20 · Q25 · Q29)

- **계산 위치**: 07:20 배치 뒤 격리된 단계에서 성숙 결과를 계산한다(Q25).
  실패해도 배치 status · 가격 적재 · 08:00 실행에 영향이 없어야 한다. 신규 cron 은 없다(Q2).
- **가격 계열**: ETF 는 KRX 무조정 종가, 비ETF 보유는 기존 FDR 계열이다(Q15).
  - source 와 분배락 포함 여부를 반드시 기록한다.
  - KRX 무조정 계열은 FDR 보다 1거래일 늦게 적재된 것이 관측됐다(§1-6). 성숙 판정은 '평가일 가격 행이 실제로 적재된 뒤'다.
- **t0**(Q16):
  - 장중 · 보유 신호의 PRIMARY t0 는 메시지 생성에 실제 사용한 현재가다.
  - 신호일 종가와 전일 종가는 보조 비교값이다.
  - 현재가가 없으면 종가로 대체하지 않는다.
- **horizon 축**(Q17): 실제 가격 적재일 순서로 +1/+5/+20 을 센다.
  2027 CSV 는 선행조건이 아니다. 기존 snapshot 우선 · 평일 fallback 정책을 유지한다.
- **결측**(Q18):
  - 가격 대체는 금지다. `PRICE_MISSING` · `UNTRACKED_AFTER_EXIT` 등으로 기록한다.
  - 거래량 필드는 이번에 추가하지 않는다. 그래서 거래정지는 판별할 수 없다 → 한계로 기록한다.
- **최대 유리 · 불리 움직임**: 종가 경로 기준이다(KRX · benchmark 는 종가만 있다 · §1-6).
- **원시 결과만**(Q20): 상태별 '유리한 방향'과 단일 성공 라벨은 만들지 않는다.
- **시장 브리핑**(Q13 (d) · Q14):
  - 방향 적중률은 계산하지 않는다. S&P500 상태와 한국 시장 원시 결과만 나란히 둔다. 어떤 한국 시장 계열을 둘지는 POC5-02 PLAN 에서 정한다.
  - 기초지수 후보(운용사|기초지수명 그룹 · 실제 사용 ticker)는 별도로 1·5·20거래일 원시 성과를 기록하되 추천 적중률로 부르지 않는다(설계 §4.2).
    후보 ticker 는 POC5-01 flow payload 로 실행 시점에 기록한다(Q7).
  - 별도 태그: FLAT/NONE · 동일 미국 세션 · 연휴 직후 · 입력 지연.
- **집계**(Q19 · Q29):
  - 성공 임계는 없다. kind · state · contract_version · horizon 별 원시 분포를 보고한다.
  - Q19: 같은 상태의 반복 노출은 보조(SECONDARY) 기록이다. 신규 진입 · 구간 악화 · 회복 뒤 재진입이 PRIMARY 전이 이벤트다.
  - Q29: 같은 종목 · 같은 상태 · 같은 날은 첫 노출을 PRIMARY, 반복은 SECONDARY 로 둔다. 악화 · 회복 뒤 재진입은 새 사건이다.
  - 두 규칙은 **여러 날 이어지는 같은 상태**(예: 보유 RECENT_DECLINE 이 며칠 연속 노출)에서 갈린다.
    둘째 날 이후 첫 노출이 Q29 로는 PRIMARY, Q19 로는 보조다. 이 경우의 규칙은 POC5-01 PLAN 에서 설계자에게 확인한 뒤 확정한다(§2-3 exposure).
  - 잘림 · 억제는 관측 모수에는 포함하고, 전달 효과 모수에서는 뺀다.
- 운영 결과 · 과거 수익률은 계속 열지 않는다(설계자 판정). 결과는 R0 · R1 절차(§2-7 · Q28)로만 보고한다.
- legacy 진단 backfill 에 가격 결과 계산 · 열람이 들어가는지와 그 조건은 POC5-02 PLAN 에서 설계자에게 확인한다. 그 전까지 legacy 가격 결과는 계산 · 열람하지 않는다.

### 2-7. cohort · 리뷰 (Q1 · Q28 · Q30)

- **LEGACY_DIAGNOSTIC**:
  - 과거 실행 단위 연결은 허용한다(DB `run_id` · `(push_kind, started_at)` 정확 일치). 과거 종목 단위는 `UNLINKABLE_LEGACY` 다(Q1).
  - spike 는 legacy 에서도 제외하고, 운영 3종만 허용한다(Q30).
  - legacy 버전과 결과는 진단 전용이고, PRIMARY 통계에 섞지 않는다. legacy 가격 결과의 계산 · 열람 여부는 §2-6 대로 POC5-02 PLAN 에서 확인한다.
- **PRIMARY_LIVE**(Q28): PRIMARY 시작 전 운영 정정(§3-1)과 POC5-01 코드 pull 이 끝난 뒤, 첫 KRX 거래일부터다.
  시작일과 근거(OCI reflog)는 원장 메타에 기록한다.
- **R0**: PRIMARY 10거래일 뒤 수집 점검을 한다(연결 · gap · 결측 · 현행 PUSH 회귀). 신호 효과 결론은 내지 않는다.
- **R1**: 정기 기술통계다. 겹치는 날짜는 날짜 블록 bootstrap 으로 처리한다. 다음 개발을 기다리게 하지 않는다.

### 2-8. PC 동기화 · 피드백 (Q3 · Q21 ~ Q24)

- **동기화**(Q21):
  - 원장 화면을 열 때 1회 동기화하고, 수동 새로고침 버튼을 둔다. PC 전체 기동 시 자동 SSH 조회는 하지 않는다.
  - 주의: 원장 구역이 PC 첫 기본 화면(「오늘의 투자 점검」 · `MainPanel` 기본값)에 들어간다. 그래서 구역 렌더만으로 동기화하면 PC 를 켤 때마다 SSH 가 돈다.
    동기화를 무엇으로 시작할지(`신호 결과 원장` 펼침 · 버튼 등)는 POC5-03 PLAN 에서 설계자에게 확인한 뒤 확정한다.
  - 방식은 OCI 측 읽기 전용 export 를 SSH 로 실행해 행을 받는 것이다. 선례는 `sync_intraday_config._remote_active` 다. 세부는 POC5-03 PLAN 에서 정한다.
  - PC 사본 upsert 키: run · delivery = `event_id` · item = `(event_id, item_seq)` · outcome = `(event_id, item_seq, horizon)`.
- **화면**(Q23): 「오늘 확인 > 오늘의 투자 점검」 안에 새 구역 **`받은 알림 기록`** 을 두고, 상세 접기 영역은 **`신호 결과 원장`** 이다.
  메뉴는 14개로 늘리지 않는다(13 유지).
- **피드백**(Q24):
  - 대상은 `sent` 와 실제 일부가 전달된 `partial` 뿐이다.
  - append-only 로 쌓고, 미입력은 행을 만들지 않는다.
  - 가격 결과는 피드백 전에 노출하지 않는다.
- **API**(Q3): `127.0.0.1` 전용 로컬 API 로 둔다(공개 API 아님).

### 2-9. 기존 'Decision Outcome Ledger' (Q27)

- POC5 가 기존 `Decision Outcome Ledger` 미결 항목(POC3-00 지도 P-19 · `docs/MASTER_PLAN.md` 5번)을 이어받아 완성한다.
- 별도 중복 원장은 만들지 않는다.
- 기존 선행 gate 가 있다: POC3-00 지도 P-19 'First Real Decision Cycle formal PASS 와 실제 판단 1건 기록 후' · S-05 'Decision Outcome Ledger 선행 진입 금지 유지' ·
  `docs/MASTER_PLAN.md` canonical 순서 3 → 5. 개발자는 이 gate 가 Q27 로 대체됐다고 읽는다 — 해석이 맞는지 POC5-01 PLAN 에서 설계자에게 확인한다.
- 두 기존 문서의 표기 정리와 KS-11(결정 변경 근거 기록)은 POC5-01 PLAN 에서 함께 제안한다.

---

## 3. 구현 순서 · 범위 (Q26 — 단계마다 짧은 PLAN · MASTER 질문 반복 없음)

### 3-1. POC3 운영 정정 소형 PLAN (PRIMARY 시작 전 필수 · 설계자 판정)

현재 메시지 계약이 PRIMARY 중간에 바뀌면 원장 데이터가 섞인다. 그래서 아래를 먼저 정리한다. 이 단계는 POC5 가 아니라 POC3 운영 정정이다.

1. 08:00 기초지수 구역 복구 — 공식 CSV 갱신 및 정합성 검증(§5-1)
2. 폐지된 spike 를 요구하는 OCI 상태 화면 수정(§5-3 · Q30)
3. 장중 본문의 `현재가 —` 가 실제로 발생하는지 확인하고, 결함이면 수정(§5-5)
4. 상한에 잘려 발송되지 않은 보유 급락이 당일 억제되는 문제 수정(§5-6)
5. Telegram 실패가 `no_signal` 로 집계되는 문제 수정(§5-7)
6. `holdings_risk_alert.message_text_length=0` 기록 수정(§5-8)
7. KOSPI 09-17 정지 — 원인 조사 뒤 복구 또는 명시적 stale 처리(§5-2)

### 3-2. POC5 단계

| 순서 | 단계 | 범위 | 핵심 검증 |
|---|---|---|---|
| 2 | POC5-01a 러너 기계 분리 | 동작 · 문구 · 순서 불변 · KS-10 선제 | 기존 러너 테스트 전부 · 본문 byte 동일 |
| 3 | POC5-01 운영 원장 | OCI 전용 원장 DB · 실행 진입 `event_id` · 초기 행 · 최외곽 종료 확정 · gap · flow additive payload · 비선정 결과 · 계약 버전 상수 · 운영 3종 허용 목록 | 본문 byte · 판정 · 순서 동일 · 기록 실패가 PUSH 를 막지 않음 · gap · 대조 보고 · 스냅샷 불변 · spike 제외 · 실발송 0 · tmp DB |
| 4 | POC5-02 outcome 성숙 | 07:20 뒤 격리 단계 · t0 · 보조 기준 · 적재일 축 · 결측 · 분배락 표시 · 시장 · 기초지수 원시 결과 · legacy 진단 backfill(실행 단위 · 가격 결과 포함 여부는 설계자 확인) | 성숙 규칙 고정 fixture · KRX 적재 지연 · 배치 status 불변 · 현재가 누락 시 대체 없음 |
| 5 | POC5-03 PC 동기화 · 피드백 | 화면 열 때 1회 동기화(시작 계기는 설계자 확인) + 새로고침 · PC `decision_evidence.sqlite` 테이블 · 로컬 API · `받은 알림 기록` 구역 · `신호 결과 원장` 접기 | API tmp DB · vitest · 외부 호출 0 · 사용자 실화면 |
| 6 | POC5-04 R0 · R1 리포트 | R0 수집 점검 · R1 정기 기술통계(날짜 블록 bootstrap) | 원시 분포만 · 성공 판정 없음 |

모든 단계 공통: 신규 의존성 0 · 테스트의 라이브 DB · 외부 호출 · 실발송 0 · 전체 회귀 · KS-10 · `PROGRAM_TRUTH` 갱신(화면 · API · 저장소가 바뀌는 단계).

---

## 4. 설계자 확정 (2026-09-26 · Q1~Q30)

판정 원문은 설계서 끝 `# 설계자 PLAN 판정` 이다. 질문 요지는 이 PLAN 제출판의 질문을 줄인 것이다.

| Q | 질문 요지 | 확정 |
|---|---|---|
| Q1 | 기존 이벤트 연결(§3 대 §12) | 과거 실행 단위 연결 허용 · 과거 종목 단위는 `UNLINKABLE_LEGACY` |
| Q2 | §9 'OCI 배포 금지'와 POC5 배포 | 승인된 POC5 구현 · 수동 배포는 §9 금지 대상 아님 · cron 추가 금지 |
| Q3 | PC 로컬 API 가 공개 API 인가 | `127.0.0.1` 전용 API 는 공개 API 아님 |
| Q4 | AVOID_SURGE 표기 | 코드 값 `AVOID_CHASE` 정본 · 이름 변경 없음 |
| Q5 | OCI 원장 저장 위치 | OCI 전용 `state/decision/decision_evidence.sqlite` 생성 · `runtime_state.sqlite` 와 분리 · 짧은 트랜잭션 · WAL · busy timeout |
| Q6 | 러너 부착 · 누락 경로 · §11 | POC5-01a 러너 선분리 · 실행 진입 때 `event_id` · 초기 행 · 최외곽 종료 확정 · 기록 실패는 PUSH 를 막지 않되 오류 · 대조 보고 · 모집단 축소 불승인 |
| Q7 | 종목 단위 payload | flow 반환값에 additive · 본문 byte · 판정 · 순서 동일 테스트 필수 |
| Q8 | 대조군(비선정) | 이미 계산된 보유 · 27 사업군 비선정 결과 기록 · 추가 조회 · 재계산 금지 |
| Q9 | 본문 보존 | 분할 전 전문 + SHA-256 · 파일 권한 · DB 접근 로컬 사용자 한정 |
| Q10 | event_id | 실행 진입 때 발급 · `run_id` · `started_at` 은 보조키 |
| Q11 | dry-run · 수동 실행 | `mode=send` 만 · 수동 send 는 `off_schedule=true` · PRIMARY 통계 제외 |
| Q12 | contract_version | kind 별 코드 상수 · legacy 버전은 진단 전용 |
| Q13 | 시장 채점 대상 | (d) 방향 적중률 없음 · S&P500 상태와 한국 시장 원시 결과만 병기 |
| Q14 | 시장 부속 규칙 | FLAT/NONE · 동일 미국 세션 · 연휴 직후 · 입력 지연 태그 |
| Q15 | 가격 계열 · 분배락 | ETF = KRX 무조정 종가 · 비ETF 보유 = FDR · source 와 분배락 포함 여부 기록 |
| Q16 | 기준 가격 t0 | 장중 · 보유 신호의 PRIMARY t0 = 메시지 생성에 실제 사용한 현재가 · 신호일 · 전일 종가는 보조 · 현재가 누락 시 대체 없음 |
| Q17 | 거래일 축 | 실제 가격 적재일 순서 · 2027 CSV 선행조건 아님 · snapshot 우선 · 평일 fallback 유지 |
| Q18 | 결측 · 폐지 · 거래정지 | 가격 대체 금지 · `PRICE_MISSING` · `UNTRACKED_AFTER_EXIT` 등 · 거래량 필드 추가 없음 |
| Q19 | 표본 단위 | 반복 노출은 보조 · 신규 진입 · 구간 악화 · 회복 뒤 재진입이 PRIMARY 전이 이벤트 |
| Q20 | 상태별 방향 | 원시 결과만 · '유리한 방향' · 단일 성공 라벨 없음 |
| Q21 | OCI→PC 전달 | 원장 화면 열 때 1회 동기화 + 수동 새로고침 · PC 기동 시 자동 SSH 없음 |
| Q22 | PC 저장 | 기존 PC `state/decision/decision_evidence.sqlite` 에 원장 · 피드백 테이블 추가 · `runtime_state.sqlite` 사용과 새 PC DB 생성은 모두 불필요 |
| Q23 | 피드백 화면 | 「오늘의 투자 점검」 새 구역 `받은 알림 기록` · 상세 접기 `신호 결과 원장` · 메뉴 13 유지 |
| Q24 | 피드백 규칙 | `sent` · 실제 일부 전달된 `partial` 만 · append-only · 미입력 행 없음 · 가격 결과는 피드백 전 비노출 |
| Q25 | 성숙 계산 위치 | 07:20 배치 뒤 격리 단계 · 실패해도 배치 · 가격 적재 · 08:00 무영향 |
| Q26 | 단계 운영 | 단계마다 짧은 PLAN · MASTER 질문 반복 없음 |
| Q27 | Decision Outcome Ledger | POC5 가 기존 미결 항목을 이어받아 완성 · 중복 원장 없음 |
| Q28 | PRIMARY 시작 · 리뷰 | 운영 계약 정정 · 코드 pull 뒤 첫 거래일 · 10거래일 뒤 R0 · R1 정기 기술통계(날짜 블록 bootstrap) · 개발 대기 없음 |
| Q29 | 성공 임계 · 집계 | 성공 임계 없음 · kind · state · contract_version · horizon 별 원시 분포 · 첫 노출 PRIMARY · 반복 SECONDARY · 악화 · 재진입 새 사건 · 잘림 · 억제는 관측 모수 포함 · 전달 효과 모수 제외 |
| Q30 | 운영 3종 · 폐지 1종 | 운영 3종만 · spike 는 legacy 에서도 제외 · 낡은 OCI 상태 화면은 POC5 와 분리된 작은 수정으로 먼저 |

---

## 5. 조사 중 발견한 운영 이슈와 처리

| # | 이슈 | 처리 |
|---|---|---|
| 5-1 | 08:00 브리핑 기초지수 구역이 09-17 부터 빠짐(`CSV_REFRESH_REQUIRED` · 발송 5건 후보 0 · 본문 127자) | §3-1 정정 1 |
| 5-2 | KOSPI 지수 적재 09-17 정지(`kospi_as_of`) | §3-1 정정 7 |
| 5-3 | PC 「진단·상태 > OCI 운영 상태」 필수 push kind 목록이 낡음(spike 필수 · 장중 누락) | §3-1 정정 2 |
| 5-4 | 미국 입력 신선도 상한 없음 | 정정 목록 밖 · 원장에 '입력 지연' 태그로 기록(Q14) |
| 5-5 | 장중 통합 본문 '기준' 줄이 코드상 '현재가 —' | §3-1 정정 3(실제 발생 확인 먼저) |
| 5-6 | 구역 상한에 잘린 보유 급락도 당일 억제 | §3-1 정정 4 |
| 5-7 | 장중 집계 outcome 이 Telegram 실패 때 잠정값(`no_signal` 등)으로 남음 | §3-1 정정 5 |
| 5-8 | `holdings_risk_alert.message_text_length` 가 항상 0 | §3-1 정정 6 |
| 5-9 | PC `runtime_state.sqlite` 의 출처 불명 발송 기록 12행 · 등록부 9행 | 삭제하지 않음(설계자) · 전용 원장이라 새 데이터와 섞이지 않음 |
| 5-10 | 문서 stale(`PROGRAM_TRUTH` §3 · §9-C 실행 기록 위치 · §5.2 · §6.1 · §9-D · 러너 docstring 18행) | 정정 목록 밖 · 해당 단계의 `PROGRAM_TRUTH` 갱신 때 함께 정리 |
| 5-11 | 2026 캘린더 09-14 이후 USER_CONFIRMED · 2027 파일 없음 | Q17 — 기존 정책 유지 · 선행조건 아님 |
| 5-12 | 「승인·적용」 '발송 결과는 진단·상태에서 확인' 안내와 「오늘의 투자 점검」 OCI 한 줄 링크 대상 불일치 | 정정 목록 밖 · 기록 유지 |

---

## 6. 금지 범위 · 중단 조건 대조 (확정 계약 기준)

| 항목 | 확정 계약 |
|---|---|
| 현행 PUSH 문구 · 시간 · 임계 · 억제 · 상한 변경 | POC5 안에서는 0 — 본문 byte · 판정 · 순서 동일 테스트로 증명. §3-1 운영 정정은 POC5 가 아니라 설계자가 지시한 POC3 정정 단계(별도 PLAN) |
| 새로운 매수 · 매도 추천 | 0 |
| ML 학습 · RF · XGB · LGBM | 0 |
| outcome 을 보고 성공 기준 변경 | 해당 없음 — 성공 임계 자체가 없다(Q29 · RAW_ONLY) · 운영 결과 · 과거 수익률 계속 비열람 |
| 누락된 과거 신호 역생성 | 0 — 과거 종목 단위 `UNLINKABLE_LEGACY` |
| 테스트의 라이브 DB · 상태 파일 쓰기 | 0 — `_live_guard` + tmp DB · Telegram stub 기본 fixture |
| 실제 Telegram 발송 | 0 |
| OCI write · cron 변경 · 배포 | 승인된 POC5 구현 · 수동 배포만(Q2) · cron 추가 금지 |
| 사용자 피드백을 모델 label 로 사용 | 0 |
| 운영 DB 스키마 | `RUNTIME_STATE_DB_CHANGE = 0` · OCI 전용 원장 신규 · PC 기존 `decision_evidence.sqlite` 테이블 추가(사용자 승인 2026-09-26) |
| §12 현행 메시지 생성 · 발송 순서 변경 | 해당 없음 — additive payload · 최외곽 종료 확정은 PUSH 동작 불변(Q6 · Q7) |
| §12 기존 이벤트 연결키 불가 | 해당 없음 — 과거 종목 단위는 `UNLINKABLE_LEGACY`(Q1) |
| §12 운영 DB 를 테스트가 변경 | 해당 없음(가드) |
| §12 outcome 에 신규 외부 API | 해당 없음(OCI 적재 가격 · §1-6) |
| §12 Telegram callback · 신규 공개 API · 신규 cron | 해당 없음 — callback 없음 · 로컬 API(Q3) · cron 없음(Q2 · Q25) |
| §12 피드백이 발송에 영향 | 해당 없음 — PC 전용 저장 · 발송 경로와 분리 |
| §12 과거 결과를 본 뒤 기준 결정 | 해당 없음 — 성공 임계 없음(Q29 · RAW_ONLY) · 운영 결과 · 과거 수익률 계속 비열람 |
| §12 POC5 안에서 ML 재개 | 해당 없음 — POC5_PURPOSE: ML 재개 아님 |
| §11 신규 이벤트 100% | 실행 진입 전체가 모집단 · 누락은 명시적 gap · 대조 보고(Q6) |
| §11 운영 3종 · 폐지 1종 구분 | 원장 허용 목록 3종 · spike 제외 · OCI 상태 화면은 §3-1 정정 2 |

---

## 7. 작업 순서

1. 이 확정 PLAN 과 설계서 기록(설계자 PLAN 판정 원문 · 사용자 승인)을 커밋한다(설계자 판정). push 는 사용자가 따로 정한다.
2. **POC3 운영 정정 소형 PLAN**(§3-1)을 작성해 설계자에게 제출한다.
3. 그 뒤 POC5-01a → 01 → 02 → 03 → 04 순서로, 단계마다 짧은 PLAN → 판정 → 구현 → 결과서 → 설계자 → 검증자 → 커밋 → 사용자 pull.
4. PRIMARY 는 §2-7 시작 규칙대로 시작한다. R0 · R1 을 기다리는 동안 다른 UI · 운영 개선 작업은 막지 않는다.
