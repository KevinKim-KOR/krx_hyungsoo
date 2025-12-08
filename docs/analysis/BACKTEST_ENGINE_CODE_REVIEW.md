# 백테스트 엔진 전체 코드 리뷰

**작성일**: 2025-12-08  
**목적**: 백테스트 엔진의 모든 계산 로직 검토 및 문제점 식별

---

## 1. 검토 대상 파일

| 파일 | 역할 |
|------|------|
| `core/engine/backtest.py` | 핵심 백테스트 엔진 |
| `extensions/backtest/runner.py` | 백테스트 실행기 |
| `app/services/backtest_service.py` | 백테스트 서비스 |
| `app/services/tuning_service.py` | 튜닝 서비스 |

---

## 2. 발견된 문제점

### 🔴 심각 (계산 오류)

#### 2.1 CAGR 계산 - 이중 기준 혼용
**위치**: `core/engine/backtest.py:411-423`

```python
# 현재 코드 (문제)
if days >= 126:
    annual_return = ((nav_series.iloc[-1] / self.initial_capital) ** (252 / days) - 1.0) * 100
elif days > 0:
    annual_return = total_return * (252 / days)  # ❌ 단순 비례 (선형)
    annual_return = max(-100, min(200, annual_return))  # ❌ 임의 제한
```

**문제점**:
1. `252/days` 지수 사용 → 거래일 기준 (252일)
2. 짧은 기간은 단순 비례 → 선형 외삽 (복리 무시)
3. 임의 제한 → 증상 치료, 근본 해결 아님

**표준 공식**:
```python
years = (end_date - start_date).days / 365.25  # 달력일 기준
cagr = ((final / initial) ** (1 / years) - 1) * 100
```

---

#### 2.2 Sharpe Ratio 계산 - 비표준 방식
**위치**: `core/engine/backtest.py:425-430`

```python
# 현재 코드 (문제)
volatility = np.std(self.daily_returns) * np.sqrt(252) * 100  # 연율화 변동성 (%)
sharpe_ratio = (annual_return / volatility)  # ❌ 연율화된 값끼리 나눔
```

**문제점**:
1. `annual_return`은 이미 연율화된 CAGR (%)
2. `volatility`도 연율화된 값 (%)
3. 둘 다 %인데 나누면 단위가 맞지 않음

**표준 공식**:
```python
daily_returns = pv_series.pct_change().dropna()
mean_ret = daily_returns.mean()  # 일평균 수익률
std_ret = daily_returns.std()    # 일간 표준편차
sharpe = (mean_ret / std_ret) * np.sqrt(252)  # 연율화
```

---

#### 2.3 MDD 부호 - 음수 반환
**위치**: `core/engine/backtest.py:432-434`

```python
# 현재 코드
drawdown = (nav_series / cummax - 1.0) * 100  # 음수
max_drawdown = drawdown.min()  # 가장 큰 음수 = 최대 낙폭
```

**문제점**:
- MDD가 `-15.5%`로 반환됨
- UI에서 `-(-15.5%) = 15.5%`로 표시해야 하는 혼란
- 업계 관례는 양수 (15.5%)

---

#### 2.4 Win Rate 계산 - 일별 기준
**위치**: `core/engine/backtest.py:436-439`

```python
# 현재 코드
win_rate = (np.array(self.daily_returns) > 0).sum() / len(self.daily_returns) * 100
```

**문제점**:
- **일별 수익률** 기준 승률 (거래 승률 아님)
- 실제 거래 승률과 다름
- 사용자 혼란 유발

**개선 방안**:
```python
# 거래 기준 승률
winning_trades = [t for t in trades if t.pnl > 0]
win_rate = len(winning_trades) / len(trades) * 100
```

---

### 🟡 주의 (잠재적 문제)

#### 2.5 Gross 성과 계산 - 동일한 문제
**위치**: `core/engine/backtest.py:467`

```python
annual_return_gross = ((nav_series_gross.iloc[-1] / self.initial_capital) ** (252 / days) - 1.0) * 100
```

- Net 성과와 동일한 문제 (252일 기준)
- 짧은 기간 처리 로직 없음

---

#### 2.6 리밸런싱 임계값 - 하드코딩
**위치**: `core/engine/backtest.py:355`

```python
if abs(weight_diff) > 0.01:  # 1% 이상 차이
```

- 임계값이 하드코딩됨
- 설정 파일에서 읽어야 함

---

#### 2.7 슬리피지 계산 - 단순 비율
**위치**: `core/engine/backtest.py:158-163`

```python
def calculate_slippage(self, price: float, action: str) -> float:
    if action == 'BUY':
        return price * (1 + self.slippage_rate)
    else:
        return price * (1 - self.slippage_rate)
```

- 거래량 무시 (대량 주문 시 슬리피지 증가)
- 시장 유동성 무시
- 단순화된 모델 (실제와 차이 가능)

---

#### 2.8 Calmar Ratio 미계산
**위치**: `app/services/backtest_service.py:202`

```python
calmar_ratio=metrics.get("calmar_ratio", 0),  # 항상 0
```

- 엔진에서 계산하지 않음
- 항상 0 반환

**계산 공식**:
```python
calmar_ratio = cagr / abs(max_drawdown)
```

---

### 🟢 정상 (문제 없음)

#### 2.9 거래세 계산
**위치**: `core/engine/backtest.py:95-102`

```python
TAX_RATES = {
    'stock': 0.0023,       # 주식: 0.23%
    'etf': 0.0,            # ETF: 면제 ✅
    'leveraged_etf': 0.0,  # 레버리지 ETF: 면제 ✅
}
```

- ETF 면세 정확함
- 매도 시에만 부과 정확함

---

#### 2.10 수수료 계산
**위치**: `core/engine/backtest.py:154-156`

```python
def calculate_commission(self, amount: float) -> float:
    return amount * self.commission_rate  # 0.015%
```

- 양방향 수수료 적용 정확함
- 비율 합리적 (0.015%)

---

## 3. 수정 우선순위

| 순위 | 항목 | 심각도 | 예상 시간 |
|------|------|--------|----------|
| 1 | CAGR 계산 수정 | 🔴 심각 | 30분 |
| 2 | Sharpe Ratio 수정 | 🔴 심각 | 30분 |
| 3 | MDD 부호 통일 | 🔴 심각 | 15분 |
| 4 | Win Rate 기준 명확화 | 🔴 심각 | 30분 |
| 5 | Calmar Ratio 추가 | 🟡 주의 | 15분 |
| 6 | 리밸런싱 임계값 설정화 | 🟡 주의 | 15분 |

**총 예상 시간**: 2시간 15분

---

## 4. 수정 계획

### Phase 1: 핵심 계산 로직 수정

#### 4.1 CAGR 수정
```python
def _calculate_cagr(self, final_value: float, initial_value: float, 
                    start_date: date, end_date: date) -> float:
    """표준 CAGR 계산"""
    years = (end_date - start_date).days / 365.25
    if years <= 0 or initial_value <= 0:
        return 0.0
    return ((final_value / initial_value) ** (1 / years) - 1) * 100
```

#### 4.2 Sharpe Ratio 수정
```python
def _calculate_sharpe(self, daily_returns: List[float]) -> float:
    """표준 Sharpe Ratio 계산"""
    if len(daily_returns) < 2:
        return 0.0
    returns = np.array(daily_returns)
    mean_ret = returns.mean()
    std_ret = returns.std()
    if std_ret <= 0:
        return 0.0
    return (mean_ret / std_ret) * np.sqrt(252)
```

#### 4.3 MDD 수정
```python
def _calculate_mdd(self, nav_series: pd.Series) -> float:
    """MDD 계산 (양수 반환)"""
    cummax = nav_series.cummax()
    drawdown = (nav_series / cummax - 1.0)
    return abs(drawdown.min()) * 100  # 양수로 반환
```

#### 4.4 Calmar Ratio 추가
```python
def _calculate_calmar(self, cagr: float, mdd: float) -> float:
    """Calmar Ratio 계산"""
    if mdd <= 0:
        return 0.0
    return cagr / mdd
```

### Phase 2: 테스트 및 검증

1. 단위 테스트 작성
2. 동일 조건 비교 테스트
3. 결과 검증

---

## 5. 승인 체크리스트

- [ ] 코드 리뷰 검토 완료
- [ ] 수정 계획 검토 완료
- [ ] 작업 시작 승인

---

## 6. 참고

### 표준 공식 출처
- CAGR: CFA Institute
- Sharpe Ratio: William F. Sharpe (1966)
- MDD: 업계 표준 관례
- Calmar Ratio: Terry W. Young (1991)
