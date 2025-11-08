# 방어 시스템 설계

**작성일**: 2025-11-08  
**목적**: MDD -23.5% → -10~12% 감소  
**방법**: 자동 손절 시스템 구현

---

## 🎯 설계 목표

### 핵심 목표
1. **MDD 감소**: -23.5% → -10~12%
2. **수익률 유지**: CAGR 30% 이상
3. **Sharpe 유지**: 1.5 이상
4. **자동화**: 수동 개입 없이 자동 손절

### 설계 원칙
- **보수적 접근**: 손실 최소화 우선
- **명확한 규칙**: 모호함 없는 손절 조건
- **재진입 가능**: 손절 후 회복 시 재진입
- **백테스트 검증**: 실제 효과 측정

---

## 🔧 손절 시스템 구조

### 3단계 방어 체계

```
┌─────────────────────────────────────────────────────┐
│              방어 시스템 (DefenseSystem)             │
├─────────────────────────────────────────────────────┤
│                                                      │
│  1단계: 개별 종목 손절 (-7%)                         │
│  ├─ 고정 손절: 진입가 대비 -7%                       │
│  └─ 트레일링 스톱: 최고가 대비 -10%                  │
│                                                      │
│  2단계: 포트폴리오 손절 (-15%)                       │
│  ├─ 전체 포트폴리오 가치 -15% 하락                   │
│  └─ 모든 포지션 청산 + 현금 보유                     │
│                                                      │
│  3단계: 재진입 관리                                  │
│  ├─ 쿨다운 기간 (3~5일)                             │
│  ├─ 시장 회복 신호 확인                             │
│  └─ 점진적 재진입                                   │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## 📐 1단계: 개별 종목 손절

### 1.1 고정 손절 (-7%)

#### 개념
- 진입가 대비 -7% 하락 시 자동 매도
- 단순하고 명확한 규칙
- 큰 손실 방지

#### 알고리즘
```python
def check_fixed_stop_loss(position, current_price):
    """
    고정 손절 체크
    
    Args:
        position: 포지션 정보 (entry_price, quantity, ...)
        current_price: 현재 가격
    
    Returns:
        bool: True면 손절 발동
    """
    entry_price = position['entry_price']
    loss_pct = ((current_price / entry_price) - 1.0) * 100
    
    # -7% 이하 하락 시 손절
    if loss_pct <= -7.0:
        return True
    
    return False
```

#### 예시
```
진입가: 10,000원
손절가: 9,300원 (10,000 × 0.93)

현재가 9,200원 → 손절 발동! (-8%)
현재가 9,400원 → 손절 미발동 (-6%)
```

#### 장단점
**장점**:
- 명확한 규칙
- 구현 간단
- 큰 손실 방지

**단점**:
- 일시적 하락에도 손절
- 재진입 비용 발생
- 변동성 큰 종목에 불리

---

### 1.2 트레일링 스톱 (-10%)

#### 개념
- 최고가 대비 -10% 하락 시 매도
- 수익 보호 + 추세 추종
- 상승 시 손절선도 상승

#### 알고리즘
```python
def update_trailing_stop(position, current_price):
    """
    트레일링 스톱 업데이트
    
    Args:
        position: 포지션 정보 (peak_price, trailing_stop_price, ...)
        current_price: 현재 가격
    
    Returns:
        dict: 업데이트된 포지션
    """
    # 최고가 업데이트
    if current_price > position['peak_price']:
        position['peak_price'] = current_price
        # 손절선 업데이트 (최고가의 90%)
        position['trailing_stop_price'] = current_price * 0.90
    
    return position

def check_trailing_stop(position, current_price):
    """
    트레일링 스톱 체크
    
    Args:
        position: 포지션 정보
        current_price: 현재 가격
    
    Returns:
        bool: True면 손절 발동
    """
    trailing_stop_price = position['trailing_stop_price']
    
    # 트레일링 스톱 가격 이하로 하락 시 손절
    if current_price <= trailing_stop_price:
        return True
    
    return False
```

#### 예시
```
진입가: 10,000원
최고가: 12,000원 → 손절선: 10,800원 (12,000 × 0.90)

시나리오 1: 상승 후 하락
- Day 1: 10,000원 (진입) → 손절선: 9,000원
- Day 5: 12,000원 (최고가) → 손절선: 10,800원 (상승!)
- Day 10: 10,700원 → 손절 발동! (10,800원 이하)
- 결과: +7% 수익 실현

시나리오 2: 지속 상승
- Day 1: 10,000원 (진입) → 손절선: 9,000원
- Day 5: 12,000원 → 손절선: 10,800원
- Day 10: 13,000원 (신고가) → 손절선: 11,700원 (계속 상승!)
- 결과: 수익 보호하며 추세 추종
```

#### 장단점
**장점**:
- 수익 보호
- 추세 추종
- 큰 수익 가능

**단점**:
- 구현 복잡
- 변동성에 민감
- 조기 청산 가능

---

### 1.3 하이브리드 손절 (추천)

#### 개념
- 고정 손절 + 트레일링 스톱 결합
- 손실 제한 + 수익 보호

#### 알고리즘
```python
def check_hybrid_stop_loss(position, current_price):
    """
    하이브리드 손절 체크
    
    1. 고정 손절: 진입가 대비 -7%
    2. 트레일링 스톱: 최고가 대비 -10%
    
    둘 중 하나라도 발동 시 손절
    """
    # 1. 고정 손절 체크
    if check_fixed_stop_loss(position, current_price):
        return True, "fixed_stop_loss"
    
    # 2. 트레일링 스톱 체크
    if check_trailing_stop(position, current_price):
        return True, "trailing_stop"
    
    return False, None
```

#### 예시
```
진입가: 10,000원
고정 손절선: 9,300원 (-7%)

시나리오 1: 하락
- Day 1: 10,000원 (진입)
- Day 3: 9,200원 → 고정 손절 발동! (-8%)
- 결과: -7% 손실 제한

시나리오 2: 상승 후 하락
- Day 1: 10,000원 (진입)
- Day 5: 12,000원 (최고가) → 트레일링 손절선: 10,800원
- Day 10: 10,700원 → 트레일링 손절 발동!
- 결과: +7% 수익 실현

시나리오 3: 지속 상승
- Day 1: 10,000원 (진입)
- Day 10: 13,000원 → 트레일링 손절선: 11,700원
- 결과: 수익 보호하며 보유 지속
```

---

## 📐 2단계: 포트폴리오 손절

### 2.1 포트폴리오 손절 (-15%)

#### 개념
- 전체 포트폴리오 가치 -15% 하락 시
- 모든 포지션 청산
- 시장 급락 대응

#### 알고리즘
```python
def check_portfolio_stop_loss(
    current_portfolio_value,
    peak_portfolio_value,
    threshold=-15.0
):
    """
    포트폴리오 손절 체크
    
    Args:
        current_portfolio_value: 현재 포트폴리오 가치
        peak_portfolio_value: 최고 포트폴리오 가치
        threshold: 손절 임계값 (%)
    
    Returns:
        bool: True면 손절 발동
    """
    if peak_portfolio_value <= 0:
        return False
    
    # 손실률 계산
    loss_pct = ((current_portfolio_value / peak_portfolio_value) - 1.0) * 100
    
    # -15% 이하 하락 시 손절
    if loss_pct <= threshold:
        return True
    
    return False

def execute_portfolio_stop_loss(positions, current_prices):
    """
    포트폴리오 손절 실행
    
    모든 포지션 청산
    """
    trades = []
    total_cash = 0
    
    for ticker, position in positions.items():
        shares = position['quantity']
        price = current_prices.get(ticker, 0)
        
        if price > 0:
            sell_amount = shares * price
            total_cash += sell_amount
            
            trades.append({
                'ticker': ticker,
                'action': 'SELL',
                'shares': shares,
                'price': price,
                'reason': 'portfolio_stop_loss'
            })
    
    # 모든 포지션 청산
    positions.clear()
    
    return positions, total_cash, trades
```

#### 예시
```
초기 자본: 10,000,000원
최고 가치: 12,000,000원
손절선: 10,200,000원 (12,000,000 × 0.85)

시나리오 1: 시장 급락
- Day 1: 10,000,000원 (시작)
- Day 30: 12,000,000원 (최고가)
- Day 35: 10,100,000원 → 포트폴리오 손절 발동! (-15.8%)
- 결과: 모든 포지션 청산, 현금 보유

시나리오 2: 정상 변동
- Day 1: 10,000,000원 (시작)
- Day 30: 12,000,000원 (최고가)
- Day 35: 11,000,000원 → 손절 미발동 (-8.3%)
- 결과: 포지션 유지
```

#### 장단점
**장점**:
- 시장 급락 대응
- 큰 손실 방지
- 심리적 안정

**단점**:
- 일시적 하락에도 청산
- 재진입 어려움
- 기회 손실 가능

---

## 📐 3단계: 재진입 관리

### 3.1 쿨다운 기간

#### 개념
- 손절 후 일정 기간 재진입 금지
- 감정적 거래 방지
- 시장 안정화 대기

#### 알고리즘
```python
class CooldownManager:
    """쿨다운 관리자"""
    
    def __init__(self, cooldown_days=3):
        self.cooldown_days = cooldown_days
        self.stop_loss_history = {}  # {ticker: stop_loss_date}
    
    def record_stop_loss(self, ticker, stop_loss_date):
        """손절 기록"""
        self.stop_loss_history[ticker] = stop_loss_date
    
    def can_reenter(self, ticker, current_date):
        """재진입 가능 여부"""
        if ticker not in self.stop_loss_history:
            return True
        
        stop_loss_date = self.stop_loss_history[ticker]
        days_passed = (current_date - stop_loss_date).days
        
        # 쿨다운 기간 경과 시 재진입 가능
        if days_passed >= self.cooldown_days:
            # 기록 삭제
            del self.stop_loss_history[ticker]
            return True
        
        return False
```

#### 예시
```
쿨다운 기간: 3일

시나리오:
- Day 1: 종목 A 손절 (-7%)
- Day 2: 종목 A 매수 신호 → 재진입 불가 (쿨다운 중)
- Day 3: 종목 A 매수 신호 → 재진입 불가 (쿨다운 중)
- Day 4: 종목 A 매수 신호 → 재진입 가능! (쿨다운 종료)
```

---

### 3.2 재진입 조건

#### 개념
- 쿨다운 기간 + 시장 회복 신호
- 안전한 재진입

#### 알고리즘
```python
def check_reentry_conditions(
    ticker,
    current_date,
    cooldown_manager,
    ma_score,
    market_condition
):
    """
    재진입 조건 체크
    
    조건:
    1. 쿨다운 기간 경과
    2. MAPS 점수 양수
    3. 시장 상태 정상
    """
    # 1. 쿨다운 체크
    if not cooldown_manager.can_reenter(ticker, current_date):
        return False, "cooldown"
    
    # 2. MAPS 점수 체크
    if ma_score <= 0:
        return False, "negative_score"
    
    # 3. 시장 상태 체크
    if market_condition == "crash":
        return False, "market_crash"
    
    return True, "ok"
```

---

## 🎯 통합 방어 시스템

### DefenseSystem 클래스 구조

```python
class DefenseSystem:
    """
    통합 방어 시스템
    
    기능:
    1. 개별 종목 손절 (고정 + 트레일링)
    2. 포트폴리오 손절
    3. 재진입 관리
    """
    
    def __init__(
        self,
        # 개별 손절 파라미터
        fixed_stop_loss_pct=-7.0,
        trailing_stop_pct=-10.0,
        
        # 포트폴리오 손절 파라미터
        portfolio_stop_loss_pct=-15.0,
        
        # 재진입 파라미터
        cooldown_days=3,
        
        # 활성화 플래그
        enable_fixed_stop=True,
        enable_trailing_stop=True,
        enable_portfolio_stop=True
    ):
        self.fixed_stop_loss_pct = fixed_stop_loss_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.portfolio_stop_loss_pct = portfolio_stop_loss_pct
        self.cooldown_days = cooldown_days
        
        self.enable_fixed_stop = enable_fixed_stop
        self.enable_trailing_stop = enable_trailing_stop
        self.enable_portfolio_stop = enable_portfolio_stop
        
        # 쿨다운 관리자
        self.cooldown_manager = CooldownManager(cooldown_days)
        
        # 통계
        self.stats = {
            'fixed_stop_count': 0,
            'trailing_stop_count': 0,
            'portfolio_stop_count': 0
        }
    
    def check_individual_stop_loss(self, position, current_price):
        """개별 종목 손절 체크"""
        # 1. 고정 손절
        if self.enable_fixed_stop:
            if check_fixed_stop_loss(position, current_price):
                self.stats['fixed_stop_count'] += 1
                return True, 'fixed_stop_loss'
        
        # 2. 트레일링 스톱
        if self.enable_trailing_stop:
            if check_trailing_stop(position, current_price):
                self.stats['trailing_stop_count'] += 1
                return True, 'trailing_stop'
        
        return False, None
    
    def check_portfolio_stop_loss(
        self,
        current_value,
        peak_value
    ):
        """포트폴리오 손절 체크"""
        if not self.enable_portfolio_stop:
            return False
        
        if check_portfolio_stop_loss(
            current_value,
            peak_value,
            self.portfolio_stop_loss_pct
        ):
            self.stats['portfolio_stop_count'] += 1
            return True
        
        return False
    
    def update_trailing_stops(self, positions, current_prices):
        """트레일링 스톱 업데이트"""
        for ticker, position in positions.items():
            if ticker in current_prices:
                current_price = current_prices[ticker]
                update_trailing_stop(position, current_price)
    
    def can_reenter(self, ticker, current_date):
        """재진입 가능 여부"""
        return self.cooldown_manager.can_reenter(ticker, current_date)
    
    def record_stop_loss(self, ticker, date):
        """손절 기록"""
        self.cooldown_manager.record_stop_loss(ticker, date)
    
    def get_stats(self):
        """통계 조회"""
        return self.stats
```

---

## 📊 예상 효과

### 시뮬레이션 결과 (예상)

| 시나리오 | 방어 없음 | 방어 있음 | 개선 |
|---------|----------|----------|------|
| **MDD** | -23.5% | **-10~12%** | **+50%** |
| **CAGR** | 39.0% | 30~35% | -10~20% |
| **Sharpe** | 1.71 | 1.5~2.0 | 유지 |
| **Win Rate** | ? | 55~60% | +5~10% |

### 트레이드오프

**손실**:
- 수익률 감소 (39% → 30~35%)
- 거래 횟수 증가 (손절 + 재진입)
- 기회 손실 (일시적 하락에도 손절)

**이득**:
- MDD 대폭 감소 (-23.5% → -10~12%)
- 심리적 안정
- 큰 손실 방지
- 안정적 수익

---

## 🧪 테스트 시나리오

### 시나리오 1: 개별 손절 테스트
```
상황: 종목 A가 -8% 하락
예상: 고정 손절 발동, 매도
검증: 손실 -7% 이내 제한
```

### 시나리오 2: 트레일링 스톱 테스트
```
상황: 종목 B가 +20% 상승 후 -12% 하락
예상: 트레일링 스톱 발동, 수익 실현
검증: +8% 수익 확보
```

### 시나리오 3: 포트폴리오 손절 테스트
```
상황: 시장 급락, 포트폴리오 -16% 하락
예상: 포트폴리오 손절 발동, 전체 청산
검증: 손실 -15% 이내 제한
```

### 시나리오 4: 재진입 테스트
```
상황: 손절 후 3일 경과, 매수 신호 발생
예상: 재진입 가능
검증: 쿨다운 정상 작동
```

---

## 📝 구현 체크리스트

### Day 2: 구현 (4시간)
- [ ] `DefenseSystem` 클래스 구현
- [ ] 개별 손절 로직 구현
- [ ] 포트폴리오 손절 로직 구현
- [ ] 트레일링 스톱 로직 구현
- [ ] 쿨다운 관리자 구현

### Day 3: 통합 (2시간)
- [ ] Jason 어댑터에 통합
- [ ] 백테스트 실행
- [ ] 결과 분석

### Day 4: 검증 (2시간)
- [ ] 단위 테스트 작성
- [ ] 통합 테스트 작성
- [ ] MDD 감소 확인

---

## 🎯 완료 기준

### 필수
- [x] 손절 로직 설계 완료
- [x] 알고리즘 의사코드 작성
- [x] 파라미터 정의
- [x] 테스트 시나리오 정의

### 다음 단계
- [ ] DefenseSystem 클래스 구현
- [ ] Jason 어댑터 통합
- [ ] 백테스트 실행 및 검증

---

**설계 완료**: 2025-11-08  
**다음 작업**: Day 2 - 구현  
**예상 시간**: 4시간
