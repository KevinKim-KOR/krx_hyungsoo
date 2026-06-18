# OCI 3-PUSH Crontab Runner — 운영 등록 Template

작성일: 2026-06-15
최신화: 2026-06-18 (Step `PARAM_HANDOFF_OCI_RUNTIME_3PUSH` — **정식 운영 경로가 PARAM runtime 으로 전환됨**)
Step 이력: OCI_THREE_PUSH_CRONTAB_RUNNER_AUTOSEND → OCI_THREE_PUSH_OPERATION_REGISTRATION → PARAM_HANDOFF_OCI_RUNTIME_3PUSH

---

## 0. 정식 운영 경로 변경 안내 (2026-06-18)

### 0.1 정식 운영 경로 = PARAM Runtime

정식 crontab command 는 아래 `scripts/run_three_push_runtime_oci.py` 를 호출한다.

```text
PC 에서 사용자가 승인한 PARAM snapshot 생성
→ scripts/sync_three_push_runtime_param.py 로 OCI 전달
→ OCI latest PARAM 저장 (state/three_push/params/latest_runtime_param.json)
→ OCI crontab 이 하루 3회 scripts/run_three_push_runtime_oci.py 실행
→ OCI runtime 메시지 생성 (app/three_push_runtime_message_builder.py)
→ Telegram 발송
```

핵심: **PC 가 매 발송마다 message package 를 생성하지 않는다**. PC 는 승인된 PARAM snapshot 만 OCI 에 전달한다.

### 0.2 Fallback / Manual Recovery 경로 = 기존 Package 경로

기존 `scripts/run_three_push_oci.py` 는 정식 경로에서 제외하되 산출물은 그대로 보존한다.

용도:

```text
- manual recovery
- smoke test
- OCI 파일 전달 검증
- 비상 fallback
- 과거 package 기반 발송 재현
```

PC 의 `scripts/sync_three_push_packages.py` 와 `scripts/run_three_push_sync_task.ps1` /
Task Scheduler 등록도 **정식 운영 자동화에서 격하**되었다. 자세한 격하 사유는
[`PC_THREE_PUSH_SYNC_TASKSCHEDULER.md`](PC_THREE_PUSH_SYNC_TASKSCHEDULER.md) §0 참조.

---

PC sync 운영 등록(격하됨)은 [`PC_THREE_PUSH_SYNC_TASKSCHEDULER.md`](PC_THREE_PUSH_SYNC_TASKSCHEDULER.md) 참조.

---

## 1. 전제 조건

OCI 에서 실행 전 확인 사항:

```bash
# PC sync 완료 여부 확인 (PC 에서 sync 후)
ls ~/krx_hyungsoo/state/three_push/packages/
# 기대: manifest.json + latest_market_briefing.json + latest_holdings_briefing.json + latest_spike_or_falling_alert.json

# runner 동작 확인 (venv python 사용)
cd ~/krx_hyungsoo
venv/bin/python scripts/run_three_push_oci.py --push-kind market_briefing --mode dry-run
```

OCI 의 venv는 `venv/` (소문자) 이다. PC의 `.venv/` 와 경로가 다르다.

---

## 2. 필수 환경변수

OCI `~/krx_hyungsoo/.env` 에 다음 값이 설정되어 있어야 한다.

```text
TELEGRAM_BOT_TOKEN=<실제값>
TELEGRAM_CHAT_ID=<실제값>
PUSH_AUTOSEND_ENABLED=true
PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED=true
PUSH_AUTOSEND_HOLDINGS_BRIEFING_ENABLED=true
PUSH_AUTOSEND_SPIKE_OR_FALLING_ALERT_ENABLED=true
```

runner는 `.env` 파일을 자동 로드한다 (FIX r4 이후). crontab에 token/chat_id를 inline으로 쓰지 않는다.

옵션 환경변수:

```text
# package 경로 (기본값: /home/ubuntu/krx_hyungsoo/state/three_push/packages)
# THREE_PUSH_PACKAGE_DIR=/home/ubuntu/krx_hyungsoo/state/three_push/packages

# stale 판정 기준 시간 (기본값: 36시간)
# asof_date 는 UTC 자정 기준이므로, 평일 KST 08:00 발송 (UTC 23:00 전일) 까지는
# 같은 날 sync한 package가 fresh로 인정된다. 만약 sync 누락에 대비해 안전 마진이
# 필요하면 48시간으로 늘릴 수 있다.
# THREE_PUSH_MAX_PACKAGE_AGE_HOURS=36
```

`.env` 내용 확인 (값 마스킹):

```bash
grep -c '^TELEGRAM_BOT_TOKEN=' ~/krx_hyungsoo/.env
grep -c '^PUSH_AUTOSEND_ENABLED=' ~/krx_hyungsoo/.env
```

각각 `1` 이 나오면 키 존재. 값은 출력하지 않는다.

---

## 3. Crontab Template (정식 운영 경로 = PARAM Runtime)

`crontab -e` 로 편집:

```crontab
# ─── 3-PUSH 자동 발송 (PARAM Runtime, KST 기준) ────────────────────────
# OCI 서버 timezone 확인: date +%Z
# UTC 면 아래 UTC 컬럼 시간 사용.
# .env 자동 로드되므로 crontab에 TELEGRAM_BOT_TOKEN을 inline으로 쓰지 않는다.

# Cron이 PATH를 좁게 가지고 있으므로 시작 시 PATH 보강
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# PUSH-1: 시장 흐름 브리핑 — 평일 08:00 KST = UTC 23:00 전날 (요일 0-4 = 일~목 UTC)
00 23 * * 0-4 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind market_briefing --mode send >> logs/three_push_runtime_cron.log 2>&1

# PUSH-2: 보유 종목 관찰 브리핑 — 평일 12:30 KST = UTC 03:30 (요일 1-5 = 월~금 UTC)
30 03 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode send >> logs/three_push_runtime_cron.log 2>&1

# PUSH-3: 급등락/상승 관찰 신호 — 평일 15:30 KST = UTC 06:30 (요일 1-5)
30 06 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode send >> logs/three_push_runtime_cron.log 2>&1
```

> 📌 PUSH-1 의 요일이 `0-4` 인 이유: 한국 평일(월~금) 08:00 KST는 UTC 기준 전일 23:00 → UTC 요일은 일~목 (0-4).
> PUSH-2 / PUSH-3 는 UTC 시간이 같은 날이므로 요일 1-5 (월~금) 그대로.

---

## 3-fallback. Manual Recovery Template (package fallback)

정식 운영이 아닌 비상 복구용으로만 사용한다. crontab 에 함께 등록하지 않는다.

```bash
# 수동 등가 실행 예시 (정식 등록 X)
cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_oci.py --push-kind market_briefing --mode send
```

이 경로는:

```text
- PC 에서 sync_three_push_packages.py 로 미리 동기화된 package 의 message_text 를 그대로 보낸다.
- 정식 자동 발송 경로가 아니다.
- PARAM runtime 경로가 동작하지 않을 때만 사용한다.
- crontab 자동 등록 대상이 아니다.
```

---

## 4. PC PARAM handoff 와의 순서 (정식 운영 경로)

운영 시간표 (KST):

| 시각 | 작업 | 실행 위치 |
|---|---|---|
| 사용자 결정 시점 | PARAM snapshot 생성 + approve | PC CLI (`create_three_push_runtime_param.py --approve`) |
| 사용자 결정 시점 | PARAM OCI handoff | PC CLI (`sync_three_push_runtime_param.py`) |
| 08:00 | PUSH-1 market_briefing send | OCI crontab (PARAM runtime) |
| 12:30 | PUSH-2 holdings_briefing send | OCI crontab (PARAM runtime) |
| 15:30 | PUSH-3 spike_or_falling_alert send | OCI crontab (PARAM runtime) |

PARAM handoff 는 **매 발송 직전 sync 가 아니다**. 사용자가 PARAM 을 변경하기로 결정한 시점에만 새 PARAM 을 approve + sync 한다. PARAM 변경이 없으면 기존 latest PARAM 이 그대로 사용된다.

latest PARAM 부재 시:
- runtime runner 는 `status=failed, reason=missing_latest_param` 으로 차단.
- `state/three_push/oci_runtime_status_latest.json` 에 기록.
- 이는 정상 동작 (fail-closed). 사용자가 PARAM 을 approve + sync 후 다음 scheduled run 에서 정상화.

### 4-fallback. (격하된) PC package sync 시간표 참고

기존 PC sync 운영 시간표 (07:50 / 12:20 / 15:20) 는 **정식 운영에서 제외**되었다. 이는 manual recovery / smoke test 용도로만 보존한다. 자세한 내용은 [`PC_THREE_PUSH_SYNC_TASKSCHEDULER.md`](PC_THREE_PUSH_SYNC_TASKSCHEDULER.md) §0 참조.

---

## 5. dry-run 먼저 확인 (PARAM runtime)

발송 전 반드시 dry-run으로 각 push_kind 검증:

```bash
cd ~/krx_hyungsoo
venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind market_briefing --mode dry-run
venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode dry-run
venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode dry-run
```

`status=dry_run_success` 3건 확인 후 crontab 등록.

`status=failed, reason=missing_latest_param` 이 나오면 PC 에서 PARAM 을 approve + sync 한다:

```powershell
# PC PowerShell
& "d:\AI\krx_alertor_modular\.venv\Scripts\python.exe" "d:\AI\krx_alertor_modular\scripts\create_three_push_runtime_param.py" --source manual_seed --approve
& "d:\AI\krx_alertor_modular\.venv\Scripts\python.exe" "d:\AI\krx_alertor_modular\scripts\sync_three_push_runtime_param.py"
```

---

## 6. 실행 결과 확인

PARAM runtime 정식 경로:

```bash
# 최신 실행 결과
cat ~/krx_hyungsoo/state/three_push/oci_runtime_status_latest.json

# 실행 이력 (jsonl)
tail -20 ~/krx_hyungsoo/state/three_push/oci_runtime_history.jsonl

# crontab 로그
tail -50 ~/krx_hyungsoo/logs/three_push_runtime_cron.log

# 발송 registry (중복 방지, key = push_kind::param_id::KST_date)
cat ~/krx_hyungsoo/state/three_push/oci_runtime_sent_registry.json

# 현재 latest PARAM 정보
cat ~/krx_hyungsoo/state/three_push/params/latest_runtime_param.json
```

기존 package fallback 경로 (manual recovery):

```bash
cat ~/krx_hyungsoo/state/three_push/oci_runner_status_latest.json
tail -20 ~/krx_hyungsoo/state/three_push/oci_runner_history.jsonl
tail -50 ~/krx_hyungsoo/logs/three_push_cron.log
cat ~/krx_hyungsoo/state/three_push/oci_sent_registry.json
```

token/chat_id 는 어떤 산출물에도 기록되지 않는다.

---

## 7. crontab 등록 / 확인 / 삭제

등록:

```bash
crontab -e
# 위 §3 내용을 붙여넣고 저장
```

확인:

```bash
crontab -l
```

다음 실행 예정 확인 (옵션 — `cron-utils` 또는 외부 도구):

```bash
# 단순 확인: 운영체제의 syslog/journal에서 CRON 실행 로그 확인
sudo grep CRON /var/log/syslog | tail -5
# 또는
journalctl -u cron --since "10 min ago"
```

삭제 (전체 중단):

```bash
crontab -r       # 전체 crontab 삭제 — 위험! 다른 cron job이 있으면 안 됨
crontab -e       # 안전한 방법: 해당 줄만 주석 처리
```

---

## 8. 운영 중단 방법

전체 발송 중단 (cron entry는 그대로 두고 runner 측에서 차단):

```bash
# OCI .env 편집
nano ~/krx_hyungsoo/.env
# PUSH_AUTOSEND_ENABLED=false 로 변경 후 저장
```

다음 cron 실행 시 runner가 `status=skipped, reason=autosend_disabled` 로 차단.

push_kind 별 중단:

```bash
# PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED=false
```

이 경우 해당 push_kind만 `status=skipped, reason=push_kind_disabled` 로 차단된다.

---

## 9. 수동 검증 등가 실행 (PARAM runtime)

scheduled run 시간을 기다리지 않고 동일한 command를 즉시 실행해 검증:

```bash
cd ~/krx_hyungsoo
venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind market_briefing --mode send
```

- status=sent, telegram_sent=true → 정상
- status=skipped, reason=duplicate_runtime → 동일 `push_kind + param_id + KST 날짜` 재실행 (정상 — duplicate guard)
- status=failed, reason=missing_latest_param → PC 에서 PARAM approve + sync 필요
- status=failed, reason=param_load_error → PARAM 파일 손상 또는 schema 불일치 — PC PARAM 재생성
- status=skipped, reason=push_kind_not_in_param → PARAM 의 `enabled_push_kinds` 에 해당 push_kind 없음
- status=skipped, reason=autosend_disabled → `.env` 의 `PUSH_AUTOSEND_ENABLED=true` 확인
- status=skipped, reason=push_kind_disabled → `.env` 의 `PUSH_AUTOSEND_{KIND}_ENABLED=true` 확인
- status=failed, reason=forbidden_wording → message_text 에 금지 문구 포함 (정책 가드)

---

## 10. 주의사항

```text
- TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 는 로그/status 파일에 기록되지 않는다.
- 같은 package_id 는 1회만 발송된다 (oci_sent_registry.json 관리).
- generation_status=failed 인 package 는 발송하지 않는다 (Run.message_text, message_contract.message_text 모두 빈/None 강제).
- stale package (기본 36시간 초과) 는 발송하지 않는다.
- 금지 문구(매수/매도/비중조절/조정장 확정/위험 threshold 확정 등) 가 포함된 message_text 는 발송하지 않는다.
- crontab은 로그인 shell 환경변수를 상속하지 않으므로 PATH 보강이 필요할 수 있다 (§3 참조).
- OCI 서버 timezone이 UTC가 아니라면 crontab 시간을 다시 계산해야 한다 (`date +%Z` 로 확인).
```
