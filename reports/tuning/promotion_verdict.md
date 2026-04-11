# 승격 판정

- 현재 판정: 기각
- SSOT 반영 여부: 예
- 유니버스 일치: 예
- universe_snapshot_id: snap_20260411_002122_700c57e6
- universe_mode: dynamic_etf_market
- universe_size: 15

## Full Backtest 핵심 수치
- CAGR: 12.3870%
- MDD: 12.7446%
- Sharpe: 1.1019

## Tune 핵심 수치
- Best Trial: 15
- Best Score: -3.2642
- 최악 구간: SEG_1
- 과최적화 벌점: 5.0000

## 판정 사유
- Full Backtest CAGR이 15% 초과 기준을 만족하지 못합니다.
- Full Backtest MDD가 10% 미만 기준을 만족하지 못합니다.
- 최악 구간이 SEG_1이므로 초기 구간 일관성 재검토가 필요합니다.
- 과최적화 벌점이 높아 추가 검산이 필요합니다.

## 다음 행동
- 현재 후보는 기준 정합성은 충족했지만 Full Backtest 성능 기준을 만족하지 못해 기각합니다. 다음 후보를 검토하거나 유니버스/탐색범위를 재검토합니다.
