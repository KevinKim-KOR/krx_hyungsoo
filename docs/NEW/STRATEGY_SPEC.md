# STRATEGY_SPEC — 전략 스펙 정의 및 규칙 (v2 개정)

## 1. 목적
투자전략은 YAML 기반 스펙 파일로 정의하며, 각 전략은 `strategies/{전략명}` 폴더에 개별로 구성된다. 본 문서는 각 필드의 의미, 유효성 규칙, 검증 절차를 명시하고 **핵심 보유 종목(CORE_HOLDINGS)** 규칙을 추가 반영한다.

---

## 2. 디렉터리 구조
```
strategies/
  momentum_topN_v1/
    strategy.yaml
    params.yaml
    backtest_config.yaml
  dividend_stable_v1/
    strategy.yaml
```
- 각 전략은 독립된 폴더에 구성되어야 하며, 동일 스키마를 따른다.
- 백테스트는 동일 유니버스 내 여러 전략 폴더를 비교 가능해야 한다.

---

## 3. 스펙 구조
```yaml
id: momentum_topN_v1            # 전략 식별자
universe: KOR_ETF_CORE          # 종목 유니버스
lookback: [21, 63, 126]         # 룩백 기간 (거래일)
weights: [0.5, 0.3, 0.2]        # 룩백 가중치
filters:
  min_liquidity: 3e8            # 일평균 거래대금 최소값
  exclude_categories: [LEVERAGED, INVERSE]
ranking: zscore_weighted_mom    # 랭킹 알고리즘
action: long_only               # 매수 전략 유형
risk:
  position_cap: 0.25            # 종목 비중 상한
  portfolio_vol_target: 0.12    # 목표 변동성
  cooldown_days: 5              # 재진입 제한 기간
rebalance: WEEKLY_FRI           # 리밸런스 주기
fees:
  commission_bps: 3             # 수수료
  slippage_bps: 5               # 슬리피지
core_holdings: ["091160", "426030", "473640"]  # 핵심 보유 종목 목록
benchmark: KODEX_200            # 비교 지수
alert:
  channel: slack:invest_ops     # 알림 채널
  template: default_v1          # 템플릿 ID
```

---

## 4. CORE_HOLDINGS 필드 정의
| 필드 | 타입 | 설명 | 필수 | 유효성 |
|------|------|------|------|--------|
| core_holdings | list[str] | 매도 제외 및 자동 매수 대상 종목 | ❌ | Universe 내 종목이어야 함 |

**규칙:**
- 매도 신호(`SELL_TREND`, `SELL_RSI`, `CUT_STOPLOSS`, `SELL_REPLACE`) 무시.
- 포트폴리오에 없을 경우 자동 매수.
- TOPN 계산에서 제외.
- 백테스트와 실시간 추천 모두 동일하게 적용.
- `HOLD_CORE` 상태로 표시되며, `HOLD` 바로 아래 우선순위를 가짐.

---

## 5. 필드 정의 요약
| 필드 | 타입 | 설명 | 필수 | 유효성 |
|------|------|------|------|--------|
| id | str | 전략명(버전 포함) | ✅ | 중복 불가 |
| universe | str | 유니버스 키 | ✅ | 존재해야 함 |
| lookback | list[int] | 룩백 기간 | ✅ | >0 |
| weights | list[float] | 룩백 가중치 | ✅ | 합=1.0 ±0.001 |
| filters.min_liquidity | float | 최소 거래대금 | ✅ | >0 |
| ranking | str | 랭킹 알고리즘 ID | ✅ | 존재해야 함 |
| action | str | long_only/long_short | ❌ | 기본: long_only |
| risk.* | float/int | 리스크 제어 파라미터 | ✅ | 유효 범위 내 |
| rebalance | str | 리밸런스 주기 | ✅ | DAILY/WEEKLY/MONTHLY |
| fees.* | int | 거래비용 | ✅ | 0 이상 |
| core_holdings | list[str] | 핵심 보유 종목 | ❌ | Universe 내 존재 |
| benchmark | str | 비교 지수 | ✅ | 존재해야 함 |
| alert.* | str | 알림 설정 | ✅ | 유효 경로 존재 |

---

## 6. 검증 프로세스
1. YAML 로드 → `core.strategy.schema` 검증.
2. `universe`, `ranking`, `core_holdings` 존재 여부 점검.
3. Universe 외 종목 발견 시 로그 경고(`WARN: CORE_HOLDINGS invalid`).
4. 샘플 데이터 기반 드라이런 후 결과 리포트(`reports/validation/{strategy_id}.md`).

---

## 7. 전략 검증 체크리스트
- [ ] `strategies/{name}` 폴더 존재 여부 확인
- [ ] core_holdings 유효성 검증 완료
- [ ] 룩백/랭킹 정의 확인
- [ ] 리스크/필터 설정 완료
- [ ] 백테스트 비교 전략 구성 가능

---

> v2에서는 `CORE_HOLDINGS`(HOLD_CORE 상태) 및 전략 폴더 구조를 통합 반영했다.

