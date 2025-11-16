# KRX Alertor Frontend (React + TypeScript)

## 🎯 **설치 방법**

### **1. Node.js 설치**
```
https://nodejs.org/ 에서 LTS 버전 다운로드 및 설치
```

### **2. 프로젝트 생성**
```bash
# 프로젝트 루트에서
npx create-react-app frontend --template typescript

# 또는 이 폴더에서
cd frontend
npm install
```

### **3. TailwindCSS 설치**
```bash
cd frontend
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

### **4. 추가 패키지 설치**
```bash
npm install react-router-dom axios react-query recharts
npm install -D @types/react-router-dom
```

---

## 🚀 **실행**

```bash
cd frontend
npm start
```

브라우저에서 자동으로 열림: `http://localhost:3000`

---

## 📁 **프로젝트 구조** (예정)

```
frontend/
├── public/
├── src/
│   ├── components/        # 공통 컴포넌트
│   │   ├── Layout/
│   │   ├── Charts/
│   │   ├── Tables/
│   │   └── Forms/
│   ├── pages/             # 6개 페이지
│   │   ├── Dashboard.tsx
│   │   ├── Assets.tsx
│   │   ├── Backtest.tsx
│   │   ├── StopLoss.tsx
│   │   ├── Signals.tsx
│   │   └── Market.tsx
│   ├── services/          # API 서비스
│   │   └── api.ts
│   ├── hooks/             # Custom Hooks
│   ├── utils/             # 유틸리티
│   ├── types/             # TypeScript 타입
│   ├── App.tsx
│   └── index.tsx
├── package.json
├── tsconfig.json
└── tailwind.config.js
```

---

## 📝 **다음 단계**

Day 4부터 React 컴포넌트 구현 시작
