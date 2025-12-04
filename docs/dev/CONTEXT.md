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

## 4. Recent Changes (Phase 2)
- **Regime-based Backtest**:
  - `MarketRegimeDetector`를 `BacktestRunner`에 통합.
  - 시장 상황(Bull/Bear/Neutral)에 따라 포지션 비중(Exposure) 동적 조절.
  - 검증 스크립트: `scripts/dev/verify_regime_backtest.py`

## 5. Next Steps (Phase 3 & 4)
- **Phase 3**: `BacktestRunner` 병렬 처리 (`joblib`)
- **Phase 4**: AI 분석 API (`api/v1/ai.py`) 및 프롬프트 고도화

## 6. How to Run Verification
```bash
# 레짐 기반 백테스트 검증
python scripts/dev/verify_regime_backtest.py

# 비용 모델 검증
python scripts/dev/verify_backtest_enhancement.py
```
