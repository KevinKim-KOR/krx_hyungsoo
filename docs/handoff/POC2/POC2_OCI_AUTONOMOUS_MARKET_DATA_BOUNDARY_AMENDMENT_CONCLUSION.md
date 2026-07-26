# OCI Autonomous Market Data Boundary Amendment — Conclusion

작성일: 2026-07-26
성격: **PC·OCI 역할 경계를 정정하는 문서 전용 STEP.** 코드·DB·Scheduler·crontab·Telegram 동작 변경 없음.
상태: **DONE (문서 전용)** · Low-Frequency Telegram Push Operation v1 은 **PARTIAL** 유지.

---

## 0. 상태 앵커

```text
current_step = OCI_AUTONOMOUS_MARKET_DATA_BOUNDARY_AMENDMENT
low_frequency_push_operation = PARTIAL_BLOCKED_BY_DATA_BOUNDARY
market_holdings_operation = ACTIVE
spike_operation = DISABLED
next_step_gate = LOW_FREQUENCY_TELEGRAM_PUSH_OPERATION_V1_SAME_STEP_CONTINUE
```

---

## 1. 목적

PC 없이 Spike 를 반복 운영하려면 OCI 가 승인 대상의 일별 시세를 스스로 갱신하고 운영 artifact 를 생성할 수 있어야 한다. 이번 정정 **이전** OCI 는 "실행 시점 현재가 조회" 까지만 허용되어 있어 PC 비의존 Spike 운영이 불가했다. 이번 STEP 은 그 역할 경계를 canonical 문서에 정정한다 — 정정 후 OCI 는 승인 대상 자율 시세 갱신·운영 artifact 생성까지 허용된다 (구현이 아니라 **경계 정의만**).

---

## 2. 배경 (직전 세션 실측)

- **builder 는 pykrx 직접 호출**: `build_universe_momentum_result_scored` → `run_universe_refresh` → `score_candidates` → `fetch_one_month_basis` → `stock.get_market_ohlcv()`. SQLite 미경유.
- **OCI `market_data.sqlite` 에 데이터는 있으나 오래됨**: `etf_daily_price` 1.34M 행 · 승인 seed 20종목 + Holdings 시세 존재. 단 **적재가 2026-07-03 에서 중단** = artifact 신선도 상한.
- **`fetch_price_history(ticker)` DB 읽기 함수 이미 존재** → builder 를 DB 읽기로 전환하는 것은 원리적으로 가능하나 신선도 문제는 별개.
- **Spike 차단 진짜 원인 = seed 부재 아님 · 일별 시세가 2026-07-03 에서 중단된 것.**

---

## 3. 역할 경계 (정정 후)

### PC = 대상·기준·전략 결정

- seed 생성·변경·승인
- PARAM 생성·승인
- factor·threshold 결정
- 전체 시장 후보 탐색 · Market Discovery
- ML·백테스트
- 전략 및 판단 기준 결정

### OCI = 승인된 대상·기준의 반복 계산·운영

- 승인된 seed 와 현재 Holdings ticker 확인
- 해당 ticker 의 일별 시세 **증분** 갱신 → 운영 시장 데이터 저장소 갱신
- 승인된 seed·PARAM·기존 산식으로 운영 artifact (Universe 등) 생성
- 실행 시점 현재가 조회
- Holdings 평가 및 Spike 조건 재평가
- Telegram 발송
- freshness·실패·중복 상태 기록

### OCI 금지

- seed 임의 추가·삭제
- 전체 시장 후보 탐색
- 신규 factor·threshold 생성
- PARAM 생성·승격
- 전략 변경
- ML 학습·튜닝
- Holdings 수량·평단 변경
- 자동 주문

```text
PC = 대상·기준·전략 결정
OCI = 승인된 대상과 기준의 반복 계산·운영
```

---

## 4. Evidence 계약

- **PC Published Evidence** (OCI read-only · 변경 불가): seed · PARAM · factor·threshold · 후보 선정 규칙 · 전략/판단 기준.
- **OCI Operational Derived Evidence** (2026-07-26 신설): 일별 시세 저장 결과 · Universe 운영 artifact · Holdings Runtime 평가 · Spike Runtime 신호 · freshness/실행 상태. **Published Evidence 를 변경·대체하지 않는다.**
- **Runtime Evidence** (발송 시점 계산): 현재 가격 · Holdings 현재 평가 · 수익률 · Spike 조건 결과 · as-of. Published Evidence 대체 X.

---

## 5. 데이터 대상 경계

```text
갱신 가능 대상 = 승인된 seed ticker ∪ 현재 Holdings ticker
```

전체 시장 수집 · seed 외 종목 자동 추가 · 신규 후보 탐색 금지. 구체 source · 저장 함수 · 실행 시각 · freshness 수치는 후속 구현 설계에서 확정.

---

## 6. 실패 원칙 (Fail-Closed)

다음 실패 시 관련 artifact 와 Spike 는 Fail-Closed:

- 일별 시세 갱신 실패
- 승인 대상 데이터 누락
- freshness 기준 미달
- artifact 생성 실패
- 승인된 seed·PARAM·산식 불일치

```text
오래된 결과를 최신으로 표시하지 않음
Spike 미발송
sent registry 미기록
Market·Holdings 기존 운영은 유지
```

---

## 7. 문서 변경 범위

- `docs/PROJECT_ORIGIN_INTENT.md` (OCI 승인 대상 자율 시세 갱신·운영 artifact 생성 블록 신설)
- `docs/ASSUMPTIONS.md` §5.2 (OCI 역할 확장 · Operational Derived Evidence 층위 신설 · Fail-Closed · 현재 운영 상태)
- `docs/MASTER_PLAN.md` (OCI 자율 시장 데이터 경계 정정 섹션 신설)
- `docs/KILL_SWITCHES.md` (KS-11 변경 근거 기록 · KS 자체 미변경)
- `docs/STATE_LATEST.md` (이번 STEP 요약 + 상태 앵커)
- `docs/handoff/STATE_LATEST.md` (redirect 최신화)
- `docs/handoff/POC2/POC2_B_NEXT_ACTIONS.md` (§0 상태 반영)
- `docs/backlog/BACKLOG.md` (저빈도 scheduler 항목 상태 정정)
- 신규: 본 문서

---

## 8. 하지 않은 것

시세 수집 코드 구현 · SQLite 갱신 코드 구현 · Universe Builder 수정 · 신규 source 선정 · DB schema 변경 · crontab 수정 · Spike 활성화 · Telegram 발송 · 전체 시장 데이터 수집 · UI·메시지 변경 · ML·백테스트 · 자동 주문.

---

## 9. KS-11 근거

PC 비의존 Spike 운영 목적 + 실측 배경 (builder pykrx 직접 호출 · 시세 2026-07-03 중단) 을 KILL_SWITCHES 에 근거로 기록. **KS-11 자체는 변경/약화하지 않는다.** 규칙 변경이 아니라 운영 정책 결정 근거의 문서화.

---

## 10. 다음 진행

```text
1. Market·Holdings OCI 적용 (완료 2026-07-26)
2. Market 08:00 + Holdings 3슬롯 crontab 등록 (완료)
3. 수동 실행 확인 (완료 · Telegram 4건 수신)
4. Spike cron 비활성 유지 (현재)
5. 본 STEP: OCI 자율 시장 데이터 경계 정의 (완료)
6. 후속 구현: 승인 seed·Holdings ticker 일별 시세 증분 갱신
7. Builder SQLite 연결
8. Spike 실측·등록
9. Low-Frequency Telegram Push Operation v1 최종 PASS
```
