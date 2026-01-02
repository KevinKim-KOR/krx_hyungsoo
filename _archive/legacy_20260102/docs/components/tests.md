# Tests Module (`tests/`)

**Last Updated**: 2026-01-01
**Purpose**: 유닛 테스트 및 통합 테스트 모음

---

## 📊 Test File Usage Summary

| File/Folder | Status | Description |
|-------------|--------|-------------|
| `test_indicators.py` | ✅ **ACTIVE** | 지표 함수 테스트 |
| `test_backtest_metrics.py` | ✅ **ACTIVE** | 백테스트 메트릭 테스트 |
| `test_scanner_filters.py` | ✅ **ACTIVE** | 스캐너 필터 테스트 |
| `test_config_loader.py` | ✅ **ACTIVE** | 설정 로더 테스트 |
| `test_market_data.py` | ✅ **ACTIVE** | 마켓 데이터 테스트 |
| `test_holiday_rules.py` | ⚠️ **LOW** | 휴일 규칙 테스트 |
| `integration/` | ✅ **ACTIVE** | 통합 테스트 (5 files) |
| `market_data/` | ✅ **ACTIVE** | 마켓 데이터 테스트 (3 files) |
| `tuning/` | ✅ **ACTIVE** | 튜닝 테스트 (13 files) |

---

## 📁 Folder Structure
```
tests/
├── integration/     # 통합 테스트 - ✅ ACTIVE
├── market_data/     # 마켓 데이터 테스트 - ✅ ACTIVE
├── tuning/          # 튜닝 테스트 - ✅ ACTIVE
└── (Root Tests)     # 유닛 테스트 - ✅ ACTIVE
```

---

## 📄 Root Test Files

| File | Status | Description |
|------|--------|-------------|
| `test_backtest_metrics.py` | ✅ | 백테스트 지표 테스트 |
| `test_config_loader.py` | ✅ | 설정 로더 테스트 |
| `test_holiday_rules.py` | ⚠️ | 휴일 규칙 테스트 |
| `test_indicators.py` | ✅ | 기술적 지표 테스트 |
| `test_market_data.py` | ✅ | 마켓 데이터 테스트 |
| `test_scanner_filters.py` | ✅ | 스캐너 필터 테스트 |

---

## 🚀 테스트 실행

```bash
# 전체 테스트
pytest tests/

# 특정 테스트
pytest tests/test_indicators.py -v

# 커버리지 포함
pytest --cov=core tests/
```

---

## 🧹 정리 권장 사항
1. `test_holiday_rules.py`: 실행 확인 후 유지/삭제 결정
