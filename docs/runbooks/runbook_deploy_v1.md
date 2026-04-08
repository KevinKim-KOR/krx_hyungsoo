# 운영 배포 Runbook V1

**Version**: 1.1 (Systemd Only)
**Date**: 2026-02-18
**Status**: ACTIVE

---

## 1. 개요

OCI Execution Plane에 KRX Alertor Modular 시스템을 배포하고 관리하는 표준 절차입니다.
P146부터 **"Systemd Only"** 원칙이 적용되어, 수동 프로세스 실행이 금지됩니다.

---

## 2. 배포 및 업데이트 (OCI)

### 2.1 코드 업데이트
```bash
cd /path/to/krx_hyungsoo
git fetch origin
git checkout main
git pull
pip install -r requirements.txt
```

### 2.2 Systemd 서비스 등록 (최초 1회)
```bash
# 1. Unit 파일 생성
./deploy/oci/print_systemd_backend_service.sh > krx-backend.service

# 2. 등록
sudo mv krx-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable krx-backend
```

### 2.3 서비스 재시작 (Standard)
코드 배포 후에는 반드시 아래 명령어로 서비스를 재시작해야 합니다.

```bash
# 권장: 스크립트 사용
./deploy/oci/restart_backend.sh

# 또는 직접 명령
sudo systemctl restart krx-backend
```

> 🚫 **CRITICAL WARNING**:
> - 절대로 `uvicorn backend.main:app`을 수동으로 실행하지 마십시오.
> - 수동 실행 시 `systemd` 프로세스와 포트(8000) 충돌이 발생하여 장애의 원인이 됩니다.

---

## 3. Trouble Shooting

### 3.1 포트 충돌 (Port 8000 in use)
`restart_backend.sh`가 실패하거나 `Address already in use` 에러 발생 시:

```bash
# 1. 점유 프로세스 확인
sudo lsof -i :8000

# 2. 강제 종료 (Kill)
sudo fuser -k 8000/tcp

# 3. 서비스 정상 시작
./deploy/oci/restart_backend.sh
```

### 3.2 로그 확인
`systemd`로 실행되므로 로그는 `journalctl`로 확인합니다.

```bash
# 실시간 로그 확인
sudo journalctl -u krx-backend -f

# 오늘 에러 로그만 확인
sudo journalctl -u krx-backend --since today -p err
```

---

## 4. 스케줄러 (Cron)

Daily Ops(09:05)는 Cron에 의해 자동 실행됩니다.

```bash
# Cron 등록 확인
crontab -l

# 수동 등록 (최초)
./deploy/oci/print_cron_install.sh | crontab -
```
