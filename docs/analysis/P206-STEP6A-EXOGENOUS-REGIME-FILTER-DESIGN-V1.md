# P206-STEP6A-EXOGENOUS-REGIME-FILTER-DESIGN-V1
**프로젝트:** KRX Alertor Modular 투자모델  
**문서 목적:** P205 Dynamic Scanner 파이프라인 이후, 내부 5축 파라미터만으로 해결되지 않는 MDD 문제를 완화하기 위한 **외생 변수 / Regime Filter 플러그인 아키텍처**를 정의한다.  
**문서 상태:** Design Freeze / 구현 전 기준 문서  
**작성 목적:** Step6B 최소 구현, Step6C A/B 검증, 신규 세션 Hand-off 기준

---

## 1. 배경

P205 Step5를 통해 아래가 확인되었다.

1. `dynamic_etf_market` 파이프라인은 기능적으로 완성되었다.
   - Dynamic Scanner
   - Time-aware execution
   - Dynamic allocation path
   - Metric integrity
   - Risk calibration pipeline
   가 모두 구축되었다.

2. `dynamic_etf_market` 는 `fixed_current` 대비 높은 수익률을 낸다.
   - 대표 비교 예시:
     - `fixed_current`: CAGR 약 4~8%, MDD 약 4~5%
     - `dynamic_etf_market`: CAGR 약 29%, MDD 약 17~21%

3. 그러나 현재 dynamic 후보는 **승격 실패(reject)** 상태다.
   - `CAGR > 15` 는 만족
   - `MDD < 10` 는 불만족

4. Step5I까지의 실험으로, 내부 5축 파라미터만으로는
   **dynamic의 고수익을 유지하면서 MDD를 10% 미만으로 안정적으로 억제하기 어렵다**는 것이 사실상 증명되었다.

따라서 다음 단계는 더 이상의 내부 파라미터 미세조정보다,  
**시장 위험 국면을 감지해 dynamic scanner의 공격성을 줄이는 외생 변수 / Regime Filter 계층**을 도입하는 것이다.

---

## 2. Step6A의 핵심 질문

Step6A는 아래 질문에 답하는 설계 단계다.

- Regime Filter는 기존 파이프라인의 어디에 꽂을 것인가?
- 어떤 외생 지표를 V1에서 실제 활성화할 것인가?
- 어떤 정책(hard gate / soft gate)으로 dynamic 전략을 완화할 것인가?
- 기존 `fixed_current`, `expanded_candidates`, `dynamic_etf_market` 와 어떻게 충돌 없이 공존하게 할 것인가?
- 이후 Step6B 구현과 Step6C A/B 검증을 어떤 증거 파일로 설명할 것인가?

---

## 3. 원칙

### 3.1 플러그인 아키텍처 유지
기존 P205 dynamic scanner / time-aware schedule / allocation path를 뜯어고치지 않는다.  
Regime Filter는 **plugin layer** 로 붙인다.

### 3.2 V1 최소 활성화
처음부터 많은 외생 변수를 활성화하지 않는다.

V1은 아래 원칙을 따른다.
- 활성 지표 1~2개만
- 나머지는 slot만 열고 `enabled = false`
- 복잡한 API 연동, 뉴스 감성, 다변량 모델은 보류

### 3.3 Fail-Closed
Regime 계산 실패 시, 조용히 risk-on으로 처리하지 않는다.  
실패를 기록하고, 정책적으로 `neutral` 또는 `risk_off` 쪽으로 보수적으로 처리할 수 있어야 한다.

### 3.4 증거 우선
Regime Filter의 판단은 반드시 파일로 남긴다.
- 어떤 지표를 봤는지
- 어떤 값 때문에 risk_off가 됐는지
- 그 결과 dynamic scanner가 어떻게 완화됐는지

### 3.5 기존 파이프라인 무결성 유지
아래는 깨지면 안 된다.

- `fixed_current`
- `expanded_candidates`
- `dynamic_etf_market`
- `dynamic_equal_weight (bucket bypass)`
- `equal_3way`
- `objective_breakdown`
- `overfit_penalty`
- `used_params_5axes`
- `used_params_match_ssot`
- `used_universe_match`
- `promotion_verdict`
- `study.sqlite3`
- `resume`

---

## 4. Step6A 목표

1. 외생 변수 / Regime Filter의 전체 아키텍처를 정의한다.
2. V1에서 실제 활성화할 지표 1~2개를 고정한다.
3. Hard Gate / Soft Gate 정책 옵션을 구분한다.
4. 이후 Step6B 구현 시 필요한 증거 파일과 UI 최소 노출 규칙을 정의한다.
5. 기존 P205 파이프라인과 충돌하지 않도록 경계를 못 박는다.

---

## 5. 비목표

Step6A에서 아래는 하지 않는다.

- 실제 코드 구현
- 실제 뉴스 API 연동
- 실제 VIX / 금리 / 환율 API 연결
- Objective 변경
- 승격 기준 변경
- UI 전체 개편
- allocation 로직 변경

---

## 6. Regime Filter를 어디에 꽂을 것인가

Regime Filter는 후보군/배분 로직과 충돌하지 않도록 **두 단계 위치**를 고려할 수 있다.

### 위치 A — Scanner 전단 (Universe Gating)
Regime 판정이 `risk_off` 이면
- dynamic scanner 실행 자체를 완화
- selected top-N 수를 줄이거나
- 아예 현금 유지 모드로 전환

### 위치 B — Allocation 전단 (Exposure Gating)
Dynamic scanner는 그대로 selected universe를 생성하되,
allocation 직전에서
- 현금 비중 상향
- max_positions 축소
- buy budget 제한
등을 적용

### 설계 결론
V1은 **위치 A 우선 + 필요 시 위치 B 연결 가능 구조** 로 설계한다.

이유:
- 지금 가장 큰 문제는 “위험한 시장에서도 너무 공격적으로 진입”하는 것
- scanner 앞단에서 risk-off를 걸면 단순하고 설명 가능
- allocation 계층을 직접 건드리는 것보다 P205 무결성을 덜 해친다

---

## 7. 정책 형태

Regime Filter는 두 가지 정책 유형을 가진다.

### 7.1 Hard Gate
위험 국면이면 매수 자체를 차단한다.

예:
- `risk_off` → dynamic selected universe 무시, 현금 유지
- 장점: 강력한 MDD 억제
- 단점: 수익률 희생 가능성 큼

### 7.2 Soft Gate
위험 국면이면 공격성을 줄인다.

예:
- `risk_off` → top_n 축소
- `risk_off` → 현금 비중 증가
- `risk_off` → max_positions 축소
- 장점: 유연함
- 단점: 구현 복잡도 증가

### 설계 결론
V1은 **단순한 Hard Gate 또는 아주 약한 Soft Gate** 중 하나로 시작한다.  
처음부터 둘 다 복잡하게 섞지 않는다.

권장:
- V1 기본정책 = **Hard Gate**
- 후속 Step에서 Soft Gate 확장

---

## 8. V1에서 우선 고려할 외생 지표

### 8.1 후보 1 — KOSPI/대표 ETF 장기 이평선 레짐
예시:
- 대표 시장지표(예: KOSPI 또는 대표 ETF)가
  - 120일 이평 아래
  - 200일 이평 아래
이면 `risk_off`

#### 장점
- 계산 단순
- 재현성 높음
- look-ahead 통제 쉬움
- 설명 가능성 높음

### 8.2 후보 2 — 시장 breadth / 참여도 단순 지표
예시:
- 후보 universe 내 모멘텀 양수 비율 급감
- scanner 후보군 중 일정 비율 이상이 음수 모멘텀
이면 `neutral` 또는 `risk_off`

#### 장점
- dynamic scanner와 자연스럽게 연결
- 외부 API 부담 적음

### 8.3 V1 우선 활성화 결론
V1에서 실제 활성화는 아래 2개만 고려한다.

1. `market_trend_ma_regime`
2. `market_breadth_regime`

### 8.4 V1에서 비활성 슬롯만 유지할 항목
아래는 설계 슬롯만 열고 `enabled = false` 로 둔다.

- `news_sentiment_regime`
- `fear_index_regime`
- `fx_regime`
- `rate_regime`
- `macro_composite_regime`

---

## 9. Feature / Provider Registry 설계

Regime Filter도 P205 Dynamic Scanner와 같은 철학으로 **registry 기반** 이어야 한다.

각 regime provider는 최소 아래 속성을 가진다.

- `key`
- `enabled`
- `source`
- `lookback`
- `lag_days`
- `freshness_ttl`
- `thresholds`
- `missing_policy`
- `regime_map`
- `notes`

예시:
- `market_trend_ma_regime`
- `market_breadth_regime`
- `fear_index_regime` (disabled)
- `news_sentiment_regime` (disabled)

---

## 10. Regime State 정의

V1의 regime 상태는 너무 복잡하게 나누지 않는다.

### 10.1 기본 상태
- `risk_on`
- `neutral`
- `risk_off`

### 10.2 V1 정책 매핑 예시
#### risk_on
- 기존 dynamic scanner 정상 실행

#### neutral
- 정책에 따라 그대로 실행하거나 약한 제한 적용
- V1에서는 `neutral = risk_on과 동일` 로 둘 수도 있음

#### risk_off
- Hard Gate: 신규 매수 차단
- 또는 V1.5 이후 Soft Gate로 확장 가능

---

## 11. SSOT / 실행 파이프라인과의 연결 설계

### 11.1 SSOT 확장 방향
SSOT는 이후 아래를 저장할 수 있어야 한다.

- `regime.mode`
- `regime.providers[]`
- `regime.policy`
- `regime.last_verdict`
- `regime.last_snapshot_id`

단, Step6A에서는 설계만 하고 실제 적용은 Step6B에서 구현한다.

### 11.2 dynamic_etf_market와의 연결
`dynamic_etf_market` 에서만 regime filter가 실질적으로 의미 있다.  
`fixed_current` / `expanded_candidates` 는 기본적으로 영향 받지 않게 두는 것이 V1 원칙이다.

즉:
- `fixed_current` → 기존 그대로
- `expanded_candidates` → 기존 그대로
- `dynamic_etf_market` → regime plugin 적용 대상

---

## 12. 증거 파일 설계

Step6B/6C 이후 아래 산출물을 기대한다.

### 12.1 regime verdict snapshot
- `reports/tuning/regime_verdict_latest.json`

최소 항목:
- `asof`
- `regime_state`
- `active_providers`
- `provider_values`
- `provider_thresholds`
- `policy_applied`
- `regime_valid`
- `regime_error_code`

### 12.2 regime schedule
- `reports/tuning/regime_schedule_latest.json`
- `reports/tuning/regime_schedule_latest.csv`

rebalance date별로
- regime state
- provider values
- gate applied 여부
를 남긴다.

### 12.3 regime selection reason
- `reports/tuning/regime_reason_latest.md`

한국어로
- 왜 risk_off가 됐는지
- 어떤 지표가 트리거였는지
- 결과적으로 dynamic scanner가 어떻게 완화됐는지
설명한다.

---

## 13. UI 최소 노출 원칙

새 페이지를 만들지 않는다.

기존 `백테스트 및 튜닝 시뮬레이션` 화면 안에 아래만 최소로 노출한다.

- `Regime 상태: risk_on / neutral / risk_off`
- `활성 provider 수`
- `정책: hard_gate / soft_gate`
- `최근 verdict 시각`

긴 설명문 금지.

---

## 14. Step6B 구현 계획

Step6B는 아래 범위까지만 구현한다.

1. regime provider registry
2. V1 활성 provider 1~2개 계산
3. regime verdict 생성
4. dynamic_etf_market에 hard gate 또는 단순 soft gate 적용
5. regime verdict / schedule / reason 산출물 생성
6. UI 최소 노출

### Step6B 금지
- 뉴스/VIX 실연동
- objective 수정
- 승격 기준 완화
- allocation path 구조 변경
- fixed_current 흐름 개조

---

## 15. Step6C 검증 계획

Step6C의 비교군은 아래 3개다.

1. `fixed_current`
2. `dynamic_etf_market` (no regime)
3. `dynamic_etf_market + regime V1`

### 비교 지표
- Full CAGR
- Full MDD
- Sharpe
- total_return
- 승격 판정
- regime 적용 횟수 / risk_off 횟수

### 성공 기준
- dynamic + regime가
  - CAGR을 일부 희생하더라도
  - MDD를 유의미하게 낮추고
  - 가능하면 `MDD < 10` 또는 근접
시키면 성공

---

## 16. Step6A 불변조건

이 문서는 아래 불변조건을 확정한다.

1. 외생 변수는 plugin 방식으로 도입한다.
2. V1에서는 활성 provider 1~2개만 쓴다.
3. fixed_current / expanded_candidates 흐름은 건드리지 않는다.
4. 기존 dynamic scanner / time-aware schedule / dynamic_equal_weight는 유지한다.
5. objective / 승격 기준은 유지한다.
6. Fail-Closed 를 유지한다.
7. 새 페이지를 만들지 않는다.

---

## 17. 설계상 주의점

### 17.1 외생 변수 과도 도입 금지
뉴스 / 공포지수 / 환율 / 금리 / breadth를 동시에 넣으면 원인 분리가 불가능해진다.  
V1은 단순 지표부터 시작해야 한다.

### 17.2 Regime와 Allocation을 한 번에 섞지 말 것
먼저 scanner 앞단 hard gate가 먹는지 확인하고,
그 다음 soft gate로 확장한다.

### 17.3 승격 기준 완화 금지
현재 기준:
- `CAGR > 15`
- `MDD < 10`
은 그대로 유지한다.  
Regime Filter는 기준을 낮추는 수단이 아니라, **그 기준을 만족하는 후보를 찾기 위한 방어막**이다.

---

## 18. 성공 기준 (Step6A 관점)

Step6A 설계 문서는 아래를 달성하면 성공이다.

1. Regime Filter의 plugin 구조가 명확하다.
2. V1 활성 provider 1~2개가 정해졌다.
3. Hard Gate / Soft Gate 정책 방향이 구분되었다.
4. 증거 파일 계약이 정의되었다.
5. Step6B / Step6C 구현이 이 문서만으로 가능하다.
6. 기존 P205 파이프라인과 충돌하지 않는다.

---

## 19. 실패 기준

아래면 Step6A 설계 실패다.

- 처음부터 외부 변수 5개 이상 동시 도입
- plugin이 아니라 기존 파이프라인을 갈아엎는 구조
- fixed_current / expanded_candidates까지 함께 깨뜨리는 구조
- 증거 파일 / regime verdict / fail-closed 규칙 부재
- Step6B에서 무엇을 구현할지 불명확
- Step6C에서 어떻게 검증할지 불명확

---

## 20. 최종 결론

Step6A의 본질은 “뉴스/VIX를 넣어보자”가 아니다.  
**P205에서 완성된 dynamic scanner 파이프라인 위에, 시스템 리스크 국면에서 공격성을 줄이는 작은 플러그인 방어막을 설계하는 것**이다.

핵심 한 줄 요약:

> Regime Filter는 기존 dynamic engine을 대체하는 새 엔진이 아니라,  
> **dynamic_etf_market의 과도한 MDD를 제어하기 위해 앞단에 붙는 보수적 방어 플러그인**이다.

---

## 21. 후속 세션 / Hand-off 용 요약

새로운 세션의 GPT는 이 문서를 읽고 즉시 아래를 이해해야 한다.

- P205는 기능적으로 완료되었다.
- dynamic 후보는 수익이 강하지만 MDD가 높아 승격 기각 상태다.
- Step6A는 외생 변수 / Regime Filter 설계 단계다.
- V1은 plugin 방식, 1~2개 provider만 활성화, hard gate 우선이다.
- Step6B는 최소 구현, Step6C는 A/B 검증이다.
