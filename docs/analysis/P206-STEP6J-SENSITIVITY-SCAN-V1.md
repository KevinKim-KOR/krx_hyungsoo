# P206-STEP6J: Hybrid B+D 민감도 스캔

> asof: 2026-04-09
> 상태: 완료 (날짜 보정 후 재실행)

---

## 1. 목적

Step6I에서 구현한 B+D 정책의 5축 파라미터 공간을 체계적으로 탐색하여 최적 조합을 찾는다.

---

## 2. 스캔 축 (5축)

| 축 | 파라미터 | 탐색 범위 | 의미 |
|---|---|---|---|
| 1 | neutral_risky_pct | [0.35, 0.50, 0.65, 0.80, 0.95] | neutral 시 위험자산 비중 |
| 2 | neutral_dollar_pct | [0.0, 0.10, 0.20, 0.30] | neutral 시 달러 ETF 비중 |
| 3 | riskoff_dollar_pct | [0.30, 0.50, 0.70] | risk_off 시 달러 ETF 비중 |
| 4 | domestic_neutral_threshold | [-0.005, -0.01, -0.015, -0.02, -0.03] | 069500 neutral 판정 기준 |
| 5 | domestic_riskoff_threshold | [-0.03, -0.05] | 069500 risk_off 판정 기준 |

### 제약 조건
- `neutral_risky_pct + neutral_dollar_pct <= 0.95` (최소 5% cash)
- `domestic_riskoff_threshold < domestic_neutral_threshold`

### 총 조합: 405개

---

## 3. 구현

### 3.1 스캔 스크립트

`app/tuning/hybrid_bd_sensitivity_scan.py` 신규 생성.

- `run_backtest(skip_baselines=True)` 파이프라인 재사용
- `fear_threshold_override`를 통한 파라미터 주입
- 비교군 baseline 계산 비활성화 → 1회당 ~0.7초 (405조합 ≈ 5분)
- 순위 매기기: MDD<10 우선, CAGR>15 다음, Sharpe 순

### 3.2 skip_baselines 파라미터

`run_backtest()`에 `skip_baselines=False` 파라미터 추가.
스캔 시 비교군 3종 계산을 건너뛰어 실행 시간 75% 절감.

---

## 4. 스캔 결과

### 4.1 전체 요약

| 항목 | 값 |
|---|---|
| 총 조합 | 405 |
| PROMOTE (CAGR>15 + MDD<10) | **0** |
| CAGR_OK (CAGR>15) | 105 |
| REJECT | 300 |
| MDD 범위 | 12.26% ~ 12.29% |
| CAGR 범위 | 5.09% ~ 19.18% |

### 4.2 상위 후보

| 순위 | nrp | ndp | rdp | dnt | CAGR | MDD | Sharpe | N | RO |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.80 | 0.10 | 0.30 | -0.015 | 15.05% | 12.27% | 1.19 | 13 | 4 |
| 8 | 0.95 | 0.00 | 0.30 | -0.015 | 19.18% | 12.28% | 1.39 | 13 | 4 |

### 4.3 핵심 발견

1. **MDD는 배분 파라미터로 통제 불가**: 모든 405조합에서 MDD ≈ 12.27%. drawdown이 risk_on 구간에서 발생하므로 neutral/risk_off 배분을 아무리 바꿔도 MDD에 영향 없음.

2. **neutral_risky_pct가 CAGR의 지배적 변수**: nrp 0.35 → CAGR ~10%, nrp 0.95 → CAGR ~19%. 나머지 파라미터 영향 미미.

3. **domestic_neutral_threshold 효과 확인**: dnt=-0.005일 때 N=16, dnt=-0.03일 때 N=9. 느슨한 threshold → neutral 빈도 증가 → CAGR 감소.

4. **domestic_riskoff_threshold 효과 미미**: 모든 조합에서 RO=4. 069500 수익률이 -3% 이하인 날이 백테스트 기간 내 없어 threshold 변경 무의미.

---

## 5. 산출물

| 산출물 | 경로 |
|---|---|
| 감도 그리드 | reports/tuning/hybrid_bd_sensitivity_grid.csv |
| 감도 요약 | reports/tuning/hybrid_bd_sensitivity_summary.md |

---

## 6. 수정 파일

| 파일 | 변경 |
|---|---|
| `app/tuning/hybrid_bd_sensitivity_scan.py` | 신규 — 5축 그리드 스캔 |
| `app/run_backtest.py` | `skip_baselines` 파라미터 추가 |

---

## 7. 후속 과제

- MDD<10 달성을 위해서는 **risk_on 구간 자체의 방어 메커니즘** 필요
  - 추가 센서 (국내 intraday, 거래량 급변 등)
  - 동적 stop-loss
  - risk_on 내 부분 방어 (soft neutral)
- 현재 운영 정책(nrp=0.35)은 보수적. 스캔 결과상 nrp 상향 여지 있음.

---

## 8. 커밋 이력

| 커밋 | 내용 |
|---|---|
| `0c0b1edc` | P206-STEP6J: B+D 민감도 스캔 (216조합) + neutral 배분 최적화 |
| `5af9d799` | P206-STEP6J-FIX: regime schedule 날짜 보정 + 민감도 스캔 재구현 |
