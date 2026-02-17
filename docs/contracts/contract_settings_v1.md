# Contract: Unified Settings V1

**Version**: 1.0
**Date**: 2026-01-26
**Status**: DRAFT

---

## 1. 개요

기존 `SPIKE_SETTINGS_V1`을 확장하여, 보유 종목 감시(`holding`) 설정을 포함하는 **통합 설정(Unified Settings)** 스키마를 정의합니다.
UI와 백엔드는 이 단일 파일을 통해 모든 감시/알림 설정을 관리합니다.

> 🔒 **Single Source**: `state/settings/latest/settings_latest.json`

---

## 2. Schema: SETTINGS_V1

```json
{
  "schema": "SETTINGS_V1",
  "updated_at": "2026-01-26T10:00:00",
  "spike": {
    "enabled": true,
    "threshold_pct": 3.0,
    "cooldown_minutes": 15,
    "session_kst": {
        "start": "09:10",
        "end": "15:20"
    },
    "options": {
        "include_value_volume": true,
        "include_deviation": false,
        "include_portfolio_context": true
    }
  },
  "holding": {
    "enabled": true,
    "pnl_up_pct": 5.0,
    "pnl_down_pct": 3.0,
    "use_trail_stop": false,
    "trail_stop_pct": 2.0,
    "cooldown_m": 15,
    "realert_delta_pp": 1.0,
    "session_kst": {
        "start": "09:10",
        "end": "15:20"
    },
    "weekdays": [0, 1, 2, 3, 4],
    "options": {
        "include_trade_value": true,
        "include_deviation": true,
        "include_pnl": true
    }
  }
}
```

---

## 3. 필드 정의

### 3.1 Common
- `schema`: "SETTINGS_V1" 고정
- `updated_at`: 마지막 수정 시각 (ISO8601)

### 3.2 Spike Section
- 기존 `SPIKE_SETTINGS_V1`과 동일 (하위 호환)

### 3.3 Holding Section (New)
- `enabled` (bool): 감시 기능 전체 ON/OFF
- `pnl_up_pct` (float): 수익 알림 임계치 (예: 5.0 -> +5% 이상 시 알림)
- `pnl_down_pct` (float): 손실 알림 임계치 (예: 3.0 -> -3% 이하 시 알림)
- `use_trail_stop` (bool): Trailing Stop 기능 사용 여부
- `trail_stop_pct` (float): 고점 대비 하락 임계치 (예: 2.0 -> 2%p 하락 시 알림)
- `cooldown_m` (int): 기본 재발송 금지 시간 (분)
- `realert_delta_pp` (float): 쿨다운 중이라도 재알림 허용하는 추가 변동폭 (%p)
- `session_kst`: 감시 허용 시간대 (KST)
- `options`: 표시 옵션

---

## 4. 저장소 경로

| 경로 | 용도 | 방식 |
|------|------|------|
| `state/settings/latest/settings_latest.json` | 최신 통합 설정 | Atomic Write |

---

## 5. Migration Guide
- 기존 `SPIKE_SETTINGS_V1` (`state/spike_settings/latest/*`)은 Deprecated 되며, `SETTINGS_V1`으로 마이그레이션 됩니다.
- 백엔드는 기존 API 요청이 들어올 경우 `SETTINGS_V1`의 `spike` 섹션과 매핑하여 처리 가능해야 합니다.

---

## 6. Related API Endpoints (P146.8)

### 6.1 Execution Mode Control
- **GET /api/settings/mode**: 현재 실행 모드 조회 (Live/Replay, AsOf, SimDay)
- **POST /api/settings/mode**: 실행 모드 변경 및 OCI 동기화 (Push via `api/sync`).

