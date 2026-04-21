# P211 STEP11A DESIGN V1

작성 목적: Phase 2 Step11A를 실제로 진행 가능한 수준의 축소 설계 문서로 고정한다.  
성격: analysis-only / 설계자 초안  
기준: Main Run / Compare Run 혼용 금지  
현재 단계: Step11A 착수 전 설계 고정

---

## 0. 이번 문서의 한 줄 정의

Step11A는 **friend source에서 코드로 추출 가능한 core primitive를 식별하고, 현재 프로젝트에 지금 가져올 수 있는지 여부만 판정하는 portability 설계 스텝**이다.

이 문서는 성능 승격 문서가 아니다.  
이 문서는 MDD 10% 달성 증명 문서가 아니다.  
이 문서는 compare rerun 지시문이 아니다.

---

## 1. Step11A의 목표

이번 Step11A의 목표는 아래 2개만 허용한다.

1. friend source에서 **code-derived core primitive** 를 식별한다.
2. 각 primitive를 현재 프로젝트에 붙일 때,
   - 바로 이식 가능한지
   - overlay가 필요한지
   - 지금 단계에서 부적합한지
   를 3단계로 판정한다.

즉 Step11A의 중심 질문은 아래와 같다.

- 이 규칙이 실제로 friend source 코드에서 읽히는가?
- 이것이 core primitive인가, 아니면 해석이 섞인 overlay hypothesis인가?
- 현재 프로젝트 구조와 직장인형 운영 원칙 아래에서 지금 이식 가능한가?

---

## 2. 이번 Step11A에서 하지 않는 것

아래는 이번 Step11A의 범위 밖이다.

1. MDD 13%대 벽 직접 공격 메커니즘 확정
2. MDD 10% 달성 가능성 판정
3. protective ledger 상세 설계
4. gate auditability 풀스펙 설계
5. compare run 제안
6. Tune rerun / Full Backtest rerun / Analysis-only regenerate 제안
7. 구현 지시문 작성
8. Step11B 자동 예약
9. 인간 뉴스 해석 규칙의 코드화
10. friend source 전체 운영 흐름 이식

---

## 3. 이번 Step11A의 판정값

각 후보는 아래 3개 중 하나로만 판정한다.

### 3.1 PRIMITIVE_PORTABLE
아래를 모두 만족할 때 부여한다.

- friend source 코드에서 core primitive가 명확히 읽힌다.
- 현재 프로젝트 구조를 깨지 않고 추가 가능하다.
- 직장인형 저빈도 운영 원칙과 충돌하지 않는다.
- canonical / handoff / Main Run / Compare Run 구분을 흔들지 않는다.
- 추가 overlay 없이도 “기능 단위”로 코드베이스 편입 정의가 가능하다.

### 3.2 PRIMITIVE_PORTABLE_WITH_OVERLAY
아래를 만족할 때 부여한다.

- friend source 코드에서 core primitive는 읽힌다.
- 다만 현재 프로젝트에 붙이려면 별도 trigger / policy / selection context / risk policy 같은 overlay가 필요하다.
- 즉, primitive 자체는 이식 가능하지만 현재 프로젝트의 목적에 맞게 쓰려면 다음 스텝 분리가 필요하다.

### 3.3 NOT_PORTABLE
아래 중 하나라도 해당되면 부여한다.

- friend source 코드에서 core primitive가 명확히 읽히지 않는다.
- 해석·추정이 너무 많이 섞인다.
- 현재 프로젝트 구조 또는 직장인형 운영 원칙과 충돌한다.
- 실시간 외부 의존 또는 전업 운영 리듬이 사실상 필수다.
- primitive가 아니라 사실상 인간 판단 규칙이 핵심이다.

---

## 4. 판정 기준

이번 Step11A는 아래 5개 기준으로만 본다.

### C1. Source readability
- 이 후보가 friend source 코드에서 실제로 읽히는가?
- 파일 / 함수 / 규칙 단위로 지목 가능한가?

### C2. Primitive purity
- 이것이 core primitive 자체인가?
- 아니면 trigger 수치, 운영 습관, 인간 해석이 섞인 overlay인가?

### C3. Structural compatibility
- 현재 프로젝트의 canonical / handoff / 연구용 UI / 운영용 UI 방향과 충돌하지 않는가?
- 기존 closeout 축을 억지 재개하는 방식이 아닌가?

### C4. Operating compatibility
- 직장인형 저빈도 운영에 맞는가?
- 장중 대응, 상시 감시, 외부 뉴스 해석이 필수인가?

### C5. Step separability
- 지금 이 스텝에서 portability까지만 말할 수 있는가?
- 성능 논쟁, gate 논쟁, UX 논쟁을 같이 끌고 오지 않고 다음 스텝으로 분리 가능한가?

---

## 5. 후보 분류 체계

이번 Step11A에서 후보는 아래 4개 분류로 관리한다.

### A. 코드 추출 후보
friend source 코드에서 직접 읽히는 primitive 후보.

예상 대상:
- S1 관련 이동평균 primitive(ALMA 등)
- S2 점수 정규화 primitive
- S3 다중 규칙 조합 primitive
- S4 데이터 충분성 처리 primitive
- S5 반복 정규화 allocation primitive

### B. Overlay 필요 후보
primitive 자체는 있으나 현재 프로젝트에 맞추려면 해석 또는 정책을 덧붙여야 하는 후보.

예상 대상:
- S1 조기경보형 regime trigger 해석
- S5를 현재 risk-aware equal weight 구조에 연결하는 방식

### C. 운영 UX 참고 후보
현재 Step11A의 본론은 아니지만, 이후 operator UX / decision loop에 참고할 수 있는 구조.

예상 대상:
- U1 / U2 / U4 계열 화면 구조 또는 운영 흐름 참고점

### D. 인간 판단 규칙 경계 항목
코드 추출 대상이 아닌 항목. Step11A에서 코드 후보로 다루지 않는다.

예상 대상:
- 뉴스 해석
- veto
- 장중 상황 판단
- 전업 운영 습관

---

## 6. 이번 Step11A의 입력

이번 설계에서 읽는 입력은 아래뿐이다.

1. 프로젝트 불변 문서
   - ORIGIN_INTENT.md
   - KILL_SWITCHES.md
   - ASSUMPTIONS_UNDER_QUESTION.md

2. Step11A 전용 문서
   - STEP_INTENT.md
   - STEP_KILLSWITCHES.md
   - STEP_ASSUMPTIONS.md

3. friend source에서 실제로 확인 가능한 코드 구조 또는 추출 메모

4. 기존 Step11A 초안 및 종합의견
   - 단, 초안은 정답이 아니라 참고 입력으로만 사용한다.

---

## 7. 이번 Step11A의 출력

이번 Step11A에서 최종 출력은 아래 3개만 허용한다.

### O1. Step11A portability 기준 요약
- 이번 스텝이 무엇을 보고 무엇을 보지 않는지

### O2. 후보별 portability 판정표
각 후보마다 아래 항목만 기록한다.

- 후보명
- 후보 분류
- friend source에서 읽히는 primitive
- overlay 필요 여부
- 직장인형 운영 충돌 여부
- portability 판정
  - PRIMITIVE_PORTABLE
  - PRIMITIVE_PORTABLE_WITH_OVERLAY
  - NOT_PORTABLE
- 한 줄 근거

### O3. 다음 단계 1개
아래 중 하나만 허용한다.

- portability 결과 문서 확정
- 추가 source evidence 확보
- Step11A 중단

---

## 8. 후보별 초기 설계 프레임

아래는 현재 기준의 초기 프레임이며, 본 판정은 Step11A 본문에서 확정한다.

### S1. ALMA 계열
- 현재 위치: 코드 추출 후보 + overlay 필요 후보
- 이유: ALMA 자체는 primitive로 식별 가능성이 높다.
- 주의: 조기경보 trigger, regime 해석, episode 운영 규칙은 Step11A 범위 밖이다.
- 초기 판정 방향: PRIMITIVE_PORTABLE 또는 PRIMITIVE_PORTABLE_WITH_OVERLAY 중 하나

### S2. 0중심 부호 보존 백분위 점수
- 현재 위치: 코드 추출 후보
- 이유: ranking primitive로 읽힐 가능성은 있다.
- 주의: MDD 개선 논쟁은 이번 Step11A에서 금지.
- 초기 판정 방향: PRIMITIVE_PORTABLE 가능성 검토

### S3. MA_RULES 기반 다중 규칙 조합
- 현재 위치: 코드 추출 후보
- 이유: 구조 primitive로 볼 수 있다.
- 주의: selection 강화와 성능 공격은 분리한다.
- 초기 판정 방향: PRIMITIVE_PORTABLE 또는 WITH_OVERLAY 검토

### S4. 데이터 충분성 완화
- 현재 위치: 코드 추출 후보
- 이유: rule primitive로는 읽힐 수 있다.
- 주의: 현재 KRX 유니버스 실익과는 별개로 portability만 본다.
- 초기 판정 방향: PRIMITIVE_PORTABLE 가능성 검토

### S5. min/max 반복 정규화 allocation
- 현재 위치: 코드 추출 후보 + overlay 필요 후보
- 이유: allocator primitive로 식별 가능성이 높다.
- 주의: drawdown 개선 주장, 회피 기동 필요성 논쟁은 Step11A 밖이다.
- 초기 판정 방향: PRIMITIVE_PORTABLE_WITH_OVERLAY 가능성 우선 검토

### U1 / U2 / U4. 운영 UX 참고 후보
- 현재 위치: 운영 UX 참고 후보
- 이유: portability 판정의 본론은 아니며 Step11B 입력 성격이 강하다.
- 주의: 현재 canonical / handoff 구조를 흔들면 탈락.
- 초기 판정 방향: 코드 portability 대상이 아니라 별도 참고 메모 처리

### 인간 판단 규칙 후보
- 현재 위치: 경계 항목
- 이유: 코드가 아니라 인간 의사결정 입력이다.
- 초기 판정 방향: NOT_PORTABLE

---

## 9. 중단 조건

이번 Step11A는 아래 중 하나면 즉시 중단한다.

1. portability 판정이 아니라 성능 논쟁으로 흐를 때
2. primitive와 overlay를 구분하지 못할 때
3. friend source 코드에서 실제 근거를 못 찾고 감상으로 흐를 때
4. 직장인형 저빈도 운영 원칙과 충돌하는데도 억지로 살리려 할 때
5. U1/U2/U4 같은 UX 참고항목을 코드 portability 후보처럼 밀어붙일 때
6. 인간 판단 규칙을 코드 후보로 변환하려 할 때
7. Step11A 결과를 근거로 바로 rerun / 구현 / 승격으로 건너뛰려 할 때

---

## 10. Step11A 종료 조건

아래 중 하나면 Step11A를 닫는다.

1. 주요 후보의 portability 판정표가 완성됨
2. 필요한 source evidence가 부족하여 추가 확보 단계로 넘김
3. portability 관점에서 의미 있는 후보가 없다고 판정됨

---

## 11. 이번 설계의 기대 결과

이번 설계가 끝나면 적어도 아래는 분리된다.

- 지금 당장 코드로 읽히는 것
- 나중에 overlay 설계가 필요한 것
- 애초에 지금 프로젝트에 들이면 안 되는 것
- 인간 판단 규칙으로 남겨야 하는 것

즉 Step11A의 역할은 "정답 후보 고르기"가 아니라, **friend source를 현재 프로젝트 언어로 번역 가능한 단위로 분해하는 것**이다.

---

## 12. 다음 단계 제안

이번 설계 문서 기준 다음 단계는 하나만 허용한다.

**Step11A portability 판정표 본문 작성**

이 단계에서는 후보별로 실제 판정만 한다.  
구현 지시문, rerun 제안, 승격 논쟁은 다음 단계로 넘긴다.
