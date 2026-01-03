# Contract: Shadow Run V1

**Version**: 1.0
**Date**: 2026-01-03
**Status**: LOCKED

---

## 1. 개요

Shadow Run은 **REAL_ENABLED 실행 전 리허설**입니다.

> 🌑 **Shadow Mode**: 실제 실행(subprocess) 없이 "만약 Real이었다면" 시뮬레이션을 기록합니다.

---

## 2. 스키마 정의

### SHADOW_RUN_V1

```json
{
  "schema": "SHADOW_RUN_V1",
  "request_id": "uuid",
  "shadowed_at": "2026-01-03T19:30:00+09:00",
  "request_type": "REQUEST_RECONCILE",
  "would_run_command": ["python", "-m", "app.reconcile"],
  "inputs_checked": {
    "module_exists": true,
    "python_available": true,
    "config_valid": true
  },
  "expected_outputs": [
    "reports/phase_c/latest/recon_summary.json",
    "reports/phase_c/latest/recon_daily.jsonl"
  ],
  "decision": "SHADOW_OK | SHADOW_BLOCKED",
  "reason": "All checks passed. Ready for real execution."
}
```

| Key | Type | 필수 | 생성 주체 | 설명 |
|-----|------|------|-----------|------|
| `request_id` | UUID | ✅ | From Ticket | 원본 티켓 ID |
| `shadowed_at` | ISO8601 | ✅ | **Server** | Shadow 실행 시각 |
| `request_type` | string | ✅ | From Ticket | 티켓 타입 |
| `would_run_command` | array | ✅ | From Plan | 실행될 명령어 |
| `inputs_checked` | object | ✅ | Worker | 입력 검증 결과 |
| `expected_outputs` | array | ✅ | From Plan | 예상 출력 파일 |
| `decision` | enum | ✅ | Worker | Shadow 판정 |
| `reason` | string | ✅ | Worker | 판정 사유 |

---

## 3. Decision 정의

| Decision | 설명 |
|----------|------|
| `SHADOW_OK` | 모든 검증 통과, Real 실행 준비 완료 |
| `SHADOW_BLOCKED` | 검증 실패, Real 실행 불가 |

---

## 4. 저장소 경로

| 경로 | 파일명 패턴 | 정책 |
|------|-------------|------|
| `reports/tickets/shadow/` | `{request_id}.json` | 중복 생성 금지 |

---

## 5. Worker 동작

| Gate Mode | Worker 동작 |
|-----------|-------------|
| MOCK_ONLY | 기존 Mock 처리 |
| DRY_RUN | 기존 Dry-Run 처리 |
| REAL_ENABLED | **Shadow 강제**: 아티팩트 생성 + Receipt [SHADOW] |

---

## 6. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-P.7) |
