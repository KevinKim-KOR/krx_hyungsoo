# P205-STEP5A-DYNAMIC-SCANNER-DESIGN-V1
**프로젝트:** KRX Alertor Modular 투자모델  
**문서 목적:** Dynamic Scanner 도입의 설계 기준과 구현 순서를 명확히 정의하고, 이후 Step5B~Step5I가 같은 철학과 경계를 유지하도록 하는 기준 문서  
**문서 상태:** As-designed / 기록용  
**작성 목적:** 새 세션 Hand-off, 구현 기준, 회귀 검증 기준

---

## 1. 배경

기존 `fixed_current` / `expanded_candidates` 방식은 고정 유니버스 중심이다.  
이 방식은 다음 한계를 가진다.

1. 시장 국면이 바뀌어도 후보군이 정적이라 주도주 추적력이 떨어진다.
2. 사람이 고른 유니버스에 성능이 과도하게 의존한다.
3. 장기 하락장/회전장에서는 “지금 시장에서 강한 종목”을 기계가 즉시 반영하지 못한다.

따라서 Step5에서는 **시장 전체 후보군에서 기계가 동적으로 후보를 추려내는 Dynamic Scanner 파이프라인**을 도입한다.

---

## 2. Step5A의 핵심 질문

Step5A는 “코드를 어떻게 짤까”보다 먼저 아래 질문에 답하는 설계 단계다.

- 어떤 후보군을 스캔할 것인가?
- 어떤 feature를 계산할 것인가?
- 어떤 규칙으로 top-N을 고를 것인가?
- churn(후보군 급변)을 어떻게 통제할 것인가?
- 이후 Tune / Full Backtest / Promotion Verdict와 어떻게 충돌 없이 연결할 것인가?

---

## 3. 원칙

### 3.1 플러그인 방식
기존 P204 / P205 이전 파이프라인을 갈아엎지 않는다.  
Dynamic Scanner는 **후보군 선택 플러그인**으로 설계한다.

### 3.2 V1 최소기능 우선
처음부터 뉴스/공포지수/매크로/복합 모델을 넣지 않는다.  
V1은 다음만 한다.

- 후보군 수집
- feature 계산
- selector/ranking
- snapshot identity
- churn 관측
- 이후 단계에서 time-aware execution 연결

### 3.3 Fail-Closed
후보군/feature/snapshot 계산이 실패하면 조용히 fallback하지 않는다.  
실패 원인을 산출물에 기록한다.

### 3.4 증거 우선
모든 주요 결과는 파일로 남긴다.

- `universe_snapshot_latest.json`
- `universe_feature_matrix_latest.csv`
- `dynamic_scanner_smoke_result.json`

### 3.5 기존 파이프라인 무결성 유지
아래는 Step5A 설계상 절대 깨지면 안 된다.

- `fixed_current`
- `expanded_candidates`
- P204 objective / segment evaluation / promotion verdict
- 기존 UI 페이지 구조
- 기존 백테스트/튜닝 실행 버튼 계약

---

## 4. 목표

### 4.1 Step5A 설계 목표
1. Dynamic Scanner를 구성하는 레이어를 분리 정의한다.
2. V1에서 구현할 것과 하지 않을 것을 명확히 구분한다.
3. snapshot identity와 churn control을 설계 수준에서 못 박는다.
4. 이후 Step5B~Step5I 구현이 흔들리지 않도록 **불변조건(Invariants)** 을 문서화한다.

### 4.2 비목표
Step5A에서 아래는 하지 않는다.

- Tune/Backtest 직접 연결
- 외생 변수 도입
- 승격 기준 완화
- allocation 변경
- objective 변경

---

## 5. 전체 구조

Dynamic Scanner는 V1에서 아래 3계층으로 나눈다.

### Layer 1. Candidate Pool
시장 전체 후보 중 “스캔 가능한 우주”를 만든다.

### Layer 2. Feature Provider
후보별 점수 계산에 필요한 feature를 생성한다.

### Layer 3. Selector / Ranking
feature를 바탕으로 최종 top-N을 선택한다.

---

## 6. Layer 1 — Candidate Pool 설계

### 6.1 기본 후보군
V1 기본 후보군은 **KRX ETF 시장 전체**를 기본으로 한다.

### 6.2 Hard Exclusion
V1에서는 아래를 제외한다.

- 레버리지 ETF
- 인버스 ETF
- 합성 구조 ETF(정책상 제외가 필요한 경우)
- 데이터 결측이 심한 종목
- 상장 이력이 너무 짧아 lookback 계산이 불가능한 종목

### 6.3 Candidate Pool 메타
후보군 산출 시 아래 메타를 남긴다.

- `candidate_pool_source`
- `total_candidates_before_exclusion`
- `excluded_count`
- `eligible_count`

### 6.4 Max Candidate Guard
V1에서는 과도한 연산 폭발을 막기 위해 `max_candidates` cap을 둔다.  
기본 정책은 **200개 cap** 이다.

---

## 7. Layer 2 — Feature Provider 설계

### 7.1 V1 활성 feature
V1에서 실제 점수 계산에 쓰는 feature는 6개다.

1. `price_momentum_3m`
2. `price_momentum_6m`
3. `volatility_20d`
4. `liquidity_20d`
5. `turnover_rate`
6. `drawdown_from_high`

### 7.2 Feature Registry 구조
Feature는 registry 기반으로 관리한다.

각 feature는 아래 속성을 가진다.

- `key`
- `enabled`
- `weight`
- `missing_policy`
- `normalization_rule`

### 7.3 Missing Policy
V1 missing policy는 아래 3개만 허용한다.

- `exclude`
- `fill_zero`
- `skip_scoring`

### 7.4 정규화
점수 계산은 raw feature가 아니라 **normalized feature** 기반으로 한다.

### 7.5 Feature Matrix 산출물
아래 파일을 산출한다.

- `reports/tuning/universe_feature_matrix_latest.csv`

최소 컬럼:
- ticker
- name
- 6 raw feature
- 6 normalized feature
- meta 컬럼

---

## 8. Layer 3 — Selector / Ranking 설계

### 8.1 기본 선택 공식
V1 기본 ranking 공식은 `weighted_sum` 이다.

```text
composite_score = Σ(weight × normalized_feature)
```

### 8.2 선택 규칙
- `top_n = 15`
- tie-breaker:
  1. `liquidity_20d` 높은 순
  2. `ticker` 오름차순

### 8.3 scoring eligibility
후보는 두 그룹으로 나뉜다.

- `scoring_eligible = true`
- `scoring_eligible = false`

다음은 `false` 처리한다.

- required feature 누락
- exclusion 대상
- normalization 실패
- composite score 계산 실패

### 8.4 fallback_rule
V1에서는 최소 후보 확보 실패 시 아래 순서로 완화한다.

1. `min_avg_volume_20d` 완화
2. `min_listing_days` 완화

단, **최소 후보 수 5개**도 못 채우면 fail-closed 기록한다.

### 8.5 selection reason 산출
선택/제외 이유를 사람이 이해할 수 있게 남긴다.

예시:
- `selected_top_n`
- `excluded_missing_feature`
- `excluded_hard_exclusion`
- `excluded_low_score`
- `selected_after_fallback`

---

## 9. Snapshot Identity 설계

Dynamic Scanner는 결과가 조금만 달라도 완전히 다른 snapshot으로 취급해야 한다.

### 9.1 Snapshot 필수 항목
- `snapshot_id`
- `snapshot_sha256`
- `asof`
- `selected_tickers`
- `selected_tickers_with_scores`

### 9.2 Deterministic Identity
같은 입력이면 같은 snapshot hash가 나와야 한다.

### 9.3 Snapshot 산출물
- `reports/tuning/universe_snapshot_latest.json`

---

## 10. Churn Control 설계

Dynamic Scanner는 주기적으로 후보가 바뀐다.  
그러나 지나친 churn은 운영 리스크다.

### 10.1 V1 불변조건
아래는 Step5A 설계 단계에서 고정한다.

1. `refresh_frequency = weekly`
2. `min_overlap_ratio = 0.60`
3. `max_new_entries_per_refresh = 5`

### 10.2 기록 항목
- 이전 snapshot 대비 overlap ratio
- 새로 진입한 종목 수
- churn check status

### 10.3 목적
너무 자주/너무 많이 갈아타는 dynamic scanner를 방지한다.

---

## 11. Step5A 불변조건 (Invariants)

이 문서는 아래 불변조건을 후속 구현 단계에서 반드시 지키게 한다.

### 11.1 정책 불변조건
- `exclude_inverse = true`
- `exclude_leveraged = true`
- `exclude_synthetic = true` (정책상 적용 시)
- `top_n = 15`
- `refresh_frequency = weekly`
- `min_overlap_ratio = 0.60`
- `max_new_entries_per_refresh = 5`

### 11.2 구조 불변조건
- snapshot identity는 deterministic 해야 한다
- selector는 raw feature가 아닌 normalized feature를 사용해야 한다
- tuning/backtest loop 안에서 무거운 scanner 연산 반복 호출 금지
- 이후 time-aware execution 시 schedule pre-calculation 구조로 가야 한다

### 11.3 무결성 불변조건
- 기존 `fixed_current`, `expanded_candidates` 를 깨뜨리면 안 된다
- 기존 P204 objective / segment evaluation / promotion verdict 흐름을 깨뜨리면 안 된다

---

## 12. 산출물 계약 (Contracts)

Step5A 설계 기준상 최종적으로 기대하는 산출물은 아래다.

### 12.1 기본 산출물
- `reports/tuning/universe_snapshot_latest.json`
- `reports/tuning/universe_feature_matrix_latest.csv`
- `reports/tuning/dynamic_scanner_smoke_result.json`

### 12.2 이후 Step5C 이후 확장 산출물
- `reports/tuning/universe_selection_reason_latest.md`
- `reports/tuning/dynamic_universe_schedule_latest.json`
- `reports/tuning/dynamic_universe_schedule_latest.csv`

---

## 13. UI 설계 방향 (Step5A 수준)

Step5A에서는 UI를 크게 바꾸지 않는다.  
V1 UI 원칙은 아래와 같다.

1. 새 페이지 추가 금지
2. 기존 `백테스트 및 튜닝 시뮬레이션` 화면 안에 최소 노출
3. Dynamic Scanner는 “설명문”이 아니라 “상태/산출물/실행 버튼” 중심
4. 긴 운영 설명 대신 snapshot / selected_count / churn status 같은 핵심값만 노출

즉, UI도 플러그인처럼 붙인다.

---

## 14. 이후 단계별 구현 계획 (Step5A 관점)

### Step5B
- candidate pool
- feature provider
- snapshot identity
- smoke result

### Step5C
- selector / ranking
- selected universe
- selection reason

### Step5D
- scanner → SSOT wiring
- UI 최소 노출

### Step5E
- time-aware execution
- rebalance schedule
- pre-calculation / cache

### Step5F
- allocation 충돌 해결
- dynamic allocation path

### Step5G/H
- metric / UI integrity 복구

### Step5I
- dynamic risk calibration

---

## 15. 설계상 주의점

### 15.1 처음부터 외생 변수 넣지 말 것
뉴스 / VIX / 환율 / 금리 / breadth는 Step5A 설계에 **슬롯만 열어두고 비활성**으로 둔다.

### 15.2 Frozen Snapshot 오용 금지
현재 시점 snapshot을 과거 전체 기간에 덮어씌우는 방식은 금지한다.  
이건 이후 Step5E에서 반드시 time-aware execution으로 풀어야 한다.

### 15.3 Bucket Portfolio 충돌 가능성
Dynamic selected universe와 기존 `bucket_portfolio` 의 고정 `buckets[].universe` 가 충돌할 수 있다.  
이건 설계상 리스크로 명시해 두고, Step5F에서 해결 대상으로 다룬다.

---

## 16. 성공 기준 (Step5A 관점)

Step5A 설계 문서는 아래를 달성하면 성공이다.

1. Dynamic Scanner의 3계층 구조가 명확하다.
2. 불변조건이 문서로 못 박혀 있다.
3. 산출물 계약이 명확하다.
4. 기존 파이프라인 무결성 유지 범위가 명확하다.
5. Step5B~Step5I가 이 문서만으로 구현될 수 있다.

---

## 17. 실패 기준

아래면 Step5A 설계 실패다.

- scanner가 기존 파이프라인을 싹 갈아엎는 구조
- V1인데 외생 변수까지 한꺼번에 밀어넣는 구조
- snapshot identity / churn control / 산출물 계약이 없음
- 이후 time-aware execution / allocation 충돌 가능성을 문서에서 전혀 예상하지 못함
- fixed_current / expanded_candidates / P204 검증체계를 깨뜨릴 위험을 통제하지 못함

---

## 18. 최종 결론

Step5A의 본질은 “좋아 보이는 종목을 찾는 기능 추가”가 아니다.  
**기존 정적 유니버스 기반 투자모델 위에, 동적으로 후보를 고르고도 운영 가능하고 검증 가능하며 회귀 가능한 구조를 설계하는 것**이다.

이 문서의 핵심은 아래 한 줄이다.

> Dynamic Scanner는 독립 엔진이 아니라, 기존 P204/P205 파이프라인 위에 붙는 **검증 가능한 플러그인형 유니버스 선택 레이어**다.

---

## 19. 후속 세션 / Hand-off 용 요약

새로운 세션에서 이 문서를 읽은 GPT는 다음을 즉시 이해해야 한다.

- Step5A는 설계 단계다.
- 핵심은 candidate pool / feature provider / selector / snapshot / churn control 이다.
- V1은 최소 기능만 도입한다.
- 외생 변수는 아직 금지다.
- 이후 Step5B~Step5I는 이 문서의 불변조건을 어기지 않는 선에서 구현된다.
