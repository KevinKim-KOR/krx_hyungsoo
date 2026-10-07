# POC5-03 개발 결과서 — PC_LEDGER_SYNC_AND_FEEDBACK (받은 알림 기록)

작성 2026-10-07 · 갱신 2026-10-07(검증자 r1 정정 · r2 VERIFIED · 설계자 RESULT 처리 문구 반영) · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex)

```text
STATUS                 = IMPLEMENTED_VERIFIED — 검증자 r2 VERIFIED(2026-10-07 · 위험 NONE · 범위 폭주 NONE) · 설계자 RESULT `PASS_TO_USER_CHECK`(2026-10-07 · 지시문 외 변경 5/5 · 충돌 정책 수용 · 재작업 · 재제출 없음 · 처리 문구 확정 반영) · 남은 것 = 사용자 실화면 · OCI 실데이터 동기화(10-08 09:35 이후) · 실제 가격 결과(POC5-02 배포 · 첫 성숙 뒤) · STEP 미종료
STEP_ID                = POC5-03 PC 원장 동기화 · 선택 평가(받은 알림 기록)
DESIGNER_RESULT        = PASS_TO_USER_CHECK(2026-10-07 · EXTRA_CHANGES 5/5 · SYNC_CONFLICT_POLICY ACCEPTED · FUNCTIONAL_REWORK NONE · STEP_CLOSED NO) — 원문 = 설계서 끝
VERIFIER               = r2 VERIFIED(2026-10-07 · A-1 ~ A-4 통과 · B-1 ~ B-6 없음 · 결과서 §7 문구 · PLAN 말미 공백은 검증자가 직접 정정) · r1 REJECTED(2026-10-07 · A-1 · A-3 · B-1 — ① 원장 기본 표 누락 · 빈 SQLite 를 정상 동기화로 처리 ② 원장 새로고침 뒤 펼친 결과 원장을 다시 읽지 않음) → 정정(§6-3) · STATE_LATEST 메뉴 위치 문구는 검증자가 직접 정정
DESIGN                 = docs/ai_design/POC5/POC5-03_PC_LEDGER_SYNC_AND_FEEDBACK_DESIGN_V1.md (개정 2 · 2026-10-07 · 사용자 목업 결정 반영 · 끝에 결정 이력 원문)
PLAN                   = docs/ai_plan/POC5/POC5-03_PC_LEDGER_SYNC_AND_FEEDBACK_PLAN_V1.md (PASS_TO_IMPLEMENT_WITH_CORRECTIONS · §8 · 개정 2 변경점 §10)
PREDECESSOR/SUCCESSOR  = POC5-02 → POC5-04
BASE_COMMIT(코드 기준)  = f0711340 (POC5-02 커밋)
CODE_FILES             = backend 신규 6(app/ledger_copy 5 · api_decision_ledger) · 수정 2(api.py +2 · conftest +11) · frontend 신규 6 · 수정 5 · OCI 파일 · cron · .env · 의존성 0
TESTS                  = backend 새 파일 67 passed · frontend vitest 전체 25파일 306 passed(새 파일 10 · 메뉴 테스트 13 key · 처리 문구 확정 반영 뒤)
REVIEW                 = backend 독립 검토 1회(읽기 전용) — MEDIUM 2 · LOW 8 · 추측 2 · 테스트 약점 4 → 반영(§6-2) · 검증자 r1 정정은 변이 시험 4종 모두 탐지(§6-3)
KS-10                  = 트리거 0 · api.py 642 → 644(임계 650 아래) · 새 backend 모듈 최대 340 · 새 컴포넌트 최대 177 · 테스트 최대 1,161
BACKEND_FULL_REGRESSION= 3002 passed / 0 failed · exit 0 · 380.99s(2026-10-07 21:20:29 ~ 21:26:51 · r1 정정 뒤 최종 코드) · PC state/logs 1,153파일 해시 전후 동일 · 회귀 시작 뒤 코드 변경 0
USER_SCREEN            = 대기(§7)
```

## 0. 요약

「진단·상태」 `ML 실험` 바로 아래 새 메뉴 `받은 알림 기록`(`alert_records` · MenuKey 12 → 13)을 만들었다. 「오늘의 투자 점검」은 바꾸지 않았다(설계 개정 2 · 사용자 목업 결정).

- **동기화**: `원장 새로고침` 버튼을 눌렀을 때만 PC 가 SSH 1회로 OCI 원장을 읽기 전용 export 한다. OCI 에 파일을 두지 않고 저장소의 `app/ledger_copy/remote_export.py`(표준 라이브러리만)를 `python3 -` 표준입력으로 보낸다. 그래서 OCI pull · cron · `.env` 변경이 없다. 출력(JSONL · ASCII)은 메모리에서 끝까지 검증한 뒤 PC `state/decision/decision_evidence.sqlite` 의 사본 5표에 한 트랜잭션으로 반영한다. 실패하면 기존 사본 · 평가는 그대로다.
- **PC 저장**: 원격 DDL 상수(`ledger_store.DDL` · `ledger_outcome.DDL`)를 그대로 실행한 사본 5표 + PC 전용 `user_feedback`(append-only) · `ledger_sync_attempt`(시도 기록 · 성공은 반영과 같은 트랜잭션). `ledger_store.connect()` 는 쓰지 않는다 — 기존 AI 세션 파일의 권한 · 저널 방식이 바뀌지 않는다.
- **화면**: 날짜별 하루씩(처음엔 사본의 가장 최근 알림 날짜) · 종류 필터 · 카드(시각 · 종류 · 전달 상태 · 핵심 item · 내 평가 또는 '평가 없음') · `자세히 보기`(원문 · 당시 판단 근거 · 선택 평가) · 접기 `신호 결과 원장`(+1/+5/+20 원시 결과 · 평가 여부와 무관).
- **평가는 선택**: 무평가는 '평가 없음'이고 결과 조회 · 저장 · 이후 ML 사용을 막지 않는다(개정 2 · 평가 전 결과 숨김 폐기).

## 1. 처리한 요구사항

설계 개정 2 §8 수용 기준과 설계자 판정 조건 기준.

| 항목 | 상태 | 근거 |
|---|---|---|
| AC1 기동 · 화면 진입 원장 export SSH 0(기존 POC3-07 기동 SSH 예외) | DONE | `test_read_and_feedback_never_ssh`(subprocess 차단 · 조회 · 상세 · 평가 200) · vitest '진입은 사본 조회만'(sync 호출 0) |
| AC2 버튼 1회 = export 1회 · 애플리케이션의 원장 쓰기 0 · 원장 행 불변(SQLite 보조 파일 생성 가능 — 설계자 RESULT 수용) | DONE | `test_sync_runs_one_fixed_ssh_command`(argv 고정 · 1회 · 입력 = 스크립트 bytes · timeout 60) · `test_export_is_read_only_snapshot`(부속 파일 없는 WAL 원장 · 주 파일 sha256 · 행 수 전후 동일 · 출력 ASCII) |
| AC3 반복 반영 중복 0 · 평가 보존 | DONE | `test_sync_is_idempotent_and_keeps_feedback` · `test_started_run_is_updated_once_finalized` |
| AC4 중간 실패 전체 취소 · 기존 자료 유지 | DONE | `test_conflict_rolls_back_whole_sync` · `test_mid_apply_failure_leaves_nothing`(기존 사본 + 평가 + 새 원격 행) · 잘못된 export 21종 · SSH 실패 4종 · 첫 연결 실패 · 성공 기록 실패 · 원장 기본 표 누락 5종 · 결과 표 기록 뒤 누락 · 원격 행 손실 · 원장 교체(r1 정정) |
| AC5 sent · partial 만 목록 · 평가 대상 | DONE | `test_list_shows_only_sent_and_partial` · `test_feedback_is_append_only_and_limited`(skipped · failed · STARTED 409) |
| AC6 미입력 행 0 · 재입력 새 sequence | DONE | 같은 테스트(거부 시 행 0 · seq 1 · 2 · 이전 행 보존) |
| AC7 무평가 결과 조회 · 조회가 평가 행을 만들지 않음 | DONE | `test_outcomes_visible_without_feedback` · vitest '신호 결과 원장 … 평가가 없어도' · '원장 새로고침 뒤 … 다시 읽는다'(r1 정정) |
| AC8 MATURED · 집계 중 · 결측 · 결과 대상 아님 정확 · 무평가 ≠ 부정 | DONE | `test_feedback_changes_neither_outcomes_nor_targets` · `test_outcome_target_for_event_and_item` · `test_market_target_is_sp500_only` · vitest 원장 문구 7종 |
| AC9 메뉴 1개만 · 「오늘의 투자 점검」 · cron · 외부 시세 · OCI 쓰기 · 실 Telegram 0 | DONE | `LeftSidebar.test`(13 key · 진단·상태 순서) · `test_new_modules_have_no_network_or_telegram_imports`(AST · subprocess 는 sync.py 만) · 「오늘의 투자 점검」 파일 diff 0 |
| AC10 API tmp DB · frontend · 전체 회귀 · 라이브 불변 · KS-10 · 사용자 실화면 | PARTIAL | 사용자 실화면 대기(§7) · 나머지 §8 |
| 판정 Q-C 확장 — event · item '결과 대상 아님' | DONE | `views.event_target` · `item_target`(market 은 SP500 만 · POC5-02 와 같음) |
| 판정 — partial 원문 표기 | DONE | 상세 `body_partial_delivery` · 화면 `생성된 원문 — 일부만 전달됨` + `실제 수신된 범위는 확인할 수 없습니다.` · '받은 전문 · 전달된 원문' 0(vitest) |
| 개정 2 — 기본 날짜 = 최근 알림 날짜 · 고른 날짜 유지 · 이전/다음 날 | DONE | `test_default_date_is_latest_alert_day` · `test_default_date_without_copy_is_today` · vitest 날짜 유지 |
| 개정 2 — 미평가 수 · 완료율 · 독촉 0 | DONE | vitest 카드 테스트 |
| OCI 실데이터 동기화 확인 | SKIPPED | 설계 §10 — 원장 첫 활성(2026-10-08 08:30) · POC5-02 배포 뒤 사용자 버튼으로 확인(§5-1) |

## 2. 변경된 파일 목록

backend

- `app/ledger_copy/__init__.py`: 신규(7)
- `app/ledger_copy/remote_export.py`: 신규(78) — OCI 에서 표준입력으로 실행되는 읽기 전용 export
- `app/ledger_copy/sync.py`: 신규(269) — SSH 1회 · export 검증 · 반영 · 실패 기록 · 잠금
- `app/ledger_copy/store.py`: 신규(340) — 사본 DDL · `apply_export` · `add_feedback` · `record_failure` · `sync_status`
- `app/ledger_copy/views.py`: 신규(299) — 목록 · 상세 · 기본 날짜 · 결과 대상 · 상태 라벨 · 이름
- `app/api_decision_ledger.py`: 신규(181) — `/decision-ledger` router 4개
- `app/api.py`: 수정(642 → 644 · import 1 · include 1)
- `tests/conftest.py`: 수정(615 → 626 · `_isolated_decision_ledger` 에 PC 사본 · 이름 조회 경로 tmp)
- `tests/test_poc5_03_ledger_copy.py`: 신규(1,161)

frontend

- `frontend/app/components/AlertRecordsView.tsx`: 신규(177)
- `frontend/app/components/alert_records/AlertCard.tsx`: 신규(152)
- `frontend/app/components/alert_records/FeedbackForm.tsx`: 신규(103)
- `frontend/app/components/alert_records/SignalOutcomeLedger.tsx`: 신규(168)
- `frontend/app/components/alert_records/format.ts`: 신규(130)
- `frontend/app/components/AlertRecordsView.test.tsx`: 신규(409)
- `frontend/lib/api/decisionLedger.ts`: 신규(165)
- `frontend/lib/api/index.ts`: 수정(+1 export)
- `frontend/app/components/LeftSidebar.tsx`: 수정(MenuKey · 메뉴 · 무결성 목록 `alert_records`)
- `frontend/app/components/LeftSidebar.test.tsx`: 수정(12 → 13 key · 진단·상태 순서 · 라벨 · 힌트)
- `frontend/app/components/MainPanel.tsx`: 수정(라우트 1)
- `frontend/app/globals.css`: 수정(`.ar-*` 블록 · CSS 는 KS-10 컴포넌트 기준 밖)

문서

- `docs/ai_design/POC5/POC5-03_PC_LEDGER_SYNC_AND_FEEDBACK_DESIGN_V1.md`: 신규(개정 2 본문 + 결정 이력 원문)
- `docs/ai_plan/POC5/POC5-03_PC_LEDGER_SYNC_AND_FEEDBACK_PLAN_V1.md`: 신규(§8 판정 · §9 사용자 결정 · §10 개정 2 변경점)
- `docs/ai_result/POC5/POC5-03_PC_LEDGER_SYNC_AND_FEEDBACK_RESULT.md`: 신규(이 문서)
- `docs/ai_plan/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_PLAN_V1.md`: 수정(Q23 · Q24 · §2-8 · §3-2 행에 '대체' 표시 — 설계 개정 2 §13 지시)
- `docs/PROGRAM_TRUTH.md`: 수정(머리 · §3 · §4 · §5.1 · §5.2 · §6.1 · §7.1 · §9 · §11 · §12 · 부록 A)
- `docs/STATE_LATEST.md`: 수정(머리)

## 3. 신규 추가된 의존성

없음.

## 4. 지시문 외 변경

1. **동기화 응답 · 시도 기록에서 price_outcome 반영 수와 `outcome_table` 을 뺐다** — 검토 지적(피드백 전 결과 존재 여부 노출). PLAN §2-3 응답 형태와 다르다 → 설계 개정 2 §3 이 '수용 · 다시 넣지 않음'으로 확정.
2. **상세 응답에 `state_label` · `prev_state_label` 을 더했다** — '당시 판단 근거'의 상태를 코드(`D10_PLUS` 등)가 아니라 알림 본문이 이미 쓰는 기존 라벨표(`holdings_risk.RISK_STATE_LABEL` · `SURGE_STATE_LABEL` · `holdings_selection.DECLINE_STATE_LABEL` · `sector_signal.STATE_LABEL`)로 보이려고. 같은 코드 `D10_PLUS` 가 '전일 대비 하락'과 '20거래일 하락'에 함께 있어 알림 종류 · subject 로 표를 고른다. 라벨표가 없는 값(시장 전망 `UP` · `DOWN` · `FLAT`)은 코드 그대로다. 새 라벨을 만들지 않았다.
3. **화면 문구 중 설계서에 없는 것**: 처리(disposition) 6종 — 설계자 RESULT 판정(2026-10-07)의 확정 표현으로 반영: `알림 본문에 포함` · `반복 알림 생략` · `구역별 항목 수 제한으로 제외` · `하루 알림 횟수 제한으로 제외` · `이번 알림에 포함 안 됨` · `자료 문제로 판단 보류`(`format.ts :: DISPOSITION_LABEL` · vitest 로 고정), 카드 `예정 외 실행`, 메뉴 힌트 '받은 알림 · 당시 근거 · 이후 결과', 평가 저장 결과 '저장했습니다' · '저장하지 못했습니다 — …'. 메뉴 힌트 · `예정 외 실행` · 원장 문구는 개정 목업에서 사용자가 확인했다. 처리 6종 중 목업에 없던 4종은 설계자 판단 항목(§7).
4. **마스터 PLAN Q23 의 '메뉴 13 유지' 문장** — 실제 MenuKey 는 12개였다. 대체 표시에 '12 → 13 · 위 문장도 대체'로 적었다.
5. **비공개 이름 재사용** — `ledger_store._FINAL_FIELDS`(확정 갱신 허용 열) · `ledger_outcome._TARGET_KINDS`(결과 대상 subject) · `oci_startup_status._ssh_key_opts`(SSH 키 옵션). 같은 계약을 복사하지 않으려고 원본을 그대로 쓴다.

## 5. 알려진 한계 / 미완성

1. **OCI 실데이터 동기화는 아직 확인하지 못했다** — OCI 원장 폴더가 아직 없다(읽기 전용 확인 · 2026-10-07 · 첫 활성 실행 2026-10-08 08:30). 지금 버튼을 누르면 `NO_REMOTE_LEDGER` 실패가 정상이다. `price_outcome` 은 POC5-02 OCI 배포와 첫 08:10 성숙 뒤에 생긴다(그 전 export 는 '표 없음'으로 정상 처리).
2. **OCI 원장 폴더에 `-wal` · `-shm` 이 생길 수 있다**(설계자 RESULT 수용 — '애플리케이션의 원장 쓰기 0 · 원장 행 불변 · SQLite 보조 파일 생성 가능') — 읽기 전용(`mode=ro`) 연결이 부속 파일 없는 WAL 원장을 열면 SQLite 가 만든다(주 파일 불변 · 권한은 원장과 같음 · 다음 러너 연결이 정리 · 기존 대조 CLI 와 같음). OCI python3 3.12.3 · SQLite 3.45.1(읽기 전용 확인)은 이 상태를 읽을 수 있다. 맥 시스템 python3 3.9(Apple SQLite)는 부속 파일이 없으면 열지 못하지만 OCI 와 무관하다.
3. **`CONFLICT` 가 한 번 나면 화면에서 고칠 방법이 없다** — PC 사본의 확정 행이 원격과 다르거나, PC 사본의 행이 원격에 없을 때다(원격 원장 손실 · 교체 · PC 사본을 손으로 바꾼 경우). 원격은 행을 고치거나 지우지 않으므로 정상 운영에서는 생기지 않는다. 기존 사본은 그대로 보인다 — 원장을 새로 만들어야 하는 경우의 사본 정리 절차는 아직 없다.
4. **원장 스키마(열)가 바뀌면 PC 와 OCI 코드가 같아야 동기화된다** — 열 집합이 PC 표와 정확히 같아야 받는다(부분 열 행이 다음 동기화를 영구 충돌로 만드는 것을 막기 위해).
5. **전체 export(V1)** — 설계 §3. 1년 규모(코드 근사 수십 MB)에서는 60초 timeout 이 부족할 수 있다. 실제 크기로 문제가 확인되면 증분을 다룬다.
6. **Windows PC 미확인** — 실측은 맥북만. 권한 · 저널을 바꾸지 않아 Windows 고유 실패 경로는 없다고 보지만 실행은 안 했다.

## 6. 다음 검증자(Codex)에게 알릴 점

### 6-1. 판단이 어려웠던 부분

1. **export 위치** — OCI 저장소에 스크립트를 두면 POC5-03 코드를 OCI 에 pull 해야 한다(설계 §10 'OCI pull 없음'과 충돌). PC 가 저장소 파일을 표준입력으로 보내는 방식을 택했다(셸 인용 없음 · 로컬 테스트로 같은 파일을 실행).
2. **반영 경계** — `evaluation_run` 은 PC 사본이 `STARTED` · 원격이 `FINALIZED` · 시작 열(`_FINAL_FIELDS` 밖 · `run_state` 제외)이 같을 때만 원격 행으로 갱신한다. 나머지 표와 확정 run 은 '같으면 통과 · 다르면 충돌(전체 롤백)'. PC 사본에만 있는 행이 있으면 충돌이다(r1 정정 · §6-3 — 원격은 지우지 않으므로 원장 손실 · 교체 신호 · PLAN §2-2 '지우지 않는다' 는 유지하되 받아 넘기지 않는다).
3. **성공 기록 위치** — `ledger_sync_attempt` ok=1 행을 `apply_export` 의 같은 트랜잭션에서 넣는다. 실패 기록만 롤백 뒤 별도 트랜잭션.
4. **화면 effect** — `AlertRecordsView` 는 처음 날짜 없이 조회하고 응답 `date` 로 날짜를 채운다. 날짜를 채운 뒤 같은 조회를 다시 하지 않으려고 `loadedKey` ref 로 막는다(vitest 가 첫 진입 조회 1회를 단언). 단 개발 모드(React StrictMode)는 effect 를 두 번 돌려 첫 조회가 2번 나간다 — dev 서버 로그 실측 `GET /decision-ledger/alerts?kind=all` 2줄(19:55). 조회(GET)만이라 결과는 같다.

### 6-2. 독립 검토(2026-10-07 · backend · 읽기 전용 · tmp 재현) 반영

| 지적 | 반영 |
|---|---|
| MEDIUM-1 본문의 U+2028 · U+2029 · U+0085 가 JSON 줄을 잘라 그 뒤 동기화 영구 실패 | 원격 출력 `ensure_ascii=True` + PC 는 `b"\n"` 으로 나눔 · `test_line_separator_characters_survive` |
| MEDIUM-2 성공 기록이 반영 트랜잭션 밖 → 화면이 '새로고침 필요'로 보일 수 있음 | 같은 트랜잭션으로 · `test_success_record_is_part_of_the_copy_transaction` |
| LOW-3 원격 stdout 인코딩이 locale 에 의존 | ASCII 출력으로 해소 |
| LOW-4 부분 열 · 타입 · NaN · Infinity 통과 | 열 집합 일치 · 선언 타입 검사(bool 거부 · INTEGER 범위 · 유한 REAL) · `parse_constant` 거부 · 잘못된 export 테스트 8종 추가(21종) |
| LOW-5 STARTED 사본을 아무 행으로 갱신 | FINALIZED · 시작 열 일치 때만 · `test_started_copy_only_accepts_its_finalize` 3종 |
| LOW-6 RecursionError · OverflowError 오분류 · 스크립트 읽기 오류가 SSH 실패로 | `INVALID_EXPORT` 로 · 스크립트 읽기는 SSH 시도 밖 |
| LOW-7 동기화 응답의 결과 반영 수 노출 | 제거(§4-1 · 개정 2 수용) |
| LOW-8 날짜 파라미터 이름이 PLAN 과 다름(`day`) | `date` 로 |
| LOW-9 partial 표기 필드 없음 | `body_partial_delivery` |
| LOW-10 market 대상 판정이 POC5-02 와 다를 수 있음 | SP500 만 · `test_market_target_is_sp500_only` |
| 추측 — 이름 조회가 이상한 보유 파일에서 500 | `TypeError` 도 흡수 · `test_name_map_tolerates_odd_holdings_file` |
| 테스트 약점 — 공존 테스트가 빈 표 · 중간 실패가 빈 사본에서만 · 첫 연결 실패 | AI 세션 기록 1건 전후 비교 · 기존 사본 + 평가 + 새 원격 행으로 · `test_first_connect_failure_skips_ssh` |

### 6-3. 검증자 r1 REJECTED(2026-10-07) 정정

| 지적 | 원인 | 정정 · 테스트 |
|---|---|---|
| A-1 · A-3 · B-1 원장 기본 표(`delivery` · `ledger_meta` 등) 누락 · 표 없는 빈 SQLite 를 `ok=true` 로 기록 | `parse_export` 가 표 이름 집합 · boolean 형식만 보고 '없음' 을 빈 자료로 받았다 | `sync.CORE_TABLES`(원장을 처음 열 때 함께 생기는 4표) 가 하나라도 없으면 `INVALID_EXPORT` · `price_outcome` 은 없어도 정상(성숙 전)이지만 `ledger_meta` 에 그 표를 만든 기록(`schema_version.price_outcome`)이 있으면 `INVALID_EXPORT` · `test_normal_empty_ledger_is_ok`(정상 빈 원장 = 4표 0행 · 성공) · `test_missing_core_table_is_not_a_normal_empty_ledger` 5종 · `test_outcome_table_missing_after_it_was_created_is_invalid` |
| 같은 계열(옆칸) — 원격이 행을 잃었거나 원장이 새 파일로 바뀌어도 PC 사본에만 있는 행을 두고 정상 처리 | PLAN §2-2 가 'PC 에만 있는 행은 지우지 않는다' 만 정하고 받아 넘겼다 | `store._check_nothing_lost` — 반영 트랜잭션 안에서 사본 키가 export 에 모두 있는지 확인 · 없으면 `CONFLICT`(지우지도 덮지도 않음) · `test_rows_missing_from_remote_are_a_conflict`(행 1개 손실 · 원장 교체) |
| A-3 원장 새로고침 뒤 알림 ID · 평가 수가 같으면 펼친 `신호 결과 원장` 이 상세를 다시 읽지 않아 이전 `집계 중` 이 남음 | 다시 읽는 조건이 `event_id#feedback_count` 뿐이었다 | 화면이 목록을 다시 읽을 때마다 바뀌는 `refreshKey`(새로고침 · 평가 저장)를 `SignalOutcomeLedger` 와 열린 `AlertCard` 상세 둘 다에 넘김 · vitest '원장 새로고침 뒤 펼친 신호 결과 원장 · 열린 상세를 다시 읽는다' |

- 변이 시험(정정을 되돌린 상태에서 새 테스트가 실패하는지 · 2026-10-07): 기본 표 검사 제거 → 5 실패 · 결과 표 기록 검사 무력화 → 1 실패 · 손실 검사 제거 → 1 실패 · `refreshKey` 의존 제거 → 1 실패. 4종 모두 탐지.

반영하지 않은 것: 동시 평가 저장 seq 경쟁 테스트(검토자가 20스레드로 seq 1~20 유일 실측 · `BEGIN IMMEDIATE`) · 기동 SSH 0 의 문자열 검사(실제 방어는 전역 subprocess 차단 테스트).

## 7. 사용자 확인이 필요한 항목

1. **실화면 확인** — 「진단·상태 > 받은 알림 기록」. 지금은 PC 사본이 없어 `원장 새로고침이 필요합니다` 가 정상이다. 처음 열면 PC `decision_evidence.sqlite` 에 사본 표가 생긴다(설계된 동작).
2. **원장 새로고침 버튼** — 지금 누르면 OCI 원장이 아직 없어 '실패'(`NO_REMOTE_LEDGER`)가 정상이다. 2026-10-08 08:30 이후 누르면 08:30 시장 브리핑부터 보인다. 가격 결과는 POC5-02 배포 뒤 다음 거래일부터 채워진다.
3. **처리 문구**(사용자 2026-10-07: "이 부분은 설계자가 판단하는게 맞을 것 같아요") — 설계자 RESULT 판정의 확정 표현 6종으로 반영했다(§4-3). 실화면에서 '자세히 보기 > 당시 판단 근거 > 처리' 칸으로 확인.

## 8. 검증 실측 (2026-10-07)

### 8-1. 테스트

- `tests/test_poc5_03_ledger_copy.py`: **67 passed**
- frontend `npx vitest run`: **25 files · 306 passed**(새 `AlertRecordsView.test.tsx` 10 · `LeftSidebar.test.tsx` 14 · `MainPanel.test.tsx` 1 포함 · 처리 문구 확정 반영 뒤)

### 8-2. 정적 검사

- `black --check` · `flake8` · `py_compile`: 새 · 수정 backend 파일 모두 통과
- `npx tsc --noEmit` · `npx eslint`(새 · 수정 frontend 파일): 통과

### 8-3. OCI 읽기 전용 확인(SSH · 쓰기 0)

- `python3` 3.12.3 · SQLite 3.45.1 · `venv/bin/python` 3.12.3 · SQLite 3.45.1 · `state/decision` 없음(2026-10-07)

### 8-4. KS-10 · 줄 수

- §2 줄 수 · `app/api.py` 644(임계 650 아래) · 새 backend 모듈 최대 `store.py` 340 · 새 컴포넌트 최대 `AlertRecordsView.tsx` 177 · 새 테스트 최대 1,161(단일 Step)

### 8-5. 백엔드 전체 회귀 · 라이브 보호

- 최종(r1 정정 뒤): `.venv/bin/python -m pytest -q -p no:cacheprovider` → **3002 passed · exit 0 · 380.99s**(2026-10-07 21:20:29 시작 · 21:26:51 끝) · 회귀 전후 PC `state/` · `logs/` 1,153파일 sha256 **동일**(r1 제출 때 회귀 = 2994 passed · exit 0 · 20:00:03 ~ 20:06:25 — 늘어난 8 = 새 테스트).
- 첫 회(19:52 ~ 19:58)는 2994 passed 였지만 **exit 1** 이었다 — 테스트 세션 라이브 가드가 `stat:state/decision/decision_evidence.sqlite` 변경을 잡았다. 원인은 테스트가 아니라 실행 중인 dev backend(uvicorn · 8000)다: 그 사이 사용자가 새 메뉴를 열어 `GET /decision-ledger/alerts?kind=all` 2건(dev 로그 실측)이 들어왔고, 첫 조회가 PC 파일에 사본 표를 만들었다(설계된 동작 · `ledger_sync_attempt` 0행 · `evaluation_run` 0행 · `ai_session_records` 0행 그대로). 테스트 프로세스가 라이브 DB 를 열었다면 가드가 그 테스트를 실패시킨다(전부 통과). 그래서 화면을 열지 않은 상태로 다시 돌린 위 결과를 최종으로 쓴다.

## 9. git 상태

`git status --short --untracked-files=all`(보고 직전 실측 · 커밋 전):

- staged **27** = 신규(`A`) 17 · 수정(`M`) 10 · unstaged 0
- `??` 1 = `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` — 사용자 소유 · 이 작업과 무관 · stage 하지 않는다
- 배포 경로(OCI) 파일 0 — OCI 는 `remote_export.py` 를 표준입력으로 받을 뿐 파일을 두지 않는다
