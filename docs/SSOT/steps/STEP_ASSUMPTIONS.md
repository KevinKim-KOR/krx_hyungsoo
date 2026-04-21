# STEP_ASSUMPTIONS.md

작성 목적: Step11A에서만 유효한 가정을 분리 보관한다.
성격: step-level assumptions
우선순위: 높음
변경 빈도: 중간

---

## 1. 사용 규칙

이 문서의 항목은 Step11A 범위 안에서만 관리한다.
상태는 아래 4개를 쓴다.

- OPEN
- WEAK
- STRONGER_BUT_NOT_PROVEN
- REJECTED

Step11A 종료 시 이 문서는 아카이브한다.

---

## 2. 후보별 가정

### S1. ALMA 계열 MA primitive는 코드로 추출 가능하다
- 상태: STRONGER_BUT_NOT_PROVEN
- 이유: friend source의 MA 지원은 primitive 후보로 볼 수 있다.
- 주의: ALMA 기반 trigger 정책까지 source-derived인 척 확장 금지

### S2. 0 중심 부호 보존 백분위 점수는 primitive로 분리 가능하다
- 상태: OPEN
- 이유: ranking 계산 규칙으로는 읽히지만, 현재 프로젝트 적합성은 미확정
- 주의: selection 개선 효과를 곧바로 성능 개선으로 단정 금지

### S3. MA_RULES 기반 다중 규칙 조합은 primitive로 분리 가능하다
- 상태: OPEN
- 이유: 구조적 primitive 가능성은 있으나, 현재 프로젝트에 붙이는 방식은 별도 검토 필요
- 주의: 운영 규칙과 혼합 금지

### S4. 데이터 충분성 완화 규칙은 primitive로 추출 가능하다
- 상태: OPEN
- 이유: 구현 규칙으로는 읽히지만 현재 유니버스 적합성은 미확정
- 주의: "나중에 쓸모 있을 것"이라는 감상으로 승격 금지

### S5. min/max 반복 정규화 allocation은 primitive로 추출 가능하다
- 상태: STRONGER_BUT_NOT_PROVEN
- 이유: allocation 알고리즘 자체는 추출 후보로 볼 수 있다.
- 주의: 이 단계에서 MDD 해결사 프레임으로 확대 금지

### S6. 최근 월간 수익률 curve feature는 Step11A 범위에 맞지 않는다
- 상태: REJECTED
- 이유: Track B 동일 축 재개 명분으로 흐를 위험이 큼
- 주의: Step11A에서 제외

---

## 3. 스텝 운영 관련 가정

### A-S1. Step11A는 portability 판정만으로도 의미가 있다
- 상태: STRONGER_BUT_NOT_PROVEN
- 이유: 범위를 줄이면 문서가 작동할 가능성이 올라감

### A-S2. portability와 overlay 필요 여부를 분리하면 다음 스텝 결정이 쉬워진다
- 상태: OPEN
- 이유: 구현 전의 최소 분류로는 적절해 보임

### A-S3. Step11A에서 gate/ledger를 완성하지 않아도 된다
- 상태: STRONGER_BUT_NOT_PROVEN
- 이유: 종합의견에서 제기된 과대 범위 문제를 줄이는 핵심 가정

---

## 4. 현재 Step11A에서 가장 중요한 질문 Top 3

1. 무엇이 truly source-derived primitive인가
2. 무엇이 primitive는 맞지만 overlay 없이는 못 쓰는가
3. 무엇이 현재 프로젝트 원칙과 충돌해서 가져오면 안 되는가

---

## 5. 마지막 원칙

이번 스텝에서는 성능을 예언하지 않는다.
primitive를 primitive답게 분리해 놓는 것만으로도 충분하다.
