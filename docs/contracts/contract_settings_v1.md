# Contract: Unified Settings V1

**Version**: 1.1 (Added System Mode)
**Date**: 2026-02-18
**Status**: ACTIVE

---

## 1. 개요

시스템의 모든 설정(감시, 매매, 운영 모드)을 정의하는 통합 스키마입니다.
P146부터 **System Mode Settings**가 추가되어 Replay/Simulation 상태도 관리합니다.

---

## 2. Schema: SETTINGS_V1

```json
{
  "schema": "SETTINGS_V1",
  "updated_at": "2026-02-18T10:00:00",
  "system_mode": {
    "execution_mode": "REAL_ENABLED", 
    "replay_date": null, 
    "sim_trade_day": null 
  },
  "spike": {
    "enabled": true,
    "threshold_pct": 3.0,
    "cooldown_minutes": 15
  },
  "holding": {
    "enabled": true,
    "pnl_up_pct": 5.0,
    "pnl_down_pct": 3.0
  }
}
```

---

## 3. 필드 정의

### 3.1 System Mode Settings (New)
UI 상단 "Mode Control" 패널과 연동됩니다.

| 필드 | 설명 | 값 |
|---|---|---|
| `execution_mode` | 실행 권한 | `MOCK_ONLY` / `DRY_RUN` / `REAL_ENABLED` |
| `replay_date` | 과거 시점 조회 | `YYYY-MM-DD` (NULL이면 현재 시점) |
| `sim_trade_day` | 전략 시뮬레이션 날짜 | `YYYY-MM-DD` (NULL이면 오늘) |

### 3.2 Spike / Holding
(기존 V1.0 정의와 동일)

---

## 4. 저장소 경로

| 경로 | 용도 | 방식 |
|---|---|---|
| `state/settings/latest/settings_latest.json` | 최신 통합 설정 | Atomic Write |
