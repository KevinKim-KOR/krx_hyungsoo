# 다음 단계 작업 계획 (2025-11-25 이후)

**작성일**: 2025-11-25  
**상태**: 계획 수립 완료

---

## 🎯 목표

핵심 기능 완성 후 **고도화 및 정리** 단계

---

## 📋 작업 항목 (우선순위 순)

### 1. 미국 시장 지표 레짐 분석 개선 🇺🇸
**우선순위**: 높음  
**예상 시간**: 4-6시간

#### 현재 상태
- ⚠️ `core/strategy/us_market_monitor.py`에서 일부 지표 조회 실패
- ⚠️ Daily Regime Check에서 미국 레짐 표시 안됨
- ✅ 한국 시장 레짐은 정상 작동

#### 문제점
```python
# 현재 오류 발생 지표
- VIX (변동성 지수)
- DXY (달러 인덱스)
- TNX (10년물 국채 수익률)
```

#### 해결 방안

**Option 1: 데이터 소스 변경** (권장)
```python
# yfinance 대신 다른 소스 사용
- Alpha Vantage API (무료 500 calls/day)
- FRED API (연준 경제 데이터)
- Yahoo Finance 심볼 수정
```

**Option 2: 심볼 수정**
```python
# 현재
VIX_SYMBOL = "^VIX"
DXY_SYMBOL = "DX-Y.NYB"
TNX_SYMBOL = "^TNX"

# 수정 후
VIX_SYMBOL = "^VIX"  # 유지
DXY_SYMBOL = "UUP"   # ETF로 대체
TNX_SYMBOL = "^TNX"  # 유지
```

**Option 3: 필수 지표만 사용**
```python
# 최소 필수 지표
- S&P 500 (^GSPC) - 미국 주식 시장
- NASDAQ (^IXIC) - 기술주 시장
- VIX (^VIX) - 변동성

# 선택 지표 (실패 시 무시)
- DXY, TNX, 기타
```

#### 작업 단계
1. **진단** (1시간)
   - 현재 오류 로그 분석
   - 각 지표별 조회 테스트
   - 실패 원인 파악

2. **데이터 소스 조사** (1-2시간)
   - Alpha Vantage API 테스트
   - FRED API 테스트
   - 대체 심볼 테스트

3. **구현** (2-3시간)
   - `us_market_monitor.py` 수정
   - 폴백 로직 추가
   - 오류 처리 개선

4. **테스트** (1시간)
   - 로컬 테스트
   - Oracle Cloud 테스트
   - 텔레그램 알림 확인

#### 파일 수정
```
core/strategy/us_market_monitor.py
- get_market_data() 수정
- 데이터 소스 추가/변경
- 오류 처리 개선

config/us_market_indicators.yaml (필요 시)
- API 키 설정
- 심볼 매핑
```

---

### 2. Streamlit UI 정리 🗑️
**우선순위**: 중간  
**예상 시간**: 1-2시간

#### 현재 상태
- 📁 `extensions/ui/` 디렉토리에 Streamlit UI 존재
- 🚫 React UI로 완전 대체됨
- ⚠️ 혼란 가능성 있음

#### 작업 내용

**Option 1: Archive로 이동** (권장)
```bash
# 디렉토리 구조
extensions/
├── ui/                    # 삭제
└── ui_archive/            # 이동
    ├── README.md          # 보관 이유 설명
    └── streamlit/         # Streamlit UI
        ├── app.py
        ├── pages/
        └── components/
```

**Option 2: 완전 삭제**
```bash
# Git 이력은 유지됨
git rm -r extensions/ui/
```

#### 작업 단계
1. **백업** (10분)
   ```bash
   mkdir -p extensions/ui_archive/streamlit
   git mv extensions/ui/* extensions/ui_archive/streamlit/
   ```

2. **README 작성** (20분)
   ```markdown
   # Streamlit UI (보관)
   
   **상태**: 사용 안함 (React UI로 대체)
   **보관 이유**: 참고용
   **복원 방법**: git checkout <commit> extensions/ui/
   ```

3. **문서 업데이트** (30분)
   - PROJECT_STATUS.md 수정
   - README.md 수정
   - 관련 문서에서 Streamlit 언급 제거

4. **Git Commit** (10분)
   ```bash
   git add -A
   git commit -m "Streamlit UI archive로 이동 (React UI로 대체)"
   git push
   ```

---

### 3. Oracle Cloud 프론트엔드 배포 (선택) 🌐
**우선순위**: 낮음  
**예상 시간**: 3-4시간

#### 현재 상태
- ✅ 백엔드: Oracle Cloud에서 실행 중
- ❌ 프론트엔드: 로컬에서만 실행
- ✅ Git Pull: 매일 08:00 자동 동기화

#### 배포 방법

**Option 1: Nginx + React 빌드** (권장)
```bash
# 1. React 빌드
cd web/dashboard
npm run build

# 2. Nginx 설정
sudo apt install nginx
sudo nano /etc/nginx/sites-available/krx-dashboard

# 3. 설정 파일
server {
    listen 80;
    server_name your-domain.com;
    
    root /home/ubuntu/krx_hyungsoo/web/dashboard/build;
    index index.html;
    
    location / {
        try_files $uri /index.html;
    }
    
    location /api {
        proxy_pass http://localhost:8000;
    }
}

# 4. 활성화
sudo ln -s /etc/nginx/sites-available/krx-dashboard /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

**Option 2: PM2로 개발 서버 실행**
```bash
# 1. PM2 설치
npm install -g pm2

# 2. 실행
cd /home/ubuntu/krx_hyungsoo/web/dashboard
pm2 start npm --name "krx-dashboard" -- start

# 3. 자동 시작 설정
pm2 startup
pm2 save
```

#### 작업 단계
1. **환경 준비** (1시간)
   - Nginx 설치
   - 도메인 설정 (선택)
   - SSL 인증서 (선택)

2. **빌드 및 배포** (1시간)
   - React 빌드
   - Nginx 설정
   - 테스트

3. **자동화** (1시간)
   - Git Pull 후 자동 빌드 스크립트
   - Cron 설정

4. **문서화** (1시간)
   - 배포 가이드 작성
   - 트러블슈팅 가이드

---

### 4. 코드 정리 및 문서화 📝
**우선순위**: 중간  
**예상 시간**: 2-3시간

#### 작업 내용

**1. 미사용 파일 정리**
```bash
# 확인 필요
- scripts/_deprecated_*/
- scripts/archive/
- docs/archive/
- extensions/ui/ (Streamlit)
```

**2. README 업데이트**
```markdown
# 프로젝트 구조
- backend/ - FastAPI 백엔드
- web/dashboard/ - React 프론트엔드
- core/ - 공통 모듈
- scripts/nas/ - NAS 스크립트
- scripts/cloud/ - Oracle Cloud 스크립트
- docs/ - 문서
```

**3. 문서 정리**
```
docs/
├── README.md                    # 문서 목록
├── GETTING_STARTED.md           # 시작 가이드
├── ARCHITECTURE.md              # 아키텍처
├── API_REFERENCE.md             # API 문서
├── DEPLOYMENT.md                # 배포 가이드
└── completed/                   # 완료 문서
```

**4. 주석 정리**
- TODO 주석 제거 또는 이슈로 전환
- 오래된 주석 삭제
- 중요 로직에 설명 추가

---

## 📅 작업 일정 (제안)

### Week 1 (2025-11-25 ~ 2025-12-01)
**목표**: 미국 시장 지표 개선

- **Day 1-2**: 진단 및 데이터 소스 조사
- **Day 3-4**: 구현 및 테스트
- **Day 5**: 문서화 및 배포

### Week 2 (2025-12-02 ~ 2025-12-08)
**목표**: 코드 정리 및 문서화

- **Day 1**: Streamlit UI 정리
- **Day 2-3**: 미사용 파일 정리
- **Day 4-5**: 문서 업데이트

### Week 3 (2025-12-09 ~ 2025-12-15) - 선택
**목표**: Oracle Cloud 프론트엔드 배포

- **Day 1-2**: 환경 준비 및 빌드
- **Day 3-4**: 배포 및 테스트
- **Day 5**: 자동화 및 문서화

---

## 🎯 성공 기준

### 미국 시장 지표
- ✅ VIX, S&P 500, NASDAQ 정상 조회
- ✅ Daily Regime Check에서 미국 레짐 표시
- ✅ 텔레그램 알림에 미국 레짐 포함
- ✅ 오류 발생 시 한국 레짐만으로 계속 진행

### 코드 정리
- ✅ Streamlit UI archive로 이동
- ✅ 미사용 파일 정리
- ✅ README 업데이트
- ✅ 문서 정리

### 프론트엔드 배포 (선택)
- ✅ Oracle Cloud에서 접속 가능
- ✅ API 연동 정상
- ✅ Git Pull 후 자동 빌드

---

## 📚 참고 자료

### 미국 시장 지표
- [Alpha Vantage API](https://www.alphavantage.co/)
- [FRED API](https://fred.stlouisfed.org/docs/api/fred/)
- [Yahoo Finance Symbols](https://finance.yahoo.com/)

### 배포
- [Nginx 설정 가이드](https://nginx.org/en/docs/)
- [PM2 문서](https://pm2.keymetrics.io/)
- [React 빌드 최적화](https://create-react-app.dev/docs/production-build/)

---

## 💡 추가 아이디어

### 1. 성능 최적화
- React 빌드 최적화
- API 응답 캐싱
- 데이터베이스 인덱싱

### 2. 모니터링
- 백엔드 헬스체크
- 프론트엔드 에러 추적
- 텔레그램 알림 성공률 모니터링

### 3. 테스트
- 단위 테스트 추가
- 통합 테스트
- E2E 테스트

---

**작성자**: Cascade AI  
**검토 필요**: 사용자  
**다음 세션**: 미국 시장 지표 개선부터 시작
