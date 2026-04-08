# P206-STEP6I: Hybrid B+D 정책 구현

> asof: 2026-04-08
> 상태: 구현 완료

---

## 1. 배경 및 현재 상태

### Step6H 설계 결론

Step6H에서 4개 정책 후보(A/B/C/D) 비교 후 **안 B + D 조합**을 추천안으로 확정.

| 항목 | 현행 (Step6G) | B+D 변경 |
|---|---|---|
| domestic 단독 risk_off | hard gate (100% cash) | **neutral로 격하** |
| neutral 배분 | 50% cash | 50% 위험 + 30% 현금 + 20% 달러 ETF |
| risk_off 배분 | 100% cash | 50% 현금 + 50% 달러 ETF |
| 안전자산 | 없음 | 261240 (KOSEF 미국달러선물) |

---

## 2. 구현 내용

### 2.1 진리표 수정 — exo_regime_filter.py

`compute_hybrid_aggregate()` 함수에서 domestic 단독 risk_off → neutral 격하 구현.

| Global | Domestic | 변경 전 | 변경 후 |
|---|---|---|---|
| risk_on | risk_off | risk_off | **neutral** |
| neutral | risk_off | risk_off | **neutral** |
| risk_off | risk_off | risk_off | risk_off (유지) |

핵심: `global_state == "risk_off"`일 때만 aggregate risk_off 발동.

### 2.2 안전자산 배분 — backtest_runner.py

기존 `adjusted_weights` 로직에 파라미터화된 배분 삽입 (P206-STEP6J 라벨).

```
neutral 시:
  adjusted_weights = {k: v * neutral_risky_pct for k, v in adjusted_weights.items()}
  adjusted_weights[safe_ticker] += neutral_dollar_pct

risk_off 시:
  adjusted_weights = {}
  adjusted_weights[safe_ticker] = riskoff_dollar_pct
```

기본값: `neutral_risky_pct=0.35`, `neutral_dollar_pct=0.20`, `riskoff_dollar_pct=0.50`

### 2.3 안전자산 ETF 데이터 — run_backtest.py

- 261240 (KOSEF 미국달러선물)을 OHLCV fetch 대상에 자동 추가
- `_hybrid["safe_asset_ticker"] = "261240"` 설정
- `fear_threshold_override`를 통한 배분 파라미터 주입 지원

### 2.4 비교군 4종 동적 계산

run_backtest.py 내에서 동일 기간 baseline 3종을 동적으로 계산하여 비교:

| # | 구성 | 비고 |
|---|---|---|
| 1 | no_regime | regime 없이 전량 투자 |
| 2 | vix_baseline | VIX 단독 (기본 임계치) |
| 3 | hybrid_cash_only | B+D 진리표 적용, 안전자산 없음 |
| 4 | **hybrid_B+D** | B+D + 안전자산 스위칭 (본 구현) |

### 2.5 산출물

| 산출물 | 경로 |
|---|---|
| hybrid_policy_compare.csv | reports/tuning/ |
| hybrid_policy_summary.md | reports/tuning/ |
| hybrid_regime_schedule_latest.csv/json | reports/tuning/ |
| hybrid_regime_reason_latest.md | reports/tuning/ |
| hybrid_regime_verdict_latest.json | reports/tuning/ |
| dynamic_evidence_latest.md | reports/tuning/ |

evidence 확장 필드:
- Policy Variant, Domestic Handling, Safe Asset Mode
- Neutral/Risk-off Alloc, Checkpoint Summary
- One-line Conclusion

---

## 3. 수정 파일

| 파일 | 변경 |
|---|---|
| `app/backtest/strategy/exo_regime_filter.py` | 진리표 수정, SAFE_ASSET_TICKER 상수 |
| `app/backtest/runners/backtest_runner.py` | 파라미터화된 neutral/risk_off 배분 |
| `app/run_backtest.py` | 261240 fetch, hybrid 산출물 생성, 비교군 동적 계산 |
| `app/run_tune.py` | tune 경로 동일 hybrid 적용 |

---

## 4. 결과 (구현 시점, 날짜 보정 전)

| 지표 | 값 |
|---|---|
| CAGR | 17.65% |
| MDD | 12.27% |
| Sharpe | 1.2047 |
| Neutral Count | 11 |
| Risk-off Count | 2 |
| Verdict | REJECT (MDD > 10) |

**주의**: 이 수치는 Step6J-FIX 이전이며, regime schedule 날짜 불일치 버그로 인해 inflated된 값. 보정 후 수치는 Step6J-FIX 참조.

---

## 5. 커밋 이력

| 커밋 | 내용 |
|---|---|
| `5f5c5138` | Hybrid B+D 정책 구현 (domestic softening + safe asset switching) |
| `4e07a56d` | 산출물 2종 + evidence 확장 필드 추가 |
| `c0f344b9` | 산출물 A9 스펙 보강 + evidence One-line Conclusion |
| `e31de00b` | 비교군 4종 동적 계산 (stale 하드코딩 제거 + VIX baseline 추가) |
| `82b40802` | summary 결론 줄이 B+D 행을 정확히 참조하도록 수정 |
