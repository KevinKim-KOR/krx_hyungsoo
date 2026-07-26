# POC2-Step2 Conclusion & Step3 Handoff

작성일: 2026-04-30
작성자: 사용자 본인 (지시문 원본) + 개발자 저장
대상: 다음 세션 진입자 (Step3 설계자 / 개발자)
성격: Step2 종료 선언 + Step3 진입 가드. 본 문서는 Step3 의 구체 구현을 미리 정하지 않는다.

---

## 1. 현재 위치

현재 프로젝트는 `POC2-Step2D — Approval Draft Preview Separation`까지 완료되었다.

Step2D는 검증자 OK 및 사용자 실제 테스트를 통해 PASS로 판단한다.

확인된 사항:
- 승인 초안 영역이 `message_text` 미리보기 중심으로 변경됨
- `message_text`는 백엔드에서 생성되어 Run top-level 필드로 저장됨
- Run 조회 API 응답에 `message_text` 포함
- 프론트엔드는 `message_text`를 직접 조립하지 않고 원본 문자열을 그대로 렌더링
- 전체 요약은 기본 노출
- 계좌별 요약과 compact table은 근거 데이터 접힘 안으로 이동
- 기존 승인/OCI/Telegram 경로 유지
- Telegram 수신까지 사용자 테스트로 확인
- pytest 82개 통과

검증 보고 기준으로 Step2D의 AC는 모두 충족되었다.

---

## 2. POC2-Step2 전체 Conclusion

POC2-Step2의 목적은 holdings 기반 운영 화면과 승인 흐름을 실제 사용 가능한 수준으로 정리하는 것이었다.

Step2 전체는 아래 기능을 완료한 상태로 닫는다.

### 2.1 Holdings 입력/저장

완료:
- 사용자가 holdings를 UI에서 입력 가능
- 종목코드, 수량, 평균매입단가 등 입력 가능
- account_group 도입
- account_group 기본값/직접입력/정규화/하위호환 처리
- holdings JSON SSOT 저장 유지

판정:
- PASS

### 2.2 시장데이터 시세 갱신

완료:
- Naver 기반 현재가 조회
- 명시적 시세 갱신 버튼 기반 동작
- 페이지 로딩/polling에서 외부 fetch 금지 유지
- market_cache 분리 유지

판정:
- PASS

### 2.3 평가 계산

완료:
- 평가금액
- 평가손익
- 평가수익률
- 시장비중
- 전체 요약
- 계좌별 요약
- 시세 확인/미확인 구분
- 부분 시세 미확인 시 PnL 계산 기준 원금 분리
- 전 종목 시세 미확인 계좌의 계산 불가 처리

판정:
- PASS

### 2.4 UI 압축

완료:
- 긴 카드 나열 방식에서 compact table 중심으로 전환
- 전체 요약 / 계좌별 요약 / compact table 구성
- 상세 정보는 펼침 영역으로 이동
- 동일 계좌/동일 종목 다중 행 key 충돌 방어

판정:
- PASS

### 2.5 Telegram 메시지 요약화

완료:
- Telegram 메시지 길이 초과 방어
- 기본 HOLD 종목 전체 상세 나열 제거
- 전체 요약 + 주목 종목 중심 메시지 구성
- message_text 3500자 이하 안전 한도 적용
- 사용자 실제 Telegram 수신 확인

판정:
- PASS

### 2.6 승인 초안 역할 분리

완료:
- `초안 본문`을 `승인 초안 / 전송 메시지 미리보기` 성격으로 변경
- 백엔드 생성 `message_text` 원본을 preview로 표시
- 전체 요약 기본 노출
- 계좌별 요약 / compact table은 근거 데이터 접힘 안으로 이동
- 과거 run fallback 처리
- raw JSON 기본 노출 방지

판정:
- PASS

---

## 3. Step2 최종 판단

POC2-Step2는 종료한다.

종료 근거:
- holdings 입력 → 시세 갱신 → 평가 계산 → 초안 생성 → 승인 → OCI handoff → Telegram 수신 흐름이 동작한다.
- 화면은 최소 운영 가능한 수준으로 압축되었다.
- Telegram 메시지 길이 문제는 해결되었다.
- 승인 화면은 실제 전송 메시지 중심으로 분리되었다.
- 추가 UI 개선을 계속하는 것은 다음 기능 검증 진입을 지연시킨다.

Step2 이후 더 이상의 UI polish 작업은 진행하지 않는다.

---

## 4. 현재 남은 한계

아래 항목은 Step2 종료를 막지 않는다.

### 4.1 샘플 초안 raw JSON 표시

상태:
- 운영 holdings 흐름에서는 raw JSON 기본 노출이 제거되었다.
- 개발/테스트용 샘플 초안 분기에서는 일부 raw JSON 표시가 남아 있다.

판정:
- 운영 흐름 영향 없음
- Step2D 차단 이슈 아님
- 개발/테스트 영역 분리 시 정리 후보

### 4.2 근거 데이터 접힘 상태 영구 저장 없음

상태:
- 현재 컴포넌트 메모리 기준 유지
- F5 또는 새 run 전환 시 초기화

판정:
- Step2D 차단 이슈 아님
- 사용자 선호 저장 요구가 생길 때 재검토

### 4.3 모바일 최적화 미흡

상태:
- desktop/browser 운영 기준으로 compact table 구성
- 모바일 협소 화면은 별도 최적화하지 않음

판정:
- Step2D 차단 이슈 아님

### 4.4 message_text와 Telegram 렌더 차이 자동 검증 미도입

상태:
- 같은 message_text 원본을 사용
- Telegram 클라이언트 렌더 차이는 수동 확인

판정:
- Step2D 차단 이슈 아님

---

## 5. 절대 주의: 다음 단계 선확정 금지

이 handoff는 다음 단계의 구체 구현을 미리 정하는 문서가 아니다.

절대 금지:
- Step3의 factor 종류를 이 handoff에서 확정하지 않는다.
- Step3의 판단 라벨을 이 handoff에서 확정하지 않는다.
- WATCH / REVIEW / BUY / SELL 등의 라벨을 미리 박지 않는다.
- factor 산식, threshold, Top N 기준을 미리 박지 않는다.
- 친구 프로젝트의 전략이나 화면을 통째로 이식하지 않는다.
- 다음다음 단계 로드맵을 미리 설계하지 않는다.
- UI polish를 이유로 Step3 진입을 지연시키지 않는다.

이 문서가 고정하는 것은 오직 다음이다.

```text
POC2-Step2는 종료한다.
다음 세션은 POC2-Step3 설계에 진입한다.
Step3의 구체 내용은 Step3 설계서에서 다시 검토한다.
```

---

## 6. 다음 Step 진입 기준

다음 Step의 이름은 아래로 둔다.

```text
POC2-Step3 — First Factor Signal Integration
```

단, 이 문서에서 Step3의 factor 종류나 판단 라벨을 확정하지 않는다.

Step3에서 검토해야 할 큰 방향만 남긴다.

Step3의 목적:

* HOLD 고정 초안에서 벗어나, 판단 사유가 있는 초안으로 전진 가능한지 검증한다.
* factor 1개를 초안과 Telegram까지 전달할 수 있는지 검증한다.
* 이때 factor 종류, 라벨, 산식, threshold는 Step3 설계에서 새로 검토한다.

Step3에서 금지할 범위:

* BUY 추천
* SELL 추천
* 자동 리밸런싱
* 주문 계획 생성
* ML 학습
* 여러 factor 동시 추가
* pykrx/yfinance 추가
* 계좌별 세금 판단
* UI 대개편
* Telegram 메시지 디자인 개선
* 친구 프로젝트 전략 통째 이식

---

## 7. Step3 종료 조건

Step3는 아래 조건을 만족하면 종료한다.

1. factor 1개가 계산된다.
2. factor 결과가 `draft_payload`에 반영된다.
3. factor 결과가 승인 초안 화면에 표시된다.
4. factor 결과가 `message_text`에 반영된다.
5. 승인 후 Telegram에서 factor 기반 판단 사유를 확인한다.
6. 기존 승인/OCI/Telegram 경로가 유지된다.
7. BUY / SELL / 리밸런싱 / ML 확장은 발생하지 않는다.

표현 다듬기는 최소 가독성만 포함한다.

포함:

* 사람이 읽을 수 있는 판단 사유 문장

제외:

* 문장 톤 고도화
* Telegram 디자인 개선
* UI 문구 대대적 정리
* 리포트 문장 품질 개선
* 여러 문장 버전 실험

---

## 8. ASSUMPTIONS Q1 연결

Step3 설계서에는 ASSUMPTIONS Q1 연결을 반드시 명시한다.

Q1의 핵심:

* 이 시스템이 단순 보유현황 표시를 넘어,
* 사용자의 투자 판단에 도움이 되는 초안을 만들 수 있는가.

Step3는 Q1을 검증하는 첫 기능 단계다.

Step3 성공의 의미:

* 단순 HOLD 고정 초안에서 벗어남
* factor 기반 판단 사유가 초안과 Telegram에 도달함
* 시스템이 단순 UI/전송 도구에서 투자 판단 보조 도구로 전진함

Step3 실패의 의미:

* 프로젝트가 holdings 표시/전송 시스템에 머묾
* 투자 판단 보조라는 원래 목표로 전진하지 못함

주의:

* Q1 연결은 Step3 설계서에서 명시한다.
* 이 handoff에서 factor의 구체 내용까지 정하지 않는다.

---

## 9. STATE_LATEST.md 동기화 기준

`docs/STATE_LATEST.md` 또는 현재 프로젝트에서 사용하는 최신 상태 문서에는 아래 내용을 반영한다.

### 9.1 현재 상태

```text
현재 단계: POC2-Step2D 완료
POC2-Step2 전체 종료
다음 단계: POC2-Step3 — First Factor Signal Integration 설계 진입
```

### 9.2 Step2 완료 요약

```text
POC2-Step2는 holdings 입력/저장, account_group, Naver 시세 갱신, 평가 계산, compact table, Telegram message compaction, 승인 초안 preview 분리까지 완료했다.
사용자 테스트 기준 Telegram 수신까지 확인했다.
```

### 9.3 다음 단계 주의사항

```text
다음 세션은 Step3 설계에 진입한다.
Step3의 factor 종류, 라벨, 산식, threshold는 이 handoff에서 확정하지 않는다.
Step3 설계서에서 다시 검토한다.
추가 UI polish Step으로 우회하지 않는다.
ASSUMPTIONS Q1과 명시적으로 연결한다.
BUY/SELL/리밸런싱/ML 확장은 금지한다.
```

### 9.4 금지사항

```text
- Step3 factor 종류 선확정 금지
- WATCH/REVIEW 등 라벨 선확정 금지
- 다음다음 단계 로드맵 선설계 금지
- UI polish로 Step3 진입 지연 금지
- 친구 프로젝트 통째 복제 금지
```

---

## 10. 최종 선언

POC2-Step2는 종료한다.

다음은 아래 단계의 설계 진입이다.

```text
POC2-Step3 — First Factor Signal Integration
```

단, Step3의 factor 종류, 라벨, 산식, threshold는 아직 확정하지 않는다.

Step3는 반드시 별도 설계서에서 검토한다.
