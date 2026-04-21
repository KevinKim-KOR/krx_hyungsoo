# STEP_KILLSWITCHES.md

작성 목적: Step11A에서 즉시 멈춰야 하는 상황만 최소한으로 고정한다.
성격: step-level kill switches
우선순위: 최상
변경 빈도: 낮음

---

## 1. 공통 원칙

아래 중 하나라도 발생하면 해당 후보 또는 Step11A 전체를 중단하거나 보류한다.
이번 스텝에서는 규칙을 늘리지 않고, 스텝 목적을 깨는 경우만 잡는다.

---

## 2. 후보 단위 중단 조건

### KS-S1. source-derived 아님
- friend source 코드에서 직접 읽히는 primitive가 아닌데, 해석이나 추정으로 덧붙인 경우
- 조치: overlay로 분리하거나 보류

### KS-S2. overlay 경계 불명확
- primitive와 운영 규칙이 섞여 있으면 중단
- 조치: core primitive / overlay 분리 전까지 판정 보류

### KS-S3. 저빈도 운영 위반
- 장중 반응형 / 상시 관측형 / 실시간 외부 데이터 필수면 중단
- 조치: NOT_PORTABLE

### KS-S4. canonical/handoff 구조 훼손
- 현재 구조를 바꾸지 않으면 성립하지 않는 제안이면 중단
- 조치: NOT_PORTABLE

### KS-S5. 플랫폼 전환 요구
- MongoDB / Next.js / OAuth / 계정 구조 / 인프라 전체 전환이 전제되면 중단
- 조치: NOT_PORTABLE

---

## 3. 스텝 단위 중단 조건

### KS-S6. 다시 MDD 직접 공격 문서로 커짐
- Step11A가 portability 판정이 아니라 MDD 공격 메커니즘 논쟁으로 커지면 중단
- 조치: STEP_INTENT로 복귀

### KS-S7. gate / ledger 상세 설계를 다시 끌어옴
- 이번 스텝에서 ledger, cause_code, continuity, failed_gate_ids까지 완성하려 들면 중단
- 조치: 후속 스텝으로 분리

### KS-S8. 후보 순위화 시작
- 누가 제일 유력한지, 누가 대표 후보인지 순위화하면 중단
- 조치: portability 판정만 유지

### KS-S9. compare rerun / 구현 지시문으로 이탈
- 분석 스텝인데 rerun 종류, 구현 파일, 수정 지시문까지 넘어가면 중단
- 조치: 다음 스텝으로 분리

---

## 4. 마지막 원칙

이번 스텝은 작아야 한다.
Step11A가 다시 커지는 순간, 지난 핑퐁이 그대로 재발한다.
