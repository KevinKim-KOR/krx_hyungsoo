# POC2 Mobile Decision Operating Sequence Anchor

작성일: 2026-07-20  
성격: 사용자 확정 운영 순서 및 재설계 방지 앵커  
적용 범위: MASTER_PLAN / STATE_LATEST / handoff / BACKLOG / 후속 Step 설계

## 1. 확정된 제품 역할

- **PC Workbench**: 보유 현황 관리, 전체 시장·후보 비교, 상세 evidence 검토, 초안 생성 및 복기.
- **Mobile Decision Cockpit**: 핵심 정보만 빠르게 확인하고, 필요하면 상세 evidence를 펼쳐 투자 판단을 기록.
- **증권 앱(영웅문·카카오페이 등)**: 실제 주문·체결.

모바일은 PC 화면의 축소판이 아니다. 모바일은 빠른 판단을 위한 별도 정보 구조를 사용한다.

## 2. 사용자 개입 원칙

정보 PUSH와 관찰 알림은 매 발송 전 사용자 승인을 요구하지 않는다.

사용자가 최종 개입하는 대상은 다음으로 한정한다.

- 매수 판단
- 매도 판단
- 비중 변경
- 종목 교체
- 주문 실행

단순 조회는 판단 기록을 강제하지 않는다.

## 3. 모바일 판단 언어

기존 `Approve / Reject`를 사용자 투자 판단 언어로 사용하지 않는다.

모바일과 PC가 공유할 판단 종류는 후속 설계에서 아래 범주를 기준으로 확정한다.

- 매수 판단
- 매도 판단
- 관망
- 추가 확인 필요

정보 품질 평가는 투자 판단과 분리한다.

- 판단에 도움 됨
- 판단에 도움 안 됨

PC와 모바일에서 입력된 판단은 동일 저장 계약과 동일 기록으로 관리한다.

## 4. 모바일을 여는 상황

모바일 Decision Cockpit은 다음 세 상황에서 사용한다.

1. 저빈도 정기 알림이 도착했을 때
2. Spike·위험 등 예외 알림이 도착했을 때
3. 증권 앱에서 움직임을 발견하고 추가 판단 근거가 필요할 때

이 시스템은 증권 앱을 대체하지 않는다. 시장·보유·위험 evidence를 교차 확인하는 두 번째 판단 화면이다.

## 5. 잠금된 후속 Step 순서

아래 순서는 사용자가 명시적으로 변경하지 않는 한 재배열하지 않는다.

### Step 1 — Mobile Decision Cockpit v1

목표:
- 모바일에서 PENDING 초안과 직접 선택한 ETF를 빠르게 확인
- 핵심 정보 우선, 상세 evidence 접기/펼치기
- 필요할 때 투자 판단과 정보 도움 여부 기록
- PC·모바일 공통 판단 저장
- 기존 PUSH에서 모바일 화면으로 진입 가능한 최소 연결
- 모바일 실제 사용성 및 와이프 이해도 검증

### Step 2 — Low-Frequency Mobile Alert Operation v1

진입 조건: Mobile Decision Cockpit v1 PASS

목표:
- 정기 PUSH와 예외 PUSH의 역할 확정
- Market·Holdings PUSH 통합 여부 결정
- 실제 저빈도 scheduler 운영
- PENDING 초안 생성 또는 초안 도착 알림 리듬 확정
- 중요 변화가 없을 때 미발송

### Step 3 — First Real Decision Cycle v1

진입 조건: 모바일 접근과 저빈도 알림 운영 PASS

목표:
- 실제 사용자 판단 1건 기록
- 매수 판단 / 매도 판단 / 관망 / 추가 확인 필요 중 실제 선택
- 필요하면 실제 거래 여부를 별도로 연결
- 정보 PUSH → 모바일 확인 → 판단 기록의 1회전 검증

### Step 4 — Decision Outcome Ledger v1

진입 조건: First Real Decision Cycle v1 PASS

목표:
- 판단 당시 가격과 evidence snapshot 고정
- 이후 1주·1개월 성과 및 상승·하락폭 연결
- 사용자 판단과 정보 품질 평가 축적

### Step 5 — 판단 품질 개선

진입 조건: 실제 판단 기록이 누적되어 개선 근거가 생김

후보:
- Universe 후보 품질 개선
- ML·백테스트 고도화
- factor·threshold 재검토
- PC UI에 모바일 디자인 언어 역적용

## 5.1 OCI 경계 보완 (Mobile Decision Operating Boundary Amendment v1, 2026-07-20)

기존 문서의 "OCI 순수 read-only" 표현을 다음으로 명확히 한다.

```text
OCI published evidence 는 read-only 다.
사용자의 투자 판단 기록만 별도의 제한된 command 로 저장할 수 있다.
주문 · Holdings 변경 · 시장 데이터 변경 · Universe seed 변경 · PARAM 변경 ·
Telegram 설정 변경 은 허용하지 않는다.
```

판단 기록의 구체 저장 방식(API 경로 · 스키마 · 인증) 은 본 앵커에서 확정하지 않는다. 후속 Step (`Mobile Decision Cockpit v1` → `First Real Decision Cycle v1` 등) 에서 별도 지시문으로 확정한다.

## 6. 순서 변경 금지 규칙

다음은 사용자의 명시적 변경 승인 없이 금지한다.

- Mobile Decision Cockpit PASS 전에 scheduler 운영부터 시작
- 실제 판단 1건 전에 Decision Outcome Ledger 개발
- 실제 판단 사이클 전에 Universe·ML·factor 고도화로 회귀
- 모바일 정보 우선순위가 확정되기 전에 PC UI 전면 개편
- 차단 결함이 아닌 OCI·Telegram 세부 개선을 다음 기능 Step보다 우선
- 기존 Approve / Reject 버튼을 그대로 모바일 투자 판단으로 복제

새 결함이 현재 Step을 사용할 수 없게 만들면 같은 Step에서 최소 수정한다. 새 기능으로 커지면 BACKLOG로 분리한다.

## 7. 문서 반영 위치

### docs/MASTER_PLAN.md

`모바일 판단 운영 순서 앵커` 섹션을 추가하고 §5의 잠금 순서를 canonical 계획으로 기록한다.

### docs/STATE_LATEST.md

현재 상태를 다음으로 기록한다.

- Holdings–Market PENDING Judgment Draft v1: PASS / DONE
- 현재 활성 Step: Mobile Decision Cockpit v1
- 잠금된 다음 순서: Low-Frequency Mobile Alert Operation → First Real Decision Cycle → Decision Outcome Ledger → 판단 품질 개선

### docs/handoff/STATE_LATEST.md

STATE_LATEST의 동일 내용을 curated mirror로 반영한다.

### docs/handoff/POC2_B_NEXT_ACTIONS.md

문서 상단에 본 앵커를 참조하고, 과거의 임의 분기 후보보다 이 순서를 우선하도록 기록한다.

### docs/backlog/BACKLOG.md

- `모바일 최적화`: BACKLOG 유지가 아니라 Mobile Decision Cockpit v1 활성 범위로 승격
- `와이프 UI 이해도 검증`: Mobile Decision Cockpit v1 AC로 승격
- `저빈도 scheduler 운영`: Mobile Decision Cockpit PASS 후 활성화
- `판단 성과 원장`: First Real Decision Cycle PASS 후 활성화
- `Universe·ML 품질 개선`: 실제 판단 사이클과 결과 데이터 확보 후 재검토

### docs/ASSUMPTIONS.md

PC / 모바일 / OCI / 증권 앱의 역할과 최소 사용자 개입 원칙을 운영 전제로 추가한다.

## 8. 문서 우선순위

이 앵커의 결정은 2026-07-20 사용자 확정 사항으로, 이전의 다음-Step 후보·모바일 후순위·1일 3회 고정 PUSH 문구보다 우선한다.

문서 간 충돌이 있으면 다음 순서로 해석한다.

1. 최신 사용자 결정
2. MASTER_PLAN의 본 앵커
3. STATE_LATEST
4. 최신 handoff
5. BACKLOG 재검토 트리거
6. 과거 conclusion 및 이전 분기 후보

## 9. 현재 다음 게이트

```text
next_step_gate = MOBILE_DECISION_COCKPIT_V1
```

다음 설계는 Mobile Decision Cockpit v1 한 Step만 다룬다.