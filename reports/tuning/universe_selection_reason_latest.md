# 유니버스 선택 근거

- 실행 시각: 2026-04-08T22:20:26+09:00
- scanner_mode: dynamic_etf_market
- scanner_version: v1

## 후보 풀 요약

- 전체 후보: 1088
- pre-filter 후: 168
- hard exclusion 제거: 165
- scoring eligible: 159

## 선택 결과

- ranking_formula: weighted_sum
- top_n: 15
- tie_breaker: liquidity_20d → ticker
- fallback 적용: 아니오
- 최종 선택: 15종목
- selection_status: ok
- min_candidates_met: 예

## 상위 10개 종목

| 순위 | 종목코드 | 종목명 | composite_score | 주요 기여 feature |
| --- | --- | --- | --- | --- |
| 1 | 0091P0 | TIGER 코리아원자력 | 0.787499 | price_momentum_3m(0.300), price_momentum_6m(0.200), liquidity_20d(0.141) |
| 2 | 396500 | TIGER 반도체TOP10 | 0.786508 | price_momentum_3m(0.276), price_momentum_6m(0.194), liquidity_20d(0.149) |
| 3 | 0098F0 | KODEX 원자력SMR | 0.784358 | price_momentum_3m(0.298), price_momentum_6m(0.187), liquidity_20d(0.133) |
| 4 | 091160 | KODEX 반도체 | 0.778849 | price_momentum_3m(0.282), price_momentum_6m(0.186), liquidity_20d(0.147) |
| 5 | 469150 | ACE AI반도체TOP3+ | 0.758121 | price_momentum_3m(0.284), price_momentum_6m(0.196), liquidity_20d(0.120) |
| 6 | 157500 | TIGER 증권 | 0.747435 | price_momentum_3m(0.296), price_momentum_6m(0.190), liquidity_20d(0.105) |
| 7 | 315960 | RISE 대형고배당10TR | 0.743367 | price_momentum_3m(0.263), price_momentum_6m(0.195), liquidity_20d(0.106) |
| 8 | 433500 | ACE 원자력TOP10 | 0.734619 | price_momentum_3m(0.293), price_momentum_6m(0.189), turnover_rate(0.094) |
| 9 | 102970 | KODEX 증권 | 0.733642 | price_momentum_3m(0.295), price_momentum_6m(0.182), liquidity_20d(0.129) |
| 10 | 395270 | HANARO Fn K-반도체 | 0.728188 | price_momentum_3m(0.287), price_momentum_6m(0.199), liquidity_20d(0.135) |

## 주요 제외 종목 (상위 10개)

| 종목코드 | 사유 |
| --- | --- |
| 459580 | is_synthetic |
| 122630 | is_leveraged |
| 357870 | is_synthetic |
| 423160 | is_synthetic |
| 233740 | is_leveraged |
| 481050 | is_synthetic |
| 449170 | is_synthetic |
| 488080 | is_leveraged |
| 475630 | is_synthetic |
| 494310 | is_leveraged |
