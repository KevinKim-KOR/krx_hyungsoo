# POC5-18 개발 결과서 — PC_MARKET_REFRESH_UNEXPECTED_FAILURE_STATUS (PC 시장 갱신의 예상 밖 오류 상태 정정)

작성 2026-10-16 · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex) · 설계자

```text
STATUS        = IMPLEMENTED_VERIFIED_CLOSED — 검증자 r1 VERIFIED(2026-10-16 · §10) · 설계자 RESULT PASS · 종료(2026-10-16 · §11) · 커밋 · push 는 이번 단계 사용자 승인 뒤
VERIFIER      = Codex r1 · staged 9파일 · 신규/관련 174건 · 독립 재현 2건 통과 · 운영 코드·원본 시험 수정 0
STEP_ID       = POC5-18 PC 시장 갱신의 예상 밖 오류 상태 정정(DEF-PC-REFRESH-UNEXPECTED-COMPLETED)
DESIGN        = docs/ai_design/POC5/POC5-18_PC_MARKET_REFRESH_UNEXPECTED_FAILURE_STATUS_DESIGN_V1.md
PLAN          = docs/ai_plan/POC5/POC5-18_PC_MARKET_REFRESH_UNEXPECTED_FAILURE_STATUS_PLAN_V1.md (PASS · 제출안 그대로 · 판정 원문 §5)
BASE_COMMIT   = 64749ad4 (POC5-17 종료)
SCOPE         = app/market_refresh_service.py 의 refresh_unexpected 예외 경계 · 최종 성공 판정
                API · 응답 필드 · 화면 · DB 표 · 의존성 · 공유 함수(market_data_fdr) · OCI · PUSH · 수동 스크립트 · POC5-17 요청 timeout 변경 0
CHECKS        = §8
```

## 0. 요약

- **원인**(PLAN §1-2): ETF 목록을 받은 뒤 ETF 목록 · 가격 블록 안에서 예상 밖 예외가 나면 가격 건수를 받지 못한다.
  - 경로: 종목 목록 읽기(`list_etf_tickers`) 실패 · 가격 함수 반환 전 예외(가격 기록 쓰기 등).
  - 그래서 `price_attempted` 가 초깃값 0인 채 최종 판정 `universe_ok and (price_success > 0 or price_attempted == 0)` 이 참이 되어 `completed` 와 6시간 대기가 됐다.
- **정정**(`app/market_refresh_service.py` 한 파일 · 597 → 598줄)
  1. 실행마다 새 지역 표식 `stage_unexpected = False` 를 만든다. 다음 실행은 물려받지 않는다.
  2. 예외 경계(`except Exception` · ETF 목록 · 가격 블록)에서 `stage_unexpected = True` 를 세운다. 사유 `refresh_unexpected: …` 는 그대로다.
  3. 최종 판정: `success_overall = success_overall and not (price_stopped or stage_unexpected)`.
  4. POC5-17 의 중단 · 오류 사유 결합은 오류 문자열 접두어 대신 이 표식으로 판단한다. 결과 문구는 같다('중단 문구 · refresh_unexpected: …').
- **결과**
  - 예상 밖 오류 회차는 뒤 단계(보유 개별주 · KOSPI · VIX · NAV)가 성공해도 `failed` 다. 메모리 · 영속 상태 모두 그렇다.
  - 새 성공 시각 · 6시간 대기는 생기지 않고, 이전 성공 기록은 그대로다. 작업이 끝나면 같은 버튼으로 다시 실행할 수 있다.
  - 받은 가격은 종목마다 즉시 저장되므로 그대로 남는다. 건수는 기존 뜻 그대로다(예외로 받지 못하면 0 · 추정하지 않음).
  - 예상 밖 오류가 있으면 VIX 단독 실패로 판정되지 않는다(VIX 다시 받기 표식 없음).
- **그대로**: 정상 완료 · 대기 · 종목별 일부 실패 완료 · 마지막 5종목 시간 초과 · 미조회 0 판정 · ETF 목록 실패 · 보유 개별주 · KOSPI · VIX · NAV 정책 · VIX 단독 실패 표식 · 공유 함수 · 화면.

## 1. 처리한 요구사항

| 출처 | 요구 | 상태 |
|---|---|---|
| 설계 §5-1 · PLAN §1 | 예외 경계 · 두 재현 경로 · 최종 상태 · 성공 시각 결정 위치 확인 | DONE |
| 설계 §3 · 판정 1 | 실행별 표식 · 예외 경계에서 남김 · 최종 failed · 뒤 단계 성공이 지우지 않음 · 다음 실행에 넘기지 않음 | DONE |
| 판정 2 | POC5-17 사유 결합을 문자열 대신 표식으로 · 두 사유 보존 | DONE |
| 설계 §3 · 판정 3 | 정상 · 일부 실패 · 마지막 5종목 · VIX 단독 실패 · 이전 성공 기록 · 저장 가격 보존 | DONE(시험) |
| 설계 §4 | 자료 롤백 · 삭제 없음 · 기존 failed 표시 · 오류 요약 · 건수 추정 없음 · 과거 이력 소급 없음 | DONE |
| 판정 4 | POC5-17 시험 두 건 정정(가격 기록 오류 시험 이동 · 복원 검사 유지) | DONE |
| 설계 §6 | 목록 읽기 오류 · 중단 없는 기록 오류 · 중단 결합 · 대조 · 실행 간 분리 · VIX · 관련 · 전체 회귀 | DONE(§8) |

## 2. 변경된 파일 목록

- `app/market_refresh_service.py`: 수정(표식 · 예외 경계 · 최종 판정 · 사유 결합 · 598줄)
- `tests/test_pc_refresh_unexpected_failure.py`: 신규(8건 · 160줄)
- `tests/test_pc_refresh_stall_protection.py`: 수정(25건 · 528줄)
  - 예전 동작(completed)을 고정한 시험 `test_price_log_failure_without_stop_keeps_existing_judgement` 를 지우고 새 파일로 옮겼다.
  - `test_function_restored_when_exception_leaves_the_block[price]` 에 `failed` 확인을 더했다(복원 검사 유지).
- 문서
  - 신규: 설계 V1 · PLAN V1(판정 원문 §5) · 이 결과서
  - 수정: `docs/PROGRAM_TRUTH.md` · `docs/backlog/BACKLOG.md` · `docs/STATE_LATEST.md`

## 3. 신규 추가된 의존성

- 없음.

## 4. 지시문 외 변경 · 구현 판단

1. **줄 수**: 처음 반영 때 black 줄바꿈으로 602줄이 되어 PLAN '598줄'과 600줄 근접선을 넘었다. 주석을 줄이고 사유 결합을 두 줄로 다시 써서 598줄로 맞췄다(동작 같음).
2. **ETF 목록 단계 안의 예외**: `refresh_etf_universe` 의 저장 · 기록 실패도 같은 경계에 닿는다. 이 경로는 원래 `universe_ok` 가 거짓이라 이미 failed 였다. 표식으로 바뀌는 것은 없다.

## 5. 알려진 한계 / 미완성

- **동등 변이 1건**: '사유 결합을 문자열 판단으로 되돌림'은 지금 모든 경로에서 결과 문구가 같다(예외 사유는 그 경계에서만 생김). 그래서 시험으로 구분되지 않는다. 판정(성공 · 실패)은 표식만 쓰며, 이 판정은 변이로 확인했다(§8).
- **POC5-17 한계 그대로**: 요청 20초는 연결 · 읽기 대기 설정이다. DNS 대기 · 느린 연속 응답 · 파싱 · 저장 지연에 대한 전체 종료 보장은 없다. 프로세스 공통 교체 · 터미널 수동 스크립트 제외도 그대로다.
- **과거 이력**: 지난 completed 기록 · 과거 로그는 고치지 않는다(설계 §4).

## 6. 다음 검증자(Codex)에게 알릴 점

1. **표식 범위**: `stage_unexpected` 는 `_execute_refresh_job` 의 지역 변수다. ETF 목록 · 가격 블록의 `except` 에서만 참이 된다. 뒤 단계 예외(보유 개별주 · KOSPI · VIX · NAV)는 각자의 처리 그대로이고 이 표식에 닿지 않는다.
2. **영속 상태**: 최종 블록이 메모리 상태를 `failed` 로 두고 `_persist_current_state` 로 저장한다. 실패 경로는 `last_success_*` 를 덮지 않는다(기존 규칙). 시험 `test_failed_run_keeps_the_previous_success_record` 가 이전 성공(7시간 전)이 그대로인지 확인한다.
3. **시험 기대값 정정**: POC5-17 의 예전 고정 시험 두 건은 판정 4 대로 정정했다. 중단 + 기록 오류(`test_stop_survives_price_log_failure`)는 그대로 통과한다(failed · 두 사유).
4. **변이**: 저장소 사본에서 5개 · 모두 검출(§8).

## 7. 사용자 확인이 필요한 항목

- 화면 변경이 없어 실화면 확인은 필요 없다.

## 8. 검증 실측 (2026-10-16 · 최종 코드)

- 정적 검사(`app/market_refresh_service.py` · `tests/test_pc_refresh_unexpected_failure.py` · `tests/test_pc_refresh_stall_protection.py`): `black --check` `3 files would be left unchanged` · `flake8` 출력 없음 · `py_compile` 통과
- 새 시험 `tests/test_pc_refresh_unexpected_failure.py` `8 passed` + POC5-17 시험 25 → 두 파일 `33 passed`
- 관련 시험 18파일: `471 passed`
  - 갱신 6파일 · POC5-17 · POC5-18 · OPS-03 10파일
- 변이(저장소 사본 · 복원 뒤 `33 passed`) 5/5 검출
  - 표식을 세우지 않음 · 최종 판정에서 표식 빠짐 · 표식이 다음 실행으로 넘어감
  - 중단 판정 빠짐(POC5-17 회귀) · 중단 + 오류일 때 오류 사유 버림
- 백엔드 전체 pytest(최종 코드 · 2026-10-16 17:54): `3662 passed, 1 warning in 398.09s` · 종료 0(POC5-17 종료 시점 3655 − 옮기며 지운 1 + 새 8)

## 9. git 상태 (2026-10-16 · 보고 직전 실측)

- `git status --short --untracked-files=all`: 이 단계 파일 9개 모두 staged(신규 `A` 4 · 수정 `M` 5) · 오른쪽 열 공백(작업 트리 = staged).
- `??` 1건은 사용자 소유 `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`(이 단계와 무관 · stage 하지 않음).
- 검증자 도구 경로(`.agents` · `.codex` · `AGENTS.md`) 변경 없음.
- 커밋 · push 는 이 시점(검증 전)에는 하지 않았다. 설계자 RESULT PASS 뒤 종료 기록과 함께 사용자 승인 범위로 한다(§11 · 커밋 내역은 `git log` 로 확인).

## 10. 검증자 r1 판정 (2026-10-16)

**종합 판정: VERIFIED — 추가 코드 결함 없음.**

### 10-1. A. 기능/산출물 검증

- **A-1 지시 일치: 통과.** 실행별 지역 표식은 ETF 목록·가격 블록의 실제 예외 경계에서만 세워지고, 최종 성공 판정과 중단·오류 사유 결합이 이를 사용한다. 뒤 단계의 성공이 오류를 지우지 않고, 다음 실행은 새 표식으로 시작한다.
- **A-2 보고 정확성: 통과.** staged 9파일(A 4 · M 5), unstaged 0과 변경 목록이 일치한다. 서비스 598줄 · 기존 시험 528줄 · 신규 시험 160줄을 실측했다. PLAN §1-2의 '종목 루프 밖 행 변환'은 실제 호출 위치(`market_data_fdr.py:307` · 루프 안이지만 fetch 예외 처리 블록 밖)에 맞춰 위치 메타 설명만 직접 정정했다. 계약·코드 변경은 없고 반려 사유가 아니다.
- **A-3 산출물 정합성: 통과.** 종목 목록 읽기 오류와 중단 없는 가격 로그 INSERT 오류를 독립 재현해 메모리/영속 상태 failed · 대기 0초 · 이전 성공 시각/기준일 보존 · 다음 실행 accepted를 확인했다. 오류 원인을 제거하면 다음 실행은 completed가 되고 기존 대기가 적용된다. 가격 로그 오류 뒤에도 먼저 저장한 새 가격이 유지된다.
- **A-4 금지사항: 위반 없음.** 운영 변경은 `market_refresh_service.py` 한 파일이다. 공유 가격 함수·OCI·PUSH·수동 스크립트·화면·API·스키마·의존성 변경이 없다. 기존 시험 두 건의 정정은 설계자 PLAN 판정 4의 승인 범위다.

### 10-2. B. 구현 규칙/구조 품질

- **B-1 암묵 fallback: 위반 없음.** 오류 사실을 명시적인 표식으로 최종 판정까지 보존하고 오류 요약을 유지한다. 문자열로 성공 여부를 결정하지 않는다.
- **B-2 단일 책임: 위반 없음.** 기존 서비스의 실행 상태 판정 경계에 한정한 수정이다.
- **B-3 파일 책임 과다: 위반 없음.** 서비스 598줄로 기존 기준 미만이다. 새 프레임워크나 불필요한 구조 분리를 도입하지 않았다.
- **B-4 실험/운영 경계: 위반 없음.** 오류 주입·SQLite 트리거·로컬 소켓은 시험과 저장소 밖 사본에만 있다.
- **B-5 배포/실행 경로: 위반 없음.** 보고한 변경 9파일은 모두 index에 있고 파일 이동·배포 경로 변경이 없다. 실행 파일은 기존 Git 추적 경로를 유지한다.
- **B-6 기술부채/구조적 퇴행: 위반 없음.** 표식은 함수 지역 변수이며 실행 간 오류를 물려받지 않는다. 새 전역 상태·자동 재시도·대기를 추가하지 않았다.

### 10-3. 기반 문서 준수

- 위반 없음. 신규 문서 3개는 승인된 설계·PLAN·RESULT 산출물이다. 요청 timeout과 POC5-17의 승인된 한계를 그대로 유지한다.
- 검증자는 결과서·STATE·PROGRAM_TRUTH·BACKLOG의 검증 상태 메타를 갱신하고 위 PLAN의 위치 설명 한 곳만 정정했다. 결함의 최종 종료 기록은 설계자 RESULT 판정 뒤 순서다.

### 10-4. 코드 안전성

- 위험 수준 **NONE**(이번 변경에서 추가 결함 발견 없음).
- 독립 재현에서 NAV 실행 중 메모리/영속 상태가 모두 running이고, 같은 버튼의 중복 실행 요청도 running으로 거절됨을 확인했다. 뒤 단계가 끝난 뒤 failed로 정리된다.
- 정상·일부 가격 실패 완료·마지막 5종목 timeout/미조회 0·중단 후 로그 오류·VIX 단독 실패는 관련 시험에서 기존 계약을 유지한다.

### 10-5. 범위 폭주

- 폭주 수준 **NONE**. 예상 밖 오류 경계와 최종 판정, 승인된 시험 정정에 한정한다.

### 10-6. 검증자 직접 실행한 검사와 근거 범위

- HEAD `64749ad41b2d9ca2ab91db9227af88296ce91f3e`와 staged 9파일을 고정했다. 저장소 밖 사본의 index·작업 파일이 원본과 같음을 확인했다.
- 사본: `/private/tmp/poc518-verifier-1s_0ztt9/staged` · 시작 파일 해시/줄 수는 상위 폴더 `manifest.json`.
- 신규/관련 8파일 **174 passed**: 소켓 외 **171 passed · 3 deselected**, 로컬 소켓 3건 별도 **3 passed**. 이번 두 시험 파일의 33건을 모두 포함한다. 실행 출력은 상위 폴더 `related.log` · `local.log`다.
- 독립 재현 **2 passed**(`tests/_verifier_poc518_boundary.py` · 임시 사본 전용): 목록 읽기 오류와 실제 SQLite 가격 로그 INSERT 실패를 각각 확인했다. 이전 정상 성공 기록·저장 가격·뒤 단계 순서·실행 중 중복 방지·오류 후 정상 재실행·정상 대기를 함께 확인했다. 출력은 상위 폴더 `independent.log`다. 관련 시험과 합해 직접 실행 176건 통과다.
- 변경 Python 3파일 `black --check`·`flake8`·문법 검사, `git diff --cached --check` 모두 통과했다. 기존 Starlette deprecation 경고 외 실패는 없다.
- 전체 회귀 **3662 passed**·관련 18파일 **471 passed**·변이 **5/5**는 §8의 개발자 최종 코드 근거다. 검증자는 전체 회귀·변이를 반복하지 않았다. 동등 변이의 사유 결합은 코드에서 표식 사용을 직접 확인했다. 화면 변경이 없어 프론트 검사를 실행하지 않았다.
- 실제 외부 API·라이브 state/logs·운영 DB·사용자 서버·OCI에는 접근하지 않았다. 운영 코드·원본 시험·검증자 도구 변경 0이다.

### 10-7. 다음 순서

- 설계자 RESULT 판정으로 넘길 수 있다. 커밋·push는 별도 사용자 승인 대상이며 검증자는 수행하지 않았다.

## 11. 설계자 RESULT 판정 · 종료 (2026-10-16)

- **판정: PASS — 추가 코드 보완 없음 · 종료 기록 정리 후 이번 단계 사용자 승인 범위로 커밋 · push.** 판정 원문은 아래에 그대로 둔다(별도 파일로 두지 않음).
- 수용: 검증자 r1 VERIFIED · 실행별 표식과 최종 판정 · 기존 계약 유지 · §4 줄 수 정리와 ETF 목록 단계 내부 예외 처리 · 동등 변이(추가 시험 불요) · PLAN 위치 설명 정정.
- **근거 구분**: 전체 회귀 3662 · 관련 471 · 변이 5/5 는 개발자 근거다. 검증자 직접 근거는 관련 174 · 독립 재현 2 · 정적 검사다.
- **`DEF-PC-REFRESH-UNEXPECTED-COMPLETED` 해소**로 기록했다. POC5-17 의 전체 종료 보장 부재(DNS 대기 · 느린 연속 응답 등)는 기존 승인 한계로 남는다.
- 상태 `IMPLEMENTED_VERIFIED_CLOSED`. STATE · PROGRAM_TRUTH · BACKLOG · PLAN 상태를 맞췄다.
- 문서 정리만이므로 재검증 · 재판정은 요청하지 않는다. POC5-17 ~ 18 의 갱신 보완은 이 범위에서 마무리한다(다음 설계는 남은 사용자 기능 · 미구현 요구에서).

### 판정 원문 (설계자 · 2026-10-16)

````text
# POC5-18 예상 밖 갱신 오류 상태 정정 — RESULT 판정

작성일: 2026-10-16 · 작성자: 설계자 · 독자: 개발자

**판정: PASS. 종료 기록 정리 후 해당 작업의 사용자 승인 범위에 따라 커밋·push한다. 추가 코드 보완은 요구하지 않는다.**

## 판정 근거

- 첨부 RESULT §0~§10을 승인한 DESIGN·PLAN과 대조했다. 문서 기반 설계 판정이며, 설계자가 저장소·DB·서버를 직접 재검증한 것은 아니다.
- 검증자 r1 VERIFIED를 수용한다. 목록 읽기 오류와 중단 없는 가격 기록 INSERT 오류에서 failed·대기 0·이전 성공 기록 보존·다음 실행 accepted가 확인됐다. 먼저 저장한 가격도 유지된다.
- 뒤 단계 실행 중에는 running과 중복 방지를 유지하고, 종료 뒤 failed로 정리되는 근거를 수용한다. 오류 뒤 정상 실행은 completed와 기존 대기로 돌아간다.
- 운영 변경은 서비스 한 파일의 실행별 표식과 최종 판정에 한정됐다. 정상·부분 실패·마지막 5종목·POC5-17 중단·VIX 전용 재시도의 기존 계약 유지도 수용한다.
- 전체 회귀 3,662건·관련 471건·변이 5/5는 개발자 근거다. 검증자 직접 근거는 관련 174건·독립 재현 2건·정적 검사다. 두 근거를 구분한다.

## 구현 판단과 검증 설명

- RESULT §4의 줄 수 정리와 원래부터 failed였던 ETF 목록 단계 내부 예외의 처리를 수용한다.
- 사유 결합을 문자열 판단으로 되돌려도 결과가 같은 동등 변이는 기능 결함이나 검증 반려 사유가 아니다. 현재 코드의 표식 사용을 검증자가 확인했으므로 이를 잡기 위한 추가 시험은 요구하지 않는다.
- PLAN의 '루프 안·조회 예외 처리 블록 밖' 위치 설명 정정은 사실 표현 정리로 수용한다.
- POC5-17의 DNS·느린 연속 응답 등 전체 종료 보장 부재는 기존 승인 한계로 남긴다. 이번 정정이 그 한계까지 해소한 것으로 기록하지 않는다.

## 종료 지시

1. 기존 RESULT에 판정과 종료 기록을 붙이고 `IMPLEMENTED_VERIFIED_CLOSED`로 정리한다. STATE·PROGRAM_TRUTH·BACKLOG·PLAN의 해당 상태를 맞추고 `DEF-PC-REFRESH-UNEXPECTED-COMPLETED`를 해소로 기록한다.
2. 이번 단계의 사용자 커밋·push 승인이 있으면 구현·시험·종료 기록을 함께 커밋·push하고 커밋 ID와 저장소 상태를 보고한다. 이미 받은 동일 범위 승인은 다시 요청하지 않는다. 설계 판정 자체가 새 사용자 승인은 아니다.
3. 문서 정리만으로 추가 검증·재판정·목업·실화면 확인·OCI pull·거래일 대기는 필요 없다. 별도 인계 문서도 요구하지 않는다.

**POC5-17~18의 갱신 보완은 이 범위에서 마무리한다. 다음 설계 우선순위는 남은 사용자 기능과 미구현 요구에서 정하며, 이번 종료를 위한 추가 갱신 조사나 구조 개편 단계를 만들지 않는다.**
````
