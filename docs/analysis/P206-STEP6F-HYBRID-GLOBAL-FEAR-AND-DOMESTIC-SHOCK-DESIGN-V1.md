# P206-STEP6F: Hybrid Global Fear + Domestic Shock 설계서 V1

> asof: 2026-04-06
> 상태: 설계 확정 (구현은 Step6G)

---

## 1. 배경 및 현재 상태

### Step6E까지 확인된 사실

| 구성 | CAGR | MDD | Sharpe | neutral | risk_off | 판정 |
|---|---|---|---|---|---|---|
| no regime | 29.51% | 17.80% | 1.36 | — | — | MDD 초과 |
| VIX baseline (20/30/0.20) | 18.73% | 19.30% | 0.95 | 4 | 0 | 실패 |
| VIX tuned (20/26/0.05) | 16.11% | 16.81% | 0.85 | 2 | 2 | 실패 |

**결론**: VIX 단독은 글로벌 리스크오프만 감지. 한국장 독자 급변동을 놓침.

### 왜 하이브리드인가

- 미국 VIX는 **선행 공포 센서**로 유효 — 버리지 않음
- 한국장은 미국과 무관한 **국내 수급/섹터/정책 쇼크**로 독자 급락 발생
- 따라서 **글로벌(VIX) + 국내(domestic shock)** 2축이 필요

---

## 2. 센서 구조: 2축

### 2.1 Global Fear Regime (기존 계승)

| 항목 | 값 |
|---|---|
| Provider | `global_fear_regime` (= 기존 `fear_index_regime`) |
| Source | 미국 CBOE VIX (`^VIX`, yfinance) |
| 정렬 | `us_close_to_kr_next_open` (미국 T → 한국 T+1) |
| TTL | 캘린더 5일 |
| 판별 | 절대 임계치 + 5DMA spike |

Step6D/6E 배선 100% 재사용. fetch, 정렬, fail-closed 로직 변경 없음.

### 2.2 Domestic Shock Regime (신규)

한국장 독자 급변동을 감지하는 국내 센서.

---

## 3. 국내 센서 후보

### 후보 A: 전일 대표 ETF 급락폭 (V1 권장)

| 항목 | 값 |
|---|---|
| Source | 069500 (KODEX 200) 전일 종가 대비 수익률 |
| 판별 | 전일 수익률 기준 3단계 |
| 데이터 | 일봉 (이미 보유 가능) |
| 장전 판단 | 가능 (전일 종가 확정) |
| 장중 판단 | 체크포인트 시점 현재가 vs 전일 종가 |

**판별 규칙 (V1 권장)**:

```
daily_return = (today_close / prev_close) - 1.0  (장전은 전일 종가 기준)

daily_return >= -0.01         → risk_on    (하락 1% 미만)
-0.03 < daily_return < -0.01 → neutral    (하락 1~3%)
daily_return <= -0.03         → risk_off   (하락 3% 이상)
```

**장중 체크포인트에서는**:

```
intraday_return = (checkpoint_price / prev_close) - 1.0

intraday_return >= -0.015     → risk_on
-0.03 < intraday_return < -0.015 → neutral
intraday_return <= -0.03      → risk_off
```

**장점**: 단순, 결정론적, 데이터 무료, 장전/장중 모두 사용 가능
**단점**: 단일 ETF 의존, 섹터 쏠림 미감지

### 후보 B: 단기 Realized Volatility 급등

| 항목 | 값 |
|---|---|
| Source | 069500 최근 5일 일간 수익률 표준편차 (연율화) |
| 판별 | RV가 장기 평균 대비 급등 시 경고 |

```
rv_5d = std(최근 5일 일간 수익률) * sqrt(252)
rv_60d = std(최근 60일 일간 수익률) * sqrt(252)

rv_5d / rv_60d < 1.5  → risk_on
1.5 <= ratio < 2.5    → neutral
ratio >= 2.5           → risk_off
```

**장점**: 변동성 급등을 직접 감지
**단점**: 장중 실시간 RV 계산이 어려움 (일봉 기반만 가능)

### 후보 C: 장초 15분 누적 변동폭

| 항목 | 값 |
|---|---|
| Source | 069500 장초 15분 고가-저가 범위 / 전일 종가 |
| 판별 | 장초 변동폭이 비정상적으로 클 때 경고 |

```
opening_range = (high_15min - low_15min) / prev_close

opening_range < 0.01  → risk_on
0.01 <= range < 0.02  → neutral
range >= 0.02         → risk_off
```

**장점**: 장초에 즉시 판단 가능, 갭다운 + 변동성 동시 포착
**단점**: 분봉 데이터 필요 (일봉 인프라로는 부족), 장초에만 유효

### V1 권장안: **후보 A (전일 대표 ETF 급락폭)**

**이유**:
1. 일봉 데이터만으로 장전 판단 가능 — 기존 인프라 재사용
2. 장중 체크포인트에서는 현재가 1개만 확인하면 됨
3. 결정론적이고 단순
4. 후보 B는 장중 실시간 계산 어렵고, 후보 C는 분봉 인프라 필요

---

## 4. 장중 대응: 체크포인트 모델

### 4.1 허용 체크포인트

| ID | 시각 | 성격 | 필수 |
|---|---|---|---|
| K1 | 09:00~09:15 | 장초 (갭다운/개장 충격 확인) | 필수 |
| K2 | 10:30~11:00 | 오전 1차 (초반 방향성 확인) | 필수 |
| K3 | 11:30~12:00 | 오전 2차 (점심 전 최종) | 선택 |
| K4 | 14:00~14:30 | 오후 1차 (후장 방향성 확인) | 필수 |
| K5 | 14:30~15:00 | 오후 2차 (마감 준비) | 선택 |
| K6 | 15:20~15:30 | 마감 (다음날 개장 전 최종) | 필수 |

### 4.2 운영 원칙

- 하루 최대 **6회**, 기본 운용은 **4회** (K1, K2, K4, K6)
- 체크포인트 외 시간에는 **재판정 없음**
- 분 단위 상시 추적 **금지**
- 각 체크포인트에서 **domestic shock만 재판정** (VIX는 장전 고정)

### 4.3 상태 전이 규칙

```
개장 전: global + domestic(전일 기준) → 기본 상태 확정
K1:      domestic(장초 현재가) 재판정 → 격상만 허용 (risk_on→neutral, neutral→risk_off)
K2~K5:   domestic(체크포인트 현재가) 재판정 → 격상만 허용
K6:      마감 확정 → 다음날 개장 전 기본 상태 준비
```

**핵심**: 장중 재판정은 **격상(더 보수적)만 허용**. 장중에 risk_off→risk_on 복귀는 금지.
복귀는 **다음 개장 전 판정에서만** 가능.

### 4.4 한계 명시

- 이 모델은 **직장인형 저빈도 장중 체크포인트 대응**
- 상시 실시간 모니터링이 아님
- 장중 급락 저점/고점 완벽 포착은 목표가 아님
- 목표: **대응 불가능한 직장인 조건에서 MDD를 덜 맞는 것**
- 브로커 자동 주문 연동은 설계 범위 밖

---

## 5. 통합 판정 규칙

### 5.1 후보 비교

| 방식 | 설명 | 장점 | 단점 |
|---|---|---|---|
| A. 우선순위형 | 글로벌 극단 시 즉시 risk_off, 나머지는 국내 보조 | 단순 | 국내 단독 쇼크 대응 약함 |
| B. 최댓값형 | 두 센서 중 더 위험한 상태 채택 | 보수적 | cash drag 우려 |
| **C. 가중 보수형** | 글로벌/국내 조합 규칙 명시 | 균형적 | 규칙 관리 필요 |

### 5.2 V1 권장: 가중 보수형 (C)

#### 진리표

| Global | Domestic | Aggregate |
|---|---|---|
| risk_on | risk_on | **risk_on** |
| risk_on | neutral | **neutral** |
| risk_on | risk_off | **risk_off** |
| neutral | risk_on | **neutral** |
| neutral | neutral | **risk_off** (이중 경고 → 격상) |
| neutral | risk_off | **risk_off** |
| risk_off | risk_on | **risk_off** |
| risk_off | neutral | **risk_off** |
| risk_off | risk_off | **risk_off** |

#### 핵심 원칙

1. **글로벌 risk_off = 단독 hard gate** (미국 패닉은 한국에 반드시 전이)
2. **국내 risk_off = 단독 hard gate** (국내 독자 급락은 즉시 방어)
3. **글로벌 neutral + 국내 neutral = risk_off** (양쪽 다 불안하면 보수적)
4. **한쪽만 neutral = neutral** (한쪽만 불안하면 50% 방어)
5. **둘 다 risk_on = risk_on** (양쪽 다 안전할 때만 정상 투자)

---

## 6. 정책 맵

| 상태 | 정책 | target_cash_pct | 동작 |
|---|---|---|---|
| risk_on | none | 0.0 | dynamic scanner 정상 실행 |
| neutral | soft_gate | **0.50** | 비중 50% 축소 |
| risk_off | hard_gate | 1.0 | 100% 현금, 기존 보유 청산 |

### neutral 강도 권장

Step6E 결과상 `neutral_cash_pct=0.50`이 CAGR-MDD 균형이 가장 나았음. V1에서는 0.50 유지.

### 장중 risk_off 격상 후 복귀 규칙

- 장중에 risk_off로 격상되면, **당일 남은 체크포인트에서 risk_on 복귀 금지**
- risk_off→neutral 격하도 당일 금지
- 복귀는 **다음 개장 전 판정**에서만 가능
- 이유: 장중 whipsaw(빠른 왕복) 방지

---

## 7. 데이터 제약 및 Fail-Closed

### 7.1 글로벌 센서 (VIX)

기존 Step6D 정책 유지:
- yfinance `^VIX` fetch, 캐시 재사용
- staleness > 5일 → neutral fallback
- fetch 실패 → risk_off fallback

### 7.2 국내 센서 (후보 A: 069500)

| 상황 | 정책 |
|---|---|
| 069500 전일 종가 있음 | 정상 계산 |
| 069500 전일 종가 없음 (한국 휴장) | 직전 유효 종가 carry-forward (최대 캘린더 3일) |
| 장중 현재가 fetch 실패 | neutral fallback |
| 데이터 완전 부재 | risk_off fallback |

### 7.3 장중 현재가 소스

- **백테스트**: 일봉 종가로 시뮬레이션 (장중 체크포인트는 일봉 1개로 근사)
- **실운용**: 장중 현재가는 yfinance 또는 pykrx 등 무료 API로 획득
- 초고빈도 스트리밍 금지

---

## 8. 산출물 계약

### 8.1 hybrid_regime_verdict_latest.json

```json
{
  "asof": "2026-04-07T09:15:00+09:00",
  "global_state": "neutral",
  "domestic_state": "risk_off",
  "aggregate_state": "risk_off",
  "policy_applied": "hard_gate",
  "target_cash_pct": 1.0,
  "global_source_timestamp": "2026-04-04",
  "domestic_source_timestamp": "2026-04-07",
  "checkpoint_id": "K1",
  "regime_valid": true,
  "error_code": null
}
```

### 8.2 hybrid_regime_schedule_latest.json/csv

각 행:

| 필드 | 예시 |
|---|---|
| date | 2026-04-07 |
| checkpoint_id | K1 |
| global_state | neutral |
| domestic_state | risk_off |
| aggregate_state | risk_off |
| gate_applied | true |
| target_cash_pct | 1.0 |
| vix_value | 25.25 |
| domestic_return | -0.035 |
| global_source_ts | 2026-04-04 |
| domestic_source_ts | 2026-04-07 |

### 8.3 hybrid_regime_reason_latest.md

한국어로:
- 현재 글로벌/국내 각 상태와 근거
- 어느 센서가 트리거했는지
- 장중 체크포인트인지 장전 판정인지
- aggregate 상태 결정 사유

### 8.4 dynamic_evidence_latest.md 확장

기존 필드 유지 + 아래 추가:

```markdown
## Hybrid Regime
| Field | Value |
|---|---|
| Global State | neutral |
| Domestic State | risk_off |
| Aggregate State | risk_off |
| Checkpoint | K1 |
| Intraday Reassessments | 2 |
```

---

## 9. 비교군

Step6G/6H 이후:

| # | 구성 | 예상 특성 |
|---|---|---|
| 1 | no regime | 높은 CAGR, 높은 MDD |
| 2 | VIX baseline (20/30/0.20) | 글로벌만 방어, 국내 취약 |
| 3 | VIX tuned (20/26/0.05) | 약간 개선, 여전히 부족 |
| 4 | **Hybrid (VIX + domestic shock)** | 글로벌+국내 이중 방어 |

---

## 10. 구현 경계 (Step6G 범위)

### 수정 대상 파일 (예상)

| 파일 | 변경 |
|---|---|
| `exo_regime_filter.py` | `domestic_shock_regime` provider 추가, hybrid 통합 판정 |
| `run_backtest.py` | 069500 일봉 + hybrid schedule 구축 |
| `backtest_runner.py` | hybrid schedule gate 적용 |
| `run_tune.py` | 동일 hybrid schedule |
| `workflow.py` | UI 1~2줄 변경 |

### 백테스트에서의 장중 체크포인트 처리

- 백테스트는 **일봉만 사용** — 장중 체크포인트는 일봉 1개로 근사
- 즉 백테스트에서는 K1~K6 구분 없이 당일 종가 기준으로 domestic 판정
- 실운용 전환 시에만 체크포인트별 현재가 사용
- 이 근사의 한계를 결과 해석에 명시

---

## 11. provider registry 항목 (Step6G 참조용)

```python
{
    "key": "domestic_shock_regime",
    "enabled": True,
    "source": "KRX 069500 일봉/현재가 기반 급락폭",
    "lookback": 1,
    "lag_days": 0,
    "freshness_ttl": 5,
    "thresholds": {
        "risk_on_max_return": -0.01,
        "risk_off_min_return": -0.03,
        "intraday_risk_on_max": -0.015,
        "intraday_risk_off_min": -0.03,
    },
    "missing_policy": "neutral_fallback",
    "regime_map": {
        "stable": "risk_on",
        "mild_decline": "neutral",
        "sharp_decline": "risk_off",
    },
    "required_symbols": ["069500"],
    "notes": "전일 수익률 기반: >-1%=risk_on, -1~-3%=neutral, <=-3%=risk_off",
}
```
