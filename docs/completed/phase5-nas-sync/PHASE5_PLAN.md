# Phase 5 계획: 고도화 및 고급 기능 구현

**작성일**: 2025-11-17  
**상태**: 계획 단계  
**이전 단계**: Phase 4.5 완료 (FastAPI + HTML 대시보드 + Oracle Cloud 배포)

---

## 🎯 **Phase 5 목표**

Phase 4.5에서 구축한 3-Tier 아키텍처(PC/NAS/Oracle) 위에 고급 기능을 추가하여 완전한 자동화 투자 시스템 구축

---

## 🏗️ **현재 아키텍처 (Phase 4.5 완료)**

```
┌─────────────────────────────────────────────────────────┐
│                         PC                              │
│  ✅ FastAPI 백엔드                                       │
│  ✅ 최소 HTML UI                                         │
│  ✅ 백테스트 환경                                        │
│  ⚠️ 룩백 분석 (미구현)                                   │
│  ⚠️ 머신러닝 (미구현)                                    │
│  ⚠️ 포트폴리오 최적화 (미구현)                           │
└─────────────────────────────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────┐
│                        NAS                              │
│  ✅ 장중 데이터 수집                                     │
│  ✅ PUSH 알림 (텔레그램)                                 │
│  ✅ EOD 작업                                            │
│  ✅ 크론 스케줄                                          │
│  ⚠️ Oracle 동기화 (미구현)                               │
└─────────────────────────────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────┐
│                   Oracle Cloud                          │
│  ✅ FastAPI 백엔드 (Docker)                              │
│  ✅ HTML 대시보드                                        │
│  ✅ 읽기 전용 조회                                       │
│  ✅ 모바일 접속 가능                                     │
│  ⚠️ 실시간 데이터 (미연동)                               │
│  ⚠️ React UI (미구현)                                   │
└─────────────────────────────────────────────────────────┘
```

---

## 📋 **Phase 5 전체 로드맵**

### **Phase 5-1: 데이터 연동 (NAS ↔ Oracle)** ← 다음 작업

**목표**: NAS에서 생성한 실시간 데이터를 Oracle에서 조회 가능하게

**작업 내용**
1. 동기화 파일 구조 설계
   - 포트폴리오 스냅샷 (일별/주별)
   - 백테스트 결과 JSON
   - 신호/알림 히스토리
   - 손절 대상 종목

2. NAS → Oracle 동기화 스크립트
   - rsync 기반 파일 전송
   - SSH 키 기반 인증
   - 에러 핸들링

3. 동기화 주기 설정
   - 5분/1시간/일 1회 선택
   - NAS cron 설정

4. Oracle FastAPI 수정
   - 동기화된 파일 읽기
   - API 응답에 실시간 데이터 반영

**예상 기간**: 1~2일

**결과물**
- Oracle 대시보드에서 "실제 운영 데이터" 조회 가능
- 모바일에서 현재 포트폴리오/손절 대상 실시간 확인

**파일 구조**
```
NAS: /volume2/homes/Hyungsoo/krx/krx_alertor_modular/data/sync/
├── portfolio_snapshot_YYYYMMDD.json
├── backtest_results_latest.json
├── signals_today.json
└── stop_loss_targets.json

Oracle: ~/krx_hyungsoo/data/sync/
└── (NAS에서 동기화된 파일들)
```

---

### **Phase 5-2: 머신러닝 모델 (PC)**

**목표**: ETF 랭킹, 레짐 감지, 이상치 탐지 등 ML 기반 스코어링

**작업 내용**
1. 데이터 파이프라인
   - 특징 엔지니어링 (기술적 지표, 거시 지표)
   - 학습/검증/테스트 데이터 분리
   - 데이터 정규화/스케일링

2. 모델 학습 (PC에서만 수행)
   - XGBoost, LightGBM (트리 기반)
   - LSTM, GRU (시계열)
   - 앙상블 모델

3. 백테스트 검증
   - 기존 MAPS vs ML 스코어 비교
   - 성능 지표 (CAGR, Sharpe, MDD)
   - 워크포워드 분석

4. 결과 저장
   - `ml_scores_YYYYMMDD.json`
   - (선택) NAS로 전송 → Oracle 동기화

**예상 기간**: 1~2주

**결과물**
- ML 기반 종목 스코어링 시스템
- 백테스트 비교 리포트
- 대시보드에서 ML 스코어 Top N 조회

**파일 구조**
```
pc/ml/
├── feature_engineering.py
├── train_model.py
├── backtest_ml.py
└── models/
    ├── xgboost_model.pkl
    └── lstm_model.h5

data/output/ml/
├── ml_scores_YYYYMMDD.json
└── backtest_comparison.json
```

---

### **Phase 5-3: 포트폴리오 최적화 (PC)**

**목표**: 효율적 프론티어, 리스크 패리티, 동적 자산 배분

**작업 내용**
1. 최적화 프레임워크
   - PyPortfolioOpt, cvxpy 활용
   - 제약 조건 (최소/최대 비중, 섹터 제한)
   - 목적 함수 (Sharpe 최대화, 변동성 최소화)

2. 최적 포트폴리오 계산 (PC에서만 수행)
   - 평균-분산 최적화
   - 리스크 패리티
   - 블랙-리터만 모델

3. 백테스트 검증
   - 최적 포트폴리오 vs 현재 포트폴리오
   - 리밸런싱 효과 분석

4. 결과 저장
   - `optimal_portfolio_YYYYMMDD.json`
   - (선택) NAS → Oracle 동기화

**예상 기간**: 1주

**결과물**
- 최적 포트폴리오 추천 시스템
- 현재 vs 최적 비교 UI
- 리밸런싱 제안

**파일 구조**
```
pc/optimization/
├── portfolio_optimizer.py
├── constraints.py
└── backtest_optimization.py

data/output/optimization/
├── optimal_portfolio_YYYYMMDD.json
└── rebalancing_suggestions.json
```

---

### **Phase 5-4: 룩백 분석 (PC)**

**목표**: 과거 특정 시점 기준 "그때 전략을 썼다면?" 시뮬레이션

**작업 내용**
1. 룩백 엔진
   - 과거 데이터 기준 백테스트 재실행
   - 여러 시나리오 비교 (파라미터 변화, 전략 조합)

2. 시각화 (PC에서만 수행)
   - 시점별 성과 비교
   - 파라미터 민감도 분석
   - 전략 조합 효과

3. 결과 저장
   - `lookback_results_YYYYMMDD.json`

**예상 기간**: 3~5일

**결과물**
- 전략 검증 도구
- "만약 그때 이렇게 했다면?" 분석 리포트
- 대시보드에서 룩백 결과 조회

**파일 구조**
```
pc/lookback/
├── lookback_engine.py
├── scenario_generator.py
└── visualizer.py

data/output/lookback/
└── lookback_results_YYYYMMDD.json
```

---

### **Phase 5-5: UI/UX 고도화 (Oracle)**

**목표**: 현재 HTML 대시보드를 React + 차트로 업그레이드

**작업 내용**
1. React 프로젝트 생성
   - Create React App + TypeScript
   - TailwindCSS (스타일링)
   - shadcn/ui (컴포넌트)

2. 컴포넌트 설계
   - 포트폴리오 카드
   - 백테스트 차트 (Recharts, Chart.js)
   - 손절 대상 테이블 (필터/정렬)
   - 신호 타임라인

3. FastAPI 연동
   - 기존 API 그대로 사용
   - Axios 또는 Fetch API

4. 빌드 & 배포
   - `npm run build`
   - Oracle에 정적 파일 배포

**예상 기간**: 1~2주

**결과물**
- 모던한 대시보드 UI
- 인터랙티브 차트/필터
- 모바일 반응형 최적화

**파일 구조**
```
frontend/
├── src/
│   ├── components/
│   │   ├── PortfolioCard.tsx
│   │   ├── BacktestChart.tsx
│   │   └── StopLossTable.tsx
│   ├── pages/
│   │   ├── Home.tsx
│   │   ├── Backtest.tsx
│   │   └── StopLoss.tsx
│   └── services/
│       └── api.ts
└── package.json
```

---

### **Phase 5-6: 자동화 & 모니터링 강화 (NAS)**

**목표**: 알림, 리포트, 에러 핸들링 고도화

**작업 내용**
1. 텔레그램 알림 확장
   - ML 스코어 변화 알림
   - 포트폴리오 리밸런싱 제안 알림
   - 시스템 헬스 체크 알림

2. 리포트 자동 생성
   - 주간 리포트 (성과, 손절, 신호)
   - 월간 리포트 (전략 비교, 최적화 제안)

3. 에러 핸들링
   - 로그 수집 & 알림
   - 자동 재시도
   - 장애 복구

**예상 기간**: 3~5일

**결과물**
- 완전 자동화된 모니터링 시스템
- 수동 개입 최소화

**파일 구조**
```
scripts/automation/
├── telegram_alerts.py
├── weekly_report.py
├── monthly_report.py
└── health_check.py
```

---

## 🗓️ **Phase 5 전체 타임라인**

```
Week 1-2:  Phase 5-1 (NAS ↔ Oracle 데이터 연동)      ← 다음 작업
Week 3-4:  Phase 5-2 (머신러닝 모델)
Week 5:    Phase 5-3 (포트폴리오 최적화)
Week 6:    Phase 5-4 (룩백 분석)
Week 7-8:  Phase 5-5 (UI/UX 고도화)
Week 9:    Phase 5-6 (자동화 강화)
Week 10:   통합 테스트 & 문서화
```

**총 예상 기간**: 2~2.5개월

---

## 💡 **우선순위 추천**

전부 다 하기 부담스러우면 아래 순서로:

1. **Phase 5-1 (데이터 연동)** ← 가장 먼저
   - Oracle을 "실전 대시보드"로 만들기
   - 모바일에서 실시간 데이터 조회

2. **Phase 5-2 (머신러닝)**
   - 핵심 전략 고도화
   - 수익률 개선

3. **Phase 5-3 (포트폴리오 최적화)**
   - 실전 수익률 개선
   - 리스크 관리

4. **Phase 5-5 (UI 고도화)**
   - 사용성 개선
   - 모던 UI/UX

5. Phase 5-4, 5-6
   - 필요 시 추가

---

## 📊 **예상 결과**

### **Phase 5 완료 후 시스템**

```
┌─────────────────────────────────────────────────────────┐
│                         PC                              │
│  ✅ 백테스트 환경                                        │
│  ✅ 룩백 분석                                            │
│  ✅ 머신러닝 모델                                        │
│  ✅ 포트폴리오 최적화                                    │
└─────────────────────────────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────┐
│                        NAS                              │
│  ✅ 장중 데이터 수집                                     │
│  ✅ PUSH 알림 (확장)                                     │
│  ✅ EOD 작업                                            │
│  ✅ Oracle 동기화 (5분/1시간/일)                         │
│  ✅ 주간/월간 리포트                                     │
└─────────────────────────────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────┐
│                   Oracle Cloud                          │
│  ✅ FastAPI 백엔드                                       │
│  ✅ React 대시보드                                       │
│  ✅ 실시간 데이터 조회                                   │
│  ✅ 인터랙티브 차트                                      │
│  ✅ 모바일 최적화                                        │
└─────────────────────────────────────────────────────────┘
```

### **성과 지표 (예상)**
- **자동화율**: 95% 이상
- **수동 개입**: 주 1회 미만
- **모바일 접근**: 언제 어디서나
- **전략 성과**: CAGR 30%+ 목표
- **리스크 관리**: MDD -20% 이내

---

## 🎯 **다음 액션**

### **Phase 5-1 시작 준비**

1. NAS 환경 확인
   - SSH 키 설정
   - rsync 설치 확인
   - 크론 권한 확인

2. Oracle 환경 확인
   - SSH 접속 가능 여부
   - 디스크 용량 확인
   - 방화벽 설정 확인

3. 동기화 파일 구조 설계
   - 어떤 데이터를 동기화할지
   - 파일 포맷 (JSON, CSV, Parquet)
   - 동기화 주기 결정

---

## 📚 **참고 문서**

- `docs/PHASE4.5_COMPLETE.md` - Phase 4.5 완료 문서
- `docs/ORACLE_CLOUD_DEPLOY_GUIDE.md` - Oracle Cloud 배포 가이드
- `backend/README.md` - 백엔드 API 문서

---

## 📞 **협업 가이드**

이 문서는 다른 코딩 에이전트와 협업할 때 사용할 수 있도록 작성되었습니다.

### **Phase 5-1 시작 시 필요한 정보**
- NAS 경로: `/volume2/homes/Hyungsoo/krx/krx_alertor_modular`
- Oracle 경로: `~/krx_hyungsoo`
- Oracle IP: `168.107.51.68`
- 동기화 방식: rsync over SSH
- 동기화 주기: TBD (5분/1시간/일 중 선택)

### **Phase 5-2 시작 시 필요한 정보**
- PC 경로: `E:\AI Study\krx_alertor_modular`
- Python 버전: 3.13 (PC), 3.8 (NAS)
- ML 라이브러리: XGBoost, LightGBM, TensorFlow/PyTorch
- 데이터 기간: 2022-01-01 ~ 현재

### **Phase 5-5 시작 시 필요한 정보**
- 프론트엔드 프레임워크: React + TypeScript
- 스타일링: TailwindCSS
- 차트 라이브러리: Recharts
- 빌드 도구: Vite 또는 Create React App

---

**작성자**: Cascade AI  
**최종 수정**: 2025-11-17  
**다음 업데이트**: Phase 5-1 시작 시
