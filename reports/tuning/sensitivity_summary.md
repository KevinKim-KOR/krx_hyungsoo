# 감도 보정 결과 (Sensitivity Calibration)

실행 시각: 2026-03-28 17:54:56 KST

## Baseline 5축

- `momentum_period`: 54
- `volatility_period`: 13
- `entry_threshold`: 0.05
- `stop_loss`: -0.07
- `max_positions`: 4

Baseline 성과: CAGR=8.1323%, MDD=4.7404%, Sharpe=0.9408, Trades=7

## volatility_period 감도 결과

- 스캔 값: [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
- 감도 있음: [2] (성과 급감 방향만)
- 무반응 구간: [4, 6, 8, 10, 12, 14, 16, 18, 20] (baseline과 동일)
- Dead Zone: 없음
- **LOW_SENSITIVITY**: 예
- 최종 범위: 기존 유지 (12~24)
- 사유: 4~20 범위에서 결과가 완전히 동일. vol=2에서만 성과 급감(CAGR -5.14). 현재 6개월 quick 데이터 창에서는 이 축의 탐색 가치가 제한적.

## entry_threshold 감도 결과

- 스캔 값: [0.01, 0.03, 0.05, 0.07, 0.10, 0.15, 0.20, 0.30]
- 감도 있음: [0.07, 0.10, 0.15, 0.20, 0.30] (모두 성과 하락 방향)
- 무반응 구간: [0.01, 0.03, 0.05] (baseline과 동일)
- Dead Zone: 없음
- **LOW_SENSITIVITY**: 예
- 최종 범위: 기존 유지 (0.01~0.05)
- 사유: 0.01~0.05에서 결과 동일. 0.07부터 CAGR 하락 시작, 0.10에서 급감(CAGR 1.45). baseline(0.05)이 이미 최적 근처이며 탐색 범위를 넓히면 성과 악화 방향만 추가됨.

## 해석

현재 데이터 창(6개월 quick backtest)에서는 두 축 모두 감도가 낮으므로 범위를 보수적으로 유지합니다.

이는 새 2축이 "연결되지 않았다"가 아니라 **현재 유니버스+데이터 기간에서 리밸런싱 시점의 후보 필터링에 큰 영향을 주지 않기 때문**입니다. 유니버스 확장 또는 데이터 기간 연장 시 감도가 달라질 수 있으며, 그때 범위를 재조정해야 합니다.

## 검산 파일

- `sensitivity_volatility_period.csv` — volatility_period 10개 후보 스캔 결과
- `sensitivity_entry_threshold.csv` — entry_threshold 8개 후보 스캔 결과
