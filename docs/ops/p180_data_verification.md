# P180 Data Abstraction Verification Report

## 1) SSOT 우선권 + data_source_used 증거
- **실행**: `python3 -m app.run_backtest --mode quick`
- **검증**: `strategy_params_latest.json` 내의 `data_source: "fdr"` 설정이 프롬프트를 타고 그대로 `load_ohlcv_cached`로 들어감.
- **결과**: `PASS` (`data_source_used: fdr`, `download_count: 4`, `cache_hit_count: 0`)

## 2) 캐시 경로 분리 (충돌 방지) 검증
- **실행**: `ls -R data/cache/ohlcv`
- **검증**: Provider 이름(`fdr`, `yfinance`)으로 물리적인 하위 디렉토리가 엄격히 분리됨. 
- **결과**: `PASS` (동일 종목이라도 `data/cache/ohlcv/fdr/069500...` vs `data/cache/ohlcv/yfinance/069500...` 경로가 상호 독립적으로 유지됨.)

## 3) “네트워크 0” 재현 검증 (Batch Stress Test)
- **실행**: 유니버스 20종목 확장 후 `python3 -m app.run_backtest --mode full` 연속 2회 실행.
- **검증**:
  - 1회차: `download_count: 20`, `cache_hit_count: 0` (전체 외부 API 수집)
  - 2회차: `download_count: 0`, `cache_hit_count: 20` (전체 로컬 캐시 사용)
- **결과**: `PASS` (정확히 `0 API Downloads`를 증명. 메모리 및 캐시 키가 한 치의 오차 없이 일치함.)

## 4) 폴백 (yfinance) 강제 테스트
- **실행**: `data_source: "yfinance"` 강제 할당.
- **검증**: yfinance 전용 `YFinanceProvider`로 라우팅되어 고유의 `.KS` suffix 붙이기 및 데이터프레임 변환(MultiIndex 컬럼 제거 등) 로직을 거침.
- **결과**: `PASS` (`data_source_used: yfinance`, 별도의 `data/cache/ohlcv/yfinance` 공간에 저장 완료.)

## 5) Optuna 튜닝의 동일 프리페치(Prefetch) 파이프라인
- **실행**: `python3 -m app.run_tune --mode quick --n-trials 50 --seed 42`
- **검증**: 20종목 × 50번의 루프(총 1,000회 조회)가 작동함에도 텔레메트리에 API 스팸이 단 1회도 발생하지 않음.
- **결과**: `PASS` (`download_count: 0`, `cache_hit_count: 20`, 50 Trials가 RAM에서 즉시 처리되어 Backtest 파이프라인과 100% 동일한 Telemetry 규격을 준수함.)
