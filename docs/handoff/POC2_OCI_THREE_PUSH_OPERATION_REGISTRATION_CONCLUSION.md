# POC2 OCI 3-PUSH 운영 등록 — Conclusion

작성일: 2026-06-18
Step: `OCI_THREE_PUSH_OPERATION_REGISTRATION`
직전 Step: `OCI_THREE_PUSH_CRONTAB_RUNNER_AUTOSEND` (2026-06-16 FIX r4)

---

## 0. 한 줄 요약

PC → OCI 3-PUSH package sync와 OCI runner Telegram autosend를 운영 스케줄(KST 07:50/12:20/15:20 sync → 08:00/12:30/15:30 send)로 연결할 수 있도록 **PC PowerShell wrapper + Task Scheduler 등록 절차 + OCI crontab template 최신화**를 완료했고, 그 절차가 실제로 동작하는지 수동 등가 실행으로 **Telegram 1회 발송 및 duplicate guard까지 실측 통과**시켰다.

scheduled run 시각이 아직 도래하지 않아 자동 trigger 도달은 미확인 — 이번 STEP은 **PARTIAL**로 보고한다.

---

## 1. 처리한 요구사항 (지시문 §3 / §16 AC 기준)

| ID | 요구 | 결과 | 비고 |
|---|---|---|---|
| AC-1 | PC sync schedule 등록 | **개발자 산출물 완료 / 사용자 등록 대기** | wrapper 스크립트 + schtasks 명령 + GUI 절차 문서화. 실제 등록은 사용자 PC에서 수행 |
| AC-2 | OCI crontab 3종 등록 | **template 최신화 완료 / 사용자 등록 대기** | KST 08:00/12:30/15:30 entry + venv 경로 + .env 자동 로드 안내 |
| AC-3 | sync 선행 구조 | DONE (시간 배치 설계) | 07:50/12:20/15:20 sync → 08:00/12:30/15:30 send 10분 마진 |
| AC-4 | .env / enable flag 확인 | DONE | OCI .env 키 8개 (token/chat_id 마스킹) + 4개 enable flag 모두 존재. 값은 출력하지 않음 |
| AC-5 | 실제 Telegram 수신 | DONE (수동 등가 실행) | OCI `venv/bin/python scripts/run_three_push_oci.py --push-kind market_briefing --mode send` → status=sent, telegram_sent=true |
| AC-6 | stale 미발생 (운영 검증 시) | DONE (재sync 후 fresh package) | 첫 dry-run에서 asof_date 기반 36.7h stale 감지 → PC re-sync로 asof_date=2026-06-18 갱신 후 통과 |
| AC-7 | duplicate guard 유지 | DONE | 동일 package_id 재실행 → status=skipped, reason=duplicate_package, telegram_attempted=false |
| AC-8 | status/history/log 기록 | DONE | `oci_runner_status_latest.json` / `oci_runner_history.jsonl` 모두 정상 기록. token/chat_id 미노출 |
| AC-9 | PC-to-OCI sync 유지 | DONE | sync script 변경 0건. wrapper는 호출만 |
| AC-10 | runner 유지 | DONE | runner 코드 변경 0건. crontab/Task Scheduler 외부 등록만 |
| AC-11 | message_text 의미 변경 없음 | DONE | message_text / message 모듈 0건 변경 |
| AC-12 | scheduler framework 없음 | DONE | Windows Task Scheduler + 기존 cron만 사용. Celery/Redis/Airflow 0건 |
| AC-13 | DB 추가 없음 | DONE | DB 변경 0건 |
| AC-14 | 매수/매도/위험 threshold 추가 없음 | DONE | 판단 로직 0건 추가 |
| AC-15 | 문서 갱신 | DONE | STATE_LATEST.md / B_NEXT_ACTIONS / FEATURE_INVENTORY / OCI_THREE_PUSH_CRONTAB_TEMPLATE.md / 본 conclusion 갱신 |

---

## 2. 산출물 분류 (지시문 §8 A/B/C/D/E/F/G/H)

### A. 개발자가 작성한 산출물

| 파일 | 종류 | 내용 |
|---|---|---|
| `scripts/run_three_push_sync_task.ps1` | 신규 | PC PowerShell wrapper. `.venv\Scripts\python.exe scripts/sync_three_push_packages.py` 실행 후 `logs/three_push_sync_task.log`에 append. exit code 전달. PS 5.1 NativeCommandError 회피를 위해 `2>&1` 대신 `*>`로 stdout+stderr 모두 동일 파일로 redirect (sync 스크립트가 INFO 로그를 stderr에 쏘는 특성 때문) |
| `docs/handoff/PC_THREE_PUSH_SYNC_TASKSCHEDULER.md` | 신규 | schtasks CLI 명령 3종 (월~금 07:50/12:20/15:20) + GUI 절차 + 등록 확인 / 수동 트리거 / 중단·재개 / 트러블슈팅 |
| `docs/handoff/OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` | 수정 | venv 경로 `venv/bin/python` 명시 / .env 자동 로드 (FIX r4 이후 동작) / PC sync 선행 시간표 / dry-run/send 등가 실행 절차 / 운영 중단 절차 |
| `docs/handoff/POC2_OCI_THREE_PUSH_OPERATION_REGISTRATION_CONCLUSION.md` | 신규 | 본 문서 |
| `docs/STATE_LATEST.md` | 수정 | §1 최신 STEP entry 추가 + 갱신 일자 변경 |
| `docs/handoff/POC2_B_NEXT_ACTIONS.md` | 수정 | 직전 STEP 완료 표시 + 다음 후보 갱신 |
| `docs/handoff/POC2_FEATURE_INVENTORY.md` | 수정 | 운영 자동화 메뉴에 PC Task Scheduler + OCI crontab 운영 상태 항목 반영 |

### B. 사용자가 실행해야 하는 OS 등록 작업

#### B-1. PC Windows Task Scheduler 등록 (관리자 PowerShell)

```powershell
$U = $env:USERNAME
schtasks /Create /TN "KRX_ThreePushSync_MarketBriefing" `
  /TR "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File `"d:\AI\krx_alertor_modular\scripts\run_three_push_sync_task.ps1`"" `
  /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 07:50 /RU $U /RL HIGHEST /F

schtasks /Create /TN "KRX_ThreePushSync_HoldingsBriefing" `
  /TR "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File `"d:\AI\krx_alertor_modular\scripts\run_three_push_sync_task.ps1`"" `
  /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 12:20 /RU $U /RL HIGHEST /F

schtasks /Create /TN "KRX_ThreePushSync_SpikeOrFallingAlert" `
  /TR "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File `"d:\AI\krx_alertor_modular\scripts\run_three_push_sync_task.ps1`"" `
  /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 15:20 /RU $U /RL HIGHEST /F
```

상세 절차는 `docs/handoff/PC_THREE_PUSH_SYNC_TASKSCHEDULER.md` §3 참조.

#### B-2. OCI crontab 등록

OCI에 SSH 접속 후 `crontab -e` 로 다음 추가:

```crontab
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# PUSH-1: 08:00 KST = UTC 23:00 전일 (UTC 요일 0-4)
00 23 * * 0-4 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_oci.py --push-kind market_briefing --mode send >> logs/three_push_cron.log 2>&1

# PUSH-2: 12:30 KST = UTC 03:30 (UTC 요일 1-5)
30 03 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_oci.py --push-kind holdings_briefing --mode send >> logs/three_push_cron.log 2>&1

# PUSH-3: 15:30 KST = UTC 06:30 (UTC 요일 1-5)
30 06 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_oci.py --push-kind spike_or_falling_alert --mode send >> logs/three_push_cron.log 2>&1
```

상세 절차는 `docs/handoff/OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` §3 참조.

### C. 사용자가 실제 수행 완료한 작업

- SSD 장애 복구: git pull / OCI 재생성 / holdings 재입력 / OCI .env 설정 / PC .env 일부 설정 / SSH alias `oci-krx` 접속 확인
- Telegram 토큰 재발급 + PC/OCI .env 동시 갱신 (이전 토큰 컨텍스트 노출 사고 대응)
- PC .env에 `OCI_SSH_TARGET=oci-krx` / `THREE_PUSH_REMOTE_PACKAGE_DIR=/home/ubuntu/krx_hyungsoo/state/three_push/packages` 설정 확인

### D. PC sync 결과 (수동 등가 실행)

```text
sync_status_latest.json:
  status: success
  oci_upload.package_results: market_briefing=ok, holdings_briefing=ok, spike_or_falling_alert=ok
  oci_upload.manifest_status: ok, manifest_uploaded_last: true
  oci_verification.status: success
  oci_verification.checks: 모든 항목 true (manifest_exists, schema_version, no_token, package별 schema_version_ok / package_id_matches_manifest / generation_status=ok / no_token)
asof_date: 2026-06-18 (3종 모두)
```

wrapper (`run_three_push_sync_task.ps1`) 수동 실행: exit=0, sync_status=success.

### E. OCI runner 결과 (수동 등가 실행)

```text
dry-run 3종:
  market_briefing      → dry_run_success (message_text_length=997)
  holdings_briefing    → dry_run_success (message_text_length=1606)
  spike_or_falling_alert → dry_run_success (message_text_length=878)

send 1건 (market_briefing):
  status=sent, telegram_sent=true, telegram_attempted=true
  package_id=three-push-20260618T124429-17d7a8
  duplicate_guard 검증: 즉시 재실행 → status=skipped, reason=duplicate_package, telegram_attempted=false
```

OCI venv: `/home/ubuntu/krx_hyungsoo/venv/bin/python` (Python 3.12.3, deps OK).

### F. Telegram 수신 여부

OCI runner가 `status=sent, telegram_sent=true` 반환. 사용자 단말기에서 실제 수신 확인 필요 — 본 conclusion 시점에서는 OCI 측 발송 성공만 확인되었고, 사용자 수신 확증은 사용자 시각 검증에 의존한다.

### G. scheduled run 도달 여부

미도달. PC Task Scheduler 등록 및 OCI crontab 등록은 사용자 수행 단계. 사용자 등록 완료 후 다음 scheduled 시각(KST 07:50 / 08:00 등)에서 자동 trigger 결과를 확인해야 DONE으로 격상.

### H. PARTIAL 사유 (지시문 §6 / §18 PARTIAL 조건 §18 일치)

```text
- 개발자 산출물(wrapper + 문서 + crontab template + conclusion + 회귀 검증)은 완료
- 수동 등가 실행은 PC sync success → OCI dry-run × 3 → OCI send 1회 → duplicate guard 모두 통과
- 단, 다음 두 항목은 사용자 실행 단계이며 아직 미수행:
  (1) PC Windows Task Scheduler 3 task 등록 (schtasks 명령 또는 GUI)
  (2) OCI crontab 3 entry 등록 (crontab -e)
- 따라서 자동 trigger에 의한 scheduled run 결과 로그(`logs/three_push_cron.log`, scheduled task history)는 아직 확인할 수 없음
- 사용자가 위 (1)(2)를 수행하고 첫 scheduled run을 확인하면 DONE으로 격상 가능
```

---

## 3. 변경된 파일 목록

| 파일 | 종류 |
|---|---|
| `scripts/run_three_push_sync_task.ps1` | 신규 |
| `docs/handoff/PC_THREE_PUSH_SYNC_TASKSCHEDULER.md` | 신규 |
| `docs/handoff/OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` | 수정 |
| `docs/handoff/POC2_OCI_THREE_PUSH_OPERATION_REGISTRATION_CONCLUSION.md` | 신규 |
| `docs/STATE_LATEST.md` | 수정 (§1에 entry 추가, 갱신 일자 변경) |
| `docs/handoff/POC2_B_NEXT_ACTIONS.md` | 수정 |
| `docs/handoff/POC2_FEATURE_INVENTORY.md` | 수정 |

backend 코드, frontend 코드, runner 동작은 **변경 0건**.

---

## 4. 신규 추가된 의존성

없음. PowerShell 표준 cmdlet + 기존 venv Python + 기존 `scripts/sync_three_push_packages.py` / `scripts/run_three_push_oci.py` 만 사용.

---

## 5. 지시문 외 변경

- `scripts/run_three_push_sync_task.ps1` 의 초안에서 `2>&1` redirect를 사용했다가 PS 5.1의 NativeCommandError로 실패 → `*>` 방식으로 정정. `*>` 는 stdout과 stderr를 모두 동일 파일로 redirect한다 (즉 두 stream 모두 보존). 정확한 동작 의미는 wrapper 상단 주석과 §2A에 반영.
- 토큰 노출 사고 대응으로 메모리 시스템에 `feedback_secret_file_handling.md` 영구 규칙 추가 (이번 STEP 작업 외 별도 사고 회복).
- 검증자 NOTES 반영 (2026-06-18 1차 REJECTED 후 FIX r1):
  - OCI_THREE_PUSH_CRONTAB_TEMPLATE.md §8/§9 의 disabled reason 문구 정정 (`disabled` → `autosend_disabled` / `push_kind_disabled`. 실제 runner 코드 `scripts/run_three_push_oci.py:561, 566` 와 정합).
  - PC_THREE_PUSH_SYNC_TASKSCHEDULER.md §4 GUI 절차의 "12:20, 15:30 task에 대해 반복" 표기를 "12:20, 15:20" 으로 정정 (15:30은 send 시각으로 sync와 겹쳐 fresh package 보장 깨짐).
  - POC2_FEATURE_INVENTORY.md §2.26 본문 갱신 — wrapper / TaskScheduler 문서 / 운영 등록 상태 / 운영 시간표 / 다음 조치를 본 STEP 결과로 반영 (이전엔 갱신 일자 1줄만 수정).
  - wrapper 주석 + conclusion §2A 의 redirect 설명을 실제 `*>` 동작 (stdout+stderr 양쪽 동일 파일 redirect) 과 일치시킴.

---

## 6. 알려진 한계 / 미완성

- **scheduled run 자동 trigger 결과 미확인** — 사용자가 Task Scheduler / crontab 등록을 완료한 후 첫 scheduled 시각이 지나야 검증 가능.
- **PC가 켜져 있어야 sync 동작** — PC 절전/꺼짐 상태에서는 sync 누락 → OCI는 stale_package로 안전 차단. 이는 정상 가드이나 운영 관점에서는 발송 누락.
- **asof_date vs UTC 자정 마진**: KST 07:50 sync (UTC 22:50 전일)에서 생성된 package의 asof_date는 UTC 기준 어제. 08:00 발송 (UTC 23:00 전일)에는 age ≈ 0h로 문제 없음. 12:30 KST 발송 (UTC 03:30 당일) 시 asof_date가 어제로 돌아가면 27.5h. 이는 기본 max=36h 안에 들어오지만, sync가 누락되거나 PC가 잠시 꺼졌다 깨면 마진이 좁다. 필요 시 OCI `.env`에 `THREE_PUSH_MAX_PACKAGE_AGE_HOURS=48`을 후속 STEP에서 검토.
- **SSH key passphrase / pageant**: PC가 SSH key에 passphrase가 걸려 있고 백그라운드 unlock 안 되어 있으면 Task Scheduler 비대화형 실행에서 sync가 실패할 수 있음. 본 STEP에서는 검증 안 함.
- **logrotate 미적용**: `logs/three_push_sync_task.log` 와 OCI `logs/three_push_cron.log` 는 무한 append. 운영 기간 길어지면 회수 필요.

---

## 7. 다음 검증자(Codex)에게 알릴 점

- 본 STEP은 OS 레벨 등록 작업이 사용자 수행 단계에 걸쳐 있어 자동 trigger 도달이 PARTIAL의 핵심 사유다. 검증자는 "DONE이 아닌 사유"를 §2H와 §6 기준으로 판단해주기 바람.
- wrapper 스크립트 (`scripts/run_three_push_sync_task.ps1`) 가 PS 5.1의 stderr 처리 특성 때문에 `2>&1`을 사용하지 않는 점은 의도된 설계. 회귀가 아닌 초기 설계 선택.
- conclusion §1 AC-5 / AC-7 / AC-8 의 실측 값은 OCI 측에서 직접 채집한 결과이며, 동일 명령은 `docs/handoff/OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` §9에 정리되어 있음.
- runner 코드 / sync 코드 / message_text / 산식 변경 0건. 본 STEP은 OS 레벨 운영 등록 + 문서 + wrapper 3종.

---

## 8. 사용자 확인이 필요한 항목

1. **Telegram 실제 수신 여부** — OCI runner는 status=sent를 반환했고 telegram_sent=true이지만, 사용자 단말기에서 실제 메시지가 도착했는지 확증 필요.
2. **Task Scheduler 등록 시점 결정** — 등록은 사용자 PC에서 수동으로 진행해야 함. 등록 후 다음 scheduled 시각에서 자동 trigger 결과 확인 가능.
3. **OCI crontab 등록 시점 결정** — OCI SSH 접속 후 수동 등록 필요.
4. **stale guard 마진** — 기본 36h를 그대로 유지할지, OCI .env에 `THREE_PUSH_MAX_PACKAGE_AGE_HOURS=48`로 안전 마진 추가할지 사용자 결정 항목. 이번 STEP에서는 변경하지 않음.

---

## 9. 회귀 검증

본 conclusion 작성 시점 검증 진행 중 (별도 보고서 §17 verification 섹션 참조). 회귀 대상:

- backend pytest
- black --check
- flake8
- frontend lint
- frontend build

본 STEP에서 backend / frontend 코드 변경 0건이므로 회귀 발생 가능성은 낮음.
