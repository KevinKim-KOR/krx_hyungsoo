# PC 3-PUSH Sync — Windows Task Scheduler 등록 안내 (격하됨)

작성일: 2026-06-18
최신화: 2026-06-18 (Step `PARAM_HANDOFF_OCI_RUNTIME_3PUSH` — **정식 운영 등록에서 격하됨**)
Step 이력: OCI_THREE_PUSH_OPERATION_REGISTRATION → PARAM_HANDOFF_OCI_RUNTIME_3PUSH

---

## 0. ⚠ 격하 안내 (2026-06-18)

본 문서가 안내하는 PC Task Scheduler 등록은 **더 이상 정식 운영 등록 절차가 아니다**.

### 0.1 격하 사유

정식 운영 경로가 **PC → OCI message package sync** 에서 **PC → OCI PARAM snapshot handoff** 로 전환되었다 (Step `PARAM_HANDOFF_OCI_RUNTIME_3PUSH`). PC 는 더 이상 매 발송마다 message package 를 생성하지 않으며, OCI 가 latest PARAM 을 고정 사용해 runtime 메시지를 생성한다.

자세한 내용은 [`OCI_THREE_PUSH_CRONTAB_TEMPLATE.md`](OCI_THREE_PUSH_CRONTAB_TEMPLATE.md) §0 참조.

### 0.2 새 용도

`scripts/run_three_push_sync_task.ps1` + `scripts/sync_three_push_packages.py` 산출물은 삭제하지 않으며 다음 용도로만 사용한다:

```text
- manual recovery
- smoke test
- OCI 파일 전달 검증
- 비상 fallback
- 과거 package 기반 발송 재현
```

### 0.3 이미 등록한 Task Scheduler 처리

기존에 §3 절차로 schtasks 를 등록했다면 **비활성화 또는 제거**한다. 등록된 채로 두면 매일 KST 07:50/12:20/15:20 에 sync 가 실행되어 OCI 측에 무의미한 package 가 쌓이고 디스크/SSH 비용이 발생한다.

비활성화:

```powershell
schtasks /Change /TN "KRX_ThreePushSync_MarketBriefing"      /DISABLE
schtasks /Change /TN "KRX_ThreePushSync_HoldingsBriefing"    /DISABLE
schtasks /Change /TN "KRX_ThreePushSync_SpikeOrFallingAlert" /DISABLE
```

제거:

```powershell
schtasks /Delete /TN "KRX_ThreePushSync_MarketBriefing"      /F
schtasks /Delete /TN "KRX_ThreePushSync_HoldingsBriefing"    /F
schtasks /Delete /TN "KRX_ThreePushSync_SpikeOrFallingAlert" /F
```

### 0.4 정식 운영 PARAM handoff 절차 위치

PC PARAM 생성 + OCI handoff 는 CLI 1~2회로 충분하며 Task Scheduler 등록을 필요로 하지 않는다. 사용자가 PARAM 을 변경하기로 결정한 시점에만 수동 실행한다:

```powershell
# PARAM 생성 + approve
& "d:\AI\krx_alertor_modular\.venv\Scripts\python.exe" "d:\AI\krx_alertor_modular\scripts\create_three_push_runtime_param.py" --source manual_seed --approve

# OCI 로 PARAM handoff
& "d:\AI\krx_alertor_modular\.venv\Scripts\python.exe" "d:\AI\krx_alertor_modular\scripts\sync_three_push_runtime_param.py"
```

본 문서 이하 §1~§9 는 **manual recovery 시점에 사용할 수 있는 참고 절차**다.

---

## 1. (참고) 사전 조건

이하 절차를 manual recovery 로 사용할 때 필요한 조건이다.

PC에서 OCI로 3-PUSH package를 수동 sync하기 위한 Windows Task Scheduler 등록 절차.

---

## 1. 전제 조건

다음이 이미 준비된 상태여야 한다.

```text
- PC에 .venv가 구성되어 있음 (d:\AI\krx_alertor_modular\.venv\Scripts\python.exe)
- PC에 .env가 있고 OCI_SSH_TARGET=oci-krx 설정 완료
- ssh oci-krx 명령으로 OCI 접속이 성공 (Windows SSH config가 HostName/User/IdentityFile 처리)
- scripts/sync_three_push_packages.py 가 수동 실행으로 성공함
- scripts/run_three_push_sync_task.ps1 wrapper 가 존재함
```

확인:

```powershell
ssh oci-krx "echo SSH OK"
& "d:\AI\krx_alertor_modular\.venv\Scripts\python.exe" "d:\AI\krx_alertor_modular\scripts\sync_three_push_packages.py"
powershell.exe -ExecutionPolicy Bypass -File "d:\AI\krx_alertor_modular\scripts\run_three_push_sync_task.ps1"
```

마지막 명령 exit=0 이고 `state\three_push\sync_status_latest.json` 의 `status=success` 면 wrapper 통과.

---

## 2. 등록 대상 — 운영 시간표

| Task 이름 | KST 시간 | 용도 |
|---|---|---|
| KRX_ThreePushSync_MarketBriefing | 07:50 | 08:00 PUSH-1 발송 직전 sync |
| KRX_ThreePushSync_HoldingsBriefing | 12:20 | 12:30 PUSH-2 발송 직전 sync |
| KRX_ThreePushSync_SpikeOrFallingAlert | 15:20 | 15:30 PUSH-3 발송 직전 sync |

세 task 모두 동일 wrapper 호출. wrapper 한 번 실행으로 package 3종 + manifest가 모두 sync된다 (push별로 sync를 분리하는 게 아니다 — push별 발송 직전 시점에 fresh package를 보장하기 위해 3회 실행).

평일만 실행하면 충분하다 (월~금).

---

## 3. 등록 방법 — schtasks CLI (권장)

PowerShell을 **관리자 권한**으로 열고 아래 3개 명령을 실행한다.

`<USER>` 부분은 실제 Windows 계정명으로 치환한다.
`whoami` 명령으로 확인 가능.

```powershell
# PUSH-1: 07:50 매일 sync
schtasks /Create /TN "KRX_ThreePushSync_MarketBriefing" `
  /TR "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File `"d:\AI\krx_alertor_modular\scripts\run_three_push_sync_task.ps1`"" `
  /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 07:50 `
  /RU "<USER>" /RL HIGHEST /F

# PUSH-2: 12:20 매일 sync
schtasks /Create /TN "KRX_ThreePushSync_HoldingsBriefing" `
  /TR "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File `"d:\AI\krx_alertor_modular\scripts\run_three_push_sync_task.ps1`"" `
  /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 12:20 `
  /RU "<USER>" /RL HIGHEST /F

# PUSH-3: 15:20 매일 sync
schtasks /Create /TN "KRX_ThreePushSync_SpikeOrFallingAlert" `
  /TR "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File `"d:\AI\krx_alertor_modular\scripts\run_three_push_sync_task.ps1`"" `
  /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 15:20 `
  /RU "<USER>" /RL HIGHEST /F
```

`/RU "<USER>"` 와 함께 비밀번호 입력 prompt가 표시될 수 있다. PC 로그인 비밀번호를 입력한다.

비밀번호 입력 없이 등록하려면 `/RU SYSTEM` 으로 바꿀 수 있지만, SSH key가 사용자 프로파일(`%USERPROFILE%\.ssh\`)에 있다면 SYSTEM 계정에서 못 읽으므로 권장하지 않는다.

---

## 4. 등록 방법 — Task Scheduler GUI

CLI 사용이 부담스러우면 GUI로도 등록 가능.

1. `taskschd.msc` 실행.
2. **작업 만들기** 클릭.
3. **일반** 탭:
   - 이름: `KRX_ThreePushSync_MarketBriefing`
   - 보안 옵션: "사용자가 로그온했을 때만 실행" 또는 "로그온 여부에 관계없이 실행"
   - "가장 높은 수준의 권한으로 실행" 체크
4. **트리거** 탭 → 새로 만들기:
   - 매주, 시작: 07:50, 요일: 월/화/수/목/금
5. **동작** 탭 → 새로 만들기:
   - 프로그램: `powershell.exe`
   - 인수: `-ExecutionPolicy Bypass -WindowStyle Hidden -File "d:\AI\krx_alertor_modular\scripts\run_three_push_sync_task.ps1"`
   - 시작 위치: `d:\AI\krx_alertor_modular`
6. **조건** 탭:
   - "AC 전원이 연결된 경우에만 작업 시작" → 노트북이면 해제 권장
7. 확인 → 비밀번호 입력.

같은 절차를 12:20 (KRX_ThreePushSync_HoldingsBriefing), 15:20 (KRX_ThreePushSync_SpikeOrFallingAlert) task에 대해 반복.

> 주의: sync 시각은 항상 send 시각(08:00 / 12:30 / 15:30)보다 10분 빨라야 한다. sync를 15:30으로 설정하면 OCI runner 발송 시각과 겹쳐 fresh package 선행 보장이 깨진다.

---

## 5. 등록 확인

```powershell
schtasks /Query /TN "KRX_ThreePushSync_MarketBriefing"
schtasks /Query /TN "KRX_ThreePushSync_HoldingsBriefing"
schtasks /Query /TN "KRX_ThreePushSync_SpikeOrFallingAlert"
```

각 task의 다음 실행 시간이 표시되면 등록 성공.

---

## 6. 수동 트리거 테스트

scheduled run 시간을 기다리지 않고 즉시 실행해 검증할 수 있다.

```powershell
schtasks /Run /TN "KRX_ThreePushSync_MarketBriefing"
```

실행 후 다음을 확인:

```powershell
# wrapper log
Get-Content "d:\AI\krx_alertor_modular\logs\three_push_sync_task.log" -Tail 30

# sync status
Get-Content "d:\AI\krx_alertor_modular\state\three_push\sync_status_latest.json" | ConvertFrom-Json | Select-Object status, started_at, completed_at
```

`status: success` 여야 한다.

---

## 7. 운영 중단 / 재개

전체 중단:

```powershell
schtasks /Change /TN "KRX_ThreePushSync_MarketBriefing"      /DISABLE
schtasks /Change /TN "KRX_ThreePushSync_HoldingsBriefing"    /DISABLE
schtasks /Change /TN "KRX_ThreePushSync_SpikeOrFallingAlert" /DISABLE
```

재개:

```powershell
schtasks /Change /TN "KRX_ThreePushSync_MarketBriefing"      /ENABLE
schtasks /Change /TN "KRX_ThreePushSync_HoldingsBriefing"    /ENABLE
schtasks /Change /TN "KRX_ThreePushSync_SpikeOrFallingAlert" /ENABLE
```

삭제:

```powershell
schtasks /Delete /TN "KRX_ThreePushSync_MarketBriefing"      /F
schtasks /Delete /TN "KRX_ThreePushSync_HoldingsBriefing"    /F
schtasks /Delete /TN "KRX_ThreePushSync_SpikeOrFallingAlert" /F
```

---

## 8. 주의사항

```text
- PC가 켜져 있어야 sync가 실행된다. 발송 시각 직전 PC가 꺼져 있으면 sync 누락 → OCI runner는 stale_package로 발송 차단.
- 노트북 절전 모드 / 화면 잠금에서도 task는 실행되지만, "AC 전원 연결" 조건이 켜져 있고 배터리 상태면 안 돌 수 있다.
- SSH key passphrase가 걸려 있으면 비대화형 실행에서 실패한다. ssh-agent / pageant가 백그라운드에서 미리 unlock 상태여야 한다.
- wrapper는 logs/three_push_sync_task.log에 stdout만 append한다. 로그 폭증 방지를 위해 주기적으로 회수하거나 logrotate 도구를 별도 적용한다 (이번 STEP 범위 아님).
- token/chat_id는 wrapper와 sync script 둘 다 로그에 출력하지 않는다.
```

---

## 9. 트러블슈팅

| 증상 | 가능한 원인 | 확인 |
|---|---|---|
| schtasks 등록은 됐는데 실행 결과가 없음 | "마지막 실행 결과" 코드 확인 | `schtasks /Query /TN <name> /V /FO LIST` |
| wrapper exit_code != 0 | venv python 경로 불일치 / sync 스크립트 내부 실패 | `logs/three_push_sync_task.log` 확인 |
| sync_status_latest.json status=partial | OCI 업로드 일부 실패 (네트워크) | 다음 scheduled run에서 재시도. 반복되면 SSH 환경 점검 |
| sync_status_latest.json status=failed | scp 또는 verify 실패 | `ssh oci-krx "echo OK"` 로 SSH 접속부터 재확인 |
| OCI runner가 stale_package로 차단 | sync가 발송 전에 실행 안 됨 / asof_date가 UTC 기준 어제 | sync 시각이 발송 시각보다 명확히 빠른지 확인. 필요 시 OCI에 `THREE_PUSH_MAX_PACKAGE_AGE_HOURS=48` override |
