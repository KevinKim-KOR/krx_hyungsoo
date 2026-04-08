# Ops Scheduler Runbook V1

**Version**: 1.0
**Date**: 2026-01-10
**Phase**: C-P.27

---

## 1. 개요

일일 운영 스케줄러 및 Live Fire 절차에 대한 운영 지침서입니다.

---

## 2. 기본 운영 (평시)

### 기본 모드

| 항목 | 기본값 | 설명 |
|------|--------|------|
| `execution_gate` | DRY_RUN | 시뮬레이션 모드 |
| `delivery_policy` | CONSOLE_ONLY | 콘솔만 출력 |
| `real_sender_enable` | false | 실발송 비활성 |
| `external_send` | FORBIDDEN | 외부 발송 금지 |

### 일일 스케줄

- **시간**: 09:05 KST (장 시작 5분 후)
- **Entrypoint**: `POST /api/ops/cycle/run`
- **스크립트**: `deploy/run_ops_cycle.ps1` 또는 `deploy/run_ops_cycle.sh`

### 확인 사항

1. **Health Check**: `GET /api/status`
2. **Secrets Self-Test**: `GET /api/secrets/self_test`
3. **Ops Run Receipt**: `GET /api/ops/scheduler/latest`

---

## 3. 긴급정지 (Emergency Stop)

### 활성화

```bash
curl -X POST http://127.0.0.1:8000/api/emergency_stop \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "reason": "긴급 상황"}'
```

### 해제

```bash
curl -X POST http://127.0.0.1:8000/api/emergency_stop \
  -H "Content-Type: application/json" \
  -d '{"enabled": false, "reason": "상황 해제"}'
```

### 확인 포인트

- `GET /api/emergency_stop` → `enabled: false` 확인
- Ops Run Receipt에 `observed_modes.emergency_stop: false` 확인

---

## 4. 주간 Live Fire 절차

### 사전 조건 (모두 만족 필요)

| 조건 | 필수 값 |
|------|---------|
| Gate Mode | REAL_ENABLED |
| Self-Test | SELF_TEST_PASS |
| Emergency Stop | false |
| Outbox Messages | >= 1 |
| Sender Enable | true |
| Window Active | true |
| 요일 | 월-금 |
| 시간대 | 09:00-18:00 KST |

### 실행 순서

1. **Window 요청**
   ```bash
   POST /api/real_enable_window/request
   {"duration_minutes": 60, "reason": "Live Fire"}
   ```

2. **Approval (Two-Key)**
   - Key1, Key2 순차 승인

3. **Sender Enable**
   ```bash
   POST /api/real_sender_enable
   {"enabled": true, "reason": "Live Fire", "channel": "TELEGRAM_ONLY"}
   ```

4. **Live Fire 실행**
   ```bash
   POST /api/ops/push/live_fire/run
   ```

5. **자동 Lockdown 확인**
   - `sender_enable → false` 자동 복귀
   - `window → consumed` 자동 소진

### 증거 확인

- `GET /api/ops/push/live_fire/latest`
- `GET /api/ops/push/postmortem/regenerate`
- `reports/ops/push/live_fire/live_fire_latest.json`

---

## 5. 장애 시 확인 순서

1. **Health Check**
   ```bash
   GET /api/status
   ```

2. **Secrets Self-Test**
   ```bash
   GET /api/secrets/self_test
   ```
   - SELF_TEST_FAIL → `.env` 확인

3. **Emergency Stop**
   ```bash
   GET /api/emergency_stop
   ```
   - enabled: true → 의도된 것인지 확인

4. **Ops Run Receipt**
   ```bash
   GET /api/ops/scheduler/latest
   ```
   - `live_fire_step.reason` 확인

5. **Postmortem**
   ```bash
   POST /api/ops/push/postmortem/regenerate
   GET /api/ops/push/postmortem/latest
   ```

---

## 6. 관련 문서

- [Contract: Ops Scheduler V1](../contracts/contract_ops_scheduler_v1.md)
- [Contract: Ops Run Receipt V1](../contracts/contract_ops_run_receipt_v1.md)
- [Contract: Weekly Live Fire Ops V1](../contracts/contract_weekly_live_fire_ops_v1.md)
- [Contract: Live Fire Ops Receipt V1](../contracts/contract_live_fire_ops_receipt_v1.md)

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-10 | 초기 버전 (Phase C-P.27) |
