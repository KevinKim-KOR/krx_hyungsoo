# Contract: Scheduler V1

**Version**: 1.0
**Date**: 2026-01-04
**Status**: LOCKED

---

## 1. 개요

일일 운영 스케줄러 작업을 정의합니다.

---

## 2. 스키마 정의

### SCHEDULER_JOB_V1

```json
{
  "schema": "SCHEDULER_JOB_V1",
  "job_name": "daily_ops_cycle",
  "schedule": "0 9 * * *",
  "timezone": "Asia/Seoul",
  "command": "python -m app.run_ops_cycle",
  "cwd": "/path/to/krx_alertor_modular",
  "failure_policy": "LOG_AND_EXIT",
  "artifacts_written": [
    "reports/ops/daily/latest/ops_report_latest.json",
    "reports/ops/daily/snapshots/ops_run_*.json"
  ],
  "depends_on": [
    "emergency_stop.enabled == false",
    "backend server running"
  ]
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `job_name` | string | ✅ | 작업 이름 |
| `schedule` | cron | ✅ | Cron 표현식 |
| `timezone` | string | ✅ | 타임존 |
| `command` | string | ✅ | 실행 명령 |
| `cwd` | string | ✅ | 작업 디렉토리 |
| `failure_policy` | enum | ✅ | 실패 정책 |
| `artifacts_written` | array | ✅ | 생성 Artifacts |
| `depends_on` | array | - | 의존 조건 |

---

## 4. 실패 정책 (failure_policy)

| 값 | 설명 |
|----|------|
| `LOG_AND_EXIT` | 실패 로그 기록 후 종료 (기본) |
| `RETRY_ONCE` | 1회 재시도 후 종료 |
| `NOTIFY_AND_EXIT` | 알림 전송 후 종료 |

---

## 5. 환경별 실행 방법

### Windows

```powershell
.\.venv\Scripts\python.exe -m app.run_ops_cycle
```

### Linux/macOS

```bash
./deploy/run_daily_ops.sh
```

---

## 6. 제약 조건

- 스케줄러는 **ops cycle만** 호출
- Worker/Reconcile/Report 직접 호출 금지
- 실패해도 시스템은 안전하게 유지
- 실패는 snapshot으로 기록

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-04 | 초기 버전 (Phase C-P.17) |
