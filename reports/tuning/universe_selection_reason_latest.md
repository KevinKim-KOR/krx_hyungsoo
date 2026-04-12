# 유니버스 선택 근거

- 실행 시각: 2026-04-12T15:17:46+09:00
- scanner_mode: dynamic_etf_market
- scanner_version: v1

## 후보 풀 요약

- 전체 후보: 1088
- pre-filter 후: 171
- hard exclusion 제거: 165
- scoring eligible: 161

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
| 1 | 396500 | TIGER 반도체TOP10 | 0.774062 | price_momentum_3m(0.282), price_momentum_6m(0.194), liquidity_20d(0.149) |
| 2 | 091160 | KODEX 반도체 | 0.758432 | price_momentum_3m(0.286), price_momentum_6m(0.185), liquidity_20d(0.147) |
| 3 | 0098F0 | KODEX 원자력SMR | 0.756824 | price_momentum_3m(0.298), price_momentum_6m(0.191), liquidity_20d(0.135) |
| 4 | 0091P0 | TIGER 코리아원자력 | 0.749439 | price_momentum_3m(0.300), price_momentum_6m(0.200), liquidity_20d(0.142) |
| 5 | 469150 | ACE AI반도체TOP3+ | 0.735981 | price_momentum_3m(0.287), price_momentum_6m(0.196), liquidity_20d(0.121) |
| 6 | 315960 | RISE 대형고배당10TR | 0.721534 | price_momentum_3m(0.271), price_momentum_6m(0.190), turnover_rate(0.098) |
| 7 | 395270 | HANARO Fn K-반도체 | 0.720743 | price_momentum_3m(0.291), price_momentum_6m(0.199), liquidity_20d(0.138) |
| 8 | 157500 | TIGER 증권 | 0.713980 | price_momentum_3m(0.295), price_momentum_6m(0.188), liquidity_20d(0.102) |
| 9 | 442580 | PLUS 글로벌HBM반도체 | 0.708776 | price_momentum_3m(0.266), price_momentum_6m(0.198), turnover_rate(0.099) |
| 10 | 292150 | TIGER 코리아TOP10 | 0.706204 | price_momentum_3m(0.224), price_momentum_6m(0.180), liquidity_20d(0.133) |

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
| 475630 | is_synthetic |
| 488080 | is_leveraged |
| 477080 | is_synthetic |
