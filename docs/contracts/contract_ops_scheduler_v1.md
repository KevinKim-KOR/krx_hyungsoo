# Contract: Ops Scheduler V1

**Version**: 1.0
**Date**: 2026-01-10
**Status**: LOCKED

---

## 1. 개요

일일 운영 스케줄러 정책 및 기본 안전 구성을 정의합니다.

> 🔒 **스케줄러는 엔진 실행 금지**: Ops Cycle "호출"만 수행
> 
> 🔒 **기본 모드 고정**: DRY_RUN / CONSOLE_ONLY / sender_enable=false

---

## 2. 스키마 정의

### OPS_SCHEDULER_V1

```json
{
  "schema": "OPS_SCHEDULER_V1",
  "version": "1.0",
  "schedule": {
    "type": "daily",
    "time_kst": "09:05",
    "timezone": "Asia/Seoul"
  },
  "entrypoint": {
    "type": "API",
    "method": "POST",
    "path": "/api/ops/cycle/run"
  },
  "default_safety_config": {
    "execution_gate": "DRY_RUN",
    "delivery_policy": "CONSOLE_ONLY",
    "real_sender_enable": false,
    "external_send": "FORBIDDEN"
  },
  "artifacts": {
    "latest": "reports/ops/scheduler/latest/ops_run_latest.json",
    "snapshots": "reports/ops/scheduler/snapshots/"
  }
}
```

---

## 3. 스케줄 정책

| 항목 | 값 | 설명 |
|------|------|------|
| `type` | daily | 매일 실행 |
| `time_kst` | 09:05 | 장 시작 5분 후 |
| `timezone` | Asia/Seoul | KST 기준 |

---

## 4. 기본 안전 구성

| 항목 | 기본값 | 설명 |
|------|--------|------|
| `execution_gate` | DRY_RUN | 기본 시뮬레이션 모드 |
| `delivery_policy` | CONSOLE_ONLY | 콘솔만 출력 |
| `real_sender_enable` | false | 실발송 비활성 |
| `external_send` | FORBIDDEN | 외부 발송 금지 |

---

## 5. Entrypoint

| 타입 | 메서드 | 경로 |
|------|--------|------|
| API | POST | `/api/ops/cycle/run` |

**스크립트 호출 시:**
- `deploy/run_ops_cycle.ps1` (Windows)
- `deploy/run_ops_cycle.sh` (Linux/Mac)

---

## 6. 산출물 경로

| 경로 | 용도 | 방식 |
|------|------|------|
| `reports/ops/scheduler/latest/ops_run_latest.json` | 최신 실행 | Atomic Write |
| `reports/ops/scheduler/snapshots/*.json` | 스냅샷 | Append-only |

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-10 | 초기 버전 (Phase C-P.27) |
