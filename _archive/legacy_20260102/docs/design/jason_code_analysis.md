# Jason 백테스트 코드 분석

**분석일**: 2025-11-07  
**레포**: momentum-etf  
**목적**: 백테스트 엔진 통합을 위한 구조 파악

---

## 📋 전체 구조

### 디렉토리 구조
```
momentum-etf/
├── logic/                      # 핵심 로직
│   ├── backtest/              # 백테스트 엔진
│   │   ├── account_runner.py  # 계정별 백테스트 실행
│   │   ├── portfolio_runner.py # 포트폴리오 백테스트 (핵심!)
│   │   └── reporting.py       # 결과 리포트
│   ├── common/                # 공통 로직
│   │   ├── portfolio.py       # 포지션 관리
│   │   ├── signals.py         # 매수 신호
│   │   └── filtering.py       # 카테고리 필터링
│   ├── recommend/             # 추천 시스템
│   └── performance.py         # 성과 계산 (실제 거래)
├── strategies/                # 전략 구현
│   └── maps/                  # MAPS 전략 (핵심!)
│       ├── rules.py           # 전략 규칙
│       ├── scoring.py         # 점수 계산
│       ├── backtest.py        # 백테스트 로직
│       └── recommend.py       # 추천 로직
├── utils/                     # 유틸리티
│   ├── data_loader.py         # 데이터 로딩
│   ├── indicators.py          # 기술적 지표
│   ├── db_manager.py          # DB 관리
│   └── report.py              # 리포트 포맷팅
├── backtest.py                # CLI 백테스트 실행
└── config.py                  # 설정
```

---

## 🎯 핵심 컴포넌트

### 1. 백테스트 엔진 (`logic/backtest/portfolio_runner.py`)

#### 주요 함수
```python
def run_portfolio_backtest(
    strategy_rules: StrategyRules,
    price_data: Dict[str, pd.DataFrame],
    initial_capital: float,
    country_code: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    ...
) -> BacktestResult
```

#### 핵심 로직
1. **거래 가격 계산** (`_calculate_trade_price`)
   - 다음날 시초가 + 슬리피지
   - 매수: `next_open * (1 + 0.5%)`
   - 매도: `next_open * (1 - 0.5%)`

2. **매도 로직** (`_execute_individual_sells`)
   - 손절: `hold_ret <= stop_loss_threshold`
   - RSI 과매수: `rsi_score >= rsi_sell_threshold`
   - 추세 이탈: `price < ma`
   - 핵심 보유 종목은 매도 제외

3. **매수 로직**
   - MA 점수 기반 Top N 선택
   - 카테고리 중복 필터링
   - 동일 가중 포지션 크기

4. **성과 계산**
   - 일별 NAV 추적
   - Sharpe Ratio
   - Max Drawdown
   - Win Rate

---

### 2. MAPS 전략 (`strategies/maps/`)

#### StrategyRules (전략 규칙)
```python
@dataclass(frozen=True)
class StrategyRules:
    ma_period: int              # 이동평균 기간 (기본 20)
    portfolio_topn: int         # 포트폴리오 종목 수
    replace_threshold: float    # 교체 임계값
    ma_type: str               # MA 타입 (SMA, EMA, WMA, DEMA, TEMA, HMA)
    core_holdings: List[str]   # 핵심 보유 종목
```

#### MAPS 점수 계산 (`scoring.py`)
```python
def calculate_maps_score(close_prices, moving_average):
    """
    MAPS(Moving Average Position Score) 점수
    
    공식: ((종가 / 이동평균) - 1) * 100
    
    예시:
    - 종가 110, MA 100 → 점수 10.0 (MA 대비 +10%)
    - 종가 90, MA 100 → 점수 -10.0 (MA 대비 -10%)
    """
    ma_score = ((close_prices / moving_average) - 1.0) * 100
    return ma_score
```

#### 점수 정규화 (선택)
```python
def normalize_ma_score(scores, eligibility_threshold=0.0, max_bound=30.0):
    """
    0~100 스케일로 정규화
    
    - < 0.0: 0점 (투자 부적격)
    - 0.0 ~ 30.0: 0~100점 선형 변환
    - >= 30.0: 100점
    """
```

---

### 3. 성과 계산 (`logic/performance.py`)

#### 실제 거래 기반 성과
```python
def calculate_actual_performance(
    account_id: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    initial_capital: float,
    country_code: str
) -> Dict[str, Any]:
    """
    실제 거래 내역 기반 수익률 계산
    
    Returns:
        - cumulative_return_pct: 누적 수익률
        - current_value: 현재 평가액
        - trade_count: 거래 수
        - daily_records: 일별 기록
    """
```

---

## 🔧 데이터 구조

### 입력 데이터 형식
```python
# price_data: Dict[str, pd.DataFrame]
{
    "ticker1": pd.DataFrame({
        "Date": [...],
        "Open": [...],
        "High": [...],
        "Low": [...],
        "Close": [...],
        "Volume": [...]
    }),
    "ticker2": ...
}
```

### 출력 결과 형식
```python
@dataclass
class BacktestResult:
    initial_capital_krw: float
    final_value: float
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    trades: List[Trade]
    daily_values: List[Tuple[date, float]]
    ticker_summaries: List[TickerSummary]
```

---

## 🎨 핵심 알고리즘

### 1. 모멘텀 점수 계산
```python
# 1. 이동평균 계산
ma = calculate_moving_average(close_prices, period=20, ma_type="SMA")

# 2. MAPS 점수 계산
maps_score = ((close_prices / ma) - 1.0) * 100

# 3. 정규화 (선택)
normalized_score = normalize_ma_score(maps_score, threshold=0.0, max_bound=30.0)
```

### 2. 포트폴리오 구성
```python
# 1. 매수 후보 필터링
candidates = [ticker for ticker in tickers if maps_score[ticker] > 0]

# 2. 점수 기준 정렬
candidates.sort(key=lambda t: maps_score[t], reverse=True)

# 3. Top N 선택
selected = candidates[:portfolio_topn]

# 4. 동일 가중 포지션
position_size = total_equity / portfolio_topn
```

### 3. 리밸런싱 로직
```python
# 1. 매도 우선 (손절, RSI, 추세)
for ticker in current_holdings:
    if should_sell(ticker):
        sell(ticker)

# 2. 매수 (Top N 중 미보유 종목)
for ticker in top_n_candidates:
    if ticker not in current_holdings:
        buy(ticker)
```

---

## 📊 성과 지표

### 계산 방식
```python
# 1. Sharpe Ratio
daily_returns = (daily_values[i] / daily_values[i-1]) - 1
sharpe_ratio = (mean(daily_returns) / std(daily_returns)) * sqrt(252)

# 2. Max Drawdown
peak = max(daily_values[:i])
drawdown = (daily_values[i] / peak) - 1
max_drawdown = min(drawdowns)

# 3. Win Rate
win_rate = (winning_trades / total_trades) * 100
```

---

## 🔄 우리 시스템과의 차이점

### 1. 데이터 구조
| 항목 | Jason | 우리 |
|------|-------|------|
| 가격 데이터 | Dict[ticker, DataFrame] | MultiIndex DataFrame |
| 날짜 형식 | pd.Timestamp | date |
| 컬럼 이름 | Open, Close, ... | open, close, ... |

### 2. 백테스트 로직
| 항목 | Jason | 우리 |
|------|-------|------|
| 거래 가격 | 다음날 시초가 + 슬리피지 | 당일 종가 (임시) |
| 포지션 크기 | 동일 가중 | 동일 가중 |
| 리밸런싱 | 일별 | 일별 |
| 손절 | 개별 + 포트폴리오 | 미구현 |

### 3. 전략 로직
| 항목 | Jason | 우리 |
|------|-------|------|
| 신호 생성 | MAPS 점수 | MAPS + RSI |
| 매수 조건 | MA 위 + Top N | MA 위 + RSI 과매도 |
| 매도 조건 | 손절 + RSI + 추세 | 추세 이탈만 |
| 카테고리 필터 | 있음 | 없음 |

---

## 🎯 통합 전략

### 어댑터 패턴 사용
```python
class JasonBacktestAdapter:
    """Jason 백테스트 엔진 어댑터"""
    
    def __init__(self, jason_engine):
        self.jason_engine = jason_engine
    
    def run(self, price_data, strategy):
        # 1. 데이터 변환 (우리 → Jason)
        jason_data = self._convert_data(price_data)
        
        # 2. Jason 엔진 실행
        jason_results = self.jason_engine.run(jason_data, strategy)
        
        # 3. 결과 변환 (Jason → 우리)
        our_results = self._convert_results(jason_results)
        
        return our_results
```

### 변환 로직
```python
def _convert_data(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    MultiIndex DataFrame → Dict[ticker, DataFrame]
    
    입력: (code, date) MultiIndex
    출력: {ticker: DataFrame(Date, Open, Close, ...)}
    """
    jason_data = {}
    for ticker in df.index.get_level_values(0).unique():
        ticker_df = df.xs(ticker, level=0).copy()
        ticker_df.index.name = 'Date'
        ticker_df.columns = [col.capitalize() for col in ticker_df.columns]
        jason_data[ticker] = ticker_df
    return jason_data

def _convert_results(self, jason_results) -> Dict:
    """
    Jason 결과 → 우리 형식
    
    입력: BacktestResult (dataclass)
    출력: Dict (우리 형식)
    """
    return {
        'final_value': jason_results.final_value,
        'total_return': jason_results.final_value - jason_results.initial_capital,
        'total_return_pct': jason_results.total_return_pct,
        'sharpe_ratio': jason_results.sharpe_ratio,
        'max_drawdown': jason_results.max_drawdown,
        'num_trades': jason_results.trade_count,
        'trades': jason_results.trades,
        'daily_values': jason_results.daily_values
    }
```

---

## 🚨 호환성 이슈

### 1. 데이터 형식
- ❌ **문제**: MultiIndex vs Dict
- ✅ **해결**: 어댑터에서 변환

### 2. 날짜 형식
- ❌ **문제**: date vs pd.Timestamp
- ✅ **해결**: `pd.to_datetime()` 변환

### 3. 컬럼 이름
- ❌ **문제**: 대소문자 차이
- ✅ **해결**: `.capitalize()` 변환

### 4. 의존성
- ❌ **문제**: MongoDB, Streamlit 등
- ✅ **해결**: 백테스트 엔진만 복사, DB 의존성 제거

---

## 📦 복사할 파일

### 필수 파일
```
momentum-etf/
├── logic/backtest/
│   ├── portfolio_runner.py    ✅ 핵심 백테스트 엔진
│   └── reporting.py           ✅ 결과 리포트
├── strategies/maps/
│   ├── rules.py               ✅ 전략 규칙
│   ├── scoring.py             ✅ 점수 계산
│   └── constants.py           ✅ 상수 정의
└── utils/
    ├── indicators.py          ✅ 기술적 지표
    └── formatters.py          ✅ 포맷팅
```

### 선택 파일
```
momentum-etf/
├── logic/common/
│   ├── portfolio.py           ⚠️ 포지션 관리 (필요 시)
│   └── signals.py             ⚠️ 신호 생성 (필요 시)
└── utils/
    └── data_loader.py         ⚠️ 데이터 로딩 (필요 시)
```

---

## 🎯 다음 단계 (Day 2)

### 어댑터 설계
1. **인터페이스 정의**
   - `JasonBacktestAdapter` 클래스
   - `run()` 메서드
   - 데이터 변환 메서드

2. **데이터 변환 로직**
   - `_convert_data()`: 우리 → Jason
   - `_convert_strategy()`: 전략 변환
   - `_convert_results()`: Jason → 우리

3. **설계 문서 작성**
   - 클래스 다이어그램
   - 데이터 흐름
   - 변환 로직

---

## 📝 메모

### 장점
- ✅ 검증된 백테스트 엔진
- ✅ 정확한 성과 지표 계산
- ✅ 슬리피지 고려
- ✅ 손절 로직 구현
- ✅ 카테고리 필터링

### 단점
- ❌ MongoDB 의존성
- ❌ 복잡한 구조
- ❌ 데이터 형식 차이

### 통합 방향
- ✅ 어댑터 패턴으로 안전하게 통합
- ✅ 핵심 로직만 복사
- ✅ 의존성 최소화
- ✅ 롤백 가능한 구조

---

**분석 완료**: 2025-11-07  
**다음 작업**: Day 2 - 어댑터 설계  
**예상 시간**: 2시간
