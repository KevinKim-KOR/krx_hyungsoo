# KRX Alertor Modular - Project Context

## 1. Project Overview
KRX(한국거래소) 및 미국 주식 시장을 대상으로 하는 모듈형 알림 및 백테스트 시스템입니다.
FastAPI 백엔드와 React 프론트엔드로 구성되어 있으며, 시장 레짐(Regime)을 감지하여 동적으로 포트폴리오 비중을 조절하는 하이브리드 전략을 사용합니다.

## 2. Key Components

### Backend (`backend/app`)
- **Framework**: FastAPI
- **API**: `api/v1` (RESTful)
- **Core Logic**:
  - `core/engine/backtest.py`: 백테스트 엔진 (비용, 세금, 슬리피지 포함)
  - `core/strategy/market_regime_detector.py`: 시장 레짐 감지 (MA, 추세 강도)
  - `extensions/backtest/runner.py`: 백테스트 실행기 (레짐 연동)

### Frontend (`web/dashboard`)
- **Framework**: React (Vite)
- **Pages**: Dashboard, Portfolio, Backtest, ML Model

### Data Pipeline
- **Cache**: `data/cache/*.parquet` (OHLCV 데이터)
- **Output**: `data/output` (분석 결과, 로그)

## 3. Development Environment
- **OS**: Windows
- **Server Start**: `start.bat` (Backend: 8000, Frontend: 3000)
- **Server Stop**: `stop.bat`
- **Rules**: `.antigravityrules` (개발 규칙)

## 4. Recent Changes (Phase 2 ~ 5)
- **Phase 2: Regime-based Backtest**:
  - `MarketRegimeDetector`를 `BacktestRunner`에 통합.
  - 시장 상황(Bull/Bear/Neutral)에 따라 포지션 비중(Exposure) 동적 조절.
- **Phase 3: Performance Optimization**:
  - `joblib`을 이용한 백테스트 병렬 처리 (`run_batch`).
  - 벤치마크 스크립트: `scripts/dev/benchmark_backtest.py`
- **Phase 4: AI Analysis Enhancement**:
  - AI 분석 전용 API 엔드포인트 생성 (`backend/app/api/v1/ai.py`).
  - 백테스트, 포트폴리오, ML 모델, 룩백 분석을 위한 컨텍스트 인식 프롬프트 구현.
- **Phase 5: Frontend Integration**:
  - `Backtest`, `Portfolio`, `MLModel`, `Lookback` 페이지에 AI 분석 기능 연동.
  - `ApiClient` 업데이트 및 `AIPromptModal` 활용.
  - 검증 스크립트: `scripts/dev/verify_ai_endpoints.py`

## 5. Next Steps
- **Deployment**: 운영 환경 배포 준비.
- **Monitoring**: 실시간 모니터링 및 알림 강화.

## 6. How to Run Verification
```bash
# 레짐 기반 백테스트 검증
python scripts/dev/verify_regime_backtest.py

# 병렬 처리 벤치마크
python scripts/dev/benchmark_backtest.py

# AI API 엔드포인트 검증
python scripts/dev/verify_ai_endpoints.py
```
