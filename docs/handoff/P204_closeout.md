# P204 종료 문서

## 1. P204 완료 범위

- Step 1: SQLite 영속화 / resume / checkpoint
- Step 2: `equal_3way` 구간 산출
- Step 3: 멀티구간 기반 목적함수 + Safe Math
- Step 4A: 검산 파일 / Top 5 / 요약 리포트
- Step 4B: 승격 판정 게이트

## 2. 현재 운영 루프

1. `Run Tune`
2. Top 5 / 검산 파일 확인
3. Best Params를 SSOT에 수동 반영
4. `Run Full Backtest`
5. `승격 판정` 확인

## 3. 현재 최신 스냅샷

- tune asof: `2026-03-25T23:11:00+09:00`
- best trial: `63`
- best params:
  - `momentum_period = 55`
  - `stop_loss = -0.09000000000000001`
  - `max_positions = 4`
- best score: `-4.2637`
- worst segment: `SEG_1`
- overfit penalty: `5.0`
- full backtest asof: `2026-03-25T22:29:57+09:00`
- full backtest:
  - `CAGR = 9.293698765332303`
  - `MDD = 9.1062`
  - `Sharpe = 1.4367`
- promotion verdict: `REJECT`
- candidate_applied_to_ssot: `true`

## 4. 이번 단계에서 의도적으로 제외한 것

다음 항목은 미완료가 아니라 P204 범위 밖으로 유지했다.

- 유니버스 확장
- 뉴스 / 공포지수 등 외생 변수
- 체결 모델 현실화(익일 시가)
- 자동 승격 / 자동 OCI 반영
- 검색 공간 확대(현재 3축 외)

## 5. 현재 해석

`P204는 후보 탐색·검산·승격 판정까지 완료했으며, 실전 확장은 P205 범위입니다.`

## 6. 운영자 주의사항

- Tune 결과와 Full Backtest 결과는 역할이 다르다.
- 같은 조건 반복 Tune은 새 후보 발굴보다 안정성 확인 목적이 크다.
- 현재 검색 공간은 `momentum_period / stop_loss / max_positions` 3축이다.
- `stop_loss` 는 SSOT의 `exit_threshold` 와 같은 개념으로 취급한다.
- 사용자가 임의로 추가한 UI 편의 기능(예: SSOT 자동 적용 버튼)은 P204 공식 합격 범위에 포함하지 않는다.
