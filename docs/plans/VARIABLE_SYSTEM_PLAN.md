# 변수 관리 시스템 계획

**작성일**: 2025-12-08  
**목적**: 튜닝 시 새로운 변수를 추가하고 관리할 수 있는 시스템 구축

---

## 1. 현재 상태

### 1.1 현재 튜닝 가능한 변수 (고정)
| 변수 | 범위 | 설명 |
|------|------|------|
| `ma_period` | 20-200 | 이동평균 기간 |
| `rsi_period` | 5-30 | RSI 기간 |
| `stop_loss` | -20% ~ -5% | 손절 비율 |

### 1.2 문제점
- 변수 추가 시 **코드 수정 필요**
- 새 변수 테스트가 어려움
- AI 제안을 바로 적용할 수 없음

---

## 2. 목표 시스템

### 2.1 변수 On/Off 설정
```yaml
# config/variables.yaml
variables:
  ma_period:
    enabled: true
    range: [20, 200]
    default: 60
    
  rsi_period:
    enabled: true
    range: [5, 30]
    default: 14
    
  stop_loss:
    enabled: true
    range: [-20, -5]
    default: -10
    
  # 새 변수 (비활성화 상태)
  volatility_filter:
    enabled: false
    range: [10, 50]
    default: 25
    description: "변동성 임계값 - 초과 시 진입 제한"
    
  market_breadth:
    enabled: false
    range: [30, 70]
    default: 50
    description: "시장 폭 - 상승 종목 비율 기준"
```

### 2.2 UI에서 변수 관리
```
┌─────────────────────────────────────────────────────────────────┐
│ ⚙️ 튜닝 변수 설정                                                │
├─────────────────────────────────────────────────────────────────┤
│ ☑ MA 기간        [20] ~ [200]    기본값: 60                     │
│ ☑ RSI 기간       [5]  ~ [30]     기본값: 14                     │
│ ☑ 손절 비율      [-20] ~ [-5]    기본값: -10                    │
│ ☐ 변동성 필터    [10] ~ [50]     기본값: 25   (비활성화)         │
│ ☐ 시장 폭        [30] ~ [70]     기본값: 50   (비활성화)         │
│                                                                 │
│ [+ 새 변수 추가]                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 구현 계획

### Phase 1: 설정 파일 기반 변수 관리 (1주)
- [ ] `config/variables.yaml` 생성
- [ ] 튜닝 서비스에서 설정 파일 읽기
- [ ] 활성화된 변수만 Optuna에 전달

### Phase 2: 백테스트 엔진 변수 연동 (1주)
- [ ] 변수별 계산 로직 모듈화
- [ ] 변수 → 전략 로직 매핑
- [ ] 변수 유효성 검증

### Phase 3: UI 변수 관리 (1주)
- [ ] 변수 목록 조회 API
- [ ] 변수 활성화/비활성화 API
- [ ] 변수 범위 수정 API
- [ ] UI 변수 설정 패널

### Phase 4: 새 변수 추가 워크플로우 (1주)
- [ ] 변수 정의 템플릿
- [ ] 변수 계산 로직 플러그인
- [ ] A/B 테스트 (변수 추가 전/후 비교)

---

## 4. 변수 추가 예시

### 4.1 변동성 필터 추가

**AI 제안**: "MDD를 줄이기 위해 변동성이 높을 때 진입을 제한하세요"

**1단계: 설정 파일에 변수 추가**
```yaml
volatility_filter:
  enabled: true
  range: [10, 50]
  default: 25
  description: "20일 변동성이 이 값 초과 시 진입 제한"
```

**2단계: 계산 로직 추가** (`strategy/variables/volatility.py`)
```python
def calculate_volatility_filter(prices: pd.Series, period: int = 20) -> float:
    """20일 변동성 계산"""
    returns = prices.pct_change().dropna()
    volatility = returns.tail(period).std() * np.sqrt(252) * 100
    return volatility
```

**3단계: 전략 로직에 통합**
```python
def should_enter(self, ticker: str, params: dict) -> bool:
    # 기존 조건
    if not self.ma_condition(ticker, params['ma_period']):
        return False
    if not self.rsi_condition(ticker, params['rsi_period']):
        return False
    
    # 새 변수 조건 (활성화된 경우만)
    if params.get('volatility_filter'):
        current_vol = calculate_volatility_filter(self.prices[ticker])
        if current_vol > params['volatility_filter']:
            return False  # 변동성 높으면 진입 제한
    
    return True
```

**4단계: 튜닝 실행**
- Optuna가 `volatility_filter` 최적값 탐색
- 결과: `volatility_filter=32` 일 때 MDD 3% 감소

---

## 5. 변수 카테고리

### 5.1 추세 지표
| 변수 | 설명 | 우선순위 |
|------|------|----------|
| `ma_period` | 이동평균 기간 | ✅ 구현됨 |
| `ma_type` | SMA/EMA/WMA | 중 |
| `trend_strength` | ADX 기반 추세 강도 | 중 |

### 5.2 모멘텀 지표
| 변수 | 설명 | 우선순위 |
|------|------|----------|
| `rsi_period` | RSI 기간 | ✅ 구현됨 |
| `rsi_threshold` | RSI 과매수/과매도 기준 | 중 |
| `momentum_period` | 모멘텀 계산 기간 | 낮 |

### 5.3 리스크 관리
| 변수 | 설명 | 우선순위 |
|------|------|----------|
| `stop_loss` | 손절 비율 | ✅ 구현됨 |
| `volatility_filter` | 변동성 필터 | 높 |
| `max_position_size` | 최대 포지션 크기 | 중 |

### 5.4 시장 상황
| 변수 | 설명 | 우선순위 |
|------|------|----------|
| `market_breadth` | 시장 폭 (상승 종목 비율) | 높 |
| `vix_threshold` | VIX 기반 시장 공포 지수 | 중 |
| `regime_weight` | 레짐별 가중치 | 낮 |

---

## 6. 성공 지표

### 6.1 시스템 목표
- 새 변수 추가 시간: 코드 수정 없이 **10분 이내**
- 변수 테스트: UI에서 **즉시 가능**
- 변수 롤백: **1클릭**으로 비활성화

### 6.2 전략 개선 목표
- 변수 추가 후 Sharpe Ratio: **+0.1 이상**
- 변수 추가 후 MDD: **악화 없음**
- 과적합 방지: Out-of-Sample 테스트 필수

---

## 7. 주의사항

### 7.1 과적합 방지
- 변수 개수 제한: **최대 10개**
- 각 변수 추가 시 Out-of-Sample 검증
- 정기적인 변수 유효성 검토 (분기별)

### 7.2 복잡성 관리
- 변수 간 상관관계 모니터링
- 중복 변수 제거
- 단순한 변수 우선

### 7.3 문서화
- 모든 변수에 설명 필수
- 변수 추가 이력 기록
- AI 제안 → 변수 추가 연결 추적

---

## 8. 관련 문서

- `docs/plans/AI_ANALYSIS_INTEGRATION_PLAN.md` - AI 분석 연동
- `docs/plans/BACKTEST_IMPROVEMENT_PLAN.md` - 백테스트 개선
- `strategy/backtest_engine.py` - 백테스트 엔진

---

## 9. 체크리스트

- [ ] Phase 1: 설정 파일 기반 변수 관리
- [ ] Phase 2: 백테스트 엔진 변수 연동
- [ ] Phase 3: UI 변수 관리
- [ ] Phase 4: 새 변수 추가 워크플로우
- [ ] 첫 번째 새 변수 추가 (volatility_filter)
- [ ] A/B 테스트 완료
