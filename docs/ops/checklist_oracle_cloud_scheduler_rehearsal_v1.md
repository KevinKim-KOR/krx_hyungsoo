# Oracle Cloud Scheduler 리허설 체크리스트 V1

**Version**: 1.0
**Date**: 2026-01-12
**Status**: PRINT-ONLY (실행 금지)

---

> ⚠️ **WARNING: 이번 단계에서는 실행하지 않습니다!**
>
> 아래 명령들은 **복붙용 레퍼런스**입니다.
> 실제 실행은 별도 승인 후 진행합니다.

---

## 섹션 1: Preflight (환경/TZ/안전장치/Health)

### 1-1. OS & Timezone

```bash
# OS 정보
uname -a
cat /etc/os-release

# Timezone 확인
timedatectl
date
TZ=Asia/Seoul date
```

### 1-2. Python & Venv

```bash
# Python 버전
python3 --version

# venv 확인
ls -la .venv/bin/python
.venv/bin/python --version

# 필수 패키지
.venv/bin/pip freeze | grep -E "(fastapi|uvicorn|requests|pydantic)"
```

### 1-3. Backend Health

```bash
# Backend 실행 중인지 확인
curl -s http://127.0.0.1:8000/api/ops/health | jq .

# Secrets Self Test
curl -s http://127.0.0.1:8000/api/secrets/self_test | jq .decision
```

### 1-4. 안전장치 3종 확인

```bash
# 1. sender_enable (기대값: false)
cat state/real_sender_enable.json | jq .enabled

# 2. execution_gate (기대값: DRY_RUN 또는 MOCK_ONLY)
cat state/execution_gate.json | jq .mode

# 3. emergency_stop (기대값: false)
cat state/emergency_stop.json | jq .enabled
```

---

## 섹션 2: Install Options (Cron / Systemd)

### 2-A. Cron 설치용 명령 출력

```bash
# 출력 스크립트 실행 (명령 출력만)
./deploy/oci/print_cron_install.sh

# 출력된 내용을 복붙하여 crontab -e 에서 등록
# (지금은 실행하지 않음)
```

### 2-B. Systemd 설치용 명령 출력

```bash
# 출력 스크립트 실행 (명령 출력만)
./deploy/oci/print_systemd_units.sh

# 출력된 유닛 파일을 /etc/systemd/system/ 에 저장
# (지금은 실행하지 않음)
```

---

## 섹션 3: Post-Install Proof (실행 후 확인)

### 3-1. 스케줄러 등록 확인

```bash
# Cron 확인
crontab -l | grep krx

# Systemd Timer 확인
systemctl list-timers | grep krx
systemctl status krx-ops-cycle.timer
```

### 3-2. 증거 파일 확인

```bash
# Ops Cycle 최신 결과
cat reports/ops/scheduler/latest/ops_run_latest.json | jq .overall_status

# Ops Summary 최신
cat reports/ops/summary/ops_summary_latest.json | jq .schema

# Drill 최신
cat reports/ops/drill/latest/drill_latest.json | jq .overall_result
```

### 3-3. Console-Only 확인

```bash
# Drill의 send_console 단계 확인
cat reports/ops/drill/latest/drill_latest.json | jq '.steps[] | select(.name=="send_console")'
# delivery_actual: "CONSOLE" 또는 "CONSOLE_SIMULATED" 이어야 함
```

---

## 섹션 4: Rollback

### 4-1. Cron 제거

```bash
# cron 목록 확인
crontab -l

# cron 편집하여 KRX 관련 라인 삭제
crontab -e
```

### 4-2. Systemd 비활성화

```bash
# Timer 중지
sudo systemctl stop krx-ops-cycle.timer

# Timer 비활성화
sudo systemctl disable krx-ops-cycle.timer

# 서비스 상태 확인
systemctl status krx-ops-cycle.timer
systemctl status krx-ops-cycle.service
```

### 4-3. Rollback 명령 출력 스크립트

```bash
./deploy/oci/print_rollback.sh
```

---

## 완료 체크

| # | 항목 | 확인 |
|---|------|------|
| 1 | Preflight 모든 항목 OK | ☐ |
| 2 | 안전장치 3종 기본값 확인 | ☐ |
| 3 | Backend Health OK | ☐ |
| 4 | Install 명령 출력 확인 | ☐ |
| 5 | Rollback 명령 출력 확인 | ☐ |
| 6 | **실행 안함** (Print-Only) | ☑ |
