# Extensions Module (`extensions/`)

**Last Updated**: 2026-01-01
**Purpose**: 확장 기능 모듈 (자동화, 백테스트, 모니터링, 알림, 튜닝 등)

---

## 📊 Usage Summary

| Subdir | Status | Used By |
|--------|--------|---------|
| `extensions/automation/` | ✅ **ACTIVE** | scripts, tools (regime_monitor 등) |
| `extensions/backtest/` | ✅ **ACTIVE** | tests, tools (runner.py) |
| `extensions/optuna/` | ✅ **ACTIVE** | tests, scripts (objective, walk_forward) |
| `extensions/tuning/` | ✅ **ACTIVE** | tests (12+ test files) |
| `extensions/monitoring/` | ⚠️ **LOW** | 사용 빈도 낮음 |
| `extensions/notification/` | ⚠️ **LOW** | 사용 빈도 낮음 |
| `extensions/realtime/` | ⚠️ **LOW** | 사용 빈도 낮음 |
| `extensions/strategy/` | ⚠️ **LOW** | 사용 빈도 낮음 |
| `extensions/ui_archive/` | ❌ **DEPRECATED** | 아카이브됨 |

---

## 📁 Folder Structure
```
extensions/
├── analysis/       # 분석 도구
├── automation/     # 자동화 - ✅ ACTIVE
├── backtest/       # 백테스트 확장 - ✅ ACTIVE
├── monitoring/     # 모니터링 - ⚠️ LOW
├── notification/   # 알림 확장 - ⚠️ LOW
├── optuna/         # Optuna 튜닝 - ✅ ACTIVE
├── realtime/       # 실시간 처리 - ⚠️ LOW
├── scheduler/      # 스케줄러
├── strategy/       # 전략 확장 - ⚠️ LOW
├── tuning/         # 파라미터 튜닝 - ✅ ACTIVE
└── ui_archive/     # UI 아카이브 - ❌ DEPRECATED
```

---

## 📁 주요 Subdirectories

### `extensions/automation/` - ✅ ACTIVE
자동화 모듈 (50+ files에서 import)

| File | Status | Description |
|------|--------|-------------|
| `regime_monitor.py` | ✅ | Market Regime 모니터링 |
| `daily_report.py` | ✅ | 일일 리포트 생성 |
| `portfolio_loader.py` | ✅ | 포트폴리오 로더 |
| `price_updater.py` | ✅ | 가격 업데이터 |

### `extensions/backtest/` - ✅ ACTIVE
백테스트 확장 기능

| File | Status | Description |
|------|--------|-------------|
| `runner.py` | ✅ | 백테스트 러너 (tests에서 사용) |

### `extensions/optuna/` - ✅ ACTIVE
Optuna 기반 하이퍼파라미터 튜닝

| File | Status | Description |
|------|--------|-------------|
| `objective.py` | ✅ | 최적화 목적 함수 |
| `robustness.py` | ✅ | 강건성 검증 |
| `walk_forward.py` | ✅ | Walk-Forward 검증 |

### `extensions/tuning/` - ✅ ACTIVE
전략 파라미터 튜닝 도구 (12+ test files에서 사용)

### `extensions/notification/` - ⚠️ LOW USAGE
알림 채널 확장 - `infra/notify/` 사용 권장

### `extensions/monitoring/` - ⚠️ LOW USAGE
시스템 모니터링 도구

### `extensions/ui_archive/` - ❌ DEPRECATED
이전 UI 코드 아카이브 (삭제 검토)

---

## 🔗 Usage Example
```python
from extensions.automation.regime_monitor import RegimeMonitor
from extensions.backtest.runner import run_backtest
from extensions.optuna.objective import create_objective

monitor = RegimeMonitor()
regime_info = monitor.analyze_daily_regime(target_date)
```

---

## 🧹 정리 권장 사항
1. ❌ `extensions/ui_archive/`: 삭제 검토 (14 files)
2. ⚠️ `extensions/notification/`: `infra/notify/`로 마이그레이션
3. ⚠️ `extensions/realtime/`: 사용 여부 확인 후 정리
4. ⚠️ `extensions/strategy/`: 사용 여부 확인 후 정리
