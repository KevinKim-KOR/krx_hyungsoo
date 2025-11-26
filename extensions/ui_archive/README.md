# UI Archive

**상태**: 보관 (사용 안함)  
**이유**: React UI로 완전 대체됨  
**날짜**: 2025-11-26

---

## 📁 보관된 UI

### Streamlit UI
**경로**: `extensions/ui_archive/streamlit/`  
**상태**: 사용 안함  
**대체**: React UI (`web/dashboard/`)

**보관 이유**:
- React UI로 완전 대체됨
- 더 나은 UX/UI
- FastAPI 백엔드와 완벽 통합
- 파라미터 히스토리 관리 기능
- 히스토리 비교 기능

**복원 방법** (필요 시):
```bash
# Git 이력에서 복원
git log --all --full-history -- extensions/ui/

# 특정 커밋으로 복원
git checkout <commit-hash> -- extensions/ui/
```

---

## 🚀 현재 사용 중인 UI

### React Dashboard
**경로**: `web/dashboard/`  
**상태**: ✅ 사용 중  
**기술 스택**: React + TypeScript + Vite + TailwindCSS

**주요 기능**:
1. **Dashboard**: 포트폴리오 현황, 성과 지표
2. **Portfolio**: 보유 종목, 평가액, 수익률
3. **Holdings**: 매도 신호, 손익률
4. **Backtest**: 백테스트 실행, 파라미터 설정, 히스토리
5. **ML Model**: ML 모델 파라미터 설정, 히스토리
6. **Lookback**: 룩백 분석 파라미터 설정, 히스토리

**실행 방법**:
```bash
# 백엔드
cd backend
uvicorn app.main:app --reload

# 프론트엔드
cd web/dashboard
npm run dev
```

**접속**:
- 프론트엔드: http://localhost:5173
- 백엔드 API: http://localhost:8000
- API 문서: http://localhost:8000/docs

---

## 📊 비교

| 항목 | Streamlit UI | React UI |
|------|-------------|----------|
| 기술 스택 | Python Streamlit | React + TypeScript |
| 성능 | 느림 (Python) | 빠름 (JavaScript) |
| UX/UI | 기본적 | 현대적 |
| 커스터마이징 | 제한적 | 자유로움 |
| 백엔드 통합 | 직접 호출 | REST API |
| 파라미터 히스토리 | 기본 | 고급 (비교 기능) |
| 히스토리 비교 | 없음 | ✅ 있음 |
| 상태 | 보관 | ✅ 사용 중 |

---

## 🗂️ 파일 구조

### Streamlit UI (보관)
```
extensions/ui_archive/streamlit/
├── app.py                      # 메인 앱
├── dashboard.py                # 대시보드
├── backtest_database.py        # 백테스트 DB
├── components/
│   └── parameter_presets.py    # 파라미터 프리셋
├── pages/
│   ├── 1_📊_Dashboard.py
│   ├── 2_⚙️_Parameters.py
│   ├── 3_🔬_Backtest.py
│   ├── 4_📈_Signals.py
│   └── 5_🔍_Compare.py
└── README.md
```

### React UI (사용 중)
```
web/dashboard/
├── src/
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── Portfolio.tsx
│   │   ├── Holdings.tsx
│   │   ├── Backtest.tsx
│   │   ├── MLModel.tsx
│   │   └── Lookback.tsx
│   ├── components/
│   ├── api/
│   └── App.tsx
├── package.json
└── vite.config.ts
```

---

## 📝 변경 이력

### 2025-11-26
- Streamlit UI를 `extensions/ui_archive/streamlit/`로 이동
- React UI로 완전 대체
- 이 README 작성

### 2025-11-24
- React UI 완전 구현
- 파라미터 히스토리 관리 기능 추가
- 히스토리 비교 기능 추가

### 2025-11-10
- Streamlit UI 개발 완료
- 4개 페이지 구현
- 파라미터 프리셋 추가

---

**보관 완료**: 2025-11-26  
**다음 확인**: 필요 시 Git 이력에서 복원
