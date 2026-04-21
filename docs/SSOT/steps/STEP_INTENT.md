# STEP_INTENT.md

작성 목적: P211-STEP11A의 축소된 목적을 고정한다.
성격: step-level intent
우선순위: 높음
변경 빈도: 낮음

---

## 1. 이 스텝의 역할

Step11A는 **friend source에서 코드로 추출 가능한 core primitive를 식별하고,
현재 프로젝트에 이식 가능한지 판정하는 분석 스텝**이다.

이 스텝은 더 이상 아래를 동시에 하려고 하지 않는다.
- MDD 13% 벽 직접 공격 메커니즘 확정
- gate ledger 상세 설계
- failure traceability 구조 완성
- compare run 설계

이번 스텝은 범위를 줄인다.

---

## 2. Step11A의 축소 목표

이번 스텝의 목표는 2개뿐이다.

1. friend source에서 **core primitive** 를 추출한다.
2. 각 primitive를 현재 프로젝트에 붙일 때,
   **overlay 없이 바로 가져올 수 있는지 / overlay가 필요한지 / 가져오면 안 되는지** 판정한다.

---

## 3. 이번 스텝이 다루는 것

- friend source 코드에서 직접 읽히는 계산 규칙
- primitive 단위 분해
- primitive의 현재 코드베이스 적합성
- overlay 필요 여부 판단
- 이식 금지 판정

---

## 4. 이번 스텝이 다루지 않는 것

- MDD 10% 달성 증명
- MDD 공격 메커니즘 확정
- 상세 gate 설계
- ledger 컬럼 설계
- compare rerun 제안
- 구현 지시문
- Step11B 자동 진입 선언

---

## 5. 판정값

각 후보는 아래 3개 중 하나로만 판정한다.

- `PRIMITIVE_PORTABLE`
  - 현재 코드베이스에 overlay 없이 바로 이식 가능한 primitive

- `PRIMITIVE_PORTABLE_WITH_OVERLAY`
  - primitive 자체는 이식 가능하지만,
    현재 프로젝트에 쓰려면 운영 규칙 / 정책 / 연결 설계가 추가로 필요한 경우

- `NOT_PORTABLE`
  - 현재 프로젝트 원칙과 충돌하거나,
    구조상 가져오면 안 되는 경우

---

## 6. 후보별 고정 질문

각 후보마다 아래만 묻는다.

1. 이 규칙은 friend source 코드에서 실제로 읽히는가?
2. 이것은 core primitive 인가, 아니면 이미 overlay가 섞인 해석인가?
3. 현재 프로젝트 코드베이스에 그대로 붙일 수 있는가?
4. 붙이려면 별도 overlay 설계가 필요한가?
5. 직장인형 저빈도 운영과 충돌하는가?

---

## 7. 산출물

이번 스텝 산출물은 아래 3개뿐이다.

1. core primitive 목록
2. 후보별 portability 판정표
3. 다음 단계 1개

---

## 8. 다음 단계 규칙

Step11A 이후 가능한 다음 단계는 아래 3개뿐이다.

1. Step11A portable primitive 구현 설계 문서화
2. Step11A overlay 필요 후보 분리 분석
3. Step11A 중단

자동으로 Step11B로 가지 않는다.

---

## 9. 마지막 원칙

이번 스텝은 "무엇이 좋아 보이는가"를 고르는 자리가 아니다.
이번 스텝은 **무엇을 지금 가져올 수 있는가**만 냉정하게 가르는 자리다.
