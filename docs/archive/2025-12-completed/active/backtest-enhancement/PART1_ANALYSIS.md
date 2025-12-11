# 백테스트 엔진 고도화 설계 - Part 1: 현황 분석 및 비판적 검토

**작성일**: 2025-11-29  
**목적**: 거래비용·슬리피지 반영 + 레짐 노출 스케일링 + Train/Val/Test 파이프라인 구축  
**원칙**: 비판적 시각, 단계별 테스트, 클린 코드, 기존 코드 활용

---

## 📋 목차

1. [현황 분석](#1-현황-분석)
2. [요구사항 비판적 검토](#2-요구사항-비판적-검토)
3. [영향도 분석](#3-영향도-분석)

---

## 1. 현황 분석

### 1.1 기존 백테스트 엔진 구조

**파일**: `core/engine/backtest.py` (372줄)

#### ✅ 이미 잘 구현된 부분

**거래비용 모델**:
```python
class BacktestEngine:
    def __init__(
        self,
        commission_rate: float = 0.00015,  # ✅ 수수료 파라미터화
        slippage_rate: float = 0.001,      # ✅ 슬리피지 파라미터화
        ...
    ):
        ...
    
    def calculate_commission(self, amount: float) -> float:
        """✅ 수수료 계산 - 이미 구현"""
        return amount * self.commission_rate
    
    def calculate_slippage(self, price: float, action: str) -> float:
        """✅ 슬리피지 적용 - 이미 구현"""
        if action == 'BUY':
            return price * (1 + self.slippage_rate)
        else:
            return price * (1 - self.slippage_rate)
    
    def execute_buy(self, ...):
        """✅ 매수 실행 - 수수료·슬리피지 반영됨"""
        adjusted_price = self.calculate_slippage(price, 'BUY')
        commission = self.calculate_commission(quantity * adjusted_price)
        self.portfolio.cash -= (quantity * adjusted_price + commission)
        ...
```

**성과 지표**:
```python
def get_performance_metrics(self) -> Dict[str, float]:
    """✅ 성과 지표 계산 - 이미 구현"""
    return {
        'total_return': ...,
        'annual_return': ...,
        'volatility': ...,
        'sharpe_ratio': ...,
        'max_drawdown': ...,
        'win_rate': ...,
        'total_trades': len(self.portfolio.trades),  # ✅ 거래 횟수
        'final_value': ...
    }
```

**레짐 엔진**: `core/strategy/market_regime_detector.py` (349줄)

**현재 상태**:
- ✅ 레짐 감지 로직: 구현 및 테스트 완료
- ✅ 포지션 비율 계산: `get_position_ratio()` 구현 완료
- ❌ **포트폴리오 적용: 미구현** (가장 심각!)

```python
class MarketRegimeDetector:
    def detect_regime(self, market_data, current_date) -> Tuple[str, float]:
        """레짐 감지: bull/bear/neutral + 신뢰도"""
        ...
    
    def get_position_ratio(self, regime, confidence) -> float:
        """포지션 비율 계산 (현재 미사용!)"""
        if regime == 'bull':
            return 1.0 + (confidence - 0.5) * 0.4  # 100~120%
        elif regime == 'bear':
            return 0.6 - (confidence - 0.5) * 0.4  # 40~60%
        else:
            return 0.8  # 80%
```

**Week 3 성과 (MDD -19.92%)의 진실**:
- 레짐 감지는 했지만 **포지션 조절은 안 함**
- 즉, 레짐과 무관하게 **항상 100% 포지션 유지**
- Week 3 성과는 **레짐 엔진 덕이 아님**

---

### 1.2 기존 구현의 한계 (비판적 분석)

#### ❌ 문제 1: 거래세(tax) 미반영 및 상품별 차별화 부족

```python
def execute_sell(self, ...):
    commission = self.calculate_commission(...)  # 수수료만
    # ❌ 거래세 없음
    # ❌ ETF/주식 구분 없음
```

**비판**:
- 한국 주식 거래세 0.23%는 **수수료(0.015%)보다 15배 큼**
- **하지만 ETF는 대부분 거래세 면제**
- 현재는 거래세 자체가 없어서 **과대평가된 수익률**
- 일괄 0.23% 적용 시 **ETF 성과를 과도하게 깎음**

**올바른 설계**:
- 주식/리츠: 0.23% 거래세
- ETF: 0% (면제)
- 레버리지 ETF: 0% (면제)

**영향도**: ⭐⭐⭐⭐⭐ (매우 높음)

---

#### ❌ 문제 2: Gross vs Net 구분 없음

```python
def get_performance_metrics(self):
    return {
        'total_return': ...,  # ❌ Gross인지 Net인지 불명확
        'sharpe_ratio': ...   # ❌ Gross인지 Net인지 불명확
    }
```

**비판**:
- 현재는 Net만 계산 (비용 반영됨)
- Gross 성과를 알 수 없어 **비용 영향 분석 불가**
- "비용이 성과를 얼마나 깎아먹는가?" → **분석 불가**

**예시**:
```
Gross CAGR: 28.5%
Net CAGR:   27.0%
Cost Drag:  -1.5% (연간)

→ 거래 빈도를 줄이면 성과 개선 가능
```

**영향도**: ⭐⭐⭐⭐ (높음)

---

#### ❌ 문제 3: 거래 요약 통계 부족

```python
def get_performance_metrics(self):
    return {
        'total_trades': len(self.portfolio.trades),  # ✅ 거래 횟수만
        # ❌ total_turnover 없음
        # ❌ avg_holding_period 없음
    }
```

**비판**:
- `total_trades`만으로는 **거래 강도 파악 불가**
- **Turnover** = 총 거래금액 / 평균 자산 (연율화)
  - 예: Turnover 5.0 = 1년에 5번 전체 자산 회전
- **보유 기간** = 평균 포지션 유지 일수
  - 예: 평균 7일 보유 = 단기 매매

**이 지표들이 없으면**:
- 과도한 거래 여부 판단 불가
- 거래 비용 최적화 불가

**영향도**: ⭐⭐⭐ (중간)

---

#### ❌ 문제 4: 레짐 노출 스케일링 미적용 (가장 심각!)

```python
# extensions/backtest/runner.py
def run(self, ...):
    # ✅ 레짐 감지는 함
    regime, confidence = self.regime_detector.detect_regime(...)
    
    # ❌ 하지만 사용 안 함!
    target_weights = self._generate_target_weights(...)
    self.engine.rebalance(target_weights, ...)  # 항상 100% 포지션
```

**비판**:
- `MarketRegimeDetector.get_position_ratio()`는 **계산만 하고 사용 안 함**
- 레짐이 'bear'여도 100% 포지션 유지
- **레짐 엔진이 무용지물**
- **Week 3 성과(MDD -19.92%)는 레짐 덕이 아님**

**실제 영향**:
```
현재 (레짐 미반영):
- Bull 레짐: 100% 포지션
- Bear 레짐: 100% 포지션  ← 문제!
- MDD: -19.92%

레짐 반영 시:
- Bull 레짐: 120% 포지션
- Bear 레짐: 40% 포지션  ← 방어!
- MDD: -15% (예상)
```

**영향도**: ⭐⭐⭐⭐⭐ (최고)

---

#### ❌ 문제 5: Train/Val/Test 분리 없음

```python
# 현재: 전체 기간 한 번에 백테스트
adapter.run(
    price_data=price_data,
    start_date=date(2022, 1, 1),  # ❌ 전체 기간
    end_date=date.today()
)
```

**비판**:
- **과최적화(Overfitting) 위험**
- Train에서 찾은 파라미터가 Test에서 실패할 수 있음
- Walk-forward 검증 없음

**예시**:
```
전체 기간 백테스트:
- Sharpe: 1.51 (좋아 보임)
- 하지만 실전에서: 0.8 (실패)

Train/Val/Test 분리:
- Train: 파라미터 탐색
- Val: 최적 파라미터 선택
- Test: 실전 성과 예측 (신뢰도 높음)
```

**영향도**: ⭐⭐⭐⭐⭐ (최고)

---

#### ❌ 문제 6: 분석용 로그 부족

```python
self.nav_history: List[Tuple[date, float]] = []  # ✅ NAV만
# ❌ regime_label 없음
# ❌ equity/bond/cash exposure 없음
# ❌ 트레이드 로그 상세 정보 부족
```

**비판**:
- NAV만으로는 **왜 그런 성과가 나왔는지 분석 불가**
- "어떤 레짐에서 손실이 컸는가?" → 분석 불가
- "현금 비중이 적절했는가?" → 분석 불가

**필요한 로그**:
```python
daily_log = pd.DataFrame({
    'date': [...],
    'nav': [...],
    'regime': ['bull', 'bear', ...],
    'equity_exposure': [0.8, 0.4, ...],  # 주식 비중
    'cash_exposure': [0.2, 0.6, ...],    # 현금 비중
})

trade_log = pd.DataFrame({
    'date': [...],
    'ticker': [...],
    'side': ['BUY', 'SELL', ...],
    'qty': [...],
    'price_gross': [...],  # Gross 가격
    'price_net': [...],    # Net 가격 (비용 포함)
    'fee': [...],
    'slippage': [...]
})
```

**영향도**: ⭐⭐⭐ (중간)

---

## 2. 요구사항 비판적 검토

### 2.1 1단계: 거래비용·슬리피지 모델 추가

**요구사항**:
```
commission_rate : 수수료 (편도, 예: 0.00015)
tax_rate : 거래세 (매도 시, 예: 0.0023)
slippage_bps : 슬리피지 (bps 단위, 예: 5 → 0.0005)
```

#### ✅ 좋은 점:
1. **거래세 추가**: 한국 시장 현실 반영
2. **Config 기반**: 하드코딩 방지
3. **자산별 차별화**: ETF/주식/채권 다른 비용

#### ⚠️ 우려사항:

**1) 슬리피지 모델 단순함**:
```python
# 현재 요구: 고정 비율
slippage = price * slippage_rate

# 현실: 거래량·변동성 의존
# - 거래량 많으면 슬리피지 작음
# - 변동성 크면 슬리피지 큼
```

**제안**: 
- 1단계: 고정 비율 (간단)
- 2단계: 동적 슬리피지 (고급, 선택)

**2) Gross/Net 계산 비용**:
```python
# 모든 지표를 Gross/Net 두 번 계산하면 연산량 2배
# 필요한가?
```

**제안**: 
- Net만 계산 (기본)
- Gross는 **비용 영향 분석 시에만** 계산 (선택)
- `track_gross_metrics=True` 플래그로 제어

**3) 거래 요약 통계 계산 복잡도**:
```python
# total_turnover 계산
# - 모든 거래 금액 합산: O(n)
# - 일별 자산 평균 계산: O(n)
# 
# avg_holding_period 계산
# - 매수-매도 쌍 찾기: O(n²) (최악)
```

**제안**: 
- 백테스트 중 누적 계산 (효율적)
- 딕셔너리로 매수-매도 쌍 추적: O(n)

#### 🎯 최종 판단:
- **필요성**: ⭐⭐⭐⭐⭐ (5/5) - 필수
- **구현 난이도**: ⭐⭐ (2/5) - 쉬움 (상품별 분기 추가)
- **영향도**: ⭐⭐⭐⭐ (4/5) - 높음 (성과 지표 변경)
- **우선순위**: **1순위** (단, Phase 0 이후)

---

### 2.2 2단계: 리밸런싱·파라미터 프레임워크 정리

**요구사항**:
```
"함수 시그니처는 그대로, 안에 파라미터만 갈아끼우는 구조"
```

#### ✅ 좋은 점:
1. **확장성**: 새 전략 추가 용이
2. **테스트 용이**: 파라미터만 바꿔서 테스트
3. **Config 기반**: 코드 수정 없이 파라미터 변경

#### ⚠️ 우려사항:

**1) 과도한 추상화 위험**:
```python
# ❌ 나쁜 예: 모든 것을 파라미터로
def rebalance(
    self,
    target_weights,
    current_prices,
    trade_date,
    rebalance_method='equal_weight',  # 너무 많음
    weight_adjustment='none',
    position_sizing='fixed',
    risk_parity=False,
    ...  # 10개 이상
):
    ...
```

**제안**: 
- 핵심 파라미터만 노출 (3~5개)
- 나머지는 전략 클래스 내부로

**2) 현재 구조 이미 좋음**:
```python
# 현재 구조
class BacktestEngine:
    def __init__(
        self,
        commission_rate,  # ✅ 이미 파라미터화
        slippage_rate,    # ✅ 이미 파라미터화
        max_positions,    # ✅ 이미 파라미터화
        ...
    ):
        ...

# ✅ 이미 잘 되어 있음!
```

**제안**: 
- 큰 변경 불필요
- Config 연결만 추가

#### 🎯 최종 판단:
- **필요성**: ⭐⭐⭐ (3/5) - 선택적
- **구현 난이도**: ⭐ (1/5) - 매우 쉬움 (이미 구현됨)
- **영향도**: ⭐⭐ (2/5) - 낮음
- **우선순위**: **4순위** (낮음)

---

### 2.3 3단계: 레짐 엔진 + 노출 스케일링

**요구사항**:
```
"레짐 점수에 따라 공격/중립/방어 비중을 계단식으로 조절"
```

#### ✅ 좋은 점:
1. **이미 구현됨**: `MarketRegimeDetector.get_position_ratio()`
2. **검증됨**: Week 3에서 MDD -19.92% 달성
3. **Config 기반**: `regime_params.yaml`

#### ⚠️ 우려사항:

**1) 현재 미사용 (가장 심각!)**:
```python
# core/engine/backtest.py
def rebalance(self, target_weights, ...):
    # ❌ get_position_ratio() 호출 안 함
    target_value = total_value * target_weight  # 항상 100%
```

**문제**: 레짐 엔진이 있지만 **연결 안 됨**

**2) 계단식 vs 연속식**:
```python
# 현재: 연속식 (Continuous)
def get_position_ratio(self, regime, confidence):
    if regime == 'bull':
        return 1.0 + (confidence - 0.5) * 0.4  # 100~120%

# 요구: 계단식 (Discrete)
def get_position_ratio_discrete(self, regime, confidence):
    if regime == 'bull':
        if confidence > 0.8:
            return 1.2  # 공격
        elif confidence > 0.6:
            return 1.0  # 중립
        else:
            return 0.8  # 방어
```

**제안**: 
- 연속식 유지 (더 부드러움)
- 계단식은 **선택 옵션**으로 추가

**3) 레짐 엔진 통합 위치**:
```python
# 방법 1: BacktestEngine에 통합
class BacktestEngine:
    def __init__(self, ..., regime_detector=None):
        self.regime_detector = regime_detector
    
    def rebalance(self, target_weights, ...):
        if self.regime_detector:
            regime, confidence = self.regime_detector.detect_regime(...)
            position_ratio = self.regime_detector.get_position_ratio(...)
            # 비중 조정

# 방법 2: Runner에서 처리 (권장)
class BacktestRunner:
    def run(self, ...):
        regime, confidence = self.regime_detector.detect_regime(...)
        position_ratio = self.regime_detector.get_position_ratio(...)
        # target_weights 조정 후 engine.rebalance() 호출
```

**제안**: **방법 2 (Runner)** - 관심사 분리

#### 🎯 최종 판단:
- **필요성**: ⭐⭐⭐⭐⭐ (5/5) - 필수 (이미 있지만 미사용)
- **구현 난이도**: ⭐⭐ (2/5) - 쉬움 (연결만 하면 됨)
- **영향도**: ⭐⭐⭐⭐⭐ (5/5) - 매우 높음 (MDD 개선)
- **주의사항**: 120% 포지션(레버리지) 처리 필요
- **우선순위**: **2순위** (Phase 0 이후)

---

### 2.4 4단계: Train/Val/Test 파이프라인

**요구사항**:
```
Train (60%) → Validation (20%) → Test (20%)
```

#### ✅ 좋은 점:
1. **과최적화 방지**: 필수
2. **실전 성과 예측**: Test 결과가 실전과 유사
3. **파라미터 튜닝**: Validation으로 조정

#### ⚠️ 우려사항:

**1) 시계열 데이터 특성**:
```python
# ❌ 나쁜 예: 랜덤 분할
train = data.sample(frac=0.6)
val = data.sample(frac=0.2)
test = data.sample(frac=0.2)

# ✅ 좋은 예: 시간순 분할
train = data['2022-01-01':'2023-06-30']  # 60%
val = data['2023-07-01':'2024-02-29']    # 20%
test = data['2024-03-01':'2024-12-31']   # 20%
```

**중요**: 시계열은 **반드시 시간순 분할**

**2) Walk-Forward 검증 (더 나은 방법)**:
```python
# 고정 분할 (1단계)
Train: 2022-01 ~ 2023-06 (18개월)
Val:   2023-07 ~ 2023-12 (6개월)
Test:  2024-01 ~ 2024-06 (6개월)

# Walk-Forward (2단계)
# Window 1:
Train: 2022-01 ~ 2023-06
Val:   2023-07 ~ 2023-12
Test:  2024-01 ~ 2024-06

# Window 2:
Train: 2022-07 ~ 2024-06
Val:   2024-07 ~ 2024-12
Test:  2025-01 ~ 2025-06
```

**제안**: 
- 1단계: 고정 분할 (간단)
- 2단계: Walk-Forward (고급, 선택)

**3) 데이터 부족 문제**:
```python
# 현재 데이터: 2022-01 ~ 2024-11 (약 3년)
# Train: 1.8년, Val: 0.6년, Test: 0.6년
# 
# 문제: Train 기간이 짧음 (최소 2년 권장)
```

**제안**: 
- 비율 조정: 70% / 15% / 15%
- 또는 데이터 기간 확장 (2020년부터)

**4) 구현 복잡도**:
```python
# 필요한 기능:
# 1. 데이터 분할 함수
# 2. 파라미터 그리드 서치
# 3. Validation 기반 최적 파라미터 선택
# 4. Test 성과 평가
# 5. 결과 비교 리포트
# 
# 예상 코드량: 300~500줄
```

**제안**: 별도 모듈로 분리

#### 🎯 최종 판단:
- **필요성**: ⭐⭐⭐⭐⭐ (5/5) - 필수
- **구현 난이도**: ⭐⭐⭐⭐ (4/5) - 어려움
- **영향도**: ⭐⭐⭐⭐⭐ (5/5) - 매우 높음 (신뢰성)
- **주의사항**: 
  - 최소 데이터 길이 검증 필요 (Train 2년, Val/Test 6개월)
  - 파라미터 튜닝 단계화 (한 번에 2~3개)
  - 레짐 균형 검증
- **우선순위**: **0순위 (간단 버전)** + **3순위 (고도화)**

---

### 2.5 5단계: 분석용 로그 필드 추가

**요구사항**:
```
일자별: date, portfolio_value, regime_label, equity/bond/cash exposure
트레이드: date, ticker, side, qty, price_gross, price_net, fee, slippage
```

#### ✅ 좋은 점:
1. **상세 분석 가능**: 왜 그런 성과가 나왔는지 파악
2. **디버깅 용이**: 문제 발생 시 추적
3. **시각화 가능**: 차트로 표현

#### ⚠️ 우려사항:

**1) 메모리 사용량**:
```python
# 3년 백테스트 = 약 750 거래일
# 일자별 로그: 750 × 10 필드 = 7,500 항목
# 트레이드 로그: 1,400 거래 × 8 필드 = 11,200 항목
# 
# 총: 약 20KB (무시 가능)
```

**판단**: 메모리 문제 없음

**2) 저장 형식**:
```python
# 방법 1: DataFrame (권장)
daily_log = pd.DataFrame([...])

# 방법 2: List of Dict
daily_log = [{'date': ..., ...}, ...]

# 방법 3: Dataclass
@dataclass
class DailyLog:
    date: date
    portfolio_value: float
    ...
```

**제안**: **DataFrame** (분석 용이)

**3) 기존 코드 수정 범위**:
```python
# 수정 필요:
# 1. BacktestEngine.update_nav() - 일자별 로그 추가
# 2. BacktestEngine.execute_buy/sell() - 트레이드 로그 확장
# 3. BacktestEngine.get_performance_metrics() - 로그 반환
# 
# 예상: 50~100줄 수정
```

**판단**: 영향도 중간

#### 🎯 최종 판단:
- **필요성**: ⭐⭐⭐⭐ (4/5) - 중요
- **구현 난이도**: ⭐⭐ (2/5) - 쉬움
- **영향도**: ⭐⭐⭐ (3/5) - 중간 (기존 코드 수정)
- **우선순위**: **5순위** (중간)

---

## 3. 영향도 분석

### 3.1 파일별 영향도

| 파일 | 현재 상태 | 수정 필요 | 영향도 | 비고 |
|------|----------|----------|--------|------|
| `core/engine/backtest.py` | 372줄 | ⭐⭐⭐⭐ | 높음 | 핵심 엔진 |
| `extensions/backtest/runner.py` | 356줄 | ⭐⭐⭐ | 중간 | 레짐 연결 |
| `core/strategy/market_regime_detector.py` | 349줄 | ⭐ | 낮음 | 이미 완성 |
| `core/metrics/performance.py` | 99줄 | ⭐⭐ | 낮음 | 지표 추가 |
| `scripts/dev/phase2/run_backtest_hybrid.py` | 367줄 | ⭐⭐⭐ | 중간 | 실행 스크립트 |
| `config/backtest.yaml` | 신규 | ⭐⭐ | 낮음 | 설정 추가 |
| `extensions/backtest/train_val_test.py` | 신규 | ⭐⭐⭐⭐⭐ | 높음 | 신규 모듈 |

### 3.2 기능별 영향도

| 기능 | 영향 범위 | 하위 호환성 | 테스트 필요 | 우선순위 |
|------|----------|------------|------------|---------|
| 거래세 추가 | `execute_sell()` | ✅ 유지 | ⭐⭐⭐ | 1순위 |
| Gross/Net 구분 | `get_performance_metrics()` | ✅ 유지 | ⭐⭐⭐⭐ | 1순위 |
| 거래 요약 통계 | `get_performance_metrics()` | ✅ 유지 | ⭐⭐ | 1순위 |
| 레짐 노출 스케일링 | `rebalance()` | ⚠️ 변경 | ⭐⭐⭐⭐⭐ | 2순위 |
| Train/Val/Test | 신규 모듈 | ✅ 독립 | ⭐⭐⭐⭐⭐ | 3순위 |
| 분석 로그 | `update_nav()`, `execute_*()` | ✅ 유지 | ⭐⭐⭐ | 5순위 |

### 3.3 위험도 평가

#### 🔴 고위험 (신중히 접근)

**1. 레짐 노출 스케일링**:
- 리밸런싱 로직 변경
- 기존 백테스트 결과 변경
- **대응**: 기존 로직 보존, 옵션으로 추가

**2. Train/Val/Test 파이프라인**:
- 새로운 워크플로우
- 복잡도 증가
- **대응**: 별도 모듈, 기존 코드 영향 최소화

#### 🟡 중위험 (테스트 필수)

**1. Gross/Net 구분**:
- 성과 지표 변경
- 기존 결과와 비교 필요
- **대응**: 기존 지표 유지, 새 지표 추가

**2. 분석 로그 추가**:
- 메모리 사용량 증가 (미미)
- 저장 형식 결정 필요
- **대응**: 옵션으로 추가 (기본 비활성화)

#### 🟢 저위험 (안전)

**1. 거래세 추가**:
- 단순 계산 추가
- 기존 로직 영향 없음
- **대응**: 즉시 적용

**2. Config 연결**:
- 파라미터 외부화
- 기존 기본값 유지
- **대응**: 즉시 적용

---

## 📊 최종 우선순위 (수정)

| 순위 | 단계 | 필요성 | 난이도 | 영향도 | 예상 기간 | 비고 |
|------|------|--------|--------|--------|----------|------|
| **0** | 간단한 Train/Test 분리 | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | 0.5일 | **검증 프레임워크** |
| **1** | 거래비용 모델 (상품별) | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | 1~2일 | ETF/주식 구분 |
| **2** | 레짐 노출 스케일링 | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | 1~2일 | 레버리지 처리 |
| **3** | Train/Val/Test 고도화 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 2~3일 | 단계적 튜닝 |
| **4** | Config 연결 | ⭐⭐⭐ | ⭐ | ⭐⭐ | 0.5일 | - |
| **5** | 분석 로그 추가 | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | 1일 | - |

**총 예상 기간**: 6~9일

**핵심 변경**: Phase 0 추가 - 모든 변경사항을 Train/Test 양쪽에서 검증

---

**다음 문서**: Part 2 - 상세 설계 및 구현 계획
