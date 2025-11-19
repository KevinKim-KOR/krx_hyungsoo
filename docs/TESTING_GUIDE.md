# Phase 5-5 테스트 가이드

**작성일**: 2025-11-19  
**목적**: React 대시보드 테스트 및 검증

---

## 📋 목차

1. [서버 실행](#서버-실행)
2. [접속 방법](#접속-방법)
3. [기능 테스트](#기능-테스트)
4. [오류 확인](#오류-확인)
5. [오라클 클라우드 배포](#오라클-클라우드-배포)

---

## 서버 실행

### 1. FastAPI 서버 실행 (포트 8000)

**터미널 1**:
```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**확인**:
- 브라우저: http://localhost:8000/api/docs
- 상태: `INFO: Application startup complete`

---

### 2. React 서버 실행 (포트 3000)

**터미널 2**:
```bash
cd web/dashboard
npm run dev
```

**확인**:
- 브라우저: http://localhost:3000
- 상태: `VITE v5.4.21 ready in XXX ms`

---

## 접속 방법

### ✅ 올바른 접속

**React 대시보드**:
- URL: http://localhost:3000
- 브라우저에서 직접 접속

**FastAPI 문서**:
- URL: http://localhost:8000/api/docs
- API 테스트용

### ❌ 잘못된 접속

- http://127.0.0.1:50239 → FastAPI 프리뷰 (대시보드 아님)
- http://localhost:8000 → FastAPI 루트 (대시보드 아님)

---

## 기능 테스트

### 1. Dashboard 페이지 테스트

**접속**: http://localhost:3000

**확인 사항**:
- [ ] 요약 카드 4개 표시 (포트폴리오 가치, Sharpe, 변동성, 기대 수익률)
- [ ] 최근 분석 결과 표시
- [ ] 로딩 스피너 표시 후 데이터 로드

**예상 결과**:
```
총 포트폴리오 가치: ₩10,000,000 (+5.2%)
Sharpe Ratio: 1.49
변동성: 18.1%
기대 수익률: 29.9%
```

**오류 발생 시**:
- FastAPI 서버가 실행 중인지 확인
- 브라우저 콘솔(F12) 확인
- 에러 메시지: "FastAPI 서버가 실행 중인지 확인하세요 (포트 8000)"

---

### 2. Portfolio 페이지 테스트

**접속**: http://localhost:3000/portfolio

**확인 사항**:
- [ ] 최적 비중 표시 (종목별 %)
- [ ] 성과 지표 3개 (기대 수익률, 변동성, Sharpe)
- [ ] 이산 배분 표시 (있는 경우)
- [ ] "최적화 실행" 버튼 표시

**실행 테스트**:
1. "최적화 실행" 버튼 클릭
2. 로딩 스피너 확인 ("실행 중...")
3. 5분 이내 완료 대기
4. 페이지 자동 새로고침
5. 새로운 결과 확인

**예상 결과**:
```
data/output/optimization/optimal_portfolio_YYYYMMDD_HHMMSS.json 생성
```

**오류 발생 시**:
- 스크립트 경로 확인: `pc/optimization/run_optimization.py`
- Python 환경 확인
- 터미널에서 수동 실행:
  ```bash
  python pc/optimization/run_optimization.py --method max_sharpe --capital 10000000
  ```

---

### 3. MLModel 페이지 테스트

**접속**: http://localhost:3000/ml-model

**확인 사항**:
- [ ] 학습 결과 3개 (Train R², Test R², 특징 개수)
- [ ] Feature Importance 바 차트
- [ ] 과적합 경고 (Test R² < 0인 경우)
- [ ] "모델 학습" 버튼 표시

**실행 테스트**:
1. "모델 학습" 버튼 클릭
2. 로딩 스피너 확인 ("학습 중...")
3. 15분 이내 완료 대기
4. 페이지 자동 새로고침
5. 새로운 결과 확인

**예상 결과**:
```
data/output/ml/meta_YYYYMMDD_HHMMSS.json 생성
data/output/ml/model_YYYYMMDD_HHMMSS.pkl 생성
```

**오류 발생 시**:
- 스크립트 경로 확인: `pc/ml/train_model.py`
- 데이터 확인: OHLCV 데이터가 충분한지
- 터미널에서 수동 실행:
  ```bash
  python pc/ml/train_model.py --model-type xgboost --task regression
  ```

---

### 4. Lookback 페이지 테스트

**접속**: http://localhost:3000/lookback

**확인 사항**:
- [ ] 요약 통계 4개 (리밸런싱 횟수, 평균 수익률, 평균 Sharpe, 승률)
- [ ] 리밸런싱 결과 테이블
- [ ] "분석 실행" 버튼 표시

**실행 테스트**:
1. "분석 실행" 버튼 클릭
2. 로딩 스피너 확인 ("분석 중...")
3. 10분 이내 완료 대기
4. 페이지 자동 새로고침
5. 새로운 결과 확인

**예상 결과**:
```
data/output/analysis/lookback_analysis_YYYYMMDD_HHMMSS.json 생성
```

**오류 발생 시**:
- 스크립트 경로 확인: `pc/analysis/lookback_analysis.py`
- 터미널에서 수동 실행:
  ```bash
  python pc/analysis/lookback_analysis.py --method portfolio_optimization --lookback-days 120 --rebalance-frequency 30
  ```

---

## 오류 확인

### 1. 브라우저 콘솔 확인

**Chrome/Edge**:
1. F12 키 누르기
2. Console 탭 선택
3. 빨간색 에러 메시지 확인

**일반적인 에러**:
```
Failed to fetch
→ FastAPI 서버가 실행되지 않음

CORS error
→ CORS 설정 확인 (이미 설정됨)

404 Not Found
→ API 엔드포인트 경로 확인
```

---

### 2. FastAPI 로그 확인

**터미널 1 (FastAPI)**:
```
INFO:     127.0.0.1:XXXXX - "GET /api/v1/dashboard/summary HTTP/1.1" 200 OK
INFO:     127.0.0.1:XXXXX - "POST /api/v1/portfolio/optimize HTTP/1.1" 200 OK
```

**에러 발생 시**:
```
ERROR:    Exception in ASGI application
→ Python 스크립트 실행 오류
→ 로그에서 상세 에러 확인
```

---

### 3. React 로그 확인

**터미널 2 (React)**:
```
[vite] page reload src/pages/Dashboard.tsx
→ 정상 (파일 변경 시 자동 reload)

[vite] hmr update /src/pages/Dashboard.tsx
→ 정상 (Hot Module Replacement)
```

---

## 오라클 클라우드 배포

### 현재 상태

**PC 전용**:
- React 개발 서버 (포트 3000)
- FastAPI 개발 서버 (포트 8000)
- 로컬에서만 접근 가능

**오라클 클라우드 배포는 선택 사항**입니다.

---

### 배포가 필요한 경우

**1. 외부 접근이 필요한 경우**:
- 다른 PC/모바일에서 접속
- 팀원과 공유
- 24시간 운영

**2. 배포 방법**:

#### Option 1: React 빌드 + FastAPI 프로덕션

```bash
# 1. React 빌드
cd web/dashboard
npm run build

# 2. FastAPI에서 빌드된 파일 서빙
# backend/app/main.py에 이미 설정됨
app.mount("/static", StaticFiles(directory="../../web/dashboard/dist"), name="static")

# 3. FastAPI만 실행
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### Option 2: Nginx + FastAPI

```nginx
# Nginx 설정
server {
    listen 80;
    
    # React 정적 파일
    location / {
        root /path/to/web/dashboard/dist;
        try_files $uri $uri/ /index.html;
    }
    
    # FastAPI 프록시
    location /api {
        proxy_pass http://localhost:8000;
    }
}
```

---

### 배포하지 않아도 되는 경우

**PC에서만 사용**:
- 로컬 개발 및 테스트
- 개인 분석 도구
- 빠른 프로토타이핑

**현재 권장**: 배포하지 않고 PC에서만 사용

**이유**:
1. 개발 단계 (아직 완성 전)
2. 데이터가 로컬에만 존재
3. 보안 설정 필요 (인증, HTTPS 등)

---

## 테스트 체크리스트

### 기본 기능

- [ ] FastAPI 서버 실행 (포트 8000)
- [ ] React 서버 실행 (포트 3000)
- [ ] Dashboard 페이지 접속
- [ ] Portfolio 페이지 접속
- [ ] MLModel 페이지 접속
- [ ] Lookback 페이지 접속

### 데이터 로딩

- [ ] Dashboard 요약 카드 표시
- [ ] Portfolio 최적 비중 표시
- [ ] MLModel Feature Importance 표시
- [ ] Lookback 리밸런싱 결과 표시

### 실행 기능

- [ ] Portfolio 최적화 실행
- [ ] MLModel 학습 실행
- [ ] Lookback 분석 실행

### 에러 처리

- [ ] FastAPI 중지 시 에러 메시지 표시
- [ ] 데이터 없을 때 안내 메시지 표시
- [ ] 실행 실패 시 에러 메시지 표시

---

## 문제 해결

### 1. "데이터를 불러오는데 실패했습니다"

**원인**: FastAPI 서버가 실행되지 않음

**해결**:
```bash
# 터미널 1
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

### 2. "포트폴리오 최적화 결과가 없습니다"

**원인**: 아직 최적화를 실행하지 않음

**해결**:
1. "최적화 실행" 버튼 클릭
2. 또는 터미널에서 수동 실행:
   ```bash
   python pc/optimization/run_optimization.py
   ```

---

### 3. "최적화 실행 실패"

**원인**: Python 스크립트 오류

**해결**:
1. 터미널에서 수동 실행하여 에러 확인
2. 데이터 확인 (OHLCV 데이터 존재 여부)
3. 필요한 패키지 설치 확인

---

### 4. 포트 충돌

**증상**: "Port 3000 is already in use"

**해결**:
```powershell
# 포트 사용 프로세스 확인
netstat -ano | findstr :3000

# 프로세스 종료
taskkill /PID <PID> /F
```

---

## 다음 단계

### 테스트 완료 후

1. **정상 작동 확인**:
   - 모든 페이지 접속 가능
   - 데이터 정상 표시
   - 실행 기능 정상 작동

2. **선택 사항**:
   - 차트 추가 (Recharts)
   - Backtest 페이지 추가
   - 실시간 로그 표시

3. **배포 고려**:
   - 외부 접근 필요 시 오라클 클라우드 배포
   - 아니면 PC에서만 사용

---

## 요약

### 현재 상태

| 항목 | 상태 | 비고 |
|-----|------|------|
| React 서버 | ✅ 실행 중 | 포트 3000 |
| FastAPI 서버 | ✅ 실행 중 | 포트 8000 |
| Dashboard | ✅ 작동 | API 연동 |
| Portfolio | ✅ 작동 | 실행 기능 포함 |
| MLModel | ✅ 작동 | 실행 기능 포함 |
| Lookback | ✅ 작동 | 실행 기능 포함 |

### 접속 정보

- **React 대시보드**: http://localhost:3000
- **FastAPI 문서**: http://localhost:8000/api/docs

### 권장 사항

1. **PC에서만 사용** (현재 단계)
2. **테스트 후 피드백**
3. **필요 시 기능 추가**

---

**작성**: Cascade AI Assistant  
**최종 수정**: 2025-11-19
