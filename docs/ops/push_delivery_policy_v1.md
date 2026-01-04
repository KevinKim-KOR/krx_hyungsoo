# Push Delivery Policy V1

**Version**: 1.0
**Date**: 2026-01-04
**Status**: LOCKED

---

## 1. 개요

푸시 메시지 발송 라우터의 정책을 정의합니다.

---

## 2. Gate Mode별 행동 수칙

| Gate Mode | 외부 발송 | 결정 |
|-----------|-----------|------|
| `MOCK_ONLY` | ❌ 불가 | 전량 CONSOLE |
| `DRY_RUN` | ❌ 불가 | 전량 CONSOLE |
| `REAL_ENABLED` | ⚠️ 조건부 | Secrets 확인 필요 |

---

## 3. Secrets Fallback 규칙

```
if gate_mode == "REAL_ENABLED":
    if secrets_available:
        channel = "EXTERNAL"  # 외부 발송 시뮬레이션
    else:
        channel = "CONSOLE"   # Fallback
else:
    channel = "CONSOLE"       # 무조건 Console
```

> 🔒 **Secrets 없으면 CONSOLE**: REAL_ENABLED라도 Secrets가 없으면 무조건 CONSOLE로 회귀

---

## 4. Emergency Stop 규칙

```
if emergency_stop_enabled:
    channel = "CONSOLE"  # 강제 Console
    reason = "EMERGENCY_STOP_FORCED_CONSOLE"
```

> 🛑 **Emergency Stop 최우선**: 모든 조건보다 우선하여 CONSOLE 강제

---

## 5. 결정 우선순위 (Fail-Fast)

1. Emergency Stop 확인 → ON이면 CONSOLE 강제
2. Gate 모드 확인 → MOCK/DRY면 CONSOLE
3. Secrets 확인 → 없으면 CONSOLE (Fallback)
4. 모든 조건 통과 → EXTERNAL 가능 (시뮬레이션만)

---

## 6. 콘솔 출력 정책

CONSOLE로 결정된 메시지는:
1. `reports/ops/push/console_out_latest.json`에 내용 기록
2. 터미널/로그에 출력 (선택)
3. 외부 발송 **절대 금지**

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-04 | 초기 버전 (Phase C-P.18) |
