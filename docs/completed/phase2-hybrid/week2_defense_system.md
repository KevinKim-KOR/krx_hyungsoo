# Week 2: 방어 시스템 구현

**기간**: 2025-11-08 ~ 2025-11-14  
**목표**: MDD를 -23.5% → -10~12%로 감소  
**예상 시간**: 9시간 (평일 저녁 2시간 × 4일 + 주말 1시간)

---

## 🎯 목표

### 주요 목표
1. 자동 손절 시스템 구현 (개별 -7%, 포트폴리오 -15%)
2. 시장 급락 감지 시스템
3. 변동성 기반 포지션 관리
4. MDD 감소 효과 검증

### 성공 기준
- ✅ 손절 로직 정상 작동
- ✅ 백테스트에서 MDD -23.5% → -10~12% 감소
- ✅ 수익률 유지 (CAGR 30% 이상)
- ✅ Sharpe Ratio 유지 또는 개선 (1.5 이상)

---

## 📋 작업 체크리스트

### Day 1: 자동 손절 시스템 설계 (2시간)

#### 손절 로직 설계
- [ ] 개별 종목 손절 (-7%)
  - 진입가 대비 -7% 하락 시 자동 매도
  - 트레일링 스톱 (최고가 대비 -10%)
  
- [ ] 포트폴리오 손절 (-15%)
  - 전체 포트폴리오 가치 -15% 하락 시
  - 모든 포지션 청산 및 현금 보유
  
- [ ] 손절 후 재진입 로직
  - 쿨다운 기간 (3~5일)
  - 시장 회복 신호 확인

#### 설계 문서 작성
```
docs/defense_system_design.md
- 손절 로직 상세
- 트레일링 스톱 알고리즘
- 재진입 조건
```

---

### Day 2: 손절 시스템 구현 (4시간)

#### 파일 생성
```python
# core/strategy/defense_system.py

class DefenseSystem:
    """방어 시스템"""
    
    def __init__(
        self,
        individual_stop_loss: float = -7.0,
        portfolio_stop_loss: float = -15.0,
        trailing_stop_pct: float = -10.0,
        cooldown_days: int = 3
    ):
        pass
    
    def check_individual_stop_loss(
        self,
        position,
        current_price: float
    ) -> bool:
        """개별 종목 손절 체크"""
        pass
    
    def check_portfolio_stop_loss(
        self,
        portfolio_value: float,
        peak_value: float
    ) -> bool:
        """포트폴리오 손절 체크"""
        pass
    
    def update_trailing_stop(
        self,
        position,
        current_price: float
    ):
        """트레일링 스톱 업데이트"""
        pass
    
    def can_reenter(
        self,
        ticker: str,
        current_date: date
    ) -> bool:
        """재진입 가능 여부"""
        pass
```

#### 구현 체크리스트
- [ ] `DefenseSystem` 클래스 구현
- [ ] 개별 손절 로직
- [ ] 포트폴리오 손절 로직
- [ ] 트레일링 스톱 로직
- [ ] 쿨다운 관리

---

### Day 3: 시장 급락 감지 (3시간)

#### 시장 급락 감지 로직
```python
# core/strategy/market_crash_detector.py

class MarketCrashDetector:
    """시장 급락 감지기"""
    
    def __init__(
        self,
        index_ticker: str = "069500",  # KODEX 200
        crash_threshold: float = -10.0,
        crash_period: int = 5
    ):
        pass
    
    def detect_market_crash(
        self,
        index_data: pd.DataFrame,
        current_date: date
    ) -> bool:
        """시장 급락 감지"""
        # 최근 5일간 -10% 하락 시
        pass
    
    def detect_portfolio_crash(
        self,
        positions: Dict,
        current_prices: Dict
    ) -> bool:
        """보유 종목 동반 하락 감지"""
        # 80% 이상 종목이 하락 중
        pass
```

#### 구현 체크리스트
- [ ] `MarketCrashDetector` 클래스 구현
- [ ] KOSPI 급락 감지 (5일 -10%)
- [ ] 보유 종목 동반 하락 감지 (80% 이상)
- [ ] 급락 시 방어 모드 전환

---

### Day 4: 변동성 관리 (2시간)

#### 변동성 기반 포지션 관리
```python
# core/strategy/volatility_manager.py

class VolatilityManager:
    """변동성 관리자"""
    
    def __init__(
        self,
        volatility_window: int = 20,
        max_volatility: float = 30.0,
        cash_buffer_pct: float = 20.0
    ):
        pass
    
    def calculate_volatility(
        self,
        price_data: pd.DataFrame
    ) -> float:
        """변동성 계산 (표준편차)"""
        pass
    
    def adjust_position_size(
        self,
        base_size: float,
        volatility: float
    ) -> float:
        """변동성 기반 포지션 크기 조절"""
        # 변동성 높을수록 포지션 축소
        pass
    
    def check_cash_buffer(
        self,
        cash: float,
        total_value: float
    ) -> bool:
        """현금 버퍼 확인"""
        # 최소 20% 현금 유지
        pass
```

#### 구현 체크리스트
- [ ] `VolatilityManager` 클래스 구현
- [ ] 변동성 계산 (20일 표준편차)
- [ ] 변동성 기반 포지션 크기 조절
- [ ] 현금 버퍼 관리 (20%)

---

## 🔧 Jason 어댑터 통합

### 방어 시스템 통합
```python
# core/engine/jason_adapter.py 수정

class JasonBacktestAdapter:
    def __init__(
        self,
        # 기존 파라미터...
        enable_defense: bool = True,
        individual_stop_loss: float = -7.0,
        portfolio_stop_loss: float = -15.0
    ):
        # 방어 시스템 초기화
        if enable_defense:
            self.defense_system = DefenseSystem(
                individual_stop_loss=individual_stop_loss,
                portfolio_stop_loss=portfolio_stop_loss
            )
            self.crash_detector = MarketCrashDetector()
            self.volatility_manager = VolatilityManager()
    
    def _simple_maps_backtest(self, ...):
        # 기존 로직...
        
        # 방어 시스템 체크 추가
        if self.enable_defense:
            # 1. 시장 급락 감지
            if self.crash_detector.detect_market_crash(...):
                # 모든 포지션 청산
                pass
            
            # 2. 개별 손절 체크
            for ticker, position in positions.items():
                if self.defense_system.check_individual_stop_loss(...):
                    # 손절 매도
                    pass
            
            # 3. 포트폴리오 손절 체크
            if self.defense_system.check_portfolio_stop_loss(...):
                # 전체 청산
                pass
```

---

## 🧪 테스트 계획

### 단위 테스트
```python
# tests/test_defense_system.py

def test_individual_stop_loss():
    """개별 손절 테스트"""
    defense = DefenseSystem(individual_stop_loss=-7.0)
    
    # 진입가 10,000원, 현재가 9,200원 (-8%)
    assert defense.check_individual_stop_loss(
        position={'entry_price': 10000},
        current_price=9200
    ) == True  # 손절 발동
    
    # 진입가 10,000원, 현재가 9,400원 (-6%)
    assert defense.check_individual_stop_loss(
        position={'entry_price': 10000},
        current_price=9400
    ) == False  # 손절 미발동

def test_portfolio_stop_loss():
    """포트폴리오 손절 테스트"""
    defense = DefenseSystem(portfolio_stop_loss=-15.0)
    
    # Peak 10,000,000원, 현재 8,400,000원 (-16%)
    assert defense.check_portfolio_stop_loss(
        portfolio_value=8400000,
        peak_value=10000000
    ) == True  # 손절 발동

def test_trailing_stop():
    """트레일링 스톱 테스트"""
    defense = DefenseSystem(trailing_stop_pct=-10.0)
    
    # 진입가 10,000원, 최고가 12,000원, 현재가 10,700원
    # 최고가 대비 -10.8% → 손절 발동
    pass
```

### 통합 테스트
```python
# tests/test_defense_integration.py

def test_backtest_with_defense():
    """방어 시스템 포함 백테스트"""
    adapter = JasonBacktestAdapter(
        enable_defense=True,
        individual_stop_loss=-7.0,
        portfolio_stop_loss=-15.0
    )
    
    results = adapter.run(price_data, strategy)
    
    # MDD 감소 확인
    assert results['max_drawdown'] > -15.0  # -23.5% → -15% 이내
    
    # 수익률 유지 확인
    assert results['cagr'] > 30.0  # 30% 이상 유지
```

---

## 📊 예상 결과

### 목표 지표
| 지표 | Week 1 (방어 없음) | Week 2 (방어 포함) | 목표 |
|------|-------------------|-------------------|------|
| **CAGR** | 39.02% | 30~35% | 30% 이상 |
| **Sharpe** | 1.71 | 1.5~2.0 | 1.5 이상 |
| **MDD** | -23.51% | **-10~12%** | **-15% 이내** |
| **Win Rate** | ? | 55~60% | 55% 이상 |

### 트레이드오프
- **수익률 감소**: 39% → 30~35% (손절로 인한 기회 손실)
- **리스크 감소**: MDD -23.5% → -10~12% (안정성 대폭 개선)
- **Sharpe 유지**: 1.71 → 1.5~2.0 (위험 대비 수익 유지)

---

## 🎯 완료 기준

### 필수 (Must Have)
- [x] 손절 로직 구현 완료
- [ ] 시장 급락 감지 구현 완료
- [ ] 변동성 관리 구현 완료
- [ ] Jason 어댑터 통합 완료
- [ ] 백테스트 실행 및 MDD 감소 확인

### 선택 (Nice to Have)
- [ ] VIX 지수 연동
- [ ] 섹터 분산 체크
- [ ] 동적 손절 라인 조정

---

## 📝 다음 단계

Week 2 완료 후:
1. **Week 3**: 하이브리드 전략 구현
   - 시장 상태 감지 (상승/하락/중립)
   - Jason 공격 로직 + 방어 시스템 결합
   - 상황별 전략 전환

2. **Week 4**: 자동화 시스템
   - 자동 모니터링
   - 알림 시스템
   - 리포트 자동화

---

## 💡 참고 자료

### 손절 전략
- **고정 손절**: 진입가 대비 -7%
- **트레일링 스톱**: 최고가 대비 -10%
- **포트폴리오 손절**: 전체 -15%

### 시장 급락 정의
- **KOSPI 급락**: 5일간 -10% 이상
- **동반 하락**: 보유 종목 80% 이상 하락
- **방어 모드**: 현금 비중 80% 이상 유지

### 변동성 관리
- **변동성 계산**: 20일 표준편차
- **포지션 조절**: 변동성 높을수록 축소
- **현금 버퍼**: 최소 20% 유지

---

**시작일**: 2025-11-08 (금요일 저녁)  
**완료 예정**: 2025-11-14 (목요일)  
**담당**: 본인  
**상태**: ⏳ 대기 중

---

## 🚀 시작 준비

### 다음 세션 시작 시
1. 이 문서 재확인
2. Week 1 결과 분석 (MDD -23.5%)
3. Day 1 손절 로직 설계 시작

**화이팅!** 💪
