# Backend Module (`backend/`)

**Last Updated**: 2026-01-01
**Purpose**: FastAPI 기반 읽기 전용 옵저버 백엔드 (Dashboard API 서버)

---

## 📁 Folder Structure
```
backend/
├── app/            # 모듈화된 API/서비스
│   ├── api/        # API 라우터
│   ├── core/       # 설정
│   ├── models/     # ORM 모델
│   ├── schemas/    # Pydantic 스키마
│   └── services/   # 비즈니스 로직
├── data/           # 백엔드 전용 데이터
├── static/         # 정적 파일
├── tests/          # 테스트
├── main.py         # FastAPI 앱 진입점
└── test_api.py     # API 테스트
```

---

## 📊 API Endpoint Usage

| Endpoint | Status | Used By |
|----------|--------|---------|
| `/api/status` | ✅ **ACTIVE** | dashboard/index.html |
| `/api/portfolio` | ✅ **ACTIVE** | dashboard/index.html |
| `/api/signals` | ✅ **ACTIVE** | dashboard/index.html |
| `/api/history` | ✅ **ACTIVE** | dashboard/index.html |
| `/api/raw` | ⚠️ **DEBUG** | 디버깅 전용 |
| `/api/validation` | ✅ **ACTIVE** | dashboard/index.html |
| `/api/diagnosis/v3` | ✅ **ACTIVE** | dashboard/index.html |
| `/api/gatekeeper/v3` | ✅ **ACTIVE** | dashboard/index.html |
| `/api/report/human` | ✅ **ACTIVE** | dashboard/index.html (Contract 5) |
| `/api/report/ai` | ✅ **ACTIVE** | AI Agent Context |
| `/api/recon/summary` | ✅ **ACTIVE** | dashboard/index.html |
| `/api/recon/daily` | ✅ **ACTIVE** | dashboard/index.html |

---

## 📄 Root Files

### `main.py` (474 lines) - ✅ ACTIVE
**Purpose**: FastAPI 앱 메인 및 모든 API 엔드포인트 정의

#### Utility Functions
| Function | Status | Description |
|----------|--------|-------------|
| `setup_backend_logger()` | ✅ | 로깅 설정 |
| `get_today_str()` | ✅ | 오늘 날짜 문자열 반환 |
| `safe_read_text_advanced(path)` | ✅ | 안전한 텍스트 읽기 |
| `safe_read_text(path)` | ✅ | 단순 텍스트 반환 래퍼 |
| `safe_read_json(path)` | ✅ | JSON 안전 읽기 |
| `safe_read_yaml(path)` | ✅ | YAML 안전 읽기 |

---

### `test_api.py` (3KB) - ✅ ACTIVE
**Purpose**: API 엔드포인트 테스트

---

## 📁 Subdirectories

### `backend/app/` - ⚠️ PARTIALLY USED
모듈화된 FastAPI 구조 (현재 `main.py`가 주로 사용됨)

| Subdir | Status | Description |
|--------|--------|-------------|
| `app/api/` | ⚠️ | API 라우터 (일부만 활성) |
| `app/core/` | ⚠️ | 설정 (부분 사용) |
| `app/models/` | ⚠️ | ORM 모델 (부분 사용) |
| `app/schemas/` | ⚠️ | Pydantic 스키마 (부분 사용) |
| `app/services/` | ⚠️ | 비즈니스 로직 (부분 사용) |

---

## 🔗 Dependencies
- FastAPI, Uvicorn, Starlette
- Pydantic, SQLAlchemy
- 내부: `core.db`, `core.data_loader`

---

## 🚀 실행 방법
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📋 Contract 5 지원
- `/api/report/human`: `REPORT_HUMAN_V1` 스키마 - ✅ ACTIVE
- `/api/report/ai`: `REPORT_AI_V1` 스키마 - ✅ ACTIVE
- 모든 엔드포인트는 Envelope 형식 권장

---

## 🧹 정리 권장 사항
1. ⚠️ `backend/app/` 서브 모듈: `main.py`로 통합 또는 활성화 검토
2. ⚠️ `/api/raw`: 프로덕션에서 비활성화 검토
