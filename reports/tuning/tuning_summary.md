# 튜닝 검산 요약

- 실행 시각(asof): 2026-03-28T18:16:35+09:00
- study_name: tune_quick_069500_P204_STEP3_V2
- mode: quick
- 기간: 2025-09-29 ~ 2026-03-27
- best trial 번호: 163
- best params: momentum_period=54, volatility_period=13, entry_threshold=0.05, stop_loss=-0.07, max_positions=4

## Full Period 요약
- CAGR: 44.2865%
- MDD: 6.3595%
- Sharpe: 1.8703

## 구간 리스크 요약
- 최악 구간: SEG_1
- 과최적화 벌점: 5.0000

## 상위 5개 후보 비교 요약
| 순위 | Trial | Score | momentum_period | volatility_period | entry_threshold | stop_loss | max_positions | worst_segment |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 163 | -4.262703 | 54 | 13 | 0.05 | -0.0700 | 4 | SEG_1 |
| 2 | 170 | -4.262703 | 54 | 13 | 0.05 | -0.0900 | 4 | SEG_1 |
| 3 | 184 | -4.262703 | 54 | 12 | 0.05 | -0.0900 | 4 | SEG_1 |
| 4 | 63 | -4.263669 | 55 | None | 0.00 | -0.0900 | 4 | SEG_1 |
| 5 | 72 | -4.263669 | 55 | None | 0.00 | -0.0900 | 4 | SEG_1 |

## 감도 보정 결론 (P205-STEP2)
신규 2축(volatility_period, entry_threshold)은 현재 데이터 창(6개월 quick)에서 LOW_SENSITIVITY로 판단되어 기존 범위를 유지합니다.
- volatility_period: 12~24 step 1 (기존 유지)
- entry_threshold: 0.01~0.05 step 0.01 (기존 유지)

## 현재 단계 해석
이 결과는 후보 탐색용이며, Full Backtest 검증 후에만 승격 판단이 가능합니다.
