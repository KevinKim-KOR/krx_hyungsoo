# Contract: Deployment Profile V1

**Version**: 1.0
**Date**: 2026-01-12
**Status**: LOCKED

---

## 1. 개요

Golden Build(v1.0-golden)를 Windows/NAS/Server 환경에서 일관되게 배포하기 위한 프로필 계약입니다.

> 🔒 **No Secret in Repo**: Git에 시크릿 포함 금지
> 
> 🔒 **System Env Priority**: SYSTEM_ENV > DOTENV
> 
> 🔒 **Guard Always First**: 스케줄러 호출 시에도 안전장치 우선

---

## 2. Schema: DEPLOYMENT_PROFILE_V1

```json
{
  "schema": "DEPLOYMENT_PROFILE_V1",
  "profile": "WINDOWS_LOCAL | NAS_SYNOLOGY | LINUX_SERVER",
  "python_version": "3.10+",
  "venv_path": ".venv",
  "start_command": "uvicorn backend.main:app --host 0.0.0.0 --port 8000",
  "health_check": "GET /api/ops/health",
  "ops_cycle_command": "python -m app.run_ops_cycle",
  "secrets_source_priority": ["SYSTEM_ENV", "DOTENV"],
  "no_secret_in_repo": true,
  "log_locations": {
    "backend": "logs/backend_YYYYMMDD.log",
    "ops": "logs/ops_runner/",
    "daily": "logs/daily_YYYYMMDD.log"
  },
  "artifact_locations": {
    "reports": "reports/",
    "state": "state/",
    "snapshots": "reports/ops/**/snapshots/"
  }
}
```

---

## 3. Profile 정의

### 3-A. WINDOWS_LOCAL

| 항목 | 값 |
|------|-----|
| OS | Windows 10/11 |
| Python | `py -3.10` or `.venv\Scripts\python.exe` |
| venv 활성화 | `.\.venv\Scripts\Activate.ps1` |
| 실행 스크립트 | `deploy\run_ops_cycle.ps1` |
| 스케줄러 | Windows Task Scheduler |
| 시크릿 | System Environment Variables |

### 3-B. NAS_SYNOLOGY

| 항목 | 값 |
|------|-----|
| OS | DSM 7.x (Linux-based) |
| Python | `/usr/local/bin/python3` or venv |
| venv 활성화 | `source .venv/bin/activate` |
| 실행 스크립트 | `deploy/run_ops_cycle.sh` |
| 스케줄러 | Synology Task Scheduler (Control Panel) |
| 시크릿 | System Environment Variables (DSM 환경변수) |

### 3-C. LINUX_SERVER

| 항목 | 값 |
|------|-----|
| OS | Ubuntu 20.04+ / CentOS 8+ |
| Python | `python3.10` |
| venv 활성화 | `source .venv/bin/activate` |
| 실행 스크립트 | `deploy/run_ops_cycle.sh` |
| 스케줄러 | cron / systemd timer |
| 시크릿 | `/etc/environment` or systemd unit file |

---

## 4. Secrets Source Priority

```
1. SYSTEM_ENV (System Environment Variables) - 우선
2. DOTENV (.env file) - 로컬 개발 편의용
3. (금지) Hardcoded in code
```

> ⚠️ **WARNING**: .env 파일은 Git에 절대 포함 금지. `.gitignore`에 등록 필수.

---

## 5. Rollback Procedure

1. **Stop**: 실행 중인 서비스 중지
2. **Checkout**: `git checkout v1.0-golden` (또는 이전 태그)
3. **Dependencies**: `pip install -r requirements.txt`
4. **Health Check**: `GET /api/ops/health` 확인
5. **Restart**: 서비스 재시작

---

## 6. 안전장치 체크리스트

배포 후 반드시 확인:

| 항목 | 기본값 | 확인 |
|------|--------|------|
| `state/real_sender_enable.json` | `enabled: false` | ☐ |
| `state/execution_gate.json` | `mode: "MOCK_ONLY"` | ☐ |
| `state/emergency_stop.json` | `enabled: false` | ☐ |

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-12 | 초기 버전 (Phase C-P.39) |
