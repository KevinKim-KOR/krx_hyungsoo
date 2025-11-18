# 포트 아키텍처 및 서버 구조

**작성일**: 2025-11-18  
**목적**: 프로젝트 내 모든 서버와 포트를 명확히 정리

---

## 📋 포트 할당 현황

| 포트 | 서버 | 용도 | 환경 | 상태 |
|-----|------|------|------|------|
| **3000** | Vite Dev Server | React 대시보드 (개발) | PC | ✅ 활성 |
| **8000** | FastAPI (backend) | REST API (Phase 5-1~4) | PC/Cloud | ⚠️ 미사용 |
| **8899** | FastAPI (web) | 레거시 웹 서버 | NAS | ⚠️ 정리 필요 |

---

## 🏗️ 서버 구조

### 1. **React 대시보드** (신규, Phase 5-5)

**위치**: `web/dashboard/`  
**포트**: 3000  
**환경**: PC (개발)  
**실행**:
```bash
cd web/dashboard
npm run dev
```

**용도**:
- UI/UX 통합 대시보드
- 포트폴리오 최적화 결과 시각화
- 백테스트 비교
- ML 모델 Feature Importance
- 룩백 분석 결과

**API 프록시**:
```typescript
// vite.config.ts
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://localhost:8000',  // FastAPI 백엔드
      changeOrigin: true,
    },
  },
}
```

---

### 2. **FastAPI 백엔드** (Phase 5-1~4)

**위치**: `backend/app/main.py`  
**포트**: 8000  
**환경**: PC/Cloud  
**실행**:
```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**API 엔드포인트**:
```
GET  /api/v1/dashboard       # 대시보드 요약
GET  /api/v1/assets          # 자산 목록
GET  /api/v1/backtest        # 백테스트 결과
GET  /api/v1/stop-loss       # 손절 정보
GET  /api/v1/signals         # 매매 신호
GET  /api/v1/market          # 시장 정보
```

**용도**:
- Phase 5-1: NAS ↔ Oracle 데이터 동기화
- Phase 5-2: ML 모델 결과 제공
- Phase 5-3: 포트폴리오 최적화 결과
- Phase 5-4: 룩백 분석 결과

**현재 상태**: ⚠️ **미사용** (React 대시보드가 정적 데이터 사용 중)

---

### 3. **레거시 웹 서버** (정리 대상)

**위치**: `web/main.py`  
**포트**: 8899 (NAS), 가변 (PC)  
**환경**: NAS  
**실행**:
```bash
# NAS
./scripts/linux/jobs/run_web.sh start

# PC (포트 가변)
python -m uvicorn web.main:app --host 0.0.0.0 --port 8899
```

**용도**:
- 레거시 백테스트 히스토리
- EOD 리포트 트리거
- 간단한 홈 대시보드

**현재 상태**: ⚠️ **정리 필요** (React 대시보드로 대체 예정)

---

## 🎯 권장 아키텍처

### PC 개발 환경

```
┌─────────────────────────────────────────┐
│  React Dashboard (Port 3000)            │
│  - UI/UX                                │
│  - 차트 시각화                           │
│  - 사용자 인터랙션                       │
└──────────────┬──────────────────────────┘
               │ HTTP Proxy
               ↓
┌─────────────────────────────────────────┐
│  FastAPI Backend (Port 8000)            │
│  - REST API                             │
│  - 데이터 제공                           │
│  - 비즈니스 로직                         │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│  Data Layer                             │
│  - SQLite DB                            │
│  - Parquet 캐시                         │
│  - JSON 결과 파일                        │
└─────────────────────────────────────────┘
```

### NAS 운영 환경

```
┌─────────────────────────────────────────┐
│  FastAPI Web (Port 8899)                │
│  - 간단한 모니터링                       │
│  - EOD 리포트 트리거                     │
│  - 헬스 체크                             │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│  Batch Jobs (Cron)                      │
│  - 데이터 수집                           │
│  - 스캐너 실행                           │
│  - 텔레그램 알림                         │
└─────────────────────────────────────────┘
```

---

## 🔧 정리 계획

### Phase 1: 포트 표준화 ✅

**완료**:
- React 대시보드: 3000 (고정)
- FastAPI 백엔드: 8000 (고정)
- 레거시 웹: 8899 (NAS 전용)

### Phase 2: 서버 통합 (예정)

**목표**: 레거시 웹 서버 기능을 React + FastAPI로 이전

**작업**:
1. **백테스트 히스토리** → React 페이지로 이전
2. **EOD 리포트 트리거** → FastAPI 엔드포인트로 이전
3. **홈 대시보드** → React 대시보드로 대체
4. `web/main.py` 제거 또는 최소화

### Phase 3: API 연동 (다음 작업)

**목표**: React 대시보드와 FastAPI 백엔드 연결

**작업**:
1. FastAPI 서버 실행
2. API 클라이언트 작성 (`src/api/client.ts`)
3. 정적 데이터를 API 호출로 교체
4. 로딩/에러 상태 처리

---

## 📝 포트 충돌 해결

### 문제: 실행할 때마다 포트가 달라짐

**원인**:
- 여러 서버가 동시에 실행 중
- 포트가 명시적으로 지정되지 않음

**해결**:

#### 1. 실행 중인 서버 확인

**Windows (PowerShell)**:
```powershell
# 포트 사용 확인
netstat -ano | findstr :3000
netstat -ano | findstr :8000
netstat -ano | findstr :8899

# 프로세스 종료
taskkill /PID <PID> /F
```

**Linux/NAS**:
```bash
# 포트 사용 확인
netstat -ltnp | grep :8899

# 프로세스 종료
kill <PID>
```

#### 2. 서버 실행 순서

**PC 개발 환경**:
```bash
# 1. FastAPI 백엔드 (선택적)
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 2. React 대시보드
cd web/dashboard
npm run dev
```

**NAS 운영 환경**:
```bash
# 레거시 웹 서버
./scripts/linux/jobs/run_web.sh start
```

#### 3. 포트 고정 설정

**Vite (React)**:
```typescript
// web/dashboard/vite.config.ts
export default defineConfig({
  server: {
    port: 3000,  // 고정
    strictPort: true,  // 포트 충돌 시 에러
  },
})
```

**FastAPI**:
```python
# backend/app/main.py
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,  # 고정
        reload=True
    )
```

---

## 🌐 환경별 구분

### PC (개발)

**용도**: 개발, 테스트, 백테스트, 분석

**서버**:
- React 대시보드 (3000) ✅
- FastAPI 백엔드 (8000) - 필요 시

**특징**:
- 빠른 개발 사이클
- Hot reload
- 전체 기능 사용 가능

### Cloud (Oracle)

**용도**: 데이터 저장, API 제공 (예정)

**서버**:
- FastAPI 백엔드 (8000) - 예정

**특징**:
- NAS 데이터 동기화
- 외부 접근 가능
- 프로덕션 배포

### NAS (운영)

**용도**: 자동화, 배치 작업, 알림

**서버**:
- 레거시 웹 (8899)

**특징**:
- 경량 환경
- Cron 기반 자동화
- 텔레그램 알림

---

## 🚀 다음 단계

### 즉시 진행 가능

1. **포트 충돌 해결**:
   ```bash
   # 실행 중인 서버 확인
   netstat -ano | findstr :3000
   netstat -ano | findstr :8000
   
   # 필요 시 종료
   taskkill /PID <PID> /F
   ```

2. **React 대시보드만 실행** (현재):
   ```bash
   cd web/dashboard
   npm run dev
   ```

### Phase 5-5 완성

1. **FastAPI 백엔드 실행**:
   ```bash
   cd backend
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **API 연동**:
   - API 클라이언트 작성
   - 정적 데이터 → API 호출
   - 로딩/에러 처리

3. **차트 추가**:
   - Recharts 설치
   - 시각화 구현

### 레거시 정리

1. **기능 이전**:
   - 백테스트 히스토리 → React
   - EOD 리포트 → FastAPI

2. **서버 통합**:
   - `web/main.py` 최소화
   - 포트 8899 해제

---

## 📊 요약

### 현재 상태

| 항목 | 상태 | 비고 |
|-----|------|------|
| React 대시보드 (3000) | ✅ 실행 중 | Phase 5-5 |
| FastAPI 백엔드 (8000) | ⚠️ 미사용 | API 연동 필요 |
| 레거시 웹 (8899) | ⚠️ 정리 필요 | 기능 이전 후 제거 |

### 권장 사항

**PC 개발**:
- React 대시보드만 실행 (현재)
- API 연동 시 FastAPI 추가

**NAS 운영**:
- 레거시 웹 유지 (당분간)
- 기능 이전 후 제거

**Cloud**:
- FastAPI 배포 (예정)
- 외부 접근 설정

---

**작성**: Cascade AI Assistant  
**최종 수정**: 2025-11-18
