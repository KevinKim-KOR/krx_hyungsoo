# P205-STEP5A: 다이나믹 유니버스 스캐너 아키텍처 설계

> asof: 2026-03-30
> 상태: 설계 완료 / 구현 미착수
> 범위: 설계·문서화만. 코드·UI·Objective 변경 없음.

---

## 1. 배경 및 목적

### 1.1 현재 한계

현재 유니버스 관리 방식은 두 가지 **정적 리스트**에 의존한다.

| 모드 | 구성 | 한계 |
|---|---|---|
| `fixed_current` | 12종목 하드코딩 | 시장 변화 반영 불가, 상장폐지/유동성 고갈 대응 불가 |
| `expanded_candidates` | 33종목 하드코딩 | 범위는 넓지만 여전히 수동 관리, 신규 ETF 자동 편입 불가 |

### 1.2 목표

정적 리스트를 대체할 **다이나믹 유니버스 스캐너**를 설계한다.

- 시장 데이터 기반으로 후보를 자동 선별
- 입력 파라미터를 하드코딩하지 않고 **Feature Provider / Registry 기반 확장형 구조**로 설계
- 뉴스/공포지수 등 외생 변수는 **비활성 슬롯**으로만 포함 (V1에서는 활성화하지 않음)
- 기존 승격 판정 체계(`used_params_match_ssot`, `used_universe_match`)와 호환

---

## 2. 3계층 아키텍처

```
┌─────────────────────────────────────────────────┐
│          Layer 1: Candidate Pool                │
│   (어떤 시장/자산군에서 후보를 가져올 것인가)       │
└───────────────────┬─────────────────────────────┘
                    │ raw tickers
                    ▼
┌─────────────────────────────────────────────────┐
│          Layer 2: Feature Provider              │
│   (각 후보에 대해 점수 계산용 feature 공급)        │
│   Registry 기반 확장형 구조                       │
└───────────────────┬─────────────────────────────┘
                    │ feature matrix (ticker × feature)
                    ▼
┌─────────────────────────────────────────────────┐
│          Layer 3: Selector / Ranking            │
│   (필터링 → 점수화 → 상위 N개 선택)               │
└───────────────────┬─────────────────────────────┘
                    │ selected universe
                    ▼
              [SSOT / Tune / Backtest]
```

---

### 2.1 Layer 1: Candidate Pool

후보군의 **원천**을 정의하는 계층이다.

| 모드 | 설명 | V1 상태 |
|---|---|---|
| `fixed_current` | 기존 12종목 정적 리스트 | 레거시 호환용 유지 |
| `expanded_candidates` | 기존 33종목 정적 리스트 | 레거시 호환용 유지 |
| `dynamic_etf_market` | KRX 전체 ETF 또는 전략 허용 ETF 풀에서 동적 선별 | **V1 신규 대상** |

#### V1 범위 제한

- ETF 시장만 대상으로 한다. 전체 개별주 시장으로 확장하지 않는다.
- 이유: ETF는 유동성·분산·거래세 면에서 모멘텀 전략에 적합하며, 개별주 확장은 데이터 품질 및 종목 수 폭증 리스크가 크다.

#### Candidate Pool 설정 스키마

```json
{
  "candidate_pool": {
    "mode": "dynamic_etf_market",
    "source": "krx_etf_list",
    "filters": {
      "min_listing_days": 180,
      "min_avg_volume_20d": 50000,
      "min_nav": 1000,
      "exclude_leveraged": false,
      "exclude_inverse": true,
      "exclude_synthetic": true,
      "asset_class_whitelist": ["equity", "bond", "commodity", "mixed"]
    },
    "refresh_frequency": "weekly",
    "max_candidates": 200
  }
}
```

---

### 2.2 Layer 2: Feature Provider (Registry 기반)

각 후보 종목에 대해 **점수 계산에 필요한 feature를 공급**하는 계층이다.

#### 핵심 원칙: 확장형 Registry 구조

Feature는 하드코딩 키(`momentum_period`, `fear_index_weight` 등)로 박지 않는다.
`features[]` 리스트형 오브젝트 구조로 정의하여, 새 feature 추가 시 코드 수정 없이 설정만으로 확장 가능하게 한다.

#### Feature Object 메타 스키마

각 feature는 아래 메타를 반드시 가진다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `key` | string | feature 고유 식별자 (예: `price_momentum_3m`) |
| `source` | string | 데이터 출처 (예: `ohlcv`, `external_api`, `derived`) |
| `enabled` | boolean | 현재 활성화 여부 |
| `required` | boolean | 누락 시 후보 제외 여부 |
| `weight` | float | 최종 점수 계산 시 가중치 (0.0이면 점수에 불참) |
| `lookback` | int | 계산에 사용할 과거 영업일 수 |
| `lag_days` | int | 데이터 지연 허용일 (0 = 당일 필요) |
| `freshness_ttl` | string | 데이터 유효 기간 (예: `1d`, `7d`) |
| `missing_policy` | string | 누락 시 처리 (`exclude` / `fill_zero` / `fill_median` / `skip_scoring`) |
| `normalization` | string | 정규화 방식 (`z_score` / `min_max` / `percentile_rank` / `none`) |
| `notes` | string | 설명 (한국어) |

#### V1 활성 Feature 목록

| key | source | enabled | weight | lookback | normalization | 설명 |
|---|---|---|---|---|---|---|
| `price_momentum_3m` | ohlcv | ✅ | 0.30 | 60 | percentile_rank | 3개월 가격 모멘텀 |
| `price_momentum_6m` | ohlcv | ✅ | 0.20 | 120 | percentile_rank | 6개월 가격 모멘텀 |
| `volatility_20d` | ohlcv | ✅ | 0.15 | 20 | z_score (역) | 20일 변동성 (낮을수록 좋음) |
| `liquidity_20d` | ohlcv | ✅ | 0.15 | 20 | percentile_rank | 20일 평균 거래대금 |
| `turnover_rate` | ohlcv | ✅ | 0.10 | 20 | percentile_rank | 회전율 |
| `drawdown_from_high` | ohlcv | ✅ | 0.10 | 60 | min_max (역) | 고점 대비 낙폭 |

**V1 활성 feature 선정 이유:**
- 모두 OHLCV 데이터에서 파생 가능 → 외부 API 의존 없음
- 모멘텀 전략의 핵심 축(추세·위험·유동성)을 커버
- 정규화 후 가중 합산으로 단일 점수 산출 가능

#### V2 이후 비활성 슬롯

| key | source | enabled | weight | 비활성 이유 |
|---|---|---|---|---|
| `news_sentiment` | external_api | ❌ | 0.0 | 데이터 품질 미검증, API 비용, 지연 리스크 |
| `fear_index` | external_api | ❌ | 0.0 | VIX/VKOSPI 데이터 수급 안정성 미확인 |
| `market_breadth` | derived | ❌ | 0.0 | 계산 로직 정의 및 백테스트 검증 필요 |
| `macro_regime` | external_api | ❌ | 0.0 | 레짐 분류 모델 설계·검증 선행 필요 |

**비활성 슬롯 설계 원칙:**
- 구조상 수용 가능해야 하지만, 동시에 활성화하면 **원인 분리가 어렵고 데이터 품질 리스크가 커진다.**
- V1에서는 스캐너 핵심 성능(가격·거래·변동성)을 먼저 검증한 뒤, V2에서 외생 변수를 하나씩 활성화하며 A/B 검증한다.

---

### 2.3 Layer 3: Selector / Ranking

Feature matrix를 받아 최종 유니버스를 선별하는 계층이다.

#### 선별 파이프라인

```
raw candidates
  → pre_filters (사전 필터)
  → hard_exclusions (강제 제외)
  → feature scoring (가중 점수 계산)
  → ranking (순위 정렬)
  → top_n 선택
  → tie_breaker (동점 처리)
  → fallback_rule (후보 부족 시)
  → selected universe
```

#### Selector 설정 스키마

```json
{
  "selector": {
    "pre_filters": [
      {"field": "avg_volume_20d", "op": ">=", "value": 100000},
      {"field": "listing_days", "op": ">=", "value": 180},
      {"field": "price", "op": ">=", "value": 1000}
    ],
    "hard_exclusions": [
      {"field": "is_inverse", "op": "==", "value": true},
      {"field": "is_suspended", "op": "==", "value": true},
      {"field": "daily_limit_hit_5d", "op": ">", "value": 0}
    ],
    "ranking_formula": "weighted_sum",
    "top_n": 15,
    "tie_breaker": "liquidity_20d",
    "fallback_rule": {
      "min_candidates": 5,
      "action": "relax_pre_filters",
      "relaxation_order": ["min_avg_volume_20d", "min_listing_days"]
    }
  }
}
```

#### 랭킹 계산

```
score(ticker) = Σ (feature_i.weight × normalized_value_i)
                for feature_i in features where enabled=true
```

- 모든 feature는 정규화 후 0~1 범위로 변환
- `volatility`, `drawdown` 등 "낮을수록 좋은" feature는 역방향 정규화 적용
- 비활성 feature(`enabled=false`)는 점수 계산에서 완전히 제외

---

## 3. 통합 설정 스키마 (확장형)

```json
{
  "scanner": {
    "mode": "dynamic_etf_market",
    "version": "v1",
    "candidate_pool": { "..." },
    "features": [
      {
        "key": "price_momentum_3m",
        "source": "ohlcv",
        "enabled": true,
        "required": false,
        "weight": 0.30,
        "lookback": 60,
        "lag_days": 0,
        "freshness_ttl": "1d",
        "missing_policy": "exclude",
        "normalization": "percentile_rank",
        "notes": "3개월 가격 모멘텀 (종가 기준 수익률)"
      },
      {
        "key": "news_sentiment",
        "source": "external_api",
        "enabled": false,
        "required": false,
        "weight": 0.0,
        "lookback": 7,
        "lag_days": 1,
        "freshness_ttl": "1d",
        "missing_policy": "skip_scoring",
        "normalization": "z_score",
        "notes": "[V2 슬롯] 뉴스 감성 점수. V1에서는 비활성."
      }
    ],
    "selector": { "..." },
    "outputs": {
      "snapshot_path": "reports/tuning/universe_snapshot_latest.json",
      "feature_matrix_path": "reports/tuning/universe_feature_matrix_latest.csv",
      "selection_reason_path": "reports/tuning/universe_selection_reason_latest.md"
    }
  }
}
```

**핵심:** `features[]`는 리스트형이므로, 새 feature 추가 시 이 리스트에 객체 하나만 추가하면 된다. 코드 변경 없이 설정 파일만으로 feature set을 조절할 수 있다.

---

## 4. 산출물 / 증거 구조 설계

구현 완료 시 아래 3종의 증거 파일이 생성되어야 한다.

### 4.1 `reports/tuning/universe_snapshot_latest.json`

스캐너 실행 결과의 스냅샷이다.

```json
{
  "asof": "2026-03-30T21:00:00+09:00",
  "scanner_mode": "dynamic_etf_market",
  "scanner_version": "v1",
  "candidate_pool_size": 187,
  "pre_filter_passed": 62,
  "hard_exclusion_removed": 3,
  "scoring_eligible": 59,
  "selected_top_n": 15,
  "selected_tickers": ["069500", "229200", "..."],
  "excluded_tickers_with_reasons": [
    {"ticker": "123456", "reason": "avg_volume_20d < 100000"},
    {"ticker": "789012", "reason": "is_suspended == true"}
  ],
  "feature_weights_used": {
    "price_momentum_3m": 0.30,
    "price_momentum_6m": 0.20,
    "volatility_20d": 0.15,
    "liquidity_20d": 0.15,
    "turnover_rate": 0.10,
    "drawdown_from_high": 0.10
  },
  "disabled_features": ["news_sentiment", "fear_index", "market_breadth", "macro_regime"]
}
```

### 4.2 `reports/tuning/universe_feature_matrix_latest.csv`

모든 scoring 대상 후보의 feature 값 테이블이다.

| ticker | name | price_momentum_3m | price_momentum_6m | volatility_20d | liquidity_20d | turnover_rate | drawdown_from_high | composite_score | rank | selected |
|---|---|---|---|---|---|---|---|---|---|---|
| 069500 | KODEX 200 | 0.82 | 0.75 | 0.33 | 0.95 | 0.67 | 0.12 | 0.7315 | 1 | Y |
| 229200 | KODEX 코스닥150 | 0.78 | 0.68 | 0.41 | 0.88 | 0.72 | 0.18 | 0.6982 | 2 | Y |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

- 모든 feature 값은 정규화 후 수치
- `composite_score` = 가중 합산 점수
- `selected` = Y/N

### 4.3 `reports/tuning/universe_selection_reason_latest.md`

한국어로 작성되는 선택 근거 요약 문서이다.

최소 포함 내용:
- 스캐너 실행 일시 및 모드
- 후보 풀 규모 → 필터 후 → 최종 선택 수
- 상위 5~10개 종목의 선택 근거 요약
- 제외된 주요 종목과 사유
- 사용된 feature 활성/비활성 현황
- 이전 스냅샷 대비 변경 사항 (신규 편입 / 제외)

---

## 5. A/B 검증 계획

### 5.1 비교 대상

| 유니버스 모드 | 설명 | 비교 목적 |
|---|---|---|
| `fixed_current` | 기존 12종목 정적 | 기준선 (baseline) |
| `expanded_candidates` | 기존 33종목 정적 | 수동 확장 효과 측정 |
| `dynamic_etf_market` | 스캐너 자동 선별 | 동적 선별의 실질 효과 측정 |

### 5.2 검증 순서 (모드별 동일)

```
1. SSOT에 universe_mode 설정
2. Run Tune (Optuna 탐색)
3. 1등 파라미터 SSOT 반영
4. Run Full Backtest (전체 기간 검산)
5. 승격 판정 (promotion_verdict)
6. A/B 비교팩 갱신
```

### 5.3 비교 지표

| 지표 | 설명 |
|---|---|
| Best Score | Optuna 목적함수 기준 최고 점수 |
| CAGR (Full / 구간별) | 연환산 수익률 |
| MDD (Full / 구간별) | 최대 낙폭 |
| Sharpe (Full / 구간별) | 위험 조정 수익 |
| Overfit Penalty | 과적합 벌점 |
| Worst Segment | 최악 구간 |
| 유니버스 크기 | 선택된 종목 수 |
| 모멘텀 집중도 | 상위 종목 편중 여부 |

### 5.4 승격 판정 체계 연동

다이나믹 스캐너 결과도 기존 승격 판정 체계 안으로 들어와야 한다.

#### `used_universe_match` 연동

- `dynamic_etf_market` 모드에서는 스캐너가 산출한 `selected_tickers` 리스트가 SSOT의 `universe`에 반영된다.
- 승격 판정 시 `used_universe_match`는 다음과 같이 평가한다:
  - Tune 시점의 `selected_tickers` == Backtest 시점의 SSOT `universe` → `match = true`
  - 불일치 시 → `PROMOTE_CANDIDATE` 금지 (기존 규칙 유지)

#### `used_params_match_ssot` 연동

- 5축 파라미터 일치 여부는 기존과 동일하게 유지
- 유니버스 선택 방식이 바뀌어도 파라미터 정합성 체크는 독립적으로 작동

#### 스캐너 결과의 SSOT 반영 흐름

```
Scanner 실행 → universe_snapshot_latest.json 생성
  → 사용자가 "스캐너 결과 적용" 버튼 클릭 (수동)
  → SSOT의 universe 리스트를 snapshot의 selected_tickers로 교체
  → SSOT의 universe_mode를 "dynamic_etf_market"으로 설정
  → 이후 Tune/Backtest는 이 리스트 기준으로 실행
```

**중요:** 자동 적용(auto-promotion)은 하지 않는다. 사용자가 스냅샷을 확인하고 수동으로 적용한다.

---

## 6. 구현 로드맵 (향후 참고용)

| 단계 | 내용 | 전제 조건 |
|---|---|---|
| Step5A (본 단계) | 아키텍처 설계 + 문서화 | 없음 |
| Step5B | Candidate Pool + V1 Feature Provider 구현 | Step5A 설계 승인 |
| Step5C | Selector/Ranking 구현 + 증거 파일 생성 | Step5B 완료 |
| Step5D | 스캐너 결과 → SSOT 적용 배선 + UI 최소 노출 | Step5C 완료 |
| Step5E | dynamic_etf_market vs fixed A/B 검증 | Step5D 완료 |
| Step6+ | 외생 변수 슬롯 활성화 (하나씩) | Step5E A/B 기준선 확립 |

---

## 7. 위험 요소 및 대응

| 위험 | 영향 | 대응 |
|---|---|---|
| KRX ETF 목록 데이터 품질 | 상장폐지/거래정지 종목 혼입 | pre_filter에서 거래정지 체크 + hard_exclusion |
| Feature 계산 시간 과다 | 스캐너 실행이 Tune 전처리를 지연 | lookback 최대 120일 제한 + 캐싱 |
| 유니버스 급변 (매주 대폭 변경) | Tune 결과 안정성 저하 | `min_overlap_ratio` 제약 추가 고려 |
| 외생 변수 데이터 지연 | 뉴스/공포지수가 실시간이 아님 | `lag_days`, `freshness_ttl`로 제어 + V1에서 비활성 |

---

*본 문서는 설계 전용이며, 실제 코드/UI/Objective 변경은 포함하지 않는다.*
