# KRX Alertor Dashboard

React + TypeScript + TailwindCSS 기반 대시보드

## 🚀 기능

- **대시보드**: 전체 요약 및 최근 분석 결과
- **포트폴리오 최적화**: Sharpe Ratio 최대화, 이산 배분
- **백테스트 비교**: MAPS vs ML 모델 성능 비교
- **ML 모델**: XGBoost Feature Importance 분석
- **룩백 분석**: 워크포워드 분석 결과

## 📦 설치

### 1. Node.js 설치

Node.js가 설치되어 있지 않다면 [nodejs.org](https://nodejs.org/)에서 다운로드하여 설치하세요.

### 2. 의존성 설치

```bash
cd web/dashboard
npm install
```

## 🏃 실행

### 개발 모드

```bash
npm run dev
```

브라우저에서 `http://localhost:3000` 접속

### 프로덕션 빌드

```bash
npm run build
npm run preview
```

## 🛠️ 기술 스택

- **React 18**: UI 라이브러리
- **TypeScript**: 타입 안정성
- **Vite**: 빠른 개발 환경
- **TailwindCSS**: 유틸리티 CSS
- **React Router**: 라우팅
- **Lucide React**: 아이콘
- **Recharts**: 차트 (예정)

## 📁 프로젝트 구조

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
└── postcss.config.js
```

## 🔌 API 연동

현재는 정적 데이터를 표시합니다. 실제 데이터 연동을 위해서는:

1. FastAPI 백엔드 실행 (`http://localhost:8000`)
2. `vite.config.ts`의 proxy 설정 확인
3. API 호출 코드 추가

## 🎨 커스터마이징

### 색상 테마

`tailwind.config.js`에서 색상 변경:

```js
theme: {
  extend: {
    colors: {
      primary: "hsl(var(--primary))",
      // ...
    }
  }
}
```

### 다크 모드

`src/index.css`에 다크 모드 색상 정의되어 있음:

```css
.dark {
  --background: 222.2 84% 4.9%;
  /* ... */
}
```

## 📝 TODO

- [ ] API 연동 (FastAPI)
- [ ] 차트 추가 (Recharts)
- [ ] 실시간 데이터 업데이트
- [ ] 다크 모드 토글
- [ ] 반응형 개선
- [ ] 로딩 상태 처리
- [ ] 에러 처리

## 🐛 문제 해결

### npm install 실패

```bash
# 캐시 삭제 후 재시도
npm cache clean --force
npm install
```

### 포트 충돌

`vite.config.ts`에서 포트 변경:

```ts
server: {
  port: 3001, // 원하는 포트
}
```

## 📄 라이선스

MIT
