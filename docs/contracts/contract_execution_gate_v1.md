# Contract: Execution Gate V1

**Version**: 1.1 (Replay vs Dry Run)
**Date**: 2026-02-18
**Status**: ACTIVE

---

## 1. 개요

Execution Gate는 **워커의 실행 모드를 제어**하는 게이트웨이입니다.
P146부터 **Data Mode (Replay)**와 **Execution Mode (Gate)**의 개념이 명확히 분리되었습니다.

---

## 2. Mode 개념 분리 (Orthogonal)

### 2.1 Data Mode (Source)
- **LIVE**: 현재 시점의 데이터를 사용. (오늘)
- **REPLAY**: 과거 특정 시점의 데이터를 사용. (Backtest)

### 2.2 Execution Mode (Action)
- **MOCK_ONLY**: 아무것도 하지 않음 (Sleep 1s).
- **DRY_RUN**: 로직 검증만 수행. (실제 주문 전송 차단)
- **REAL_ENABLED**: 실제 주문 전송 허용. (C-P.4 제약 준수)

### 2.3 조합 예시
- **Shadow Mode**: `LIVE` + `DRY_RUN` (실시간 데이터로 로직 검증)
- **Simulation**: `REPLAY` + `DRY_RUN` (과거 데이터로 백테스트)
- **Real Trading**: `LIVE` + `REAL_ENABLED` (실전 매매)

> ⚠️ **REPLAY + REAL_ENABLED** 조합은 논리적으로 불가능하며 차단됩니다.

---

## 3. Schema: EXECUTION_GATE_V1

```json
{
  "schema": "EXECUTION_GATE_V1",
  "mode": "MOCK_ONLY", 
  "updated_at": "2026-02-18T10:00:00+09:00",
  "updated_by": "local_api",
  "reason": "Initial Boot"
}
```

---

## 4. Transition Rules

| From | To | 허용 |
|---|---|---|
| `MOCK_ONLY` | `DRY_RUN` | ✅ |
| `DRY_RUN` | `REAL_ENABLED` | ❌ **API Blocked** (Manual Approval via File Only) |
| Any | `MOCK_ONLY` | ✅ (Emergency Stop) |

> **Real Enable**: `REAL_ENABLED` 모드는 API로 설정할 수 없으며, **파일 기반 2단계 인증**(Two-Key Approval)을 통해서만 진입 가능합니다.
