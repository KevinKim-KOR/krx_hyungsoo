# Week 1: Jason 백테스트 엔진 통합

**기간**: 2025-11-07 ~ 2025-11-14  
**목표**: Jason 백테스트 엔진으로 정확한 성과 측정  
**예상 시간**: 8시간 (평일 저녁 2시간 × 4일)

---

## 🎯 목표

### 주요 목표
1. Jason 백테스트 엔진 분석 및 이해
2. 어댑터 패턴으로 안전하게 통합
3. 정확한 성과 지표 계산 (Sharpe, MDD 등)
4. 기존 시스템 영향 없이 통합

### 성공 기준
- ✅ Jason 엔진으로 백테스트 실행 성공
- ✅ 정확한 Sharpe Ratio, MDD 계산
- ✅ 기존 시스템 정상 작동
- ✅ 롤백 가능한 구조

---

## 📋 작업 체크리스트

### Day 1: Jason 코드 분석 (2시간)
- [ ] Jason 레포 클론
  ```bash
  cd ~/projects
  git clone https://github.com/jasonisdoing/momentum-etf.git
  cd momentum-etf
  ```

- [ ] 핵심 파일 확인
  - [ ] `backtest/engine.py` - 백테스트 엔진 구조
  - [ ] `backtest/portfolio.py` - 포지션 관리
  - [ ] `utils/metrics.py` - 성과 지표 계산
  - [ ] `strategy/momentum.py` - 모멘텀 전략

- [ ] 데이터 구조 분석
  - [ ] 입력 데이터 형식 (DataFrame 구조)
  - [ ] 출력 결과 형식
  - [ ] 파라미터 인터페이스

- [ ] 분석 노트 작성
  ```
  docs/jason_code_analysis.md
  - 엔진 구조
  - 주요 함수
  - 인터페이스
  - 호환성 이슈
  ```

### Day 2: 어댑터 설계 (2시간)
- [ ] 인터페이스 정의
  ```python
  # core/engine/jason_adapter.py
  
  class JasonBacktestAdapter:
      def __init__(self, jason_engine):
          pass
      
      def run(self, price_data, strategy):
          # 우리 형식 → Jason 형식
          # Jason 엔진 실행
          # Jason 결과 → 우리 형식
          pass
  ```

- [ ] 데이터 변환 함수 설계
  - [ ] `_convert_data()` - 우리 → Jason
  - [ ] `_convert_strategy()` - 전략 변환
  - [ ] `_convert_results()` - Jason → 우리

- [ ] 설계 문서 작성
  ```
  docs/adapter_design.md
  - 클래스 다이어그램
  - 데이터 흐름
  - 변환 로직
  ```

### Day 3: 구현 (2시간)
- [ ] Jason 엔진 복사
  ```bash
  # Jason 코드를 우리 프로젝트로 복사
  cp -r ~/projects/momentum-etf/backtest core/engine/jason/
  cp -r ~/projects/momentum-etf/utils core/metrics/jason/
  ```

- [ ] 어댑터 구현
  ```python
  # core/engine/jason_adapter.py
  
  import pandas as pd
  from core.engine.jason.engine import BacktestEngine as JasonEngine
  
  class JasonBacktestAdapter:
      """Jason 백테스트 엔진 어댑터"""
      
      def __init__(self, initial_capital=10_000_000, **kwargs):
          self.jason_engine = JasonEngine(
              initial_capital=initial_capital,
              **kwargs
          )
      
      def run(self, price_data, strategy):
          # 1. 데이터 변환
          jason_data = self._convert_data(price_data)
          
          # 2. Jason 엔진 실행
          jason_results = self.jason_engine.run(jason_data, strategy)
          
          # 3. 결과 변환
          our_results = self._convert_results(jason_results)
          
          return our_results
      
      def _convert_data(self, df):
          """우리 데이터 → Jason 데이터"""
          # MultiIndex (code, date) → Jason 형식
          pass
      
      def _convert_results(self, jason_results):
          """Jason 결과 → 우리 형식"""
          return {
              'final_value': jason_results['final_value'],
              'total_return': jason_results['total_return'],
              'total_return_pct': jason_results['total_return_pct'],
              'sharpe_ratio': jason_results['sharpe_ratio'],
              'max_drawdown': jason_results['max_drawdown'],
              'num_trades': len(jason_results['trades']),
              'trades': jason_results['trades'],
              'daily_values': jason_results['daily_values']
          }
  ```

- [ ] 성과 지표 모듈 추가
  ```python
  # core/metrics/performance.py
  
  from core.metrics.jason.metrics import (
      calculate_sharpe_ratio,
      calculate_max_drawdown,
      calculate_win_rate
  )
  ```

### Day 4: 테스트 및 검증 (2시간)
- [ ] 단위 테스트 작성
  ```python
  # tests/test_jason_integration.py
  
  def test_data_conversion():
      """데이터 변환 테스트"""
      pass
  
  def test_backtest_execution():
      """백테스트 실행 테스트"""
      pass
  
  def test_metrics_calculation():
      """성과 지표 계산 테스트"""
      pass
  ```

- [ ] 통합 테스트
  ```bash
  # 간단한 데이터로 테스트
  python tests/test_jason_integration.py
  ```

- [ ] 실제 데이터 테스트
  ```bash
  # Phase 2 데이터로 백테스트
  python scripts/phase2/run_backtest_jason.py
  ```

- [ ] 결과 비교
  - [ ] 임시 결과 vs Jason 결과
  - [ ] 성과 지표 검증
  - [ ] 거래 내역 확인

---

## 📁 생성할 파일

```
krx_alertor_modular/
├── core/
│   ├── engine/
│   │   ├── jason/                    # 신규 디렉토리
│   │   │   ├── __init__.py
│   │   │   ├── engine.py             # Jason 엔진 (복사)
│   │   │   └── portfolio.py          # Jason 포트폴리오 (복사)
│   │   └── jason_adapter.py          # 신규 파일
│   └── metrics/
│       ├── jason/                    # 신규 디렉토리
│       │   ├── __init__.py
│       │   └── metrics.py            # Jason 지표 (복사)
│       ├── performance.py            # 신규 파일
│       └── risk.py                   # 신규 파일
├── scripts/
│   └── phase2/
│       └── run_backtest_jason.py     # 신규 파일 (Jason 엔진 사용)
├── tests/
│   └── test_jason_integration.py     # 신규 파일
└── docs/
    ├── jason_code_analysis.md        # 신규 문서
    └── adapter_design.md             # 신규 문서
```

---

## 🔧 구현 예시

### 1. Jason 엔진 사용 백테스트 스크립트

```python
# scripts/phase2/run_backtest_jason.py

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 2 재테스트 - Jason 엔진 사용 백테스트
"""
import sys
from pathlib import Path
from datetime import date
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.phase2.utils.logger import create_logger
from core.engine.jason_adapter import JasonBacktestAdapter
from extensions.strategy.signal_generator import SignalGenerator
from infra.data.loader import load_price_data

logger = create_logger("3_run_backtest_jason", PROJECT_ROOT)

logger.info("Phase 2 재테스트 - Jason 엔진 백테스트")

# 1. 데이터 로드
universe_file = PROJECT_ROOT / 'data' / 'universe' / 'etf_universe.csv'
universe_df = pd.read_csv(universe_file, encoding='utf-8-sig')
tickers = universe_df['ticker'].tolist()

logger.info(f"유니버스: {len(tickers)}개")

start_date = date(2022, 1, 1)
end_date = date.today()

price_data = load_price_data(tickers, start_date, end_date)
logger.success(f"데이터 로드 완료: {price_data.shape}")

# 2. Jason 엔진 초기화
engine = JasonBacktestAdapter(
    initial_capital=10_000_000,
    commission_rate=0.00015,
    slippage_rate=0.001,
    max_positions=10
)

logger.success("Jason 엔진 초기화 완료")

# 3. 전략 초기화
strategy = SignalGenerator(
    ma_period=60,
    rsi_period=14,
    rsi_overbought=70,
    maps_buy_threshold=0.0,
    maps_sell_threshold=-5.0
)

logger.success("전략 초기화 완료")

# 4. 백테스트 실행
logger.info("백테스트 실행 중...")

try:
    results = engine.run(price_data, strategy)
    
    logger.success("백테스트 완료!")
    
    # 5. 결과 출력
    logger.section("백테스트 결과")
    logger.info(f"최종 자산: {results['final_value']:,.0f}원")
    logger.info(f"수익률: {results['total_return_pct']:.2f}%")
    logger.info(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    logger.info(f"Max Drawdown: {results['max_drawdown']:.2f}%")
    logger.info(f"거래 수: {results['num_trades']}회")
    
except Exception as e:
    logger.fail(f"백테스트 실패: {e}")
    import traceback
    traceback.print_exc()

logger.finish()
```

---

## 🧪 테스트 시나리오

### 시나리오 1: 단순 데이터 테스트
```python
# 10개 종목, 100일 데이터
# 예상: 정상 실행, 결과 반환
```

### 시나리오 2: 실제 데이터 테스트
```python
# 81개 종목, 3.8년 데이터
# 예상: 정상 실행, 정확한 지표
```

### 시나리오 3: 성과 지표 검증
```python
# Sharpe Ratio, MDD 계산 확인
# 예상: 합리적인 값
```

---

## 📊 예상 결과

### 임시 결과 (현재)
```
수익률: 15%
CAGR: 3.7%
Sharpe: N/A
MDD: N/A
```

### Jason 엔진 결과 (예상)
```
수익률: 12~18%
CAGR: 3~5%
Sharpe: 0.8~1.2
MDD: -15~20%
```

---

## ⚠️ 주의사항

### 호환성 이슈
1. **데이터 형식**: MultiIndex vs 단일 Index
2. **날짜 형식**: datetime vs date
3. **컬럼 이름**: 대소문자, 언어

### 해결 방법
- 어댑터에서 모든 변환 처리
- 명확한 에러 메시지
- 롤백 가능한 구조

---

## 🎯 완료 기준

### 필수 (Must Have)
- [x] Jason 코드 분석 완료
- [ ] 어댑터 구현 완료
- [ ] 백테스트 실행 성공
- [ ] 성과 지표 계산 정확

### 선택 (Nice to Have)
- [ ] 성능 최적화
- [ ] 상세 로깅
- [ ] 시각화 추가

---

## 📝 다음 단계

Week 1 완료 후:
1. Week 2: 방어 시스템 구현
2. Jason 엔진 기반 백테스트 결과 분석
3. 개선 사항 도출

---

**시작일**: 2025-11-07  
**완료 예정**: 2025-11-14  
**담당**: 본인  
**상태**: 🔄 진행 중
