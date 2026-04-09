# P207-STEP7A-RISK-AWARE-ALLOCATION-DESIGN-V1

## 0. 문서 목적

본 문서는 P206 종료 이후, P207을 **거시/하이브리드 타이밍 엔진 추가 실험**이 아니라 **포트폴리오 엔지니어링 챕터**로 정의하고, 기존 `dynamic_equal_weight`를 대체 또는 병렬 비교할 **risk-aware allocation 구조**를 설계하는 문서다. 현재 handoff 문서는 P207의 목표를 "타이밍 미세조정이 아니라 포트폴리오 구성 자체 개선"으로 고정하고 있으며, 기존 `dynamic scanner / hybrid regime`는 유지하고 `allocation`만 바꾸라고 명시하고 있다. 

## 1. 현재 상태 요약

현재 최신 증거 기준 성능은 `CAGR 12.58% / MDD 12.26% / Sharpe 1.1536 / Verdict REJECT`이며, 하이브리드 정책은 `B+D (domestic softening + safe asset)` 상태다. 즉 P206은 엔지니어링은 끝났지만 정책 성능은 목표를 넘지 못했다. 
또한 현재 백테스트 메타에는 `allocation_mode = dynamic_equal_weight`, `universe_mode = dynamic_etf_market`, `exo_regime_applied = true`, `max_positions = 2`, 월간 리밸런스가 기록되어 있으므로, P207은 이 실행 골격을 깨지 않고 배분 방식만 바꾸는 것이 맞다.

## 2. 왜 P207이 필요한가

P206 비교 결과를 보면 `hybrid_B+D`는 `12.58 / 12.26`, `hybrid_cash_only`는 `16.12 / 12.29`, `vix_baseline`은 `25.78 / 12.27`, `no_regime`는 `28.29 / 15.04`다. 즉 방어 정책을 바꿔도 MDD는 12%대에 머물렀고, CAGR만 깎이는 구간이 많았다. 결론은 "언제 피할까"를 더 비트는 것보다 "무엇을 얼마나 들고 있느냐"를 손대는 쪽이 다음 병목이라는 뜻이다.

## 3. P207 목표

P207의 목표는 아래 3개다.

1. `dynamic_equal_weight`를 대체하거나 병렬 비교 가능한 **risk-aware allocation** 도입
2. 기존 `dynamic scanner + hybrid regime + safe asset` 구조는 유지
3. **objective / promotion 기준은 변경하지 않음**

이 목표는 handoff 문서에 이미 명시되어 있다. 즉 이번 단계는 전략 철학 갈아엎기가 아니라, **배분 엔진만 교체하는 외과수술**이다. 

## 4. 설계 원칙

### 4.1 유지할 것

* `dynamic_etf_market` 유니버스 흐름 유지
* `hybrid B+D` 방어 체계 유지
* 월간 리밸런스와 `rebalance_only` 유지
* 현재 SSOT 파라미터 축(`momentum_period 44`, `volatility_period 19`, `entry_threshold 0.04`, `max_positions 2`) 유지
* 승격 기준 `CAGR > 15`, `MDD < 10` 유지

### 4.2 바꿀 것

* 위험자산 sleeve 내부의 종목 간 배분 방식
* equal weight를 risk-aware weight로 대체 또는 비교
* allocation trace를 UI/JSON/evidence에 노출

### 4.3 하지 않을 것

* VIX / MA / Breadth / Hybrid 정책 재튜닝
* ML classifier 진입
* 외부 센서 추가
* 초고빈도 대응
* 브로커 자동주문
* objective 변경 

## 5. 목표 아키텍처

P207의 핵심은 **상위 배분과 하위 배분을 분리**하는 것이다.

### 5.1 상위 레이어

Regime 엔진이 먼저 총 포트폴리오를 나눈다.

* `neutral`: risky / cash / dollar
* `risk_off`: cash / dollar
* safe asset 및 현금 정책은 기존 B+D 그대로 사용 

### 5.2 하위 레이어

`risky sleeve > 0` 인 경우에만, 그 risky sleeve 내부에서 종목별 weight를 결정한다.

* 현재: `dynamic_equal_weight`
* P207 후보: `risk_aware_equal_weight_v1`, `inverse_volatility_v1`, `min_variance_lite_v1`

즉,

* Regime는 "얼마를 위험자산에 둘지"
* Allocation은 "그 위험자산 몫을 누구에게 얼마나 줄지"
  를 담당한다.

이렇게 분리하면 P206 엔진을 건드리지 않고 P207만 독립 검증할 수 있다.

## 6. 후보 배분 모델

### A. risk_aware_equal_weight_v1

가장 먼저 붙일 1순위 모델이다.

개념:

* 기본은 equal weight
* 단, 최근 변동성이 큰 종목은 weight를 자동 감산
* 너무 튀는 값은 cap/floor로 잘라낸다

권장 계산 흐름:

1. 후보 종목 선택
2. 각 종목 최근 N일 realized volatility 계산
3. equal base weight 생성
4. volatility penalty 반영
5. cap/floor 적용
6. 합이 1이 되도록 재정규화

장점:

* 설명이 쉽다
* 현재 equal weight와 가장 연속적이다
* max_positions가 2인 현재 구조에도 무리 없이 붙는다

### B. inverse_volatility_v1

2순위 모델이다.

개념:

* 종목 가중치 `w_i ∝ 1 / vol_i`
* 변동성이 낮을수록 더 큰 비중

장점:

* 업계에서 흔한 구조
* 계산이 단순하다
* 후보 수가 적어도 안정적이다

주의:

* 변동성이 지나치게 낮은 종목에 weight가 몰릴 수 있으므로 cap 필요

### C. min_variance_lite_v1

3순위 후보다.

개념:

* 공분산 기반 최소분산 포트폴리오를 쓰되
* full optimizer 대신 diagonal shrinkage 또는 simplified covariance만 사용
* 수치 불안정 시 자동 fallback

장점:

* 이론상 분산 억제 효과 기대

주의:

* 현재 `max_positions = 2` 구조에서는 과설계가 될 수 있다
* Step7A의 기본안이 아니라 비교 후보로 두는 게 맞다 

## 7. Step7A 권장 채택안

이번 설계 단계의 기본 채택안은 **A → B → C 순서**다.

### 최우선 기본안

`risk_aware_equal_weight_v1`

채택 이유:

* 현재 시스템과의 차이가 가장 작다
* "equal weight에서 위험한 놈만 좀 덜 주자"라는 설명이 된다
* 실패해도 원인 추적이 쉽다
* UI 설명과 evidence 작성이 가장 간단하다

즉 P207의 첫 타석은 화려한 최적화가 아니라, **같이 들되 덜 위험하게 들기**다.

## 8. 비교군 설계

Step7A 비교군은 아래 4개로 고정한다.

### G0. no_regime + dynamic_equal_weight

* 기존 순수 baseline

### G1. hybrid B+D + dynamic_equal_weight

* P206 최신 기준 baseline

### G2. hybrid B+D + risk_aware_equal_weight_v1

* P207 기본안

### G3. hybrid B+D + inverse_volatility_v1

* 대안 1

선택 비교군:

### G4. hybrid B+D + min_variance_lite_v1

* 대안 2
* Step7A 본선이 아니라 보조군

비교 목적은 단순하다.

* Regime 효과와 Allocation 효과를 섞지 말고 분리해서 본다
* "방어 엔진은 그대로인데 배분만 바꾸면 무엇이 달라지는가"를 확인한다

## 9. 파라미터 설계

기존 `strategy_params_latest.json`에 allocation 블록을 추가하는 방향으로 설계한다. 현재 SSOT는 월간 리밸런스, `bucket_portfolio`, `max_positions 2`, `min_cash_pct 0.5`를 사용 중이다. 

권장 구조:

```json
"allocation": {
  "mode": "risk_aware_equal_weight_v1",
  "risky_sleeve_only": true,
  "volatility_lookback": 20,
  "volatility_floor": 0.05,
  "volatility_cap": 0.60,
  "weight_floor": 0.35,
  "weight_cap": 0.65,
  "fallback_mode": "dynamic_equal_weight"
}
```

설계 해석:

* `mode`: 배분 엔진 종류
* `risky_sleeve_only`: safe asset/cash는 기존 regime가 담당
* `volatility_lookback`: 종목 리스크 측정 창
* `volatility_floor/cap`: 이상치 완화
* `weight_floor/cap`: 1개 종목 쏠림 방지
* `fallback_mode`: 계산 실패 시 안전 복귀

중요:

* 기존 `risk_limits`, `position_limits`, `cash_policy` 의미를 **묵살하면 안 된다**
* P207은 새로운 allocation이 들어와도 현재 위험 제한 해석을 깨지 않도록 설계해야 한다
* 해석 충돌이 있으면 "새 규칙"이 아니라 "문서화된 우선순위"로 풀어야 한다

## 10. 실행 순서 설계

### 10.1 런타임 순서

1. dynamic universe snapshot 확정
2. scanner/selector로 후보 종목 확정
3. regime로 risky/cash/dollar 총량 확정
4. risky sleeve 내부에서 allocation mode 적용
5. safe asset/cash sleeve는 기존 방식 유지
6. final weights 생성
7. evidence / backtest_result / UI trace 저장

### 10.2 fallback 순서

* 데이터 부족 → equal weight fallback
* volatility NaN/0 → 해당 종목 floor 처리 또는 fallback
* covariance singular → inverse vol fallback
* 후보 1개뿐 → 100% 단일 배분
* 후보 0개 → 기존 cash/dollar policy 유지

이 fallback 체계는 LIVE에서 fail-closed 철학을 깨지 않으면서도, REPLAY/BACKTEST에서 왜 fallback 되었는지 보여줘야 한다.

## 11. 산출물 설계

### 11.1 backtest_result.json 추가 필드

권장 추가 필드:

* `allocation_mode`
* `allocation_input_count`
* `allocation_fallback_used`
* `allocation_volatility_lookback`
* `allocation_weights_raw`
* `allocation_weights_final`
* `allocation_trace_date`
* `risky_sleeve_weight`
* `safe_sleeve_weight`

현재도 `allocation_mode`, `exo_regime_applied`, `used_universe_snapshot_id` 등은 남고 있으므로, 여기에 "왜 이 weight가 나왔는지"를 붙여야 한다. 

### 11.2 dynamic_evidence_latest.md 추가 필드

권장 추가 노출:

* Allocation Mode
* Selected Risky Names
* Raw Risk Scores / Vols
* Final Risky Weights
* Fallback 여부
* Regime별 risky sleeve 요약

### 11.3 promotion_verdict.json

변경하지 않는다.
다만 설명용 reason에 allocation mode가 어떤 후보였는지는 들어가도 된다. 승격 기준 자체는 유지한다.

## 12. UI 설계

### PC Cockpit

#### A. Strategy Parameters 화면

* Allocation Mode 드롭다운 추가
* Volatility Lookback, Weight Cap/Floor 입력칸 추가
* 기대 결과: 저장 후 현재 allocation mode가 화면에 명시됨

#### B. Full Backtest 화면

* 결과 카드에 `allocation_mode` 표시
* 비교표에 G0/G1/G2/G3 row 추가
* 기대 결과: "같은 regime인데 allocation만 바뀐 비교"가 한눈에 보임

#### C. Evidence 화면

* Allocation Trace 카드 추가
* 기대 결과: 최종 risky sleeve 내부 weight 산식과 fallback 여부가 보임

### OCI Operator

* Step7A에서는 **원칙적으로 변경 없음**
* OCI는 P207 구현 후 결과 소비만 하도록 둔다

## 13. 검증 기준

### 13.1 Step7A 설계 PASS 기준

1. 기존 regime/safe asset 엔진을 건드리지 않는다
2. allocation mode만 바꿔 비교 가능하다
3. UI에서 현재 allocation mode를 확인할 수 있다
4. JSON 산출물에서 allocation trace를 확인할 수 있다
5. fallback 이유가 로그/산출물에 남는다
6. 비교군 G0~G3 결과를 같은 포맷으로 뽑을 수 있다

### 13.2 성능 PASS 기준

변경 없음.

* `CAGR > 15`
* `MDD < 10`
* 기존 promotion verdict 체계 유지

## 14. 예상 리스크와 대응

### 리스크 1. 후보 수가 적어서 최적화 이점이 약함

현재 `max_positions = 2`이므로 min-variance는 과한 칼질이 될 수 있다. 그래서 Step7A 기본안은 risk-aware equal weight다. 

### 리스크 2. low-vol 종목 쏠림

inverse vol은 특정 종목에 과하게 몰릴 수 있다. weight cap이 필요하다.

### 리스크 3. 규칙 의미 충돌

현재 `risk_limits.max_position_pct`, `position_limits.max_positions`, regime의 safe sleeve가 동시에 존재한다. 구현 시 의미를 몰래 바꾸지 말고 우선순위를 명시해야 한다. 

### 리스크 4. 성능은 안 좋아지고 설명만 복잡해짐

그래서 Step7A는 가장 설명 쉬운 구조부터 간다. 괜히 수학만 번지르르하면 또 P206 시즌2가 된다.

## 15. 최종 판단

P207의 첫 설계는 아래처럼 고정하는 것이 맞다.

* 챕터 성격: **포트폴리오 엔지니어링**
* 변경 범위: **allocation only**
* 유지 범위: **dynamic scanner + hybrid B+D + safe asset**
* 기본 후보: **risk_aware_equal_weight_v1**
* 비교군: **G0/G1/G2/G3**
* 산출물: **UI + JSON + evidence에서 allocation trace 확인 가능**
* 승격 기준: **변경 금지**

이 설계가 Step7A의 기준본입니다.
