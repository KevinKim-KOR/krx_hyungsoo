# 유니버스 선택 근거

- 실행 시각: 2026-04-15T21:29:45+09:00
- scanner_mode: dynamic_etf_market
- scanner_version: v1

## 후보 풀 요약

- 전체 후보: 1093
- pre-filter 후: 174
- hard exclusion 제거: 165
- scoring eligible: 163

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
| 1 | 396500 | TIGER 반도체TOP10 | 0.768340 | price_momentum_3m(0.282), price_momentum_6m(0.191), liquidity_20d(0.149) |
| 2 | 0098F0 | KODEX 원자력SMR | 0.759592 | price_momentum_3m(0.295), price_momentum_6m(0.194), liquidity_20d(0.135) |
| 3 | 091160 | KODEX 반도체 | 0.756353 | price_momentum_3m(0.286), price_momentum_6m(0.188), liquidity_20d(0.147) |
| 4 | 0091P0 | TIGER 코리아원자력 | 0.750110 | price_momentum_3m(0.300), price_momentum_6m(0.200), liquidity_20d(0.141) |
| 5 | 469150 | ACE AI반도체TOP3+ | 0.730939 | price_momentum_3m(0.289), price_momentum_6m(0.195), liquidity_20d(0.121) |
| 6 | 395270 | HANARO Fn K-반도체 | 0.724604 | price_momentum_3m(0.293), price_momentum_6m(0.199), liquidity_20d(0.139) |
| 7 | 442580 | PLUS 글로벌HBM반도체 | 0.709149 | price_momentum_3m(0.270), price_momentum_6m(0.196), turnover_rate(0.099) |
| 8 | 315960 | RISE 대형고배당10TR | 0.707825 | price_momentum_3m(0.268), price_momentum_6m(0.187), turnover_rate(0.098) |
| 9 | 157500 | TIGER 증권 | 0.705291 | price_momentum_3m(0.298), price_momentum_6m(0.185), liquidity_20d(0.106) |
| 10 | 292150 | TIGER 코리아TOP10 | 0.699493 | price_momentum_3m(0.221), price_momentum_6m(0.179), liquidity_20d(0.134) |

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
| 477080 | is_synthetic |
