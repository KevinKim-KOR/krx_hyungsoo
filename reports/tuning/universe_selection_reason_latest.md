# 유니버스 선택 근거

- 실행 시각: 2026-03-31T00:06:47+09:00
- scanner_mode: dynamic_etf_market
- scanner_version: v1

## 후보 풀 요약

- 전체 후보: 1077
- pre-filter 후: 173
- hard exclusion 제거: 165
- scoring eligible: 173

## 선택 결과

- ranking_formula: weighted_sum
- top_n: 15
- tie_breaker: liquidity_20d → ticker
- fallback 적용: 아니오
- 최종 선택: 15종목
- selection_status: ok
- min_candidates_met: 예

## 상위 10개 종목

| 순위 | 종목코드 | 종목명 | composite_score |
| --- | --- | --- | --- |
| 1 | 396500 | TIGER 반도체TOP10 | 0.801222 |
| 2 | 091160 | KODEX 반도체 | 0.784621 |
| 3 | 469150 | ACE AI반도체TOP3+ | 0.784430 |
| 4 | 292150 | TIGER 코리아TOP10 | 0.780276 |
| 5 | 0091P0 | TIGER 코리아원자력 | 0.774766 |
| 6 | 0098F0 | KODEX 원자력SMR | 0.765798 |
| 7 | 395270 | HANARO Fn K-반도체 | 0.762687 |
| 8 | 315960 | RISE 대형고배당10TR | 0.761445 |
| 9 | 442580 | PLUS 글로벌HBM반도체 | 0.746167 |
| 10 | 395160 | KODEX AI반도체 | 0.744205 |

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
| 477080 | is_synthetic |
| 252670 | is_inverse |
