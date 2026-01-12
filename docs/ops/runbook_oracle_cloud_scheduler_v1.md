# Oracle Cloud Scheduler Runbook V1

**Version**: 1.0
**Date**: 2026-01-12
**Status**: DRAFT

---

## 1. 개요

Oracle Cloud (Compute Linux) 환경에서 KRX Alertor Modular의 Ops Cycle을 매일 09:05 KST에 자동 실행하기 위한 런북입니다.

> ⚠️ **주의**: 스케줄러 등록 전 반드시 안전장치를 확인하세요.

---

## 2. 실행 대상

| 항목 | 값 |
|------|-----|
| **스크립트** | `deploy/run_ops_cycle.sh` |
| **실행 시간** | 09:05 KST (매일) |
| **로그 위치** | `logs/ops_cycle.log` |
| **결과 확인** | `reports/ops/scheduler/latest/ops_run_latest.json` |

---

## 3. 타임존 주의사항

### 3-A. 서버 TZ가 Asia/Seoul (KST)인 경우

```bash
# cron entry
5 9 * * * cd /path/to/krx_hyungsoo && ./deploy/run_ops_cycle.sh >> logs/ops_cycle.log 2>&1
```

### 3-B. 서버 TZ가 UTC인 경우

09:05 KST = **00:05 UTC** (KST = UTC+9)

```bash
# cron entry (UTC 기준)
5 0 * * * cd /path/to/krx_hyungsoo && ./deploy/run_ops_cycle.sh >> logs/ops_cycle.log 2>&1
```

### 3-C. TZ 강제 지정 방식 (권장)

```bash
# crontab에서 TZ 강제
TZ=Asia/Seoul
5 9 * * * cd /path/to/krx_hyungsoo && ./deploy/run_ops_cycle.sh >> logs/ops_cycle.log 2>&1
```

---

## 4. 안전장치 확인 체크리스트

**스케줄러 등록 전 반드시 확인:**

| # | 항목 | 기대값 | 확인 명령 |
|---|------|--------|-----------|
| 1 | `sender_enable` | `false` | `cat state/real_sender_enable.json` |
| 2 | `execution_gate` | `≠ REAL_ENABLED` | `cat state/execution_gate.json` |
| 3 | `emergency_stop` | `enabled: false` | `cat state/emergency_stop.json` |

> ❌ **위 3개가 모두 확인되지 않으면 스케줄러 등록 금지**

---

## 5. cron 등록 방법

### 5-A. 등록용 cron entry 확인

```bash
# 화면에 출력만 (등록하지 않음)
./deploy/oci/print_cron_install.sh
```

### 5-B. 실제 등록 (수동)

```bash
# crontab 편집
crontab -e

# 아래 줄 추가 (TZ=Asia/Seoul 방식)
TZ=Asia/Seoul
5 9 * * * cd /home/opc/krx_hyungsoo && ./deploy/run_ops_cycle.sh >> logs/ops_cycle.log 2>&1
```

---

## 6. systemd timer 등록 방법

### 6-A. 유닛 파일 확인

```bash
# 화면에 출력만 (등록하지 않음)
./deploy/oci/print_systemd_units.sh
```

### 6-B. 실제 등록 (수동)

```bash
# 1. 유닛 파일 생성
sudo nano /etc/systemd/system/krx-ops-cycle.service
sudo nano /etc/systemd/system/krx-ops-cycle.timer

# 2. systemd 리로드
sudo systemctl daemon-reload

# 3. timer 활성화
sudo systemctl enable krx-ops-cycle.timer
sudo systemctl start krx-ops-cycle.timer

# 4. 상태 확인
systemctl status krx-ops-cycle.timer
systemctl list-timers | grep krx
```

---

## 7. 실행 확인

```bash
# 최신 실행 결과
cat reports/ops/scheduler/latest/ops_run_latest.json | jq .overall_status

# 최신 Ops Summary
cat reports/ops/summary/ops_summary_latest.json | jq .schema

# 로그 확인
tail -50 logs/ops_cycle.log
```

---

## 8. 트러블슈팅

### 문제: cron이 실행되지 않음

```bash
# cron 로그 확인
sudo cat /var/log/cron

# 또는
journalctl -u cron
```

### 문제: Python 경로 문제

```bash
# cron에서 전체 경로 사용
5 9 * * * cd /home/opc/krx_hyungsoo && /home/opc/krx_hyungsoo/.venv/bin/python ...
```

---

## 9. 관련 문서

| 문서 | 경로 |
|------|------|
| 배포 Runbook | [runbook_deploy_v1.md](runbook_deploy_v1.md) |
| 스케줄러 Runbook | [runbook_scheduler_v1.md](runbook_scheduler_v1.md) |
| Deployment Contract | [contract_deployment_profile_v1.md](../contracts/contract_deployment_profile_v1.md) |
