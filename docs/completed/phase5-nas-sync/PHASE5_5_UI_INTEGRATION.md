# Phase 5-5: UI/UX 통합

**작성일**: 2025-11-18  
**상태**: 초기 구조 완료

---

## 📋 목차

1. [개요](#개요)
2. [구현 내용](#구현-내용)
3. [프로젝트 구조](#프로젝트-구조)
4. [설치 및 실행](#설치-및-실행)
5. [주요 페이지](#주요-페이지)
6. [다음 단계](#다음-단계)

---

## 개요

Phase 5-5는 **UI/UX 통합**을 목표로 하며, 모든 분석 결과를 하나의 대시보드에서 확인할 수 있도록 합니다.

### 목표

1. ✅ React 기반 대시보드 구축
2. ⏳ API 연동 (FastAPI)
3. ⏳ 차트 시각화 (Recharts)
4. ⏳ 실시간 데이터 업데이트

### 기술 스택

- **React 18**: UI 라이브러리
- **TypeScript**: 타입 안정성
- **Vite**: 빠른 개발 환경
- **TailwindCSS**: 유틸리티 CSS
- **React Router**: 라우팅
- **Lucide React**: 아이콘
- **Recharts**: 차트 (예정)

---

## 구현 내용

### 1. 프로젝트 초기화

**위치**: `web/dashboard/`

**주요 파일**:
- `package.json`: 의존성 관리
- `vite.config.ts`: Vite 설정
- `tsconfig.json`: TypeScript 설정
- `tailwind.config.js`: TailwindCSS 설정
- `postcss.config.js`: PostCSS 설정

### 2. 레이아웃 컴포넌트

**파일**: `src/components/Layout.tsx`

**기능**:
- 사이드바 네비게이션
- 헤더
- 메인 콘텐츠 영역
- 활성 페이지 하이라이트

**네비게이션 메뉴**:
- 대시보드 (/)
- 포트폴리오 (/portfolio)
- 백테스트 (/backtest)
- ML 모델 (/ml-model)
- 룩백 분석 (/lookback)

### 3. 페이지 컴포넌트

#### Dashboard (`src/pages/Dashboard.tsx`)

**표시 내용**:
- 요약 카드 (총 가치, Sharpe, 변동성, 기대 수익률)
- 최근 분석 결과 타임라인

**데이터 (현재 정적)**:
```typescript
총 포트폴리오 가치: ₩10,000,000 (+5.2%)
Sharpe Ratio: 1.49
변동성: 18.1%
기대 수익률: 29.9%
```

#### Portfolio (`src/pages/Portfolio.tsx`)

**표시 내용**:
- 최적 비중 (Sharpe Ratio 최대화)
- 성과 지표 (기대 수익률, 변동성, Sharpe)
- 이산 배분 (실제 매수 주식 수)

**데이터 예시**:
```
069500 (KODEX 200): 40% → 120주
091160 (KODEX 반도체): 20% → 63주
133690 (KOSEF 국고채): 40% → 33주
잔액: ₩21,441
```

#### Backtest (`src/pages/Backtest.tsx`)

**표시 내용**:
- MAPS vs ML 모델 성능 비교 테이블
- CAGR, Sharpe, MDD 비교

**데이터**:
```
MAPS (하이브리드):
- CAGR: 27.05%
- Sharpe: 1.51
- MDD: -19.92%

ML 모델 (XGBoost): 예정
```

#### MLModel (`src/pages/MLModel.tsx`)

**표시 내용**:
- 학습 결과 (Train R², Test R²)
- Top 5 중요 특징
- 과적합 경고

**데이터**:
```
Train R²: 0.9986
Test R²: -0.3973 (과적합 신호)
특징 수: 46개

Top 5 특징:
1. volatility_60: 0.0629
2. ma_100: 0.0609
3. roc_60: 0.0592
4. macd_signal: 0.0536
5. williams_r: 0.0513
```

#### Lookback (`src/pages/Lookback.tsx`)

**표시 내용**:
- 워크포워드 분석 요약
- 리밸런싱 결과 테이블

**데이터**:
```
리밸런싱 횟수: 4회
평균 수익률: 3.71%
평균 Sharpe: 2.47
승률: 75%

리밸런싱 결과:
2023-09-25: -0.46% (Sharpe -0.23)
2024-01-29: 2.96% (Sharpe 1.67)
2024-06-03: 10.09% (Sharpe 6.31) ⭐
2024-10-07: 2.23% (Sharpe 2.15)
```

---

## 프로젝트 구조

```
web/dashboard/
├── src/
│   ├── components/
│   │   └── Layout.tsx          # 레이아웃 (사이드바, 헤더)
│   ├── pages/
│   │   ├── Dashboard.tsx       # 대시보드
│   │   ├── Portfolio.tsx       # 포트폴리오 최적화
│   │   ├── Backtest.tsx        # 백테스트 비교
│   │   ├── MLModel.tsx         # ML 모델
│   │   └── Lookback.tsx        # 룩백 분석
│   ├── App.tsx                 # 메인 앱
│   ├── main.tsx                # 엔트리 포인트
│   └── index.css               # 글로벌 스타일
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
└── README.md
```

---

## 설치 및 실행

### 사전 요구사항

**Node.js 설치** (필수):
1. [nodejs.org](https://nodejs.org/) 방문
2. LTS 버전 다운로드 및 설치
3. 설치 확인:
   ```bash
   node --version
   npm --version
   ```

### 설치

```bash
cd web/dashboard
npm install
```

### 개발 모드 실행

```bash
npm run dev
```

브라우저에서 `http://localhost:3000` 접속

### 프로덕션 빌드

```bash
npm run build
npm run preview
```

---

## 주요 페이지

### 1. 대시보드

![Dashboard](../../assets/dashboard-preview.png)

**기능**:
- 전체 요약 카드
- 최근 분석 결과 타임라인
- 빠른 네비게이션

### 2. 포트폴리오 최적화

**기능**:
- 최적 비중 시각화
- 성과 지표 표시
- 이산 배분 계산

### 3. 백테스트 비교

**기능**:
- MAPS vs ML 성능 비교
- 성과 지표 테이블
- 차트 (예정)

### 4. ML 모델

**기능**:
- 학습 결과 표시
- Feature Importance 시각화
- 과적합 경고

### 5. 룩백 분석

**기능**:
- 워크포워드 분석 결과
- 리밸런싱 히스토리
- 성과 추이 (예정)

---

## 다음 단계

### Phase 5-5-1: API 연동 (예정)

**목표**: FastAPI 백엔드와 연결

**작업 내용**:
1. API 클라이언트 작성
2. 데이터 페칭 로직
3. 로딩 상태 처리
4. 에러 처리

**예상 API 엔드포인트**:
```
GET /api/portfolio/optimization
GET /api/backtest/results
GET /api/ml/model/info
GET /api/analysis/lookback
```

### Phase 5-5-2: 차트 추가 (예정)

**목표**: Recharts를 사용한 시각화

**차트 종류**:
1. **포트폴리오 비중**: 파이 차트
2. **백테스트 성과**: 라인 차트 (누적 수익률)
3. **Feature Importance**: 바 차트
4. **룩백 분석**: 라인 차트 (리밸런싱별 수익률)

### Phase 5-5-3: 실시간 업데이트 (예정)

**목표**: 자동 데이터 갱신

**방법**:
- WebSocket 연결 또는
- 폴링 (5분마다)

### Phase 5-5-4: 추가 기능 (예정)

**기능**:
- 다크 모드 토글
- 반응형 디자인 개선
- 데이터 필터링
- 날짜 범위 선택
- PDF 리포트 다운로드

---

## 기술 세부사항

### Vite 설정

**파일**: `vite.config.ts`

```typescript
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

**주요 설정**:
- `@` 별칭: `src/` 디렉토리 참조
- 포트: 3000
- API 프록시: FastAPI (8000) → Vite (3000)

### TailwindCSS 테마

**파일**: `tailwind.config.js`

**색상 시스템**:
- `primary`: 주요 색상 (파란색)
- `secondary`: 보조 색상 (회색)
- `accent`: 강조 색상
- `destructive`: 경고/삭제 색상 (빨간색)

**다크 모드**: 
- CSS 변수 기반
- `.dark` 클래스로 토글

### TypeScript 설정

**파일**: `tsconfig.json`

**주요 설정**:
- `strict`: true (엄격한 타입 체크)
- `jsx`: "react-jsx"
- Path mapping: `@/*` → `./src/*`

---

## 문제 해결

### npm install 실패

**원인**: Node.js 미설치

**해결**:
1. [nodejs.org](https://nodejs.org/)에서 Node.js 설치
2. 터미널 재시작
3. `npm install` 재실행

### 포트 충돌

**원인**: 3000 포트가 이미 사용 중

**해결**:
`vite.config.ts`에서 포트 변경:
```typescript
server: {
  port: 3001, // 다른 포트
}
```

### 린트 에러

**원인**: npm 패키지 미설치

**해결**:
```bash
npm install
```

---

## 성과

### ✅ 완료

- React 프로젝트 구조 완성
- 5개 주요 페이지 구현
- TailwindCSS 스타일링
- React Router 라우팅
- 레이아웃 컴포넌트

### ⏳ 진행 중

- Node.js 설치 대기
- npm install 대기

### 📝 예정

- API 연동
- 차트 추가
- 실시간 업데이트
- 추가 기능

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|-----|------|----------|
| 2025-11-18 | 1.0 | Phase 5-5 초기 구조 완성 |

---

**작성**: Cascade AI Assistant  
**최종 수정**: 2025-11-18
