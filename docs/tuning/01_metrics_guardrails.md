# 튜닝/검증 체계 설계 - 지표 및 가드레일 (v2.1)

> 관련 문서: [00_overview.md](./00_overview.md)

---

## 3. 지표 정의

### 3.1 핵심 지표 정의

```
⚠️ 아래 정의는 구현 시 반드시 준수. 정의가 다르면 결과 비교 불가.
```

| 지표 | 정의 | 산식 |
|------|------|------|
| **num_trades** | 매수+매도 거래 횟수 합계 | `len(buy_orders) + len(sell_orders)` |
| **exposure_ratio** | 전체 거래일 중 포지션을 보유한 거래일 비율 (현금일도 분모에 포함) | `포지션_보유일 / 전체_거래일` |
| **annual_turnover** | 연간 매매 회전율 (리밸런싱 기준) | `(연간_매수금액 + 연간_매도금액) / (2 × 평균_포트폴리오_가치)` |
| **Sharpe** | 연환산 샤프 비율 (무위험 수익률 0% 가정) | `mean(daily_returns) / std(daily_returns) × sqrt(252)` |
| **CAGR** | 연복리 수익률 | `(최종가치 / 초기가치)^(1/연수) - 1` |
| **MDD** | 최대 낙폭 (고점 대비 최대 하락률) | `min((현재가치 - 고점) / 고점)` |

**exposure_ratio 정의 명확화:**

```
⚠️ exposure_ratio = position_days / total_trading_days
   - 분모: 전체 거래일 (현금 100%일 포함)
   - 분자: 포지션 보유일 (현금 100%일은 포함되지 않음)
   - 예: 252거래일 중 180일 포지션 보유 → 180/252 = 0.714
```

```python
def calculate_exposure_ratio(daily_positions, trading_days):
    """
    exposure_ratio 계산
    - position_days: 포지션 > 0인 날 수
    - total_trading_days: 전체 거래일 수 (현금일 포함)
    """
    position_days = sum(1 for pos in daily_positions if pos > 0)
    total_trading_days = len(trading_days)
    return position_days / total_trading_days
```

### 3.2 가드레일 임계값

| 가드레일 | 임계값 | 위반 시 처리 |
|----------|--------|-------------|
| 최소 거래수 | num_trades ≥ 30 | score = -999 (탈락) |
| 최소 노출 | exposure_ratio ≥ 0.30 | score = -999 (탈락) |
| 최대 회전율 | annual_turnover ≤ 24 | score = -999 (탈락) |

### 3.3 비용 모델 정의

```
⚠️ commission/slippage는 "편도" 기준. 왕복 시 2배 적용.
```

| 비용 항목 | 기본값 | 적용 방식 |
|----------|--------|----------|
| commission | 0.00015 (0.015%) | 매수/매도 각각 적용 (편도) |
| slippage | 0.001 (0.1%) | 매수/매도 각각 적용 (편도) |

**왕복 비용 계산:**
```python
round_trip_cost = 2 * (commission + slippage)
# 기본값: 2 * (0.00015 + 0.001) = 0.0023 (0.23%)
```

### 3.4 stop_loss 트리거/체결 규칙

```
⚠️ 절대 규칙: 손절 판단과 체결 시점을 명확히 분리한다.
   이 규칙 하나로 MDD/Sharpe가 크게 달라진다.
```

**entry_price 정의:**

```
⚠️ entry_price = 포지션의 VWAP(가중평균 매수가)
   추가매수/리밸런싱이 있으면 평균단가로 갱신
```

| 상황 | entry_price 계산 |
|------|-----------------|
| 최초 매수 | 매수 체결가 |
| 추가 매수 | VWAP = (기존금액 + 추가금액) / (기존수량 + 추가수량) |
| 리밸런싱 | 리밸런싱 후 평균단가로 갱신 |

**권장 방식 (현실형):**

| 단계 | 시점 | 설명 |
|------|------|------|
| 손절 조건 판단 | T일 종가 | 종가 기준으로 stop_loss 도달 여부 확인 |
| 손절 체결 | T+1일 시가 | 다음 거래일 시가로 청산 |

**구현:**
```python
def check_stop_loss(position, current_close, stop_loss_pct):
    """
    T일 종가 기준 손절 조건 판단
    entry_price는 VWAP (가중평균 매수가)
    """
    entry_price = position['entry_price']  # VWAP
    return_pct = (current_close - entry_price) / entry_price
    
    # stop_loss_pct는 음수 (예: -0.10)
    return return_pct <= stop_loss_pct

def execute_stop_loss(position, next_open, costs):
    """
    T+1일 시가로 손절 체결 (비용 적용: 슬리피지 + 수수료 모두 편도)
    """
    # 슬리피지 반영 가격(체결가 가정)
    traded_price = next_open * (1 - costs['slippage_rate'])

    # 수수료 반영(매도 대금 차감)
    net_price = traded_price * (1 - costs['commission_rate'])

    return {
        'action': 'SELL',
        'price': net_price,
        'reason': 'STOP_LOSS',
    }
```

**대안 방식:**

| 방식 | 판단 기준 | 체결 시점 | 특징 |
|------|----------|----------|------|
| **현실형 (권장)** | T일 종가 | T+1일 시가 | 실제 거래 가능, 보수적 |
| 보수형 | T일 종가 | T일 종가 | 슬리피지 없음 가정, 낙관적 |
| 공격형 | T일 저가 | T일 저가 | Intraday 가정, OHLC만 있으면 비현실적 |

```
⚠️ 공격형(저가 기준)은 실제로 그 가격에 체결 가능한지 알 수 없음.
   OHLC 데이터만 있으면 "가정"임을 명시해야 함.
```

---

## 4. 이상치 감지 레이더

### 4.1 자동 경고 규칙

```
⚠️ 아래 조건 충족 시 UI에 경고 배지 표시 + 자동 검토 대상
```

| 조건 | 경고 메시지 | 배지 | 적용 시점 |
|------|------------|------|----------|
| Sharpe > 5.0 | "산출/표본/누수 점검 필요" | 🔴 | 튜닝 중 |
| CAGR > 1.0 (100%) | "비현실적 수익률, 누수 의심" | 🔴 | 튜닝 중 |
| num_trades < 30 | "표본 부족, 통계적 신뢰도 낮음" | 🟡 | 튜닝 중 |
| exposure_ratio < 0.30 | "노출 부족, 대부분 현금 보유" | 🟡 | 튜닝 중 |
| Val↓ Test↑↑ (Val < 0, Test > 1.5) | "Val/Test 괴리, 과적합 의심" | 🔴 | **Gate 3 이후** |

```
⚠️ Val↓Test↑↑ 규칙은 Test 산출 이후(=Gate 3 시점)에만 평가한다.
   튜닝 중에는 Test를 계산하지 않으므로 이 규칙 적용 불가.
```

### 4.2 UI 표시 예시

```
┌────┬────┬────┬───────┬────────┬────────┬──────┬───────┬──────────────┐
│ #  │ MA │RSI │ SL(%) │ Train  │  Val   │ Test │ 거래수│ 상태         │
├────┼────┼────┼───────┼────────┼────────┼──────┼───────┼──────────────┤
│ 1  │ 60 │ 14 │ -10%  │  2.1   │  1.5   │  🔒  │  45   │ ✅ 정상      │
│ 2  │ 80 │ 12 │  -8%  │  1.9   │  1.3   │  🔒  │  38   │ ✅ 정상      │
│ 3  │ 40 │ 21 │ -15%  │  2.5   │  0.2   │  🔒  │  12   │ 🟡 표본↓     │
│ 4  │ 30 │  5 │  -5%  │  6.0   │ -0.5   │  🔒  │  52   │ 🔴 Sharpe↑↑  │
│ 5  │ 50 │ 10 │ -12%  │  2.0   │ -0.3   │  🔒  │  40   │ 🔴 Val↓Test↑ │
└────┴────┴────┴───────┴────────┴────────┴──────┴───────┴──────────────┘
```

### 4.3 표본 부족 시 Sharpe 표시

```python
def display_sharpe(sharpe, num_trades):
    if num_trades < 30:
        return f"<span class='text-gray-400'>{sharpe:.2f}*</span>"  # 회색 + 별표
    return f"{sharpe:.2f}"
```

---

## 5. 멀티 룩백 결합 설계

### 5.1 문제 정의

UI에서 3M/6M/12M 룩백을 동시에 선택할 수 있는데, 각 룩백별로 Val 점수가 다르게 나옴.
이를 **하나의 objective로 결합하는 규칙**이 필요.

### 5.2 결합 방식 비교

| 방식 | 공식 | 장점 | 단점 |
|------|------|------|------|
| **평균** | `mean(scores)` | 단순 | 하나가 나빠도 평균에 묻힘 → 과적합 |
| **최솟값 (min)** | `min(scores)` | 최악 케이스 방어 | 보수적, 최적 성과 낮음 |
| **평균-표준편차** | `mean - k*std` | 균형 (안정성 반영) | k 설정 주관적 |

### 5.3 권장 결합 규칙

**Option A: 최솟값 (강력한 안정성 지향) — 기본값**

```python
final_score = min(val_score_3m, val_score_6m, val_score_12m)
```

**Option B: 평균 - k*표준편차 (균형형)**

```python
scores = [val_score_3m, val_score_6m, val_score_12m]
final_score = np.mean(scores) - 1.0 * np.std(scores)
```

### 5.4 룩백 정의

```
⚠️ 절대 규칙: 룩백은 거래일 기준으로 정의한다.
   3M = 63거래일, 6M = 126거래일, 12M = 252거래일
   end_date 포함해서 정확히 63/126/252 거래일 (inclusive)
```

| 룩백 | 거래일 수 | 비고 |
|--------|----------|------|
| 3M | **63일** | 약 3달량 |
| 6M | **126일** | 약 6달량 |
| 12M | **252일** | 약 1년량 |

**룩백 계산 로직:**
```python
LOOKBACK_TRADING_DAYS = {
    3: 63,    # 3개월 = 63거래일
    6: 126,   # 6개월 = 126거래일
    12: 252,  # 12개월 = 252거래일
}

def get_lookback_start(end_date, lookback_months, trading_calendar):
    """
    거래일 기준 룩백 시작일 계산 (v2.1)
    - end_date는 snap_end로 먼저 거래일로 보정
    - 룩백 길이는 end_date를 '포함'하여 정확히 N거래일
    """
    end_date = snap_end(end_date, trading_calendar)

    trading_days = LOOKBACK_TRADING_DAYS[lookback_months]
    calendar_before_end = [d for d in trading_calendar if d <= end_date]

    if len(calendar_before_end) < trading_days:
        raise ValueError(
            f"데이터 부족: {trading_days}거래일 필요, {len(calendar_before_end)}일 존재"
        )

    # end_date 포함해서 trading_days개를 확보 → 시작일
    return calendar_before_end[-trading_days]
```

**달력월 대신 거래일을 쓰는 이유:**
- 달력월은 휴장일/공휴일에 따라 실제 거래일 수가 다름
- 3개월이 60일일 수도, 66일일 수도 있음
- 거래일 기준이면 항상 동일한 데이터 양으로 비교 가능

### 5.5 캐시 설계

멀티 룩백 실행 시 계산량이 3배로 증가. 캐시로 중복 계산 방지.

```
⚠️ 캐시 키에 data_version, universe_version 필수 포함.
   다른 데이터인데 캐시 재사용되는 사고 방지.
⚠️ hash() 대신 hashlib.md5() 사용 (프로세스 간 일관성 보장)
```

**split_config 필드 통일:**

```python
# ✅ 통일된 split_config 구조
split_config = {
    'train_months': 12,      # 실제 적용값 (개월)
    'val_months': 6,
    'test_months': 6,
    'method': 'chronological',
    'target_ratios': {       # 참고값 (비율)
        'train': 0.70,
        'val': 0.15,
        'test': 0.15,
    }
}
```

**캐시 키 설계:**
```python
def make_cache_key(params, lookback, period, costs, split_config, data_config):
    """
    동일한 조건의 백테스트 결과를 캐싱
    
    v2: hash() 대신 hashlib.md5() 사용 (프로세스 간 일관성)
    v2: split_config 필드명 통일
    """
    # ⭐ v2: 안정 해시 사용 (hash()는 프로세스마다 다를 수 있음)
    params_sig = json.dumps(params, sort_keys=True)
    params_hash = hashlib.md5(params_sig.encode()).hexdigest()
    
    key_dict = {
        # 파라미터
        'params_hash': params_hash,
        'lookback': lookback,
        
        # 기간
        'start_date': period['start_date'],
        'end_date': period['end_date'],
        
        # 비용
        'commission': costs['commission_rate'],
        'slippage': costs['slippage_rate'],
        
        # Split (통일된 필드명)
        'train_months': split_config['train_months'],
        'val_months': split_config['val_months'],
        'test_months': split_config['test_months'],
        'split_method': split_config['method'],
        
        # 데이터/유니버스 버전
        'data_version': data_config['data_version'],
        'universe_version': data_config['universe_version'],
        'price_type': data_config.get('price_type', 'adj_close'),
        'dividend_handling': data_config.get('dividend_handling', 'total_return'),
    }
    return hashlib.md5(json.dumps(key_dict, sort_keys=True).encode()).hexdigest()

# 캐시 사용
split_config = {
    'train_months': 12,
    'val_months': 6,
    'test_months': 6,
    'method': 'chronological',
}
data_config = {
    'data_version': 'ohlcv_20251216',
    'universe_version': 'krx_etf_20251216',
    'price_type': 'adj_close',
    'dividend_handling': 'total_return',
}
cache_key = make_cache_key(params, lookback, period, costs, split_config, data_config)
if cache_key in run_cache:
    return run_cache[cache_key]
result = run_backtest(params, lookback, costs=costs)
run_cache[cache_key] = result
```
