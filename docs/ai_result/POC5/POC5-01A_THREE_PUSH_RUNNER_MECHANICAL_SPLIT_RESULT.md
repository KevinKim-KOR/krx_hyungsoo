# POC5-01A 개발 결과서 — THREE_PUSH_RUNNER_MECHANICAL_SPLIT

작성 2026-10-03 · 갱신 2026-10-04(독립 검토 반영 · 설계자 RESULT 판정 반영 · 검증자 재검증 VERIFIED 기록) · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex)

```text
STATUS                 = IMPLEMENTED_VERIFIED — 커밋 · push 사용자 승인(2026-10-04) · OCI pull(사용자) · 첫 거래일 확인 대기(§11)
DESIGNER_RESULT        = PASS_TO_VERIFIER (2026-10-04 · 코드 재작업 없음 · 지시문 외 변경 4건 수용 · __context__ 차이 수용 · 원문 = 설계서 끝)
STEP_ID                = POC5-01A 세 PUSH 러너 기계 분리
DESIGN                 = docs/ai_design/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_DESIGN_V1.md
PLAN                   = docs/ai_plan/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_PLAN_V1.md (설계자 재판정 PASS 2026-10-03)
PREDECESSOR/SUCCESSOR  = POC3-02D-OPS-03 / POC3-02D-OPS-04 → POC5-01B
BASE_HEAD(구현 기준)    = a0a2c5141f258554074de7f02c6985c0d2af3b0f (선행 문서 커밋 · 코드 변경 0)
BASELINE_RUNNER_BLOB   = f256677020232600627d207c54baf5081c70c6e2 (§3-1 기준점 4단계 통과 · §8-1)
RUNNER_LINES           = 646 → 517 (KS-10 근접 해소)
EQUIVALENCE            = 49 시나리오 · 종료 27곳 전부 · 다름 0(기준 대 작업 트리) · 기준 대 기준 다름 0 · 정적 문제 0 · 라이브 차단 0
RUNNER_TESTS           = 러너 구동 16파일 305 passed — 분리 전 · A · B · D/E 단계마다 같음 · 테스트 파일 변경 0
SABOTAGE               = 10종 전부 동등성 스크립트가 탐지 · 기존 테스트만으로는 4종(§8-5)
VERIFIER               = VERIFIED (재검증 2026-10-04 · 위험 NONE · 범위 폭주 NONE) ← r1 REJECTED(A-2 · A-3 — 러너에 쓰는 이름 '13개' → 실제 14개 · `is_already_sent` 누락) → 정정(§6-8 · 런타임 전수 기록 14개)
INDEPENDENT_REVIEW     = 3관점 · 지적 15 · 확정 8(검증자 2명 모두 인정) — 동등성 관점 지적 0 · 확정 8건은 검증 스크립트 · 문서 정확성(§6-6 · 모두 반영)
CONTRACT_DIFFERENCE    = 운영 계약 차이 0.
                         단, PARAM 실패와 insert_status 실패가 겹친 경로에서
                         traceback __context__ 연결 차이 1건이 있으며 §6-1에 기록했다.
BACKEND_FULL_REGRESSION= 2709 passed / 0 failed · exit 0 · 370.41s (최종 코드 · 2026-10-04 11:31) · PC state/logs 229파일 hash 전후 동일
CODE_FILES             = 5 (신규 4 = 운영 모듈 3 + 검증 스크립트 1 · 수정 1 = 러너) · 테스트 0 · DB · cron · 스키마 0
```

## 0. 요약

`scripts/run_three_push_runtime_oci.py` 의 `run()` 안 네 블록(설계 STEP 6 우선순위 1~5 · PLAN Q1 (a) A · B · D · E)을
`app/three_push_runtime/` 새 모듈 3개로 **문장 순서 그대로** 옮겼다. 러너에는 `run()` · CLI · 가격 조회 · spike 신선도(테스트
고정) · §4 · 금지 문구 · dry-run · flag guard · 중복 · 발송 · `_finish` closure(1문장)가 남는다.

테스트가 러너 모듈에서 바꿔 끼우는 이름 14개(PLAN 1-8 · 전체 테스트 런타임 전수 기록)는 다음처럼 처리했다. 그래서 테스트 변경 0 으로 통과한다.
- 7개(`_HISTORY_PATH` · `insert_status_from_record` · `read_active_param_dict` · `param_from_dict` · `kst_today` · 상태 경로 2개): 쓰는 코드가 새 모듈로 갔고, 러너가 호출 때 인자로 넘긴다.
- 7개(`telegram_send` · `_collect_target_tickers` · `kst_now_iso` · `kst_today_date` · `build_runtime_message` · `mark_sent` · `is_already_sent`): 쓰는 코드가 러너에 그대로 남는다.

운영 계약이 같다는 것은 두 가지로 보였다. 하나는 분리 전 러너(blob 고정)와 작업 트리 러너를 한 프로세스에서 같은 대역으로 돌려 비교하는 검증 스크립트다. 다른 하나는 3관점 독립 검토(동등성 관점 지적 0)다. 운영 계약 차이는 0 이다. 단, PARAM 실패와 insert_status 실패가 겹친 경로에서 traceback __context__ 연결 차이 1건이 있으며 §6-1에 기록했다(설계자 RESULT 판정에서 진단 차이로 수용).

---

## 1. 처리한 요구사항

| # | 요구사항(설계 STEP · PLAN) | 결과 | 근거 |
|---|---|---|---|
| 1 | STEP 5 동작 · 메시지 · 일정 · DB · 상태 스키마 · 외부 호출 · Telegram 변경 0 | DONE | §8-3 동등성 49 다름 0 · §8-4 테스트 305 · cron/DB 파일 무변경 · traceback 예외 문맥 1건 §6-1(설계자 수용) |
| 2 | STEP 6-1 실행 시작 · 종료 기록 조립 | DONE | `runner_record.new_run_record` |
| 3 | STEP 6-2 `_finish` 종료 상태 확정 | DONE | `runner_record.finish_run` · 러너 `_finish` 는 호출 1문장 |
| 4 | STEP 6-3 JSONL · DB 상태 기록 | DONE | `finish_run` 안 원래 순서(apply_intraday_records → 필드 → insert_status → JSONL → 로그) |
| 5 | STEP 6-4 공통 예외 종료 처리 | DONE(Q3 a 범위) | PARAM 예외 → 실패 변환 2곳만 `runner_preflight` 로 · 새 try/except 0 · 최외곽 변환은 POC5-01B |
| 6 | STEP 6-5 push kind 별 dispatch 보조 | DONE | `runner_dispatch.assemble_push_kind` · `decide_after_flag_guard` |
| 7 | STEP 6-6 원장 writer 주입 경계 | DONE(Q4 a 범위) | 식별만 — `new_run_record` 직후 · `finish_run` · `KindAssembly`(각 모듈 docstring) · 빈 hook 0 |
| 8 | STEP 7 `run()` · CLI 유지 · cron 불변 · `app/three_push_runtime/` · 순환 import 금지 · 570줄 이하 | DONE | 517줄 · §8-6 import 70(=67+3) · 외부 패키지 0 · 순환 0 |
| 9 | STEP 7 위장 분리 금지 | DONE | 옮긴 블록 = 기록 · 사전 검사 · kind 조립/판정(각자 책임) · §9 이동표 |
| 10 | STEP 8 조립 순서 · flag/mode/중복/상한 · 본문 byte · status/reason · JSONL 내용과 순서 · DB · 부분 전송 · state 저장 · exit code · 예외 전파 동일 | DONE | §8-3(항목별) · 예외 문맥 1건 §6-1 |
| 11 | STEP 8 기존 테스트 단언 완화 금지 | DONE | `git diff a0a2c514 -- tests/` 0줄 · `tests/conftest.py` blob 불변 |
| 12 | PLAN §3-1 기준점 4단계 | DONE | §8-1 |
| 13 | PLAN §3-1 ④ 14개 이름을 `run()` 전에 바꿔 끼웠을 때 두 러너가 같은 대역을 쓰는지 | DONE | 14개 모두 매 시나리오 기록 대역(§8-3) |
| 14 | PLAN §3-1 ⑤ 정적 검사(14개 이름 직접 import 0 · 모듈 상수 0 · 모듈 전역 logger 0 · 기존 모듈 20개 blob 불변) | DONE | §8-3 `static_problems=0` |
| 15 | PLAN §3-3 파괴 시험 검토 1회 | DONE | §8-5 — PLAN 의 (a) ~ (e) 와 추가 5종 |
| 16 | PLAN §3-2 KS-10 전 파일 재실측 | DONE | §8-6 |
| 17 | PLAN §2-4 문서(PROGRAM_TRUTH · STATE_LATEST · 결과서) | DONE | §2 |
| 18 | 배포 · 첫 거래일 OCI 확인(§4 · §3-2 ⑤) | PARTIAL | 커밋 · push 는 검증자 VERIFIED 뒤 사용자 승인(2026-10-04)으로 진행 · OCI pull(사용자)과 첫 거래일 확인은 남음 — §11 절차 |

## 2. 변경된 파일 목록

| 파일 | 변경 | 줄 |
|---|---|---|
| `scripts/run_three_push_runtime_oci.py` | 수정 | 646 → 517 |
| `app/three_push_runtime/runner_record.py` | 신규 | 91 |
| `app/three_push_runtime/runner_preflight.py` | 신규 | 75 |
| `app/three_push_runtime/runner_dispatch.py` | 신규 | 178 |
| `scripts/poc5_01a/runner_split_equivalence.py` | 신규(검증 전용 · 운영 경로 import 0 · OCI 실행 금지 · 폴더 `__init__.py` 없음) | 597 |
| `docs/PROGRAM_TRUTH.md` | 수정 — 머리 '최종 반영'(검증자 VERIFIED · OCI pull 대기) · §4 진입점 행 · C-1 근거 · 부록 A `_finish` 행 · OCI runner 목록 · PARAM 전달 관찰 단서 3곳(프로세스 B · §12 · 적용 항목 · §7-4) | |
| `docs/STATE_LATEST.md` | 수정 — 머리 '최종 업데이트' · POC5 '다음' 줄(검증자 VERIFIED · 설계자 항목 1건) | |
| `docs/backlog/BACKLOG.md` | 수정 — §11 설계자 판단 요청 1건 등재(PARAM '적용'이 OCI JSON 만 교체 · §7-4) | |
| `docs/ai_plan/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_PLAN_V1.md` | 수정 — '23키' 오기 3곳을 21키로(§4-2) | |
| `docs/ai_result/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_RESULT.md` | 신규(이 문서 · `docs/ai_result/POC5/` 폴더도 신규) | |
| `docs/ai_design/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_DESIGN_V1.md` | 수정 — 끝에 설계자 RESULT 판정 원문 기록(2026-10-04) | |

선행 문서 커밋 `a0a2c514`(설계 정정 · PLAN · 판정 원문 · OPS-03 후속 배포 확인 · 코드 0)는 이 구현과 분리된 커밋이다(설계자 지시).

## 3. 신규 추가된 의존성

없음(검증 스크립트는 기존 `pytest.MonkeyPatch` · `tests/_live_guard` · 표준 라이브러리만 쓴다).

## 4. 지시문 외 변경

설계자 RESULT 판정(2026-10-04)에서 아래 4건 모두 **수용**됐다.

1. **`KindAssembly` 필드 1개가 PLAN §2-1 과 다르다** — PLAN 의 `intraday` 대신 `risk_assembly`(장중 조립 결과 객체 그대로)를 둔다. 이유: 원래 러너는 `_rasm.intraday` 를 §3-d 가 아니라 §6-c 판정 시점(분리 전 449행)에 읽는다. 객체를 그대로 들고 있다가 같은 시점에 `.intraday` 를 읽어야 속성 조회 시점이 그대로다(`decide_after_flag_guard`). 나머지 필드는 PLAN 과 같다.
2. **PLAN 사실 오기 정정** — 'record 23키'는 21키다(분리 전 blob 148~170행 AST · `new_run_record` 반환 모두 21). PLAN 1-1 · 2-1 · 2-2 ④ 세 곳을 21키로 고치고 정정 표시를 남겼다(계약 내용 변경 아님). `runner_record.new_run_record` docstring 도 21키다.
3. **검증 스크립트 시각 정규화 키 1개 추가** — PLAN §3-1 ④ 는 `started_at` · `finished_at` · 등록부 `sent_at_utc` 3개를 적었다. DB 두 표의 `inserted_at` 도 실제 시계(`utc_now_iso`)라 4개로 둔다. 그 밖의 값은 정규화하지 않는다(키 단위 · §5-3).
4. **검증 스크립트의 기존 모듈 blob 출처** — PLAN 1-0 표 20개를 상수로 두지 않는다. PLAN 실측 커밋 `7d507951` 에서 `git ls-tree` 로 읽는다. 값은 PLAN 표와 20/20 같다(2026-10-04 대조).

## 5. 알려진 한계 / 미완성

1. **조립 대역**: 동등성 스크립트는 보유 · 장중 · 시장 조립 함수와 spike evidence 를 같은 가짜로 대신한다(옮긴 코드 = 조립 결과를 다루는 오케스트레이션). 실제 조립 함수는 blob 불변(20개)이고, 실제 흐름은 러너 구동 테스트 16파일(305)과 전체 회귀가 덮는다.
2. **미포착 예외 경로는 그대로다**(Q3 a). 발송 뒤 `mark_sent` 예외 · 조립 예외 · `insert_status` 예외는 지금처럼 `run()` 밖으로 빠지고 DB · JSONL 행이 남지 않는다(동등성 M14 · M15 · M16 · H13 에서 두 러너가 같은 예외로 끝남). POC5-01B 최외곽 확정이 맡는다.
3. **시각 키 4개는 비교에서 가린다** — 그 키에 엉뚱한 시계 값을 넣는 결함(예: `finished_at` = `started_at`)은 동등성 스크립트가 잡지 못한다. 해당 줄(`finish_run` 의 `datetime.now(timezone.utc)`)은 분리 전 문장 그대로이고 독립 검토 동등성 관점이 확인했다.
4. **시나리오 공백 1**: 장중 '사유는 있는데 본문도 있는' 조합(§6-c `and not message_text`)을 다루는 시나리오가 없다. 그 조건 줄을 지우는 변경은 동등성 스크립트가 잡지 못한다(독립 검토 재현). 해당 줄은 분리 전과 같은 문장이다.
5. **종료 지점 기대값**: 스크립트는 두 러너가 같은지만 판정한다. 시나리오가 노린 종료 지점에 닿았는지는 출력(status/reason)과 §8-3 표의 대조로 확인했다(스크립트가 단언하지 않음).
6. **배포 전**: OCI 는 분리 전 러너(blob `f2566770…` · 2026-10-02 OCI 읽기 확인)로 돈다. 첫 거래일 확인은 pull 뒤(§11).

## 6. 다음 검증자(Codex)에게 알릴 점

1. **예외 문맥(`__context__`) 차이 1건**: B 단계에서 `param_load_error` · `param_secret_exposed` 의 `_finish` 호출이 `except` 블록 **밖**으로 나왔다(`runner_preflight` 가 실패 튜플을 돌려주고 러너가 `_finish(*fail)` — PLAN §2-1 시그니처 · 기존 `runner_evidence` 와 같은 규약). 그 경로에서 `insert_status_from_record` 가 다시 예외를 내면, 전파되는 예외 종류 · 메시지 · 전파 여부는 같다. 다만 traceback 의 'During handling of the above exception…' 연결(원래 PARAM 예외)이 없어진다. 운영 기록(DB · JSONL · status) 차이는 없다.
2. **이름 조회 시점(PLAN 1-8 표 7 · 8 · 10 · 11 · 12 · 13)**: 같은 호출 안에서 블록 입구로 당겨졌다. 동등성 스크립트는 14개 이름 전부를 매 시나리오 `run()` 전에 러너 모듈에 바꿔 끼운다. 함수 11개는 호출 기록 대역으로 감싸고, 경로 3개는 tmp 로 바꾼다. 이 상태로 두 러너를 비교한다. `kst_today` 는 러너 대역 `2099-01-02` · 원래 모듈(`holdings_selection_state`) 대역 `2099-01-03` 으로 서로 달라서, 러너 전역을 거치지 않는 경로(별칭 import · 모듈 속성 · 값 미리 계산)가 드러난다(§8-5 (b) · (b′) · (f)).
3. **import 순서**: 새 모듈을 통해 `holdings_risk_flow` · `holdings_selection_flow`(`runner_record` · `runner_dispatch`)와 `registry_key`(`runner_preflight`)가 조금 일찍 import 된다. `runner_evidence` · `runner_spike` 는 상대적으로 뒤로 간다. 모듈 집합은 67 + 새 3 = 70 으로 같다(§8-6). 이 모듈들의 머리에는 파일 · 환경변수 부수효과가 없다.
4. **spike 경로**(폐지 · cron 0)는 러너에 그대로 둔다 — §3-a2 는 `tests/test_oci_market_data_refresh.py:316-327`(`getsource(runner.run)`)이 위치를 고정한다.
5. **검증 스크립트 만들며 고친 빈 곳**(도구 자체 검증 · 파괴 시험 · 독립 검토에서 발견 — 운영 코드 결함 아님): ① 러너 안에서 만든 함수의 모듈 이름이 비교값에 섞임 → `<RUNNER>` 정규화 ② 보유 선정 상태 저장이 자기 모듈 시계(초 단위)를 써 흔들림 → 그 모듈 시계 대역 ③ `kst_today` 대역이 실제 날짜 · 원래 모듈 대역과 같아 우회가 안 보임 → 서로 다른 날짜 ④ 정적 검사가 좁음 → 14개 이름의 원래 (모듈, 이름)을 분리 전 러너 import 문에서 읽어 원래 이름 import · 모듈 속성 접근 · 상태 파일 이름 상수 · logger 생성까지 검사 ⑤ `build_runtime_message` 등 일부 이름을 바꿔 끼우지 않음 → 14개 모두(⑧ 포함) ⑥ H12 '비거래일 + kind 꺼짐' 복원 ⑦ UTC 문자열 전체 정규화 → 키 4개만 ⑧ 고정 이름 목록에 `is_already_sent` 누락(검증자 r1) → 추가(§6-8).
6. **독립 검토(2026-10-04 · 읽기 전용 · 3관점)**: (A) 분리 전후 동등성 (B) 검증 스크립트 타당성 · 안전 (C) 결과서 · 문서 정확성. 지적 15건마다 반박 기본 검증자 2명을 붙였다. **(A) 지적 0**. 확정 8건(2명 모두 인정) = 검증 스크립트 3(⑤의 ③ · ④ · 파괴 시험 (b) 정의) · 문서 5(21키 · 고정 이름 처리 표현 · `build_runtime_message` 미대역 · pull 시각 15:40 → 15:45 · `KindAssembly` 필드 미기재). 모두 반영했다. 검증자 1명만 인정한 문서 표현 3건(PROGRAM_TRUTH '예외 전파 변경 0' · §9 인용 · import 순서 기술)도 반영했다.
8. **검증자 r1 반려(2026-10-04 · A-2 보고 정확성 · A-3 산출물 정합성) 처리**: 테스트가 러너에서 바꿔 끼우는 이름은 13개가 아니라 14개였다.
   - 빠진 이름: `is_already_sent` — `tests/test_poc3_02d_ops01_holdings_risk_flow.py:590` 의 `monkeypatch.setattr(rig["runner"], …)`.
   - 놓친 이유: 첫 AST 스캔은 `runner` 같은 이름 변수만 봤다. 그래서 딕셔너리 원소 형태를 놓쳤다. poc4 파일을 빼서 `tests/test_poc4_02b_runner_guards.py:76 · 159` 의 상태 경로 교체 위치도 빠졌다.
   - 다시 센 방법: 전체 테스트를 돌리며 러너 모듈의 모든 속성 쓰기를 런타임에 기록했다(import 순간 모듈 클래스를 기록용으로 바꾸는 관찰 플러그인 · scratchpad · 저장소 밖 · 동작 변경 없음 · 2709 passed · 2026-10-04 12:09:40 ~ 12:15:47). 결과는 **정확히 14개**다.
   - 이름별 고유 호출 위치 · 파일 수: `telegram_send` 30 · 12 · `_collect_target_tickers` 17 · 8 · `_HISTORY_PATH` 12 · 9 · `HOLDINGS_SELECTION_STATE_PATH` 12 · 6 · `kst_today_date` 7 · 3 · `kst_now_iso` 4 · 3 · `HOLDINGS_RISK_STATE_PATH` 4 · 3 · `build_runtime_message` · `insert_status_from_record` · `param_from_dict` · `read_active_param_dict` 각 2 · 2 · `kst_today` · `mark_sent` · `is_already_sent` 각 1 · 1(conftest 포함).
   - 코드 영향: 없다 — `is_already_sent` 는 분리 전 534 · 550행 그대로 러너 §7 에 남아 기존 helper 에 인자로 넘긴다((가) 러너 잔류 · 결합 시점 같음).
   - 고친 것: PLAN §1-8 표(14행 추가 · 건수를 런타임 실측으로 · 정정 표시) · 검증 스크립트 고정 이름 목록 · 기록 대역(`is_already_sent` 포함 14개 전부) · 이 결과서의 '13개' 전부.
   - 다시 검증: 기준 대 기준 · 기준 대 작업 트리 2회 다름 0 · 정적 문제 0 · 파괴 시험 (h) · (i) 추가 탐지.
9. **검증 스크립트 의존**: `git`(blob 읽기 · `ls-tree`) · 저장소 · `tests/_live_guard`(테스트용 모듈 import) · `.venv` 의 pytest. 실행 = `python scripts/poc5_01a/runner_split_equivalence.py [--self-check] [--only 이름조각]`.

## 7. 사용자 확인이 필요한 항목

1. **커밋 · push**: 검증자 재검증 `VERIFIED` 뒤 사용자가 커밋과 push 를 함께 승인했다(2026-10-04). 선행 문서 커밋 `a0a2c514` 와 이 구현 커밋(코드 5 + 문서 6)이 같이 push 된다. OCI pull 은 사용자 몫이다.
2. **OCI pull 시각**: 설계자 RESULT 판정 · 검증자 뒤에 한다. 거래일 08:05 ~ 15:45 는 금지다(PLAN §4). 2026-10-03(토) ~ 10-05(월)은 휴장이다(10-05 는 거래일 캘린더 `krx_trading_days_2026.csv` 에 없고, 2026-10-02 다음 행이 10-06). 그 사이 pull 하면 첫 거래일 확인은 10-06(화)이다.
3. **사용자 소유 문서**: 두 문서 모두 내용을 고치지 않았다.
   - `docs/handoff/POC5-00_INVESTMENT_MODEL_V2_MASTER_DESIGNER_HANDOFF_2026-10-03.md` 는 구현 전부터 있던 사용자 소유 staged 문서였다. 사용자 승인으로 선행 문서 커밋 `a0a2c514` 에 들어갔고, 코드 변경 수에 넣지 않았다.
   - `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` 는 그대로 untracked 다(손대지 않음).
4. **관찰(이번 작업과 무관)**: (사용자 화면 조작 — 사용자 확인 2026-10-04) 2026-10-04 11:09 KST 에 PC 화면 경로로 새 PARAM `param-20261004T020942-999570`(`approved_by: user` · `POST /three-push/param/apply`)이 만들어졌다. 그 PARAM 은 OCI 동기화 · 검증까지 성공했다. 11:11 에는 시장 데이터 갱신 흔적(KOSPI 정정 증거 · NAV 갱신 파일)이 생겼다. 사용자가 직접 조작한 것으로 확인됐다.
   - 에이전트 명령 475개 · 이번 작업 명령에는 API 호출 · ssh 쓰기 · PARAM 스크립트 실행이 없다.
   - OCI 읽기 확인 결과: 러너가 읽는 활성 PARAM(DB `runtime_param_active`)은 그대로 `param-20260907T152806-255383` 이다. 바뀐 것은 `latest_runtime_param.json` 뿐이다. 두 쪽 값을 같은 키 14개로 펼쳐 비교하면 차이 0 이라(OCI 읽기 전용 · 2026-10-04) 운영 발송 영향은 없다.
   - 이 관찰(화면 '적용'이 OCI JSON 만 바꾸고 OCI 러너의 활성 PARAM(DB)은 바꾸지 않음)은 사용자 지시로 설계자 판단 요청 항목에 올렸다 — `docs/backlog/BACKLOG.md` §11 · `docs/STATE_LATEST.md` · `docs/PROGRAM_TRUTH.md`(PARAM 전달 설명 3곳에 단서). 이번 단계(동작 변경 0) 범위가 아니라 코드는 고치지 않았다.

---

## 8. 검증 실측 (2026-10-03 ~ 10-04)

### 8-1. 기준점 (PLAN §3-1 · 구현 첫 수정 전)

| 단계 | 결과 |
|---|---|
| 1 `BASE_HEAD = git rev-parse HEAD` | `a0a2c5141f258554074de7f02c6985c0d2af3b0f` |
| 2 `git rev-parse BASE_HEAD:scripts/run_three_push_runtime_oci.py` | `f256677020232600627d207c54baf5081c70c6e2` = 기준 blob |
| 3 작업 트리 `git hash-object` (첫 수정 전) | `f256677020232600627d207c54baf5081c70c6e2` = 기준 blob |
| 4 `git diff 7d507951 BASE_HEAD -- '*.py' '*.ts' '*.tsx'` | 0줄 |
| (추가) 기존 모듈 20개 blob(PLAN 1-0) | 20/20 일치 |

### 8-2. 단계별 진행

| 단계 | 러너 줄 | 동등성 | 러너 구동 16파일 |
|---|---|---|---|
| 분리 전 | 646 | — | 305 passed |
| A 실행 기록(`runner_record`) | 629 | 49 다름 0 | 305 passed |
| B 사전 검사(`runner_preflight`) | 597 | 49 다름 0 | 305 passed |
| D · E kind 조립 · 판정(`runner_dispatch`) | 517 | 49 다름 0 · 정적 문제 0 | 305 passed |

### 8-3. 동등성 비교 (최종 · `python scripts/poc5_01a/runner_split_equivalence.py` rc 0)

`scenarios=49 diff=0 static_problems=0 live_blocks=0 mode=baseline-vs-worktree` · rc 0 — 보강한 스크립트로 2026-10-04 에 3회(보강 직후 2회 · 최종 코드(21키 docstring 정정 뒤) 11:27 1회) 모두 같음 · `--self-check`(기준 대 기준) 같은 때 `diff=0`.

- **비교 항목**(설계 STEP 8): Telegram 본문(문자열) · 조립 함수에 넘어간 인자(경로 · 날짜 · 함수 이름 · logger 이름) · 러너 전역 14개 이름의 호출 기록 · `main()` stdout(들여쓴 JSON 원문 → 키 순서 포함) · 종료 코드 · 예외 종류와 메시지 · JSONL 원문(키 순서 포함) · `runtime_execution_status` · `runtime_sent_registry` 행 · tmp 상태 파일 원문 · 로그(logger 이름 · 수준 · 문장).
- **정규화**: 시각 키 4개(`started_at` · `finished_at` · `sent_at_utc` · `inserted_at`) · tmp 경로 · 러너 모듈 이름뿐.
- **정적 검사**(새 운영 모듈 3개 AST):
  - 14개 이름(별칭 포함) import 0
  - 14개 이름의 원래 (모듈, 이름) — 분리 전 러너 import 문에서 읽음 — 의 import · 모듈 속성 접근 0
  - 상태 파일 이름(`oci_runtime_history.jsonl` · `holdings_selection_state_latest.json` · `holdings_risk_state_latest.json`) 문자열 상수 0
  - 모듈 전역 logger · `getLogger` · `setup_logging` 대입 0
  - 기존 모듈 20개 blob 불변
  - 러너 전역에 14개 이름 모두 있음
- **안전**: `tests/_live_guard` 설치(라이브 `state/` · `logs/` 쓰기 · 라이브 DB 연결 차단) · `socket.connect` 차단 · Telegram 토큰 가짜 값 · tmp 만 사용.

종료 27곳 대응(분리 전 러너 행 · 시나리오):

| 행 | 종료 | 시나리오 |
|---|---|---|
| 207 · 217 · 225 · 228 · 245 | param_load_error · param_secret_exposed · slot_id_required · slot_id_invalid · push_kind_not_in_param | M17 · M18 · H03 · H04 · M19 |
| 265 · 274 · 295 | runtime_price_refresh_error · runtime_price_all_failed · freshness_stale | H05 · H06 · S01 |
| 393 · 404 · 410 · 419 | runtime_evidence_error · reevaluate_missing_published_evidence · forbidden_wording · raw_identifier_exposed | S02 · S03 · M03 · M04 |
| 425 · 432 | dry-run 조립 실패 · dry_run_success | H08 · M02 · R06 · S08 |
| 437 · 442 · 456 · 465 | autosend_disabled · push_kind_disabled · no_signal(진단) · no_signal(신규 0) | M05 · M06 · H12 · S04 · S05 |
| 477 · 481 · 485 · 495 · 509 | 조립 실패 · non_trading_day · 시장 skip/fail · 장중 skip · 보유 skip(빈 상태 저장) | H09 · R07 · H10 · R08 · M07 · M08 · M09 · R03 · H11 |
| 538 · 554 | spike duplicate · duplicate_runtime / registry_corrupted | S07 · M12 · M13 |
| 591 · 594 | sent · telegram_send_error(부분 전송 포함) | M01 · M20 · H01 · H02 · H07 · R01 · R02 · S06 · M10 · M11 · R04 · R05 |
| (미포착 예외) | 조립 예외 · 발송 뒤 `mark_sent` 예외 · `_finish` 안 `insert_status` 예외 | M14 · H13 · M16 · M15 |

### 8-4. 테스트

- 러너 구동 16파일(PLAN 부록 A 명령): 분리 전 · 각 단계 · 최종 모두 `305 passed, 1 warning`(warning = fastapi testclient 제3자).
- 테스트 파일 변경: `git diff a0a2c514 -- tests/` 0줄.

### 8-5. 파괴 시험 (검토 1회 · 결함 하나씩 넣고 되돌림 · 되돌린 뒤 sha256 일치 확인 · 보강한 검증 스크립트로 2026-10-04 재실행)

| 결함 | 동등성 스크립트 | 러너 구동 16파일 |
|---|---|---|
| (a) `finish_run` 이 기록 경로를 인자 대신 모듈 상수로(PLAN (a)) | rc 2 · 45 다름 + 정적(상태 파일 상수) | 13 failed |
| (b) 러너가 `kst_today` 를 값으로 미리 계산해 넘김(PLAN (b) 원래 정의) | rc 1 · 24 다름(호출 기록) | 305 passed(못 잡음) |
| (b′) `runner_dispatch` 가 `kst_today` 를 별칭 import 해 직접 호출 | rc 2 · 9 다름 + 정적 | 305 passed(못 잡음) |
| (c) §6-c 판정을 flag guard 앞으로(PLAN (c)) | rc 1 · 2 다름(H11 · H12) | 6 failed |
| (d) record 키 순서 2개 바꿈(PLAN (d)) | rc 1 · 45 다름 | 305 passed(못 잡음) |
| (e) `runner_record` 가 `insert_status_from_record` 를 직접 import(PLAN (e)) | rc 2 · 46 다름 + 정적 2 | 305 passed(못 잡음) |
| (f) `runner_dispatch` 가 `holdings_selection_state.kst_today` 를 모듈 속성으로 호출(독립 검토 발견) | rc 2 · 9 다름 + 정적 | 305 passed(못 잡음) |
| (g) `runner_preflight` 가 원래 이름 `from_dict` 를 import 해 호출 | rc 2 · 48 다름 + 정적 | 2 failed |
| (h) `runner_dispatch` 가 `is_already_sent` 를 직접 import(검증자 r1 뒤 추가) | rc 2 · 정적 2 | 305 passed(못 잡음) |
| (i) 러너가 러너 전역 대신 원래 모듈 `is_already_sent` 를 넘김(검증자 r1 뒤 추가) | rc 1 · 15 다름(호출 기록) | 1 failed |

10종 모두 동등성 스크립트가 잡는다. 기존 테스트만으로는 (a) · (c) · (g) · (i) 4종이다. (h) · (i) 는 `is_already_sent` 를 고정 이름에 넣은 뒤(2026-10-04 · §6-8) 돌렸다. 보강 전 첫 실행(2026-10-03)에서는 (b) 를 별칭 import 형태로만 돌렸다. 원래 정의 '값으로 미리 계산'은 보강 전 스크립트로는 차이가 없었다. 그래서 그 정의를 그대로 넣어 다시 돌렸다(독립 검토 지적).

### 8-6. import · KS-10 · 품질

- fastapi · pydantic · starlette 를 meta_path 로 막고 러너 import: 정상 · `app`/`scripts` 모듈 70개(분리 전 67 + `runner_dispatch` · `runner_preflight` · `runner_record`) · 외부 패키지 0 · 러너 전역에 14개 이름 모두 있음.
- KS-10 전 파일 재실측(PLAN 1-13 명령 + 새 파일 · 2026-10-04): 564개 · 159,045줄 · **TRIGGER 0 · NEAR 6**. 러너가 NEAR 에서 빠졌고, 나머지 6개는 PLAN 1-13 과 같은 파일 · 같은 줄 수다. 바뀐 코드 파일은 §2 의 5개뿐이다(최대 597 = 검증 스크립트 · 백엔드 근접 600 미만).
- black --check · flake8 · py_compile: 코드 5파일 모두 rc 0.

### 8-7. 백엔드 전체 회귀 · 라이브 보호

- 명령: `.venv/bin/python -m pytest -q -p no:cacheprovider -o faulthandler_timeout=300 --durations=5 tests/`.
- **최종 코드 회귀(2026-10-04 11:31:24 ~ 11:37:36)**: **2709 passed / 0 failed · exit 0** · 370.41s · 1 warning(fastapi testclient `StarletteDeprecationWarning` 제3자) · 멈춤 덤프 0. 통과 수는 OPS-03 종료 커밋 회귀(2,709)와 같다(테스트 변경 0).
  - 코드 5파일 sha256 은 회귀 시작 전에 찍은 최종본 값과 같다.
  - 라이브 DB 세션 사본(`market_data.sqlite` · `decision_evidence.sqlite`): 복사 전후 · 세션 끝 sha256 같음 · integrity ok.
  - PC `state/` · `logs/`(`state/ml/research` 제외) **229파일 sha256 전후 동일**.
- 앞선 실행 기록(같은 명령):
  - 2026-10-03 10:02 실행: 82% 지점에서 출력이 멈췄고 시간 한도(20분)로 중단됐다. 맥북 배터리 · 잠자기로 추정한다. 중단 전후 라이브 hash 는 동일했다.
  - 2026-10-04 10:50 실행: docstring 정정 직전 코드로 2709 passed · exit 0 · 366.20s · 라이브 226파일 동일.
  - 2026-10-04 11:24 실행: 2709 passed 였으나 exit 1 이었다. 세션 중 11:26:39 에 PC 백엔드의 유니버스 모멘텀 갱신(`app/api_universe.py` → `run_universe_refresh` · `artifact_generated_at` 02:26:39Z · 사용자 화면 조작 · 사용자 확인 2026-10-04)이 `state/universe/universe_momentum_latest.json` 을 바꿔 conftest 세션 전후 감시가 실패로 처리했다. 그래서 11:31 에 다시 돌렸다.
- 런타임 전수 기록 실행(2026-10-04 12:09:40 ~ 12:15:47 · 같은 테스트에 관찰 플러그인만 더함 · §6-8): 2709 passed · exit 0 · 365.26s · 라이브 229파일 hash 전후 동일. 이 실행 뒤 바뀐 것은 검증 스크립트뿐이다(594 → 597줄 · 테스트가 import 하지 않음). 운영 코드 4파일 sha256 은 위 최종 코드 회귀 때와 같다.
- 라이브 파일 수가 226 → 229 로 늘어난 것은 2026-10-04 11:09 ~ 11:11 사용자 화면 조작(PARAM 적용 · 시장 데이터 갱신 · §7-4) 때문이다. 이번 작업의 쓰기가 아니다.

## 9. 이동표 (이동 전 → 이동 후)

| 이동 전(러너 · 분리 전 행) | 이동 후 | 러너에 남은 호출 |
|---|---|---|
| 148~170 record 21키 dict | `runner_record.new_run_record(push_kind, mode, *, started_at, runtime_kst, runtime_date_kst)` | `record = new_run_record(...)` |
| 172~192 `_finish` 본문 | `runner_record.finish_run(record, status, reason, error, *, push_kind, mode, logger, history_path, insert_status)` | `_finish` closure 가 `history_path=_HISTORY_PATH` · `insert_status=insert_status_from_record` 를 매번 넘김 |
| 201~245 §1 · §1-b · §2 | `runner_preflight.load_param_and_check_slot(record, *, push_kind, slot_id, logger, read_active_param_dict, param_from_dict)` → `(param, fail)` | `if pre_fail is not None:` → `return _finish(*pre_fail)` |
| 276 ctx 초기화 · 315~375 §3-c · §3-d · §3-e | `runner_dispatch.KindAssembly`(holdings_outcome · risk_outcome · risk_assembly · market_outcome · fail · skip_non_trading_day · message_text) · `assemble_push_kind(record, *, push_kind, market_quotes, price_refresh_diag, slot_id, runtime_kst, runtime_date_kst, kst_today, holdings_state_path, risk_state_path, logger)` | `asm = assemble_push_kind(...)` · `message_text = asm.message_text` · dry-run `asm.fail` · §8 `asm.market_outcome` |
| 467~513 §6-c | `runner_dispatch.decide_after_flag_guard(asm, *, message_text, slot_id, save_state, holdings_state_path, logger)` → `(fail, holdings_selection_ctx)` | `if gate_fail is not None:` → `return _finish(*gate_fail)` |

러너에서 빠진 import: `assert_no_sensitive_keys` · `holdings_risk_flow as _hrf` · `assemble_holdings_push`(새 모듈이 import). 남은 것: 테스트 고정 14개 이름 · `save_state` · `save_risk_state` · `HOLDINGS_SLOT_IDS`(CLI).

## 10. git 상태

커밋 직전 실측(2026-10-04 · 검증자 재검증 `VERIFIED` 기록 뒤 · `git status --short --untracked-files=all`). 아래 staged 11개(오른쪽 열 공백 · unstaged 0)가 구현 커밋 한 개에 들어간다. 코드는 5개(`*.py`), 테스트는 0개다. 검증자 r1 때 10개에서 `docs/backlog/BACKLOG.md`(설계자 항목 · §7-4)가 더해졌다. 커밋 SHA 는 이 문서에 적지 않는다(자기참조) — `git log -1 -- docs/ai_result/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_RESULT.md` 로 실측한다.

```text
A  app/three_push_runtime/runner_dispatch.py
A  app/three_push_runtime/runner_preflight.py
A  app/three_push_runtime/runner_record.py
M  docs/PROGRAM_TRUTH.md
M  docs/STATE_LATEST.md
M  docs/backlog/BACKLOG.md
M  docs/ai_design/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_DESIGN_V1.md
M  docs/ai_plan/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_PLAN_V1.md
A  docs/ai_result/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_RESULT.md
A  scripts/poc5_01a/runner_split_equivalence.py
M  scripts/run_three_push_runtime_oci.py
?? docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md   (사용자 소유 · 손대지 않음)
```

줄 수 합계는 이 결과서 자신이 들어가 바뀌므로 적지 않는다(`git show --stat` 로 실측). 바로 앞 커밋은 선행 문서 커밋 `a0a2c514` 이고, 두 커밋이 함께 push 된다.

## 11. 배포 절차 (1 완료 · 2 부터 남음)

1. 설계자 RESULT 판정 `PASS_TO_VERIFIER` → 검증자 `VERIFIED` → 커밋 · push(사용자 승인 2026-10-04).
2. OCI `git pull`(사용자 · 거래일 15:45 뒤 또는 휴장일). cron · `.env` 변경 없음.
3. 읽기 전용 확인: OCI 러너 blob = 새 blob · 새 모듈 3개 존재 · fastapi 등 차단 import 정상.
4. 첫 거래일(OCI 읽기 전용): 08:30 · 09:15 · 09:30~15:20 · 12:30 · 15:40 실행 기록 status · reason · 길이가 평소 모양 · `logs/` Traceback 0 · 발송 수 변화 0 → 그 뒤 `POC3-02D-OPS-04`.
5. 롤백 = 커밋 revert + OCI pull(분리 전용 스키마 · 데이터 변경이 없어 되돌릴 데이터가 없다).
