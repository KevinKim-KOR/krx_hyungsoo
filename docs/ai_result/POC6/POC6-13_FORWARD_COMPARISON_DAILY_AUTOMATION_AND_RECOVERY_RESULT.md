# POC6-13 개발 결과서 — 전향 비교 정기 실행 · 연구 증거 별도 보관

작성 2026-10-28 · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex) · 설계자

```text
STATUS        = IMPLEMENTED_ISOLATED(2026-10-28) — 격리 구현 · 시험 → 독립 검토 1회 반영(§4-2) → 전체 회귀(§8) → 검증자 r1 REJECTED(§10 · F1~F4)
                → 개발자 정정(§4-3 · 같은 종류 포함) → 변이 4종 · 전체 회귀 → 검증자 r2 REJECTED(§11 · F3/F4 잔여 경로)
                → 개발자 정정(§4-3 · 외장 사본 파일 경계 · launchctl 응답 3갈래) → 독립 검토 1회(§4-4 · 같은 종류 6건 재현) → 정정
                → 변이 22종 · 전체 회귀(§8) → 검증자 r3 VERIFIED(격리 구현 범위 · §12)
                → 설계자 RESULT PASS(V1.1 · 2026-10-29 · §13) · 맥북 보조 A/B 설치됨(2026-10-29 20:54 · §14) · 첫 정기 실행 확인 대기 · C 목적 기기 PC 확정/연결 준비 대기
                → C 보완(별도 PC 공유 폴더 · SMB) 판정 PASS_WITH_REQUIRED_CORRECTIONS → 구현 · 변경분 시험(§15) → 검증자 변경분 REJECTED(§16 · C-F1) → 정정(§15-6) → C 보완 r2 VERIFIED(§17 · 격리 구현 범위)
                사용자 승인(2026-10-29) → 구현 커밋 e0a94175 push · LaunchAgent 설치(§14) · C(별도 PC) 쓰기 0
VERIFIER      = Codex r3 VERIFIED — r1·r2 독립 재현 10건 · 관련 시험 263건 통과 · 격리 구현 범위(실제 설치·연결·외장 백업 승인 전)
VERIFIER_C    = Codex C SMB 보완 r2 VERIFIED — C-F1 정정 · 관련 시험 298건 · 독립 대조 6건 통과(§17 · 실제 PC 연결/백업 승인 전)
STEP_ID       = POC6-13 전향 비교 정기 실행 · 연구 증거 별도 보관
DESIGN        = docs/ai_design/POC6/POC6-13_FORWARD_COMPARISON_DAILY_AUTOMATION_AND_RECOVERY_DESIGN_V1.md
DECISION      = docs/ai_design/POC6/POC6-13_FORWARD_COMPARISON_DAILY_AUTOMATION_AND_RECOVERY_PLAN_DECISION_2026-10-28.md
                (PASS_WITH_REQUIRED_CORRECTIONS · Q1 = C 전체를 사용자 소유 다른 물리 저장소 · Q2 = (b) · Q3 = 활성화 전 확인)
PLAN          = docs/ai_plan/POC6/POC6-13_FORWARD_COMPARISON_DAILY_AUTOMATION_AND_RECOVERY_PLAN_V1.md(판정 반영 = 본문 정정 + §7)
SCOPE         = PC 모듈 `app/forward_auto/`(8) · CLI `scripts/run_forward_auto.py` · 공유 코드 Q2(`app/ml_evidence/transfer.py` 함수 1개 추가
                · 단건 함수 선택 인자 · `scripts/run_forward_compare.py` 업로드 호출부) · `.gitignore` 1줄 · 시험 2파일
REAL_RUNS     = 맥북 읽기 전용 명령 3회(status · install dry-run · backup plan · 2026-10-28 16:27 KST 무렵)
                — 06 호출 · 일정 설치 · 업로드 · 외장 쓰기 · OCI 쓰기 0
```

## 0. 요약

- **A 정기 실행**: 맥북 LaunchAgent 1개(10:05 · 12:05 · 14:35 · 15:25 + 로그인)가 `run_forward_auto.py tick` 을 부른다. tick 은 10:00 ~ 15:20 KST 에만 기존 06 `run --pull` 을 자식으로 부르고(오늘 미완료 · 자동 4회 · 15분 간격 · 20분 상한), 성공 판정은 종료 코드가 아니라 06 의 `records.primaries`(마감 전 영수증이 있는 주 기록)로 한다.
- **B 보관**: 예측과 따로 `archive --upload` 를 부른다(보관 대기 · 자동 4회 · 10분 상한). 예측이 완료여도 보관 대기는 따로 처리한다. Q2 로 업로드 작업 한 번에 OCI 목록을 한 번만 읽는다(묶음별 기존 판정은 그대로).
- **C 백업**: 08 ~ 11 · 봉인 DB · 코드 bundle 을 **외장 장치**에 `.partial` → 해시 대조 → 이름 바꾸기로 남기고, 맥북 빈 임시 칸으로 되가져와 파일 해시 · 커밋 7개를 확인한다. 외장 장치가 없어 지금 상태 = WAITING_TARGET(완료 · 제외 아님).
- 실제 설치 · 자동 업로드 · 외장 쓰기는 하지 않았다(§7 승인 묶음).

## 1. 처리한 요구사항

| 요구사항(설계 · 판정) | 상태 | 근거 |
|---|---|---|
| A 일정 · 창 · 상한(설계 §3-1 · PLAN §3-1 · §3-2) | DONE(격리) | `schedule.py` · `launchd.py` · `runner.tick` · 시험 창 경계 · 상한 · 간격 |
| A 호출 · 마감 · 중복(설계 §3-2) | DONE(격리) | 06 CLI 를 자식으로만 부름 · 15:20 뒤 호출 0 · 자기 그룹만 정리 · 잠금 겹침 = 겹침 기록 |
| 판정 §5-1 완료 = 실제 D · 주 기록 · 마감 전 영수증 · 실제 분모 · 방법 실패 0 | DONE | `view.completion`(06 `records.primaries` 재사용) · 실제 06 산출물 시험(영수증 삭제 → 0) |
| 판정 §5-2 예측 완료여도 보관 따로 · 시도 수 분리 | DONE | `runner.tick` · 시험 '예측 DONE + 보관 실패 → 다음 일정에 보관만' |
| 판정 §5-3 AUTO_WINDOW_CLOSED / DEADLINE_PASSED 구분 · 지난 날 요약 | DONE | `status._predict_state` · 시험 15:25 · 15:29:59 · 15:30 · 토요일(마감 = 월) · 다음 날 |
| 판정 §5-4 사유 = 추정 · 알림 전달 확인 불가 | DONE | 시도 기록 `reason_note` · 알림 결과 `REQUESTED_DELIVERY_UNKNOWN` / `NOTIFY_FAILED` |
| 판정 §4 caffeinate = 작업 생애마다(A · B · C) | DONE | `runner.awake` · 가짜 caffeinate 프로세스 생애 시험(정상 · 예외 · 시간 초과) |
| B 새 산출물 보관(설계 §4) | DONE(격리) | `archive --upload` 별도 호출 · 보관 대기 = 미등록 + 자동화가 OK 받은 적 없는 묶음 |
| Q2 (b) 업로드 작업당 목록 1회(판정 §3) | DONE | `transfer.upload_research_many` · 시험 175묶음 목록 1회 · 조회 실패 예외 · 손상 복구 · 중간 실패 · 경쟁 업로드 · 단건 호환 |
| 상태 CLI · 최신 상태 파일 · 로컬 알림(설계 §5) | DONE(격리) | `status.py` · `run_forward_auto.py status`(읽기만 · 실측 §8-3) |
| C 외장 사본 · 복원 확인(판정 §2) | PARTIAL | 구현 · 가짜 외장 경로 시험 완료. 실제 외장 장치 없음 → WAITING_TARGET(§5 · §7) |
| 실제 설치 · 연결 확인(설계 §11) | SKIPPED | 사용자 승인 전(§7). 판정 §6 대로 지금은 새 실행 승인이 아님 |
| PROGRAM_TRUTH · STATE 갱신 | DONE | §2(BACKLOG 는 해당 항목이 없어 변경 없음) |

## 2. 변경된 파일 목록

| 파일 | 종류 | 내용 |
|---|---|---|
| `app/forward_auto/__init__.py` | 신규 | 묶음 설명 |
| `app/forward_auto/schedule.py` | 신규 | KST 창 · 일정 · 사유 추정 · 상한 상수 |
| `app/forward_auto/view.py` | 신규 | 06 산출물 읽기 · 필요한 D · 완료 판정 · 보관 대기 |
| `app/forward_auto/status.py` | 신규 | 시도 기록 · 상태 판정 · 문장 · 알림 · latest 원자 교체 |
| `app/forward_auto/runner.py` | 신규 | 자식 실행 · 그룹 정리 · caffeinate · 시도 기록 · tick |
| `app/forward_auto/launchd.py` | 신규 | plist · 설치 · 해제 · dry-run |
| `app/forward_auto/backup_source.py` | 신규 | C 대상 목록 · 목적지(외장 장치) 검사 · 코드 참조 · 계획 |
| `app/forward_auto/backup.py` | 신규 | C 외장 사본 · 대조 · 복원 확인 |
| `scripts/run_forward_auto.py` | 신규 | 진입점 |
| `app/ml_evidence/transfer.py` | 수정 | `upload_research(listing=)` 선택 인자 · `upload_research_many` 추가 |
| `scripts/run_forward_compare.py` | 수정 | `_upload` 가 업로드 작업 1회 함수를 씀 |
| `.gitignore` | 수정 | `state/ml/operations/` |
| `tests/test_poc6_13_forward_auto.py` · `tests/test_poc6_13_backup.py` | 신규 | §8 |
| `docs/ai_design/POC6/POC6-13_…_DESIGN_V1.md` · `…_PLAN_DECISION_2026-10-28.md` | 신규 | 설계자 원문 보관 |
| `docs/ai_plan/POC6/POC6-13_…_PLAN_V1.md` | 신규 | PLAN(판정 반영) |
| `docs/ai_result/POC6/POC6-13_…_RESULT.md` | 신규 | 이 문서 |
| `docs/PROGRAM_TRUTH.md` | 수정 | 6곳: 최종 반영 · CLI 표(새 행 + 06 행 업로드 문구 · 새 행은 검증자 정정 · §4-4 동작까지) · 상태 경로 표 · 모듈 표 · 06 운영 절차 · 함수 목록 |
| `docs/STATE_LATEST.md` | 수정 | 머리 줄 · POC6 칸에 POC6-12 · POC6-13 |
| `docs/ai_plan/POC6/POC6-12_…_PLAN_V1.md` | 수정 | 머리말에 설계 §12(API 확인 우선) · 10-29 사실 2줄 · §7-3 D = 10-28 결측 · §7-4 · §7-6 SEIBro API 가입 = 사업자등록번호 필요(사용자 10-29) — POC6-12 기록(이 작업의 코드 변경 아님) |

같은 stage 에 POC6-12 문서 4개(설계 · PLAN 판정 · 점검 요청 · PLAN)가 함께 있다(§9 · 이 작업의 변경 아님).

## 3. 신규 추가된 의존성

없음(표준 라이브러리 `plistlib` · `tarfile` · `tempfile` · 시스템 `/usr/bin/caffeinate` · `/usr/bin/osascript` · `/usr/sbin/diskutil` · `launchctl` · `git`).

## 4. 지시문 외 변경 · 구현 판단

### 4-1. 구현 판단

- **자식 출력을 통로 대신 임시 파일로 받음**: 처음 구현(`communicate`)은 06 자식이 끝났는데 손자 프로세스가 출력 통로를 붙잡고 있으면 상한(20분)까지 기다려 '시간 초과'로 잘못 기록했다(새 시험이 잡음). 자식의 종료만 기다리고, 끝난 뒤 자기 그룹에 남은 손자만 정리하도록 고쳤다.
- **완료 판정의 '필요한 D'** = 오늘 KST 의 06 실행 기록(수동 포함) 중 D 가 있는 가장 늦은 기록의 D. 06 이 이번 입력 · 달력으로 정한 값이며 자체 달력 계산은 없다. 06 기록이 없으면 '필요 기준일 확인 불가'로 둔다.
- **보관 대기**: 06 `archive.local_state` 미등록 수 + 등록 묶음 중 자동화 보관 시도에서 업로드 OK 를 받은 적 없는 것. 지금 맥북 = 미등록 4 · 미확인 묶음 1(10-23 수동 업로드 묶음 · 첫 자동 보관에서 '이미 OCI 에 있음 OK' 로 확인될 예정).
- **같은 종류 시도 사이 15분**: 로그인 직후 일정이 겹칠 때 같은 시각 두 번 부르지 않게 한 '같은 시각 중복 합치기'의 구현.
- **알림**: (날짜 · 상태)마다 한 번. 입력 지연은 시도가 남아 있으면 알리지 않는다. 지난 날 미완료는 다음 날 첫 tick 에 한 번.
- **C**: 외장 장치는 로컬 복사라 압축하지 않았다(PLAN §4-4). 10:00 ~ 15:45 KST 에는 시작하지 않는다. 네트워크 공유 · 확인 불가 장치는 WAITING_TARGET(판정 §2 마지막 줄 · §4 마지막 줄).

### 4-2. 독립 검토 1회(2026-10-28 · 읽기 전용 · 높음 1 · 중간 3 · 낮음 5 · 참고 2 → 고칠 것 모두 고침)

검토는 판정 §5-1 · §5-2 · §5-3, Q2, tar 풀기 안전성, status 읽기 전용, 시험의 tmp 격리에서 문제를 찾지 못했다고 보고했다.

| 지적 | 고친 것 | 시험 |
|---|---|---|
| 높음 — LaunchAgent 의 로그 폴더가 없으면 launchd 가 작업을 띄우지 못할 수 있음(설치는 OK 로 보고) | `install --apply` 가 `state/ml/operations/poc6_13/` 를 먼저 만듦 · `check` 에 launchd `last exit code` · 로그 폴더 유무 · status 에 0 아닌 종료 코드 표시 | 설치 뒤 폴더 존재 · `last exit code = 78` 해석 · 출력 |
| 중간 — 지난 날 실패가 다음 날 두 번째 tick 부터 사라짐(범위를 latest.json 날짜로 잡음) | 지난 날 = 자동화 첫 기록일 이후 최근 7일. 기록이 있는데 미완료인 날 + 기록 0 인 평일(거래일 여부 미확인 문구)만 한 문장으로 알림 · 주말 기록 0 은 표시만 | 두 번째 tick 뒤에도 표시 · 금 기록 0 알림 · 토 · 일 제외 · 첫 기록일 전 제외 |
| 중간 — COPY_HASH_OK 가 tar 안 파일을 원본 해시와 대조하지 않음(목적지끼리 비교) · 이름 바꾸기 전 동기화 없음 | 이름 바꾸기 전에 목적지 tar 의 파일별 해시 = 원본에서 읽은 해시 · 목록 일치 · `git bundle verify` · 모든 파일과 폴더 `F_FULLFSYNC` | 묶음 해시끼리는 맞고 tar 내용만 다른 경우 COPY_INCOMPLETE |
| 중간 — 내부 디스크의 디스크 이미지가 외장으로 통과할 수 있음 | `BusProtocol = Disk Image` 거부 · APFS 물리 저장소(`APFSPhysicalStores`)도 Internal 아님 · 디스크 이미지 아님 확인 | 디스크 이미지 · 내부 물리 저장소 위 APFS 거부 · 외장 물리 저장소 통과 |
| 낮음 — tick 이 끊기면 06 자식이 고아로 남을 수 있음 · 끝난 뒤 남은 것에 SIGTERM 만 | `run_child` 가 모든 예외(SystemExit · Ctrl-C)에서 자기 그룹 정리 뒤 다시 올림 · CLI `tick` 의 SIGTERM → SystemExit · 끝난 뒤 SIGTERM → 유예 → SIGKILL | 끊김 중 자식 정리 · SIGTERM 을 무시하는 손자도 정리 |
| 낮음 — INTERRUPTED 를 pid 생존으로만 판정(pid 재사용) | 자동 잠금 기준: 잠금을 쥔 tick 이 없으면 미완료 = INTERRUPTED · tick 안에서 남의 미완료 = INTERRUPTED · status 는 읽기 전용 공유 잠금 시도만 | 살아 있는 pid 여도 잠금 없으면 INTERRUPTED · 다른 tick 이 쥐면 RUNNING |
| 낮음 — D 를 모를 때 알림에 오늘 날짜를 D 로 씀 | 'D 확인 불가' | 수신 실패 날 알림 문구 |
| 낮음 — 백업 예외 경우(대조 · 이름 바꾸기가 caffeinate 밖 · verify 시간 막기 · 잠금 · id 형식 · manifest 기록 대조 · 단계 순서) | 대조 · 이름 바꾸기를 작업 생애 안으로 · verify 도 10:00 ~ 15:45 거부 · `.backup.lock` · `backup_id` 형식 검사 · 외장 manifest 해시 = 복사 때 기록 · 단계 순서 = 순번 | id · 시간 거부 · manifest 변조 거부. 이 시험이 **단계 기록 순번을 '파일 수'로 매기던 결함**(기록이 빠지면 번호가 겹쳐 쓰기 실패)을 잡아 '최대 번호 + 1'로 고침 |
| 참고(기존 동작) — 한 묶음 예외가 뒤 묶음 업로드를 막음 | `upload_research_many`: 실패 묶음만 FAILED · 나머지 계속 · 끝에서 예외(06 CLI 계약 그대로 CHECK_REQUIRED · 묶음별 결과는 예외의 `results`) | 가운데 묶음만 실패 → 앞 · 뒤 묶음 OCI 공개 · 목록 1회 |
| 참고 — `RunAtLoad` 는 설치 순간 tick 1회 | install 계획에 문구 · §7 승인 묶음에 적음 | — |

- **KS-10**: black 정리 뒤 `backup.py` 가 661줄(백엔드 650줄 기준 초과)이 되어 원본 쪽(`backup_source.py` · 대상 · 목적지 검사 · 계획)과 사본 쪽(`backup.py` · 복사 · 대조 · 복원)으로 나눴다. 동작 변경 없음. 최종 실측 269 · 553줄(§8-1).

### 4-3. 검증자 지적 정정(r1 F1 ~ F4 · r2 F3 · F4 잔여 · 같은 종류 포함)

모든 지적이 '실패 · 경계 밖 상태를 정상으로 보고'하는 같은 종류라, 지적된 줄만이 아니라 같은 경로 전체를 함께 봤다. r2 는 r1 정정이 F3 은 폴더 단계까지만, F4 는 실행 예외까지만 막았다는 지적이었다. 아래는 최종 코드 기준이다.

| 지적 | 정정(최종 코드) | 같은 종류로 함께 본 것 | 시험 |
|---|---|---|---|
| F1 — 자동화가 끊길 때 예외 경로가 자식만 기다리고 그룹 정리 없이 다시 올려 SIGTERM 을 무시하는 손자가 남음 | 예외 경로도 그룹 정리(`_reap_group` = SIGTERM → 유예 → SIGKILL) 뒤 다시 올림 · 자식 SIGKILL 뒤 기다림 | 시간 초과 · 정상 종료 경로는 이미 그룹 정리를 거침(확인) · caffeinate 는 terminate → kill 그대로 | 끊김 + SIGTERM 무시 손자 → 사라짐 |
| F2 — 대상 폴더 자체가 링크면 그 너머 파일을 묶음(시작 경로 경계 누락) | `real_path`: 경로의 어느 단계도 링크가 아니고 실제 경로 = 저장소 안 그 자리 → 대상 폴더 4개 · 봉인 DB 에 적용 | 상위 폴더(`state/ml/research`) 링크 · 봉인 DB 링크 · 목록 뒤 파일이 링크로 바뀐 경우(묶기 직전 재확인) · 봉인 DB 복사 직전 재확인 | 대상 폴더 링크 · 상위 폴더 링크 · 봉인 DB 링크 · 목록 뒤 바뀜 |
| F3 — 외장 목적지 아래 링크를 따라 내부 경로에 쓰거나(r1 · 폴더 단계), 외장 최종 폴더 안 파일이 내부 경로 링크인데 그 본문으로 대조 · 복원 확인(r2 · 파일) | 폴더: `_dest` = 백업 폴더 각 단계 링크 거부 · 실제 경로가 목적지 안 · 같은 장치(st_dev) → 어긋나면 WAITING_TARGET. 파일: `_open_ext` = 링크를 따라가지 않고(O_NOFOLLOW) 일반 파일 · 목적지 장치 번호가 같을 때만 열고 **연 그 파일에서** 해시. 이름 바꾸기 전 대조(묶음 5개 · tar 안 파일) · manifest 해시 · verify 의 manifest 읽기 · 되가져오기가 모두 이것만 쓴다 | verify 장치 검사 · 같은 경로 검사 · 최종 폴더 링크 거부 · manifest 묶음 목록 = 정해진 5개만(복사 때 기록이 없는 복원 포함) · 복원 임시 칸 정리 실패 표시(`cleanup`) | 폴더 링크 2단계 · verify 폴더 링크 · 비외장 · verify 파일 링크 6종(묶음 5 · manifest) · 복사 뒤 파일 링크 3종(DB · tar · manifest) · 다른 장치 번호(복사 · verify) · 묶음 목록 변조 |
| F4 — 해제를 확인하지 않고 OK(r1 · bootout 무시), 상태 조회 오류를 '없음'으로 보고 OK(r2) | `launchd._probe` 한 곳에서 `launchctl print` 응답을 셋으로 나눈다: 0 = 올라 있음 · 113('서비스 없음' · 이 맥북 실측 · 잘못된 도메인 = 112) = 없음 · 그 밖 종료 코드 · 실행 예외 = 확인 불가(None). `uninstall` 은 '없음'일 때만 plist 삭제 · OK, 나머지는 FAILED · plist 유지 | `check`(설치 · 상태 화면)도 같은 판정 · 상태 화면 '등록 확인 불가'(활성 아님과 구분) · CLI `uninstall` FAILED = 종료 코드 2(예전 0) · `install` 은 설치 뒤 '올라 있음'이 확인될 때만 OK(확인 불가도 FAILED · 기존) | 응답 5종(113 · 0 · 1 · 112 · 예외) · bootout 거절 · 이미 내려감 · check · 상태 문장 · CLI 종료 코드 |

- **변이 시험**(정정 하나씩 되돌림 · 내용 쓰기 + 수정 시각 복원 · `PYTHONDONTWRITEBYTECODE`): r1 4종(F1 · F2 · F3 · F4)에 이어, 최종 코드에서 r2 정정 10곳(O_NOFOLLOW · 되가져오기 · 복사 대조 · manifest 해시 · 장치 번호 · 묶음 목록 · verify manifest 읽기 · 조회 오류 판정 · 상태 문장 · CLI 종료 코드)과 §4-4 정정 12곳을 함께 되돌린 22종 모두 새 시험이 잡았다.
- **검증자 r2 재현 시험**(`test_adjacent.py` · 사본의 증거 출력 경로만 개발자 임시 폴더로 바꿈 · 검증자 폴더에 쓰지 않음)을 정정 뒤 코드로 실행 = 6 passed(이전 실패 3 포함).
- `_sync_all`(이름 바꾸기 전 동기화)은 링크를 막지 않는다. 링크 판정은 바로 뒤 대조(`_open_ext`) 한 곳에서 이유와 함께 거른다.

### 4-4. r2 정정 뒤 독립 검토 1회(2026-10-29 · 읽기 전용 · 같은 종류 6건 재현 → 모두 고침)

r2 지적과 같은 종류('실패 · 경계 밖 상태를 정상으로 보고')가 남았는지만 봤다. 검토자는 결함이 '있다'고 단언하는 재현 시험 9개를 남겼고, 정정 뒤 9개 모두 실패로 바뀌었다(결함 사라짐).

| 찾은 것 | 정정 | 시험 |
|---|---|---|
| 기대 해시를 외장에서 다시 읽어 잼 — manifest · env · inputs 가 쓴 뒤 바뀌어도 COPY_HASH_OK, 이어서 verify 도 RESTORE_VERIFIED(manifest 커밋을 비우면 '커밋 0개 확인') | `_write_new` = 새 파일로 쓰고 **쓴 바이트**의 해시를 기대값으로(env · inputs · manifest) · DB = 원본에서 읽으며 잰 값 · 이름 바꾸기 전 외장 manifest = 쓴 바이트 해시 대조 · 복원 = manifest 커밋 목록이 정해진 커밋과 같을 때만. tar · bundle 은 목적지에서 읽은 해시를 쓰되 tar 안 파일 = 원본 해시 · bundle = `git bundle verify` 로 따로 대조 | manifest 쓴 뒤 손상 · env · inputs 쓴 뒤 해시 재기 전 손상 · 커밋 목록 비움 |
| 원본 상위 폴더가 목록 뒤 링크로 바뀌면 범위 밖 내용이 묶임(마지막 단계만 검사) | 읽기 직전 `_source` = `real_path`(경로 모든 단계) 재확인 · 봉인 DB 도 복사 직전 같은 검사 | 상위 폴더 링크(크기 · 수정 시각 같음) · 봉인 DB 확인 뒤 링크 |
| 복사 기록을 읽지 못하면 '기록 없음'으로 보고 manifest 대조를 건너뜀 · 상태 화면은 읽지 못한 최신 기록 대신 앞선 RESTORE_VERIFIED 를 보임 | `_recorded_manifest` = 기록 파일이 없을 때만 None · 있는데 못 읽거나 해시 형식이 아니면 멈춤(RESTORE_FAILED) · `backup_state` = 읽지 못한 기록이 있으면 CHECK_REQUIRED | 기록 권한 0 · 해시 빠짐 · 깨진 JSON · 목록 JSON |
| git 조회 실패를 빈 출력으로 바꿔 COPY_HASH_OK 안에 `bundle_heads: []` · '코드 공백'으로 기록 | `git_bytes` = 0 아닌 종료는 멈춤 · 커밋에 없는 경로는 커밋별 `ls-tree` 목록으로 판정(`git show` 는 경로 없음 · 커밋 없음이 같은 오류 문구 · 실측) · bundle 머리 목록에 정해진 브랜치 2개가 있어야 함 | 없는 커밋 → COPY_INCOMPLETE · 머리 목록 빈 경우 · `git_bytes` 실패 예외 |
| 알림 실패(`NOTIFY_FAILED`)도 '보냄'으로 적어 다시 시도하지 않음 | 실패는 보냄 목록에 넣지 않음 → 다음 tick 에 다시 | 실패 → 다음에 다시 보냄 → 성공 뒤 없음 |
| caffeinate 가 바로 끝나도 '깨어 있음'(True) | 띄운 뒤 아직 살아 있을 때만 True | 바로 끝난 가짜 프로세스 → False |

- 기존 시험 1개를 바꿨다: '없는 커밋을 목록에 넣고 복사 → 복원에서 실패'는 이제 복사 단계에서 git 조회 실패로 멈춘다(의도한 변화). 복원 단계의 'bundle 에 없는 커밋' 검사는 **저장소에는 있고 bundle 브랜치 밖인 커밋**으로 계속 시험한다.
- 검토자가 확인하고 문제 없다고 한 것: `install` 확인 불가 뒤 bootstrap(끝난 뒤 올라 있어야 OK) · `uninstall` 113 만 삭제 · CLI 종료 코드 · diskutil 오류 → WAITING_TARGET · flock 오류 → REFUSED · COALESCED · `killpg` 권한 오류 · 06 대상이 비면 DONE 이 되는 경로 없음(24종 고정 검사).

## 5. 알려진 한계 / 미완성

- **가동 조건**: 맥북 잠자기 1분 · launchd 달력 일정은 잠든 맥북을 깨우지 않는다. 유효 창에서 예약 · 로그인 · 놓친 일정 복귀 중 하나가 실제로 시작되고 작업이 끝날 때까지 쓸 수 있어야 그날 기록이 생긴다. 사용자 답 = "평일 사용 가능 · 장담 불가" → 매일 기록 보장 아님. 기록이 없는 날은 상태 · 알림으로만 드러난다.
- **C = WAITING_TARGET**: 외장 장치 없음. 사용자 답(2026-10-29) = "백업은 PC 에서만" · 'PC' = 2TB · 맥북(내장 494GB 실측)과 다른 컴퓨터. 지금 구현은 맥북에 연결한 외장 장치에만 쓰고 네트워크 공유 · 다른 컴퓨터는 WAITING_TARGET 이라, PC 를 목적지로 쓰려면 연결 방식 · 비공유 범위를 설계자가 정해야 한다(판정 §2). 백업 크기 실측 ≈ 2.4GB(08 ~ 11 391,101,456 바이트 · 봉인 DB 1,862,836,224 바이트 · 코드 bundle 은 저장소 팩 193MB 이하) · 시작 조건 = 여유 공간 ≈ 3.3GB 이상. 그때까지 08 ~ 11 산출물 · 봉인 DB 는 맥북 단일 사본 그대로다.
- **알림 전달**: osascript 는 실제로 보였는지 알려 주지 않는다. 알림 설정에서 막혀 있으면 상태 파일 · CLI 로만 확인된다.
- **호출 사유**: SCHEDULED / CATCH_UP 은 시각 추정이다.
- **SSH 실패 날**: 06 `run --pull` 은 OCI 목록 조회 실패 시 예측을 하지 않는다(기존 계약). 그날 남은 시도에서 다시 부른다.
- **06 실행 기록 증가**: 자동 호출마다 06 run · report 파일이 생기고(이미 기록이어도) 보관 묶음도 하루 1 ~ 2개 늘어난다. Q2 로 원격 목록 조회는 작업당 1회가 됐지만, PC 쪽 묶음 목록 읽기는 묶음 수에 비례한다(로컬 파일 읽기).
- 첫 정기 실행 · 실제 설치 동작(macOS 백그라운드 항목 허용 포함)은 승인 뒤 연결 확인에서 본다.
- **외장 사본 대조의 한계**: 이름 바꾸기 전 목적지 재읽기 · verify 의 되가져오기는 OS 캐시에서 읽힐 수 있다(F_FULLFSYNC 뒤에도). 장치 자체의 늦은 손상까지 찾아낸다고 보장하지 않는다.
- **지난 날 알림의 '평일'**: 기록 0 인 평일을 알릴 때 거래일인지 확인하지 않는다(휴장 평일은 '거래일 여부 미확인' 문구로 그대로 알림). 자동 호출 판단에는 요일을 쓰지 않는다(설계 §3-1).
- `transfer.py` 는 517줄(기존 453 + Q2)이다.
- **원본 재확인 · 외장 대조의 범위**: 원본은 읽기 직전에 경로를 다시 확인하지만, 확인과 읽기 사이에 누군가 동시에 바꾸는 경우까지 막지는 않는다. COPY_HASH_OK 는 바이트 대조까지이고, 커밋 7개가 bundle 에 들어 있는지는 복원 확인(RESTORE_VERIFIED)에서 본다.
- **'서비스 없음' 판정**은 이 맥북에서 잰 `launchctl print` 응답 코드 113 하나만 쓴다. macOS 가 이 코드를 바꾸면 해제는 FAILED(plist 유지)로 멈춘다(성공 쪽으로 넘어가지 않음).
- **06 실행 기록이 없는 날의 15:20 뒤 상태 문장**: 필요한 D 를 모르므로(자체 달력 없음 · §4-1) 실제 마감이 지났는지 표시하지 못한다. 2026-10-29 18:31 KST 맥북 실측(읽기만 · 쓰기 0) = '예측 AUTO_WINDOW_CLOSED · 필요 기준일 확인 불가 · 수동 실행은 실제 마감 전까지 가능'이었고, 그날 D = 10-28 의 실제 마감(15:30)은 이미 지났다. 그 시각에 수동 실행해도 06 이 마감 뒤 진단 기록만 남긴다(새 주 기록 없음).

## 6. 다음 검증자(Codex)에게 알릴 점

- 공유 코드 변경은 Q2 한 곳이다: `transfer.upload_research` 는 `listing` 을 안 주면 예전과 같다. `upload_research_many` 는 목록 조회 실패를 예외로 두고, 원격 accept OK 인 묶음만 작업 안 목록에 반영한다.
- 완료 판정은 06 `records.primaries` 를 그대로 쓴다(영수증 해시 · id · D · confirmed_at < close_cutoff_at). 실제 06 산출물로 '영수증 없음 = 0', '다른 D = 0' 을 시험했다.
- tick 시험은 06 결과 · 06 산출물 읽기를 가짜로 바꿔 끼운다(`ST.view.runs_on/completion/archive_pending` · `runner.run_child`). 실제 06 읽기 · 06 CLI 업로드 경로는 06 시험 세계로 따로 확인했다.
- `status` 는 쓰지 않는다(시험 · 맥북 실측). `install` / `uninstall` / `backup run` / `backup verify` 는 `--apply` 없이는 쓰지 않는다.
- 시험은 라이브 state 를 열지 않는다(tmp · 06 시험 세계 복사본 · 가짜 외장 경로).
- 검증자 정정(§4-3): 원본 경계 = `backup_source.real_path` · `sealed_path` · 목적지 폴더 경계 = `backup._dest`(run · verify 둘 다) · 외장 사본 파일 경계 = `backup._open_ext`(`_hash_ext` · `_copy_hash(dev=)` 경유 · 이름 바꾸기 전 대조 · manifest 해시 · verify 의 manifest 읽기 · 되가져오기) · launchctl 응답 = `launchd._probe`(`check` · `uninstall` 공통 · 113 만 '없음') · CLI `uninstall` 종료 코드 · 끊김 = `runner.run_child` 예외 경로의 `_reap_group`.
- 독립 검토 정정(§4-4): 기대 해시 = `backup._write_new`(쓴 바이트) · `_check_written` 의 manifest 대조 · `_restore` 커밋 목록 · 원본 재확인 = `backup._source` · 기록 읽기 = `_recorded_manifest` · `status.backup_state`(CHECK_REQUIRED 는 화면 상태값만 · 기록 단계 아님) · git = `backup_source.git_bytes` · `code_refs`(`ls-tree`) · 알림 = `status.send_new` · caffeinate = `runner.awake`.
- 판단 항목: §5 마지막 줄(06 기록이 없는 날 15:20 뒤 '수동 실행은 실제 마감 전까지 가능' 문장)은 설계대로 D 를 모를 때의 문장이라 코드는 바꾸지 않았다.

## 7. 사용자 확인이 필요한 항목

1. **A · B 활성화 승인(한 묶음)**: `state/ml/operations/poc6_13/`(로그 폴더) · `~/Library/LaunchAgents/` 만들기 · 자기 plist 1개 · `launchctl bootstrap` · 정해진 `run --pull` / `archive --upload` 자동 호출 · 로컬 알림 · (macOS 백그라운드 항목 허용 = 사용자 조작). **설치 순간 tick 이 한 번 돈다(RunAtLoad)** — 10:00 ~ 15:20 에 설치하면 06 호출 · 업로드가 바로 시작된다. 판정 §4 대로 평일 사용 여건(답 = '장담 불가')을 받아들이는지 함께 확인.
2. **C 목적지**: 사용자 답(2026-10-29) = PC(2TB · 맥북과 다른 컴퓨터)에만. 맥북 → PC 연결 방식 · 비공유 범위는 설계자 확인 대상이다(지금 코드는 외장 장치용 · §5).
3. **커밋 · push**.

## 8. 검증 실측(2026-10-29 · 최신 정정 기준)

### 8-1. 정적 검사(새 · 바뀐 Python 13파일)

- `black --check` = "13 files would be left unchanged" · `flake8` 종료 코드 0 · `py_compile` 통과(r2 정정 뒤).
- 줄 수(r2 정정 · 독립 검토 정정 뒤 · `wc -l`): `schedule.py` 88 · `view.py` 114 · `status.py` 487 · `runner.py` 346 · `launchd.py` 185 · `backup_source.py` 269 · `backup.py` 553 · `run_forward_auto.py` 115 · `transfer.py` 517 · `run_forward_compare.py` 209 · 시험 1,123 · 744.
- KS-10 기준(백엔드 650 · 시험 1,500) 안이다. PLAN §5-1 목표 줄 수는 `status.py`(≤ 350) · `launchd.py`(≤ 160) · `test_poc6_13_forward_auto.py`(≤ 1,000)가 넘는다.

### 8-2. 시험

- 새 시험 116개(`test_poc6_13_forward_auto.py` 70 · `test_poc6_13_backup.py` 46 · r1 정정 시험 9 · r2 정정 시험 18 · §4-4 정정 시험 12 포함) 통과.
- 관련 05 · 06 · 13 시험 6파일 263개 통과(최종 코드 · 84.9초).
- 변이 r1 4종 · 최종 코드 22종(§4-3) 모두 잡힘 · 검증자 r2 재현 시험 사본 6 passed · §4-4 검토자 재현(결함 단언) 9개 모두 실패로 바뀜.
- **전체 회귀(최종 코드 · r2 정정 + §4-4 정정 뒤)**: `4928 passed, 2 skipped, 1 warning in 1272.73s (0:21:12)` · 실패 0 · 2026-10-29 19:14 ~ 19:35 KST(`caffeinate -i`). 회귀 뒤 `state/ml/operations/` · `~/Library/LaunchAgents/` 없음. 직전 회귀(r1 정정 뒤) 4898 passed 에서 늘어난 30 = 이번 새 시험 수.

### 8-3. 맥북 읽기 전용 실측(2026-10-28 16:27 KST 무렵 · 독립 검토 반영 전 코드 · 읽기 경로는 반영 뒤와 같음)

- `status`: 예측 DONE · D = 2026-10-27 · 주 기록 24/24 · 공개 확인 ~10-28 10:53:38 · 실제 마감 10-28 15:30 / 보관 NOT_TRIED · 미등록 4 · 미확인 묶음 1 / 백업 WAITING_TARGET / 일정 미설치.
- `install`(dry-run): DRY_RUN · 경로 `~/Library/LaunchAgents/com.krx-hyungsoo.poc6-13.forward-auto.plist` · LaunchAgents 폴더 만들 예정 · 실행 전후 폴더 없음.
- `backup plan`: 08 50파일 27,430,459 · 09 5 · 2,000,053 · 10 8 · 18,090,873 · 11 586 · 343,580,071 · 합계 649파일 391,101,456 · 봉인 DB 1,862,836,224 · 입력 연결 3묶음 모두 PC 보관소에 있음.
- 세 명령 전후 `state/ml/operations/` · `~/Library/LaunchAgents/` 없음(쓰기 0).
- 2026-10-29 18:31 KST(r2 정정 전 코드 · 읽기만): `status` = 예측 AUTO_WINDOW_CLOSED · 필요 기준일 확인 불가 / 보관 NOT_TRIED · 미등록 4 · 미확인 묶음 1 / 백업 WAITING_TARGET / 일정 미설치(§5 마지막 줄). `launchctl print`(자기 Label) = 종료 코드 113 · "Could not find service" · 잘못된 도메인(`gui/99999`) = 112. 전후 두 폴더 없음.

## 9. git 상태(보고 직전 실측 · `git status --short --untracked-files=all` · 2026-10-29 19:4x KST · r2 정정 · §4-4 정정분 포함)

```text
M  .gitignore
A  app/forward_auto/__init__.py
A  app/forward_auto/backup.py
A  app/forward_auto/backup_source.py
A  app/forward_auto/launchd.py
A  app/forward_auto/runner.py
A  app/forward_auto/schedule.py
A  app/forward_auto/status.py
A  app/forward_auto/view.py
M  app/ml_evidence/transfer.py
M  docs/PROGRAM_TRUTH.md
M  docs/STATE_LATEST.md
A  docs/ai_design/POC6/POC6-12_ETF_DISTRIBUTION_AND_TOTAL_RETURN_DATA_VALIDATION_DESIGN_V1.md
A  docs/ai_design/POC6/POC6-12_ETF_DISTRIBUTION_AND_TOTAL_RETURN_DATA_VALIDATION_PLAN_DECISION_2026-10-28.md
A  docs/ai_design/POC6/POC6-13_FORWARD_COMPARISON_DAILY_AUTOMATION_AND_RECOVERY_DESIGN_V1.md
A  docs/ai_design/POC6/POC6-13_FORWARD_COMPARISON_DAILY_AUTOMATION_AND_RECOVERY_PLAN_DECISION_2026-10-28.md
A  docs/ai_design/POC6/POC6_DATA_USE_RETENTION_AND_PUSH_CONNECTION_AUDIT_REQUEST_2026-10-27.md
A  docs/ai_plan/POC6/POC6-12_ETF_DISTRIBUTION_AND_TOTAL_RETURN_DATA_VALIDATION_PLAN_V1.md
A  docs/ai_plan/POC6/POC6-13_FORWARD_COMPARISON_DAILY_AUTOMATION_AND_RECOVERY_PLAN_V1.md
A  docs/ai_result/POC6/POC6-13_FORWARD_COMPARISON_DAILY_AUTOMATION_AND_RECOVERY_RESULT.md
A  scripts/run_forward_auto.py
M  scripts/run_forward_compare.py
A  tests/test_poc6_13_backup.py
A  tests/test_poc6_13_forward_auto.py
?? docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md
```

- 모든 변경이 staged(오른쪽 칸 공백). `??` 1개 = 사용자 소유 handoff 문서(stage 하지 않음).
- POC6-12 문서 4개(설계 · PLAN 판정 · 점검 요청 · PLAN)는 POC6-12 작업분으로 같은 stage 에 있다(POC6-12 PLAN = 머리말 · §7 원천 확인 · 10-29 §7-3 D = 10-28 결측 · §7-6 SEIBro API 가입 결과).
- 커밋 · push 0(사용자 승인 대기). 맥북 LaunchAgent · OCI · 외장 장치 변경 0.

## 10. 검증자 r1 판정 — 2026-10-28 · Codex

### 1) A. 기능/산출물 검증

- **A-1 지시 일치: 위반(F1~F4).** 일반 일정/보관 흐름, 마감 전 영수증을 이용한 주 기록 판정, A/B 별도 재처리, Q2 단건 호환·작업당 목록 1회 시험은 통과했다. 그러나 기존 계약인 자기 프로세스 그룹 정리, 백업 대상/다른 물리 저장소 경계, 일정 해제의 실패 처리가 아래 경로에서 충족되지 않는다.
- **A-2 보고 정확성: 일부 위반(F1~F3).** 시작 시 staged 24개(A 19·M 5), unstaged 0, 사용자 handoff untracked 1개이며 §9와 일치한다. 변경 Python 13파일·파일별 줄 수·관련 시험 224건도 보고와 같다. 상단 SCOPE의 모듈 수 6만 실제 8로 직접 정정했다. 이 숫자 정정은 반려 사유가 아니다. 프로세스 정리·심볼릭 거부·외장 사본 경계의 보장에는 아래 코드 공백이 있다.
- **A-3 산출물 정합성: 위반.** 독립 재현에서 중단 뒤 프로세스가 남고, 비대상 소스 포함 및 내부 경로 쓰기도 COPY_HASH_OK로 보고되며, 해제 실패도 OK로 끝난다. 모든 재현은 임시 프로세스·폴더·가짜 OS 응답만 사용했다. 실제 운영 자료의 유출이나 실제 설치 실패가 발생했다는 판정이 아니다.
- **A-4 금지사항 위반: 실제 실행 위반 없음.** 검증 중 실제 설치·업로드·외장 장치 쓰기·운영 데이터 접근은 하지 않았다. F2는 실제 적용 시 선택하지 않은 자료를 포함할 수 있는 코드 경계 결함이다. 신규 의존성·OCI/API/DB 스키마 변경은 없다.

**F1 [P2] — 자동화 중단 시 SIGTERM을 무시하는 손자 프로세스가 남음**

- 위치: `app/forward_auto/runner.py:117~126`의 `run_child` 예외 처리.
- BaseException을 받으면 그룹에 SIGTERM을 보낸 뒤 직접 자식의 종료만 기다린다. 자식이 바로 끝나면 `raise`로 나가 정상 경로의 `_reap_group`을 거치지 않으며, 남은 손자에게 SIGKILL이 전달되지 않는다. 판정 §4의 중단/실패 때 자기 그룹을 남기지 않는 계약과 다르다.
- 독립 재현은 제출 시험의 '중단'과 'SIGTERM 무시 손자'를 결합했다. 임시 자식이 시작한 손자는 SIGTERM 무시 설정을 끝낸 뒤 준비 파일을 쓰고, 그때 wait에 SystemExit(143)을 발생시켰다. 직접 자식은 종료됐지만 손자는 살아 있었다. 재현 finally에서 검증자가 자기 그룹에 SIGKILL을 보내 정리했고 그룹 소멸도 확인했다. 사용자의 수동 프로세스에는 신호를 보내지 않았다.

**F2 [P2] — 백업 대상 폴더 자체가 링크이면 범위 밖 원본까지 포함함**

- 위치: `app/forward_auto/backup_source.py:143~158`의 `inventory`.
- 하위 폴더·파일의 링크는 거절하지만 대상 루트 `root` 자체는 `is_dir()` 후 `os.walk`를 시작한다. `followlinks=False`는 시작 경로 자체가 링크인 경우를 거절하지 않는다.
- 임시 저장소의 `poc6_08` 루트를 별도 임시 폴더로 연결하고, 그 안에 시험용 비대상 `outside.txt`를 뒀다. inventory는 이를 `state/ml/research/poc6_08/outside.txt`로 채택했고 실제 백업 tar에도 그 내용이 포함되며 COPY_HASH_OK로 끝났다. 선택한 자료만 포함하고 대상 밖 링크를 거절하는 설계 §6-1·§6-2 및 PLAN §4-5 계약을 충족하지 못한다.

**F3 [P2] — 외장 목적지 아래의 링크를 따라 내부 경로에 써도 사본 완료로 보고함**

- 위치: `app/forward_auto/backup.py:144~153`, `_dest` 및 `_write`의 목적지 생성(`part.mkdir`, 213줄).
- 장치 확인은 전달받은 target까지만 한다. 그 아래 실제 출력 경로 `krx_hyungsoo_private_backup/poc6_13/<id>`의 경계는 확인하지 않은 채 부모를 따라 만든다.
- 가짜 외장 target의 `krx_hyungsoo_private_backup`을 별도 임시 내부 목적지로 연결했다. 외장 장치 확인 응답은 target에만 주입했으며 연구/봉인 파일은 모두 시험용이다. run은 내부 목적지에 tar·DB·bundle·manifest를 쓰고 COPY_HASH_OK를 돌려줬다. 바이트 대조는 통과하지만 다른 물리 저장소의 사본이라는 판정 §2·PLAN §4-4 조건을 보장하지 못한다. 실제 외장 장치 연결이나 내부 운영 자료 쓰기는 없었다.

**F4 [P2] — 일정 해제 실패를 OK로 보고하고 plist도 삭제함**

- 위치: `app/forward_auto/launchd.py:155~163`의 `uninstall` 및 CLI의 해제 응답 전달 경로.
- `launchctl bootout`의 결과와 관계없이 자기 plist를 삭제하고 `status=OK`를 돌려준다. 해제가 거절돼 작업이 계속 등록된 경우에도 비활성화 성공으로 보일 수 있다.
- 임시 plist와 상태를 유지하는 가짜 Launchctl로, bootout은 rc 5로 거절하고 후속 print는 여전히 활성(rc 0)인 경우를 만들었다. 함수는 `status=OK, bootout_rc=5`였고 plist는 삭제됐다. 이는 이미 해제돼 있어 bootout이 0이 아닌 경우와 구분한 재현이다. 실제 launchctl 설치/해제는 실행하지 않았다.

### 2) B. 구현 규칙/구조 품질 검증

- **B-1 fallback 위반: 있음(F4).** 일정 해제 실패의 성공 상태 대체가 있다. Q2의 원격 목록 조회 실패를 빈 목록으로 바꾸는 경로는 발견하지 않았으며 관련 시험도 통과했다.
- **B-2 단일 책임 위반: 없음.** 일정·06 읽기·상태·프로세스·설치·백업 원본/사본 책임은 분리돼 있다.
- **B-3 파일 책임 과다: 없음.** 변경 Python 13파일이 KS-10 상한 안이며 status 473·transfer 517줄이다. PLAN의 목표 줄 수 초과와 실제 상한 위반을 구분했다.
- **B-4 실험/운영 경계 위반: 없음.** 06의 가격/모델/예측 계약을 바꾸지 않고 기존 CLI를 호출한다. 새 상태는 06 연구 폴더 밖에 분리돼 있다.
- **B-5 배포/실행 경로: 추적/경로 일치.** CLI·신규 패키지·시험은 Git 추적/staged이다. 기존 OCI 배포 스크립트와 Dockerfile 경로 변경은 없다. 로컬 실행 생애/해제의 F1·F4는 위 기능 결함으로 기록했다.
- **B-6 별도 구조적 퇴행: 없음.** F1~F4 이외의 stale 성과 재사용·범용 백업 계층·영구 원격 목록 캐시는 발견하지 않았다.

### 3) 기반 문서 준수

연구 한정·Q6 OPEN·운영 ML 미승격은 유지된다. 새 문서는 설계/판정/PLAN/결과서 범위로 공개돼 있다. 같은 stage의 POC6-12 문서 4개는 목록과 소유 범위만 확인했고 POC6-12의 수집/이용 조건을 판정하지 않았다. 사용자 handoff는 이름만 확인했으며 읽기·수정·stage하지 않았다. znotes·실제 .env·라이브 DB/보유 파일에도 접근하지 않았다.

### 4) 코드 안전성

**위험 수준: MEDIUM.** 자동화 중단/해제 뒤 작업이 남을 수 있고, 백업의 소스/목적지 링크 경계가 실제 선택·다른 물리 사본 조건을 벗어날 수 있다. 현재 실제 설치·업로드·외장 쓰기가 승인됐다는 의미는 아니며, 그 동작을 검증 중 실행하지 않았다. 제출 시험은 통과하지만 독립 재현 4건이 각 계약 위반을 확인한다.

### 5) 범위 폭주

**폭주 수준: MINOR.** backup_source 분리와 실패 묶음 뒤 업로드 계속 처리는 공개된 판단이며 Q2의 작은 공유 접점 안이다. 별도 운영 모델·UI·API·원격 백업 형식 확대는 없다. C의 장치 미정/WAITING_TARGET 자체와 POC6-12의 대기는 반려 사유로 삼지 않았다. 새 위조 방지 체계나 모든 실행 이력 인증을 요구한 검증도 아니다.

### 6) 종합 판정

**REJECTED — 기존 계약의 프로세스 정리·백업 경로 경계·일정 해제 실패 처리에서 P2 코드 결함 F1~F4를 확인했다. 문서의 모듈 수 정정이나 실제 C 목적지 미정 때문에 반려한 것이 아니다.**

| 검증자 실측 | 결과 |
|---|---|
| 고정 소스 | HEAD `da643ed57e711a705d3210adf6962324da315cf6` 대비 staged 24개(A 19·M 5)를 저장소 밖 사본으로 추출. unstaged 0·사용자 handoff untracked 1 |
| 관련 시험 | 05 store/daily·06 core/flow·13 auto/backup, 6파일 `224 passed`(76.45초) |
| 독립 재현 | 별도 `test_independent.py`에서 4건 모두 실패(17.62초). 제출 시험 실패와 구분. 일정 해제는 활성 상태가 유지되는 OS 응답을 명시한 대조에서도 동일 |
| 프로세스 정리 | 재현에서 남은 자기 프로세스 그룹은 finally에서 정리하고 소멸을 확인 |
| 정적 검사 | 변경 Python 13파일 black --check·flake8·py_compile 통과 |
| 범위 확인 | 실제 LaunchAgent 설치/해제·06 운영 실행·원격 업로드·외장 장치 쓰기·공식 연구/학습 실행 없음. 복사/해시/복원은 가짜 자료·임시 경로만 사용 |
| 전체 회귀 | 개발자의 최종 코드 `4889 passed, 2 skipped` 보고를 참고했고 재실행하지 않았다. 공유 접점 검증은 위 224건으로 수행 |

근거: `/private/tmp/poc613-r1-verify-shuy3s08/`의 `related.log`, `test_independent.py`, `independent.log`, `uninstall-control.log`, `interrupted-process.json`, `source-root-symlink.json`, `destination-child-symlink.json`, `failed-uninstall.json`, `cleanup.json`, `black.log`, `flake8.log`, `checks.json`. 임시 상태·DB·외장 경로 주입과 실행한 재현을 코드/로그에서 확인할 수 있다.

검증자가 직접 수정한 곳(이 결과서 한 파일만):

| 위치 | 수정 전 → 수정 후 |
|---|---|
| 상단 STATUS·VERIFIER | 검증자 대기 → r1 REJECTED(F1~F4) 기록 및 VERIFIER 줄 추가 |
| 상단 SCOPE | `app/forward_auto/` 모듈 수 6 → 실제 8. 숫자 정정이며 반려 사유 아님 |
| §10 | 없음 → 검증 근거·독립 재현 4건·판정 추가 |

코드·시험·다른 문서는 수정하지 않았다. 커밋·push·배포·설치·업로드는 하지 않았다.

### 7) 사용자에게 한마디

다음은 개발자 정정이다. 이번 4건은 이미 정해진 실패 처리와 경로 경계의 코드 결함이므로 별도 설계 판단을 기다릴 사안이 아니다. 실제 활성화 승인은 정정·재검증·설계자 RESULT 판정 뒤이며, C 목적지는 정해질 때 별도로 확인한다.

## 11. 검증자 r2 판정 — 2026-10-28 · Codex

### 1) A. 기능/산출물 검증

- **A-1 지시 일치: 일부 위반(F3·F4 잔여 경로).** r1의 정확한 재현 4건은 모두 통과했다. F1의 중단 후 손자 정리, F2의 원본 루트 링크 거절, F3의 목적지 하위 폴더 링크 거절, F4의 작업이 여전히 등록된 경우 실패 처리는 확인됐다. 그러나 외장 사본의 파일 경계와 해제 확인 불가 처리는 아래 경로에서 미충족이다.
- **A-2 보고 정확성: 일부 위반.** 시작 시 staged 24개(A 19·M 5), unstaged 0, 사용자 handoff untracked 1개가 §9와 같다. 관련 시험 233건·Python 13파일의 정적 검사·결과서 §8-1 줄 수도 실측과 일치한다. §4-3의 '내부 경로 사본을 외장 복원 확인으로 보고하지 않게', '확인 불가 = FAILED' 보장에는 코드 공백이 남아 있다. PLAN §5-1의 두 파일 줄 수는 지난 실측값이어서 검증자가 현재 값으로 직접 정정했다. 이 숫자 정정은 반려 사유가 아니다.
- **A-3 산출물 정합성: 위반.** 파일 내용·manifest·해시를 바꾸지 않은 내부 경로 링크가 RESTORE_VERIFIED로 보고되고, 상태 조회의 일반 오류가 일정 해제 OK로 보고된다. 제출 시험이 통과해도 이 두 경우의 결과는 기존 계약과 다르다.
- **A-4 금지사항 위반: 실제 실행 위반 없음.** 실제 설치·해제·원격 업로드·외장 장치 쓰기·운영 자료 접근 없이 임시 자료와 가짜 OS/장치 응답만 사용했다. 신규 라이브러리·외부 API·DB 스키마 변경도 없다.

**F3 잔여 [P2] — 외장 백업의 파일이 내부 경로 링크여도 RESTORE_VERIFIED로 보고함**

- 위치: `app/forward_auto/backup.py:369`의 최종 폴더 검사 및 `_restore`의 `427~429`줄.
- `_dest`와 최종 폴더의 링크는 거절하지만, 그 안에서 읽는 `manifest.json`과 artifact 파일의 실제 경계는 확인하지 않는다. `_copy_hash(final / n, ...)`가 파일 링크를 따라간다.
- 독립 재현: 가짜 외장 경로에 정상 백업을 만든 뒤, 봉인 DB 사본 한 파일만 별도 임시 내부 경로로 옮기고 원위치에 링크를 뒀다. manifest·기록·해시·파일 내용은 전혀 바꾸지 않았다. 외장에는 해당 본문이 없는데 verify는 RESTORE_VERIFIED, ok=true를 반환했다. 연구 tar 파일도 같은 방법으로 같은 결과가 나왔다.
- 이는 바이트 손상을 탐지하지 못했다는 주장이 아니다. 읽은 바이트는 정확하지만 현재 외장 장치에 독립된 본문 사본이 없는데도 외장 사본 복원 확인으로 기록하는 문제다. 판정 §2의 다른 물리 저장소 계약 및 §4-3의 공개 보장 범위에 직접 해당한다. 새 서명·위조 방지 체계나 과거 실행 재현을 요구하는 판정이 아니다.

**F4 잔여 [P2] — 상태 조회 명령의 일반 오류를 '내려감'으로 판정함**

- 위치: `app/forward_auto/launchd.py:181~191`의 `_loaded`, 이를 사용하는 `165~178`줄.
- `_loaded`는 실행 예외일 때만 확인 불가(None)를 반환하고, `launchctl print`가 실행된 뒤 0이 아닌 코드로 끝나면 모두 False를 반환한다. 서비스가 없다는 응답과 조회 자체의 오류를 구분하지 않는다.
- 독립 재현: 가짜 OS가 bootout에 rc=5 실패를, 후속 print에 rc=1과 `Operation not permitted` 오류를 돌려줬다. 작업 부재를 확인한 응답이 아닌데 결과는 status=OK, loaded_after=false가 됐고 자기 plist도 삭제됐다.
- 대조군인 서비스 없음(rc=113)은 OK·plist 삭제, 아직 등록됨(rc=0)은 FAILED·plist 유지, 조회 실행 예외(OSError)는 FAILED·plist 유지로 통과했다. 특정 실제 Mac에서 이 오류가 발생했다고 주장하지 않으며, 일반 실패 응답을 성공으로 바꾸는 코드 경로를 가짜 OS로 재현한 것이다. 설계 §9의 일정 비활성화 및 §4-3의 '확인 불가 = FAILED·plist 유지' 계약에 위배된다.

### 2) B. 구현 규칙/구조 품질 검증

- **B-1 fallback 위반: 있음(F4).** 조회 오류를 미등록(false)으로 대체해 해제 성공으로 진행한다.
- **B-2 단일 책임 위반: 없음.** 자동 실행·상태·설치·백업 원본·복사/복원 경계는 분리돼 있다.
- **B-3 파일 책임 과다: 없음.** 변경 운영 Python 최대 517줄이며 KS-10 상한 안이다. PLAN의 예상 줄 수와 실제 구현 줄 수는 구분했다.
- **B-4 실험/운영 경계 위반: 없음.** 06의 주 기록 판정 재사용과 A/B 분리 호출은 유지된다. Q2 공유 변경은 r1과 같고 관련 05·06 시험을 다시 통과했다.
- **B-5 배포/실행 경로 영향: 경로 누락 없음.** 보고된 CLI·모듈·설계/PLAN/결과서가 index에 추적돼 있고 실행 경로와 맞는다. 이번 라운드 파일 이동·신규 실행 경로가 없으며 Dockerfile/OCI 호출 변경도 없다. 실제 설치·C 목적지 연결은 승인 전으로 남긴다.
- **B-6 기술부채/구조적 퇴행: 위 두 경계 결함 외 추가 위반 없음.** r1 대비 코드 4개·시험 2개·문서 2개 변경을 확인했다. 원본 손상/대상 밖 자료를 정상 처리하던 r1 F2 경로는 거절로 바뀌었다.

### 3) 기반 문서 준수

신규 Markdown은 설계·판정·PLAN·결과 보관용이며 신고돼 있다. 신규 의존성·MongoDB·UI 프레임워크·운영 계산 복제는 없다. 같은 stage의 POC6-12 문서는 별도 단계임을 유지했고 이번에 판정하지 않았다. C 장치 미정과 실제 설치 승인 대기는 격리 구현 자체의 반려 사유가 아니다.

### 4) 코드 안전성

**위험 수준: MEDIUM.** F3은 두 번째 물리 사본이 없는 상태를 완료로 기록할 수 있고, F4는 해제 확인에 실패했는데도 해제 완료로 기록할 수 있다. 임시 재현에서 확인한 잠재 경로이며 실제 자료 손실·실제 일정 잔류 발생 보고는 아니다. F1 재현에서 띄운 자기 프로세스 그룹은 종료됐고 손자 잔류도 없었다.

### 5) 범위 폭주

**폭주 수준: MINOR.** r1 지적과 같은 경로 보강 및 cleanup 표시가 공개돼 있고 목적과 직접 연결된다. 승인 없는 실제 실행은 없다. 신규 검증 대상이나 전수 위조 방지 체계를 추가하지 않았다.

### 6) 종합 판정

**종합 판정: REJECTED.** 문서 수치 불일치 때문이 아니라 F3·F4 잔여 경로의 코드 동작 때문이다.

| 검증 | 실측 결과 |
|---|---|
| 관련 05·06·13 시험 | 6파일 **233 passed**, 81.04초. 저장소 밖 index 사본·임시 상태/DB 사용 |
| r1 정확한 독립 재현 | **4 passed**, 17.36초. 소스 루트 링크의 명시적 거절을 성공으로 인정 |
| 추가 경계 대조 | **3 failed·3 passed**, 1.91초. 실패 3건 = F3 파일 2종·F4 일반 조회 오류 1종, 통과 3건 = F4 대조군 |
| 정적 검사 | Python 13파일 black --check·flake8·py_compile 모두 통과 |
| 범위 대조 | 검증 중 소스·HEAD·index 변경 없음 확인. 모든 대상이 index에 있고 untracked는 제외한 사용자 문서 1개뿐 |
| 전체 회귀 | 개발자 최종 코드의 **4898 passed·2 skipped** 보고를 참고. 전체 회귀·공식 연구 실행은 다시 하지 않음 |
| 실제 작업 | LaunchAgent 설치/해제·자동 업로드·06 운영 호출·외장 장치 쓰기·라이브 데이터 접근·커밋·push 모두 없음 |

근거: `/private/tmp/poc613-r2-verify-ofmxpfe4/`의 `related.log`, `test_r1_reproductions.py`, `r1-reproductions.log`, `test_adjacent.py`, `adjacent.log`, `uninstall-*.json`, `restore-link-*.json`, `checks.json`, `black.log`, `flake8.log`. 외장 장치 판단은 가짜 응답을 주입했고 실제 OS 명령은 호출하지 않았다. 경계 시험에서 만든 Git 저장소·자료는 모두 임시 경로다.

검증자가 직접 수정한 곳:

| 파일·위치 | 수정 전 → 수정 후 |
|---|---|
| 이 결과서 상단 STATUS·VERIFIER | r2 대기·r1 REJECTED → r2 REJECTED(F3·F4 잔여 경로, §11) |
| 이 결과서 §11 | 없음 → r2 재현·검증 근거·판정 추가. 기존 §10 원문 보존 |
| PLAN §5-1의 백업 모듈 줄 수 | `243 · 436(실측)` → `256 · 469(r2 실측)`. 실측 숫자 정정이며 반려 사유 아님 |

운영 코드·시험·설계자 판정 원문·기타 문서는 수정하지 않았다.

### 7) 사용자에게 한마디

기존 재현 4건은 해결됐으나, 같은 F3·F4 경계에 코드 결함이 남아 재작업이 필요하다. 다음은 개발자 정정이며, 현재 검증에 새 사용자 결정이나 설계 판단이 필요한 항목은 없다. 실제 활성화·C 목적지·커밋/push 승인 조건은 그대로다.

## 12. 검증자 r3 판정 — 2026-10-29 · Codex

### 1) A. 기능/산출물 검증

- **A-1 지시 일치: 통과(격리 구현 범위).** r1·r2 독립 재현 10건을 현재 index 사본에 다시 적용해 모두 통과했다. F1 중단 후 자기 프로세스 그룹 정리, F2 원본 루트/상위 링크 거절, F3 목적지 폴더 및 외장 사본 파일 경계, F4 상태 조회 실패의 성공 대체 방지가 확인됐다. 일정 창·실제 D·마감 전 영수증·실제 분모를 이용한 완료 판정, A/B 별도 시도, Q2 목록 1회·단건 호환은 관련 시험으로 다시 확인했다.
- **A-2 보고 정확성: 통과.** staged 24개(A 19·M 5), unstaged 0, 사용자 handoff untracked 1개가 §9와 일치한다. r2 대비 변경 13개는 코드 6·시험 2·문서 5이며 제출 목록과 같다. 파일별 줄 수·새 시험 116건·관련 시험 263건이 실측과 같다. §8 제목의 지난 날짜만 검증자가 직접 정정했다(아래 수정 내역). 숫자·메타 정보 정정을 코드 결함으로 취급하지 않았다.
- **A-3 산출물 정합성: 통과.** r2의 DB/tar 내부 경로 링크 재현은 이제 RESTORE_FAILED가 된다. bootout 실패 뒤 print 일반 오류 재현은 FAILED·loaded_after=null·plist 유지로 바뀌었다. 서비스 없음 대조군만 OK·plist 삭제이며, 아직 등록됨/조회 실행 예외 대조군도 구분한다. 기록/해시/실패 표시 보강 6건은 §4-4의 설명과 코드·시험이 일치한다.
- **A-4 금지사항 위반: 없음.** 신규 의존성·외부 API·DB 스키마 변경·추가 파일 삭제가 없다. 검증은 저장소 밖 임시 자료·DB·프로세스와 가짜 장치/OS 응답만 사용했다. 실제 LaunchAgent 설치/해제·알림·06 운영 실행·업로드·외장 장치 쓰기·라이브 자료 접근은 하지 않았다.

**정정 확인 범위**

| 대상 | 확인한 결과 |
|---|---|
| F1·F2와 F3 폴더 경계 | r1 정확한 독립 재현 4건 통과. SIGTERM 무시 손자는 남지 않았고, 원본 루트 링크는 명시적으로 거절되며 목적지 하위 링크에 쓰지 않음 |
| F3 파일 경계 | `_open_ext`가 O_NOFOLLOW·fstat의 일반 파일/장치 번호를 확인. manifest 읽기·복사 전 대조·되가져오기에 같은 검사를 사용. r2 DB/tar 링크 재현 2건이 RESTORE_FAILED로 끝남. 관련 시험은 묶음 5개+manifest 링크·다른 장치·목록 제한도 확인 |
| F4 해제 | `_probe`가 0/113/나머지 오류·예외를 구분하고 check/uninstall에서 재사용. 조회 오류는 미등록으로 대체되지 않음. CLI 실패 종료 코드 2와 등록 확인 불가 문장도 관련 시험 통과 |
| 기대 해시·원본 재확인 | env/inputs/manifest는 쓴 바이트, DB는 원본에서 읽으며 잰 해시로 대조. tar는 파일별 원본 해시, bundle은 Git 검사로 대조하는 예외를 §4-4에 공개. 원본은 읽기 직전 상위 경로를 재확인 |
| 기록·Git 조회 | 복사 기록이 있는데 읽지 못하거나 해시가 없으면 복원 실패. 손상된 단계 기록은 CHECK_REQUIRED. Git 조회 실패를 빈 사실로 기록하지 않으며, 없는 경로는 ls-tree 목록으로 구분 |
| 알림·유휴 절전 방지 | 실패한 알림은 보냄 목록에 넣지 않아 다음 tick에 재시도. caffeinate가 즉시 종료된 경우 awake=false. 관련 격리 시험 통과 |

### 2) B. 구현 규칙/구조 품질 검증

- **B-1 암묵 fallback 위반: 없음.** r2의 조회 오류→미등록 대체는 제거됐다. 이번 보강의 기록/Git 조회 실패도 정상 또는 없음으로 바꾸지 않는다.
- **B-2 단일 책임 위반: 없음.** 일정·상태·자식 실행·설치·백업 원본·복사/복원 역할을 분리했다. 이번 보강은 기존 책임 안에 있다.
- **B-3 파일 책임 과다: 없음.** 새 운영 모듈 최대 `backup.py` 553줄, 공유 `transfer.py` 517줄, 시험 1,123·744줄로 KS-10 상한 안이다. PLAN의 예상 목표를 넘은 status/launchd/시험 파일은 §8-1에 공개됐으며 강제 상한 위반과 구분했다.
- **B-4 실험/운영 경계 위반: 없음.** 기존 06 CLI를 별도 자식으로 호출하고 주 기록 판정을 재사용한다. Q2 공유 코드 2파일은 r2와 해시가 같고 관련 05·06 시험을 다시 통과했다. 기존 공식 연구·학습은 재실행하지 않았다.
- **B-5 배포/실행 경로 영향: 없음.** 안내된 CLI·모듈·문서 모두 index에 추적돼 있다. 이번에 파일 이동·새 실행 경로가 없으며 Dockerfile·OCI 호출 변경도 없다. 실제 설치·연결 확인은 별도 승인 후 단계다.
- **B-6 기술부채/구조적 퇴행: 없음.** 기존 자료·옛 코드를 현재 값으로 대체하지 않는다. 실제 자료 재계산·성과 변경·범용 백업기 확장은 없다. 113은 현 환경의 서비스 없음 응답으로 공개했고 다른 응답은 성공 대신 확인 불가로 남긴다.

### 3) 기반 문서 준수

새 Markdown은 신고된 설계·판정·PLAN·결과 보관용이며 r3에서 새 파일은 늘지 않았다. MongoDB·새 UI 프레임워크·의존성 주입 체계·무시험 운영 코드 추가는 없다. 기존 실험/운영·OCI 미전송 경계를 유지한다. 같은 stage의 POC6-12 문서는 별도 단계로 식별했으며 SEIBro 가입 경로나 해당 단계의 진행 여부는 이번 판정 대상이 아니다.

### 4) 코드 안전성

**위험 수준: LOW(공개 한계·실제 연결 미확인).** 검증 범위에서 차단할 코드 결함은 발견하지 않았다. 원본 확인과 읽기 사이의 동시 교체, OS 캐시 이후 장치 손상, 맥북 잠자기, 알림 실제 표시 여부는 공개 한계이며 완전 방어·매일 기록 보장으로 해석하지 않는다. 외장 장치 부재는 WAITING_TARGET으로 유지한다.

06 기록이 없는 날은 필요한 D/실제 마감을 확정할 수 없어 AUTO_WINDOW_CLOSED와 조건부 '수동 실행은 실제 마감 전까지 가능' 문장이 남는다. 이는 판정 §5-3의 확인 불가 표시·자체 달력 계산 금지와 일치하며, 그 시각에 주 기록 생성이 가능하다고 인증한 결과가 아니다. 결과서 §5·§6의 설명을 유지한다.

### 5) 범위 폭주

**폭주 수준: MINOR.** 실패/경계 상태 보강 6건·CHECK_REQUIRED 표시·CLI 실패 종료 코드가 공개돼 있고 기존 요구에 직접 연결된다. 새로운 플랫폼·저장소·자동 실행 범위는 추가하지 않았다. 실제 설치·외장 쓰기·커밋/push 승인은 여전히 별도다.

### 6) 종합 판정

**종합 판정: VERIFIED — 격리 구현 및 정정 범위.** A/B 전체 통과. C의 실제 외장 백업 완료나 자동 실행 활성화 완료를 뜻하지 않는다.

| 검증 | 실측 결과 |
|---|---|
| 관련 05·06·13 시험 | 6파일 **263 passed**, 96.46초. 그 안의 POC6-13 새 시험 **116건**(70+46) 포함 |
| r1·r2 독립 재현 | **10 passed**, 19.19초. r1 4건 + r2 6건(정상 대조군 포함) |
| 정적 검사 | 변경 Python 13파일 black --check·flake8·py_compile 모두 통과 |
| 소스 대조 | HEAD `da643ed57e711a705d3210adf6962324da315cf6`, staged 24개·unstaged 0. 검증 중 소스 일치 확인. 기존 §10·§11 원문 보존 확인 |
| 전체 회귀·변이 | 개발자 최종 코드의 **4928 passed·2 skipped** 및 변이 22종 보고를 참고. 전체 회귀·변이 묶음·공식 연구 실행은 다시 하지 않음 |
| 실제 작업 | LaunchAgent 설치/해제·알림·06 운영 호출·자동 업로드·외장 장치 쓰기·라이브 데이터 접근·커밋·push 모두 없음 |

근거: `/private/tmp/poc613-r3-verify-_99qmsro/`의 `changed.json`, `diffs/`, `related.log`, `test_r1_reproductions.py`, `test_r2_reproductions.py`, `reproductions.log`, `uninstall-*.json`, `restore-link-*.json`, `checks.json`, `reused-scope.json`, `black.log`, `flake8.log`. 기존 정확한 재현은 증거 출력 경로만 이번 임시 폴더로 바꿨고, OS/장치 상태는 가짜 응답으로 재현했다. 프로세스 재현은 검증자가 시작한 임시 그룹만 정리했다.

검증자가 직접 수정한 곳(이 결과서 한 파일만):

| 위치 | 수정 전 → 수정 후 |
|---|---|
| 상단 STATUS·VERIFIER | r3 대기·r2 REJECTED → r3 VERIFIED(격리 구현 범위, §12). 과거 r1/r2 이력 유지 |
| §8 제목 | `검증 실측(2026-10-28)` → `검증 실측(2026-10-29 · 최신 정정 기준)`. 최신 시험 날짜에 맞춘 메타 정정 |
| §12 | 없음 → r3 대조 근거·판정 추가. §10·§11 원문 보존 |

코드·시험·다른 문서는 수정하지 않았다. 사용자 handoff 문서도 읽거나 stage하지 않았다.

### 7) 사용자에게 한마디

다음은 설계자 RESULT 판정이다. 그 뒤 사용자 승인으로 실제 A/B 설치·연결 확인과 커밋/push를 진행한다. C 목적지('PC 2TB'가 다른 컴퓨터인지 포함)는 실제 백업 전에 별도로 정하며, 미정이라는 이유로 이번 격리 구현 검증을 막지 않는다.

## 13. 설계자 RESULT 판정 원문 (2026-10-29 · V1.1 · `docs/ai_design/POC6/POC6-13_FORWARD_COMPARISON_DAILY_AUTOMATION_AND_RECOVERY_RESULT_DECISION_2026-10-29.md`)

작성: 설계자 · 2026-10-29 · 독자: 개발자·사용자·검증자

개정 V1.1: 사용자의 OCI·개발용 맥북·별도 PC 구분, 맥북 가동에 대한 조건부 의사, 백업 용량 설명을 반영했다. 격리 구현 PASS는 유지한다. 맥북 자동화는 당분간의 보조 운용으로 반영할 수 있고, OCI 가능성은 읽기 전용으로 병행 확인한다. 직전 구두 회신의 “OCI 검토를 먼저 끝낼 때까지 맥북 설치 보류”는 이번 정리로 대체한다.

저장 권장 위치: docs/ai_design/POC6/POC6-13_FORWARD_COMPARISON_DAILY_AUTOMATION_AND_RECOVERY_RESULT_DECISION_2026-10-29.md

**판정: PASS — 격리 구현·정정·검증 완료 범위. A·B는 맥북을 사용할 수 있는 날의 보조 자동화로 실제 반영할 수 있다.** 추가 공식 연구 실행·전체 회귀·검증자 재검증은 요구하지 않는다. 실제 설치·자동 업로드·C 사본 완료까지 확인됐다는 판정은 아니다. C의 목적 기기는 사용자 소유의 별도 PC로 확정하며, 전송/복원 연결 준비는 A·B 반영의 선행 조건으로 두지 않는다.

### 1. 근거와 확인 수준

첨부 POC6-13 결과서의 구현 판단·한계·승인 범위·시험·검증자 r1~r3 기록과, 함께 온 POC6-12 PLAN §7-3·§7-6을 검토했다. 설계자가 저장소 index·운영 맥북·OCI·외장 장치를 직접 실행/재검증한 것은 아니다.

| 근거 | 수용 내용 |
|---|---|
| 결과서 §12 | 검증자 r3 VERIFIED, 격리 구현 범위. 관련 시험 263건·r1/r2 독립 재현 10건 통과·변경 Python 13파일 정적 검사 통과 |
| 결과서 §8 | 개발자 최종 회귀 4,928 passed·2 skipped, 변이 22종 검출 보고. 검증자는 이 전체 묶음을 재실행하지 않음 |
| 결과서 §4 | F1~F4 정정과 같은 종류 보강, 실제 D/영수증을 읽는 완료 판정, A/B 별도 실행·작업당 원격 목록 1회 |
| 결과서 §5·§7 | 장치 가동·알림 전달·코드 보존·실제 사본의 한계, 설치/자동 업로드/외장 쓰기 미실행 |
| 사용자·개발자 보고 | staged 24개(신규 19·수정 5)·unstaged 0·사용자 handoff 제외. 이는 검증 시점 수치이며 판정 원문 추가 후 최종 파일 수와 구분 |

원본 내용 식별:
- POC6-13 결과서 첨부 SHA-256: 46a2819f9b3dd40aa52da9df6aecae04c24ac788a1f1b3ca1805f57bb583a38a
- POC6-12 PLAN 첨부 SHA-256: f1a93829b863661c8da44681a30ea39995b5d8ba4cb7f903d560441a4b98f465

### 2. 구현 판단·검증 경과 수용

- r1/r2는 기존에 정한 실패·프로세스 정리·다른 물리 사본 경계를 충족하지 못한 코드 결함이었다. r3의 정정 확인을 수용하며 원래 REJECTED 기록을 바꾸거나 지우지 않는다.
- 자식 출력을 임시 파일로 받고 자기 프로세스 그룹을 정리하는 변경, 경로/파일 링크와 장치 경계 확인, launchctl 응답을 등록/부재/확인 불가로 나누는 변경을 수용한다.
- run --pull과 archive --upload 분리, 예측 완료 뒤 보관만 다시 처리하는 흐름, 원격 목록의 호출 내 재사용과 실패 묶음 뒤 나머지 처리도 수용한다. 기존 06의 run --archive 동작을 이번에 추가 정정하지 않는다.
- 실제 주 기록과 마감 전 영수증 판정을 재사용하고, 필요한 D는 이번 06 기록이 있을 때만 확정하는 범위를 수용한다. 새 달력·가격 계산을 자동화 계층에 복제하지 않는다.
- 상태·기록/Git 조회 실패·알림 재시도·caffeinate 보강과 backup_source 분리는 기존 목적에 직접 연결된 변경이다. 범위 MINOR와 안전성 LOW의 공개 한계를 수용한다. 파일별 최초 목표 줄 수 초과를 KS-10 강제 상한 위반으로 바꾸지 않는다.

현재 가짜 자료 시험·격리 검증으로 확인한 내용과 실제 설치 뒤 확인할 내용을 구분한다. 실제 사고·실제 장치 손상·실제 발송 실패가 관측된 것처럼 기록하지 않는다.

### 3. 수용하는 한계와 표시 해석

1. 사용자 답변 “평일 사용 가능·장담 불가”와 출근 시 맥북을 휴대한다는 설명을 가동 여건으로 수용한다. **정확히 매일 10시에 켜거나 하루 종일 켜 둘 요구가 아니다.** 10:05는 OCI 수집 뒤의 기본 일정이며 추가 점검·로그인/놓친 일정 복귀가 있다. 10:00~15:20 KST 창에서 작업이 실제 시작되고 실제 공개 마감 전에 끝나면 된다. 작업 중에만 유휴 절전을 막으며 덮개 닫기·전원 종료까지 보장하지 않는다. 매일 기록을 위해 맥북을 반드시 휴대하겠다는 확약이나 실제 설치 승인으로 이 설명을 바꾸지 않는다.
2. 필요한 D를 확정할 06 기록이 없는 날의 AUTO_WINDOW_CLOSED와 “수동 실행은 실제 마감 전까지 가능” 문장은 조건부 설명으로 수용한다. **그 시각에 새 주 기록을 만들 수 있다는 권고·인증이 아니다.** 이미 마감이 지났다고 확인한 D를 채우기 위해 run을 부르지 않는다. 이 문구 때문에 새 OS/달력 조회나 수정·재검증 라운드를 만들지 않는다.
3. 같은 D의 주말 재확인·영수증·방법별 분모, 알림 요청과 실제 전달의 구분을 유지한다. 지난 평일 기록 0은 거래일 미확인이라는 문구를 포함하므로, 모든 휴장일에 예측이 누락됐다는 해석을 하지 않는다.
4. OS 캐시·나중의 장치 손상·검사와 읽기 사이의 동시 교체·이 환경의 launchctl 부재 코드 113은 결과서의 한계 그대로다. 바이트 사본 확인을 장치 영구 보장이나 옛 연구 완전 재현으로 확대하지 않는다.
5. C는 구현·가짜 장치 시험만 통과했다. 현재 08~11 산출물·봉인 DB의 두 번째 사본은 확보되지 않았다. 기존 과거 코드 보존 공백도 그대로다.

### 4. 사용자 승인 묶음과 반영 순서

이 판정은 실제 반영 준비를 통과시킨 것이며 **새 설치·업로드·커밋/push 승인을 대신하지 않는다.** 개발자는 아래 범위를 한 번에 구체적으로 제시하고 유효한 사용자 승인을 적용한다. 이미 승인된 동일 범위는 재승인받지 않는다.

승인 묶음:
- A·B: 자기 상태/로그 폴더·사용자 LaunchAgents 폴더·Label com.krx-hyungsoo.poc6-13.forward-auto의 plist 1개, 설치/등록 확인, 정해진 run --pull 및 기존 archive --upload의 자동 호출, 로컬 알림.
- 일정: 매일 10:05·12:05·14:35·15:25 KST와 로그인/일정 복귀. 10:00~15:20의 새 실행 창·자동 시도/간격·각 시간 상한은 구현대로 유지.
- **RunAtLoad는 설치 순간 tick 1회다.** 유효 창에 설치하면 실제 06 실행·업로드가 즉시 시작될 수 있다. 창 밖 설치는 상태 확인이며, 이미 마감이 지난 D를 진단 실행으로 억지 생성하지 않는다.
- 구현·판정 원문·상태 문서의 커밋/push, 실제 반영 후 종료 기록 커밋/push. 사용자 handoff와 로컬 연구 브랜치·실제 연구 산출물은 제외한다.
- C는 이번 A·B 활성화 승인에 실제 PC 쓰기로 끼워 넣지 않는다. 목적 기기는 별도 PC로 확정했지만 경로·전송·복원 절차 준비 전에는 대기다. A·B 정상 반영 뒤 C 실연결을 잔여로 분리해 종료할지 여부를 함께 명시적으로 확인할 수 있다.

승인 뒤 순서:
1. 검증 대상 코드가 유지됐는지 확인하고 구현을 커밋·push한다. 실행할 코드 판이 실제 커밋으로 남게 한다. 기존 로컬 연구 브랜치를 push/main 병합하지 않는다.
2. 같은 맥북의 기존 가상환경·저장소 경로로 install --apply를 수행한다. 현재 창 안/밖에서 어떤 일이 일어나는지 먼저 표시하고, 자기 Label의 등록·로그 경로·상태를 확인한다. macOS의 백그라운드 항목/알림 조작이 필요할 때만 사용자에게 안내한다.
3. 처음 유효한 실제 tick에서 입력 수신·실제 D·주 기록과 영수증·기존 월별 학습 조건을 확인한다. 이미 같은 D가 기록됐으면 기존 기록 반환으로 확인하며 새 주 기록을 강제로 만들지 않는다.
4. B는 기존 허용 자료 유형만 업로드하고, 미등록/미확인 수·원격 확인 결과를 보고한다. 예측 성공·보관 대기는 별도 상태로 유지한다. 첫 유효 tick에 이 보관 경로도 확인할 수 있다. 임의 옵션·새 OCI 형식은 추가하지 않는다.
5. 첫 정기 일정 동작을 한 번 확인하고 결과서에 기록한다. 첫 연결이 정기 일정 자체였다면 같은 확인으로 충족한다. 학습 월 변경·성숙 결과·여러 거래일을 기다리지 않는다.
6. 상태 문서·종료 기록을 실제 완료 범위에 맞춰 정리하고 승인 범위로 커밋·push한다. 문서 정리·정상 연결만을 이유로 전체 회귀나 검증자 판정을 다시 받지 않는다.

A·B는 OCI 서버 코드 pull·새 cron·키·학습 설치 없이 기존 보관 경로를 사용한다. 단지 원격 main이 앞섰다는 이유로 운영 OCI를 pull하지 않는다. 실제 연결에서 새로운 코드 결함이나 기존 범위 밖 변경이 필요하면 그 영향만 보고한다.

### 5. C 목적지 — 별도 PC의 비공개 폴더

사용자 설명으로 **맥북과 별도의 PC가 있다는 점은 확인된 것으로 정리한다.** 같은 질문을 반복하지 않는다. PC의 2TB는 저장장치 용량이며 백업 필요량이 아니다. 현재 대상의 초기 사본은 연구 자료 약 391MB + 봉인 DB 약 1.86GB + 코드 bundle을 합쳐 **약 2.4~2.5GB**다. 패키지 준비·되가져오기·빈 경로 복원에 필요한 임시 여유는 별도로 확인한다. 매일 2.4GB 전체를 다시 복사하는 계획도 아니다.

C의 방향은 **맥북 → 사용자 소유 별도 PC의 비공개 폴더**로 확정한다. 외장하드를 새로 사는 것을 조건으로 두지 않는다. 현재 검증된 도구는 맥북에 연결한 외장 장치만 지원하므로 CLI의 WAITING_TARGET은 실제 연결 전 상태로 유지된다. 문서에는 “목적 기기 PC 확정·경로/전송/복원 절차 준비 대기”라고 보충한다.

개발자는 기존 대상 목록·manifest·해시·코드 bundle을 재사용해 PC로 정상 전송하고, PC 사본을 맥북의 빈 경로로 되가져와 확인하는 **한 가지 작은 연결 방식만** 보완 계획으로 제시한다. 실제 PC의 사용 가능한 경로·공간·연결 수단을 확인하며 새 공개 클라우드·OCI 원자료 전송·범용 장치 지원으로 넓히지 않는다. 현재 외장 장치 검사를 속이거나 해제하지 않는다. 변경 코드는 그 연결 부분만 시험·변경분 검증하며 이미 통과한 A·B 전체 재검증을 조건으로 두지 않는다. 별도 PC의 GPU/학습 환경 설치는 이 백업 연결에 포함하지 않는다.

C가 미완료인 동안 “전체 연구 백업 완료”라고 기록하지 않는다. A·B 먼저 반영할 수 있고 다음 설계도 진행할 수 있다. 사용자가 C 실연결을 잔여로 분리해 종료하는 데 동의하면, 다음 상태를 나란히 기록한 뒤 13을 닫을 수 있다.
- A·B 실제 반영/확인 완료 범위.
- C의 기존 외장 방식 격리 구현 검증 완료·목적 기기는 별도 PC·실제 사본 미확보. PC 연결 보완과 대상/입력/코드 공백 유지.

그 분리 결정이 없으면 A·B 완료와 C 대기를 그대로 병기한다. 형식적 전체 종료를 위해 C를 완료·제외로 바꾸지 않는다. 이 잔여 때문에 추가 연구 재실행·전체 PLAN 재제출을 요구하지 않는다.

### 6. 함께 받은 POC6-12·전향 결측 회신

#### 6-1. API 가입 경로

PLAN §7-6의 사용자 확인을 수용한다. 기록은 **“사용자가 시도한 SEIBro 오픈플랫폼 가입 경로에서 사업자등록번호가 필요해 현재 개인 경로를 진행하지 못함”**이다. 화면/명세 직접 검증은 아직 없으므로 모든 예탁결제원 API가 개인에게 불가능하거나 ETF 분배금 API 자체가 없다고 일반화하지 않는다.

POC6-12의 원천 존재 확인과 필수 필드/이용 범위 미확인은 유지하고 HOLD_SOURCE_CONFIRMATION으로 둔다. 새 계정/계약·유료 구매·다른 출처 연속 조사를 이 판정으로 자동 개방하지 않는다. 정상 수동 조회에서 본 24행을 공식 확보·정규화 완료로 바꾸지 않는다. 13의 반영을 우선하며 이 보류를 전체 개발 대기로 만들지 않는다.

#### 6-2. D=2026-10-28 미기록

10-29 마감 전에 수동 실행이 없었고 18:31 확인 때 최신 예측 D가 10-27이었다는 보고를 수용한다. D=10-28은 미기록으로 남긴다. 앞선 D=10-23·10-26과 마찬가지로 소급·전향 주 기록 생성·가짜 성숙·누락 행의 학습 편입은 하지 않는다.

입력 묶음 20261029T004002Z_5b1a4c35는 OCI에 있다는 보고이므로 원자료 손실과 예측 미실행을 구분한다. 이것은 설치 전 수동 실행 의존에 따른 운영 공백이다. 검증자 r3의 코드 VERIFIED가 이 날짜의 실행 완료를 뜻하지 않는다.

**다음 기회는 2026-10-30의 정상 OCI 수집 뒤 D=10-29 기록이다.** 활성화됐으면 유효 창의 자동 실행 결과를 한 번 확인한다. 아직 설치되지 않았으면 기존 승인된 수동 run --pull을 유효 시간대에 한 번 수행한다. 실제 공개 확인은 10-30 15:30 KST 전이어야 한다. 자동으로 이미 기록됐다면 새 예측을 강제로 다시 만들지 않는다.

### 7. 문서·종료 기록

결과서 §13에 본 V1.1 판정 원문과 수용 범위·실제 반영 조건을 추가한다. §10~§12 검증자 이력과 공개 한계는 보존한다. PLAN·STATE·PROGRAM_TRUTH는 “설계자 RESULT PASS·맥북 보조 A/B 활성화 승인/확인 대기·C 목적 기기 PC 확정/연결 준비 대기”로 현재 상태를 맞춘다. 실제 연결 뒤에만 해당 완료 상태로 바꾼다.

같이 stage된 12 문서는 조사·보류 기록으로 구분한다. 이를 함께 커밋하더라도 12 구현/자료 확보 완료를 뜻하지 않는다. 파일 수는 판정 원문·종료 기록 추가 후 최종 한 번 맞추되, 검증 당시 staged 24개라는 과거 사실은 고치지 않는다.

기존 05 수집·06 예제/recipe·공개/성숙 계약·운영 ML 미승격·Q6 OPEN·미완료 요구는 유지한다. 별도 handoff 문서는 만들지 않는다. 정상 반영과 C 잔여 결정이 위 조건 안에서 끝나면 추가 RESULT 판정 없이 사실을 짧게 보고한다.

### 8. 사용자 환경에 따른 운용 방향 보완

#### 8-1. 저빈도 투자와 일별 연구 기록

사람의 투자 검토 주기는 주 1회·보유는 수주~수개월이라는 기존 결정을 유지한다. 일별 전향 기록은 그날 받은 자료로 예측을 먼저 남겨 나중에 같은 행에서 비교하기 위한 **현재 06 연구의 기록 주기**다. 매일 매매하거나 ML 일반의 필수 요건으로 매일 맥북을 켜야 한다는 뜻이 아니다. 기록을 놓친 날은 예측 없음으로 남고 OCI의 원자료 보관은 계속된다.

최근 06 실행은 받은 입력 상태에 따라 수 초~밀린 수신을 포함한 수 분으로 보고됐으며, 매번 새로 학습하지 않는다. 이 실측은 미래 소요 시간 보장이 아니다. 맥북을 쓰는 날에는 이미 만든 13 자동화를 활용해 수동 명령을 기억해야 하는 부담을 줄인다. 맥북이 없는 날까지 기록이 필요하면 상시 실행 장치에 추론을 분리하는 쪽으로 해결한다. 사용자의 생활에 매일 정확한 시각의 가동 의무를 추가하는 것으로 대신하지 않는다.

#### 8-2. 장치 역할의 방향과 현재 사실

| 장치 | 앞으로의 역할 방향 | 현재 확정된 범위 |
|---|---|---|
| OCI | 상시 수집·보관, 가능성이 확인되면 일별 추론·연구 기록 | 지금은 수집·보관만. 추론 자원·호환성 미확인 |
| 맥북 | 개발·검증·화면 사용, 당분간 기존 06의 보조 실행 | 13 맥북 자동화 격리 검증 완료·실제 활성화 전 |
| 별도 PC | 학습/재학습·무거운 연구, 필요할 때 GPU 사용, 연구 자산 백업 | GPU 사용 경험과 별도 저장장치 존재. 이번 PC 백업 연결·06 학습 이관은 아직 미실행 |

학습과 저장된 모델의 추론은 역할을 분리할 수 있다. 기존의 “OCI 학습 금지”는 현재 운영 계약이며, 추론도 기술적으로 불가능하다는 측정 결과가 아니다. 반대로 무료 서버라는 이유만으로 무리라고 정하거나, 작은 모델 파일이라는 이유만으로 여유 메모리가 충분하다고 정하지 않는다.

현재 OCI는 보고상 약 1GB 메모리다. 기존 배치·PUSH·수집의 여유를 우선 유지한다. **OCI가 된다고도, 안 된다고도 아직 확정하지 않는다.** scikit-learn 공식 모델 보관 문서도 학습/서빙 분리를 설명하지만 저장 형식별 런타임·버전·지원 모델 조건이 다르다.[1]

당장 기존 run을 OCI cron에 그대로 넣지 않는다. 06의 현재 명령에는 조건부 학습·성숙·기록까지 묶여 있다. 지금의 고정 모델·CPU recipe를 임의로 GPU로 바꾸거나 두 방법만 남겨 네 방법 비교라고 부르지 않는다. PC 학습·OCI 추론을 실제 분리하는 변경은 월별 갱신 지연 시 동작, 모델 판·실제 가용 시각, 기존 출력과의 대조 범위를 다음 실행 설계에서 정한다.

#### 8-3. 지금 병행할 수 있는 확인의 상한

13의 맥북 A·B 실반영 준비를 기다리게 하지 않고, 개발자는 **추가 합계 30분 이내의 읽기 전용 사실 확인**을 할 수 있다. 결과는 같은 13 결과서 부록에 붙이며 이 조사만을 위한 새 POC·PLAN·검증자 라운드는 만들지 않는다.

1. 기존 06 네 방법의 저장 형식·변환값·필수 패키지·환경, 학습과 추론의 실제 분리 접점. 이미 조사한 파일·함수·보고를 재사용한다.
2. OCI CPU 아키텍처·Python/설치 패키지·실제 가용 메모리·디스크, 기존 작업의 알려진 자원 사용. 현재의 한 번 측정한 여유를 피크 시간의 보장값으로 쓰지 않는다.
3. 현재 방식 그대로의 추론 환경이 필요한지, 작은 분리가 필요한지, 제안할 실행 경로 **한 가지**와 검증에 필요한 범위. 새 추론 플랫폼 비교·변환기 구현·모델 탐색은 하지 않는다.
4. 그 경로가 기존 06의 모델 판·feature 계산·공개 마감·월별 갱신 계약에 미치는 차이. 자료 파일 크기만으로 RSS를 보증하지 않는다.

이번에 OCI 패키지 설치·모델 load/predict·추론 프로세스 실행·새 cron·파일 쓰기·운영 역할 변경은 하지 않는다. 실제 메모리/시간 시험이나 OCI 추론 배포가 필요하면, 준비된 작은 시험/변경 범위로 승인받아 실행한다. 이 사실 확인 결과가 나올 때까지 기존 연구 자산·맥북 자동화·PC 백업 준비를 멈추지 않는다.

**개발자에게 지금 전달할 결정:** 격리 구현 PASS는 유지한다. 맥북 자동화의 실제 활성화는 기존 §4의 구체적인 승인 범위로 진행할 수 있다. 사용자 설명을 설치 거부·매일 가동 확약·즉시 설치 승인 어느 것으로도 바꾸지 않는다. C는 별도 PC 연결 보완만 준비하고, OCI는 위 읽기 전용 확인만 병행한다. POC6-12 API 보류와 실제 운영 ML 미승격은 그대로다.

[1] [scikit-learn 모델 보관·서빙 환경 설명](https://scikit-learn.org/stable/model_persistence.html). 특정 추론 형식의 채택이나 기존 모델 변환 성공을 확인한 근거는 아니다.

## 14. 실제 반영 기록(RESULT 판정 V1.1 §4 · 개발자)

### 14-1. 사용자 승인(2026-10-29 · 20:5x KST)

§4 승인 묶음을 한 번에 제시했고, 사용자가 ① 커밋 · push → ② 맥북 설치 → ③ 첫 실행 확인 뒤 종료 기록 커밋 · push 를 모두 승인했다. C(별도 PC 백업) 쓰기는 이 승인에 넣지 않았다.

### 14-2. ① 커밋 · push

- 코드 유지 확인: 코드 · 시험 파일의 마지막 수정 = 19:12:16 KST(`backup.py` · `status.py`) < 최종 전체 회귀 시작 19:14:13(§8-2). 그 뒤 바뀐 것은 문서뿐이다.
- 구현 커밋 `e0a94175`(25파일 · 사용자 handoff · 상태 폴더 · 연구 산출물 제외) → `git push origin main`(`da643ed5..e0a94175`) · 원격과 차이 0 · 로컬 연구 브랜치 `research/poc6-10-local` 은 원격에 없음.

### 14-3. ② 설치(같은 맥북 · 저장소 `.venv` 파이썬)

| 시각(KST) | 확인 | 결과 |
|---|---|---|
| 20:53:43 | `install`(dry-run) | DRY_RUN · plist = 자기 Label 1개 · 절대 경로 파이썬 · 스크립트 · 일정 10:05 · 12:05 · 14:35 · 15:25 · RunAtLoad · KeepAlive 없음 · 쓰기 0 |
| 20:53 | launchd 와 같은 빈 환경(`env -i` · PATH 4개)에서 `ssh -o BatchMode=yes oci-krx true` | 종료 코드 0(비대화형 접속 가능) |
| 20:54:10 | `install --apply` | OK · bootstrap 종료 코드 0 · 등록 확인 = 올라 있음 · 로그 폴더 있음 · plist 내용 같음 |
| 20:54 | 설치 순간 tick(RunAtLoad) | launchd `runs = 1` · `last exit code = 0` · RESULT `actions: []`(06 호출 · 업로드 0 · 창 밖) · 예측 AUTO_WINDOW_CLOSED · 알림 1건 요청(REQUESTED_DELIVERY_UNKNOWN · 'D 확인 불가 AUTO_WINDOW_CLOSED') |
| 20:54 | `status` | 일정 설치됨 · 활성 · 다음 10-30 10:05 · 보관 NOT_TRIED · 미등록 4 · 미확인 묶음 1 · 백업 WAITING_TARGET |

- 만든 것: `~/Library/LaunchAgents/com.krx-hyungsoo.poc6-13.forward-auto.plist` · `state/ml/operations/poc6_13/`(`launchd.log` · `latest.json` · `latest.txt` · `notified.json` · `.auto.lock` · git 제외). 그 밖의 폴더 · 작업 · crontab · 전원 설정 변경 0.
- 해제: `python scripts/run_forward_auto.py uninstall --apply`('서비스 없음' 확인 뒤에만 plist 삭제).

### 14-4. ③ 첫 정기 실행 확인 — 대기

2026-10-30 10:05 KST 일정(맥북이 깨어 있을 때)에서 D = 10-29 의 입력 수신 · 주 기록 · 마감 전 영수증 · 월별 학습 조건 · B 보관 결과를 확인해 이 절에 적는다.

## 부록 A. OCI 일별 추론 가능성 — 읽기 전용 사실 확인(RESULT 판정 V1.1 §8-3 · 2026-10-29 20:56 ~ 20:59 KST · 약 3분)

OCI 쓰기 · 패키지 설치 · 모델 load/predict · 프로세스 실행 · cron · 운영 역할 변경 0. 맥북 측정은 읽기만(로컬 · 쓰기 0). **가능 · 불가능을 판정하지 않는다.**

### A-1. 06 네 방법의 학습 · 추론 접점(코드 읽기 · `app/forward_compare/models.py`)

| 방법 | 저장 형식 | 추론에 필요한 것 | 판 검사 |
|---|---|---|---|
| MEDIAN | `median.json` | 순수 파이썬 | 없음 |
| RIDGE | `ridge.json`(mean · scale · coef · intercept) | 순수 파이썬 식(`ridge_raw`) | 없음 |
| HGB | `hgb.joblib`(scikit-learn HistGradientBoosting) | scikit-learn · scipy · joblib · numpy | 학습 때 판과 다르면 ENV_MISMATCH(읽지 않음) |
| MLP_CPU | `mlp_state.pt` + `mlp_norm.json`(5 → 64 → 32 → 1) | torch | 같음(torch 판) |

- 모델 판 1개 = 6파일 140KB(`training.json` 포함 · 현재 `mv_e926e0661c261324`). 학습 환경 = 맥북 arm64 · Python 3.12.13 · scikit-learn 1.9.0 · numpy 2.4.6 · scipy 1.18.0 · joblib 1.5.3 · torch 2.13.0.
- 분리 접점: 학습 `models.train`(메모리 모델 + 저장 bytes) ↔ 추론 `models.Loaded`(해시 · 판 확인 뒤 방법별 로드) · `Loaded.predict`. 지금 06 `run` 은 입력 수신 → 성숙 → 학습 결정(월 최대 1회) → 예측 기록 → 공개 확인 영수증을 한 명령으로 묶는다.
- 특징값 계산 경로(`inputs.py` · `reentry_review.model`)의 외부 패키지 의존은 전수 확인하지 않았다(학습 함수 안의 numpy · scikit-learn import 만 확인).

### A-2. OCI 실측(읽기 전용 SSH 4회 · 20:56 ~ 20:57 KST · 한 번 측정 · 낮 피크 아님)

- CPU x86_64 · AMD EPYC 7551 · 2 vCPU / 메모리 954MB · 그 시각 사용 가능 538MB · **스왑 없음** / 디스크 45G 중 여유 39G / Ubuntu 24.04.4 · load 0.04.
- 운영 가상환경 `/home/ubuntu/krx_hyungsoo/venv`(402MB) = Python 3.12.3 · numpy 2.4.6 · pandas 2.3.3 · **scikit-learn · scipy · joblib · torch 없음**. 시스템 python3 에도 없음.
- cron: 평일 08:10 · 09:20 시장 배치 · 08:30 · 09:15 · 09:30 · 10:30 · 11:30 · 12:30(2줄) · 13:30 · 14:30 · 15:20 · 15:40 PUSH runtime · 매일 09:40 증거 수집.
- OCI `state/ml/evidence` = 42MB(06 입력 묶음 있음) · `state/ml/research` 없음(06 연구 폴더는 PC 에만).

### A-3. 맥북 참고 측정(arm64 macOS · OCI 보증값 아님)

- 06 모델 판 4방법 로드 + 가짜 입력 24행 예측 = 최대 RSS 325,140,480 바이트(약 310MiB) · 2.7초 · 96/96 OK.
- import 만: numpy 27MiB · `sklearn.ensemble` + joblib 150MiB · torch 199MiB.
- 특징 계산 · 입력 읽기 · 기록 쓰기 메모리는 넣지 않았다. macOS arm64 와 Linux x86_64 의 RSS 는 다르다.

### A-4. 제안 경로 한 가지와 검증 범위

- **경로**: 학습은 PC(맥북 또는 별도 PC)에서 지금 recipe 그대로 → 모델 판 묶음(06 archive 로 이미 OCI 보관되는 형식) → OCI 의 **추론 전용 명령**이 그 판으로 네 방법 예측 · 기록만 한다. OCI 운영 가상환경과 분리된 별도 가상환경에 학습 판과 같은 판의 scikit-learn · scipy · joblib · threadpoolctl · torch(CPU)를 둔다. 실행 시각은 09:40 수집 뒤 PUSH runtime 과 겹치지 않는 칸이다. 성숙 · 보고 · 학습 예제 편입은 PC 에 남긴다.
- **먼저 필요한 작은 시험(승인 뒤)**: ① 별도 가상환경 설치 크기 ② 4방법 로드 + 24행 예측의 최대 RSS · 시간(낮 운영 작업이 도는 시간대 여유 포함) ③ 같은 D 의 맥북 기록과 예측값 대조(MEDIAN · RIDGE 는 같은 식 · HGB · MLP 는 arm64 → x86_64 차이의 허용 범위를 미리 정함) ④ arm64 맥북에서 만든 joblib · torch 파일을 x86_64 에서 읽을 수 있는지.
- 메모리: 그 시각 사용 가능 538MB(한 번 측정)와 맥북 참고 310MiB(추론만)의 차이로는 여유를 단정할 수 없다. 스왑이 없어 초과하면 같은 서버의 PUSH 에 영향이 갈 수 있다.

### A-5. 이 경로가 지금 06 계약과 달라지는 곳

1. **모델 판 · 월별 갱신**: 재학습이 OCI 실행과 분리된다. PC 학습이 늦으면 OCI 는 이전 판으로 계속 예측한다(지금 = '조건을 처음 만족하는 유효 예측 실행에서 재학습'). 늦어질 때의 동작을 정해야 한다.
2. **환경 판 검사**: 학습(arm64 맥북)과 추론(x86_64 OCI) 환경이 다르다. 지금의 ENV_MISMATCH 는 라이브러리 판만 본다.
3. **공개 마감 · 영수증**: 지금은 PC 가 만든 기록을 OCI 에 올려 마감 전 공개를 확인한다. OCI 에서 만들면 '공개' = OCI 쓰기 시각이 되어 영수증의 뜻이 바뀐다.
4. **기록 흐름**: 기록이 OCI 에서 생겨 PC 로 내려오는 반대 흐름이 된다(OCI 에는 06 연구 폴더가 없음).
5. **특징 계산**: 입력은 OCI 에 이미 있으나 특징 계산 코드의 OCI 실행 의존은 미확인이다(A-1 마지막 줄).
6. **운영 격리**: 운영 가상환경 · cron · PUSH 와 분리해야 한다(A-4 메모리 줄).

## 15. C 보완 — 별도 PC 윈도우 공유 폴더(SMB) 구현(보완 판정 2026-10-29 · 변경분 · 검증자 REJECTED §16 → C-F1 정정 §15-6 → r2 VERIFIED §17)

판정: `docs/ai_design/POC6/POC6-13_PC_SMB_BACKUP_SUPPLEMENT_DECISION_2026-10-29.md`(PASS_WITH_REQUIRED_CORRECTIONS) · 반영 = PLAN §8-6. 실제 PC 공유 설정 · 연결 · 백업 쓰기 = 0(승인 전).

### 15-1. 바뀐 것

| 파일 | 변경 |
|---|---|
| `app/forward_auto/backup_source.py` | `parse_share` · `smb_source` · `mount_table` · `resolve_host` · `own_addresses` · `share_check` · `target_check`(외장 / 공유 분기) · `plan(pc_share=)` |
| `app/forward_auto/backup.py` | `run` · `verify(pc_share=)` → `target_check` · 승인값 오류 = REFUSED · verify 거부 문구 'PC 공유 아님' · `_fsync_full` 대체 조건을 '지원 안 함' 4종으로 좁힘 · 쓴 방식 기록(`sync`) · 복원 기록에 목적지 정보 · C-F1 정정(§15-6: `_undo_rename` · `_copy_refusal`) |
| `scripts/run_forward_auto.py` | `backup plan/run/verify --pc-share //서버/공유` 인자 · 전달 |
| `tests/test_poc6_13_backup.py` | 시험 +35(46 → 81 · C-F1 정정 시험 5 포함) · 복사 기록을 None 으로 우회하던 기존 시험 3개를 '기록까지 함께 변조'로 바꿈(§15-6) |

- 06 · A(tick) · B 경로 코드 변경 0: `git diff e0a94175 -- app/forward_auto/{runner,status,schedule,view,launchd}.py app/forward_compare app/ml_evidence scripts/run_forward_compare.py` = 0줄. CLI 변경은 backup 하위 명령의 인자 · 전달뿐이다. 설치된 LaunchAgent 는 작업 폴더 코드를 쓰므로 10-30 첫 tick 은 이 변경이 들어간 작업 트리에서 돈다(tick 경로 같음).

### 15-2. 판정 §4 경계별 시험

| 경계 | 시험 |
|---|---|
| 목적지 | 승인 서버 · 공유 통과 · 별칭(같은 주소) 통과 / 다른 공유 · 다른 서버 · 별칭 주소 확인 불가 · 서버 주소 확인 불가 · localhost · 맥북 자신 · 공인 주소 · 마운트 표 확인 불가 · 자기 주소 확인 불가 · 공유 해제(로컬 폴더만) · AFP 공유 · 저장소와 같은 볼륨 · 공유 밖 폴더 · 표로는 공유 안이지만 장치가 다른 자리 거부 / 승인값의 사용자 · 포트 · IPv6 · 형식 오류 거부 / 마운트 원문의 사용자 부분 미기록 |
| 분리 | 플래그 없음 = 외장 검사만(공유 검사 호출 0) · 공유 경로 = 외장 검사 호출 0 · 실제 외장 검사는 공유 폴더를 통과시키지 않음 |
| 실패 | F_FULLFSYNC '지원 안 함'(ENOTSUP · EINVAL) = fsync 로 대신 · 방식 기록 / 입출력 · 연결 끊김 오류 = 실패 / 대신한 fsync 실패 = 실패 / 폴더 동기화 입출력 오류(이름 바꾸기 전 · 뒤 모두) · 쓰는 중 연결 끊김 = COPY_INCOMPLETE · 최종 이름 폴더 없음(.partial 로 남거나 되돌림) / 되돌리기마저 실패해 최종 이름 폴더가 남아도 verify = REFUSED |
| 복원 | 공유 사본 → 빈 칸 복원 RESTORE_VERIFIED / 사본 손상 = RESTORE_FAILED(사본은 지우지 않음) / 공유 해제 뒤 verify = REFUSED · run = WAITING_TARGET(새로 쓰지 않음) / 그 id 의 마지막 복사 기록이 COPY_HASH_OK 가 아니면(기록 없음 · 뒤에 미완료) verify = REFUSED |

- 가짜 마운트 표 · 주소 확인 · 장치 번호로 tmp 폴더를 smbfs 처럼 보이게 한 시험이다. **실제 SMB 호환성 확인이 아니다**(판정 §4).
- 맥북 실제 읽기(쓰기 0 · 2026-10-29): `mount_table` = 11줄(apfs · autofs · devfs) 해석 · `own_addresses` = 12개(127.0.0.1 · ::1 포함) · 일반 폴더(`/tmp`)는 'SMB 공유 아님(apfs)'으로 거부.

### 15-3. 실측

- `black --check` 13 unchanged · `flake8` 0 · `py_compile` 통과.
- 줄 수: `backup_source.py` 431 · `backup.py` **625** · `run_forward_auto.py` 121 · `test_poc6_13_backup.py` 1,148. KS-10 상한(백엔드 650 · 시험 1,500) 안이지만 `backup.py` 는 **사전 경고선(백엔드 600) 위**다. 다음에 이 파일에 책임을 더하면 먼저 나눈다.
- 백업 시험 81 · 관련 05 · 06 · 13 시험 6파일 298 passed(100.3초 · 최종 코드).
- 변이 14종(smbfs · 공유 이름 · 별칭 주소 · localhost / 자신 · 로컬 대역 · 마운트 위 · 같은 볼륨 · 승인값 인증 정보 · 사용자 부분 기록 · 분기 2 · 대체 조건 · 마운트 표 확인 불가 · 자기 주소 확인 불가)을 하나씩 되돌림 → 모두 새 시험이 잡음(C-F1 정정 뒤 최종 코드로 다시 실행 · 2026-10-29). C-F1 정정 변이 5종은 §15-6.
- 전체 회귀는 판정 §4 대로 하지 않았다(06 · A · B 경로 변경 0).

### 15-6. 검증자 C-F1 정정(2026-10-29 · §16)

같은 종류 = '사본 폴더가 있다는 사실만으로 완료로 취급'. 두 층에서 막았다.

| 층 | 정정 | 시험 |
|---|---|---|
| run(복사) | 이름 바꾼 뒤 실패(부모 폴더 동기화 오류 등)하면 `_undo_rename` 이 최종 이름을 `.partial` 로 되돌린다. 되돌리기도 실패하면 그 사실을 결과 · 기록의 `after_rename` 에 남긴다(최종 이름 폴더가 남아도 COPY_HASH_OK 기록이 없음) | 이름 바꾸기 전 · 뒤 동기화 입출력 오류(매개변수 2) → COPY_INCOMPLETE · 최종 이름 없음 · `.partial` 있음 · 마지막 상태 COPY_INCOMPLETE · 되돌리기 실패 → 최종 이름 남음 · 사유 기록 |
| verify(복원 확인) | `_copy_refusal`: 잠금 안에서 그 id 의 마지막 복사 단계 기록(순번)이 COPY_HASH_OK 일 때만 시작 — 기록 없음 · 마지막이 COPY_INCOMPLETE 면 REFUSED. 확인 뒤 기록이 사라져 `_recorded_manifest` 가 None 이면 대조 생략 대신 RESTORE_FAILED | 최종 이름만 남은 사본 → REFUSED · COPY_HASH_OK 기록 쓰기 실패(run 예외) → REFUSED · 성공 뒤 미완료 기록 → REFUSED · 기록 삭제 → REFUSED · 확인 뒤 기록 사라짐 → RESTORE_FAILED |

- 바뀐 동작: 복사 성공 기록이 없는 사본은 복원 확인을 하지 않는다. 다른 맥에서 이 기록 없이 복원 확인하는 경로는 범위 밖이다(지금 설계 = 같은 맥북의 복원 확인).
- 기존 시험 3개(`test_verify_refuses_partial_and_unsafe_tar_member` · `test_verify_reads_only_the_fixed_artifacts` · `test_verify_requires_the_fixed_commits`)는 복사 기록을 지우거나 None 으로 우회해 뒤쪽 검사(허용 밖 tar 항목 · 정해진 묶음 5개 · 커밋 목록)를 보던 시험이다. 이제 그 우회는 앞에서 REFUSED 되므로 '기록까지 변조 manifest 와 같은 해시'로 바꿔 뒤쪽 검사를 계속 시험한다.
- run 이 COPY_HASH_OK 기록을 쓰다 실패하면 run 은 예외로 끝난다(CLI = FAILED · 종료 코드 1). 그 사본은 verify 가 받지 않는다.
- 변이 5종(되돌리기 제거 · verify 기록 확인 제거 · 기록 None 일 때 대조 생략 · '마지막' 대신 '하나라도' · 기록 없음 통과) 모두 잡힘. 검증자 독립 재현 4개(`test_independent_smb.py` 사본 · 출력 경로만 개발자 임시 폴더) = 4 passed(이전 실패 1 포함).

### 15-4. 한계(판정 §3 · PLAN §8-3)

- 공유 경로의 RESTORE_VERIFIED = 지정한 PC 공유의 사본에서 되가져와 빈 맥북 경로의 복원 내용이 목록 · 해시 · 필요 커밋과 일치했고 서버가 성공을 응답했다는 뜻이다. 전원 상실 뒤 보존 · 매체 영구 무결성 · 실험 재실행 가능성은 보장하지 않는다.
- 연결은 PC 의 IP 주소로 한다. Bonjour 서비스 이름(`…._smb._tcp.local`)은 주소 확인이 안 되면 거부한다. IPv6 주소 · 포트 지정은 지원하지 않는다.
- 첫 실제 확인 = 복사 → Finder 해제 · 재연결 → `verify --pc-share`. 두 기록의 `mount_dev` 는 관측값이다(같은 번호가 다시 배정될 수 있고, 캐시 제거 증명이 아님).
- 백업할 때 맥북과 PC 가 같은 공유기에 있어야 한다. 복원 확인은 맥북에 약 2.8GB 임시 공간(사본 2.4GB + 풀린 연구 파일)을 쓰고 끝나면 지운다(맥북 여유 약 379GB · 2026-10-29).

### 15-5. 다음

검증자 변경분 재확인(C-F1 · 판정 §4 경계) → 사용자 승인 묶음(판정 §5-3: PC · 폴더 · 계정 / 연결 범위 · 예상 용량 2.4GB · 복원 임시 경로 `state/ml/operations/poc6_13/restore/<id>`) → 구현 커밋 · 첫 실제 복사 · 재연결 · 복원 확인 → 이 절에 시각 · 바이트 · 파일 수 · 동기화 방식 · 결과 기록.

## 16. 검증자 C 보완 변경분 판정 — 2026-10-29 · Codex

### 1) A. 기능/산출물 검증

- **A-1 지시 일치: 일부 위반(C-F1).** 보완 판정 §2의 승인 서버/공유·실제 smbfs·자기 주소 거절·외장 경로 분리, §3의 미지원만 fsync 대체·방식 기록, §4의 정상 복원/손상 거절 경로는 코드 및 관련 시험과 일치한다. 그러나 이름 변경 직후 동기화 실패 경로는 §3·§4의 미완료 보존 및 실패를 완료로 올리지 않는 계약을 충족하지 못한다.
- **A-2 보고 정확성: 일부 위반(C-F1).** 검증 시작 시 staged 9개(A 1·M 8), unstaged 0, 사용자 handoff untracked 1개다. 변경 코드/시험 4개와 문서 5개가 제출 목록과 같고, §15-3의 줄 수·관련 시험 293건도 실측과 일치한다. 다만 §15-2의 동기화 실패→미완료(최종 폴더 없음) 보장은 이름 변경 뒤 오류에는 성립하지 않는다. PLAN §8의 지난 '판정 대기' 및 PROGRAM_TRUTH의 지난 최종 반영 날짜는 검증자가 직접 정정했다. 이 메타 정정은 반려 사유가 아니다.
- **A-3 산출물 정합성: 위반(C-F1).** 동기화 오류로 COPY_INCOMPLETE를 기록한 같은 id가 추가 동기화 성공 확인 없이 RESTORE_VERIFIED로 올라가며 최신 상태의 복사 실패가 가려진다. 아래 독립 재현은 정상/오류 위치 대조를 포함한다.
- **A-4 금지사항 위반: 없음.** 신규 의존성·외부 API·DB 스키마·삭제·실제 PC 공유 설정·SMB 연결/쓰기·OCI 작업은 없다. 기존 A/B 실제 설치 기록은 과거 사실로 보존했고 이번에는 해당 OS 상태나 라이브 자료를 읽지 않았다.

**C-F1 [P2] — 이름 변경 뒤 동기화 실패한 사본이 완료 폴더로 남아 verify에서 완료로 승격됨**

- 위치: `app/forward_auto/backup.py:250~266`의 이름 변경/부모 폴더 동기화 예외 처리, `474~494`의 복원 대상/복사 기록 확인, `504`의 완료 판정.
- `.partial`을 최종 이름으로 바꾼 뒤 `_fsync_dir(final.parent)`를 수행한다. 여기서 I/O 오류가 나면 COPY_INCOMPLETE로 보고하지만 폴더는 이미 최종 이름이고 `.partial`은 없다. 이후 verify는 이 폴더를 완료 대상으로 받는다. COPY_HASH_OK 기록이 없다는 사실도 '비교할 manifest 기록 없음'으로 받아 바이트 복원만 수행하고 RESTORE_VERIFIED를 남긴다.
- 독립 재현은 임시 저장소·임시 공유 경로·가짜 smbfs/주소 응답을 사용했다. 이름 변경 뒤 부모 디렉터리 동기화에만 EIO를 발생시켰다. 결과는 다음과 같다.
  - run = **COPY_INCOMPLETE**, 최종 폴더 있음, `.partial` 없음.
  - COPY_HASH_OK 기록 없음. verify = **RESTORE_VERIFIED**, `manifest_recorded=false`.
  - 기록 순서 = COPY_INCOMPLETE → COPY_INCOMPLETE → RESTORE_VERIFIED. 마지막 상태도 RESTORE_VERIFIED가 된다.
- 같은 자료의 정상 대조군은 COPY_HASH_OK → RESTORE_VERIFIED로 통과했다. 이름 변경 **전** 폴더 동기화에 동일한 EIO를 넣으면 `.partial`만 남고 verify는 REFUSED로 통과했다. 승인 서버 별칭/다른 주소 및 인증 원문 미기록 대조도 통과했다.
- 이는 매체의 영구 내구성을 추가로 요구하는 판정이 아니다. 명확하게 발생한 동기화 오류를 미완료로 유지하는 기존 판정 §3과, 실패가 COPY_HASH_OK/RESTORE_VERIFIED로 올라가지 않는 §4 경계의 문제다. 실제 PC의 SMB에서 오류가 발생했다거나 자료가 손실됐다는 보고도 아니다. 모든 기록을 함께 위조하는 시험은 하지 않았다.

### 2) B. 구현 규칙/구조 품질 검증

- **B-1 암묵 fallback 위반: 있음(C-F1).** 이 id의 복사 미완료 기록과 복사 성공 기록 부재를 구분하지 않고, 성공 manifest 기록이 없다는 이유로 비교를 생략한 채 완료 대상처럼 진행한다.
- **B-2 단일 책임 위반: 없음.** 목적지 분류·SMB 관측은 source, 복사/복원·동기화는 backup, 인자 전달은 CLI에 있다.
- **B-3 파일 책임 과다: 없음.** 변경 코드 581·431·121줄, 시험 1,036줄로 KS-10 상한 안이다.
- **B-4 실험/운영 경계 위반: 없음.** 06·tick·보관 경로의 HEAD 대비 diff 0을 확인했다. 이번 판정은 C 변경분이며 기존 A/B r3 통과 판정이나 설치 사실을 재판정하지 않는다.
- **B-5 배포/실행 경로 영향: 누락 없음.** CLI와 모듈·문서 모두 index에 추적돼 있고 파일 이동이 없다. Dockerfile/OCI 배포/cron 변경도 없다. 실제 PC 연결·첫 사본·Finder 해제/재연결·복원은 승인 후 단계다.
- **B-6 기술부채/구조적 퇴행: 위 실패 상태 공백 외 없음.** 새 전송 프로그램·윈도우 서비스·별도 인증 체계·범용 백업 계층을 추가하지 않는다. mount 정보는 서버/공유·주소·장치 번호를 관측한 것으로 기록하며 PC 물리 디스크를 인증했다고 쓰지 않는다.

### 3) 기반 문서 준수

신규 Markdown은 제출된 설계자 보완 판정 원문 1개이며 신고돼 있다. MongoDB·새 UI/의존성·운영 계산 복제는 없다. 봉인 DB의 OCI 미전송, 사용자 handoff 제외, 로컬 연구 브랜치 비공개 경계를 유지한다. C 실제 쓰기 승인은 이 판정으로 대체되지 않는다.

### 4) 코드 안전성

**위험 수준: MEDIUM.** 알려진 동기화 오류가 발생한 사본을 이후 상태에서 완료로 보이게 할 수 있다. 실제 SMB 호환성/캐시/전원 상실 뒤 내구성은 시험하지 않았고, 해당 공개 한계를 코드 결함과 구분했다. 이번 독립 시험은 가짜 마운트·주소와 작은 임시 자료만 사용했다.

### 5) 범위 폭주

**폭주 수준: MINOR.** 미지원 대체 조건의 강화가 기존 외장 경로에도 적용되고 복원 기록에 목적지 관측값이 추가됐으나, 모두 공개돼 있고 보완 판정과 직접 연결된다. A/B·공식 연구·운영 모델·외부 전송 범위는 늘지 않았다.

### 6) 종합 판정

**종합 판정: REJECTED — C SMB 보완 변경분(C-F1).** 기존 A/B r3 VERIFIED 판정은 유지한다. 문서 수치나 메타 불일치가 반려 사유가 아니다.

| 검증 | 실측 결과 |
|---|---|
| 관련 05·06·13 시험 | **293 passed**, 98.49초. 백업 시험 76건 포함 |
| 독립 변경분 대조 | **1 failed·3 passed**, 4.09초. 실패 = 이름 변경 뒤 동기화 오류. 대조군 = 정상·이름 변경 전 오류·서버 주소/인증 원문 미기록 |
| 정적 검사 | 이번 변경 Python 4파일 black --check·flake8·py_compile 모두 통과. 나머지 기존 코드의 이전 검증 근거는 유지 |
| 줄 수 | `backup.py` 581, `backup_source.py` 431, CLI 121, 백업 시험 1,036. 제출값과 일치 |
| 범위 | HEAD `e0a94175f563cfc2d77c050866cf931a65801ab7`, staged 9개·unstaged 0. A/B·06·보관 경로 diff 0 및 검증 중 소스 일치 확인 |
| 생략 | 판정 §4에 따라 전체 회귀·A/B 전체 재검증·공식 연구 실행 안 함. 개발자의 변이 14종 보고를 참고했고 반복하지 않음 |
| 실제 작업 | 공유 설정·실제 SMB 연결/쓰기·외장 장치 쓰기·LaunchAgent 변경·알림·OCI·라이브 자료 접근·커밋·push 모두 없음 |

근거: `/private/tmp/poc613-smb-verify-alcqx85r/`의 `diffs/`, `related.log`, `test_independent_smb.py`, `independent.log`, `sync-none.json`, `sync-before_rename.json`, `sync-after_rename.json`, `share-identity.json`, `checks.json`, `black.log`, `flake8.log`. 시험의 마운트/주소/장치 응답은 주입값이므로 실제 SMB 실행 근거가 아니다.

검증자가 직접 수정한 곳:

| 파일·위치 | 수정 전 → 수정 후 |
|---|---|
| 결과서 상단 STATUS·VERIFIER_C, §15 제목 | C 변경분 확인 대기 → C 변경분 REJECTED(C-F1, §16). 기존 r3 VERIFIED 이력 유지 |
| 결과서 §16 | 없음 → 이번 C 변경분 재현·근거·판정 추가. 기존 §10~§14·부록 A 및 §15 본문 보존 |
| PLAN §8 제목 | 설계자 판정 대기 → 설계자 판정 반영. §8-6과 원문에 맞춘 상태 메타 정정 |
| PROGRAM_TRUTH 머리 최종 반영 날짜 | 2026-10-28 → 2026-10-29. 현재 반영 내용의 날짜와 맞춤 |

코드·시험·판정 원문·STATE 및 다른 파일은 수정하지 않았다. 사용자 handoff 문서는 읽거나 stage하지 않았다.

### 7) 사용자에게 한마디

다음은 C 보완의 개발자 정정이다. 이번 문제는 판정에 이미 포함된 실패 처리 경계이며 새 설계 판단이 필요하지 않다. A/B 첫 정기 실행 확인은 C와 별도로 유지한다. 실제 PC 공유 설정·연결·첫 백업 승인은 변경분 재검증 뒤에 진행한다.

## 17. 검증자 C 보완 r2 재확인 — 2026-10-30 · Codex

### 1) A. 기능/산출물 검증

- **A-1 지시 일치: 통과(C 보완 격리 구현·정정 범위).** C-F1의 이름 변경 뒤 동기화 실패 재현이 해결됐다. 실패하면 `.partial`로 되돌리고, 되돌리기 실패 시에도 완료 복사 기록이 없으므로 verify가 거절한다. 복원 진입은 로컬 기록 파일명의 순번으로 마지막 복사 단계가 COPY_HASH_OK인지 확인하며, 안쪽에서는 필수 manifest 기록의 해시를 대조한다. 기록이 없어졌을 때 대조를 생략하던 경로도 제거됐다.
- **A-2 보고 정확성: 통과.** staged 9개(A 1·M 8), unstaged 0, 사용자 handoff untracked 1개가 제출 상태와 같다. 직전 C 검증 이후 변경은 backup.py·백업 시험·문서 4개(총 6개)이며 보고와 일치한다. 줄 수 625·431·121·1,148과 관련 시험 298건도 실측과 같다. 새 메타/수치 오기는 발견하지 않았다.
- **A-3 산출물 정합성: 통과.** 기존 독립 재현 4건을 같은 입력·오류 위치로 다시 실행해 모두 통과했다. 이름 변경 뒤 오류는 COPY_INCOMPLETE·최종 폴더 없음·`.partial` 유지·verify REFUSED가 된다. 정상 대조군은 COPY_HASH_OK→RESTORE_VERIFIED를 유지했다. 아래 두 추가 대조에서도 미완료/기록 소실이 완료로 올라가지 않았다.
- **A-4 금지사항 위반: 없음.** 신규 의존성·외부 API·DB 스키마·파일 이동/삭제·실제 PC 공유 설정/연결/쓰기가 없다. 검증은 저장소 밖 사본·임시 Git/DB·가짜 마운트/주소 응답만 사용했다. 기존 LaunchAgent·실제 상태·운영 자료·OCI에는 접근하지 않았다.

**정정 경계 확인**

| 경계 | 확인 결과 |
|---|---|
| 이름 변경 전/뒤 동기화 오류 | 기존 독립 재현 모두 통과. 앞/뒤 어느 오류도 COPY_HASH_OK/RESTORE_VERIFIED로 올라가지 않고 COPY_INCOMPLETE를 유지 |
| 되돌리기 실패 | 관련 시험에서 최종 폴더가 남아도 결과/기록에 사유가 남고 verify는 REFUSED |
| 폴더 존재와 완료 구분 | 독립 추가 대조: 미완료 `.partial`을 시험에서 직접 최종 이름으로 돌려놔도 마지막 복사 기록이 미완료라 REFUSED. 최신 상태도 COPY_INCOMPLETE 유지 |
| 진입 확인 뒤 기록 소실 | 독립 추가 대조: verify가 manifest를 열 때 실제 임시 COPY_HASH_OK 기록 파일을 삭제. 이후 RESTORE_FAILED·'복사 완료 기록 없음'이며 완료로 진행하지 않음 |
| 기록 부재/마지막 미완료 | 관련 시험에서 COPY_HASH_OK 기록 쓰기 실패·삭제·뒤에 남은 COPY_INCOMPLETE를 거절. 기록 없는 사본을 자동 복원 확인하지 않는 동작은 §15-6에 공개 |
| 기존 안전 검사 | 수정한 기존 시험 3개는 기록까지 같은 해시로 바뀐 조건에서도 위험한 tar 항목·정해진 묶음 5개·커밋 목록을 계속 검사한다. 앞단 검사를 제거해 결함을 숨긴 시험이 아님 |

### 2) B. 구현 규칙/구조 품질 검증

- **B-1 암묵 fallback 위반: 없음.** C-F1의 복사 성공 기록 부재→manifest 대조 생략은 제거됐다. 미완료는 진입 거절, 진입 뒤 기록 부재는 복원 실패로 구분한다.
- **B-2 단일 책임 위반: 없음.** 되돌리기·복원 전제 확인 도우미가 기존 백업 책임 안에 있다. 목적지 분류/CLI 책임은 그대로다.
- **B-3 파일 책임 과다: 상한 위반 없음.** backup.py 625줄로 KS-10 경고선 600을 넘지만 상한 650 이내다. 이 근접 상태와 다음 기능 추가 전 분리 방침을 §15-3에 공개했다. 시험은 1,148줄로 상한 1,500 이내다.
- **B-4 실험/운영 경계 위반: 없음.** 06·tick·보관·설치 관련 경로는 구현 HEAD 대비 diff 0이다. 기존 A/B 통과 판정을 재판정하거나 실제 정기 실행이 성공했다고 간주하지 않았다.
- **B-5 배포/실행 경로 영향: 없음.** CLI·모듈·판정/PLAN/결과서가 모두 index에 추적돼 있다. 파일 이동·Dockerfile·OCI 배포/cron 변경이 없다. 이번 코드 변경은 백업 흐름 한 파일이며 실행 경로는 유지된다.
- **B-6 기술부채/구조적 퇴행: 추가 위반 없음.** 새 위조 방지 체계·범용 복구기·실험 계산을 추가하지 않았다. 복사 기록이 없는 다른 컴퓨터에서의 자동 복원 확인은 현재 범위 밖이라는 동작 변경을 공개했다. 과거 산출물을 현재 결과로 대체하지 않는다.

### 3) 기반 문서 준수

신규 문서는 기존에 신고된 C 보완 판정 원문이며 이번 정정에서 파일이 늘지 않았다. MongoDB·새 UI/의존성·운영 계산 복제는 없다. 봉인 DB OCI 미전송·사용자 handoff 제외·연구 브랜치 비공개 경계를 유지한다. 실제 C 설정/연결/쓰기는 여전히 별도 승인 후다.

### 4) 코드 안전성

**위험 수준: LOW(공개 한계·실제 연결 미확인).** 검증 범위에서 차단할 결함은 발견하지 않았다. 실제 SMB 호환성·PC 저장 계층 내구성·모든 캐시 제거·동시 교체 방어를 확인했다고 쓰지 않는다. 복원 확인에 현재 맥북의 로컬 복사 성공 기록이 필요하다는 제약은 공개돼 있다. backup.py 근접선 상태는 위 B-3과 같다.

### 5) 범위 폭주

**폭주 수준: MINOR.** C-F1의 되돌리기·복원 진입 조건 보강과 기존 시험 3개의 조건 정정이 공개돼 있고 실패 처리 요구에 직접 연결된다. 추가 플랫폼/외부 전송/자동 실행 범위는 없다.

### 6) 종합 판정

**종합 판정: VERIFIED — C SMB 보완 격리 구현 및 C-F1 정정 범위.** A/B 기존 통과 판정은 유지한다. 실제 C 백업 완료나 오늘 첫 자동 실행 성공을 뜻하지 않는다.

| 검증 | 실측 결과 |
|---|---|
| 관련 05·06·13 시험 | **298 passed**, 103.72초. 그 안의 백업 시험 81건 포함 |
| 기존 독립 재현 | **4 passed**. 정상·이름 변경 전/뒤 오류·서버 주소/인증 원문 미기록 |
| 추가 독립 경계 대조 | **2 passed**. 미완료 폴더를 최종 이름으로 직접 바꿈·진입 확인 뒤 실제 기록 파일 삭제. 독립 시험 합계 **6 passed**, 4.85초 |
| 정적 검사 | 이번 stage의 Python 4파일 black --check·flake8·py_compile 통과 |
| 줄 수 | backup.py 625, backup_source.py 431, CLI 121, 백업 시험 1,148. 제출값과 일치 |
| 소스·기록 보존 | HEAD `e0a94175f563cfc2d77c050866cf931a65801ab7`, staged 9개·unstaged 0. 검증 중 소스 일치 확인. 기존 검증자 §16 원문 및 변경 없는 SMB 목적지 검사·CLI·판정 원문 확인 |
| 근거 재사용/생략 | 개발자의 최종 코드 정정 변이 5종·SMB 변이 14종 보고를 참고했고 반복하지 않음. 보완 판정 §4에 따라 전체 회귀·A/B 전체 재검증·공식 연구 실행도 하지 않음 |
| 실제 작업 | 공유 설정·실제 SMB/외장 쓰기·LaunchAgent 변경·알림·OCI·라이브 상태/자료 접근·커밋·push 모두 없음 |

근거: `/private/tmp/poc613-smb-r2-verify-awxs8jr2/`의 `changed.json`, `diffs/`, `related.log`, `test_original_reproduction.py`, `test_record_boundary.py`, `independent.log`, `sync-*.json`, `record-incomplete-final.json`, `record-disappears.json`, `checks.json`, `black.log`, `flake8.log`. 기존 재현은 증거 출력 경로만 이번 임시 폴더로 바꿨다. 실제 SMB/실제 PC 성공 근거가 아닌 격리 시험 근거다.

검증자가 직접 수정한 곳(이 결과서 한 파일만):

| 위치 | 수정 전 → 수정 후 |
|---|---|
| 상단 STATUS·VERIFIER_C | C-F1 정정 재확인 대기/REJECTED → C 보완 r2 VERIFIED(§17). 과거 A/B 통과·C r1 반려 이력 유지 |
| §15 제목 | C-F1 정정 재확인 대기 → 변경분 r2 VERIFIED(§17) |
| §17 | 없음 → 이번 재현·경계 대조·판정 추가. §16 및 기존 검증/설계자 원문·개발자 보고 본문 보존 |

코드·시험·PLAN·STATE·PROGRAM_TRUTH·판정 원문·사용자 handoff 문서는 수정하지 않았다.

### 7) 사용자에게 한마디

다음은 보완 판정 §5의 구체적인 사용자 승인 묶음과 실제 PC 공유 설정/연결·첫 복사·Finder 해제/재연결·복원 확인이다. 이 절차가 끝나야 C 완료다. 같은 판정에 따라 추가 설계자 RESULT 재판정은 필요하지 않다. 오늘 2026-10-30 10:05 첫 자동 실행 확인은 C와 별개로 남아 있으며 이번 검증에서는 실행/확인하지 않았다.
