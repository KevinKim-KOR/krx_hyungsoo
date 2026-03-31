# 승격 판정

- 현재 판정: 기각
- SSOT 반영 여부: 예
- 유니버스 일치: 아니오
- universe_snapshot_id: None
- universe_mode: expanded_candidates
- universe_size: 33

## Full Backtest 핵심 수치
- CAGR: 5.6708%
- MDD: 5.1739%
- Sharpe: 1.0684

## Tune 핵심 수치
- Best Trial: 31
- Best Score: -4.3199
- 최악 구간: SEG_1
- 과최적화 벌점: 5.0000

## 판정 사유
- Full Backtest CAGR이 15% 초과 기준을 만족하지 못합니다.
- 최악 구간이 SEG_1이므로 초기 구간 일관성 재검토가 필요합니다.
- 과최적화 벌점이 높아 추가 검산이 필요합니다.
- 튜닝 점수가 음수이므로 해석 경고가 필요합니다.

## 다음 행동
- 현재 후보는 기준 정합성은 충족했지만 Full Backtest 성능 기준을 만족하지 못해 기각합니다. 다음 후보를 검토하거나 유니버스/탐색범위를 재검토합니다.
