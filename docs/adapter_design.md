# Jason 백테스트 어댑터 설계

**작성일**: 2025-11-07  
**목적**: Jason 백테스트 엔진을 안전하게 통합  
**패턴**: Adapter Pattern

---

## 📋 설계 개요

### 목표
1. Jason 백테스트 엔진을 우리 시스템에 통합
2. 기존 시스템에 영향 없이 안전하게 통합
3. 데이터 형식 차이를 투명하게 변환
4. 롤백 가능한 구조

### 핵심 원칙
- **어댑터 패턴**: Jason 엔진을 래핑
- **데이터 변환**: 투명한 형식 변환
- **에러 처리**: 실패 시 안전한 롤백
- **최소 의존성**: Jason 코드 최소 복사

---

## 🎨 클래스 다이어그램

```
┌─────────────────────────────────────────────────────────┐
│                    우리 시스템                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  scripts/phase2/run_backtest.py                         │
│         │                                                │
│         │ price_data (MultiIndex DataFrame)             │
│         │ strategy (SignalGenerator)                    │
│         ▼                                                │
│  ┌──────────────────────────────────────────┐          │
│  │   JasonBacktestAdapter                   │          │
│  │   (core/engine/jason_adapter.py)         │          │
│  ├──────────────────────────────────────────┤          │
│  │  + run(price_data, strategy)             │          │
│  │  - _convert_data()                       │          │
│  │  - _convert_strategy()                   │          │
│  │  - _convert_results()                    │          │
│  └──────────────────────────────────────────┘          │
│         │                                                │
│         │ jason_data (Dict[ticker, DataFrame])          │
│         │ jason_strategy (StrategyRules)                │
│         ▼                                                │
├─────────────────────────────────────────────────────────┤
│                   Jason 시스템                           │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────┐          │
│  │   run_portfolio_backtest()               │          │
│  │   (logic/backtest/portfolio_runner.py)   │          │
│  └──────────────────────────────────────────┘          │
│         │                                                │
│         │ BacktestResult                                │
│         ▼                                                │
│  ┌──────────────────────────────────────────┐          │
│  │   성과 지표 계산                          │          │
│  │   (Sharpe, MDD, Win Rate)                │          │
│  └──────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────┘
```

---

## 🔄 데이터 흐름도

### 전체 흐름
```
1. 입력 데이터 (우리 형식)
   ↓
2. _convert_data() - 데이터 변환
   ↓
3. _convert_strategy() - 전략 변환
   ↓
4. Jason 백테스트 실행
   ↓
5. _convert_results() - 결과 변환
   ↓
6. 출력 결과 (우리 형식)
```

### 상세 흐름
```
┌─────────────────────────────────────────────┐
│ 1. 입력 데이터 (우리 형식)                   │
├─────────────────────────────────────────────┤
│ price_data: MultiIndex DataFrame            │
│   Index: (code, date)                       │
│   Columns: [open, high, low, close, volume] │
│                                              │
│ strategy: SignalGenerator                   │
│   - ma_period: 60                           │
│   - rsi_period: 14                          │
│   - maps_buy_threshold: 0.0                 │
│   - maps_sell_threshold: -5.0               │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ 2. _convert_data() - 데이터 변환            │
├─────────────────────────────────────────────┤
│ jason_data: Dict[ticker, DataFrame]         │
│   {                                          │
│     "069500": DataFrame({                   │
│       "Date": [...],                        │
│       "Open": [...],                        │
│       "Close": [...]                        │
│     }),                                      │
│     "122630": ...                           │
│   }                                          │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ 3. _convert_strategy() - 전략 변환          │
├─────────────────────────────────────────────┤
│ jason_strategy: StrategyRules               │
│   - ma_period: 60                           │
│   - portfolio_topn: 10                      │
│   - replace_threshold: 0.0                  │
│   - ma_type: "SMA"                          │
│   - core_holdings: []                       │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ 4. Jason 백테스트 실행                      │
├─────────────────────────────────────────────┤
│ run_portfolio_backtest(                     │
│   strategy_rules=jason_strategy,            │
│   price_data=jason_data,                    │
│   initial_capital=10_000_000,               │
│   ...                                        │
│ )                                            │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ 5. _convert_results() - 결과 변환           │
├─────────────────────────────────────────────┤
│ our_results: Dict                           │
│   {                                          │
│     "final_value": 11_500_000,              │
│     "total_return": 1_500_000,              │
│     "total_return_pct": 15.0,               │
│     "sharpe_ratio": 1.2,                    │
│     "max_drawdown": -12.5,                  │
│     "num_trades": 100,                      │
│     "trades": [...],                        │
│     "daily_values": [...]                   │
│   }                                          │
└─────────────────────────────────────────────┘
```

---

## 🔧 변환 로직 상세

### 1. 데이터 변환 (`_convert_data`)

#### 입력 (우리 형식)
```python
# MultiIndex DataFrame
price_data.head()
#                      open    high     low   close  volume
# code   date                                               
# 069500 2022-01-03  10000   10100    9900   10050  100000
#        2022-01-04  10050   10150    9950   10100  110000
# 122630 2022-01-03   5000    5050    4950    5020   50000
#        2022-01-04   5020    5070    4970    5050   55000
```

#### 출력 (Jason 형식)
```python
# Dict[ticker, DataFrame]
jason_data = {
    "069500": pd.DataFrame({
        "Date": [datetime(2022, 1, 3), datetime(2022, 1, 4)],
        "Open": [10000, 10050],
        "High": [10100, 10150],
        "Low": [9900, 9950],
        "Close": [10050, 10100],
        "Volume": [100000, 110000]
    }).set_index("Date"),
    "122630": pd.DataFrame({
        "Date": [datetime(2022, 1, 3), datetime(2022, 1, 4)],
        "Open": [5000, 5020],
        "High": [5050, 5070],
        "Low": [4950, 4970],
        "Close": [5020, 5050],
        "Volume": [50000, 55000]
    }).set_index("Date")
}
```

#### 변환 알고리즘
```python
def _convert_data(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    MultiIndex DataFrame → Dict[ticker, DataFrame]
    
    1. 종목별로 그룹화
    2. 날짜를 pd.Timestamp로 변환
    3. 컬럼명을 대문자로 변환
    4. Date를 인덱스로 설정
    """
    jason_data = {}
    
    # 종목 코드 추출
    tickers = df.index.get_level_values(0).unique()
    
    for ticker in tickers:
        # 종목별 데이터 추출
        ticker_df = df.xs(ticker, level=0).copy()
        
        # 날짜 변환 (date → pd.Timestamp)
        ticker_df.index = pd.to_datetime(ticker_df.index)
        ticker_df.index.name = 'Date'
        
        # 컬럼명 변환 (open → Open)
        ticker_df.columns = [col.capitalize() for col in ticker_df.columns]
        
        jason_data[ticker] = ticker_df
    
    return jason_data
```

---

### 2. 전략 변환 (`_convert_strategy`)

#### 입력 (우리 형식)
```python
# SignalGenerator
strategy = SignalGenerator(
    ma_period=60,
    rsi_period=14,
    rsi_overbought=70,
    maps_buy_threshold=0.0,
    maps_sell_threshold=-5.0
)
```

#### 출력 (Jason 형식)
```python
# StrategyRules
jason_strategy = StrategyRules(
    ma_period=60,
    portfolio_topn=10,
    replace_threshold=0.0,
    ma_type="SMA",
    core_holdings=[]
)
```

#### 변환 알고리즘
```python
def _convert_strategy(self, strategy, portfolio_topn: int = 10) -> StrategyRules:
    """
    SignalGenerator → StrategyRules
    
    매핑:
    - ma_period: 그대로 사용
    - portfolio_topn: 파라미터로 받음
    - replace_threshold: maps_buy_threshold 사용
    - ma_type: "SMA" 고정
    - core_holdings: 빈 리스트
    """
    from strategies.maps.rules import StrategyRules
    
    return StrategyRules(
        ma_period=strategy.ma_period,
        portfolio_topn=portfolio_topn,
        replace_threshold=strategy.maps_buy_threshold,
        ma_type="SMA",
        core_holdings=[]
    )
```

---

### 3. 결과 변환 (`_convert_results`)

#### 입력 (Jason 형식)
```python
# BacktestResult (dataclass)
jason_results = BacktestResult(
    initial_capital_krw=10_000_000,
    final_value=11_500_000,
    total_return_pct=15.0,
    sharpe_ratio=1.2,
    max_drawdown=-12.5,
    win_rate=55.0,
    trade_count=100,
    trades=[...],
    daily_values=[...]
)
```

#### 출력 (우리 형식)
```python
# Dict
our_results = {
    'final_value': 11_500_000,
    'total_return': 1_500_000,
    'total_return_pct': 15.0,
    'sharpe_ratio': 1.2,
    'max_drawdown': -12.5,
    'win_rate': 55.0,
    'num_trades': 100,
    'trades': [...],
    'daily_values': [...]
}
```

#### 변환 알고리즘
```python
def _convert_results(self, jason_results) -> Dict:
    """
    BacktestResult → Dict
    
    1. 필드명 매핑
    2. 계산 필드 추가 (total_return)
    3. 거래 내역 변환
    """
    return {
        'final_value': jason_results.final_value,
        'total_return': jason_results.final_value - jason_results.initial_capital_krw,
        'total_return_pct': jason_results.total_return_pct,
        'sharpe_ratio': jason_results.sharpe_ratio,
        'max_drawdown': jason_results.max_drawdown,
        'win_rate': jason_results.win_rate,
        'num_trades': jason_results.trade_count,
        'trades': jason_results.trades,
        'daily_values': jason_results.daily_values,
        'cagr': self._calculate_cagr(
            jason_results.initial_capital_krw,
            jason_results.final_value,
            jason_results.start_date,
            jason_results.end_date
        )
    }
```

---

## 🎯 어댑터 클래스 설계

### 클래스 구조
```python
class JasonBacktestAdapter:
    """
    Jason 백테스트 엔진 어댑터
    
    역할:
    1. 데이터 형식 변환 (우리 ↔ Jason)
    2. Jason 엔진 실행
    3. 에러 처리 및 롤백
    """
    
    def __init__(
        self,
        initial_capital: float = 10_000_000,
        commission_rate: float = 0.00015,
        slippage_rate: float = 0.001,
        max_positions: int = 10,
        country_code: str = "kor"
    ):
        """
        Args:
            initial_capital: 초기 자본
            commission_rate: 수수료율
            slippage_rate: 슬리피지율
            max_positions: 최대 보유 종목 수
            country_code: 국가 코드
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.max_positions = max_positions
        self.country_code = country_code
    
    def run(
        self,
        price_data: pd.DataFrame,
        strategy,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict:
        """
        백테스트 실행
        
        Args:
            price_data: MultiIndex DataFrame (code, date)
            strategy: SignalGenerator
            start_date: 시작일
            end_date: 종료일
        
        Returns:
            백테스트 결과 (Dict)
        """
        pass
    
    def _convert_data(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """데이터 변환: 우리 → Jason"""
        pass
    
    def _convert_strategy(self, strategy) -> StrategyRules:
        """전략 변환: 우리 → Jason"""
        pass
    
    def _convert_results(self, jason_results) -> Dict:
        """결과 변환: Jason → 우리"""
        pass
    
    def _calculate_cagr(
        self,
        initial_capital: float,
        final_value: float,
        start_date: date,
        end_date: date
    ) -> float:
        """CAGR 계산"""
        pass
```

---

## 🚨 에러 처리 전략

### 1. 데이터 변환 실패
```python
try:
    jason_data = self._convert_data(price_data)
except Exception as e:
    logger.error(f"데이터 변환 실패: {e}")
    # 빈 딕셔너리 반환 또는 예외 발생
    raise ValueError(f"데이터 변환 실패: {e}")
```

### 2. Jason 엔진 실행 실패
```python
try:
    jason_results = run_portfolio_backtest(...)
except Exception as e:
    logger.error(f"Jason 백테스트 실패: {e}")
    # 임시 결과 반환 또는 예외 발생
    return self._get_fallback_results()
```

### 3. 결과 변환 실패
```python
try:
    our_results = self._convert_results(jason_results)
except Exception as e:
    logger.error(f"결과 변환 실패: {e}")
    # 기본 결과 반환
    return self._get_default_results()
```

---

## 📦 필요한 Jason 파일

### 복사할 파일 (최소)
```
momentum-etf/
├── logic/backtest/
│   └── portfolio_runner.py    ✅ 핵심 백테스트 엔진
├── strategies/maps/
│   ├── rules.py               ✅ 전략 규칙
│   ├── scoring.py             ✅ 점수 계산
│   └── constants.py           ✅ 상수 정의
└── utils/
    └── indicators.py          ✅ 기술적 지표

→ 복사 위치:
core/engine/jason/
├── portfolio_runner.py
├── rules.py
├── scoring.py
├── constants.py
└── indicators.py
```

### 의존성 제거
```python
# 제거할 의존성
- MongoDB (db_manager.py)
- Streamlit (app.py)
- APScheduler (aps.py)

# 유지할 의존성
- pandas
- numpy
- dataclasses
```

---

## 🧪 테스트 전략

### 1. 단위 테스트
```python
# tests/test_jason_adapter.py

def test_convert_data():
    """데이터 변환 테스트"""
    # Given: MultiIndex DataFrame
    price_data = create_test_data()
    
    # When: 변환
    adapter = JasonBacktestAdapter()
    jason_data = adapter._convert_data(price_data)
    
    # Then: Dict[ticker, DataFrame] 형식
    assert isinstance(jason_data, dict)
    assert "069500" in jason_data
    assert jason_data["069500"].index.name == "Date"

def test_convert_strategy():
    """전략 변환 테스트"""
    # Given: SignalGenerator
    strategy = SignalGenerator(ma_period=60)
    
    # When: 변환
    adapter = JasonBacktestAdapter()
    jason_strategy = adapter._convert_strategy(strategy)
    
    # Then: StrategyRules 형식
    assert jason_strategy.ma_period == 60
    assert jason_strategy.portfolio_topn == 10

def test_backtest_execution():
    """백테스트 실행 테스트"""
    # Given: 테스트 데이터
    price_data = create_test_data()
    strategy = SignalGenerator()
    
    # When: 백테스트 실행
    adapter = JasonBacktestAdapter()
    results = adapter.run(price_data, strategy)
    
    # Then: 결과 반환
    assert "final_value" in results
    assert "sharpe_ratio" in results
```

### 2. 통합 테스트
```python
def test_full_backtest():
    """전체 백테스트 테스트"""
    # 실제 데이터로 백테스트 실행
    # 결과 검증
    pass
```

---

## 📊 성능 고려사항

### 1. 데이터 변환 최적화
```python
# 비효율적
for ticker in tickers:
    ticker_df = df.xs(ticker, level=0)  # 매번 검색

# 효율적
grouped = df.groupby(level=0)
for ticker, ticker_df in grouped:  # 한 번만 그룹화
    pass
```

### 2. 메모리 관리
```python
# 큰 데이터 처리 시
# - 청크 단위 처리
# - 불필요한 복사 최소화
# - del로 명시적 메모리 해제
```

---

## 🎯 다음 단계 (Day 3)

### 구현 작업
1. **Jason 파일 복사** (30분)
   - `portfolio_runner.py`
   - `rules.py`, `scoring.py`, `constants.py`
   - `indicators.py`

2. **어댑터 구현** (2시간)
   - `JasonBacktestAdapter` 클래스
   - 데이터 변환 메서드
   - 에러 처리

3. **테스트 작성** (1시간)
   - 단위 테스트
   - 통합 테스트

---

## 📝 체크리스트

### 설계 완료
- [x] 클래스 다이어그램
- [x] 데이터 흐름도
- [x] 변환 로직 상세
- [x] 에러 처리 전략
- [x] 테스트 전략

### 다음 작업
- [ ] Jason 파일 복사
- [ ] 어댑터 구현
- [ ] 테스트 작성
- [ ] 통합 테스트

---

**설계 완료**: 2025-11-07  
**다음 작업**: Day 3 - 구현  
**예상 시간**: 3.5시간
