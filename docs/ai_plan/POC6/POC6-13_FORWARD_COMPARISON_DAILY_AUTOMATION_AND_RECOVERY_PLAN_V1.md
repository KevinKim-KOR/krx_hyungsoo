# POC6-13 개발 PLAN V1 — 전향 비교 정기 실행 · 연구 증거 별도 보관

작성 2026-10-28 · 작성자: 개발자(VSCode Claude) · 수신: 설계자

```text
STATUS   = PLAN 제출(2026-10-28 · 설계 §10 다섯 묶음 · 질문 3)
           → 설계자 PASS_WITH_REQUIRED_CORRECTIONS(2026-10-28 · Q1 = C 전체를 사용자 소유 다른 물리 저장소로 · Q2 = (b) · Q3 = 활성화 전 확인)
           → 판정 반영 = 이 문서 본문 정정 + §7(재제출 없음) → 격리 구현 → 검증자 r1 · r2 REJECTED → 정정 → r3 VERIFIED
           → 설계자 RESULT PASS(V1.1 · 2026-10-29 · …_RESULT_DECISION_2026-10-29.md) · 맥북 보조 A/B 설치됨(2026-10-29) · C 목적 기기 PC 확정(→ 아래 줄에서 완료)
           → C 별도 PC 연결 보완 계획 §8(윈도우 공유 폴더 · SMB 한 가지 · 질문 2) → 설계자 PASS_WITH_REQUIRED_CORRECTIONS(2026-10-29 · §8-6)
           → C 보완 구현 · 변경분 시험(결과서 §15) → 검증자 변경분 REJECTED(C-F1 · 결과서 §16) → 정정(결과서 §15-6) → C r2 VERIFIED(결과서 §17)
           → 사용자 승인(2026-10-30) · 구현 커밋 941044d9 push → 실제 PC 사본 · 해제 · 재연결 · RESTORE_VERIFIED(결과서 §15-7) = C 완료
           → A · B 첫 정기 실행 OK(2026-10-30 10:05 · D = 10-29 · 결과서 §14-4) → IMPLEMENTED_VERIFIED_CLOSED(2026-10-30)
DESIGN   = docs/ai_design/POC6/POC6-13_FORWARD_COMPARISON_DAILY_AUTOMATION_AND_RECOVERY_DESIGN_V1.md
DECISION = docs/ai_design/POC6/POC6-13_FORWARD_COMPARISON_DAILY_AUTOMATION_AND_RECOVERY_PLAN_DECISION_2026-10-28.md
조사     = 맥북 읽기(OS · 파이썬 · 시간대 · 전원 설정 · launchd · crontab) · 06 / 05 코드와 기존 06 산출물 읽기
           OCI 읽기 SSH 7회(echo 2 · df/ls · cron 시각 · 묶음 존재 · list-runs 1회 · 기존 보관 파일 1개 내려받기 = 속도 측정 뒤 삭제)
           예측 · 학습 · pull · 업로드 · 일정 설치 · 원격 쓰기 · 백업 쓰기 0 · 봉인 DB = 파일 읽기만(앞 200MB 압축률 표본 · 메모리)
```

A(정기 실행) · B(새 산출물 보관) · C(기존 자산 백업)를 묶음마다 나눠 적는다. 한 묶음의 승인 · 장치 대기가 다른 묶음의 격리 개발을 막지 않는다.

## 1. 현재 장치(설계 §10-1)

| 항목 | 실측 |
|---|---|
| OS | macOS 27.2(빌드 26B123) · arm64 |
| 시간대 | `/etc/localtime` → `Asia/Seoul` · `date` = KST +0900. 일정 KST 와 같음(바꿀 것 없음) |
| 파이썬 | `/Users/hyungsookim/projects/krx_hyungsoo/.venv/bin/python`(→ uv CPython 3.12.13 심볼릭). 절대 경로로 부르면 venv 가 잡힌다 |
| 작업 경로 | 저장소 루트 고정 필요(06 CLI 의 기본 경로 `state/...` 가 상대 경로). `.env` 는 `app/config.py` 가 모듈 기준 경로로 읽는다 |
| launchd | 사용자 `~/Library/LaunchAgents/` **폴더 없음**(설치 때 만든다) · 등록된 krx 작업 0 · 사용자 crontab 없음 |
| 비대화형 SSH | `env -i`(launchd 와 비슷한 빈 환경)에서 `ssh -o BatchMode=yes oci-krx` 성공. 06 의 `transfer.default_remote()` 대상 = `.env` 의 별칭 `oci-krx`(키 옵션 없음 · `~/.ssh/config` 사용) · 같은 빈 환경에서 원격 `echo` rc 0 · `git rev-parse` 성공(`/usr/bin/git`) |
| 알림 | `/usr/bin/osascript` 있음(`display notification`) · 새 설치 0 |
| 전원 설정 | `pmset`: **잠자기 1분**(배터리 · 전원 연결 모두) · 화면 끄기 3분(배터리) / 20분(전원) · Power Nap 1 |
| 디스크 | 맥북 여유 359GiB · 외장 저장장치 없음(사용자 답 · §7) |

- **가동 조건(판정 §4 정정)**: launchd 달력 일정은 잠든 맥북을 깨우지 않는다. 잠든 동안 놓친 일정은 깨어난 뒤 한 번 실행되고, 꺼져 있던 동안의 일정은 실행되지 않는다. `RunAtLoad` 는 로그인 때 호출이며 덮개를 열 때마다가 아니다. 깨어날 때 놓친 일정이 없으면 다음 예약 시각까지 기다린다. 그래서 **유효 창(10:00 ~ 15:20)에서 예약 · 로그인 · 놓친 일정 복귀 중 하나가 실제로 시작되고, 작업이 끝날 때까지 맥북을 쓸 수 있어야** 그날 기록이 생긴다. 사용자 답 = "평일 사용할 수 있으나 장담은 불가"(§7) → 매일 기록을 보장한다고 설명하지 않는다. 기록이 없는 날은 상태와 알림으로 드러낸다. 전원 설정 변경 · 예약 깨우기는 하지 않는다.
- **유휴 절전 방지(판정 §4)**: 실제로 진행하는 작업마다(A 수신 · 예측 · B 보관 · C 복사 · 복원) 그 작업 생애 동안만 `/usr/bin/caffeinate -i -w <자동화 pid>` 를 띄우고 작업이 끝나면(정상 · 실패 · 시간 초과 · 예외) 종료한다. 상태 조회 · 대기 중에는 띄우지 않는다. 덮개 닫기 · 강제 잠자기 · 전원 문제는 막지 못한다.
- 설치 때 macOS 가 '백그라운드 항목 추가' 알림을 띄우면 사용자가 허용해야 할 수 있다(연결 확인 때 실제 확인).

## 2. 기존 연결(설계 §10-2 · 모두 읽기로 확인 · 예측 · 학습 실행 0)

| 접점 | 실제 계약(소스) |
|---|---|
| 06 명령 | `scripts/run_forward_compare.py run [--pull] [--archive]` · `archive [--upload]` · `report`(파일 읽기만). 과거 시각 인자 없음. 마지막 줄 `RESULT {json}` |
| 종료 코드 | 0 = OK · ALREADY · ALREADY_RECORDED · SKIPPED_NO_NEW / 2 = SKIPPED_TOO_LATE · PARTIAL · CHECK_REQUIRED · PENDING_CALENDAR · NO_INPUT · NO_MODEL · NO_EVIDENCE / 1 = FAILED / 3 = BUSY |
| RESULT 칸 | status · id · D · close_cutoff_at · input_ok · record_type · roles · prediction · publication_confirmed · confirmed_at · confirmed_earlier · report · training(decision · reason · model_version) · maturity · pull · archive_local |
| 실행 기록 | `forward.run` 은 결과와 관계없이 `runs/<id>.json`(write once)을 남긴다. 여기에 today_kst · D · close_cutoff_at · not_predicted · existing · valid_run 이 있다. 예측 기록 `predictions/<D>/<id>.json` 의 entries[].methods{MEDIAN · RIDGE · HGB · MLP_CPU}.status · 영수증 `<id>.receipt.json` 의 confirmed_at |
| 주 기록 판정 | `records.primaries(root)` = (종목, D) 의 첫 PRIMARY 중 **영수증 해시 · id · D 가 맞고 confirmed_at < close_cutoff_at** 인 것만(+ 같은 입력 · 모델 판 RETRY 로 고친 방법). 자동화의 완료 판정이 이 함수를 그대로 쓴다(§3-2) |
| 잠금 | 연구 폴더 `.run.lock` = `fcntl.flock`(기다리지 않음 · 프로세스가 끝나면 풀림 · 남는 잠금 없음). `run` 과 `archive` 등록 둘 다 같은 잠금 → 겹치면 BUSY(rc 3 · 아무것도 쓰지 않음) |
| 중복 · 마감 | (종목, D) 첫 주 기록 고정 · 같은 입력 재실행 = 새 예측 없음 · 방법 실패는 같은 입력 · 같은 모델 판일 때만 마감 전 RETRY. 마감 = D 다음 거래일 15:30 KST(`forward.close_cutoff`) · **마감 뒤 호출은 DIAGNOSTIC 기록(SKIPPED_TOO_LATE)을 새로 남긴다** → 자동 호출은 15:20 이후 06 을 부르지 않는다 |
| 학습 | `training.ensure(valid_run)` — 마감 전 · 새 주 기록 종목이 있는 실행에서만 월 최대 1회. 추가 점검이 강제 재학습을 만들 경로 없음 |
| pull 실패 | `run --pull` 에서 OCI 목록 조회가 실패하면 EvidenceError → CLI 가 CHECK_REQUIRED(rc 2)로 끝나고 **06 예측은 실행되지 않으며 run 기록도 없다** |
| `run --archive` | 같은 프로세스에서 업로드까지 한다. 업로드 예외가 나면 RESULT 전체가 CHECK_REQUIRED 로 바뀌어 예측 결과 칸이 RESULT 에서 빠진다(파일은 남음) → **자동화는 `run --pull` 과 `archive --upload` 를 따로 부른다**. `run --archive` 자체는 이번에 고치지 않는다(판정 §1) |
| `archive --upload` | 미등록 산출물을 FORWARD_RESEARCH_ARTIFACTS 묶음 하나로 등록(같은 경로 다른 해시 = CHECK_REQUIRED · 덮어쓰기 없음) → 등록된 06 묶음마다 `upload_research`(OCI 목록 조회 · 없거나 손상이면 임시 칸에 올리고 `accept-upload` 해시 검사 · 이미 있으면 OK). OCI 는 bytes 만 보관 |
| 실측 소요 | 06 run 3회 = 6.9초(INITIAL 학습 포함) · 2.3초(ALREADY_RECORDED) · 4.4초(오늘 OK). 오늘 pull 5묶음 ≈ 2분 46초. OCI `list-runs` 1회 3.47초 |
| OCI 쪽 | cron 평일 마지막 작업 15:40 · 05 수집 매일 09:40(오늘 09:47 공개). 06 첫 묶음(10-23)은 이미 OCI 에 있다 → **A · B 에 OCI 코드 변경 · pull 필요 없음** |

**공유 코드 변경(Q2 (b) · 판정 §3)**: `app/ml_evidence/transfer.py` 에 '업로드 작업 1회 = 원격 완료 목록 1회 조회 · 작업 안 재사용' 함수를 더하고, 06 CLI `archive --upload`(와 같은 함수를 쓰는 `run --archive`)의 업로드 호출부만 그 함수로 바꾼다.

- 기존 단건 `upload_research` 는 인자 없이 부르면 지금과 같다(목록을 스스로 조회). 목록을 넘겨받을 때만 재사용한다.
- 묶음마다 기존 판정(manifest · 내용 일치 · 없음 · 손상 · 충돌 · `accept-upload` 확인)을 그대로 거친다. 원격 `accept` 결과가 OK 인 것만 작업 안 목록에 반영하고, 실패한 업로드는 넣지 않는다.
- 목록 조회 실패 = 기존처럼 예외(빈 목록으로 바꿔 전량 업로드하지 않음). 업로드할 묶음이 0 이면 목록도 조회하지 않는다(지금과 같은 SSH 0).
- 프로세스 밖 캐시 · 새 DB · 커서 없음. 05 pull 의 전체 목록 대조는 바꾸지 않는다.

## 3. 일정과 표시(설계 §10-3 · 판정 §5)

### 3-1. LaunchAgent 1개

자기 Label `com.krx-hyungsoo.poc6-13.forward-auto` 의 plist 1개. `ProgramArguments` = [절대 파이썬, 절대 `scripts/run_forward_auto.py`, `tick`] · `WorkingDirectory` = 저장소 루트 · `StartCalendarInterval` = 10:05 · 12:05 · 14:35 · 15:25 · `RunAtLoad` = true(로그인 때 한 번) · KeepAlive 없음 · `EnvironmentVariables` = PATH(/usr/bin:/bin:/usr/sbin:/sbin) · PYTHONIOENCODING(utf-8) · 표준 출력 = `state/ml/operations/poc6_13/launchd.log`. 설치는 `launchctl bootstrap gui/<uid>`, 해제는 `bootout` 뒤 자기 plist 만 지운다.

### 3-2. `tick` 판단(한 번 깨어날 때) — 예측(A)과 보관(B)을 따로 센다

| 지금(KST) | 예측(A) | 보관(B) |
|---|---|---|
| 자동 잠금(`.auto.lock` · flock · 기다리지 않음)을 못 잡음 | 호출 0 · 겹침 기록만 | 호출 0 |
| 10:00 전 | 호출 0 · 상태만 | 호출 0 |
| 10:00 이상 15:20 미만 | 오늘 예측이 '완료'가 아니고 · 오늘 자동 예측 시도 < 4 · 직전 예측 시도에서 15분이 지났으면 `run --pull`(20분 상한) | 보관 대기가 있고 · 오늘 자동 보관 시도 < 4 · (방금 예측을 불렀거나 직전 보관 시도에서 15분이 지났으면) `archive --upload`(10분 상한). **예측이 완료여도 보관 대기는 따로 처리**(판정 §5-2) |
| 15:20 이상 | 호출 0(AUTO_WINDOW_CLOSED) | 호출 0 · 남은 보관은 다음 날 창에서 |

- **예측 '완료'(판정 §5-1)**: ① 오늘 KST(`today_kst`)의 06 실행 기록 중 D 가 있는 가장 늦은 기록이 정한 D 를 '오늘 필요한 D'로 쓴다(06 이 이번 입력 · 달력으로 정한 값 · 자체 달력 계산 없음 · 수동 실행 기록도 포함). ② 그 D 에 대해 `records.primaries` 가 cohort 의 모든 종목(실제 분모 24)에 마감 전 영수증이 있는 주 기록을 돌려주고 ③ 그 주 기록들의 네 방법이 모두 OK(재시도로 고친 것 포함)일 때만 완료다. exit 0 · `publication_confirmed` 없는 OK · 다른 D 의 영수증 · '오늘 run 파일이 생겼다'는 사실은 완료가 아니다. 오늘 06 기록에 D 가 없으면 '필요 기준일 확인 불가'로 두고 다음 시도를 막지 않는다. 주말 · 휴장일에 D 가 어제가 아닌 것은 실패가 아니다.
- **보관 대기**: 06 `archive.local_state` 의 미등록 수 > 0 이거나, 등록된 06 묶음 중 자동화 보관 기록에서 업로드 OK 를 받은 적이 없는 것이 있으면 대기다.
- 호출 사유는 시각으로 **추정**한다(판정 §5-4): 일정 시각 + 2분 안 = SCHEDULED, 그 밖 = CATCH_UP. 실제 깨어남 이벤트를 확인했다고 쓰지 않는다.
- 20분 · 10분 초과면 자기가 띄운 프로세스 그룹에 SIGTERM, 30초 뒤 SIGKILL. 06 은 임시 파일 + link 로 쓰고 잠금은 flock 이라 중단 뒤 남는 잠금이 없다. 놓인 뒤 영수증 전에 끊긴 기록은 06 의 `confirm_pending` 이 다음 run 에서 마감 전이면 확인한다(기존 계약). 06 산출물 · 다른 실행 프로세스 · 그 잠금은 건드리지 않는다.

### 3-3. 상태 이름

| 예측 시도 결과 | 근거 | 뜻 |
|---|---|---|
| RECORDED_NEW | 06 OK · publication_confirmed true | 새 기록이 생김(완료 여부는 §3-2 판정을 따로 거침) |
| ALREADY_RECORDED | 06 ALREADY_RECORDED | 이미 같은 D 기록 · 그 D 의 주 기록 · 영수증으로 다시 판정 |
| INPUT_PENDING | NO_INPUT · NO_EVIDENCE | 입력 아직 없음(지연) |
| CALENDAR_UNKNOWN | PENDING_CALENDAR | 달력 확인 불가 · 필요한 D 도 확인 불가 |
| OTHER_RUN_BUSY | BUSY | 다른 실행 중(수동 실행 등) · 잠금을 지우지 않음 |
| CHECK_REQUIRED | CHECK_REQUIRED · NO_MODEL · PARTIAL · 공개 확인 없는 OK(수신 실패 포함 · 사유 원문) | 확인 필요 |
| TOO_LATE | SKIPPED_TOO_LATE | 마감 경과 진단 기록(정상 경로에선 생기지 않아야 함) |
| CALL_FAILED · CALL_TIMEOUT · INTERRUPTED | rc 1 · RESULT 줄 없음 · 상한 초과 · 시작 기록만 있고 프로세스 없음 | 호출 실패 · 시간 초과 · 중단 확인 필요 |

- **오늘 예측 상태**: BEFORE_WINDOW(10:00 전 · 첫 일정 전) · DONE(§3-2 완료) · RETRY_PENDING(미완료 · 시도 남음 · 창 안 · 마지막 결과 · 부분 수 표시) · NOT_CALLED(첫 일정이 지났는데 오늘 06 기록 · 자동 시도 0) · ATTEMPTS_EXHAUSTED(자동 4회 소진) · **AUTO_WINDOW_CLOSED**(15:20 지남 · 미완료 · 실제 D · 마감을 알면 함께 표시 · '수동 실행은 실제 마감 전까지 가능') · **DEADLINE_PASSED**(지금 ≥ 그 D 의 실제 close_cutoff_at · 미완료일 때만). D 를 모르면 '필요 기준일 확인 불가'를 붙이고 영구 결측이라고 쓰지 않는다(판정 §5-3).
- **보관 상태**: ARCHIVED(대기 0 · 마지막 업로드 OK) · ARCHIVE_PENDING(미등록 수 · 미확인 묶음 수 · 마지막 실패 사유) · NOT_TRIED. 예측과 보관 어느 쪽 성공도 다른 쪽 실패를 덮지 않는다.
- **백업(C) 상태(판정 §2)**: WAITING_TARGET(목적지 장치 없음 · 마운트 안 됨 · 내부 디스크 · 확인 불가) · COPY_INCOMPLETE · COPY_HASH_OK · RESTORE_VERIFIED.
- **지난 날**: 상태를 읽을 때 오늘 KST 날짜와 마지막 시도를 다시 비교한다. 어제의 DONE 은 오늘 DONE 이 아니다. 마지막 확인 뒤 지난 날(최대 7일)은 그날 기록 그대로 요약한다('자동 호출 기록 없음' 포함 · 그날 기록이 필요했는지는 달력을 다시 계산하지 않으므로 단정하지 않음). 지난 공백을 오늘 날짜로 지우거나 과거 예측을 만들지 않는다. 설치 전 D = 10-23 · 10-26 미기록은 그대로다.

### 3-4. 상태 CLI 출력 예(`python scripts/run_forward_auto.py status` · 파일 읽기만)

```text
전향 기록 자동 실행 — 2026-10-29(목) 10:07 KST 기준
일정    설치됨 · 활성 · 다음 12:05(오늘 예측 완료라 예측 호출은 건너뜀)
예측    DONE · D=2026-10-28 · 주 기록 24/24 · 방법 실패 0 · 공개 확인 10:06:12 < 마감 10-29 15:30
        06 run 20261029T010502Z_… · 입력 묶음 20261029T004001Z_… · 학습 KEEP mv_e926e066
시도    예측 1/4 · 10:05:02 ~ 10:06:15 · SCHEDULED(추정) · rc 0 / 보관 1/4 · OK
성숙    아직 때가 아님 48 · 도래 후 결측 0
보관    ARCHIVED · 대기 0 · 마지막 업로드 OK 10:06:40
백업    WAITING_TARGET · 외장 저장장치 없음
```

```text
예측    RETRY_PENDING · 입력 아직 없음(INPUT_PENDING) · D=2026-10-28 · 입력 정상 0/24 · 다음 12:05
예측    DONE · 이미 같은 D 기록(ALREADY_RECORDED) · D=2026-10-28 · 기존 공개 확인 10:01:44(06 run 20261029T010138Z_…)
예측    RETRY_PENDING · 확인 필요(CHECK_REQUIRED) 'OCI 목록 조회 실패(rc 255)' · 06 예측 실행 안 됨 · 필요 기준일 확인 불가 · 다음 14:35
예측    AUTO_WINDOW_CLOSED · D=2026-10-28 · 주 기록 20/24 · 실제 마감 10-29 15:30 전까지 수동 실행 가능
예측    DEADLINE_PASSED · D=2026-10-28 · 마감 10-29 15:30 지남 · 주 기록 0/24 · 소급하지 않음
예측    NOT_CALLED · 10:05 이후 오늘 06 기록 · 자동 호출 0(맥북이 꺼졌거나 잠든 시간은 알 수 없음)
보관    ARCHIVE_PENDING · 미등록 31 · 미확인 묶음 1 · 마지막 업로드 실패 12:06 'object 올리기 실패(rc 1)' · 다음 14:35
지난 날 10-28(화) 예측 AUTO_WINDOW_CLOSED(시도 2 · 마지막 CALL_TIMEOUT) · 10-27(월) 자동 호출 기록 없음
```

### 3-5. 로컬 알림 · 상태 파일

- 알림 = `osascript display notification`. (날짜 · 상태 이름)마다 한 번: 실패성 예측 시도(CHECK_REQUIRED · CALENDAR_UNKNOWN · TOO_LATE · CALL_FAILED · CALL_TIMEOUT · INTERRUPTED) · ATTEMPTS_EXHAUSTED · NOT_CALLED · AUTO_WINDOW_CLOSED · DEADLINE_PASSED · 보관 실패. 입력 지연(INPUT_PENDING)은 다음 시도가 남아 있으면 알리지 않는다. 예: `전향 기록 D=10-28 확인 필요 · 다음 14:35 · 확인 run_forward_auto.py status`. 보유 · 키 · 응답 본문 없음. **osascript 는 알림이 실제로 보였는지 알려 주지 않는다** → '알림 요청함(전달 확인 불가)' / rc ≠ 0 이면 '알림 실패'.
- 상태 = `state/ml/operations/poc6_13/`(06 연구 폴더 밖 · `.gitignore` 에 1줄 추가 · 지금은 무시 규칙 없음): `attempts/<KST 날짜>/<id>.start.json` · `<id>.end.json`(둘 다 write once · 시작 기록에 종류 · pid · 사유) · `latest.json` · `latest.txt`(임시 파일 → rename 원자 교체) · `notified.json` · `backup/<backup_id>.<단계>.json`. 끝 기록이 없고 pid 가 없으면 INTERRUPTED 로 표시한다(앞 기록을 고치지 않음).

## 4. 백업 C(설계 §10-4 · 판정 §2 정정)

### 4-1. 대상

| 대상 | 실행 폴더 | 파일(점 파일 제외) | 바이트 | 기존 해시 참조 |
|---|---:|---:|---:|---|
| `state/ml/research/poc6_08` | 2(첫 실행 · 정정) | 50 | 27,430,459 | 각 실행 protocol 의 입력 · 코드 해시 |
| `state/ml/research/poc6_09` | 1 | 5 | 2,000,053 | 08 산출물 해시(examples · predictions) |
| `state/ml/research/poc6_10` | 1 | 8 | 18,090,873 | 봉인 DB 해시 · cohort 해시 |
| `state/ml/research/poc6_11` | 5(첫 실행 · 정정 4) | 586 | 343,580,071 | 봉인 DB 해시 |
| 소계 | 9 | 649 | 391,101,456 | 점 파일 4개(`.run.lock`) 제외 · 심볼릭 0 |
| 봉인 DB `state/ml/research/krx_etf_universe.sqlite` | — | 1 | 1,862,836,224 | file `fe3022e9…dacf2` · content `c1a87776…bb4c` |
| 코드 | — | git bundle | 저장소 pack 193MiB | `main` + `research/poc6-10-local`(6779a31c) |

### 4-2. 코드 참조(각 실행 protocol 의 코드 파일 해시 ↔ 커밋의 같은 파일)

| 실행 | 기록된 기준 커밋 | 해시가 모두 맞는 커밋 | 코드 보존 공백 |
|---|---|---|---|
| 08 첫 실행 890a6100 | e499e5a5 | 없음(3df43539 와 10/14) | 4 파일 판 |
| 08 정정 9452f7e4 | e499e5a5 | 3df43539(15/15) | 0 |
| 09 65bb5838 | ed18f3ce | 49f5ab88(8/8) | 0 |
| 10 104cf57b | 50a728df | 6779a31c(17/17 · 로컬 연구 브랜치에만) | 0 |
| 11 423be637 · 713f5158 · 43bec799 · 78825f8d | 기록 없음 | 없음(549af63c 와 14/20 · 16/20 · 16/20 · 17/21) | 6 · 4 · 4 · 4 파일 판 |
| 11 93eb8426 | 기록 없음 | 549af63c(21/21) | 0 |

- 커밋 e499e5a5 · ed18f3ce · 50a728df · 3df43539 · 49f5ab88 · 549af63c 는 main 에, 6779a31c 는 로컬 브랜치에만 있다. bundle 은 이 7개가 실제로 복구되는지 확인한다. 공백은 '코드 보존 공백'으로 적고 최신 HEAD 로 메우지 않는다. 로컬 연구 브랜치는 비공개 bundle 안에만 있고 원격 브랜치 · main 병합은 없다.

### 4-3. 08 ~ 11 이 참조하는 02 ~ 06 입력(재업로드 0 · 연결 목록만)

| 사용 | 입력 | 기존 보관 |
|---|---|---|
| 08 | 05 일일 묶음 20261023T004002Z_9211e9fb(달력 · KOSPI object) | OCI 원본(05) |
| 08 | `poc6_03/…/copy.sqlite` | RESEARCH_REGISTRATION 20261022T103800Z_cf957e09 · OCI 에 있음 |
| 08(경로 · 해시) · 10(cohort 해시만) | `poc6_06/cohort_v1/cohort.json` · 08 은 `poc6_06/bootstrap/…/prices.json` 도 | FORWARD_RESEARCH_ARTIFACTS 20261023T045432Z_e3570691 · OCI 에 있음 |
| 09 | 08 정정 실행의 examples · predictions | C 대상 안 |
| 10 · 11 | 봉인 DB | C 대상 안 |

없는 필수 입력은 찾지 못했다.

### 4-4. 목적지(판정 §2 정정)

- **C 전체(08 ~ 11 · 봉인 DB · 코드 bundle · 입력 참조)를 사용자 소유의 다른 물리 저장소에 한 묶음으로 둔다.** 기본 = 맥북에 연결한 외장 SSD · HDD · USB. OCI `private_backups` 생성 · scp · 원격 sha256sum · 원격 mv 는 구현하지 않는다(봉인 DB 의 OCI 미전송 계약 유지 · POC6-05 PLAN 판정 2026-10-22). 코드만 OCI 로 올리는 분할 백업도 없다. 기존 05 / 06 OCI 보관은 그대로다.
- 목적지 검사: 목적지 경로가 속한 마운트 지점이 `/` · 내부 데이터 볼륨이 아니고, `diskutil info` 가 **Internal = 아니오** 인 장치여야 한다. 기록 = 마운트 지점 · 장치 식별자 · 볼륨 UUID · 버스 · 파일 시스템. 내부 디스크의 다른 폴더 · APFS 볼륨 · 확인 불가(네트워크 공유 포함)는 WAITING_TARGET 이다. 목적지가 없으면 내부 디스크에 같은 이름 폴더를 만들어 대신 쓰지 않는다.
- 사용자 답(2026-10-28): 외장 저장장치 없음 · "PC 는 2TB 라 넉넉함"(맥북과 다른 컴퓨터로 이해 · 확인 필요). 다른 컴퓨터 · NAS 를 목적지로 쓰려면 그 연결 · 비공유 범위를 따로 확인한다(판정 §2 마지막 줄 · §4 마지막 줄) → 이번 구현은 외장 장치용만 만들고 네트워크 공유는 WAITING_TARGET 으로 둔다. 장치가 정해질 때까지 C = WAITING_TARGET(완료 · 제외 승인 아님).
- 사용자 답(2026-10-29): "백업은 PC 에서만" → 'PC' = 2TB · 맥북(내장 494GB 실측)과 다른 컴퓨터로 확정. 맥북 → PC 연결 방식 · 비공유 범위 = 설계자 확인 대상(지금 구현 범위 밖 · WAITING_TARGET 유지). 백업 크기 실측 ≈ 2.4GB.
- 묶음 크기: 원본 그대로 약 2.25GB + bundle 193MiB(압축하지 않음 · 로컬 복사라 압축 이점이 작음). 시각: 10:00 ~ 15:45 KST 에는 시작하지 않는다(자동 창과 겹침 방지). 06 `.run.lock` · 자동 잠금을 잡지 않고 자기 잠금(`.backup.lock`)만 쓴다. 상한 60분.

### 4-5. 절차(`run_forward_auto.py backup …`)

1. `backup plan --target <경로>` — 대상 목록 · 크기 · 기존 해시 참조 · 코드 참조 · 입력 연결 · 목적지 검사 결과만 출력(쓰기 0).
2. `backup run --target <경로> --apply` — 목적지 검사 → 봉인 확인(기존 `verify_sealed_source`) → 목적지 `<…>/krx_hyungsoo_private_backup/poc6_13/<backup_id>.partial/` 에 `krx_etf_universe.sqlite`(복사하며 해시 · 봉인 file 해시와 대조) · `research_poc6_08_11.tar`(표준 tarfile · 상대 경로 · 일반 파일만 · 상위 이탈 · 절대 경로 · 심볼릭 거부 · 파일마다 읽은 바이트로 해시) · `code.bundle`(`git bundle create … main research/poc6-10-local`) · `env.json` · `inputs.json`(§4-3) · `manifest.json`(원본 파일별 상대 경로 · 크기 · SHA-256 · 묶음 파일 해시 · 코드 공백 · 장치 식별). 원본 크기 · 수정 시각이 묶는 동안 바뀌면 완료로 처리하지 않는다. 목적지에서 모든 파일을 다시 읽어 해시가 맞을 때만 `<backup_id>/` 로 이름을 바꾼다(COPY_HASH_OK). 같은 id 최종 폴더가 있으면 멈춘다(덮어쓰기 없음). 실패 · 불완전은 `.partial` 로 남아 정상 목록에 나오지 않는다(COPY_INCOMPLETE).
3. `backup verify --target <경로> --backup-id <id> --apply` — 최종 폴더를 맥북의 **빈** 임시 칸으로 되가져오기 → 묶음 해시 → 안전 검사 뒤 풀기 → 파일별 해시 대조 → 봉인 DB 사본 해시 → 임시 저장소에서 `git bundle verify` + §4-2 커밋 7개 확인 → RESTORE_VERIFIED. 모델 파일은 바이트 대조만. '바이트 복원 완료'와 '과거 실행 완전 재현'은 구분해 적는다. 라이브 저장소 · DB 위로 풀지 않는다. 자기 임시 칸만 지운다.
4. 원본 삭제 · 외장 장치 포맷 · 기존 백업 덮어쓰기 · 자동 삭제 · 클라우드 동기화 없음.

## 5. 변경 · 검증 · 승인(설계 §10-5)

### 5-1. 새 파일 · 바뀌는 파일

| 파일 | 책임 | 목표 줄 수 |
|---|---|---|
| `scripts/run_forward_auto.py`(신규) | 진입점 1개: `tick` · `status` · `install` · `uninstall`(둘 다 `--apply` 없으면 dry-run) · `backup plan/run/verify` | ≤ 220 |
| `app/forward_auto/schedule.py`(신규) | KST 창 · 일정 시각 · 사유 추정 · 상한 상수 — 순수 함수 | ≤ 120 |
| `app/forward_auto/view.py`(신규) | 06 산출물 읽기: 오늘 06 실행 기록 · 필요한 D · `records.primaries` 로 완료 판정 · 보관 대기 | ≤ 200 |
| `app/forward_auto/runner.py`(신규) | 자식 실행(프로세스 그룹 · 상한 · 정리) · 작업 생애 caffeinate · RESULT 해석 · 시도 기록 · tick | ≤ 400 |
| `app/forward_auto/status.py`(신규) | 상태 판정 · latest 원자 교체 · 출력 문장 · 알림 1회 | ≤ 350 |
| `app/forward_auto/launchd.py`(신규) | plist 만들기 · 설치 · 해제 · dry-run | ≤ 160 |
| `app/forward_auto/backup_source.py` · `backup.py`(신규 · 구현 때 KS-10 으로 둘로 나눔) | C: 목적지 검사 · 목록 · 계획 / 묶기 · 해시 · 복사 · 되가져오기 · 복원 대조 · bundle 확인 | 269 · 553(r2 정정 · 독립 검토 정정 뒤 실측) |
| `tests/test_poc6_13_forward_auto.py` · `tests/test_poc6_13_backup.py`(신규) | §5-3 시험 | 각 ≤ 1,000 |
| `app/ml_evidence/transfer.py`(수정 · Q2) | 업로드 작업 1회 목록 조회 함수 · 단건 함수의 선택 인자 | +40 안팎 |
| `scripts/run_forward_compare.py`(수정 · Q2) | `archive` 업로드 호출부만 새 함수로 | 수 줄 |
| `tests/test_poc6_05_evidence_store.py`(수정 · Q2) | 목록 재사용 시험 추가 | +120 안팎 |
| `.gitignore`(수정) | `state/ml/operations/` 1줄 | 2줄 |

- LaunchAgent 템플릿은 별도 파일 없이 `launchd.py` 가 만든다(절대 경로를 설치 때 채워야 하므로). OCI 배포(`deploy/oci/daily_ops.sh` 의 `git pull origin main`)로 새 파일 · 바뀐 transfer 가 OCI 에 내려가도 OCI 의 `accept-upload` · `list-runs` 동작은 바뀌지 않는다(바뀌는 것은 PC 쪽 업로드 호출 순서뿐). Dockerfile 영향 없음.
- 구현 뒤 PROGRAM_TRUTH(06 실행 방식 · 새 CLI · 상태 경로) · STATE · BACKLOG 를 갱신한다.

### 5-2. 기반 문서 대조

- A · B: 충돌 없음. POC6-06 예외 문장(KILL_SWITCHES · ASSUMPTIONS · PROJECT_ORIGIN_INTENT)은 "PC에서 … 전향 D20 예측 기록"이며 '수동'으로 한정하지 않는다. "OCI 증거 보관은 명시한 사용자 승인 범위로 수행" → B 자동 업로드는 §5-4 승인 묶음에 넣는다. 새 예외 문장을 더하지 않는다.
- C: 판정 §2 로 OCI 전송을 빼서 POC6-05 'OCI 미전송 계약'과 충돌이 없어졌다. 기반 문서 3곳 변경 없음.
- '혹시 필요할까 아카이브 레이어' 금지(KILL_SWITCHES §4): C 는 목적(복구)과 대상이 정해진 1회 사본이라 상시 계층을 만들지 않는다.

### 5-3. 시험(가짜 시각 · 가짜 자식 · 가짜 원격 · 가짜 외장 경로 · tmp 경로 · 라이브 state 쓰기 0)

- 시간: 09:59:59 · 10:00 · 10:05 일정 · 15:19:59 · 15:20(AUTO_WINDOW_CLOSED) · 15:25 이후 · 실제 마감 15:30 경계(DEADLINE_PASSED) · 토요일의 금요일 D(마감 = 다음 거래일) · 다음 날 로그인의 지난 날 요약 · 달력 미확인.
- 완료 판정: exit 0 이지만 영수증 없음 · 마감 뒤 영수증 · 다른 D 의 영수증 · 오래된 D 의 ALREADY · 주말 같은 D · 일부 종목만 기록 · 방법 일부 실패 → RETRY 로 고침 · 수동 실행 기록 반영.
- 중복 · 실패: 자동 잠금 겹침 · 수동 실행 BUSY · 예측 4회 상한 · 15분 간격 · 완료 뒤 예측 호출 0 · 예측 DONE + 보관 실패 → 다음 시도에서 보관만 · SSH 실패(CHECK_REQUIRED · run 기록 없음) · 자식 시간 초과(프로세스 그룹 정리) · 중단(INTERRUPTED).
- caffeinate: 작업 시작 전에 뜨고 정상 · 실패 · 시간 초과 · 예외 뒤 남지 않음 · 상태 조회에선 뜨지 않음(가짜 caffeinate 프로그램으로 실제 프로세스 생애 확인).
- 실제 접점 1개: 기존 06 시험의 tmp 자료로 실제 `forward.run` 을 돌려 만든 실행 기록 · 예측 · 영수증을 자동화가 그대로 읽어 DONE 을 판정하는지.
- Q2: 가짜 묶음 170개 이상에서 목록 조회 1회 · 이미 있는 것 / 새 것 / 원격 손상 / 조회 실패(예외 · 업로드 0) / 업로드 중 실패(그 뒤 상태 보존 · 성공으로 안 셈) · 목록 뒤 다른 실행이 먼저 올린 경우 · 단건 호출 호환.
- 백업: 내부 디스크 · 확인 불가 목적지 거부(WAITING_TARGET) · 같은 id 재실행 거부 · 원본 변경 감지 · 상위 이탈 · 심볼릭 거부 · 목적지 바이트 손상 → `.partial` 유지 · 빈 칸 복원 해시 일치 · 손상 사본 verify 실패 · tmp git 저장소 bundle 복구 · 10:00 ~ 15:45 시작 거부.
- plist: 절대 경로 · KeepAlive 없음 · 일정 4개 · dry-run 쓰기 0 · 기존 자기 plist 와 내용이 다르면 설치 거부.
- 관련 05 · 06 · 13 시험 + 마지막 전체 회귀 1회(Q2 공유 코드 변경 · 판정 §6). 공식 연구 · 학습 재실행 없음.

### 5-4. 승인 묶음(구현 · 검증 · 설계자 RESULT 판정 뒤 한 번에)

1. A · B: `~/Library/LaunchAgents/` 만들기 · 자기 plist 1개 · `launchctl bootstrap` · 정해진 `run --pull` / `archive --upload` 자동 호출 · osascript 알림 · (macOS 백그라운드 항목 허용 = 사용자 조작). 해제가 필요할 때 = `bootout` + 자기 plist 1개 삭제(연구 결과 · 상태 기록 삭제 없음).
2. C: 실제 외장 장치 경로 · 장치 식별 · 용량 확인 뒤 쓰기 · 맥북 빈 칸 복원 · 자기 임시 칸 정리.
3. 커밋 · push.

## 6. 질문(판정 완료 · §7)

1. Q1 — 봉인 DB 백업 목적지 → (a) 를 C 전체로 넓힘(판정 §2).
2. Q2 — 보관 업로드 확장 한계 → (b)(판정 §3).
3. Q3 — 가동 시간 → 활성화 전 확인(판정 §4) · 사용자 답 §7.

## 7. 판정 반영(2026-10-28 · PASS_WITH_REQUIRED_CORRECTIONS)

| 판정 | 반영 위치 |
|---|---|
| §2 Q1 — C 전체를 사용자 소유 다른 물리 저장소(외장 장치) · OCI 쪽 C 절차 삭제 · 장치 식별 · WAITING_TARGET · COPY_INCOMPLETE / COPY_HASH_OK / RESTORE_VERIFIED | §4-4 · §4-5 · §3-3 · §5-1 · §5-4 |
| §3 Q2 (b) — 업로드 작업당 목록 1회 · 기존 판정 보존 · 실패 미반영 · 조회 실패 = 예외 | §2 끝 · §5-1 · §5-3 |
| §4 Q3 — 가동 조건 표현 정정 · caffeinate 를 A · B · C 작업 생애마다 | §1 |
| §5-1 — 완료 = 실제 D · 주 기록 · 마감 전 영수증 · 실제 분모 · 방법 실패 0 | §3-2 · §3-3 |
| §5-2 — 예측 완료여도 보관은 따로 · 시도 수 분리 | §3-2 표 · §3-3 |
| §5-3 — 15:20 = AUTO_WINDOW_CLOSED · DEADLINE_PASSED 는 실제 close_cutoff_at 뒤만 · 지난 날 요약 | §3-3 · §3-4 |
| §5-4 — 사유 = 추정 · 알림 전달 확인 불가 | §3-2 · §3-5 |

**사용자 답(2026-10-28)**:
- 가동: "평일에 사용할 수 있으나 장담은 불가" → A · B 를 진행하되 매일 기록을 보장한다고 쓰지 않는다. 활성화 승인 때 이 조건을 다시 적는다.
- C 목적지: "맥북이라 외장하드는 없음 · PC 는 2TB" → 외장 장치 없음. 'PC' 가 맥북과 다른 컴퓨터라면 그 연결 · 비공유 범위는 판정 §2 대로 따로 확인한다. 그때까지 C = WAITING_TARGET(구현 · 가짜 외장 경로 시험은 진행).

## 8. C 별도 PC 연결 보완 계획(RESULT 판정 V1.1 §5 · 2026-10-29 · 설계자 판정 반영)

### 8-1. 사용자 환경(2026-10-29 사용자 답)

- PC = 윈도우 · 저장장치 2TB · 유선 랜. 맥북 = 와이파이. 백업할 때는 맥북을 잠깐 같은 공유기에 둘 수 있다(유선 연결도 가능).
- 백업 크기 ≈ 2.4GB(§4-1 · 결과서 §5). 처음 1회와 필요할 때만 복사한다(매일 아님).

### 8-2. 연결 방식 한 가지 — 윈도우 공유 폴더(SMB)

- **PC(사용자 조작)**: 2TB 저장장치에 백업 전용 폴더 1개를 만든다(OneDrive 등 동기화 폴더 밖). 윈도우 사용자 계정 1개에만 읽기 · 쓰기로 공유하고, Everyone · 게스트 공유는 쓰지 않는다. 네트워크 프로필 = 개인.
- **맥북(사용자 조작)**: 백업할 때만 Finder '서버에 연결'(`smb://<PC 이름 또는 IP>/<공유 이름>`)로 붙인다 → `/Volumes/<공유 이름>`. 비밀번호는 대화 · 저장소 · 로그에 남기지 않는다(키체인 저장은 사용자 선택).
- **개발자 도구**: 지금의 `backup run` / `backup verify` 를 그대로 쓰고 목적지 종류만 하나 더한다. `--pc-share <PC 이름 또는 IP>` 를 줄 때만 'PC 공유 폴더' 검사를 한다.
  - 마운트 지점 파일 시스템 = smbfs · 연결된 서버 = 사용자가 준 PC 이름/IP · localhost · 맥북 자신 아님 · 저장소와 다른 장치.
  - 외장 장치 검사(diskutil Internal · 디스크 이미지 거부)는 그대로 둔다. 공유 폴더를 외장 장치로 통과시키지 않는다(두 검사는 따로).
- **쓰기 · 대조 · 복원은 기존 그대로**: `<공유>/krx_hyungsoo_private_backup/poc6_13/<id>.partial` → 목적지 재읽기 해시(쓴 바이트 · 원본 기준) → 이름 바꾸기 → `verify` = PC 사본을 맥북 빈 임시 칸으로 되가져와 파일 해시 · 봉인 DB 해시 · 커밋 7개 확인.

### 8-3. 이 방식의 한계(미리 적음)

- SMB 에서 F_FULLFSYNC 가 안 되면 fsync 로 대신한다(기존 `_fsync_full`). 'PC 디스크까지 내려감'의 보장은 'PC 가 쓰기 완료를 응답함' 수준이다.
- 목적지 재읽기 · 되가져오기가 맥북 SMB 캐시에서 읽힐 수 있다(외장과 같은 한계).
- 전송 시간은 측정 전이다(첫 실행에서 잰다). PC 쪽 디스크 상태 · 윈도우 자체 백업 · 바이러스 검사는 확인 범위 밖이다.

### 8-4. 바뀌는 것 · 시험 · 승인

- 코드: `backup_source.py` 에 PC 공유 폴더 검사 함수 1개 · `backup.py` run / verify 의 목적지 검사 분기 · CLI 인자 1개. 06 · A · B 코드 변경 0.
- 시험: 가짜 마운트 정보(smbfs · 서버 일치 / 불일치 · localhost · 외장 검사와 섞이지 않음) · tmp 경로로 run → verify. 변경분만 시험 · 변경분 검증(판정 §5) · A · B 재검증 없음.
- 승인: ① 이 계획 판정(설계자) → ② 구현 · 변경분 검증 → ③ 사용자 승인 묶음 = PC 폴더 공유 설정(사용자 조작) · 맥북 연결 · 첫 백업 쓰기 · 복원 확인 · 커밋 · push.

### 8-5. 질문(설계자)

- **Q-C1.** 연결 방식을 윈도우 공유 폴더(SMB) 한 가지로 진행해도 되는가.
- **Q-C2.** §8-3 의 내구성 한계('PC 가 쓰기 완료를 응답함' 수준)를 C 완료 기준(RESTORE_VERIFIED)에 그대로 두어도 되는가.

### 8-6. 판정 반영(2026-10-29 · PASS_WITH_REQUIRED_CORRECTIONS · `docs/ai_design/POC6/POC6-13_PC_SMB_BACKUP_SUPPLEMENT_DECISION_2026-10-29.md`)

- **Q-C1 수용**: SMB 한 가지. `backup plan/run/verify --pc-share //서버/공유` 일 때만 공유 검사, 없으면 기존 외장 검사(서로 대신하지 않음).
- **판정 §2-1 실제 마운트 · 승인 목적지**: `/sbin/mount` 표에서 목적지가 속한 가장 긴 마운트 = smbfs · 마운트 원본의 서버 · 공유 = 승인값(대소문자 무시) · 서버 이름이 다르면 두 이름의 확인된 주소가 겹칠 때만 · 서버 주소가 localhost · 루프백 · 맥북 자신 · 사설(로컬) 대역 밖 · 확인 불가면 거부 · 목적지 장치 번호 = 그 마운트 · 저장소와 다른 장치. 승인값에 `사용자@` · 포트 · IPv6 를 넣으면 거부하고, 마운트 원문의 사용자 부분은 버린다(기록 안 함). 연결은 PC 의 IP 주소로 한다(`smb://<IP>/<공유>` · Bonjour 이름은 주소 확인이 안 되면 거부).
- **판정 §2-2 분리**: 공유가 해제돼 같은 이름의 로컬 폴더만 남으면 마운트 표에 smbfs 가 없어 run = WAITING_TARGET · verify = REFUSED. run · verify 시작 때 다시 확인하고, 파일 접근의 경로 이탈 · 링크 · 장치 번호 검사는 기존 그대로.
- **판정 §2-3 표현**: 확인하는 것 = 그 PC 의 SMB 연결. PC 디스크 자체의 원격 인증이라고 쓰지 않는다.
- **판정 §3 내구성**: F_FULLFSYNC 가 '지원 안 함'(ENOTSUP · EOPNOTSUPP · EINVAL · ENOTTY)으로 답할 때만 fsync 로 대신하고, 쓴 방식을 COPY_HASH_OK 기록 · 결과에 `sync` 로 남긴다. 그 밖의 오류(입출력 · 연결 끊김 · 권한)와 fsync 실패는 그대로 실패(COPY_INCOMPLETE). 외장 경로도 같은 규칙(APFS 는 파일 · 폴더 모두 F_FULLFSYNC 됨 · 2026-10-29 실측).
- **첫 실제 확인 절차**: 복사(COPY_HASH_OK) → 사용자가 Finder 에서 공유를 정상 해제 · 다시 연결 → `verify --pc-share`(목적지 다시 확인). 재연결을 못 했으면 복사 확인까지만 기록한다. 복원 기록에도 목적지 정보(`mount_dev` 포함)를 남겨 두 기록의 마운트 장치 번호를 나란히 적는다(관측값 · 캐시 제거 증명 아님).
- 변경분 시험 · 검증자 변경분 확인 → 사용자 승인 묶음(PC 폴더 공유 설정 · 연결 · 첫 백업 · 복원 확인 · 커밋 · push) 순서(판정 §5).
- **검증자 C-F1(2026-10-29) 정정**: 이름 바꾼 뒤 실패하면 최종 이름을 `.partial` 로 되돌리고(못 되돌리면 사유 기록), verify 는 그 id 의 마지막 복사 기록이 COPY_HASH_OK 일 때만 시작한다(폴더가 있다는 사실만으로 받지 않음 · 결과서 §15-6).
