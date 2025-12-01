# 백테스트 엔진 고도화 설계 - 비판적 검토 및 수정안

**작성일**: 2025-11-30  
**목적**: 외부 검토 의견 반영 및 설계 개선

---

## 📋 검토 의견 분류

### ✅ 전면 수용 (설계 수정 필요)
1. 한국 ETF/주식 세율 차별화 부족
2. 레짐 엔진 "검증됨" 표현의 모순
3. 120% 포지션(레버리지) 처리 불명확
4. Train/Val/Test 데이터 길이 현실성 부족
5. 파라미터 튜닝 과적합 위험 미언급
6. Gross/Net 구현 난이도 과소평가
7. 성과 지표 계산 위치 중복
8. 우선순위와 실제 작업 순서 불일치

### ⚠️ 부분 수용 (보완 필요)
1. 슬리피지 고정 비율 근거 부족
2. Neutral 레짐 시간 축 고려 부족

### 🔄 반박 (설계 유지, 설명 보강)
- 없음 (모든 지적이 타당함)

---

## 1. 거래비용/슬리피지 부분

### 1-1. 거래세(tax_rate) 설계 - ✅ 전면 수용

#### 비판 내용
```
"한국: 0.23% 증권거래세"로 일괄 처리
→ ETF/주식/리츠 등 상품별 세율 차이 무시
→ ETF 상당수는 거래세 면제
→ 현실 반영 정확도 떨어짐
```

#### 수용 및 수정안

**현재 설계 (과도한 단순화)**:
```yaml
costs:
  korea:
    tax_rate: 0.0023  # ❌ 일괄 0.23%
```

**수정안 (상품별 차별화)**:
```yaml
costs:
  korea:
    # 주식
    stock:
      commission_rate: 0.00015
      tax_rate: 0.0023        # 0.23% (증권거래세)
      slippage_bps: 5
    
    # ETF (대부분 면제)
    etf:
      commission_rate: 0.00015
      tax_rate: 0.0          # 0% (면제)
      slippage_bps: 3        # 유동성 높음
    
    # 리츠
    reit:
      commission_rate: 0.00015
      tax_rate: 0.0023       # 0.23%
      slippage_bps: 10       # 유동성 낮음
    
    # 레버리지 ETF
    leveraged_etf:
      commission_rate: 0.00015
      tax_rate: 0.0          # 0% (면제)
      slippage_bps: 8        # 변동성 높음
```

**구현 변경**:
```python
class BacktestEngine:
    def __init__(
        self,
        ...,
        instrument_type: str = 'etf'  # ✅ 추가: 'stock', 'etf', 'reit', 'leveraged_etf'
    ):
        self.instrument_type = instrument_type
        # Config에서 해당 타입의 비용 로드
        ...
    
    def execute_sell(self, ...):
        # ✅ 상품별 거래세 적용
        if self.instrument_type == 'stock' or self.instrument_type == 'reit':
            tax = quantity * adjusted_price * self.tax_rate
        else:  # ETF, leveraged_etf
            tax = 0.0  # 면제
        ...
```

**영향**:
- 기존 예상: CAGR -0.5~1% 감소
- 수정 후 (ETF 전략): CAGR 거의 변화 없음 (거래세 면제)
- **더 현실적인 성과 예측**

---

### 1-2. 슬리피지 고정 비율 근거 부족 - ⚠️ 부분 수용

#### 비판 내용
```
"고정 비율을 어떤 근거로 잡을지" 비어 있음
→ 감으로 tuning 수준
→ 실제 스프레드/호가 깊이 데이터 없이 설정
```

#### 수용 및 보완안

**1단계: 경험적 추정 (현실적)**
```python
# 실제 ETF 스프레드 분석 (예시)
# - KODEX 200 (069500): 평균 스프레드 0.01~0.02% (1~2bps)
# - TIGER 미국S&P500 (360750): 평균 스프레드 0.03~0.05% (3~5bps)
# - 소형 ETF: 평균 스프레드 0.1~0.2% (10~20bps)

# 보수적 추정: 평균 스프레드 × 2 (시장 충격 고려)
slippage_bps_estimates = {
    'large_cap_etf': 3,      # 2bps × 1.5
    'mid_cap_etf': 5,        # 3bps × 1.5
    'small_cap_etf': 15,     # 10bps × 1.5
    'leveraged_etf': 8       # 5bps × 1.5
}
```

**2단계: 데이터 기반 추정 (이상적, 선택)**
```python
def estimate_slippage_from_data(
    ticker: str,
    price_data: pd.DataFrame
) -> float:
    """
    실제 데이터에서 슬리피지 추정
    
    방법:
    1. 일중 고가-저가 범위 분석
    2. 거래량 대비 가격 변동성
    3. 보수적으로 상위 75% 분위수 사용
    """
    # 일중 변동폭
    intraday_range = (price_data['High'] - price_data['Low']) / price_data['Close']
    
    # 상위 75% 분위수 (보수적)
    slippage_estimate = intraday_range.quantile(0.75) / 2
    
    return slippage_estimate
```

**문서 보완**:
```markdown
### 슬리피지 추정 근거

#### 1단계: 경험적 추정 (현재)
- 대형 ETF: 3bps (KODEX 200 기준)
- 중형 ETF: 5bps
- 소형 ETF: 15bps
- 레버리지 ETF: 8bps

#### 2단계: 데이터 기반 추정 (향후)
- 일중 고가-저가 범위 분석
- 거래량 대비 가격 변동성
- 상위 75% 분위수 (보수적)

#### 검증 방법
- 백테스트 결과를 실제 거래 결과와 비교
- 슬리피지 파라미터 조정
```

---

## 2. 레짐 엔진 / 노출 스케일링

### 2-1. "이미 검증됨" vs "실제로는 안 쓰고 있음" - ✅ 전면 수용

#### 비판 내용
```
"MarketRegimeDetector: ✅ 이미 구현됨 - Week 3에서 검증"
하지만 "레짐 노출 스케일링 미적용 (가장 심각!)"
→ 모순
→ 레짐 탐지는 했지만 포지션 조절은 안 했음
→ "Week3 성과는 레짐 덕이다"라고 착각할 여지
```

#### 수용 및 수정안

**기존 표현 (오해 소지)**:
```markdown
**레짐 엔진**: `core/strategy/market_regime_detector.py`
✅ 이미 구현됨 - Week 3에서 검증
```

**수정 표현 (명확화)**:
```markdown
**레짐 엔진**: `core/strategy/market_regime_detector.py`

**현재 상태**:
- ✅ 레짐 감지 로직: 구현 및 테스트 완료
- ✅ 포지션 비율 계산: `get_position_ratio()` 구현 완료
- ❌ **포트폴리오 적용: 미구현** (가장 심각!)

**Week 3 성과 (MDD -19.92%)의 진실**:
- 레짐 감지는 했지만 **포지션 조절은 안 함**
- 즉, 레짐과 무관하게 **항상 100% 포지션 유지**
- Week 3 성과는 **레짐 엔진 덕이 아님**

**예상 효과 (레짐 스케일링 적용 시)**:
- Bull 레짐: 120% 포지션 (공격)
- Bear 레짐: 40% 포지션 (방어)
- MDD: -19.92% → **-15% 예상** (약 25% 개선)
```

---

### 2-2. 120% 포지션(레버리지) 처리 - ✅ 전면 수용

#### 비판 내용
```
get_position_ratio()에서 Bull일 때 1.0~1.2 (100~120%)
→ 엔진이 레버리지/마진을 지원하는지 불명확
→ 현금 음수 가능성
→ "진짜 레버리지(마진)"인가? "레버리지 ETF"인가?
```

#### 수용 및 수정안

**현재 설계 (불명확)**:
```python
if regime == 'bull':
    return 1.0 + (confidence - 0.5) * 0.4  # 100~120%
```

**수정안 1: 레버리지 비활성화 (현실적, 권장)**
```python
class MarketRegimeDetector:
    def __init__(
        self,
        ...,
        enable_leverage: bool = False  # ✅ 추가
    ):
        self.enable_leverage = enable_leverage
    
    def get_position_ratio(self, regime, confidence):
        if regime == 'bull':
            if self.enable_leverage:
                return 1.0 + (confidence - 0.5) * 0.4  # 100~120%
            else:
                return 0.8 + (confidence - 0.5) * 0.4  # 80~100%
        
        elif regime == 'bear':
            return 0.6 - (confidence - 0.5) * 0.4  # 40~60%
        
        else:  # neutral
            return 0.6 + (confidence - 0.5) * 0.4  # 40~80%
```

**수정안 2: 레버리지 ETF 활용 (고급, 선택)**
```python
def get_position_ratio_with_leverage_etf(self, regime, confidence):
    """
    레버리지 ETF 활용 전략
    
    예:
    - Bull 레짐: 레버리지 ETF (2x) 비중 증가
    - Bear 레짐: 인버스 ETF (-1x) 또는 현금
    """
    if regime == 'bull':
        # 일반 ETF 80% + 레버리지 ETF 20% = 실질 120%
        return {
            'normal_etf_ratio': 0.8,
            'leveraged_etf_ratio': 0.2
        }
    ...
```

**엔진 수정 (현금 음수 방지)**:
```python
def rebalance(self, target_weights, ...):
    # ✅ 총 비중 확인
    total_weight = sum(target_weights.values())
    
    if total_weight > 1.0 and not self.enable_leverage:
        logger.warning(f"총 비중 {total_weight:.2f} > 1.0, 레버리지 비활성화 상태")
        # 정규화
        target_weights = {
            symbol: weight / total_weight
            for symbol, weight in target_weights.items()
        }
    
    # ✅ 현금 부족 확인
    required_cash = sum(...)
    if required_cash > self.portfolio.cash:
        logger.error("현금 부족, 리밸런싱 불가")
        return False
    ...
```

**기본 설정 (보수적)**:
```yaml
regime_detection:
  enable_leverage: false  # 레버리지 비활성화
  position_scaling_mode: 'continuous'
  
  # 비중 범위 (레버리지 없음)
  bull_range: [0.8, 1.0]
  neutral_range: [0.4, 0.8]
  bear_range: [0.0, 0.6]
```

---

### 2-3. Neutral 레짐 시간 축 고려 - ⚠️ 부분 수용

#### 비판 내용
```
Neutral = 항상 80% 노출
→ 시간 축(얼마나 오래 Neutral이었나) 고려 사라짐
→ 원래 고민: "중립이 이어지다가 상승 신호가 오면 단계적으로 진입"
```

#### 수용 및 보완안

**현재 설계 (단순)**:
```python
else:  # neutral
    return 0.8  # 항상 80%
```

**1단계: 현재 유지 (단순화)**
- Neutral = 80% 고정
- 이유: 복잡도 최소화, 빠른 검증

**2단계: 시간 축 고려 (고급, 향후)**
```python
class MarketRegimeDetector:
    def __init__(self, ...):
        self.regime_history = []  # (date, regime) 기록
    
    def get_position_ratio_with_time(self, regime, confidence):
        """시간 축 고려 포지션 비율"""
        if regime == 'neutral':
            # Neutral 지속 기간 계산
            neutral_days = self._count_consecutive_regime('neutral')
            
            if neutral_days < 5:
                return 0.8  # 초기: 80%
            elif neutral_days < 20:
                return 0.6  # 중기: 60% (관망)
            else:
                return 0.4  # 장기: 40% (현금 확보)
        ...
    
    def _count_consecutive_regime(self, target_regime):
        """연속된 레짐 일수 계산"""
        count = 0
        for date, regime in reversed(self.regime_history):
            if regime == target_regime:
                count += 1
            else:
                break
        return count
```

**문서 보완**:
```markdown
### Neutral 레짐 처리

#### 1단계: 단순 설계 (현재)
- Neutral = 80% 고정
- 목적: 복잡도 최소화, 빠른 검증

#### 2단계: 시간 축 고려 (향후)
- Neutral 지속 기간에 따라 비중 조절
  - 초기 (< 5일): 80%
  - 중기 (5~20일): 60%
  - 장기 (> 20일): 40%
- 목적: 장기 중립장에서 현금 확보
```

---

## 3. Train / Validation / Test 설계

### 3-1. 데이터 길이 현실성 부족 - ✅ 전면 수용

#### 비판 내용
```
현재 데이터: 2022-01 ~ 2025-11 (약 4년)
→ 매크로 사이클 기준 반쪽짜리
→ Train/Val/Test 나누면 각각 1.8년/0.6년/0.6년
→ Test 샘플 수 너무 적음
→ 구간별 편향 가능성 (어느 구간은 상승장만, 어느 구간은 하락장만)
```

#### 수용 및 수정안

**기존 설계 (낙관적)**:
```python
train_ratio = 0.7  # 70%
val_ratio = 0.15   # 15%
test_ratio = 0.15  # 15%
```

**수정안 1: 최소 데이터 길이 검증**
```python
class TrainValTestSplitter:
    def __init__(
        self,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        min_train_days: int = 504,  # ✅ 최소 2년 (252 × 2)
        min_val_days: int = 126,    # ✅ 최소 6개월
        min_test_days: int = 126    # ✅ 최소 6개월
    ):
        ...
    
    def split(self, start_date, end_date):
        total_days = (end_date - start_date).days
        
        # ✅ 최소 길이 검증
        train_days = int(total_days * self.train_ratio)
        val_days = int(total_days * self.val_ratio)
        test_days = total_days - train_days - val_days
        
        if train_days < self.min_train_days:
            raise ValueError(
                f"Train 기간 부족: {train_days}일 < {self.min_train_days}일 (최소 2년)"
            )
        
        if val_days < self.min_val_days:
            raise ValueError(
                f"Validation 기간 부족: {val_days}일 < {self.min_val_days}일 (최소 6개월)"
            )
        
        if test_days < self.min_test_days:
            raise ValueError(
                f"Test 기간 부족: {test_days}일 < {self.min_test_days}일 (최소 6개월)"
            )
        
        ...
```

**수정안 2: 레짐 균형 검증**
```python
def validate_regime_balance(
    self,
    market_data: pd.DataFrame,
    start_date: date,
    end_date: date,
    regime_detector: MarketRegimeDetector
) -> Dict:
    """
    구간별 레짐 균형 검증
    
    목적: 특정 구간이 한 레짐으로만 편향되지 않았는지 확인
    """
    regime_counts = {'bull': 0, 'bear': 0, 'neutral': 0}
    
    for current_date in pd.date_range(start_date, end_date):
        regime, _ = regime_detector.detect_regime(market_data, current_date)
        regime_counts[regime] += 1
    
    total = sum(regime_counts.values())
    regime_ratios = {
        regime: count / total
        for regime, count in regime_counts.items()
    }
    
    # ✅ 경고: 특정 레짐이 80% 이상
    for regime, ratio in regime_ratios.items():
        if ratio > 0.8:
            logger.warning(
                f"레짐 편향 경고: {start_date}~{end_date} 구간에서 "
                f"{regime} 레짐이 {ratio*100:.1f}% 차지"
            )
    
    return regime_ratios
```

**권장 데이터 길이**:
```markdown
### 최소 데이터 요구사항

#### 전체 기간
- **최소**: 3.5년 (Train 2년 + Val 0.75년 + Test 0.75년)
- **권장**: 5년 이상 (최소 1개 완전 사이클 포함)

#### 구간별
- Train: 최소 2년 (504 거래일)
- Validation: 최소 6개월 (126 거래일)
- Test: 최소 6개월 (126 거래일)

#### 레짐 균형
- 각 구간에서 특정 레짐이 80% 이상 차지하면 경고
- 가능하면 Bull/Bear/Neutral 골고루 포함된 구간 선택
```

**현실적 대안 (데이터 부족 시)**:
```markdown
### 데이터 부족 시 대안

#### 1. 데이터 기간 확장
- 2020년부터 시작 (코로나 포함)
- 장점: 극단적 변동성 구간 포함
- 단점: 특수 상황 (코로나) 영향

#### 2. Walk-Forward 최소화
- 고정 분할 대신 1회 Walk-Forward
- Train: 2022-01 ~ 2024-06 (2.5년)
- Val: 2024-07 ~ 2024-12 (6개월)
- Test: 2025-01 ~ 2025-06 (6개월)

#### 3. 파라미터 튜닝 최소화
- 한 번에 2~3개 파라미터만 튜닝
- 나머지는 고정값 사용
```

---

### 3-2. 파라미터 튜닝 과적합 위험 - ✅ 전면 수용

#### 비판 내용
```
"파라미터 수가 늘어날수록 Val 구간도 overfit된다"
→ 조합 폭발 시 Validation도 Train처럼 overfit
→ "모든 걸 한 번에 튜닝"은 위험
```

#### 수용 및 수정안

**기존 설계 (위험)**:
```python
param_grid = {
    'commission_rate': [0.00015, 0.0003],
    'max_positions': [5, 10, 15],
    'rebalance_frequency': ['daily', 'weekly'],
    'ma_period': [20, 50, 100],
    'rsi_period': [7, 14, 21],
    ...  # 조합 폭발!
}
```

**수정안: 단계적 튜닝**
```python
class ParameterGridSearch:
    def __init__(
        self,
        param_grid: Dict[str, List],
        max_params_per_search: int = 3  # ✅ 최대 3개 파라미터
    ):
        if len(param_grid) > max_params_per_search:
            logger.warning(
                f"파라미터 수 {len(param_grid)}개 > {max_params_per_search}개 (권장)\n"
                f"과적합 위험 증가, 단계적 튜닝 권장"
            )
        ...
```

**단계적 튜닝 전략**:
```markdown
### 파라미터 튜닝 전략

#### Phase 1: 핵심 파라미터 (2~3개)
```python
param_grid_phase1 = {
    'max_positions': [5, 10, 15],
    'rebalance_frequency': ['daily', 'weekly']
}
# → 6개 조합
```

#### Phase 2: 전략 파라미터 (2~3개)
```python
# Phase 1 최적값 고정
best_max_positions = 10
best_rebalance_freq = 'daily'

param_grid_phase2 = {
    'ma_period': [20, 50, 100],
    'rsi_period': [7, 14, 21]
}
# → 9개 조합
```

#### Phase 3: 레짐 파라미터 (2~3개)
```python
# Phase 1, 2 최적값 고정
param_grid_phase3 = {
    'regime_short_ma': [20, 50],
    'regime_long_ma': [100, 200],
    'regime_threshold': [0.01, 0.02, 0.03]
}
# → 12개 조합
```

#### 총 조합 수
- 전체 한 번에: 6 × 9 × 12 = **648개** (과적합 위험!)
- 단계적: 6 + 9 + 12 = **27개** (안전)
```

**Validation 과적합 감지**:
```python
def detect_validation_overfit(
    train_score: float,
    val_score: float,
    test_score: float,
    threshold: float = 0.2  # 20% 차이
) -> bool:
    """
    Validation 과적합 감지
    
    기준:
    - Train >> Val: 정상 (Train에 과적합)
    - Val >> Test: 위험 (Validation에 과적합)
    """
    val_test_gap = (val_score - test_score) / val_score
    
    if val_test_gap > threshold:
        logger.warning(
            f"Validation 과적합 의심!\n"
            f"Val 점수: {val_score:.4f}\n"
            f"Test 점수: {test_score:.4f}\n"
            f"격차: {val_test_gap*100:.1f}% > {threshold*100:.1f}%"
        )
        return True
    
    return False
```

---

## 4. 로그·메트릭 관련

### 4-1. 성과 지표 계산 위치 중복 - ✅ 전면 수용

#### 비판 내용
```
BacktestEngine.get_performance_metrics()
core/metrics/performance.py
→ 둘 다 성과 지표 다룸
→ 어느 쪽이 진짜 소스인지 헷갈림
→ 수정 시 두 군데 모두 수정 필요
```

#### 수용 및 수정안

**현재 구조 (중복)**:
```python
# core/engine/backtest.py
class BacktestEngine:
    def get_performance_metrics(self):
        # ❌ 여기서 직접 계산
        cagr = self._calculate_cagr(...)
        sharpe = self._calculate_sharpe(...)
        ...

# core/metrics/performance.py
def calc_cagr(...):
    # ❌ 여기서도 계산
    ...
```

**수정안: Single Source of Truth**
```python
# core/engine/backtest.py
class BacktestEngine:
    def get_performance_metrics(self) -> Dict[str, float]:
        """
        성과 지표 계산
        
        Note: 실제 계산은 core/metrics/performance.py에 위임
        """
        from core.metrics.performance import (
            calc_cagr,
            calc_sharpe_ratio,
            calc_max_drawdown,
            calc_sortino_ratio
        )
        
        if not self.nav_history:
            return {}
        
        # NAV 시계열
        nav_series = pd.Series([nav for _, nav in self.nav_history])
        returns_series = pd.Series(self.daily_returns)
        
        # ✅ 모든 계산을 performance.py에 위임
        metrics = {
            'total_return_net': (nav_series.iloc[-1] / self.initial_capital - 1.0) * 100,
            'cagr_net': calc_cagr(nav_series, self.initial_capital),
            'sharpe_ratio_net': calc_sharpe_ratio(returns_series),
            'max_drawdown_net': calc_max_drawdown(nav_series),
            'sortino_ratio_net': calc_sortino_ratio(returns_series),
            'volatility_net': returns_series.std() * np.sqrt(252) * 100,
            
            # 거래 요약
            'total_trades': len(self.portfolio.trades),
            'total_turnover': self._calculate_turnover(),  # 엔진 내부 데이터 필요
            'avg_holding_period': self._calculate_avg_holding_period(),
            
            'final_value': nav_series.iloc[-1]
        }
        
        return metrics

# core/metrics/performance.py
def calc_cagr(nav_series: pd.Series, initial_capital: float) -> float:
    """✅ 유일한 CAGR 계산 함수"""
    ...

def calc_sharpe_ratio(returns_series: pd.Series, risk_free_rate: float = 0.0) -> float:
    """✅ 유일한 Sharpe 계산 함수"""
    ...
```

**원칙**:
```markdown
### 성과 지표 계산 원칙

#### Single Source of Truth
- **모든 지표 계산은 `core/metrics/performance.py`에만 존재**
- `BacktestEngine`은 데이터만 제공하고 계산은 위임

#### 엔진의 역할
- NAV 시계열 생성
- 일별 수익률 계산
- 거래 기록 관리
- **지표 계산은 하지 않음** (위임만)

#### performance.py의 역할
- 순수 함수로 지표 계산
- 입력: 시계열 데이터
- 출력: 지표 값
- 엔진 의존성 없음
```

---

### 4-2. Gross vs Net 구현 난이도 - ✅ 전면 수용

#### 비판 내용
```
"Gross = 비용 미반영, Net = 비용 반영"
→ 현재 엔진은 NAV 자체가 이미 Net (비용 차감됨)
→ Gross를 알려면 "가상 포트폴리오" 병렬 실행 필요
→ 단순히 지표 계산 함수 두 번 돌린다고 해결 안 됨
→ 구현 난이도 과소평가
```

#### 수용 및 수정안

**기존 설계 (과소평가)**:
```python
# ❌ 이렇게 간단하지 않음
if track_gross_metrics:
    metrics['cagr_gross'] = calc_cagr(nav_series_gross)
    metrics['cagr_net'] = calc_cagr(nav_series_net)
```

**현실: 병렬 추적 필요**
```python
class BacktestEngine:
    def __init__(
        self,
        ...,
        track_gross_metrics: bool = False
    ):
        # Net 포트폴리오 (기본)
        self.portfolio = Portfolio(cash=initial_capital)
        self.nav_history: List[Tuple[date, float]] = []
        
        # ✅ Gross 포트폴리오 (병렬)
        if track_gross_metrics:
            self.portfolio_gross = Portfolio(cash=initial_capital)
            self.nav_history_gross: List[Tuple[date, float]] = []
            self.total_costs: float = 0.0
    
    def execute_buy(self, symbol, quantity, price, trade_date):
        """매수 실행 (Net + Gross 병렬)"""
        # Net 포트폴리오 (비용 차감)
        adjusted_price = self.calculate_slippage(price, 'BUY')
        commission = self.calculate_commission(quantity * adjusted_price)
        self.portfolio.cash -= (quantity * adjusted_price + commission)
        
        # ✅ Gross 포트폴리오 (비용 미차감)
        if self.track_gross_metrics:
            self.portfolio_gross.cash -= (quantity * price)  # 원가만
            self.total_costs += commission  # 비용 누적
        
        ...
    
    def update_nav(self, current_date, current_prices):
        """NAV 업데이트 (Net + Gross 병렬)"""
        # Net NAV
        position_value = sum(...)
        total_value_net = self.portfolio.cash + position_value
        self.nav_history.append((current_date, total_value_net))
        
        # ✅ Gross NAV
        if self.track_gross_metrics:
            position_value_gross = sum(...)
            total_value_gross = self.portfolio_gross.cash + position_value_gross
            self.nav_history_gross.append((current_date, total_value_gross))
```

**구현 복잡도 재평가**:
```markdown
### Gross/Net 구분 구현

#### 기존 예상
- 난이도: ⭐⭐ (쉬움)
- 작업량: 지표 계산 함수 두 번 호출

#### 실제
- 난이도: ⭐⭐⭐ (중간)
- 작업량:
  1. Gross 포트폴리오 병렬 추적
  2. 모든 거래 함수에서 Gross 업데이트
  3. NAV 업데이트 함수 수정
  4. 메모리 사용량 약 2배
  5. 연산량 약 1.5배

#### 대안: 간소화
- Gross는 "사후 재구성"으로 계산
- 거래 로그에서 비용 합산 후 Net NAV에 더하기
- 정확도는 약간 떨어지지만 구현 간단
```

**간소화 구현**:
```python
def get_performance_metrics(self):
    """성과 지표 계산 (Gross 간소화)"""
    # Net 지표 (기본)
    nav_series_net = pd.Series([nav for _, nav in self.nav_history])
    metrics = {
        'cagr_net': calc_cagr(nav_series_net, self.initial_capital),
        ...
    }
    
    # ✅ Gross 지표 (간소화: 사후 재구성)
    if self.track_gross_metrics:
        # 총 비용 계산
        total_costs = sum(
            trade.commission + trade.tax
            for trade in self.portfolio.trades
        )
        
        # Gross NAV = Net NAV + 총 비용
        nav_series_gross = nav_series_net + total_costs
        
        metrics['cagr_gross'] = calc_cagr(nav_series_gross, self.initial_capital)
        metrics['total_costs'] = total_costs
        metrics['cost_drag_annual'] = metrics['cagr_gross'] - metrics['cagr_net']
    
    return metrics
```

---

## 5. 우선순위·일정 부분

### 5-1. 우선순위와 실제 작업 순서 불일치 - ✅ 전면 수용

#### 비판 내용
```
1순위: 거래비용, 2순위: 레짐, 3순위: Train/Val/Test
→ 하지만 Train/Val/Test가 있어야 1·2번 영향 평가 가능
→ "개발 작업 순위"와 "검증 프레임워크 구축 순서" 어긋남
```

#### 수용 및 수정안

**기존 우선순위 (개발 난이도 기준)**:
```
1순위: 거래비용 모델 (쉬움)
2순위: 레짐 스케일링 (쉬움)
3순위: Train/Val/Test (어려움)
```

**수정 우선순위 (검증 안정성 기준)**:
```
0순위: 간단한 Train/Test 분리 (검증 프레임워크)
1순위: 거래비용 모델
2순위: 레짐 스케일링
3순위: Train/Val/Test 고도화
```

**실제 작업 순서**:
```markdown
### Phase 0: 검증 프레임워크 (0.5일)
**목적**: 이후 모든 변경사항을 Train/Test 양쪽에서 검증

#### 구현
```python
# 간단한 Train/Test 분리 (70/30)
def simple_train_test_split(start_date, end_date):
    total_days = (end_date - start_date).days
    train_days = int(total_days * 0.7)
    
    train_end = start_date + timedelta(days=train_days)
    test_start = train_end + timedelta(days=1)
    
    return (start_date, train_end), (test_start, end_date)

# 백테스트 함수
def run_backtest_with_split(price_data, ...):
    (train_start, train_end), (test_start, test_end) = simple_train_test_split(...)
    
    # Train
    train_results = runner.run(price_data, train_start, train_end, ...)
    
    # Test
    test_results = runner.run(price_data, test_start, test_end, ...)
    
    return {
        'train': train_results,
        'test': test_results
    }
```

#### 검증 기준
- Train 성과 > Test 성과 (정상)
- Test 성과가 너무 낮지 않음 (과적합 아님)

---

### Phase 1: 거래비용 모델 (1~2일)
**변경**: 상품별 세율 차별화

#### 검증
```python
# Train/Test 양쪽에서 실행
results_before = run_backtest_with_split(...)  # 거래세 전
results_after = run_backtest_with_split(...)   # 거래세 후

# 비교
print(f"Train CAGR: {results_before['train']['cagr']:.2f}% → {results_after['train']['cagr']:.2f}%")
print(f"Test CAGR: {results_before['test']['cagr']:.2f}% → {results_after['test']['cagr']:.2f}%")
```

---

### Phase 2: 레짐 스케일링 (1~2일)
**변경**: 레짐 비율 적용

#### 검증
```python
# Train/Test 양쪽에서 실행
results_no_regime = run_backtest_with_split(...)  # 레짐 미적용
results_with_regime = run_backtest_with_split(...) # 레짐 적용

# MDD 개선 확인
print(f"Train MDD: {results_no_regime['train']['mdd']:.2f}% → {results_with_regime['train']['mdd']:.2f}%")
print(f"Test MDD: {results_no_regime['test']['mdd']:.2f}% → {results_with_regime['test']['mdd']:.2f}%")
```

---

### Phase 3: Train/Val/Test 고도화 (2~3일)
**변경**: Validation 추가, 파라미터 그리드 서치

#### 구현
- `TrainValTestSplitter` (3분할)
- `ParameterGridSearch` (단계적 튜닝)
- 레짐 균형 검증
- Validation 과적합 감지
```

---

## 📊 최종 수정 요약

### 전면 수용 (8개)
1. ✅ 상품별 세율 차별화 (`instrument_type` 추가)
2. ✅ 레짐 "검증됨" 표현 수정 (명확화)
3. ✅ 120% 포지션 레버리지 처리 (`enable_leverage` 플래그)
4. ✅ 최소 데이터 길이 검증 (Train 2년, Val/Test 6개월)
5. ✅ 파라미터 튜닝 단계화 (한 번에 2~3개)
6. ✅ Gross/Net 구현 난이도 재평가 (간소화 대안)
7. ✅ 성과 지표 Single Source of Truth
8. ✅ 작업 순서 재조정 (Phase 0 추가)

### 부분 수용 (2개)
1. ⚠️ 슬리피지 근거 보강 (경험적 추정 + 검증 계획)
2. ⚠️ Neutral 시간 축 (2단계 계획으로 명시)

### 반박 (0개)
- 모든 지적이 타당함

---

## 🚀 다음 단계

1. **Part 1, 2, Summary 문서 업데이트**
   - 수정안 반영
   - 명확한 표현으로 개선

2. **구현 시작**
   - Phase 0: 간단한 Train/Test 분리
   - Phase 1: 거래비용 모델
   - Phase 2: 레짐 스케일링
   - Phase 3: Train/Val/Test 고도화

3. **단계별 검증**
   - 모든 변경사항을 Train/Test 양쪽에서 검증
   - 과적합 여부 확인
