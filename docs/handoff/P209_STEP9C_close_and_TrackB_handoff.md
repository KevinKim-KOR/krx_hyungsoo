# P209-STEP9C Track A Contextual Guard 종료 + Track B Hand-off 문서
> asof: 2026-04-12
> 상태: P209-STEP9C **완료** / Track B (ML) 진입 준비
> 직전 문서: [P209_STEP9B_close_and_STEP9C_handoff.md](P209_STEP9B_close_and_STEP9C_handoff.md)

---

## 0. 이 문서의 목적

P209-STEP9C Track A Contextual Guard 챕터를 정식으로 종료하고, 규칙 기반 가드의 한계 지점을 명확히 기록한 뒤 다음 대안인 **Track B (ML based Guard)** 로 넘기는 hand-off 문서다.

---

## 1. P209-STEP9C 종료 결론 (Track A Rule-based 한계 확인)

### 1.1 실험 개요
- **대상**: 문맥형 가드 (Pre-entry, Early-stop, Combined)
- **Baseline**: 
  - A (운영): `g2_pos2_raew`
  - B (연구): `g4_pos3_raew`
- **핵심 정책**: 
  - 필수 파라미터 누락 시 즉시 예외 (Fail-loud)
  - Early-stop 시 즉시 현금화 및 다음 리밸런싱까지 관망 (Wait-and-see)

### 1.2 최종 실험 결과 (MDD 오름차순)

| Rank | Variant | Baseline | Guard Mode | CAGR | MDD | Pre-Entry Hits | Early-Stop Hits | Verdict |
|---:|---|---|---|---:|---:|---:|---:|---|
| 1 | `B1_pos3_raew_pre_entry` | g4_pos3_raew | pre_entry | **16.67%** | **11.03%** | 7 | 0 | **REJECT** |
| 2 | `B0_pos3_raew_no_guard` | g4_pos3_raew | none | 15.95% | 11.03% | 0 | 0 | REJECT |
| 3 | `A1_pos2_raew_pre_entry` | g2_pos2_raew | pre_entry | 13.67% | 12.74% | 4 | 0 | REJECT |
| 4 | `A0_pos2_raew_no_guard` | g2_pos2_raew | none | 12.40% | 12.74% | 0 | 0 | REJECT |
| 5 | `B3_pos3_raew_combined` | g4_pos3_raew | combined | 9.96% | 15.63% | 7 | 9 | REJECT |
| 6 | `B2_pos3_raew_early_stop` | g4_pos3_raew | early_stop | 9.01% | 15.63% | 0 | 8 | REJECT |

### 1.3 분석 진단 (Q1~Q5)

**Q1. Pre-entry Guard 가 MDD 개선에 성공했는가?**
- **결과**: MDD 변화 없음 (A: 12.74% 유지, B: 11.03% 유지). 다만 CAGR은 소폭 개선(A: +1.27%p, B: +0.72%p).
- **진단**: 위험 국면 진입 전 "최악의 종목" 몇 개를 걸러내는 데는 성공했으나, 전체 포트폴리오 MDD를 10% 아래로 끌어내리는 결정적 요인은 아니었음.

**Q2. Early-Stop 단독 효과는 어떠한가?**
- **결과**: MDD/CAGR 모두 대폭 악화 (MDD A: +4.5%, B: +4.6% 악화).
- **진단**: 단순 가격 하락(Entry 대비) 시점의 손절 및 현금 대기는 "V자 반등" 구간에서 소외되는 결과를 초래. 규칙 기반의 경직된 Early-stop은 독배가 됨.

**Q3. Combined 시 과잉 방어 여부?**
- **결과**: Early-stop 단독보다는 낫지만 No-guard 대비 수익성이 심각하게 훼손됨.
- **진단**: 공격적 방어가 수익 기회를 과도하게 잠식함.

**Q4. A/B Baseline 흡수력 비교**
- **결과**: 연구 Baseline(B)이 Pre-entry 가드 하에서 CAGR 16.67%를 기록하며 가장 높은 탄력성을 보였으나, MDD 방어 실패는 공통적.

**Q5. 최종 채택 결론**
- **선언**: **Track A (Rule-based) 채택 실패**.
- **근거**: CAGR > 15 & MDD < 10 동시 충족 실험군 전무.
- **차선**: `B1_pos3_raew_pre_entry` 가 가장 우수하나, MDD 목표 미달로 정식 채택 불가.

---

## 2. P209-STEP9C 코드 품질 성과 (Rule 6/7)

본 단계에서는 기능 구현보다 "구조적 무결성" 확보에 중점을 두었음.

- **Fail-loud 구체화**: 
  - `backtest_runner.py` 내 모든 가드 파라미터 접근을 `KeyError` 발생 경로(subscript)로 통일.
  - 가드 연산 예외 발생 시 `pass` 대신 `RuntimeError` 전파.
- **Zero-residue Cleanup**:
  - `evidence_writer.py` (Legacy 섹션 포함) 및 `contextual_guard_panel.py` 내의 모든 `.get()` 호출에 대해 `OPTIONAL` 또는 `WHITELIST (display)` 분류 주석 완비.
  - UI 렌더링 시의 `except Exception: pass` (Silent catch) 완전 제거.
- **Static Check 완결**: 
  - `black`, `flake8`, `py_compile` 전수 통과 상태에서 종료.

---

## 3. 다음 단계 진입 가이드: Track B (ML based Guard)

규칙 기반 가드(Track A)의 한계를 확인했으므로, 이제 **예측 기반(Probabilistic prediction)** 접근으로 선회한다.

### 3.1 Track B 핵심 가설
- "단순 가격 하락"이 아니라 "추가 급락 가능성(Crash likelihood)"을 모델이 예측하여 가드를 트리거한다면, Rule-based의 경직된 대응을 극복할 수 있을 것이다.

### 3.2 준비 사항 (Next Tasks)
1. **Target Labeling**: MDD 기여도가 높았던 시점의 T+N일 수익률을 기반으로 "Crash" 라벨 정의.
2. **Feature Set 확장**: 
   - Step 9C에서 사용한 Volatility Spike, Recent Drawdown 등을 Feature화.
   - Market Regime (P206), Universe Feature Matrix (Step 9A) 연동.
3. **Model Selection**: LightGBM 또는 가벼운 MLP Classifier 후보군 검토.
4. **Integration**: `BacktestRunner`에 `ml_guard_predictor` 훅 추가.

### 3.3 주의 사항
- **Overfit 경계**: Universe가 작으므로 강력한 Regularization 필요.
- **Fail-loud 유지**: 모델 Load 실패나 Inference 에러 시 조용히 넘기지 말고 Fail-Open/Close 정책을 예러로 명시할 것.

---

## 4. 새 세션 체크리스트

1. `reports/tuning/contextual_guard_compare.md` 의 Q1~Q5 결론 숙지.
2. `app/backtest/runners/backtest_runner.py` 의 가드 구현부(310~360행) 참고.
3. **정적 게이트 무결성 유지**: 새 코드를 짤 때도 `black`, `flake8` 통과 필수.
4. `evidence_writer.py` 에 `WHITELIST (display)` 주석 패턴 유지.

---
**P209-STEP9C 종료. Track B (ML) 로 전환을 제안합니다.**
