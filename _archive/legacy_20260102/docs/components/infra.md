# Infra Module (`infra/`)

**Last Updated**: 2026-01-01
**Purpose**: 인프라 레이어 (데이터 로더, 알림, 로깅, 스토리지)

---

## 📊 Folder Usage Summary

| Subdir | Status | Used By |
|--------|--------|---------|
| `infra/data/` | ✅ **ACTIVE** | Phase9Executor, 백테스트 |
| `infra/notify/` | ✅ **ACTIVE** | CLI, 스크립트 |
| `infra/logging/` | ⚠️ **LOW** | 부분 사용 |
| `infra/storage/` | ⚠️ **LOW** | 부분 사용 |
| `infra/config/` | ⚠️ **LOW** | 부분 사용 |

---

## 📁 Folder Structure
```
infra/
├── config/     # 인프라 설정 - ⚠️ LOW
├── data/       # 데이터 로더 - ✅ ACTIVE
├── logging/    # 로깅 설정 - ⚠️ LOW
├── notify/     # 알림 - ✅ ACTIVE
└── storage/    # 파일 스토리지 - ⚠️ LOW
```

---

## 📁 Subdirectories

### `infra/data/` - ✅ ACTIVE
데이터 로딩 인프라

| File | Status | Description |
|------|--------|-------------|
| `loader.py` | ✅ | `load_price_data()` - Phase9Executor에서 사용 |

### `infra/notify/` - ✅ ACTIVE
알림 시스템

| File | Status | Description |
|------|--------|-------------|
| `telegram.py` | ✅ | Telegram 알림 전송 |
| `slack.py` | 🔶 | Slack 알림 전송 (레거시) |

### `infra/logging/` - ⚠️ LOW USAGE
로깅 설정 유틸

### `infra/storage/` - ⚠️ LOW USAGE
파일 스토리지 유틸

| File | Status | Description |
|------|--------|-------------|
| `sqlite.py` | ⚠️ | SQLite 스토리지 (사용 확인 필요) |

---

## 🔗 Usage Example
```python
from infra.data.loader import load_price_data
from infra.notify.telegram import send_alerts

# 가격 데이터 로드
prices = load_price_data(["005930", "000660"], start_date, end_date)

# 알림 전송
send_alerts(signals, template="default_v1")
```

---

## 🧹 정리 권장 사항
1. 🔶 `infra/notify/slack.py`: 삭제 또는 Telegram으로 통합 검토
2. ⚠️ `infra/logging/`, `infra/storage/`: 사용 여부 확인
