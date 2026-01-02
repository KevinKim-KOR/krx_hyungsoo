# App Module (`app/`)

**Last Updated**: 2026-01-01
**Purpose**: CLI 및 API 진입점 모듈

---

## 📊 Usage Summary

| Component | Status | Used By |
|-----------|--------|---------|
| `app.cli.alerts` | ✅ **ACTIVE** | deploy/run_daily.sh, deploy/run_daily.ps1, pyproject.toml |
| `app.api` | ⚠️ **LOW** | 부분적 사용 |
| `app.services` | ⚠️ **LOW** | 부분적 사용 |

---

## 📁 Folder Structure
```
app/
├── api/        # REST API 라우터 (2 files) - ⚠️ LOW
├── cli/        # CLI 명령어 (4 files) - ✅ ACTIVE
└── services/   # 공통 서비스 (7 files) - ⚠️ LOW
```

---

## 📁 Subdirectories

### `app/cli/` - ✅ ACTIVE
CLI 명령어 모듈

| File | Status | Description |
|------|--------|-------------|
| `alerts.py` | ✅ | 전략 스캐너 및 알림 CLI (**배포 스크립트에서 사용**) |
| `runner.py` | ⚠️ | 일일 실행기 (사용 빈도 확인 필요) |
| `main.py` | ⚠️ | CLI 진입점 (사용 빈도 확인 필요) |

### `app/api/` - ⚠️ LOW USAGE
REST API 라우터 (FastAPI) - `backend/main.py`가 주로 사용됨

### `app/services/` - ⚠️ LOW USAGE
공통 비즈니스 로직 서비스

---

## 🚀 주요 CLI 명령

```bash
# Phase 9 스캔 (V2 Config) - ✅ ACTIVE
python -m app.cli.alerts scan --strategy phase9 --config config/production_config_v2.py

# 알림 전송 - ✅ ACTIVE
python -m app.cli.alerts notify --signal-file reports/signals_20260101.yaml
```

---

## 🧹 정리 권장 사항
1. ⚠️ `app/api/`: `backend/` 모듈과 통합 검토
2. ⚠️ `app/services/`: 사용 여부 확인 후 정리
