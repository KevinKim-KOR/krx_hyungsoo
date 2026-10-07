# POC5-03 — PC 원장 동기화·피드백 개발 PLAN V1

```text
STEP_ID        = POC5-03
DESIGN         = docs/ai_design/POC5/POC5-03_PC_LEDGER_SYNC_AND_FEEDBACK_DESIGN_V1.md (설계자 2026-10-07)
UPPER          = docs/ai_plan/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_PLAN_V1.md (Q1 ~ Q30 확정 · 다시 묻지 않음)
BASE_COMMIT    = f0711340 (POC5-02 커밋 · 코드 기준)
STATUS         = PLAN 확정 — 설계자 PASS_TO_IMPLEMENT_WITH_CORRECTIONS(2026-10-07 · 재제출 불필요 · Q-A · Q-B 승인 · Q-C 승인 + item 확장 · partial 본문 표기 추가 · 원문 = 설계서 끝 · §8)
설계 개정       = 개정 2(2026-10-07 · 사용자 목업 결정 · 별도 메뉴 · 선택 평가 · 결과 조회 평가 조건 없음 · 재제출 불필요) — 변경점 = §10
조사            = 설계서 §9 7항목 — 코드 읽기 전용 3묶음(PC DB · API / SSH · 원격 export · 원장 DDL / 오늘의 투자 점검 화면) + 개발자 직접 확인
설계자 질문      = 3건(§6 · 코드 · 확정 계약과 실제로 맞지 않는 것만)
```

## 0. 요약

설계서대로 만들 수 있다. PC backend 에 새 패키지 1개와 새 router 1개를 둔다. 「오늘의 투자 점검」에는 새 구역 파일 3개를 넣는다. OCI 쪽 파일 · cron · `.env` · 의존성 변경은 0 이다.

- 원격 export 는 OCI 에 새 파일을 두지 않는다. PC 가 저장소의 stdlib 전용 스크립트를 SSH 표준입력으로 보내 실행한다. 그래서 OCI pull 이 필요 없다(설계 §10).
- PC 사본은 `ledger_store.connect()` 를 쓰지 않는다. 그 함수는 폴더 0700 · 파일 0600 · WAL 을 강제하는데, PC 의 같은 파일에는 기존 AI 세션 기록이 있다. DDL 상수만 재사용한다(§2-2).

코드 · 확정 계약과 실제로 맞지 않는 곳이 3곳 있어 추천안과 함께 묻는다(§6).

1. 수용 기준 1 의 'PC 기동 SSH 0건'과, 이미 있는 POC3-07 기동 상태 확인 SSH 1회가 부딪친다(Q-A).
2. '마지막 성공 동기화 시각'을 재기동 뒤에도 남기려면 PC 전용 표가 하나 더 필요하다. 설계 §4 에는 `user_feedback` 만 있다(Q-B).
3. 결과 대상이 아닌 event(`LEGACY_DIAGNOSTIC` · 예정 외 실행)에 `집계 중`을 붙이면 사실과 다르다. 새 문구가 필요하다(Q-C).

## 1. 사실조사 (설계서 §9)

### 1-1. PC decision DB · 기본 경로 고정 · 경로 주입 (§9-1)

- PC `state/decision/decision_evidence.sqlite` 는 있다(맥북 실측 12,288 bytes · 파일 0644 · 폴더 0755). 이 파일을 쓰는 모듈은 `app/decision_evidence_store.py`(543줄) 하나이고, 테이블은 `ai_session_records` 하나다(:37-59). WAL 은 설정하지 않는다.
- 기본 경로가 함수 정의 시점에 묶인다. 기본 인자 `db_path: Path = DEFAULT_DB_PATH` 가 4곳에 있다(`init_db` :249 · `insert_record` :313 · `list_recent_records` :496 · `get_record` :533). `api_decision_sessions` 는 이름으로 import 해서 넘긴다(:23). 그래서 기존 테스트는 두 모듈을 모두 monkeypatch 한다.
- `ledger_store` 는 같은 경로이지만 `_db_path()` 로 호출 시점에 읽는다(:161-163). `conftest` 의 autouse `_isolated_decision_ledger` 가 이 값을 tmp 로 바꾼다(:360-383).
- `ledger_store.connect()` 는 처음 열 때 폴더 0700 · 파일 0600 을 맞추고 확인한다(실패하면 `LedgerUnavailable`). 그리고 WAL 로 영구 전환한다(:166-207). PC 에서 이 함수를 쓰면 기존 AI 세션 파일의 권한과 저널 방식이 바뀐다.
- 라이브 가드(`tests/_live_guard.py`)에 걸리지 않으려면 새 테스트는 tmp DB 만 써야 한다. 호환 목록은 늘리지 않는다(상한 229).
- **안전한 주입(결정)**: 새 모듈은 `ledger_store` 처럼 호출 시점 `_db_path()` 를 쓴다. 모든 공개 함수는 `db_path` 를 키워드로 받을 수 있다. conftest autouse 에서 새 모듈 경로도 tmp 로 바꾼다. 기존 `decision_evidence_store` 의 기본 인자는 건드리지 않는다(범위 밖).

### 1-2. SSH wrapper · 원격 python · export 위치 (§9-2)

| 선례 | 성격 | 명령 · 시간 | 원격 python |
|---|---|---|---|
| `oci_startup_status._ssh_read` | 읽기 전용 | `ssh -o BatchMode=yes -o ConnectTimeout=8 [-i KEY -o IdentitiesOnly=yes] <OCI_SSH_TARGET> <고정 명령>` · timeout 15 · 실패해도 예외 없음 · 로그는 예외 · exit 만 | — |
| `oci_status_rows` | 읽기 전용 블록 | `python3 - <<'PY' … PY` heredoc · `sqlite3.connect('file:…?mode=ro', uri=True)` | 시스템 `python3`(stdlib) |
| `run_decision_ledger_reconcile.py` | OCI 원장 읽기 CLI | 두 DB 모두 mode=ro · 예외 종류만 출력 | `venv/bin/python`(OCI 저장소 파일 — pull 필요) |
| `holdings_oci_apply` · `delivery` · `sync_*` | 쓰기 계열 | 재사용 대상 아님 | — |

- `.env` 키 이름: `OCI_SSH_TARGET`(필수) · `OCI_SSH_KEY_PATH`(선택). 원격 홈은 코드 상수 `/home/ubuntu/krx_hyungsoo` 다.
- PC lifespan 은 기동 때 `oci_startup_status.refresh_snapshot()` 으로 읽기 SSH 를 1회 실행한다(`app/api.py:75-95` · POC3-07). → Q-A
- 기존 wrapper 들은 `text=True` 에 인코딩을 지정하지 않는다. 일부는 stdout · stderr 를 로그나 예외 메시지에 넣는다. export 에는 알림 본문(`delivery.body_text`)이 실리므로 이 패턴을 따르면 안 된다.
- **export 위치(결정)**: OCI 저장소에 파일을 두지 않는다(설계 §10: POC5-03 은 OCI pull 없음). 새 파일 `app/ledger_copy/remote_export.py`(stdlib 전용)를 PC 가 읽어 `ssh … "python3 - <고정 원장 경로>"` 의 표준입력으로 보낸다.
  - 셸 인용과 heredoc 문제가 없다.
  - 같은 파일을 로컬 테스트에서 tmp 원장 대상으로 그대로 실행할 수 있다. 그래서 문자열 코드의 테스트 사각이 없다.
  - 원격 명령 문자열은 모듈 상수다. 사용자 입력을 붙이지 않는다.

### 1-3. 원격 5테이블 DDL · PC upsert 경계 (§9-3)

| 표 | PK | 원격에서 바뀌는 방식(코드) | PC 반영 |
|---|---|---|---|
| `evaluation_run` | `event_id` | STARTED INSERT → finalize 가 1회 `UPDATE … SET run_state='FINALIZED' … WHERE run_state='STARTED'`(ledger_store.py:279-327) | 없으면 INSERT · PC 쪽이 STARTED 면 원격 행 전체로 UPDATE · PC 쪽이 FINALIZED 이면 같을 때만 통과(다르거나 원격이 STARTED 면 충돌) |
| `signal_item` | `(event_id, item_seq)` | finalize 트랜잭션 안 INSERT 만 | 없으면 INSERT · 같으면 통과 · 다르면 충돌 |
| `delivery` | `event_id` | 위와 같음 | 위와 같음 |
| `ledger_meta` | `key` | `INSERT OR IGNORE` 만(`meta_put_once`) | 위와 같음 |
| `price_outcome` | `(event_id, item_seq, series_id, horizon)` | `INSERT OR IGNORE` 만(ledger_outcome.py:213-226) | 위와 같음 |

- STARTED run 에는 item · delivery 가 없다. 같은 커밋에서 함께 생기기 때문이다. 원격에서 행을 지우는 경로는 0 이다.
- `price_outcome` 은 `run_maturity()` 가 처음 실행될 때 DDL 로 생긴다. 그래서 POC5-02 OCI 배포와 첫 08:10 실행 전에는 원격에 이 표가 없다. 원격 원장은 mode=ro 로 열어 표를 만들 수 없다. → export 는 `sqlite_master` 로 표 유무를 먼저 보고 '없음'을 표시한다. PC 는 이를 오류가 아니라 '성숙 전'으로 처리한다.
- 원격 finalize 는 item · delivery INSERT 와 run UPDATE 를 한 트랜잭션으로 커밋한다. 표마다 따로 SELECT 하면 그 사이 커밋 때문에 어긋난 스냅샷이 나올 수 있다(WAL). → export 는 한 mode=ro 연결의 읽기 트랜잭션 안에서 5표를 모두 읽는다.
- 크기 근사(코드 기준 · 실측 아님): 거래일당 run 약 11 · item 약 500 · price_outcome 약 1,500행이다. 원장은 10-08 첫 활성이라 V1 전체 export 는 감당할 수 있다(설계 §3: 크기 문제가 확인되기 전에는 cursor 를 만들지 않는다).

### 1-4. 「오늘의 투자 점검」 구성 · 캐시 · 라우팅 삽입 지점 (§9-4)

- 본체 `frontend/app/components/TodayInvestmentCheckView.tsx`(141줄)는 조회 · 배치만 한다. 렌더 순서는 아래와 같다(:103-140).
  1. header(+`OciStatusOneLine`)
  2. `KospiHeadline`
  3. `KospiDetailSection`
  4. `tc-queue-grid`[판단 큐 · 정비 큐]
  5. `InDevelopmentSection`
- 구역은 `today/` 아래 파일로 나뉘어 있다(가장 긴 파일 151줄). 루트는 `<section className="tc-card">` 다.
- 데이터: `useSharedQuery` 4개(모듈 메모리 캐시 · 진입 때 1회)와 `OciStatusOneLine` 의 GET 1회가 있다. 이 GET 은 backend 기동 캐시를 돌려줄 뿐 SSH 가 아니다.
- API 클라이언트: `lib/api/core.ts` 의 `request()` 기본 timeout 은 10초다. SSH 가 끼는 기존 버튼(`applyHoldingsToOci`)은 120초를 따로 넘긴다. 도메인 파일과 `lib/api/index.ts` barrel 패턴을 따른다.
- 버튼 패턴: `useLightRefreshState`(idle · running · done · failed · 실행 중 비활성 · 실패를 완료로 위장하지 않음)가 있다. 접기는 다른 화면의 네이티브 `<details>` 다.
- backend 라우팅: `app/api.py` 는 642줄이다(KS-10 백엔드 임계 650). 새 기능은 별도 router 모듈로 둔다. `api.py` 에는 import 1줄과 `include_router` 1줄만 더한다(+2줄 → 644).
- **삽입 지점(결정 · 목업으로 사용자 확인)**: `tc-queue-grid` 끝(:136)과 `<InDevelopmentSection />`(:138) 사이.
- 이름: push_kind 화면 이름은 기존 `OciStatusView.tsx:46-48` 의 것을 그대로 쓴다(`시장 브리핑` · `보유 브리핑` · `장중 급등락`). 새 이름을 만들지 않는다.

### 1-5. feedback 입력 제한 재사용 (§9-5)

- enum: `api_decision_sessions` 의 `Literal` 과 store 의 이중 검증 패턴이 있다(`ALLOWED_USER_VERDICTS` + `DecisionValidationError` → API 422).
  - `helpfulness`(필수) · `action`(선택)에 같은 패턴을 쓴다.
- 자유 텍스트 길이: `app/api_*.py` 전체에 pydantic `max_length` 는 0건이고, 기존 `user_memo` 에도 상한이 없다. 유일한 선례는 `holdings.ACCOUNT_GROUP_MAX_LEN = 30` 이다(strip 뒤 `len` 비교). 이 값은 라벨용이라 메모에는 짧다.
- **memo 상한(결정)**: strip 뒤 **500자**. 빈 문자열은 NULL 로 저장한다. 같은 strip-len 방식으로 store 와 API 에서 모두 검증한다.

### 1-6. 가격 결과 숨김을 보장할 응답 조립 위치 (§9-6)

- 기존 패턴은 pydantic 응답 모델 + `response_model` 이다. 선언하지 않은 필드는 직렬화에서 빠진다.
- **숨김(결정)**: 두 층에서 막는다.
  1. 조회 조립 함수(`app/ledger_copy/views.py`)는 `user_feedback` 이 0행인 event 에 대해 `price_outcome` 을 **조회하지 않는다**. 이때 `outcome = {"visible": false}` 만 넣는다. 행 수 · 상태 · 존재 여부를 담지 않는다.
  2. 응답 모델은 가격 필드를 이 객체 안에만 둔다.
- 숨기는 것은 `price_outcome` 의 모든 값(+1 · +5 · +20 · 상태)이다. `signal_item.t0_price` 는 설계 §5 의 '당시 상태 · t0 · disposition' 이라 보인다.

### 1-7. 변경 파일 · 테스트 · 실화면 · KS-10 (§9-7 · 2026-10-07 `wc -l`)

| 파일 | 지금 | 변경 |
|---|---|---|
| `app/ledger_copy/__init__.py` | 신규 | 패키지 |
| `app/ledger_copy/store.py` | 신규 | PC 사본 DDL(원장 DDL 상수 재사용 + `user_feedback` (+Q-B 표)) · 검증된 행 반영(단일 트랜잭션) · feedback append |
| `app/ledger_copy/sync.py` | 신규 | SSH 1회 실행 · 출력 검증(전부 메모리에서 끝낸 뒤 반영) · 동시 실행 잠금 |
| `app/ledger_copy/remote_export.py` | 신규 | stdlib 전용 export(OCI 에서 표준입력으로 실행 · 로컬 테스트 실행 가능) |
| `app/ledger_copy/views.py` | 신규 | 목록 · 상세 조립 · 숨김 · 이름 붙이기 |
| `app/api_decision_ledger.py` | 신규 | router 3종(조회 · 동기화 · feedback) |
| `app/api.py` | 642 | +2(import · include) |
| `tests/conftest.py` | 615 | autouse 에 새 경로 tmp 1줄 |
| `tests/test_poc5_03_ledger_copy.py` · `tests/test_poc5_03_ledger_api.py` | 신규 | §4 |
| `frontend/lib/api/decisionLedger.ts` · `lib/api/index.ts`(28) | 신규 · +1 | API 클라이언트 |
| `frontend/app/components/today/ReceivedAlertsSection.tsx` · `ReceivedAlertCard.tsx` · `SignalOutcomeLedger.tsx` | 신규 | 구역 · 카드+feedback · 접기 원장 |
| `frontend/app/components/TodayInvestmentCheckView.tsx` | 141 | +2(import · JSX) |
| `frontend/app/components/TodayInvestmentCheckView.test.tsx` | 810 | `@/lib/api` mock 에 새 함수 추가(목록 mock 이라 안 넣으면 깨짐) |
| `frontend/app/components/today/ReceivedAlertsSection.test.tsx` | 신규 | §4 |
| `frontend/app/globals.css` | 3,163 | `tc-*` 몇 줄(KS-10 은 컴포넌트 기준이라 CSS 제외) |

- 새 파일은 백엔드 650 · 컴포넌트 900 · 테스트 1,500 보다 충분히 작게 나눈다. 메뉴 파일(`LeftSidebar` · `MainPanel` · `MenuKey` 12개)은 바뀌지 않는다.
- 실화면: 맥북 dev 서버에서 사용자가 확인한다(설계 §10). OCI 실데이터 동기화 확인은 POC5-02 배포 뒤에 한다.

## 2. 구현 계획 (판정 뒤)

### 2-1. 원격 export (`remote_export.py`)

- 원격 명령(상수): `python3 - /home/ubuntu/krx_hyungsoo/state/decision/decision_evidence.sqlite`. 표준입력은 이 파일 내용이다.
- 원장 파일이 없으면 열지 않는다(mode=ro 연결은 파일이 없으면 오류). 이때 `{"kind":"header","ledger":"absent"}` 를 내고 exit 0 한다.
- 파일이 있으면 `file:…?mode=ro` 로 연결하고 `BEGIN` 으로 읽기 트랜잭션을 연다.
  - `sqlite_master` 로 5표 유무를 확인한다.
  - 표마다 `SELECT *` 결과를 JSONL `{"kind":"row","table":…,"row":{…}}` 로 낸다.
  - 끝에 `{"kind":"end","counts":{표: 행수}}` 를 낸다.
- 예외가 나면 `{"kind":"error","error_type":<예외 종류>}` 와 exit 3 이다. 본문 · 경로 · 메시지는 출력하지 않는다.
- 쓰기 · DDL · PRAGMA 변경은 0 이다. 테스트에서 export 전후 tmp WAL 원장의 주 파일 sha256 과 행이 같은지 확인한다. `-wal` · `-shm` 부속 파일은 SQLite 의 WAL 읽기 규약이 다룬다(기존 대조 CLI 와 같음).

### 2-2. PC 사본 저장 (`store.py`)

- 연결: `sqlite3.connect(_db_path(), timeout=5)` 다. 권한 · WAL 은 바꾸지 않는다(기존 PC 파일 방식 그대로).
- DDL: `ledger_store.DDL` + `ledger_outcome.DDL` 상수를 그대로 실행한다. 원격과 같은 스키마 · 의미다. 여기에 PC 전용 표를 더한다.
  - `user_feedback(event_id TEXT NOT NULL, feedback_seq INTEGER NOT NULL, helpfulness TEXT NOT NULL, action TEXT, memo TEXT, feedback_at TEXT NOT NULL, PRIMARY KEY(event_id, feedback_seq))`
  - (Q-B 승인 시) `ledger_sync_attempt(attempt_seq INTEGER PRIMARY KEY AUTOINCREMENT, attempted_at TEXT NOT NULL, ok INTEGER NOT NULL, failure_kind TEXT, counts_json TEXT)`
- 반영 순서: 검증을 전부 마친 행 묶음만 받는다. `BEGIN IMMEDIATE` → §1-3 표대로 표마다 반영 → `COMMIT` 이다. 충돌이나 예외가 하나라도 나면 `ROLLBACK` 한다. 기존 사본과 `user_feedback` 은 그대로 남는다.
- PC 에만 있고 export 에 없는 행은 지우지 않는다(원격 삭제 경로가 0 이므로).
- `user_feedback` 은 반영 대상이 아니다.
- feedback append 는 `BEGIN IMMEDIATE` 안에서 진행한다.
  1. 그 event 의 로컬 `delivery_status ∈ {sent, partial}` 을 확인한다. 아니면 거부한다.
  2. `MAX(feedback_seq)+1` 로 INSERT 한다.
  - UPDATE · DELETE 경로는 0 이다.

### 2-3. 동기화 (`sync.py` · `POST /decision-ledger/sync`)

1. 동시 실행을 잠금으로 막는다. 이미 진행 중이면 409 `BUSY` 다.
2. SSH 1회: `oci_startup_status._ssh_read` 와 같은 옵션(`BatchMode=yes` · `ConnectTimeout=8` · 키 옵션)을 쓴다. 전체 timeout 은 60초다.
   - stdout 은 **bytes 로 받아 UTF-8 로 명시 디코딩**한다.
   - stdout · stderr 는 로그 · 응답 · 파일 어디에도 넣지 않는다. 로그는 실패 종류 · exit code 만 남긴다.
3. 검증(메모리)
   - header 가 처음, end 가 마지막이고 표별 행 수가 end 와 같아야 한다.
   - 표 이름 · 열은 PC 표 열의 부분집합이어야 한다(`PRAGMA table_info`). 모르는 열이 있으면 스키마 불일치로 실패한다.
   - PK · NOT NULL 열이 있어야 하고, export 안에서 키가 중복되면 안 된다.
   - item · delivery 는 FINALIZED run 에만 있어야 한다. outcome 은 export 안의 item 을 가리켜야 한다.
4. 반영: §2-2 의 단일 트랜잭션이다.
5. 결과
   - 응답: `{ok, attempted_at, failure_kind?, counts{표:{inserted,updated,unchanged}}, outcome_table: present|absent}`
   - 실패 종류: `SSH_FAILED` · `TIMEOUT` · `REMOTE_ERROR` · `NO_REMOTE_LEDGER` · `INVALID_EXPORT` · `CONFLICT` · `LOCAL_WRITE_FAILED` · `BUSY`
   - (Q-B) 시도마다 `ledger_sync_attempt` 에 1행을 남긴다. 실패 기록은 롤백 뒤 별도 짧은 트랜잭션으로 한다.
- 시장 API · Telegram · OCI 쓰기 호출은 0 이다. 동기화 API 말고는 SSH 를 import · 호출하지 않는다.

### 2-4. 조회 · feedback API (`app/api_decision_ledger.py` · prefix `/decision-ledger`)

| 기능 | 경로 | 내용 |
|---|---|---|
| 로컬 사본 조회 | `GET /decision-ledger/alerts?date=YYYY-MM-DD&kind=all\|market\|holdings\|intraday` | 동기화 상태(사본 유무 · 마지막 성공 시각 · 마지막 실패 시각) + 선택 날짜(`runtime_date_kst` · 기본 오늘 KST)의 `delivery_status ∈ {sent, partial}` event 목록. 카드 = 실행 시각 · 종류 · 전달 상태 · 핵심 item(disposition `sent`) 이름 · 수 · 최근 feedback |
| 〃 상세 | `GET /decision-ledger/alerts/{event_id}` | 전문(`body_withheld=1` 이면 '본문 보류' 표시 · `partial` 은 '생성된 원문 — 일부만 전달됨 / 실제 수신된 범위는 확인할 수 없습니다' §8-2) · item 전체(상태 · 직전 상태 · disposition · t0) · feedback 이력 전체 · `outcome`(§1-6 숨김) |
| 동기화 | `POST /decision-ledger/sync` | §2-3 |
| feedback | `POST /decision-ledger/alerts/{event_id}/feedback` | `{helpfulness, action?, memo?}` → 새 `feedback_seq`. 로컬에 없는 event 404 · sent/partial 아님 409 · 검증 실패 422 |

- '신호 결과 원장'(접기)은 목록과 같은 날짜 · 종류의 event 에서 `evaluable=1` item 을 보여 준다(상세 응답 재사용).
  - feedback 대상이 아닌 event(전달 안 됨)의 결과는 영영 열 수 없어 의미가 없다. 그래서 목록 범위와 맞춘다.
- 이름 붙이기: PC 보유 목록의 `name` → PC 시장 DB `etf_master` 이름 → 없으면 코드 그대로 쓴다. 읽기 전용이고 실패해도 코드로 둔다. 테스트는 로더를 주입해 라이브 파일을 열지 않는다.
- 127.0.0.1: 기존 API 전부와 같이 `uvicorn --host 127.0.0.1`(start.sh · start.bat) 바인딩으로 보장한다. 요청마다 IP 를 검사하는 가드는 기존 API 와 다르게 이것만 두게 되므로 넣지 않는다.

### 2-5. 화면 (목업 승인 뒤 구현)

- 설계 §5 그대로다.
  - 구역 머리: `받은 알림 기록` + `[원장 새로고침]` + `마지막 성공 동기화 MM-DD HH:MM`
  - 날짜 선택 · 종류 필터(전체 · 시장 · 보유 · 장중)
  - 카드: 시각 · 종류 · 전달 상태(`partial` = `일부 전달`) · 핵심 item · `자세히 보기`
  - 카드 안 feedback: 3버튼 + 선택 행동 + 메모 + 저장
  - `▸ 신호 결과 원장` 은 `<details>` 다.
- 빈 · 실패 문구는 설계 원문을 쓴다(`원장 새로고침이 필요합니다` · `기존 기록을 표시 중입니다` + 실패 시각).
- 결과 칸
  - feedback 전: `피드백 후 결과 확인` 만 보인다.
  - feedback 뒤 행 없음: `집계 중`
  - 상태 행: `가격 자료 없음` · `매도 뒤 추적 중단` · `지원 계열 없음`
  - `결과 대상 아님` — event(`PRIMARY_LIVE` ∧ `off_schedule=0` 아님) 또는 item(`evaluable=0` 또는 subject 가 ticker · sector · market · index_group 밖)(§8-1)
  - MATURED 는 `return_raw` 를 % 로 보인다. 성공 · 실패 색이나 배지는 없다.
- 새로고침 버튼은 실행 중 비활성이다. 실패를 완료로 보이지 않는다. timeout 은 90초다(backend 60초 + 여유).
- feedback 저장이 실패하면 버튼 상태를 바꾸지 않고 오류를 보인다.
- 화면 진입은 `GET /decision-ledger/alerts` 만 부른다(SSH 0).

## 3. 문서

- `docs/PROGRAM_TRUTH.md`: 「오늘의 투자 점검」 구역 · API 3종 · PC 사본 표 · 동기화 경계를 해당 섹션 전부 grep 해서 한 번에 갱신한다.
- `docs/STATE_LATEST.md` 머리를 갱신한다. 결과서는 `docs/ai_result/POC5/POC5-03_PC_LEDGER_SYNC_AND_FEEDBACK_RESULT.md` 1개다.

## 4. 검증 계획 (줄인 방식)

| 수용 기준 | 확인 방법 |
|---|---|
| 1 기동 · 진입 SSH 0 | `subprocess.run` 을 실패 함수로 바꾸고 TestClient 로 조회 API · feedback API 를 호출한다. 원장 SSH 호출 0 을 확인한다(Q-A 범위). |
| 2 버튼 1회 = export 1회 · 애플리케이션의 원장 쓰기 0 · 원장 행 불변(SQLite 보조 파일 생성 가능 · 설계자 RESULT 2026-10-07) | sync 1회에 SSH argv 1회인지 본다(고정 명령 · BatchMode · 사용자 입력 없음). `remote_export.py` 를 tmp WAL 원장 대상으로 실제 실행해 전후 sha256 · 행이 같은지 본다. |
| 3 반복 반영 중복 0 · feedback 보존 | 같은 export 를 2회 반영해 두 번째는 전부 `unchanged` 인지, feedback 행이 그대로인지 본다. STARTED→FINALIZED 갱신 1건도 확인한다. |
| 4 중간 실패 전체 취소 | 표 3번째에서 예외를 주입하고, 충돌 행 · 잘못된 JSONL · end 누락 · 모르는 열을 넣는다. 이때 사본 · feedback 이 전후로 같은지 본다. |
| 5 sent · partial 만 | 목록 필터와, skipped · failed event 에 feedback 409 인지 본다. |
| 6 미입력 행 0 · 재입력 누적 | 동기화 뒤 `user_feedback` 이 0행인지, 2회 입력하면 seq 1 · 2 인지, 화면이 최근 것을 보이는지 본다. |
| 7 feedback 전 비노출 | API 응답 JSON 에 `price_outcome` 열 이름 · 값이 0 이고 `{"visible": false}` 만 있는지 본다. 화면은 vitest 로 확인한다. |
| 8 feedback 뒤 상태 표시 | MATURED · 행 없음 · PRICE_MISSING · UNTRACKED · UNSUPPORTED · (Q-C) 문구를 보고, 색 · 배지가 0 인지 본다. |
| 9 메뉴 · cron · 외부 · OCI 쓰기 · Telegram 0 | `LeftSidebar.test`(12 key) 변경 없음, 새 코드에 http · telegram import 0, 원격 명령 상수 1개를 grep 으로 확인한다. |
| 10 | 새 테스트(tmp DB) · vitest · tsc · eslint · black · flake8 · 전체 pytest 마지막 1회 · 라이브 파일 sha256 전후 비교 · KS-10 `wc -l` · 사용자 실화면 |

- 검토는 코드 + 문서를 한 번에 1회 한다.
- OCI 실데이터 동기화는 POC5-02 배포 뒤 사용자 버튼으로 1회 확인한다. 이때 OCI 원장 파일 mtime · 행 수를 읽기 전용으로 전후 비교한다.

## 5. 배포 · 롤백

- PC 기능이다. OCI pull · cron · `.env` 변경은 0 이다. 커밋 · push 뒤 PC 재기동과 사용자 실화면으로 끝난다.
- 롤백은 커밋 되돌리기다. PC DB 에 생긴 사본 표와 `user_feedback` 은 기존 `ai_session_records` 에 영향이 없다(테이블 이름이 겹치지 않음).

## 6. 설계자 질문 (코드 · 확정 계약과 실제로 맞지 않는 것만)

**Q-A. 수용 기준 1 'PC 기동 SSH 0건'의 범위**

- 사실: PC backend 는 POC3-07 부터 기동 때 OCI 상태 한 줄을 위한 읽기 SSH 를 1회 실행한다(`app/api.py:75-95`). 글자 그대로라면 기준 1 은 이미 실패다.
- 추천: 기준 1 = **원장 export SSH** 가 기동 · 화면 진입으로 0건. 기존 기동 상태 확인 SSH 는 그대로 둔다(설계 §2 '제외'의 대상도 원장 동기화로 읽힘).

**Q-B. '마지막 성공 동기화 시각' 저장 위치**

- 사실: 설계 §2 는 상태 JSON 을 제외하고, §4 의 PC 전용 표는 `user_feedback` 하나다. 재기동 뒤에도 마지막 성공 · 실패 시각을 보이려면 어딘가에 남겨야 한다.
- 추천: 같은 PC DB 에 append-only `ledger_sync_attempt`(시각 · 성공 여부 · 실패 종류 · 표별 반영 수)를 둔다.
- 대안: 메모리에만 두기. 이러면 재기동 뒤에는 사본이 있어도 '마지막 성공 동기화'를 알 수 없다.

**Q-C. 결과 대상이 아닌 event 의 결과 칸 문구**

- 사실: POC5-02 성숙 대상은 `PRIMARY_LIVE` · `off_schedule=0` 뿐이다. 예정 외 수동 실행이나 `LEGACY_DIAGNOSTIC` event 도 sent 면 목록 · feedback 대상이다. 그런데 결과 행은 영영 생기지 않는다. 설계 §5 대로 `집계 중`을 붙이면 사실과 다르다.
- 추천: 이 event 의 item 결과 칸에 `결과 대상 아님` 을 표시한다. 새 문구라 확인을 받는다.

## 7. 사용자 확인 항목

1. 화면 목업: PLAN 판정 뒤 backend 를 구현하는 동안 §5 한 화면 목업을 사용자에게 보인다. 승인 뒤 frontend 를 시작한다(설계 §10).
2. 개발 PC 는 맥북이다. Windows PC 에서 쓴다면 권한 강제를 하지 않기 때문에 문제는 없지만, 실화면 확인은 맥북 기준이다.

## 8. 설계자 판정 반영 (2026-10-07 · PASS_TO_IMPLEMENT_WITH_CORRECTIONS · 원문 = 설계서 끝)

- Q-A 승인: 수용 기준 1 의 SSH 0건 = **원장 export SSH** 한정. POC3-07 기동 상태 확인 SSH 1회는 유지한다.
- Q-B 승인: PC DB 에 append-only `ledger_sync_attempt` 를 둔다(§2-2 · §2-3).
- Q-C 승인 + 확장 — `결과 대상 아님` 판정(조회 조립 함수 한 곳에서 정하고 API 응답에 싣는다):
  1. event: `cohort = PRIMARY_LIVE` ∧ `off_schedule = 0` 이 아니면 그 event 의 모든 item 이 대상 아님.
  2. item: `evaluable = 1` ∧ `subject_kind ∈ {ticker, sector, market, index_group}` 가 아니면 대상 아님(`index_block` · `sector_block` · `evaluable=0` 포함).
  3. 대상 아닌 item 을 `집계 중` 으로 표시하지 않는다. `집계 중` 은 대상 item 에 결과 행이 아직 없을 때만.
- 추가 조건 — `partial` 상세 본문: 01B `body_text` 는 분할 전 전체 본문이다. `partial` 이면 본문 머리에 '생성된 원문 — 일부만 전달됨' · '실제 수신된 범위는 확인할 수 없습니다' 를 붙인다. `받은 전문` · `전달된 원문` 같은 표현은 쓰지 않는다(`sent` 는 설계 §5 표현 그대로 '원문').
- 위 조건은 backend 테스트(대상 판정 · partial 표기 필드)와 vitest(문구)에 넣는다.
- 진행: backend 구현과 화면 목업을 병행한다. 사용자 목업 확인 뒤 frontend 를 구현한다. POC5-02 OCI 배포는 10-08 01B 운영 확인 뒤.

## 9. 사용자 목업 확인 결과 (2026-10-07 · 설계 개정 2 로 확정)

목업(「오늘의 투자 점검」 안 '받은 알림 기록' 구역)을 본 사용자 결정:

> "이건 별도 메뉴로 뺐으면 좋겠습니다. ML을 위한 좋은 기능이지만 제가 매일 들어가서 저런 것을 체크하기란 어렵습니다. 받은 알림에 대해서 사후 ML돌리는 시점에 재평가하는 방향으로 했으면 합니다. 그러기 위한 저장이라고 생각했습니다."

1. **별도 메뉴** — 「진단·상태」 그룹 'ML 실험' 바로 옆(사용자 선택). 「오늘의 투자 점검」에는 넣지 않는다.
2. **목록은 날짜별 하루씩**(목업 그대로 · 사용자 선택).
3. **평가가 없어도 ML 에서 쓰인다** — 사용자: "제 평가가 없더라도 평가 없는대로 ML에서 해당 데이터 사용되어야 함". 피드백은 선택이고, 피드백이 없다는 것이 제외나 부정 신호가 되면 안 된다.

설계와 달라지는 곳: 설계서 §1 · §2(새 메뉴 제외) · §5(삽입 위치 · 기본 날짜) · 수용 기준 9(새 메뉴 0). 바뀌지 않는 곳: backend 전부(동기화 · 사본 · 피드백 append-only · 숨김 · 결과 대상 판정) — 구현 · 검토 반영 완료(테스트 55).

## 10. 설계 개정 2 반영 — 변경점만 (2026-10-07 · 설계자 `ACCEPTED_USER_DIRECTED_DESIGN_CHANGE` · 원문 = 설계서 본문 · §13)

이 PLAN 의 아래 문장은 개정 2 로 대체된다(위 본문은 결정 이력으로 둔다).

| 이 PLAN | 대체 내용 |
|---|---|
| §1-4 삽입 지점(「오늘의 투자 점검」 `tc-queue-grid` 뒤) · §1-7 프론트 파일(`today/` 3개 · `TodayInvestmentCheckView` +2 · 그 테스트 mock) | 「진단·상태」 `ML 실험` 바로 아래 새 메뉴 `받은 알림 기록`(MenuKey 12 → 13 · `LeftSidebar` · `MainPanel` · `LeftSidebar.test` · `MainPanel.test`) · 새 화면 파일은 `frontend/app/components/` 아래 · 「오늘의 투자 점검」 변경 0 |
| §1-6 · §2-4 · §8 가격 결과 숨김(feedback 0행이면 `price_outcome` 미조회 · `{"visible": False}`) | **폐기** — 상세 응답 `outcomes` 는 평가 유무와 무관하게 조회 · 조회는 feedback 행을 만들지 않는다 |
| §2-4 목록 기본 날짜(오늘 KST) | `date` 를 주지 않으면 사본의 sent · partial 알림이 있는 가장 최근 `runtime_date_kst`(전체 종류) · 없으면 오늘 KST · 응답 `date` 로 돌려준다. 화면은 사용자가 고른 날짜를 동기화 · 종류 변경 뒤에도 유지 · 이전/다음 날 = 달력 ±1일 |
| §2-5 결과 칸(`피드백 후 결과 확인`) | 없음. `집계 중` · `가격 자료 없음` · `매도 뒤 추적 중단` · `지원 계열 없음` · `기준 가격 없음`(`T0_MISSING`) · `결과 대상 아님` 만 |
| §2-5 카드 안 평가 입력 | 평가 입력은 `자세히 보기` 안의 선택 영역 · 카드에는 '내 평가: …' 또는 '평가 없음' 만 · 미평가 수 · 완료율 · 독촉 없음 |
| §4 수용 기준 1 · 7 · 8 · 9 확인 방법 | 1 = 원장 export SSH 0(기존 기동 상태 SSH 예외) · 7 = 무평가 결과 조회 · 조회가 feedback 행을 만들지 않음 · 8 = 평가 전후 결과 · 대상 판정 동일 · 9 = 메뉴 1개만 추가 · 「오늘의 투자 점검」 변경 0 |

- 유지: 동기화 · 사본 · 검증 · 단일 트랜잭션 · 성공 기록 동일 트랜잭션 · 결과 반영 수 비노출(개정 2 §3 수용) · 결과 대상 판정(§8 확장) · partial 표기 · feedback append-only · 01B · 02 코드 불변.
- backend 국소 수정: `views.alert_detail` 의 feedback 조건 제거(`outcome` → `outcomes` 목록) · `views.list_alerts(day=None)` 기본 날짜 · API `date` 생략 허용 · 숨김 테스트를 무평가 조회 · 평가 전후 동일 · 기본 날짜 테스트로 교체(새 테스트 파일 58개 통과).
- 목업: 새 메뉴 기준으로 갱신해 사용자 확인 뒤 frontend 구현(설계 §10).

## 11. 검증자 r1 정정으로 바뀐 계약 (2026-10-07 · 변경점만)

- §2-3 검증: 원장 기본 4표(`evaluation_run` · `signal_item` · `delivery` · `ledger_meta`)가 하나라도 없으면 `INVALID_EXPORT`(빈 SQLite · 표 누락 ≠ 정상 빈 원장). `price_outcome` 은 없어도 정상(성숙 전) — 단 `ledger_meta` 에 `schema_version.price_outcome` 이 있으면 `INVALID_EXPORT`.
- §2-2 반영: 'PC 에만 있는 행은 지우지 않는다' 는 유지하되, 그런 행이 있으면 받아 넘기지 않고 `CONFLICT`(원격은 지우지 않으므로 원장 손실 · 교체 신호 · 전체 취소).
- 화면: 목록을 다시 읽을 때마다(원장 새로고침 · 평가 저장) 펼친 `신호 결과 원장` 과 열린 상세도 다시 읽는다.
