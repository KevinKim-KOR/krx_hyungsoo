# 튜닝 검산 요약

- 실행 시각(asof): 2026-04-02T23:33:29+09:00
- study_name: tune_quick_dynamic_etf_market_5axis_dynamic_risk_v1
- mode: quick
- universe_mode: dynamic_etf_market (15종목) [snapshot: snap_20260402_233304_503b929d]
- 기간: 2025-10-04 ~ 2026-04-01
- best trial 번호: 15
- best params: momentum_period=44, volatility_period=19, entry_threshold=0.04, stop_loss=-0.04000000000000001, max_positions=2

## Full Period 요약
- CAGR: 148.7376%
- MDD: 6.2519%
- Sharpe: 3.8215

## 구간 리스크 요약
- 최악 구간: SEG_1
- 과최적화 벌점: 5.0000

## 상위 5개 후보 비교 요약
| 순위 | Trial | Score | momentum_period | volatility_period | entry_threshold | stop_loss | max_positions | worst_segment |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 15 | -3.264163 | 44 | 19 | 0.04 | -0.0400 | 2 | SEG_1 |
| 2 | 3 | -3.415363 | 44 | 18 | 0.05 | -0.0500 | 2 | SEG_1 |
| 3 | 2 | -3.472435 | 40 | 28 | 0.07 | -0.0600 | 2 | SEG_1 |
| 4 | 11 | -3.472435 | 40 | 28 | 0.07 | -0.0700 | 2 | SEG_1 |
| 5 | 9 | -3.718475 | 54 | 18 | 0.05 | -0.0500 | 2 | SEG_1 |

## 현재 단계 해석
이 결과는 후보 탐색용이며, Full Backtest 검증 후에만 승격 판단이 가능합니다.
