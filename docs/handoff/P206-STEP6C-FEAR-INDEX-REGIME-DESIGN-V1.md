# P206-STEP6C: Fear Index Regime 설계서 V1

> asof: 2026-04-05
> 상태: 설계 확정 (구현은 Step6D)

---

## 1. 배경 및 동기

### 현재까지 확인된 사실

| 단계 | 센서 | 결과 |
|---|---|---|
| Step6B V1 | MA200 단독 hard gate | CAGR 21.27%, MDD 16.48% — 후행성 cash drag |
| Step6B PATCH1 | MA200 + Breadth dual-confirm | CAGR 19.44%, MDD 19.30% — 오히려 악화 |

**결론**: 내부 후행성 지표(MA, Breadth)로는 MDD < 10% 달성 불가. 센서 클래스 전환 필요.

### 왜 미국 VIX인가

- 한국 증시는 미국 리스크오프 심리에 **후행 반응**
- 미국장 종가 기반 VIX는 한국장 개장 **전** 확인 가능
- 즉 VIX는 한국장 입장에서 **선행 공포 센서**로 기능
- VKOSPI 대비 유동성, 데이터 접근성, 글로벌 벤치마크 지위 모두 우월

---

## 2. 주력 센서 확정

### Provider 활성 구성 (Step6D 이후)

| Provider | enabled | 역할 |
|---|---|---|
| `fear_index_regime` | **true** | 주력 센서 (미국 VIX) |
| `market_trend_ma_regime` | false | 비교군/백업 슬롯 |
| `market_breadth_regime` | false | 비교군/백업 슬롯 |
| 기타 5개 | false | 향후 확장 슬롯 |

- MA/Breadth는 **삭제하지 않음** — registry 슬롯 유지, `enabled=false`
- VIX 센서 장애 시 즉시 재활성화 가능

---

## 3. 미국-한국 시차 정렬 규칙 (핵심)

### 3.1 기본 원칙

```
미국 VIX 거래일 T 종가 → 한국 시장 T+1 개장일 리밸런스 입력
```

- 미국 T일 16:00 ET 종가 → 한국 T+1일 09:00 KST 개장 전 확정
- 동일 캘린더 가정 **금지**
- **lookahead bias 방지**: 한국 T일 리밸런스에 미국 T일 밤 데이터 사용 금지

### 3.2 매핑 로직

```
for each 한국 리밸런스일 kr_date:
    1. kr_date - 1 이하인 미국 거래일 중 가장 최근 유효 종가를 찾는다
    2. 해당 VIX 종가를 kr_date의 regime 입력으로 사용한다
```

### 3.3 휴장일 불일치 처리

| 상황 | 처리 |
|---|---|
| 미국 휴장 + 한국 개장 | 미국 직전 유효 거래일 종가 carry-forward |
| 미국 개장 + 한국 휴장 | 한국 다음 개장일에 해당 VIX 종가 적용 |
| 양국 동시 휴장 | 가장 최근 미국 유효 종가 carry-forward |

### 3.4 Carry-Forward 한도

- **최대 3 영업일**까지 carry-forward 허용
- 3 영업일 초과 시 → `staleness_exceeded` → fallback 정책 적용

---

## 4. 3단계 상태망 및 판별 기준

### 4.1 후보 로직 비교

| 방식 | 장점 | 단점 |
|---|---|---|
| **A. 절대 임계치** (20/30) | 직관적, 시장 컨센서스 | 시기별 VIX 평균 변동 미반영 |
| **B. 통계적 z-score** (μ+1σ/+2σ) | 시기 적응적 | 계산 복잡, 직관 약함 |
| **C. 혼합** (절대 + 급등 확인) | 균형적 | 파라미터 2종 관리 |

### 4.2 V1 권장안: 혼합 방식 (절대 임계치 + 단기 급등 확인)

#### 기본 규칙

```
vix_close = 미국 VIX 직전 유효 종가
vix_5dma  = VIX 최근 5거래일 이동평균
vix_spike = (vix_close / vix_5dma - 1.0)  # 급등률
```

#### 판별표

| 조건 | 상태 |
|---|---|
| `vix_close < 20` | `risk_on` |
| `20 ≤ vix_close < 30` **and** `vix_spike < 0.20` | `neutral` |
| `20 ≤ vix_close < 30` **and** `vix_spike >= 0.20` | `risk_off` |
| `vix_close >= 30` | `risk_off` |

#### 해석

- **VIX < 20**: 시장 안정 → 정상 투자
- **20~30 구간**: 경계 구간
  - 급등률 20% 미만이면 → neutral (50% 방어)
  - 급등률 20% 이상이면 → risk_off (100% 현금) — 급격한 공포 확산 신호
- **VIX ≥ 30**: 극단 공포 → 무조건 risk_off

#### 결정론 보장

- `vix_close`와 `vix_5dma`는 과거 확정 데이터만 사용
- 동일 입력 → 동일 판별 결과 보장
- 난수, 온라인 학습, 적응형 파라미터 없음

---

## 5. 정책 맵

| 상태 | 정책 | target_cash_pct | 동작 |
|---|---|---|---|
| `risk_on` | none | 0.0 | dynamic scanner 정상 실행 |
| `neutral` | soft_gate | 0.5 | 비중 50% 축소 (나머지 현금) |
| `risk_off` | hard_gate | 1.0 | 위험자산 0%, 100% 현금, 기존 보유 청산 |

---

## 6. 결측치 처리 및 Fail-Closed

### 6.1 결측 정책

| 상황 | 정책 | 코드 |
|---|---|---|
| 미국 휴장 직후 (1~3일) | `carry_forward_last_valid` | — |
| 연속 결측 > 3 영업일 | `neutral_fallback` | `staleness_exceeded` |
| VIX fetch 완전 실패 | `risk_off_fallback` | `fetch_failed` |
| VIX 값 NaN/inf | `neutral_fallback` | `invalid_value` |

### 6.2 금지

- 계산 실패를 `risk_on`으로 보내는 설계 금지
- `regime_valid=false`일 때 정상 실행처럼 보이게 하는 것 금지

### 6.3 산출물 필수 필드

- `regime_valid`: bool
- `fear_source_timestamp`: 미국 VIX 데이터의 실제 거래일
- `alignment_mode`: `us_close_to_kr_next_open`
- `staleness_days`: 미국 기준일과 한국 적용일 사이 간격
- `error_code`: null 또는 오류 코드

---

## 7. Data Loader 설계

### 7.1 VIX Fetch Source

| 우선순위 | Source | 심볼 | 비고 |
|---|---|---|---|
| 1 | yfinance | `^VIX` | 무료, 일봉, 15분 지연 |
| 2 | 기존 FDR fallback | — | FDR이 VIX 미지원 시 skip |

- 장애 시: `regime_valid=false` + `error_code=fetch_failed`

### 7.2 캘린더 정렬

```
1. 미국 VIX 일봉 다운로드 (start - 250일 ~ end)
   - lookback 여유 포함 (5DMA + carry-forward 대비)
2. 한국 리밸런스 날짜 목록 확보
3. 각 한국 리밸런스일에 대해:
   - kr_date - 1 이하인 미국 거래일 중 최신 VIX 종가 매핑
   - staleness_days = (kr_date - us_source_date).days
   - staleness_days > 3 → fallback 적용
```

### 7.3 Freshness TTL

- **기본 TTL: 3 영업일**
- TTL 초과 시: `neutral_fallback`
- TTL 초과 + VIX >= 30 마지막 기록: `risk_off_fallback`

### 7.4 Cache 전략

- `data/cache/ohlcv/yfinance/^VIX_{start}_{end}.parquet` 패턴 사용
- 기존 OHLCV 캐시 인프라 재사용
- 반복 튜닝/백테스트에서 외부 fetch 폭탄 방지
- snapshot hash 추적: `provider_values` 에 `cache_hit` 필드

### 7.5 Lookahead 방지 체크리스트

- [ ] 한국 T일 리밸런스에 미국 T일 밤 데이터 사용하지 않음
- [ ] `kr_date - 1` 이하 필터 적용됨
- [ ] 미래 VIX 데이터가 과거 리밸런스에 유입되지 않음
- [ ] 테스트 케이스에 경계일 검증 포함

---

## 8. 산출물 계약

### 8.1 fear_regime_verdict_latest.json

```json
{
  "asof": "2026-04-05T09:00:00+09:00",
  "provider_key": "fear_index_regime",
  "fear_index_symbol": "^VIX",
  "fear_value": 22.5,
  "fear_value_timestamp": "2026-04-04",
  "alignment_mode": "us_close_to_kr_next_open",
  "regime_state": "neutral",
  "policy_applied": "soft_gate",
  "target_cash_pct": 0.5,
  "regime_valid": true,
  "staleness_days": 1,
  "error_code": null,
  "vix_5dma": 19.8,
  "vix_spike": 0.136
}
```

### 8.2 fear_regime_schedule_latest.json/csv

각 행 최소 필드:

| 필드 | 예시 |
|---|---|
| `rebalance_date` | 2026-04-01 |
| `fear_value` | 22.5 |
| `vix_5dma` | 19.8 |
| `vix_spike` | 0.136 |
| `fear_state` | neutral |
| `gate_applied` | true |
| `target_cash_pct` | 0.5 |
| `source_trade_date_us` | 2026-03-31 |
| `applied_trade_date_kr` | 2026-04-01 |
| `staleness_days` | 1 |

### 8.3 fear_regime_reason_latest.md

한국어로 아래 포함:
- 현재 VIX 레벨과 상태
- 어떤 임계치를 넘었는지
- 미국 거래일 → 한국 거래일 매핑 근거
- soft/hard gate 적용 사유

---

## 9. UI 최소 표면화

기존 `백테스트 및 튜닝 시뮬레이션` 화면 내 1~2줄 caption:

```
Fear Regime: neutral | VIX: 22.5 | 정책: soft_gate | 미국: 2026-04-04 | 적용: 2026-04-01
```

- 새 페이지 금지
- 새 탭 금지
- 장문 설명 금지

---

## 10. 비교군 설계

Step6D 구현 후 아래 4개를 비교:

| # | 구성 | 예상 특성 |
|---|---|---|
| 1 | dynamic_etf_market (no regime) | 높은 CAGR, 높은 MDD |
| 2 | MA hard_gate (Step6B V1) | MDD 소폭 개선, CAGR 크게 손실 |
| 3 | MA+Breadth dual_confirm (PATCH1) | MDD 악화, CAGR 손실 |
| 4 | **VIX fear regime V1** | 목표: CAGR 유지 + MDD < 10% |

- VIX 버전이 좋아 보여도 반드시 기존 실패본 대비 개선 입증 필요
- 비교 지표: CAGR, MDD, Sharpe, Trades, risk_off 횟수

---

## 11. 구현 경계 (Step6D 범위)

### 수정 대상 파일 (예상)

| 파일 | 변경 |
|---|---|
| `exo_regime_filter.py` | `fear_index_regime` provider 구현, MA/Breadth `enabled=false` |
| `run_backtest.py` | VIX fetch + fear regime schedule 구축 |
| `run_tune.py` | 동일 |
| `backtest_runner.py` | fear regime gate 적용 (기존 exo_regime gate 재사용) |
| `workflow.py` | UI 1줄 변경 |

### 기존 파이프라인과의 호환

- `dynamic_equal_weight` 경로 유지
- `bucket_portfolio` 경로 미영향
- `time-aware schedule` 미영향
- `objective`, `promotion_verdict`, `study.sqlite3`, `resume` 미영향

---

## 12. provider registry 항목 (Step6D 참조용)

```python
{
    "key": "fear_index_regime",
    "enabled": True,
    "source": "US CBOE VIX via yfinance",
    "lookback": 250,  # 5DMA + carry-forward 여유
    "lag_days": 1,     # 미국 T → 한국 T+1
    "freshness_ttl": 3,
    "thresholds": {
        "risk_on_max": 20.0,
        "risk_off_min": 30.0,
        "spike_threshold": 0.20,
        "spike_window": 5,
    },
    "missing_policy": "neutral_fallback",
    "regime_map": {
        "low_fear": "risk_on",
        "mid_fear_no_spike": "neutral",
        "mid_fear_spike": "risk_off",
        "high_fear": "risk_off",
    },
    "required_symbols": ["^VIX"],
    "notes": "혼합 방식: 절대 임계치(20/30) + 5DMA 대비 급등률(20%)",
}
```
