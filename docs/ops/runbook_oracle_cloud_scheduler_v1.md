# Oracle Cloud Scheduler Runbook V1

**Version**: 1.1
**Date**: 2026-01-12
**Status**: PRINT-ONLY REHEARSAL

---

> ⚠️ **IMPORTANT: 이번 단계에서는 등록을 하지 않습니다!**
>
> 이 문서의 명령들은 **출력만 기록**하는 것이 목적입니다.
> 실제 스케줄러 등록은 검증 완료 후 별도 승인 단계에서 진행합니다.

---

## 1. 개요

Oracle Cloud (Compute Linux) 환경에서 KRX Alertor Modular의 Ops Cycle을 매일 09:05 KST에 자동 실행하기 위한 런북입니다.

---

## 2. 목표 & 범위

| 항목 | 값 |
|------|-----|
| **실행 대상** | `deploy/run_ops_cycle.sh` |
| **실행 시간** | 매일 09:05 KST |
| **로그 위치** | `logs/ops_cycle.log` |
| **결과 확인** | `reports/ops/scheduler/latest/ops_run_latest.json` |

---

## 3. Timezone 결정표

기준: **매일 09:05 KST** 실행

| 서버 TZ | cron 시간 | 비고 |
|---------|-----------|------|
| `Asia/Seoul` (KST) | `5 9 * * *` | 서버 TZ가 KST인 경우 |
| `UTC` | `5 0 * * *` | 09:05 KST = 00:05 UTC |
| TZ 강제 지정 | `TZ=Asia/Seoul` + `5 9 * * *` | 권장 |

---

## 4. Preflight 체크리스트

> 아래 명령들을 **출력용으로 기록**합니다. 실행은 별도 승인 후.

### 4-A. OS/Timezone 확인

```bash
# Timezone 확인
timedatectl

# 현재 시간 확인
date
date -u  # UTC
```

### 4-B. Python/Venv 확인

```bash
# Python 버전
python3 --version

# venv 존재 확인
ls -la .venv/

# 필수 패키지 확인
.venv/bin/pip freeze | grep -E "(fastapi|uvicorn|requests)"
```

### 4-C. Backend Health 확인

```bash
# Health API (backend 실행 중이어야 함)
curl http://127.0.0.1:8000/api/ops/health
```

### 4-D. 안전장치 3종 확인

```bash
# 1. sender_enable = false
cat state/real_sender_enable.json

# 2. execution_gate != REAL_ENABLED
cat state/execution_gate.json

# 3. emergency_stop.enabled = false
cat state/emergency_stop.json
```

### 4-E. 아티팩트 갱신 확인 (경로)

```bash
# 최신 파일 존재 확인
ls -la reports/ops/scheduler/latest/ops_run_latest.json
ls -la reports/ops/summary/ops_summary_latest.json
ls -la reports/ops/drill/latest/drill_latest.json
```

---

## 5. 등록(설치) 단계 — 명령 출력만

> ⚠️ **아래 명령은 실행하지 마세요!** 
> 출력된 내용을 운영 메모에 복붙해두고, 별도 승인 후 실행합니다.

### 5-A. Cron 등록용 명령 출력

```bash
# 명령 출력 스크립트 실행 (출력만 함)
./deploy/oci/print_cron_install.sh
```

### 5-B. Systemd 등록용 명령 출력

```bash
# 명령 출력 스크립트 실행 (출력만 함)
./deploy/oci/print_systemd_units.sh
```

---

## 6. Rollback(되돌리기) 명령

> 등록 후 문제 발생 시 사용할 명령들입니다. (역시 출력만)

### 6-A. Cron 제거

```bash
# cron 확인
crontab -l

# cron 편집하여 해당 라인 삭제
crontab -e
```

### 6-B. Systemd 비활성화

```bash
# timer 중지
sudo systemctl stop krx-ops-cycle.timer

# timer 비활성화
sudo systemctl disable krx-ops-cycle.timer

# 상태 확인
systemctl status krx-ops-cycle.timer
```

### 6-C. Rollback 명령 출력 스크립트

```bash
./deploy/oci/print_rollback.sh
```

---

## 7. 사후 안전 확인

> 등록 직후 반드시 확인할 것 (명령 출력)

### 7-A. Health 확인

```bash
curl http://127.0.0.1:8000/api/ops/health
```

### 7-B. Drill 확인 (Console Only)

```bash
curl http://127.0.0.1:8000/api/ops/drill/latest | jq '.steps[] | select(.name=="send_console") | .delivery_actual'
# 기대값: "CONSOLE" 또는 "CONSOLE_SIMULATED"
```

### 7-C. 외부 발송 0 보장

- 정책 문서: `docs/contracts/contract_golden_build_freeze_v1.md`
- Safe Defaults: `sender_enable=false`, `gate=MOCK_ONLY`

---

## 8. 관련 문서

| 문서 | 경로 |
|------|------|
| 리허설 체크리스트 | [checklist_oracle_cloud_scheduler_rehearsal_v1.md](checklist_oracle_cloud_scheduler_rehearsal_v1.md) |
| 배포 Runbook | [runbook_deploy_v1.md](runbook_deploy_v1.md) |
| Golden Build Contract | [contract_golden_build_freeze_v1.md](../contracts/contract_golden_build_freeze_v1.md) |
