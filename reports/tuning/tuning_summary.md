# 튜닝 검산 요약

- 실행 시각(asof): 2026-03-30T20:33:43+09:00
- study_name: tune_quick_expanded_candidates_5axis_v1
- mode: quick
- universe_mode: expanded_candidates (33종목)
- 기간: 2025-10-01 ~ 2026-03-29
- best trial 번호: 31
- best params: momentum_period=49, volatility_period=21, entry_threshold=0.03, stop_loss=-0.05, max_positions=4

## Full Period 요약
- CAGR: -4.9368%
- MDD: 15.0965%
- Sharpe: -0.1423

## 구간 리스크 요약
- 최악 구간: SEG_1
- 과최적화 벌점: 5.0000

## 상위 5개 후보 비교 요약
| 순위 | Trial | Score | momentum_period | volatility_period | entry_threshold | stop_loss | max_positions | worst_segment |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 31 | -4.319944 | 49 | 21 | 0.03 | -0.0500 | 4 | SEG_1 |
| 2 | 20 | -4.416065 | 50 | 22 | 0.02 | -0.0500 | 5 | SEG_1 |
| 3 | 24 | -4.428691 | 47 | 22 | 0.03 | -0.0700 | 4 | SEG_1 |
| 4 | 32 | -4.428691 | 47 | 21 | 0.04 | -0.0600 | 4 | SEG_1 |
| 5 | 17 | -4.442598 | 51 | 17 | 0.02 | -0.0500 | 5 | SEG_1 |

## 현재 단계 해석
이 결과는 후보 탐색용이며, Full Backtest 검증 후에만 승격 판단이 가능합니다.
