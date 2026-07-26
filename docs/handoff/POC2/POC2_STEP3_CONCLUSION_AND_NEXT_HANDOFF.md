# POC2-Step3 Conclusion & Next Handoff

작성일: 2026-04-30
작성자: 사용자 본인 (지시문 원본) + 개발자 저장
대상: 다음 세션 진입자 (다음 Factor 방향 검토 설계자)
성격: Step3 종료 선언 + 다음 단계 진입 가드. 본 문서는 다음 단계의 구체 구현(ML / sector discovery / BUY·SELL 등) 을 미리 정하지 않는다.

---

## 1. 현재 상태

```text
POC2-Step3 — First Factor Signal Integration 완료
첫 factor: portfolio_concentration_v1
표시명: 보유 비중 영향
상태: PASS
```

표현 가드:
- Step3 결과를 "전쟁 승리 / 핵심 목표 달성 / 투자 판단 엔진 완성 / ML 확장 검증 완료 / 잘 올라가는 섹터 발굴 가능" 으로 쓰지 않는다.
- Step3 는 다음만 의미한다.
  - 첫 factor 배관 검증 완료
  - factor 1개가 draft_payload / UI / message_text / Telegram 까지 전달됨
  - 기존 승인/OCI/Telegram 경로 유지 확인

---

## 2. Step3 완료 근거

1. factor 1개가 계산됨 (`app/factors/portfolio_concentration.py::build_factor_signals`)
2. factor 결과가 `draft_payload.factor_signals` 에 반영됨 (Step3 한정 명시 승인된 5번째 키)
3. 승인 초안 UI 에 [판단 사유] 섹션으로 표시됨 (`RunPanel.tsx::JudgmentReasonSection`)
4. `message_text` 에 factor 판단 사유 1줄 반영됨 (`draft_message.py::_render_judgment_lines`)
5. 승인 후 Push/Telegram 문구에서 factor 판단 사유 확인됨 (사용자 디바이스 검증 결과)
6. 기존 승인/OCI/Telegram 경로가 유지됨 (Step2D 단일 소스 정책 — preview / OCI handoff / Telegram 모두 동일 Run.message_text)
7. BUY / SELL / 리밸런싱 / ML 확장은 발생하지 않음
8. pytest 93 passed (Step2D 82 + Step3 신규 11)

Push/Telegram 확인 문구 (사용자 디바이스 수신 본문 중 핵심 1줄):

```text
[판단 사유]
- 보유 비중 영향: 평가 계산 가능 보유분 중 KODEX 미국 S&P500의 비중이 가장 큽니다. 현재 초안은 이 종목의 가격 변동 영향을 상대적으로 크게 받습니다.
```

---

## 3. ASSUMPTIONS 정리

### 3.1 Q1. 여러 factor 를 붙일 수 있는 구조의 엔진이 될 것인가?

```text
상태: OPEN 유지 권고
```

이유:
- Step3 는 factor 1개가 기존 승인 루프를 통과할 수 있음을 보여준 1차 증거다.
- 그러나 다음은 아직 검증되지 않았다.
  - 여러 factor 확장
  - 두 번째 factor 추가 비용
  - ML feature 연결 난이도

Q1 에 대한 정확한 결론:
- Q1 은 ANSWERED 가 **아니다**.
- Q1 은 OPEN 유지가 맞다.
- 다만 Step3 결과는 Q1 검증을 위한 **첫 번째 긍정 증거** 로 기록한다.

---

### 3.2 Q2. OCI 푸쉬 파이프라인이 실제로 동작하는가?

```text
상태: ANSWERED 이동 완료 (A-4)
```

이유:
- POC1-Step3 의 실 OCI handoff + Telegram 발송 end-to-end 검증, 그리고 POC2-Step2D / Step3 종료 시점의 사용자 디바이스 수신 확인으로 답이 나왔다.
- 다만 spike_watch / holding_watch / 자연 cron / 복수 알림 경로 통합은 별도 BACKLOG 또는 별도 STEP 에서 검토한다.

---

### 3.3 Q4. "잘 올라가는 섹터 발굴" 은 holdings 분석 factor 와 별도 축으로 설계해야 하는가?

```text
상태: OPEN
```

중요한 해석:
- Step3 의 `보유 비중 영향` factor 는 holdings 내부 분석 factor 다.
- 사용자가 1년 뒤 원하는 "잘 올라가는 섹터 발굴", 즉 "잘 달리는 말 찾기" 는 아직 구현되지 않았다.
- 이는 현재 보유 종목 설명과 다른 축이며, 다음 Factor 도입 검토 전 별도 검토가 필요하다.

반드시 박아두는 문장:

```text
Step3 완료는 "잘 달리는 말 찾기" 기능의 완료가 아니다.
Step3 는 factor 배관 검증이며, sector discovery / momentum discovery / ML 판단으로 진입한 단계가 아니다.
```

---

## 4. BACKLOG / 보류 항목

각 항목은 (보류 사유 / 보류된 위험 / 재검토 트리거) 로 정리한다.
세부 BACKLOG 본문은 `docs/backlog/BACKLOG.md` 에 누적된다 (이번 문서는 인덱스만).

### 4.1 잘 올라가는 섹터 발굴 Factor
- 보류 사유: holdings 내부 분석 factor 와 다른 축. Step3 범위가 아님.
- 보류된 위험: 사용자 1년 목표("잘 올라가는 섹터")가 holdings 설명만으로는 충족되지 않는다.
- 재검토 트리거: 보유 종목과 무관한 시장/섹터 후보군 탐색 구조를 설계할 때.

### 4.2 factor 별 Top N / 랭킹 정책
- 보류 사유: Step3 message_text 정책상 portfolio-level 판단 사유 1줄 + max_weight_row 1개로 고정.
- 보류된 위험: factor 결과가 늘어나면 UI 와 Telegram 표시 범위가 충돌할 수 있다.
- 재검토 트리거: 사용자가 Telegram 에서 factor 기준 상위/하위 종목을 더 보고 싶다고 명시할 때.

### 4.3 여러 factor 동시 추가
- 보류 사유: Step3 는 factor 1개 통합 검증. 동시 추가는 Q1 의 두 번째 증거가 필요한 시점에 검토.
- 보류된 위험: 한꺼번에 여러 factor 를 추가하면 reason_text / message_text / UI 영역 책임 경계가 흐려진다.
- 재검토 트리거: 두 번째 factor 추가 비용이 충분히 작음(10줄 이내) 을 확인한 직후.

### 4.4 ML 기반 draft 생성기 연결
- 보류 사유: Step3 는 정적 stub 기반 reason_text. ML 연결은 별도 STEP.
- 보류된 위험: Phase 1 격리 모듈을 끌어오는 순간 학습/예측 데이터 파이프라인 결정이 한꺼번에 들어온다.
- 재검토 트리거: ASSUMPTIONS Q1 의 "10줄 이내 factor 추가" 가 충족된 후.

### 4.5 두 번째 factor 추가 시 구조 반복성 검증
- 보류 사유: Q1 의 진짜 증거는 두 번째 factor 추가 비용 측정에서 나온다.
- 보류된 위험: 첫 factor 만 보고 Q1 을 ANSWERED 로 옮기면 일반화 실패 위험.
- 재검토 트리거: 다음 factor 방향 결정 직후, 첫 1~2일 작업량 측정.

### 4.6 테스트 파일 분리 또는 테스트 구조 정리
- 보류 사유: tests/test_poc1_loop.py 약 2,400 라인 — 이미 BACKLOG 트리거 근접.
- 보류된 위험: 단일 파일이 비대해지며 다음 STEP 에서 추가될 factor 테스트가 누적되면 검색 비용 증가.
- 재검토 트리거: 다음 STEP 진입 전, 또는 한 파일 ~3,000 라인 도달 시.

### 4.7 max_weight_row 동률 처리 정책 고도화
- 보류 사유: 현재는 source_index 작은 쪽 우선 (결정론적이지만 사용자 의도와 다를 가능성).
- 보류된 위험: 동률 사례가 빈번한 운영에서 사용자가 "왜 이 종목이 뽑혔나" 질문할 수 있음.
- 재검토 트리거: 동률 케이스가 운영 중 1회라도 사용자 혼동을 일으킬 때.

### 4.8 draft_payload.factor_signals 외 다른 메타 키 추가 금지 가드 명문화
- 보류 사유: Step3 한정 5번째 키 명시 승인. 일반 허용 아님.
- 보류된 위험: 향후 STEP 에서 "이왕 factor_signals 가 있으니 또 다른 메타 키도..." 로 확장되면 Step2D 의 4필드 draft_payload 정신이 흐려진다.
- 재검토 트리거: 새 STEP 지시문에서 추가 메타 키 도입을 명시 요청할 때만.

---

## 5. 다음 단계 진입 가드

다음 단계로 **바로 구현하지 않는다**.

먼저 다음 Factor 방향을 결정해야 한다.

```text
다음 단계는 바로 ML 구현이 아니다.
다음 단계는 바로 "잘 올라가는 섹터 발굴" 구현도 아니다.
```

다음 단계에서 검토해야 할 질문 5개 (선결정 금지, 답을 미리 박지 말 것):

1. 다음 factor 도 holdings 내부 분석 factor 로 갈 것인가?
2. 아니면 Q4 에 따라 시장/섹터 발굴 축을 별도로 열 것인가?
3. sector discovery 를 하려면 어떤 유니버스, 데이터 소스, 판단 사유 구조가 필요한가?
4. ML 은 언제 연결할 것인가?
5. Q1 을 계속 OPEN 으로 둘지, CHECKING 으로 바꿀 근거가 충분한가?

---

## 6. 절대 쓰지 않을 표현 (재확인)

이 conclusion 문서가 다음 단계를 잘못 유도하지 않도록 가드.

```text
- 프로젝트 핵심 목표 달성
- ML 준비 완료
- sector discovery 준비 완료
- 잘 올라가는 섹터 발굴 가능
- 다음 단계에서 ML 바로 구현
- 다음 단계에서 BUY/SELL 추천 구현
- 다음 단계에서 리밸런싱 구현
- 다음 단계에서 신규 외부 API 확정
- 다음 단계에서 pykrx/yfinance 확정
- 다음 단계에서 factor threshold 확정
```

이 문서가 고정하는 것은 오직 다음이다:

```text
POC2-Step3 는 PASS 로 닫는다.
다만 Q1 은 OPEN 유지 권고다.
Step3 는 첫 factor 배관 검증이지, ML 진입도 아니고 "잘 달리는 말 찾기" 도 아니다.
다음은 Step3 conclusion 확인 후, 다음 Factor 방향 검토 설계로 간다.
```

---

## 7. STATE_LATEST 동기화 기준

### 7.1 현재 상태

```text
현재 단계: POC2-Step3 완료
다음 단계: POC2-Step3 Conclusion 확인 후, 다음 Factor 방향 검토
```

### 7.2 Step3 완료 요약

```text
보유 비중 영향 factor 1개가 draft_payload.factor_signals, 승인 초안 UI, message_text,
Telegram/Push 문구까지 전달됨을 확인했다.
```

### 7.3 주의

```text
Q1 은 ANSWERED 가 아니라 OPEN 유지 권고.
Step3 는 "잘 달리는 말 찾기" 또는 "잘 올라가는 섹터 발굴" 완료가 아니다.
Q4 는 OPEN 으로 유지하고, 현재 Factor 추가 작업 후 다음 Factor 도입 검토 전에 검토한다.
```

---

## 8. 최종 선언

POC2-Step3 는 PASS 로 닫는다.

다만 다음을 잊지 않는다.

```text
이 PASS 는 첫 factor 배관 검증의 PASS 다.
프로젝트 전체 목표 달성의 PASS 가 아니다.
Q1 은 OPEN 유지가 맞다.
Q4 는 OPEN 으로 별도 축에 둔다.
다음은 다음 Factor 방향 검토 설계다.
```
