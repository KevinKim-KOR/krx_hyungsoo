# Changelog

All notable changes to this project will be documented in this file.

## [Week 4] - 2025-11-08

### Added - 자동화 시스템 구현
- **Day 1: 실시간 모니터링 시스템**
  - `DataUpdater`: 데이터 수집 자동화
  - `RegimeMonitor`: 레짐 감지 자동화
  - `AutoSignalGenerator`: 매매 신호 생성
  
- **Day 2: 알림 시스템**
  - `TelegramNotifier`: 텔레그램 알림
  - `DailyReport`: 일일 리포트
  - `WeeklyReport`: 주간 리포트

- **Day 3: 파라미터 조정 UI**
  - `BacktestDatabase`: SQLite 기반 히스토리 DB
  - `Dashboard`: Streamlit 대시보드
  - 파라미터 조정 패널
  - 백테스트 히스토리 뷰어
  - 성과 비교 차트
  - 레짐 타임라인

- **NAS 배포**
  - `run_daily_report.py`: 일일 리포트 실행 스크립트
  - `run_weekly_report.py`: 주간 리포트 실행 스크립트
  - `daily_alert.sh`: NAS Cron 스크립트 (일일)
  - `weekly_alert.sh`: NAS Cron 스크립트 (주간)
  - `.env.template`: 환경 변수 템플릿

### Documentation
- `docs/WEEK4_AUTOMATION_COMPLETE.md`: Week 4 완료 보고서
- `docs/NAS_DEPLOYMENT_GUIDE.md`: NAS 배포 가이드
- `docs/PHASE2_COMPLETE_SUMMARY.md`: Phase 2 최종 요약

### Performance - 자동화
- ✅ 평일 5분, 주말 30분 투자로 운영 가능
- ✅ 텔레그램 자동 알림
- ✅ 파라미터 실시간 조정
- ✅ 백테스트 히스토리 관리

---

## [Week 3] - 2025-11-08

### Added - 하이브리드 전략 구현
- **MarketRegimeDetector**: 시장 레짐 감지 시스템
  - MA 50/200일 기반 레짐 분류 (상승장/하락장/중립장)
  - 추세 강도 및 신뢰도 계산
  - 레짐별 포지션 비율 제공 (상승 100~120%, 중립 80%, 하락 40~60%)
  - 방어 모드 진입 판단 (신뢰도 85% 이상)

- **KRXMAPSAdapter 통합**
  - 레짐 기반 포지션 조정 로직 추가
  - KOSPI 데이터 자동 로드
  - 레짐 통계 수집 및 보고

- **백테스트 스크립트**
  - `run_backtest_hybrid.py`: 하이브리드 전략 백테스트
  - `debug_regime.py`: 레짐 감지 디버깅 도구

### Changed - 포지션 비율 최적화
- 중립장 포지션: 50% → 80% (CAGR 6%p 회복)
- 하락장 포지션: 0~20% → 40~60% (과도한 방어 완화)
- 방어 모드 임계값: 70% → 85% (불필요한 매수 스킵 감소)

### Fixed - 버그 수정
- `_convert_results`에서 방어 시스템 통계 손실 문제 해결
- KOSPI 데이터 로드 조건에 `regime_detector` 추가
- 레짐 통계가 백테스트 결과에 표시되지 않던 문제 해결

### Performance - 성과
- **CAGR**: 27.05% (목표 30%의 90% 달성)
- **Sharpe Ratio**: 1.51 ✅ (목표 1.5 달성!)
- **Max Drawdown**: -19.92% (방어 없음 대비 15% 개선)
- **거래 수**: 1,406회

### Documentation
- `docs/WEEK3_HYBRID_STRATEGY.md`: Week 3 상세 보고서
- `docs/PHASE2_WEEK3_SUMMARY.md`: Week 3 요약
- 코드 주석 및 docstring 업데이트

---

## [Week 2] - 2025-11-07

### Added - 방어 시스템 구현
- **DefenseSystem**: 통합 방어 시스템
- **MarketCrashDetector**: 시장 급락 감지
- **VolatilityManager**: 변동성 관리

### Performance
- MDD 개선: -23.51% → -17.36%

---

## [Week 1] - 2025-11-06

### Added - KRX MAPS 엔진 통합
- **KRXMAPSAdapter**: MAPS 백테스트 어댑터
- **StrategyRules**: 전략 규칙 정의

### Performance
- CAGR: 39.01%
- Sharpe: 1.71
- MDD: -23.51%

---

## [Phase 1] - 2025-10-24

### Added - 초기 시스템 구축
- 데이터 수집 파이프라인
- 백테스트 엔진
- 스캐너 시스템
