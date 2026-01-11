# 운영 배포 Runbook V1

**Version**: 1.0
**Date**: 2026-01-12
**Status**: ACTIVE

---

## 1. 개요

Golden Build(v1.0-golden)를 Windows/NAS/Server에 배포하는 단일 페이지 가이드입니다.

---

## 2. 사전 요구사항

| 항목 | 요구사항 |
|------|----------|
| Python | 3.10+ |
| Git | 2.30+ |
| OS | Windows 10+, DSM 7.x, Ubuntu 20.04+ |

---

## 3. 처음 설치

### 3-A. Windows

```powershell
# 1. Clone
git clone https://github.com/KevinKim-KOR/krx_hyungsoo.git
cd krx_hyungsoo
git checkout v1.0-golden

# 2. Bootstrap (venv + dependencies + health check)
.\deploy\bootstrap_windows.ps1
```

### 3-B. NAS (Synology)

```bash
# 1. Clone
git clone https://github.com/KevinKim-KOR/krx_hyungsoo.git
cd krx_hyungsoo
git checkout v1.0-golden

# 2. Bootstrap
chmod +x deploy/bootstrap_linux.sh
./deploy/bootstrap_linux.sh
```

### 3-C. Linux Server

```bash
# 동일 (bootstrap_linux.sh)
./deploy/bootstrap_linux.sh
```

---

## 4. 업데이트

```bash
# 1. Pull latest
git fetch origin
git checkout v1.x.x-next  # 다음 릴리스 태그

# 2. Dependencies 갱신
pip install -r requirements.txt

# 3. Health check
curl http://localhost:8000/api/ops/health
```

---

## 5. 스케줄러 등록

### 5-A. Windows Task Scheduler

1. **시작** → **작업 스케줄러** → **작업 만들기**
2. **이름**: `KRX Ops Cycle`
3. **트리거**: 매일 09:05
4. **동작**: 
   - 프로그램: `powershell.exe`
   - 인수: `-ExecutionPolicy Bypass -File "E:\AI Study\krx_alertor_modular\deploy\run_ops_cycle.ps1"`
5. **조건**: "컴퓨터가 AC 전원에 연결된 경우에만 실행" 해제

### 5-B. Synology NAS

1. **제어판** → **작업 스케줄러** → **만들기** → **예약된 작업** → **사용자 정의 스크립트**
2. **일정**: 매일 09:05
3. **스크립트**:
   ```bash
   cd /volume1/homes/admin/krx_hyungsoo
   ./deploy/run_ops_cycle.sh
   ```

### 5-C. Linux cron

```bash
# crontab -e
5 9 * * * cd /path/to/krx_hyungsoo && ./deploy/run_ops_cycle.sh >> logs/cron.log 2>&1
```

---

## 6. 실발송 3중 안전장치 체크리스트

배포 후 **반드시** 아래 3개를 확인하세요:

| # | 항목 | 기본값 | 확인 명령 |
|---|------|--------|-----------|
| 1 | `sender_enable` | `false` | `cat state/real_sender_enable.json` |
| 2 | `execution_gate` | `"MOCK_ONLY"` | `cat state/execution_gate.json` |
| 3 | `emergency_stop` | `enabled: false` | `cat state/emergency_stop.json` |

> ⚠️ **WARNING**: 3개 모두 확인되지 않으면 운영 시작 금지

---

## 7. 장애 대응

### 문제: Backend 시작 안됨

```bash
# 1. 로그 확인
cat logs/backend_*.log

# 2. 포트 확인
netstat -an | grep 8000

# 3. 재시작
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 문제: Ops Cycle 실패

```bash
# 1. 최신 스냅샷 확인
ls -la reports/ops/scheduler/snapshots/

# 2. 드릴 실행
curl -X POST http://localhost:8000/api/ops/drill/run

# 3. 로그 확인
cat logs/ops_runner/*.log
```

### 롤백

```bash
git checkout v1.0-golden
pip install -r requirements.txt
# 재시작
```

---

## 8. 관련 문서

| 문서 | 경로 |
|------|------|
| 스케줄러 Runbook | [runbook_scheduler_v1.md](runbook_scheduler_v1.md) |
| Golden Manifest | [release_manifest_golden_v1.json](release_manifest_golden_v1.json) |
| Deployment Contract | [contract_deployment_profile_v1.md](../contracts/contract_deployment_profile_v1.md) |
