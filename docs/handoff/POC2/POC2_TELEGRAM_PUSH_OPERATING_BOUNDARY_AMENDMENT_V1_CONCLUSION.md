# Telegram Push Operating Boundary Amendment v1 — Conclusion (DONE · PASS)

작성일: 2026-07-24
성격: 문서 정정 STEP. 코드·DB·Frontend·Scheduler·crontab 변경 없음. Telegram 발송 동작 변경 없음.

## 1. 목적

Telegram PUSH 운영 정책과 PC·OCI 역할 경계를 canonical 문서에 정합화. 기존 "일 3회 자동 PUSH" 전역 제한 표현이 다음 두 개념을 혼동하게 하는 문제 해소:

```text
PUSH 종류가 3개
≠
전체 Telegram 알림을 하루 3회로 제한
```

세 PUSH 의 목적:
- Market briefing: 시장 흐름 정기 전달
- Holdings briefing: 보유 종목을 하루 중 여러 시점에 평가
- Spike/Falling Alert: 조건 발생 시에만 예외 알림

또한 기존 문서는 OCI 를 PC publish evidence 조회·발송 평면으로만 규정 → Holdings 발송 시점 평가와 Spike 조건 확인에 필요한 제한적 가격 조회 의도와 충돌.

## 2. 최종 Telegram 운영 계약

### 2.1 전체 원칙

기존 "일 3회 자동 PUSH" 전역 횟수 제한 제거. 각 PUSH 는 별도 계약 (실행 목적 · 평가 주기 · 발송 조건 · 중복 차단 · 미발송 조건 · 사용자에게 요구하는 행동) 을 가진다.

이번 STEP 에서는 구체적인 크론 실행 간격을 확정하지 않는다 (다음 STEP `Low-Frequency Telegram Push Operation v1` 에서).

### 2.2 Market Briefing

```text
평일 08:00 KST
하루 1회 정기 발송
```

목적: 전일 시장 흐름 · 장 시작 전 확인해야 할 시장 방향. 장중 반복 알림으로 변경하지 않는다.

### 2.3 Holdings Briefing

```text
평일 하루 3개 평가·발송 슬롯
- 오전 슬롯: 장 시작 전후 보유 상태 확인
- 장중 슬롯: 장중 평가 변화 확인
- 마감 슬롯: 장 마감 시점 보유 상태 확인
```

- 세 슬롯은 같은 날짜에 각각 발송 가능
- 동일 슬롯 재실행은 중복 차단
- 서로 다른 슬롯은 같은 날짜에도 발송 허용
- 각 메시지에 평가 기준시각 또는 `as-of` 표시
- 동일한 오래된 snapshot 을 세 번 반복 발송하지 않음

Holdings 하루 3회는 전체 PUSH 횟수 제한이 아니다. 정확한 실행 시각은 다음 STEP.

### 2.4 Spike or Falling Alert

기존 고정 15:30 발송 개념 폐기.

```text
고정 발송 시각 없음
고정 발송 횟수 없음
조건 발생형 예외 알림
```

동작:
```text
정해진 운영 간격으로 조건 평가
→ 신호 없음: 미발송
→ 동일 신호 지속: 중복 미발송
→ 신규 신호 발생: 알림
```

평가 간격은 다음 STEP 에서 확정 (기존 가격 조회 경로 · 데이터 source 호출 제약 · 실제 freshness · 처리시간 · 중복 차단 가능 여부 실측 후). 기존 Spike/Falling factor · 산식 · threshold 는 변경하지 않는다.

## 3. 저빈도 운영 정의

시스템 실행 횟수나 고정된 하루 메시지 수가 아니라 다음 의미:

```text
사용자가 시장을 계속 감시하지 않아도 필요한 정보를 받을 수 있음
동일하거나 의미 없는 알림을 반복하지 않음
사용자의 즉각적인 행동을 계속 요구하지 않음
정보 PUSH 와 실제 투자 행동 분리
자동 주문·리밸런싱 없음
```

양립 가능: Holdings 하루 3개 슬롯 · Spike 조건 반복 평가 · 신규 Spike 신호 조건부 알림.
금지: 신호 없는 상태 확인 메시지 · 동일 Spike 반복 · 동일 Holdings 슬롯 재발송 · 매 알림 즉각 매수/매도 요구 · 목적 불분명 PUSH 증가 · Telegram 자동 주문.

## 4. 평가 실행 ↔ 사용자 알림 구분

- **평가 실행**: 시스템이 데이터를 확인하고 조건을 계산하는 행위 (Holdings 현재 평가 · Spike 조건 확인 · 데이터 최신성 확인)
- **사용자 알림**: 평가 결과 중 사용자에게 전달할 필요가 있는 결과만 Telegram 발송

정상 사례:
```text
Spike 평가 7회 · 신호 없음 · Telegram 알림 0회
Spike 평가 7회 · 신규 신호 1건 · Telegram 알림 1회
```

평가 실행 횟수 다수를 저빈도 위반으로 판정하지 않는다. 판정 기준은 **사용자에게 의미 없는 알림 반복 여부**.

## 5. PC · OCI 역할 경계

### 5.1 PC (분석·설계·상세 판단 평면)

- Holdings 입력·관리
- 전략과 PARAM 작성
- Market Discovery
- 후보 비교
- factor·threshold 결정
- 상세 evidence 생성
- PENDING 초안 생성
- 사용자 판단·복기
- ML·백테스트

### 5.2 OCI (Telegram 운영 평면)

**기존 역할** (유지):
- PC publish PARAM/evidence 보관
- Telegram runner 실행
- 발송 registry
- 중복 차단
- 실행 로그·실패 상태 관리

**Telegram 운영 최신성을 위한 제한적 런타임 역할** (2026-07-24 명시 허용):
- 기존 승인된 시세 출처 통한 가격 조회
- 기존 Holdings 의 평가금액·수익률 재계산
- 기존 Spike/Falling 조건 재평가
- 현재 active PARAM 적용
- 조회 성공·실패와 기준시각 (`as-of`) 기록

PC 의 분석 기능을 OCI 로 이전하는 것이 아니다.

### 5.3 OCI 계속 금지

- 신규 전략 생성
- 신규 후보 선정 기준
- factor 추가
- threshold 변경
- 추천 알고리즘 변경
- ML 학습·튜닝
- Holdings 수량·평단 변경
- PARAM 생성·승격
- Market Discovery 구조 변경
- Published Evidence 임의 수정
- 자동 매수·매도
- 주문 실행

## 6. Published Evidence ↔ Runtime Evidence

### 6.1 Published Evidence

```text
PC 생성·승인·publish → OCI read-only
```

예: active PARAM · Market Discovery 후보 · Universe 후보 · ML baseline · PENDING 초안 snapshot · 분석 factor 결과.

OCI 임의 수정 X.

### 6.2 Runtime Evidence

Telegram 발송 시점 OCI 제한적 확인·계산 현재 상태.

예: 현재 가격 · Holdings 현재 평가 · 발송 시점 수익률 · Spike 조건 결과 · 데이터 조회 상태 · `as-of`.

Published Evidence 를 대체·덮어쓰지 않는다.

## 7. 가격 조회 실패 원칙

상태 구분:
```text
sent
no_signal
duplicate
partial
failed
```

- **Market**: 유효 전일 마감 데이터 사용 시 기준일 명시
- **Holdings**: 누락 가격 명확히 표시 · 전체 평가 신뢰성 부족 시 `partial` 또는 `failed` · 이전 가격을 현재 가격처럼 표시 금지
- **Spike**: 최신 시세 확보 실패 시 조건 평가 실패 → `failed` → Telegram 미발송. 조회 실패를 `no_signal` 로 처리하지 않는다.

## 8. KS-11 변경 근거 (KS 자체 미변경)

`docs/KILL_SWITCHES.md` KS-11 섹션에 다음 근거 기록:

```text
2026-07-22 ~ 2026-07-24 사용자 운영 결정

- Mobile Decision Cockpit 은 DEFERRED_BY_USER 상태로 보류
- 현재 모바일 운영 채널은 Telegram PUSH 로 제한
- 전체 PUSH 횟수를 하루 3회로 고정하지 않음
- Market briefing 은 현재 평일 08:00 1회 유지
- Holdings 평가·브리핑은 평일 하루 3개 슬롯으로 운영
- Spike/Falling Alert 는 고정 시각 발송이 아닌 조건 발생형 알림으로 운영
- 평가 실행 횟수와 사용자 알림 횟수를 구분
- 각 PUSH 의 실행·발송 정책은 해당 PUSH 목적에 맞게 결정
- Telegram 운영 최신성을 위해 OCI 의 제한적 런타임 가격 조회 허용
- OCI 의 전략·factor·threshold·ML·Holdings·주문 변경 금지는 유지
```

KS-11 규칙 자체는 수정하거나 약화하지 않는다. 사용자 요청만으로 예외 허용하지 않는다.

## 9. AC 충족 (지시문 §16)

| AC | 상태 |
|---|---|
| AC-1 전역 일 3회 제한 제거 | ✅ |
| AC-2 PUSH 별 독립 운영 정책 기록 | ✅ |
| AC-3 Market 평일 08:00 1회 기록 | ✅ |
| AC-4 Holdings 평일 하루 3개 슬롯 기록 | ✅ |
| AC-5 Spike 조건 발생형 기록 | ✅ |
| AC-6 평가 실행 ↔ 사용자 알림 구분 | ✅ |
| AC-7 저빈도 정의 정정 (알림·개입 최소화) | ✅ |
| AC-8 OCI 제한적 런타임 가격 조회 기록 | ✅ |
| AC-9 Published Evidence read-only 유지 | ✅ |
| AC-10 OCI 전략·factor·threshold·ML·Holdings·주문 금지 유지 | ✅ |
| AC-11 stale 값 발송 금지 원칙 기록 | ✅ |
| AC-12 KS-11 변경 근거 기록 · KS 자체 유지 | ✅ |
| AC-13 MASTER_PLAN·STATE·handoff·BACKLOG 다음 게이트 일치 | ✅ |
| AC-14 코드·DB·Frontend·Scheduler·crontab 변경 없음 | ✅ |

## 10. 문서 정합성 9항 자체 검증 (지시문 §15)

| # | 항목 | 결과 |
|---|---|---|
| 1 | "일 3회 자동 PUSH" 전역 제한 잔존 | ✅ 제거 확인 (PROJECT_ORIGIN_INTENT §OCI 작업 빈도 정정) |
| 2 | Holdings 3 슬롯 ↔ 전체 PUSH 횟수 혼동 | ✅ 분리 명시 |
| 3 | Spike 고정 15:30 잔존 | ✅ "조건 발생형 예외 알림" 로 재정의 |
| 4 | Spike 평가 간격 선확정 | ✅ 이번 STEP 미확정 · 다음 STEP 이관 |
| 5 | OCI "모든 가격 조회 절대 금지" 문구 | ✅ 잔존 없음. 제한적 허용 명시 |
| 6 | OCI 제한적 가격 조회 ↔ 전략 분석 역할 분리 | ✅ ASSUMPTIONS §5.2 명시 |
| 7 | Published Evidence read-only 경계 | ✅ 유지 |
| 8 | KS-11 자체 미변경 | ✅ 본문 유지 · 이력만 추가 |
| 9 | MASTER_PLAN·STATE·handoff·BACKLOG 다음 게이트 일치 | ✅ 모두 `LOW_FREQUENCY_TELEGRAM_PUSH_OPERATION_V1` |

## 11. 최종 상태

```text
current_step = TELEGRAM_PUSH_OPERATING_BOUNDARY_AMENDMENT_V1
status = DONE
completion_judgment = PASS
push_global_daily_count_limit = REMOVED
market_briefing_policy = WEEKDAY_08_00
holdings_briefing_slots_per_weekday = 3
spike_alert_policy = CONDITION_TRIGGERED
oci_runtime_price_refresh = LIMITED_ALLOWED
mobile_operation_mode = TELEGRAM_PUSH_ONLY
next_step_gate = LOW_FREQUENCY_TELEGRAM_PUSH_OPERATION_V1
```

## 12. 다음 STEP

`LOW_FREQUENCY_TELEGRAM_PUSH_OPERATION_V1` — 이번 문서 계약을 실제 저빈도 스케줄에 연결.

**포함 예정**: 현재 OCI scheduler·crontab 상태 실측 · 현재 runtime entrypoint 통일 · Market 정기 발송 · Holdings 3 슬롯 시각 확정 · Spike 조건 평가 간격 확정 · 중복 차단 유지 · no-signal 미발송 유지 · 사용자 Telegram 실제 수신 확인 · 실패 시 재실행·로그 확인 가능한 최소 운영 상태.

**제외**: 모바일 UI · Telegram 판단 버튼 · 판단 기록 저장 · 메시지 내용 고도화 · 신규 데이터 source · factor/threshold 수정 · PC UI 개선 · 실제 주문 · PUSH 종류 추가.
