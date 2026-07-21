# Mobile Decision Cockpit v1 — DEFERRED CONCLUSION

## 1. 상태

- Step: `Mobile Decision Cockpit v1`
- 최종 상태: `DEFERRED_BY_USER`
- 기능 판정: 구현 중단
- Unit 0: 조사 완료
- Unit 1~3: 미착수
- 코드·DB·Frontend·Scheduler 변경: 없음
- 다음 게이트: `LOW_FREQUENCY_TELEGRAM_PUSH_OPERATION_V1`

이 Step은 FAIL이 아니다. 사용자 운영 판단에 따라 의도적으로 보류한다.

---

## 2. 보류 결정

모바일 접근은 편리하지만, 현재 착수하면 다음 범위가 동시에 필요해진다.

- OCI 웹 Frontend·Backend 배포
- 외부 또는 사설 모바일 접근 경로
- 인증·권한 경계
- 제한된 판단 Write
- PC·모바일 공통 판단 저장
- Deep link와 보안 검증

PC 판단 흐름이 충분히 완성되지 않은 상태에서 위 범위를 진행하면 프로젝트 본체가 모바일 인프라와 보안 작업에 다시 묶일 위험이 크다.

따라서 현재는 Telegram PUSH만으로 운영하고, PC 흐름이 충분히 완성됐다고 사용자가 판단한 뒤 모바일을 다시 검토한다.

---

## 3. Unit 0 조사 결과

### 3.1 현재 인증·접근

- FastAPI에는 인증·권한 미들웨어가 없다.
- 현재 확인된 접근은 PC 로컬 Frontend·Backend 중심이다.
- OCI에서 웹 Frontend·Backend를 외부 또는 모바일용으로 운영한 실측 이력은 없다.
- OCI의 3000/8000 포트를 공용 인터넷에 직접 공개하는 방식은 허용하지 않는다.

### 3.2 기존 Approve·Reject

- `Approve`는 단순 판단 기록이 아니다.
- `PENDING_APPROVAL → DELIVERING` 전환 후 SCP·OCI outbox 전달을 실제로 트리거한다.
- `Reject`는 `REJECTED`로 종결한다.
- 따라서 `Approve = 매수 판단`, `Reject = 매도 판단` 자동 매핑은 금지한다.

### 3.3 PENDING evidence

- Run JSON은 당시 `draft_payload`, `recommendations`, `factor_signals`, Holdings·Market·ML evidence를 포함한다.
- PENDING 초안에 대한 향후 판단 기록은 `run_id` 참조만으로 당시 evidence를 식별할 수 있다.

### 3.4 직접 조회 evidence

직접 조회 판단을 향후 구현할 경우 최신 파일의 `asof`나 `refresh_id` 참조만으로는 당시 화면을 복원하지 못할 수 있다.

재개 시 다음 원칙을 적용한다.

- 사용자가 실제로 본 최소 evidence를 immutable snapshot으로 보존하거나
- 별도 immutable snapshot을 만들고 `snapshot_id`로 참조한다.

최소 snapshot 후보:

- ETF명·ticker
- 데이터 기준일
- 확인 사유
- 핵심 근거
- 반대 근거·주의점
- Holdings 관계
- 기준가격 또는 unavailable
- source artifact 식별 정보

### 3.5 판단 기록 저장 후보

재개 시 신규 DB보다 기존 JSON state 패턴을 우선한다.

- 후보 경로: `state/user_decisions/{decision_id}.json`
- 1판단 1파일
- append-only
- 판단 변경 시 새 기록 생성
- 이전 기록 덮어쓰기 금지
- `decision_id`·`idempotency_key`로 중복 차단

이 저장 계약은 조사 결과이며 현재 구현하지 않는다.

### 3.6 모바일 Web 보안 후보

모바일 Web을 재개한다면 공용 포트 직접 공개는 금지한다.

조사된 후보:

- Tailscale 사설 접근 + Serve HTTPS
- Cloudflare Tunnel + Access
- 공개 HTTPS + Basic Auth는 공격 표면과 운영 부담 때문에 후순위

그러나 1인 프로젝트에서 별도 앱·웹 배포·인증 운영 부담이 크므로 현재 채택하지 않는다.

---

## 4. 재개 방향

모바일을 다시 시작할 때 첫 후보는 모바일 Web이 아니라 `Telegram Cockpit`이다.

예상 흐름:

```text
Telegram PUSH
→ 핵심 근거·주의점 확인
→ 상세 정보 버튼
→ 매수 판단 / 매도 판단 / 관망 / 추가 확인 필요
→ OCI 판단 기록
→ PC에서 복기
```

보안 경계 후보:

- 허용된 Telegram `user_id`와 `chat_id` 일치
- Bot token은 환경변수
- callback에는 opaque ID만 사용
- 중복 callback 차단
- 선택 후 확인 단계를 거쳐 저장
- Holdings·주문·PARAM·시장 데이터 변경 금지
- 실제 주문 기능 추가 금지

현재는 Telegram Cockpit도 구현하지 않는다.

---

## 5. 재검토 트리거

다음 조건을 모두 만족하고 사용자가 명시적으로 재개를 요청할 때만 모바일을 다시 활성화한다.

1. PC에서 Holdings → evidence → PENDING 초안 → 사용자 판단·복기 흐름이 충분히 완성됐다고 사용자가 판단
2. Telegram 저빈도 운영이 실제 스케줄로 안정적으로 동작
3. 모바일 부재가 실제 운영의 차단 사유로 다시 확인
4. 사용자가 `Telegram Cockpit` 재개를 명시적으로 결정

위 트리거 전에는 모바일 Web·Telegram 판단 버튼·모바일 판단 저장을 신규 Step으로 제안하지 않는다.

---

## 6. 현재 운영 방향

현재 모바일 역할은 Telegram 정보 수신으로 제한한다.

```text
PC
= Holdings 관리·상세 분석·PENDING 초안·복기

OCI
= evidence publication·Telegram 저빈도 운영

Telegram
= Market·Holdings·Spike 정보 PUSH 수신

증권 앱
= 실시간 확인·실제 주문
```

Telegram PUSH는 정보 제공이며 실제 매수·매도·주문을 자동 실행하지 않는다.

---

## 7. 잠금 해제 및 다음 순서

기존 모바일 우선 순서는 최신 사용자 결정으로 해제한다.

현재 다음 Step:

```text
Low-Frequency Telegram Push Operation v1
```

단일 목표:

> 이미 검증된 Market·Holdings·Spike Telegram 경로를 실제 저빈도 Scheduler에 연결하고, 사용자 기기에서 운영 1회전을 확인한다.

이 Step에서는 모바일 UI·판단 저장·Telegram Cockpit을 구현하지 않는다.

---

## 8. 문서 반영 대상

- `docs/MASTER_PLAN.md`
- `docs/PROJECT_ORIGIN_INTENT.md`
- `docs/ASSUMPTIONS.md`
- `docs/STATE_LATEST.md`
- `docs/handoff/STATE_LATEST.md`
- `docs/handoff/POC2_B_NEXT_ACTIONS.md`
- `docs/backlog/BACKLOG.md`
- `docs/handoff/POC2_MOBILE_DECISION_OPERATING_SEQUENCE_ANCHOR.md`

신규 문서 실제 배치 경로 (2026-07-22 사용자 확정):

`docs/backlog/POC2_MOBILE_DECISION_COCKPIT_DEFERRED_CONCLUSION.md`

(본 문서 · 사용자가 `docs/backlog/` 에 배치하여 canonical 위치 확정)

기존 앵커 (`docs/handoff/POC2_MOBILE_DECISION_OPERATING_SEQUENCE_ANCHOR.md`) 는 삭제하지 않고 최신 사용자 결정에 의해 superseded 되었음을 표시한다.

---

## 9. 상태 앵커

```text
mobile_decision_cockpit = DEFERRED_BY_USER
mobile_unit_0_research = DONE
mobile_feature_implemented = false
mobile_reentry_candidate = TELEGRAM_COCKPIT
current_operation_mode = TELEGRAM_PUSH_ONLY
next_step_gate = LOW_FREQUENCY_TELEGRAM_PUSH_OPERATION_V1
```