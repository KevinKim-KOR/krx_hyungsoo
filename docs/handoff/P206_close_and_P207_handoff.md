# P206 종료 결론 + P207 Hand-off 문서
> asof: 2026-04-09
> 상태: P206 종료 / P207 진입 준비 완료

---

## 0. 이 문서의 목적
이 문서는 새로운 세션의 GPT가  
1) P205~P206까지의 핵심 맥락을 빠르게 이어받고,  
2) 왜 P206을 종료하는지 이해하고,  
3) P207에서 무엇을 해야 하는지 즉시 착수할 수 있게 하기 위한 hand-off 문서다.

---

## 1. 프로젝트 전체 마스터 플랜에서 현재 위치

### P204 — 튜닝/백테스트/검증 엔진 구축
목표:
- Tune / Full Backtest / Promotion Verdict 엔진 확립
- segment evaluation, objective, overfit penalty, 검산 파일 체계 확립

결론:
- 완료
- 현재 프로젝트의 검증 엔진과 판정 체계의 기반이 됨

### P205 — Dynamic Scanner / Dynamic Universe 구축
목표:
- 정적 유니버스 한계를 넘기 위해 동적 후보군 선택 구조 도입
- scanner / selector / snapshot / churn control / time-aware execution / dynamic allocation path 구축

결론:
- 완료
- `dynamic_etf_market` 파이프라인이 실제로 굴러가는 상태까지 도달
- 성능 지표/UI/산출물 무결성도 복구 완료

### P206 — 거시/하이브리드 방어 엔진 실험
목표:
- MDD < 10% 달성을 위해 거시 방어막 및 hybrid regime 도입
- VIX, domestic shock, safe asset switching 등을 활용한 리스크 제어

결론:
- 엔지니어링은 완료
- 정책 성능은 실패
- 따라서 P206 챕터 종료

---

## 2. P206에서 실제로 해본 것

### 2.1 VIX 기반 Fear Regime
- 미국 VIX(`^VIX`)를 글로벌 공포 센서로 사용
- 정렬 규칙:
  - 미국 T일 종가 → 한국 T+1 개장 리밸런스 입력
- TTL / staleness / fail-closed / 산출물 / UI 노출까지 구현

### 2.2 국내 충격 센서
- `069500` 기반 `domestic_shock_regime` 도입
- 장전/장중 체크포인트형 저빈도 대응 구조 설계 및 구현
- `preopen_return / intraday_return` 분리
- checkpoint 표시, evidence 문구 정합성까지 완료

### 2.3 Hybrid Regime
- `global_fear_regime + domestic_shock_regime` 결합
- aggregate truth table 설계/구현
- 장중 대응은 하루 4~6회 체크포인트형으로 제한
- 직장인형 운영 모델 유지

### 2.4 Safe Asset Switching
- cash-only 방어의 cash drag를 줄이기 위해
- `261240 (달러 ETF)` 를 안전자산으로 편입
- B+D 정책까지 구현
  - domestic 단독 risk_off → neutral 완화
  - neutral / risk_off 에서 달러 ETF 배분

### 2.5 운영 증거 체계
- `dynamic_evidence_latest.md` 생성
- 다음부터 캡처 없이도 정책 상태 판독 가능하도록 운영 체계 정비 완료

---

## 3. 최신 P206 SSOT (최우선 근거)
최신 판단은 반드시 아래 최신 evidence 파일 기준으로 한다.

### 최신 상태
- `CAGR = 12.58%`
- `MDD = 12.26%`
- `Sharpe = 1.1536`
- `Total Trades = 53`
- `Global State = neutral`
- `Domestic State = risk_off`
- `Aggregate = neutral`
- `Policy Variant = B+D (domestic softening + safe asset)`
- `Domestic Handling = neutral_only (no domestic hard gate)`
- `Safe Asset Mode = dollar_etf neutral/risk_off`
- `Neutral Alloc = risky 35% / cash 45% / dollar 20%`
- `Risk-off Alloc = cash 50% / dollar 50%`
- `Verdict = REJECT`

핵심:
- `CAGR > 15` 실패
- `MDD < 10` 실패
- 즉 둘 다 미달

---

## 4. P206 종료 결론

### 4.1 무엇이 성공했는가
1. Dynamic Engine / Scanner / Allocation Path / Evidence 체계 완성
2. VIX 기반 global fear regime 배선 완성
3. domestic shock regime 배선 완성
4. hybrid truth table / checkpoint model / safe asset switching 구현 완료
5. Tune / Full / Verdict / Evidence 정합성 확보

즉, 엔지니어링과 운영 구조는 충분히 완성되었다.

### 4.2 무엇이 실패했는가
정책 성능이 끝내 목표를 넘지 못했다.

핵심 실패:
- MDD를 10% 미만으로 낮추지 못함
- 최근에는 CAGR 15%마저 유지 못하는 상태까지 하락
- 결국 P206의 여러 미세조정은 새로운 철학을 열지 못하고 trade-off만 바꿨다

### 4.3 왜 종료하는가
P206은 충분히 실험했다.
- MA
- Breadth
- VIX
- Domestic shock
- Hybrid
- Cash-only
- Safe asset switching
- Sensitivity refinement

여기서 더 미세하게 threshold / 비중 / rule을 비트는 것은 수익-낙폭 균형을 근본적으로 바꾸기보다, trade-off를 옮겨 적는 수준에 머물 가능성이 높다.

따라서 P206은  
거시/하이브리드 타이밍 엔진 실험 챕터로서 종료한다.

---

## 5. P206의 교훈 (다음 챕터를 위해 가장 중요)

### 교훈 1
“언제 피할까”는 꽤 잘 만들 수 있었다.

### 교훈 2
하지만 “언제 피할까”만으로는 MDD 10% 벽을 못 깼다.

### 교훈 3
남은 병목은 타이밍이 아니라 포트폴리오 구성 자체다.

즉 다음 질문은
- “언제 방어할까?”가 아니라
- “애초에 어떤 종목을 얼마나 들고 있어야 덜 아플까?” 다.

---

## 6. P207의 목표

P207은 포트폴리오 엔지니어링 챕터다.

핵심 목표:
- 기존 `dynamic_equal_weight` 를 재검토
- 동일비중(N빵) 대신 위험 인식형 비중 배분 도입
- MDD를 타이밍이 아니라 구성 비중에서 줄이기

즉 P207은
- 새로운 거시 센서 추가 챕터가 아니라
- 리스크 인식형 배분 구조 설계 챕터다.

---

## 7. P207에서 해야 할 일

### 7.1 가장 우선할 트랙
Track A: 포트폴리오 엔지니어링 (권장)

우선순위:
1. Risk-aware equal weight
   - 변동성이 큰 종목은 자동으로 비중 축소
   - 너무 복잡한 최적화 이전의 가벼운 1단계

2. Inverse-volatility weighting
   - 최근 20일 등 변동성 역수 기반 비중

3. Light Risk Parity / Minimum Variance Lite
   - 복잡한 공분산 최적화는 뒤로
   - 먼저 단순하고 설명 가능한 구조부터

### 7.2 왜 이게 맞는가
현재까지의 증거는
- 거시 지표만으로 개별 포지션의 폭락을 막는 데 한계가 있다는 쪽을 가리킨다
- 결국 동일비중으로 위험한 놈까지 똑같이 들고 있는 것이 MDD를 끌어올리는 핵심 원인일 수 있다

즉 P207은
- “비가 올 때 우산 쓸까?”가 아니라
- “애초에 번개 잘 맞는 금속 막대를 왜 같은 비중으로 들고 있나?” 를 묻는 단계다

---

## 8. P207에서 당장 하지 말아야 할 것

1. VIX / MA / Breadth / Hybrid 방어 엔진을 또 새로 미세조정하는 일
2. ML classifier 바로 진입
3. 새 외부 센서 여러 개 동시 추가
4. 실시간 초고빈도 대응
5. 브로커 자동주문
6. objective / 승격 기준 변경

즉 P207 초반은 반드시
작고 설명 가능한 배분 구조 변화부터 가야 한다.

---

## 9. P207 첫 설계 과제

### 권장 첫 스텝
`P207-STEP7A-RISK-AWARE-ALLOCATION-DESIGN-V1`

설계 목표:
- 기존 `dynamic_equal_weight` 를 대체하거나 병렬 비교 가능한
  - inverse-volatility weighting
  - capped risk-weighted allocation
  - minimum-variance-lite
  후보를 비교
- 현재 dynamic scanner와 충돌 없이 붙는 구조 설계
- 비교군:
  - no regime + equal weight
  - hybrid B+D + equal weight
  - hybrid B+D + risk-aware allocation

즉 타이밍 엔진은 그대로 두고,
배분 엔진만 바꾸는 설계부터 시작한다.

---

## 10. P207 새 세션에서 GPT가 이해해야 할 것

새 세션의 GPT는 아래를 즉시 이해해야 한다.

1. P204 완료 — 튜닝/백테스트/판정 엔진 완성
2. P205 완료 — dynamic scanner / dynamic universe 완성
3. P206 완료 — 거시/하이브리드 방어 엔지니어링 완성
4. 하지만 P206 정책 성능 실패 — 최신 SSOT 기준 `REJECT`
5. 다음 단계는 타이밍 미세조정이 아니라 포트폴리오 엔지니어링
6. 첫 설계 과제는 `P207-STEP7A-RISK-AWARE-ALLOCATION-DESIGN-V1`

---

## 11. 새 세션 첫 오더
새 GPT는 이 문서를 읽고 아래 오더를 바로 수행하라.

**[다음 오더]**  
`P207-STEP7A-RISK-AWARE-ALLOCATION-DESIGN-V1` 설계 문서를 작성하라.

설계는 아래 원칙을 따른다.
- 기존 dynamic scanner / hybrid regime는 유지
- equal weight 경로를 risk-aware allocation 후보로 대체 또는 병렬 비교
- 설명 가능하고 단순한 구조 우선
- objective / 승격 기준 변경 금지
- UI/JSON/검산파일 증거 중심
- 비교군 명확화

---

## 12. 첨부 권장 파일
새 세션에 가능하면 아래를 함께 첨부한다.
- `dynamic_evidence_latest.md`
- `strategy_params_latest.json`
- 최신 `backtest_result.json`
- 최신 `promotion_verdict.json`
- `hybrid_policy_summary.md`
- `hybrid_policy_compare.csv`

이 문서 하나만으로도 시작은 가능하지만, 위 파일들이 있으면 더 빠르게 이어갈 수 있다.
