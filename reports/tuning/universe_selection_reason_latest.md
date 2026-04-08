# 유니버스 선택 근거

- 실행 시각: 2026-04-09T00:28:46+09:00
- scanner_mode: dynamic_etf_market
- scanner_version: v1

## 후보 풀 요약

- 전체 후보: 1088
- pre-filter 후: 169
- hard exclusion 제거: 165
- scoring eligible: 160

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
| 1 | 396500 | TIGER 반도체TOP10 | 0.771687 | price_momentum_3m(0.280), price_momentum_6m(0.195), liquidity_20d(0.149) |
| 2 | 091160 | KODEX 반도체 | 0.758729 | price_momentum_3m(0.284), price_momentum_6m(0.189), liquidity_20d(0.147) |
| 3 | 0098F0 | KODEX 원자력SMR | 0.753666 | price_momentum_3m(0.298), price_momentum_6m(0.194), liquidity_20d(0.134) |
| 4 | 0091P0 | TIGER 코리아원자력 | 0.748742 | price_momentum_3m(0.300), price_momentum_6m(0.200), liquidity_20d(0.143) |
| 5 | 469150 | ACE AI반도체TOP3+ | 0.739517 | price_momentum_3m(0.287), price_momentum_6m(0.198), liquidity_20d(0.121) |
| 6 | 315960 | RISE 대형고배당10TR | 0.723572 | price_momentum_3m(0.269), price_momentum_6m(0.191), liquidity_20d(0.103) |
| 7 | 157500 | TIGER 증권 | 0.720193 | price_momentum_3m(0.295), price_momentum_6m(0.190), liquidity_20d(0.104) |
| 8 | 395270 | HANARO Fn K-반도체 | 0.718326 | price_momentum_3m(0.289), price_momentum_6m(0.199), liquidity_20d(0.137) |
| 9 | 102970 | KODEX 증권 | 0.710299 | price_momentum_3m(0.296), price_momentum_6m(0.186), liquidity_20d(0.129) |
| 10 | 442580 | PLUS 글로벌HBM반도체 | 0.707253 | price_momentum_3m(0.262), price_momentum_6m(0.196), turnover_rate(0.099) |

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
